import os
import sqlite3
import threading
from db.schema import ensure_auth_schema

_schema_init_lock = threading.Lock()
_initialized_schema_paths = set()


def get_db_connection(db_path=None):
    """Crea y retorna una conexión SQLite configurada con row_factory = sqlite3.Row."""
    if db_path is None:
        db_path = os.environ.get("BIOSOLUTIONS_DB_PATH", "biosolutions.db")
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db_schema(db_path=None, ensure_upload_dir_fn=None, ensure_auth_schema_fn=None, initialized_paths=None):
    """Inicializa de forma idempotente el esquema relacional sobre la ruta especificada."""
    global _initialized_schema_paths
    if db_path is None:
        db_path = os.environ.get("BIOSOLUTIONS_DB_PATH", "biosolutions.db")

    if ensure_auth_schema_fn is None:
        ensure_auth_schema_fn = ensure_auth_schema

    if initialized_paths is None:
        initialized_paths = _initialized_schema_paths

    current_path = os.path.abspath(db_path)
    with _schema_init_lock:
        if current_path in initialized_paths:
            return True

        if ensure_upload_dir_fn:
            ensure_upload_dir_fn()

        conn = None
        try:
            conn = get_db_connection(db_path)
            ensure_auth_schema_fn(conn)
            initialized_paths.add(current_path)
            return True
        finally:
            if conn:
                conn.close()
