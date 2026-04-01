from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
import json
import os
import sqlite3
import uuid
from datetime import date, datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "biosolutions-dev-secret-change-this")
DB_PATH = "biosolutions.db"

UPLOAD_SUBDIR = os.path.join("uploads", "cotizaciones")
UPLOAD_DIR = os.path.join(app.static_folder, "uploads", "cotizaciones")
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


def ensure_upload_dir():
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def allowed_image_file(filename):
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS


def normalize_image_path_for_db(image_value):
    image_value = (image_value or "").strip()
    if not image_value:
        return ""

    if image_value.startswith("/static/"):
        return image_value.replace("/static/", "", 1)

    if image_value.startswith("static/"):
        return image_value.replace("static/", "", 1)

    return image_value

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_payload_json_column(conn):
    columns = conn.execute("PRAGMA table_info(cotizaciones)").fetchall()
    column_names = [col["name"] for col in columns]

    if "payload_json" not in column_names:
        conn.execute("ALTER TABLE cotizaciones ADD COLUMN payload_json TEXT")
        conn.commit()

def ensure_users_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            nombre TEXT,
            rol TEXT NOT NULL DEFAULT 'editor',
            activo INTEGER NOT NULL DEFAULT 1,
            creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def ensure_cotizaciones_audit_columns(conn):
    columns = conn.execute("PRAGMA table_info(cotizaciones)").fetchall()
    column_names = [col["name"] for col in columns]

    if "creado_por_user_id" not in column_names:
        conn.execute("ALTER TABLE cotizaciones ADD COLUMN creado_por_user_id INTEGER")
    if "actualizado_por_user_id" not in column_names:
        conn.execute("ALTER TABLE cotizaciones ADD COLUMN actualizado_por_user_id INTEGER")
    if "creado_en" not in column_names:
        conn.execute("ALTER TABLE cotizaciones ADD COLUMN creado_en TEXT")
    if "actualizado_en" not in column_names:
        conn.execute("ALTER TABLE cotizaciones ADD COLUMN actualizado_en TEXT")

    conn.commit()


def ensure_auth_schema(conn):
    ensure_users_table(conn)
    ensure_payload_json_column(conn)
    ensure_cotizaciones_audit_columns(conn)


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    conn = get_db_connection()
    user = conn.execute("""
        SELECT id, username, nombre, rol, activo
        FROM usuarios
        WHERE id = ? AND activo = 1
    """, (user_id,)).fetchone()
    conn.close()
    return user


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapper


