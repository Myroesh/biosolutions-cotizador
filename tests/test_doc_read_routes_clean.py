import os
import sys
import tempfile
import unittest

# Asegurar que el directorio raíz esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app
import init_db


class TestDocReadRoutesClean(unittest.TestCase):
    """Pruebas de integración para las rutas del Subgrupo B2 (vistas GET de entregas y garantías) sin llamadas DDL redundantes."""

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

    def test_subgroup_b2_routes_unauthenticated_no_500(self):
        """Verifica que las 4 rutas GET del Subgrupo B2 no lancen error 500 sin autenticación."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            conn.close()

            with app.app.test_client() as client:
                # GET /entregas -> 302 (redirect to login)
                res = client.get("/entregas")
                self.assertIn(res.status_code, (200, 302))

                # GET /entregas/1 -> 302
                res = client.get("/entregas/1")
                self.assertIn(res.status_code, (200, 302, 404))

                # GET /garantias -> 302
                res = client.get("/garantias")
                self.assertIn(res.status_code, (200, 302))

                # GET /garantias/1 -> 302
                res = client.get("/garantias/1")
                self.assertIn(res.status_code, (200, 302, 404))
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_subgroup_b2_routes_authenticated(self):
        """Verifica que las 4 rutas GET de entregas y garantías respondan HTTP 200/302/404 al estar autenticado sin lanzar 500."""
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
                ("editor_docs", generate_password_hash("pass"), "Editor Docs", "editor")
            )
            conn.commit()
            user_id = conn.execute("SELECT id FROM usuarios WHERE username='editor_docs'").fetchone()["id"]
            conn.close()

            with app.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["user_id"] = user_id
                    sess["user_role"] = "editor"

                # GET /entregas -> 200 OK
                res = client.get("/entregas")
                self.assertEqual(res.status_code, 200)

                # GET /entregas/999 -> 302 Redirect to /entregas (entrega inexistente)
                res = client.get("/entregas/999")
                self.assertIn(res.status_code, (200, 302, 404))

                # GET /garantias -> 200 OK
                res = client.get("/garantias")
                self.assertEqual(res.status_code, 200)

                # GET /garantias/999 -> 302 Redirect to /garantias (garantía inexistente)
                res = client.get("/garantias/999")
                self.assertIn(res.status_code, (200, 302, 404))
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)


if __name__ == "__main__":
    unittest.main()
