import os
import sys
import tempfile
import unittest

# Asegurar que el directorio raíz esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app
import init_db


class TestSchemaInit(unittest.TestCase):
    """Pruebas unitarias para verificar init_db_schema(), su idempotencia, manejo de excepciones y aislamiento de DB."""

    def setUp(self):
        self.real_db_path = "biosolutions.db"
        self.original_app_db_path = app.DB_PATH
        self.original_initialized_paths = set(app._initialized_schema_paths)

        if os.path.exists(self.real_db_path):
            self.initial_mtime = os.path.getmtime(self.real_db_path)
            self.initial_size = os.path.getsize(self.real_db_path)
        else:
            self.initial_mtime = None
            self.initial_size = None

    def tearDown(self):
        app.DB_PATH = self.original_app_db_path
        app._initialized_schema_paths = set(self.original_initialized_paths)

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

    def test_init_db_schema_initializes_temp_db(self):
        """Verifica que init_db_schema() ejecute ensure_auth_schema sobre una DB temporal."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path

            # Crear esquema base para que ensure_* no falle por ausencia de cotizaciones
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            conn.close()

            result = app.init_db_schema()
            self.assertTrue(result)

            # Verificar que las tablas fueron creadas
            conn = app.get_db_connection()
            tables = [
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            conn.close()

            self.assertIn("usuarios", tables)
            self.assertIn("entregas", tables)
            self.assertIn("garantias", tables)
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_init_db_schema_is_idempotent(self):
        """Verifica que llamar a init_db_schema() dos veces seguidas no vuelva a ejecutar el proceso innecesariamente."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path

            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            conn.close()

            res1 = app.init_db_schema()
            res2 = app.init_db_schema()

            self.assertTrue(res1)
            self.assertTrue(res2)
            self.assertIn(os.path.abspath(temp_db_path), app._initialized_schema_paths)
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_init_db_schema_tracks_different_db_paths(self):
        """Verifica que si DB_PATH cambia a una nueva base temporal, init_db_schema() vuelva a inicializar esa nueva ruta."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp1, \
             tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp2:
            db_path_1 = temp1.name
            db_path_2 = temp2.name

        try:
            # Inicializar primera DB
            app.DB_PATH = db_path_1
            conn1 = app.get_db_connection()
            conn1.executescript(init_db.schema)
            conn1.close()
            app.init_db_schema()

            # Inicializar segunda DB
            app.DB_PATH = db_path_2
            conn2 = app.get_db_connection()
            conn2.executescript(init_db.schema)
            conn2.close()
            app.init_db_schema()

            self.assertIn(os.path.abspath(db_path_1), app._initialized_schema_paths)
            self.assertIn(os.path.abspath(db_path_2), app._initialized_schema_paths)
        finally:
            if os.path.exists(db_path_1):
                os.remove(db_path_1)
            if os.path.exists(db_path_2):
                os.remove(db_path_2)

    def test_init_db_schema_closes_connection_on_exception(self):
        """Verifica que ante una excepción durante ensure_auth_schema, la conexión se cierre de forma segura."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        original_ensure_auth_schema = app.ensure_auth_schema
        try:
            app.DB_PATH = temp_db_path

            def mock_failing_ensure_auth(conn):
                raise RuntimeError("Simulación de fallo de esquema")

            app.ensure_auth_schema = mock_failing_ensure_auth

            with self.assertRaises(RuntimeError):
                app.init_db_schema()

            # La ruta no debe quedar marcada como exitosa si falló
            self.assertNotIn(os.path.abspath(temp_db_path), app._initialized_schema_paths)
        finally:
            app.ensure_auth_schema = original_ensure_auth_schema
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_before_request_auto_initializes_schema(self):
        """Verifica que al realizar una petición HTTP vía test_client(), @app.before_request inicialice el esquema automáticamente."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path

            # Inicializar esquema base para que ensure_* no falle por tablas faltantes
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            conn.close()

            abs_temp_path = os.path.abspath(temp_db_path)
            self.assertNotIn(abs_temp_path, app._initialized_schema_paths)

            with app.app.test_client() as client:
                response = client.get("/login")
                self.assertIn(response.status_code, (200, 302))

            self.assertIn(abs_temp_path, app._initialized_schema_paths)

            conn = app.get_db_connection()
            tables = [
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            conn.close()

            self.assertIn("usuarios", tables)
            self.assertIn("entregas", tables)
            self.assertIn("garantias", tables)
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)


if __name__ == "__main__":
    unittest.main()