def editor_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("login", next=request.path))
        if user["rol"] not in ("admin", "editor"):
            flash("No tienes permisos para realizar esta acción.", "error")
            return redirect(url_for("dashboard"))
        return view_func(*args, **kwargs)
    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("login", next=request.path))
        if user["rol"] != "admin":
            flash("Solo un administrador puede realizar esta acción.", "error")
            return redirect(url_for("dashboard"))
        return view_func(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_auth_context():
    user = get_current_user()
    return {
        "current_user": user,
        "current_role": user["rol"] if user else None
    }        

def next_quote_number(conn):
    row = conn.execute("""
        SELECT numero
        FROM cotizaciones
        WHERE numero IS NOT NULL AND numero != ''
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    if not row or not row["numero"]:
        return "COT-001"

    numero = row["numero"]
    try:
        last = int(numero.replace("COT-", "").strip())
    except ValueError:
        last = 0

    return f"COT-{last + 1:03d}"


def build_initial_template_data_from_equipo(equipo_row):
    """
    Construye el snapshot inicial de una plantilla creada desde un equipo maestro.
    Por ahora copiamos los campos base disponibles sin tocar todavía tablas hijas.
    """
    if not equipo_row:
        return {
            "nombre_comercial": "",
            "descripcion_breve": "",
            "descripcion_larga": "",
            "imagen": ""
        }

    descripcion_breve = (equipo_row["descripcion_breve"] or "").strip()
    descripcion_larga = (equipo_row["descripcion_larga"] or "").strip()

    extras = []
    if (equipo_row["origen"] or "").strip():
        extras.append(f"Origen: {equipo_row['origen'].strip()}")
    if (equipo_row["garantia_base"] or "").strip():
        extras.append(f"Garantía base: {equipo_row['garantia_base'].strip()}")

    if extras:
        extras_text = "\n".join(extras)
        if descripcion_larga:
            descripcion_larga = f"{descripcion_larga}\n\n{extras_text}"
        else:
            descripcion_larga = extras_text

    nombre_comercial_base = " ".join(
        part for part in [
            (equipo_row["nombre"] or "").strip(),
            (equipo_row["marca"] or "").strip(),
            (equipo_row["modelo"] or "").strip()
        ]
        if part
    ).strip()

    return {
        "nombre_comercial": nombre_comercial_base,
        "descripcion_breve": descripcion_breve,
        "descripcion_larga": descripcion_larga,
        "imagen": (equipo_row["imagen"] or "").strip()
    }

def get_plantilla_children(conn, plantilla_id):
    especificaciones = conn.execute("""
        SELECT id, parametro, detalle, orden
        FROM plantillas_especificaciones
        WHERE plantilla_id = ?
        ORDER BY orden ASC, id ASC
    """, (plantilla_id,)).fetchall()

    usos = conn.execute("""
        SELECT id, texto, orden
        FROM plantillas_usos
        WHERE plantilla_id = ?
        ORDER BY orden ASC, id ASC
    """, (plantilla_id,)).fetchall()

    accesorios = conn.execute("""
        SELECT id, texto, orden
        FROM plantillas_accesorios
        WHERE plantilla_id = ?
        ORDER BY orden ASC, id ASC
    """, (plantilla_id,)).fetchall()

    ventajas = conn.execute("""
        SELECT id, texto, orden
        FROM plantillas_ventajas
        WHERE plantilla_id = ?
        ORDER BY orden ASC, id ASC
    """, (plantilla_id,)).fetchall()

    return {
        "especificaciones": especificaciones,
        "usos": usos,
        "accesorios": accesorios,
        "ventajas": ventajas,
    }


def replace_plantilla_children(conn, plantilla_id, specs, usos, accesorios, ventajas):
    conn.execute("DELETE FROM plantillas_especificaciones WHERE plantilla_id = ?", (plantilla_id,))
    conn.execute("DELETE FROM plantillas_usos WHERE plantilla_id = ?", (plantilla_id,))
    conn.execute("DELETE FROM plantillas_accesorios WHERE plantilla_id = ?", (plantilla_id,))
    conn.execute("DELETE FROM plantillas_ventajas WHERE plantilla_id = ?", (plantilla_id,))

    for idx, row in enumerate(specs):
        parametro = (row.get("parametro") or "").strip()
        detalle = (row.get("detalle") or "").strip()
        if not parametro and not detalle:
            continue

        conn.execute("""
            INSERT INTO plantillas_especificaciones (
                plantilla_id, parametro, detalle, orden
            )
            VALUES (?, ?, ?, ?)
        """, (plantilla_id, parametro, detalle, idx))

    for idx, texto in enumerate(usos):
        texto = (texto or "").strip()
        if not texto:
            continue

        conn.execute("""
            INSERT INTO plantillas_usos (
                plantilla_id, texto, orden
            )
            VALUES (?, ?, ?)
        """, (plantilla_id, texto, idx))

    for idx, texto in enumerate(accesorios):
        texto = (texto or "").strip()
        if not texto:
            continue

        conn.execute("""
            INSERT INTO plantillas_accesorios (
                plantilla_id, texto, orden
            )
            VALUES (?, ?, ?)
        """, (plantilla_id, texto, idx))

    for idx, texto in enumerate(ventajas):
        texto = (texto or "").strip()
        if not texto:
            continue

        conn.execute("""
            INSERT INTO plantillas_ventajas (
                plantilla_id, texto, orden
            )
            VALUES (?, ?, ?)
        """, (plantilla_id, texto, idx))

@app.route("/")
@login_required
def dashboard():
    return render_template("index.html", active_page="inicio")

@app.route("/login", methods=["GET", "POST"])
def login():
    conn = get_db_connection()
    ensure_auth_schema(conn)
    conn.close()

    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        conn = get_db_connection()
        user = conn.execute("""
            SELECT *
            FROM usuarios
            WHERE username = ? AND activo = 1
        """, (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            next_url = request.args.get("next") or url_for("dashboard")
            return redirect(next_url)

        flash("Usuario o contraseña inválidos.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/usuarios")
@admin_required
def usuarios_page():
    conn = get_db_connection()
    ensure_auth_schema(conn)

    usuarios = conn.execute("""
        SELECT id, username, nombre, rol, activo, creado_en
        FROM usuarios
        ORDER BY id DESC
    """).fetchall()

    conn.close()
    return render_template("usuarios.html", usuarios=usuarios, active_page="usuarios")

@app.route("/usuarios/nuevo", methods=["POST"])
@admin_required
def crear_usuario():
    conn = get_db_connection()
    ensure_auth_schema(conn)

    username = (request.form.get("username") or "").strip()
    nombre = (request.form.get("nombre") or "").strip()
    password = request.form.get("password") or ""
    rol = (request.form.get("rol") or "editor").strip().lower()

    if rol not in {"admin", "editor", "visor"}:
        rol = "editor"

    if not username or not password:
        conn.close()
        flash("Usuario y contraseña son obligatorios.", "error")
        return redirect(url_for("usuarios_page"))

    existing = conn.execute("""
        SELECT id
        FROM usuarios
        WHERE username = ?
    """, (username,)).fetchone()

    if existing:
        conn.close()
        flash("Ese nombre de usuario ya existe.", "error")
        return redirect(url_for("usuarios_page"))

    conn.execute("""
        INSERT INTO usuarios (username, password_hash, nombre, rol, activo)
        VALUES (?, ?, ?, ?, 1)
    """, (
        username,
        generate_password_hash(password),
        nombre,
        rol
    ))

    conn.commit()
    conn.close()

    flash("Usuario creado correctamente.", "success")
    return redirect(url_for("usuarios_page"))

@app.route("/usuarios/<int:user_id>/rol", methods=["POST"])
@admin_required
def actualizar_rol_usuario(user_id):
    nuevo_rol = (request.form.get("rol") or "").strip().lower()

    if nuevo_rol not in {"admin", "editor", "visor"}:
        flash("Rol inválido.", "error")
        return redirect(url_for("usuarios_page"))

    current_user = get_current_user()
    if current_user and current_user["id"] == user_id and nuevo_rol != "admin":
        flash("No puedes quitarte a ti mismo el rol admin desde aquí.", "error")
        return redirect(url_for("usuarios_page"))

    conn = get_db_connection()
    ensure_auth_schema(conn)

    conn.execute("""
        UPDATE usuarios
        SET rol = ?
        WHERE id = ? AND activo = 1
    """, (nuevo_rol, user_id))

    conn.commit()
    conn.close()

    flash("Rol actualizado correctamente.", "success")
    return redirect(url_for("usuarios_page"))

@app.route("/usuarios/<int:user_id>/desactivar", methods=["POST"])
@admin_required
def desactivar_usuario(user_id):
    current_user = get_current_user()
    if current_user and current_user["id"] == user_id:
        flash("No puedes desactivarte a ti mismo.", "error")
        return redirect(url_for("usuarios_page"))

    conn = get_db_connection()
    ensure_auth_schema(conn)

    conn.execute("""
        UPDATE usuarios
        SET activo = 0
        WHERE id = ?
    """, (user_id,))

    conn.commit()
    conn.close()

    flash("Usuario desactivado correctamente.", "success")
    return redirect(url_for("usuarios_page"))
    
@app.route("/upload-image", methods=["POST"])
def upload_image():
    ensure_upload_dir()

    if "image" not in request.files:
        return jsonify({"ok": False, "error": "No se recibió ningún archivo"}), 400

    file = request.files["image"]
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "Archivo inválido"}), 400

    if not allowed_image_file(file.filename):
        return jsonify({"ok": False, "error": "Formato no permitido"}), 400

    original_name = secure_filename(file.filename)
    ext = original_name.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"

    save_path = os.path.join(UPLOAD_DIR, unique_name)
    file.save(save_path)

    relative_path = f"uploads/cotizaciones/{unique_name}"
    public_url = f"/static/{relative_path}"

    return jsonify({
        "ok": True,
        "relative_path": relative_path,
        "url": public_url,
        "filename": unique_name
    })

@app.route("/cotizador")
@login_required
def cotizador():
    conn = get_db_connection()
    ensure_auth_schema(conn)

    plantillas = conn.execute("""
        SELECT p.*, e.nombre AS equipo_nombre, e.marca AS equipo_marca, e.modelo AS equipo_modelo
        FROM plantillas p
        LEFT JOIN equipos e ON e.id = p.equipo_id
        WHERE p.activo = 1
        ORDER BY p.nombre_plantilla ASC
    """).fetchall()

    plantillas_json = []
    for p in plantillas:
        children = get_plantilla_children(conn, p["id"])

        plantillas_json.append({
            "id": p["id"],
            "nombre_plantilla": p["nombre_plantilla"] or "",
            "nombre_comercial": p["nombre_comercial"] or "",
            "equipo_nombre": p["equipo_nombre"] or "",
            "equipo_marca": p["equipo_marca"] or "",
            "equipo_modelo": p["equipo_modelo"] or "",
            "descripcion_breve": p["descripcion_breve"] or "",
            "descripcion_larga": p["descripcion_larga"] or "",
            "imagen": p["imagen"] or "",
            "precio_base": p["precio_base"] or 0,
            "mostrar_precio_por_defecto": p["mostrar_precio_por_defecto"] or 0,
            "especificaciones": [
                {
                    "id": row["id"],
                    "parametro": row["parametro"] or "",
                    "detalle": row["detalle"] or "",
                    "orden": row["orden"] or 0
                }
                for row in children["especificaciones"]
            ],
            "usos": [
                {
                    "id": row["id"],
                    "texto": row["texto"] or "",
                    "orden": row["orden"] or 0
                }
                for row in children["usos"]
            ],
            "accesorios": [
                {
                    "id": row["id"],
                    "texto": row["texto"] or "",
                    "orden": row["orden"] or 0
                }
                for row in children["accesorios"]
            ],
            "ventajas": [
                {
                    "id": row["id"],
                    "texto": row["texto"] or "",
                    "orden": row["orden"] or 0
                }
                for row in children["ventajas"]
            ]
        })

    new_number = next_quote_number(conn)
    conn.close()

    return render_template(
        "cotizador.html",
        active_page="cotizador",
        plantillas=plantillas,
        plantillas_json=plantillas_json,
        new_quote_number=new_number,
        today=str(date.today())
    )

@app.route("/equipos")
@login_required
def equipos_page():
    conn = get_db_connection()

    equipos = conn.execute("""
        SELECT
            e.*,
            COUNT(p.id) AS plantillas_count
        FROM equipos e
        LEFT JOIN plantillas p
            ON p.equipo_id = e.id
           AND p.activo = 1
        WHERE e.activo = 1
        GROUP BY e.id
        ORDER BY e.id DESC
    """).fetchall()

    conn.close()
    return render_template("equipos.html", equipos=equipos, active_page="equipos")

@app.route("/plantillas")
@login_required
def plantillas_page():
    conn = get_db_connection()

    equipo_id_raw = (request.args.get("equipo_id") or "").strip()
    action = (request.args.get("action") or "").strip().lower()

    if action not in {"create", "view"}:
        action = ""

    equipo_id = None
    if equipo_id_raw:
        try:
            equipo_id = int(equipo_id_raw)
        except ValueError:
            equipo_id = None

    equipos = conn.execute("""
        SELECT *
        FROM equipos
        WHERE activo = 1
        ORDER BY id DESC
    """).fetchall()

    selected_equipo = None
    if equipo_id:
        selected_equipo = conn.execute("""
            SELECT *
            FROM equipos
            WHERE id = ? AND activo = 1
        """, (equipo_id,)).fetchone()

        if not selected_equipo:
            equipo_id = None

    filter_by_equipo = bool(equipo_id and action == "view")

    if filter_by_equipo:
        plantillas_rows = conn.execute("""
            SELECT p.*, e.nombre AS equipo_nombre, e.marca AS equipo_marca, e.modelo AS equipo_modelo
            FROM plantillas p
            LEFT JOIN equipos e ON e.id = p.equipo_id
            WHERE p.activo = 1
              AND p.equipo_id = ?
            ORDER BY p.id DESC
        """, (equipo_id,)).fetchall()
    else:
        plantillas_rows = conn.execute("""
            SELECT p.*, e.nombre AS equipo_nombre, e.marca AS equipo_marca, e.modelo AS equipo_modelo
            FROM plantillas p
            LEFT JOIN equipos e ON e.id = p.equipo_id
            WHERE p.activo = 1
            ORDER BY p.id DESC
        """).fetchall()

    plantillas = []
    for p in plantillas_rows:
        children = get_plantilla_children(conn, p["id"])

        plantilla_dict = dict(p)
        plantilla_dict["especificaciones"] = [dict(x) for x in children["especificaciones"]]
        plantilla_dict["usos"] = [dict(x) for x in children["usos"]]
        plantilla_dict["accesorios"] = [dict(x) for x in children["accesorios"]]
        plantilla_dict["ventajas"] = [dict(x) for x in children["ventajas"]]
        plantillas.append(plantilla_dict)

    conn.close()

    return render_template(
        "plantillas.html",
        equipos=equipos,
        plantillas=plantillas,
        active_page="plantillas",
        selected_equipo=selected_equipo,
        selected_equipo_id=equipo_id,
        current_action=action,
        filter_by_equipo=filter_by_equipo
    )
    
@app.route("/cotizaciones")
@login_required
def cotizaciones_page():
    conn = get_db_connection()
    ensure_auth_schema(conn)
    cotizaciones = conn.execute("""
        SELECT
            c.*,
            uc.username AS creado_por_username,
            ua.username AS actualizado_por_username
        FROM cotizaciones c
        LEFT JOIN usuarios uc ON uc.id = c.creado_por_user_id
        LEFT JOIN usuarios ua ON ua.id = c.actualizado_por_user_id
        ORDER BY c.id DESC
    """).fetchall()
    conn.close()
    return render_template("cotizaciones.html", cotizaciones=cotizaciones, active_page="cotizaciones")


@app.route("/cotizaciones/<int:cotizacion_id>/json")
@editor_required
def cotizacion_json(cotizacion_id):
    conn = get_db_connection()
    ensure_payload_json_column(conn)

    cot = conn.execute("""
        SELECT *
        FROM cotizaciones
        WHERE id = ?
    """, (cotizacion_id,)).fetchone()

    if not cot:
        conn.close()
        return jsonify({"error": "Cotización no encontrada"}), 404

    payload_json = (cot["payload_json"] or "").strip()

    if payload_json:
        try:
            payload = json.loads(payload_json)

            if not isinstance(payload, dict):
                raise ValueError("payload_json inválido")

            payload.setdefault("quotation", {})
            payload.setdefault("items", [])
            payload.setdefault("selectedItemId", None)

            payload["quotation"]["dbId"] = cot["id"]
            payload["quotation"]["number"] = payload["quotation"].get("number") or (cot["numero"] or "")
            payload["quotation"]["date"] = payload["quotation"].get("date") or (cot["fecha"] or "")
            payload["quotation"]["client"] = payload["quotation"].get("client") or (cot["cliente"] or "")
            payload["quotation"]["attention"] = payload["quotation"].get("attention") or (cot["atencion"] or "")
            payload["quotation"]["city"] = payload["quotation"].get("city") or (cot["ciudad"] or "")
            payload["quotation"]["validity"] = payload["quotation"].get("validity") or (cot["validez"] or "")
            payload["quotation"]["paymentTerms"] = payload["quotation"].get("paymentTerms") or (cot["forma_pago"] or "")
            payload["quotation"]["notes"] = payload["quotation"].get("notes") or (cot["observaciones"] or "")

            if not payload["selectedItemId"] and payload["items"]:
                payload["selectedItemId"] = payload["items"][0].get("id")

            conn.close()
            return jsonify(payload)

        except Exception as e:
            print("WARNING: payload_json inválido, usando fallback antiguo:", e)

    items = conn.execute("""
        SELECT *
        FROM cotizacion_items
        WHERE cotizacion_id = ?
        ORDER BY orden ASC, id ASC
    """, (cotizacion_id,)).fetchall()

    conn.close()

    payload = {
        "quotation": {
            "dbId": cot["id"],
            "number": cot["numero"] or "",
            "date": cot["fecha"] or "",
            "client": cot["cliente"] or "",
            "attention": cot["atencion"] or "",
            "city": cot["ciudad"] or "",
            "validity": cot["validez"] or "",
            "paymentTerms": cot["forma_pago"] or "",
            "notes": cot["observaciones"] or ""
        },
        "items": [],
        "selectedItemId": None
    }

    for row in items:
        payload["items"].append({
            "id": f"dbitem_{row['id']}",
            "dbItemId": row["id"],
            "title": row["nombre_editado"] or "",
            "brand": row["marca_editada"] or "",
            "model": row["modelo_editado"] or "",
            "origin": "",
            "warranty": "",
            "price": str(row["precio_unitario"] or ""),
            "quantity": str(row["cantidad"] or 1),
            "showPrice": bool(row["mostrar_precio"]),
            "subtitle": row["descripcion_breve_editada"] or "",
            "descriptionLong": row["descripcion_larga_editada"] or "",
            "highlights": [],
            "specs": [],
            "uses": [],
            "accessories": [],
            "advantages": [],
            "imageSrc": f"/static/{row['imagen_editada']}" if row["imagen_editada"] else "",
            "templateId": row["plantilla_id"]
        })

    if payload["items"]:
        payload["selectedItemId"] = payload["items"][0]["id"]

    return jsonify(payload)



@app.route("/cotizaciones/guardar", methods=["POST"])
@editor_required
def guardar_cotizacion():
    conn = None
    try:
        data = request.get_json(force=True)
        print("=== GUARDAR COTIZACION ===")
        print(data)

        quotation = data.get("quotation", {}) or {}
        items = data.get("items", []) or []
        selected_item_id = data.get("selectedItemId")

        numero = (quotation.get("number") or "").strip()
        fecha = (quotation.get("date") or "").strip()
        cliente = (quotation.get("client") or "").strip()
        atencion = (quotation.get("attention") or "").strip()
        ciudad = (quotation.get("city") or "").strip()
        validez = (quotation.get("validity") or "").strip()
        forma_pago = (quotation.get("paymentTerms") or "").strip()
        observaciones = (quotation.get("notes") or "").strip()
        db_id = quotation.get("dbId")
        current_user = get_current_user()
        current_user_id = current_user["id"] if current_user else None
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total = 0
        for item in items:
            try:
                precio = float(str(item.get("price", "")).replace(",", "").strip() or 0)
            except ValueError:
                precio = 0

            try:
                cantidad = float(str(item.get("quantity", "")).replace(",", "").strip() or 1)
            except ValueError:
                cantidad = 1

            total += precio * cantidad

        full_payload = {
            "quotation": quotation,
            "items": items,
            "selectedItemId": selected_item_id
        }
        payload_json = json.dumps(full_payload, ensure_ascii=False)
        conn = get_db_connection()
        ensure_auth_schema(conn)

        if db_id:
            conn.execute("""
                UPDATE cotizaciones
                SET numero = ?, fecha = ?, cliente = ?, atencion = ?, ciudad = ?,
                    validez = ?, forma_pago = ?, observaciones = ?, total = ?, payload_json = ?,
                    actualizado_por_user_id = ?, actualizado_en = ?
                WHERE id = ?
            """, (
                numero, fecha, cliente, atencion, ciudad,
                validez, forma_pago, observaciones, total, payload_json,
                current_user_id, now_str, db_id
            ))
            cotizacion_id = db_id

            conn.execute("DELETE FROM cotizacion_items WHERE cotizacion_id = ?", (cotizacion_id,))
        else:
            if not numero:
                numero = next_quote_number(conn)

            cur = conn.execute("""
                INSERT INTO cotizaciones (
                    numero, fecha, cliente, atencion, ciudad,
                    validez, forma_pago, observaciones, total, estado, payload_json,
                    creado_por_user_id, actualizado_por_user_id, creado_en, actualizado_en
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'borrador', ?, ?, ?, ?, ?)
            """, (
                numero, fecha, cliente, atencion, ciudad,
                validez, forma_pago, observaciones, total, payload_json,
                current_user_id, current_user_id, now_str, now_str
            ))
            cotizacion_id = cur.lastrowid

        for idx, item in enumerate(items):
            try:
                precio = float(str(item.get("price", "")).replace(",", "").strip() or 0)
            except ValueError:
                precio = 0

            try:
                cantidad = float(str(item.get("quantity", "")).replace(",", "").strip() or 1)
            except ValueError:
                cantidad = 1

            imagen = normalize_image_path_for_db(item.get("imageSrc"))

            conn.execute("""
                INSERT INTO cotizacion_items (
                    cotizacion_id,
                    plantilla_id,
                    nombre_editado,
                    marca_editada,
                    modelo_editado,
                    precio_unitario,
                    cantidad,
                    mostrar_precio,
                    descripcion_breve_editada,
                    descripcion_larga_editada,
                    imagen_editada,
                    orden
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cotizacion_id,
                item.get("templateId"),
                (item.get("title") or "").strip(),
                (item.get("brand") or "").strip(),
                (item.get("model") or "").strip(),
                precio,
                cantidad,
                1 if item.get("showPrice") else 0,
                (item.get("subtitle") or "").strip(),
                (item.get("descriptionLong") or "").strip(),
                imagen,
                idx
            ))

        full_payload["quotation"] = dict(full_payload.get("quotation") or {})
        full_payload["quotation"]["dbId"] = cotizacion_id
        full_payload["quotation"]["number"] = numero

        payload_json_final = json.dumps(full_payload, ensure_ascii=False)

        conn.execute("""
            UPDATE cotizaciones
            SET payload_json = ?
            WHERE id = ?
        """, (payload_json_final, cotizacion_id))

        conn.commit()

        print("Cotización guardada con ID:", cotizacion_id)
        print("Número:", numero)
        print("Total:", total)

        return jsonify({
            "ok": True,
            "cotizacion_id": cotizacion_id,
            "numero": numero,
            "total": total
        })

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERROR GUARDANDO COTIZACION:", e)
        raise

    finally:
        if conn:
            conn.close()


@app.route("/equipos/nuevo", methods=["POST"])
@editor_required
def crear_equipo():
    nombre = request.form.get("nombre", "").strip()
    marca = request.form.get("marca", "").strip()
    modelo = request.form.get("modelo", "").strip()
    origen = request.form.get("origen", "").strip()
    garantia_base = request.form.get("garantia_base", "").strip()
    descripcion_breve = request.form.get("descripcion_breve", "").strip()
    descripcion_larga = request.form.get("descripcion_larga", "").strip()
    imagen = request.form.get("imagen", "").strip()

    if not nombre:
        return redirect(url_for("equipos_page"))

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO equipos (
            nombre, marca, modelo, origen, garantia_base,
            descripcion_breve, descripcion_larga, imagen, activo
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        nombre, marca, modelo, origen, garantia_base,
        descripcion_breve, descripcion_larga, imagen
    ))
    conn.commit()
    conn.close()

    return redirect(url_for("equipos_page"))

