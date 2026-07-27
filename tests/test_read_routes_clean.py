import os
import sys
import tempfile
import unittest

# Asegurar que el directorio raíz esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app
import init_db


class TestReadRoutesClean(unittest.TestCase):
    """Pruebas de integración para las rutas del Subgrupo B1 (lectura y listados) sin llamadas DDL redundantes."""

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

    def test_subgroup_b1_routes_unauthenticated_no_500(self):
        """Verifica que las 5 rutas del Subgrupo B1 no lancen error 500 sin autenticación (redireccionan a login o 404)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            conn.close()

            with app.app.test_client() as client:
                # GET /cotizador -> 302 (redirect to login)
                res = client.get("/cotizador")
                self.assertIn(res.status_code, (200, 302))

                # GET /cotizaciones -> 302
                res = client.get("/cotizaciones")
                self.assertIn(res.status_code, (200, 302))

                # GET /cotizaciones/1/json -> 302
                res = client.get("/cotizaciones/1/json")
                self.assertIn(res.status_code, (200, 302, 404))

                # GET /plantillas -> 302
                res = client.get("/plantillas")
                self.assertIn(res.status_code, (200, 302))

                # GET /equipos -> 302
                res = client.get("/equipos")
                self.assertIn(res.status_code, (200, 302))
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_subgroup_b1_routes_authenticated(self):
        """Verifica que las rutas de lectura del Subgrupo B1 respondan HTTP 200/404 al estar autenticado sin lanzar 500."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            app.ensure_auth_schema(conn)

            # Insertar un usuario editor de prueba
            from werkzeug.security import generate_password_hash
            conn.execute(
                "INSERT INTO usuarios (username, password_hash, nombre, rol, activo) VALUES (?, ?, ?, ?, 1)",
                ("editor_user", generate_password_hash("pass"), "Editor User", "editor")
            )
            conn.commit()
            user_id = conn.execute("SELECT id FROM usuarios WHERE username='editor_user'").fetchone()["id"]
            conn.close()

            with app.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["user_id"] = user_id
                    sess["user_role"] = "editor"

                # GET /cotizador -> 200 OK
                res = client.get("/cotizador")
                self.assertEqual(res.status_code, 200)

                # GET /cotizaciones -> 200 OK
                res = client.get("/cotizaciones")
                self.assertEqual(res.status_code, 200)

                # GET /plantillas -> 200 OK
                res = client.get("/plantillas")
                self.assertEqual(res.status_code, 200)

                # GET /equipos -> 200 OK
                res = client.get("/equipos")
                self.assertEqual(res.status_code, 200)

                # GET /cotizaciones/999/json -> 404 Not Found (cotización inexistente)
                res = client.get("/cotizaciones/999/json")
                self.assertEqual(res.status_code, 404)
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)


if __name__ == "__main__":
    unittest.main()
