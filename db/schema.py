# =========================
# Migraciones / schema
# =========================

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


def ensure_cotizacion_documental_column(conn):
    columns = conn.execute("PRAGMA table_info(cotizaciones)").fetchall()
    column_names = [col["name"] for col in columns]

    if "estado_documental" not in column_names:
        conn.execute("ALTER TABLE cotizaciones ADD COLUMN estado_documental TEXT DEFAULT 'borrador'")
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


def ensure_entregas_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entregas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cotizacion_id INTEGER NOT NULL,
            numero_entrega TEXT,
            fecha_entrega TEXT,
            cliente_nombre TEXT,
            cliente_documento TEXT,
            recibe_nombre TEXT,
            entrega_nombre TEXT,
            entrega_documento_texto TEXT,
            texto_intro TEXT,
            total REAL DEFAULT 0,
            payload_json TEXT,
            estado TEXT DEFAULT 'borrador',
            creado_por_user_id INTEGER,
            actualizado_por_user_id INTEGER,
            creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
            actualizado_en TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def ensure_garantias_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS garantias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cotizacion_id INTEGER NOT NULL,
            numero_garantia TEXT,
            fecha_emision TEXT,
            fecha_vencimiento TEXT,
            cliente_nombre TEXT,
            cliente_documento TEXT,
            texto_garantia TEXT,
            total REAL DEFAULT 0,
            payload_json TEXT,
            activo INTEGER NOT NULL DEFAULT 1,
            creado_por_user_id INTEGER,
            actualizado_por_user_id INTEGER,
            creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
            actualizado_en TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    columns = conn.execute("PRAGMA table_info(garantias)").fetchall()
    column_names = [col["name"] for col in columns]

    if "activo" not in column_names:
        conn.execute("ALTER TABLE garantias ADD COLUMN activo INTEGER NOT NULL DEFAULT 1")

    conn.commit()


def ensure_documentos_schema(conn):
    ensure_payload_json_column(conn)
    ensure_cotizaciones_audit_columns(conn)
    ensure_cotizacion_documental_column(conn)
    ensure_entregas_table(conn)
    ensure_garantias_table(conn)


def ensure_auth_schema(conn):
    ensure_users_table(conn)
    ensure_documentos_schema(conn)
