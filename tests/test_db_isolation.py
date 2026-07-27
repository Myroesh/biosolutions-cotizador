import os
import sys
import tempfile
import unittest

# Asegurar que el directorio raíz esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app
import init_db


class TestDBIsolation(unittest.TestCase):
    """Pruebas para verificar la conexión a bases de datos SQLite temporales y el aislamiento de biosolutions.db."""

    def setUp(self):
        self.real_db_path = "biosolutions.db"
        self.original_app_db_path = app.DB_PATH
        
        # Registrar mtime y size inicial de biosolutions.db si existe
        if os.path.exists(self.real_db_path):
            self.initial_mtime = os.path.getmtime(self.real_db_path)
            self.initial_size = os.path.getsize(self.real_db_path)
        else:
            self.initial_mtime = None
            self.initial_size = None

    def tearDown(self):
        # Restaurar la configuración original de DB_PATH en app
        app.DB_PATH = self.original_app_db_path
        
        # Verificar que biosolutions.db no sufrió ninguna modificación durante la prueba
        if os.path.exists(self.real_db_path) and self.initial_mtime is not None:
            current_mtime = os.path.getmtime(self.real_db_path)
            current_size = os.path.getsize(self.real_db_path)
            self.assertEqual(
                current_mtime,
                self.initial_mtime,
                "Riesgo detectado: la fecha de modificación de biosolutions.db cambió durante la prueba.",
            )
            self.assertEqual(
                current_size,
                self.initial_size,
                "Riesgo detectado: el tamaño de biosolutions.db cambió durante la prueba.",
            )

    def test_default_db_path_fallback(self):
        """Verifica que el valor por defecto de DB_PATH siga siendo 'biosolutions.db'."""
        self.assertEqual(self.original_app_db_path, "biosolutions.db")

    def test_get_db_connection_with_temp_db(self):
        """Verifica que get_db_connection() se conecte a un archivo SQLite temporal sin tocar la DB real."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            # Redirigir la ruta DB de la app al archivo temporal
            app.DB_PATH = temp_db_path

            conn = app.get_db_connection()
            self.assertIsNotNone(conn)

            # Ejecutar una consulta simple en la DB temporal
            cur = conn.execute("SELECT 1")
            row = cur.fetchone()
            self.assertEqual(row[0], 1)
            conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_ensure_auth_schema_on_temp_db(self):
        """Verifica que ensure_auth_schema() cree las tablas requeridas sobre la base de datos temporal con esquema base."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path

            conn = app.get_db_connection()
            # Inicializar esquema base en la DB temporal
            conn.executescript(init_db.schema)
            conn.commit()

            # Aplicar migraciones ensure_* sobre la DB temporal
            app.ensure_auth_schema(conn)

            # Verificar que las tablas principales existan en la DB temporal
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [row["name"] for row in tables]

            self.assertIn("usuarios", table_names)
            self.assertIn("cotizaciones", table_names)
            self.assertIn("entregas", table_names)
            self.assertIn("garantias", table_names)

            conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)


if __name__ == "__main__":
    unittest.main()
