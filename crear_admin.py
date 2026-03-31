import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = "biosolutions.db"

conn = sqlite3.connect(DB_PATH)

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

conn.execute("DELETE FROM usuarios WHERE username = ?", ("admin",))

conn.execute("""
INSERT INTO usuarios (username, password_hash, nombre, rol, activo)
VALUES (?, ?, ?, ?, 1)
""", (
    "admin",
    generate_password_hash("admin123"),
    "Administrador",
    "admin"
))

conn.commit()
conn.close()

print("Usuario admin recreado correctamente.")
print("Usuario: admin")
print("Contraseña: admin123")