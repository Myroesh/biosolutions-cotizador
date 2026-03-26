PRAGMA foreign_keys=off;

BEGIN TRANSACTION;

ALTER TABLE plantillas RENAME TO plantillas_old;

CREATE TABLE plantillas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id INTEGER,
    nombre_plantilla TEXT NOT NULL,
    nombre_comercial TEXT,
    descripcion_breve TEXT,
    descripcion_larga TEXT,
    imagen TEXT,
    precio_base REAL DEFAULT 0,
    mostrar_precio_por_defecto INTEGER DEFAULT 0,
    activo INTEGER DEFAULT 1,
    FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE SET NULL
);

INSERT INTO plantillas (
    id,
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
SELECT
    id,
    equipo_id,
    nombre_plantilla,
    nombre_comercial,
    descripcion_breve,
    descripcion_larga,
    imagen,
    precio_base,
    mostrar_precio_por_defecto,
    activo
FROM plantillas_old;

DROP TABLE plantillas_old;

COMMIT;

PRAGMA foreign_keys=on;