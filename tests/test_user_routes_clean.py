import os
import sys
import tempfile
import unittest

# Asegurar que el directorio raíz esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app
import init_db


class TestUserRoutesClean(unittest.TestCase):
    """Pruebas de integración para las rutas del Grupo A (Usuarios y Auth) sin llamadas DDL redundantes."""

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

    def test_login_route_get_returns_200(self):
        """Verifica que /login responda 200 OK sin llamadas ensure_auth_schema internas."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            conn.close()

            with app.app.test_client() as client:
                res = client.get("/login")
                self.assertEqual(res.status_code, 200)
                self.assertIn("Ingresar", res.get_data(as_text=True))
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_usuarios_routes_group_a_not_500(self):
        """Verifica que las 6 rutas del Grupo A no lancen error 500 al ser invocadas en una DB limpia."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            conn.close()

            with app.app.test_client() as client:
                # GET /login -> 200
                res = client.get("/login")
                self.assertNotEqual(res.status_code, 500)

                # GET /usuarios -> 302 (requiere auth admin)
                res = client.get("/usuarios")
                self.assertNotEqual(res.status_code, 500)

                # POST /usuarios/nuevo -> 302
                res = client.post("/usuarios/nuevo", data={"username": "user1", "password": "123"})
                self.assertNotEqual(res.status_code, 500)

                # POST /usuarios/1/editar -> 302
                res = client.post("/usuarios/1/editar", data={"username": "user1"})
                self.assertNotEqual(res.status_code, 500)

                # POST /usuarios/1/rol -> 302
                res = client.post("/usuarios/1/rol", data={"rol": "editor"})
                self.assertNotEqual(res.status_code, 500)

                # POST /usuarios/1/desactivar -> 302
                res = client.post("/usuarios/1/desactivar")
                self.assertNotEqual(res.status_code, 500)
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_usuarios_crud_operations_in_temp_db(self):
        """Verifica la creación y actualización de usuarios en una DB temporal limpia."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            app.ensure_auth_schema(conn)

            # Insertar un usuario admin de prueba directamente en la DB temporal
            from werkzeug.security import generate_password_hash
            conn.execute(
                "INSERT INTO usuarios (username, password_hash, nombre, rol, activo) VALUES (?, ?, ?, ?, 1)",
                ("admin_test", generate_password_hash("pass123"), "Admin Test", "admin")
            )
            conn.commit()
            admin_id = conn.execute("SELECT id FROM usuarios WHERE username='admin_test'").fetchone()["id"]
            conn.close()

            with app.app.test_client() as client:
                # Iniciar sesión como admin_test
                with client.session_transaction() as sess:
                    sess["user_id"] = admin_id
                    sess["user_role"] = "admin"

                # GET /usuarios
                res = client.get("/usuarios")
                self.assertEqual(res.status_code, 200)

                # Crear un nuevo usuario vía POST /usuarios/nuevo
                res = client.post("/usuarios/nuevo", data={
                    "username": "editor_nuevo",
                    "nombre": "Editor Test",
                    "password": "secretpass",
                    "rol": "editor"
                }, follow_redirects=True)
                self.assertEqual(res.status_code, 200)

                # Verificar en DB temporal
                conn = app.get_db_connection()
                new_user = conn.execute("SELECT * FROM usuarios WHERE username='editor_nuevo'").fetchone()
                self.assertIsNotNone(new_user)
                self.assertEqual(new_user["nombre"], "Editor Test")
                self.assertEqual(new_user["rol"], "editor")
                conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)


if __name__ == "__main__":
    unittest.main()
