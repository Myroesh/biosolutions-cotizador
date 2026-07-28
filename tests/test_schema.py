import os
import sqlite3
import tempfile
import unittest
from db.schema import ensure_auth_schema


class TestDBSchema(unittest.TestCase):
    """Pruebas unitarias directas para el módulo db.schema."""

    def setUp(self):
        self.real_db_path = os.path.abspath("biosolutions.db")
        if os.path.exists(self.real_db_path):
            self.real_db_mtime = os.path.getmtime(self.real_db_path)
            self.real_db_size = os.path.getsize(self.real_db_path)
        else:
            self.real_db_mtime = None
            self.real_db_size = None

        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_file.name
        self.temp_file.close()

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            os.unlink(self.temp_db_path)

        if os.path.exists(self.real_db_path):
            self.assertEqual(
                os.path.getmtime(self.real_db_path),
                self.real_db_mtime,
                "LA BASE DE DATOS REAL biosolutions.db FUE MODIFICADA EN MTIME",
            )
            self.assertEqual(
                os.path.getsize(self.real_db_path),
                self.real_db_size,
                "LA BASE DE DATOS REAL biosolutions.db FUE MODIFICADA EN SIZE",
            )

    def test_ensure_auth_schema_creates_tables_on_temp_db(self):
        """Verifica que db.schema.ensure_auth_schema() cree todas las tablas sobre una DB SQLite temporal."""
        conn = sqlite3.connect(self.temp_db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Crear tabla base cotizaciones requerida para ALTER TABLE en ensure_*
            conn.execute("CREATE TABLE cotizaciones (id INTEGER PRIMARY KEY AUTOINCREMENT)")
            conn.commit()

            ensure_auth_schema(conn)

            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = [t[0] for t in tables]

            self.assertIn("usuarios", table_names)
            self.assertIn("entregas", table_names)
            self.assertIn("garantias", table_names)
            self.assertIn("cotizaciones", table_names)
        finally:
            conn.close()