@app.route("/equipos/<int:equipo_id>/eliminar", methods=["POST"])
@admin_required
def eliminar_equipo(equipo_id):
    conn = get_db_connection()

    equipo = conn.execute("""
        SELECT id
        FROM equipos
        WHERE id = ? AND activo = 1
    """, (equipo_id,)).fetchone()

    if not equipo:
        conn.close()
        return redirect(url_for("equipos_page"))

    conn.execute("""
        UPDATE equipos
        SET activo = 0
        WHERE id = ?
    """, (equipo_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("equipos_page"))

@app.route("/plantillas/<int:plantilla_id>/eliminar", methods=["POST"])
@admin_required
def eliminar_plantilla(plantilla_id):
    conn = get_db_connection()

    plantilla = conn.execute("""
        SELECT id
        FROM plantillas
        WHERE id = ? AND activo = 1
    """, (plantilla_id,)).fetchone()

    if not plantilla:
        conn.close()
        return redirect(url_for("plantillas_page"))

    conn.execute("DELETE FROM plantillas_especificaciones WHERE plantilla_id = ?", (plantilla_id,))
    conn.execute("DELETE FROM plantillas_usos WHERE plantilla_id = ?", (plantilla_id,))
    conn.execute("DELETE FROM plantillas_accesorios WHERE plantilla_id = ?", (plantilla_id,))
    conn.execute("DELETE FROM plantillas_ventajas WHERE plantilla_id = ?", (plantilla_id,))

    conn.execute("""
        UPDATE plantillas
        SET activo = 0
        WHERE id = ?
    """, (plantilla_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("plantillas_page"))


@app.route("/cotizaciones/<int:cotizacion_id>/eliminar", methods=["POST"])
@admin_required
def eliminar_cotizacion(cotizacion_id):
    conn = get_db_connection()
    ensure_auth_schema(conn)

    cot = conn.execute("""
        SELECT id
        FROM cotizaciones
        WHERE id = ?
    """, (cotizacion_id,)).fetchone()

    if not cot:
        conn.close()
        return redirect(url_for("cotizaciones_page"))

    conn.execute("DELETE FROM cotizacion_items WHERE cotizacion_id = ?", (cotizacion_id,))
    conn.execute("DELETE FROM cotizaciones WHERE id = ?", (cotizacion_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("cotizaciones_page"))

@app.route("/plantillas/nueva", methods=["POST"])
@editor_required
def crear_plantilla():
    modo_creacion = request.form.get("modo_creacion", "vacia").strip()
    equipo_id_raw = request.form.get("equipo_id", "").strip()

    nombre_plantilla = request.form.get("nombre_plantilla", "").strip()
    nombre_comercial = request.form.get("nombre_comercial", "").strip()
    descripcion_breve = request.form.get("plantilla_descripcion_breve", "").strip()
    descripcion_larga = request.form.get("plantilla_descripcion_larga", "").strip()
    imagen = request.form.get("plantilla_imagen", "").strip()
    precio_base = request.form.get("precio_base", "").strip()
    mostrar_precio = 1 if request.form.get("mostrar_precio_por_defecto") == "on" else 0

    if not nombre_plantilla:
        return redirect(url_for("plantillas_page"))

    try:
        precio_base_val = float(precio_base) if precio_base else 0
    except ValueError:
        precio_base_val = 0

    conn = get_db_connection()

    equipo_id = None
    equipo_base = None

    if modo_creacion == "desde_equipo":
        if not equipo_id_raw:
            conn.close()
            return redirect(url_for("plantillas_page"))

        try:
            equipo_id = int(equipo_id_raw)
        except ValueError:
            conn.close()
            return redirect(url_for("plantillas_page"))

        equipo_base = conn.execute("""
            SELECT *
            FROM equipos
            WHERE id = ? AND activo = 1
        """, (equipo_id,)).fetchone()

        if not equipo_base:
            conn.close()
            return redirect(url_for("plantillas_page"))

        snapshot = build_initial_template_data_from_equipo(equipo_base)

        if not nombre_comercial:
            nombre_comercial = snapshot["nombre_comercial"]

        if not descripcion_breve:
            descripcion_breve = snapshot["descripcion_breve"]

        if not descripcion_larga:
            descripcion_larga = snapshot["descripcion_larga"]

        if not imagen:
            imagen = snapshot["imagen"]

    conn.execute("""
        INSERT INTO plantillas (
            equipo_id,
            nombre_plantilla,
            nombre_comercial,
            descripcion_breve,
            descripcion_larga,
            imagen,
            precio_base,
            mostrar_precio_por_defecto,
            activo
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        equipo_id,
        nombre_plantilla,
        nombre_comercial,
        descripcion_breve,
        descripcion_larga,
        imagen,
        precio_base_val,
        mostrar_precio
    ))
    conn.commit()
    conn.close()

    return redirect(url_for("plantillas_page"))

@app.route("/plantillas/<int:plantilla_id>/editar", methods=["POST"])
@editor_required
def editar_plantilla(plantilla_id):
    nombre_plantilla = request.form.get("nombre_plantilla", "").strip()
    nombre_comercial = request.form.get("nombre_comercial", "").strip()
    descripcion_breve = request.form.get("plantilla_descripcion_breve", "").strip()
    descripcion_larga = request.form.get("plantilla_descripcion_larga", "").strip()
    imagen = request.form.get("plantilla_imagen", "").strip()
    precio_base = request.form.get("precio_base", "").strip()
    mostrar_precio = 1 if request.form.get("mostrar_precio_por_defecto") == "on" else 0

    if not nombre_plantilla:
        return redirect(url_for("plantillas_page"))

    try:
        precio_base_val = float(precio_base) if precio_base else 0
    except ValueError:
        precio_base_val = 0

    spec_parametros = request.form.getlist("spec_parametro[]")
    spec_detalles = request.form.getlist("spec_detalle[]")

    specs = []
    max_specs = max(len(spec_parametros), len(spec_detalles))
    for i in range(max_specs):
        specs.append({
            "parametro": spec_parametros[i] if i < len(spec_parametros) else "",
            "detalle": spec_detalles[i] if i < len(spec_detalles) else "",
        })

    usos = request.form.getlist("uso_texto[]")
    accesorios = request.form.getlist("accesorio_texto[]")
    ventajas = request.form.getlist("ventaja_texto[]")

    conn = get_db_connection()

    plantilla = conn.execute("""
        SELECT id
        FROM plantillas
        WHERE id = ? AND activo = 1
    """, (plantilla_id,)).fetchone()

    if not plantilla:
        conn.close()
        return redirect(url_for("plantillas_page"))

    conn.execute("""
        UPDATE plantillas
        SET nombre_plantilla = ?,
            nombre_comercial = ?,
            descripcion_breve = ?,
            descripcion_larga = ?,
            imagen = ?,
            precio_base = ?,
            mostrar_precio_por_defecto = ?
        WHERE id = ?
    """, (
        nombre_plantilla,
        nombre_comercial,
        descripcion_breve,
        descripcion_larga,
        imagen,
        precio_base_val,
        mostrar_precio,
        plantilla_id
    ))

    replace_plantilla_children(
        conn,
        plantilla_id,
        specs=specs,
        usos=usos,
        accesorios=accesorios,
        ventajas=ventajas
    )

    conn.commit()
    conn.close()

    return redirect(url_for("plantillas_page"))

if __name__ == "__main__":
    ensure_upload_dir()
    app.run(host="0.0.0.0", port=8081, debug=True)