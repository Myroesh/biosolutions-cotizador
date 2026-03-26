import sqlite3

DB_PATH = "biosolutions.db"

schema = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS equipos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    marca TEXT,
    modelo TEXT,
    origen TEXT,
    garantia_base TEXT,
    descripcion_breve TEXT,
    descripcion_larga TEXT,
    imagen TEXT,
    activo INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS especificaciones_equipo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id INTEGER NOT NULL,
    parametro TEXT,
    detalle TEXT,
    orden INTEGER DEFAULT 0,
    FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS usos_equipo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id INTEGER NOT NULL,
    texto TEXT,
    orden INTEGER DEFAULT 0,
    FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS accesorios_equipo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id INTEGER NOT NULL,
    texto TEXT,
    orden INTEGER DEFAULT 0,
    FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ventajas_equipo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id INTEGER NOT NULL,
    texto TEXT,
    orden INTEGER DEFAULT 0,
    FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS plantillas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id INTEGER NOT NULL,
    nombre_plantilla TEXT NOT NULL,
    nombre_comercial TEXT,
    descripcion_breve TEXT,
    descripcion_larga TEXT,
    imagen TEXT,
    precio_base REAL DEFAULT 0,
    mostrar_precio_por_defecto INTEGER DEFAULT 0,
    activo INTEGER DEFAULT 1,
    FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS plantillas_accesorios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plantilla_id INTEGER NOT NULL,
    texto TEXT,
    orden INTEGER DEFAULT 0,
    FOREIGN KEY (plantilla_id) REFERENCES plantillas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS plantillas_ventajas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plantilla_id INTEGER NOT NULL,
    texto TEXT,
    orden INTEGER DEFAULT 0,
    FOREIGN KEY (plantilla_id) REFERENCES plantillas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS plantillas_usos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plantilla_id INTEGER NOT NULL,
    texto TEXT,
    orden INTEGER DEFAULT 0,
    FOREIGN KEY (plantilla_id) REFERENCES plantillas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS plantillas_especificaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plantilla_id INTEGER NOT NULL,
    parametro TEXT,
    detalle TEXT,
    orden INTEGER DEFAULT 0,
    FOREIGN KEY (plantilla_id) REFERENCES plantillas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cotizaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero TEXT UNIQUE,
    fecha TEXT,
    cliente TEXT,
    atencion TEXT,
    ciudad TEXT,
    validez TEXT,
    forma_pago TEXT,
    observaciones TEXT,
    moneda TEXT DEFAULT 'BOB',
    total REAL DEFAULT 0,
    estado TEXT DEFAULT 'borrador'
);

CREATE TABLE IF NOT EXISTS cotizacion_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cotizacion_id INTEGER NOT NULL,
    plantilla_id INTEGER,
    nombre_editado TEXT,
    marca_editada TEXT,
    modelo_editado TEXT,
    precio_unitario REAL DEFAULT 0,
    cantidad REAL DEFAULT 1,
    mostrar_precio INTEGER DEFAULT 0,
    descripcion_breve_editada TEXT,
    descripcion_larga_editada TEXT,
    imagen_editada TEXT,
    orden INTEGER DEFAULT 0,
    FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id) ON DELETE CASCADE,
    FOREIGN KEY (plantilla_id) REFERENCES plantillas(id) ON DELETE SET NULL
);
"""

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(schema)
    conn.commit()
    conn.close()
    print(f"Base creada/actualizada en {DB_PATH}")

if __name__ == "__main__":
    main()