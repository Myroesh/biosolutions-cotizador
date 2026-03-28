from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
from datetime import date

app = Flask(__name__)
DB_PATH = "biosolutions.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
def dashboard():
    return render_template("index.html", active_page="inicio")


@app.route("/cotizador")
def cotizador():
    conn = get_db_connection()

    plantillas = conn.execute("""
        SELECT p.*, e.nombre AS equipo_nombre, e.marca AS equipo_marca, e.modelo AS equipo_modelo
        FROM plantillas p
        LEFT JOIN equipos e ON e.id = p.equipo_id
        WHERE p.activo = 1
        ORDER BY p.nombre_plantilla ASC
    """).fetchall()

    plantillas_json = []
    for p in plantillas:
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
            "mostrar_precio_por_defecto": p["mostrar_precio_por_defecto"] or 0
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
def equipos_page():
    conn = get_db_connection()
    equipos = conn.execute("""
        SELECT *
        FROM equipos
        WHERE activo = 1
        ORDER BY id DESC
    """).fetchall()
    conn.close()
    return render_template("equipos.html", equipos=equipos, active_page="equipos")


@app.route("/plantillas")
def plantillas_page():
    conn = get_db_connection()

    equipos = conn.execute("""
        SELECT *
        FROM equipos
        WHERE activo = 1
        ORDER BY id DESC
    """).fetchall()

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
        active_page="plantillas"
    )


@app.route("/cotizaciones")
def cotizaciones_page():
    conn = get_db_connection()
    cotizaciones = conn.execute("""
        SELECT *
        FROM cotizaciones
        ORDER BY id DESC
    """).fetchall()
    conn.close()
    return render_template("cotizaciones.html", cotizaciones=cotizaciones, active_page="cotizaciones")


@app.route("/cotizaciones/<int:cotizacion_id>/json")
def cotizacion_json(cotizacion_id):
    conn = get_db_connection()

    cot = conn.execute("""
        SELECT *
        FROM cotizaciones
        WHERE id = ?
    """, (cotizacion_id,)).fetchone()

    if not cot:
        conn.close()
        return jsonify({"error": "Cotización no encontrada"}), 404

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
def guardar_cotizacion():
    data = request.get_json(force=True)

    quotation = data.get("quotation", {})
    items = data.get("items", [])

    numero = (quotation.get("number") or "").strip()
    fecha = (quotation.get("date") or "").strip()
    cliente = (quotation.get("client") or "").strip()
    atencion = (quotation.get("attention") or "").strip()
    ciudad = (quotation.get("city") or "").strip()
    validez = (quotation.get("validity") or "").strip()
    forma_pago = (quotation.get("paymentTerms") or "").strip()
    observaciones = (quotation.get("notes") or "").strip()
    db_id = quotation.get("dbId")

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

    conn = get_db_connection()

    if db_id:
        conn.execute("""
            UPDATE cotizaciones
            SET numero = ?, fecha = ?, cliente = ?, atencion = ?, ciudad = ?,
                validez = ?, forma_pago = ?, observaciones = ?, total = ?
            WHERE id = ?
        """, (
            numero, fecha, cliente, atencion, ciudad,
            validez, forma_pago, observaciones, total, db_id
        ))
        cotizacion_id = db_id

        conn.execute("DELETE FROM cotizacion_items WHERE cotizacion_id = ?", (cotizacion_id,))
    else:
        if not numero:
            numero = next_quote_number(conn)

        cur = conn.execute("""
            INSERT INTO cotizaciones (
                numero, fecha, cliente, atencion, ciudad,
                validez, forma_pago, observaciones, total, estado
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'borrador')
        """, (
            numero, fecha, cliente, atencion, ciudad,
            validez, forma_pago, observaciones, total
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

        imagen = (item.get("imageSrc") or "").strip()
        if imagen.startswith("/static/"):
            imagen = imagen.replace("/static/", "", 1)

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

    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "cotizacion_id": cotizacion_id,
        "numero": numero,
        "total": total
    })


@app.route("/equipos/nuevo", methods=["POST"])
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


@app.route("/plantillas/nueva", methods=["POST"])
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
    app.run(host="0.0.0.0", port=8081, debug=True)