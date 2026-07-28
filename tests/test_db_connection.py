import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock

import app
import db.connection
import init_db


class TestDBConnection(unittest.TestCase):
    """Pruebas unitarias para el módulo db.connection y sus wrappers en app.py."""

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

        self.original_app_db_path = app.DB_PATH

    def tearDown(self):
        app.DB_PATH = self.original_app_db_path

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

    def test_db_connection_direct_call(self):
        """Verifica que db.connection.get_db_connection trabaje sobre la ruta indicada."""
        conn = db.connection.get_db_connection(self.temp_db_path)
        try:
            self.assertIsInstance(conn, sqlite3.Connection)
            self.assertEqual(conn.row_factory, sqlite3.Row)
        finally:
            conn.close()

    def test_db_connection_init_schema_direct_call(self):
        """Verifica que db.connection.init_db_schema inicialice el esquema e invoque el callback de upload dir."""
        conn = sqlite3.connect(self.temp_db_path)
        conn.executescript(init_db.schema)
        conn.close()

        mock_upload_fn = MagicMock()
        result = db.connection.init_db_schema(self.temp_db_path, ensure_upload_dir_fn=mock_upload_fn)
        self.assertTrue(result)
        mock_upload_fn.assert_called_once()

    def test_app_wrappers_use_dynamic_app_db_path(self):
        """Verifica que app.get_db_connection() y app.init_db_schema() usen dinámicamente app.DB_PATH."""
        app.DB_PATH = self.temp_db_path

        # Crear esquema base
        conn = sqlite3.connect(self.temp_db_path)
        conn.executescript(init_db.schema)
        conn.close()

        # Probar wrapper get_db_connection
        conn = app.get_db_connection()
        try:
            self.assertIsInstance(conn, sqlite3.Connection)
        finally:
            conn.close()

        # Probar wrapper init_db_schema
        result = app.init_db_schema()
        self.assertTrue(result)

        # Verificar que las tablas fueron creadas en la base temporal
        conn = sqlite3.connect(self.temp_db_path)
        try:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios'")
            self.assertIsNotNone(cursor.fetchone())
        finally:
            conn.close()
