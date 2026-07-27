import os
import sys
import tempfile
import unittest
from werkzeug.security import generate_password_hash

# Asegurar que el directorio raíz esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app
import init_db


class TestMutationRoutesClean(unittest.TestCase):
    """Pruebas de integración para las rutas del Subgrupo C1 (mutaciones simples) sin llamadas DDL redundantes."""

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

    def test_consolidar_cotizacion_updates_status(self):
        """Verifica que /cotizaciones/<id>/consolidar cambie estado_documental a 'consolidada'."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            app.ensure_auth_schema(conn)

            # Insertar un usuario editor de prueba
            conn.execute(
                "INSERT INTO usuarios (username, password_hash, nombre, rol, activo) VALUES (?, ?, ?, ?, 1)",
                ("editor_c1", generate_password_hash("pass"), "Editor C1", "editor")
            )
            editor_id = conn.execute("SELECT id FROM usuarios WHERE username='editor_c1'").fetchone()["id"]

            # Insertar una cotización de prueba en borrador
            conn.execute(
                "INSERT INTO cotizaciones (numero, cliente, ciudad, estado_documental) VALUES (?, ?, ?, ?)",
                ("COT-TEST-001", "Cliente Test", "Ciudad Test", "borrador")
            )
            conn.commit()
            cot_id = conn.execute("SELECT id FROM cotizaciones WHERE numero='COT-TEST-001'").fetchone()["id"]
            conn.close()

            with app.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["user_id"] = editor_id
                    sess["user_role"] = "editor"

                res = client.post(f"/cotizaciones/{cot_id}/consolidar")
                self.assertIn(res.status_code, (200, 302))

                # Verificar cambio en DB temporal
                conn = app.get_db_connection()
                cot_row = conn.execute("SELECT estado_documental FROM cotizaciones WHERE id=?", (cot_id,)).fetchone()
                self.assertIsNotNone(cot_row)
                self.assertEqual(cot_row["estado_documental"], "consolidada")
                conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_eliminar_cotizacion_deletes_records(self):
        """Verifica que /cotizaciones/<id>/eliminar borre la cotización y sus ítems."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            app.ensure_auth_schema(conn)

            # Insertar usuario admin
            conn.execute(
                "INSERT INTO usuarios (username, password_hash, nombre, rol, activo) VALUES (?, ?, ?, ?, 1)",
                ("admin_c1", generate_password_hash("pass"), "Admin C1", "admin")
            )
            admin_id = conn.execute("SELECT id FROM usuarios WHERE username='admin_c1'").fetchone()["id"]

            # Insertar cotización e ítems de prueba (plantilla_id=None)
            conn.execute(
                "INSERT INTO cotizaciones (numero, cliente, ciudad) VALUES (?, ?, ?)",
                ("COT-TEST-DEL", "Cliente Del", "Ciudad Del")
            )
            conn.commit()
            cot_id = conn.execute("SELECT id FROM cotizaciones WHERE numero='COT-TEST-DEL'").fetchone()["id"]

            conn.execute(
                "INSERT INTO cotizacion_items (cotizacion_id, plantilla_id, nombre_editado, cantidad, precio_unitario) VALUES (?, ?, ?, ?, ?)",
                (cot_id, None, "Item Test", 1, 100.0)
            )
            conn.commit()
            conn.close()

            with app.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["user_id"] = admin_id
                    sess["user_role"] = "admin"

                res = client.post(f"/cotizaciones/{cot_id}/eliminar")
                self.assertIn(res.status_code, (200, 302))

                # Verificar eliminación en DB temporal
                conn = app.get_db_connection()
                cot_exists = conn.execute("SELECT id FROM cotizaciones WHERE id=?", (cot_id,)).fetchone()
                item_exists = conn.execute("SELECT id FROM cotizacion_items WHERE cotizacion_id=?", (cot_id,)).fetchone()
                self.assertIsNone(cot_exists)
                self.assertIsNone(item_exists)
                conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_eliminar_garantia_logical_delete(self):
        """Verifica que /garantias/<id>/eliminar realice borrado lógico (activo = 0)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            app.ensure_auth_schema(conn)

            # Insertar usuario admin con clave conocida
            raw_password = "admin_secret_pass"
            conn.execute(
                "INSERT INTO usuarios (username, password_hash, nombre, rol, activo) VALUES (?, ?, ?, ?, 1)",
                ("admin_garantia", generate_password_hash(raw_password), "Admin Garantia", "admin")
            )
            admin_id = conn.execute("SELECT id FROM usuarios WHERE username='admin_garantia'").fetchone()["id"]

            # Insertar garantía de prueba activa
            conn.execute(
                "INSERT INTO garantias (cotizacion_id, numero_garantia, cliente_nombre, activo) VALUES (?, ?, ?, 1)",
                (1, "GAR-TEST-001", "Cliente Garantia")
            )
            conn.commit()
            garantia_id = conn.execute("SELECT id FROM garantias WHERE numero_garantia='GAR-TEST-001'").fetchone()["id"]
            conn.close()

            with app.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["user_id"] = admin_id
                    sess["user_role"] = "admin"

                res = client.post(
                    f"/garantias/{garantia_id}/eliminar",
                    data={"password_confirm": raw_password}
                )
                self.assertIn(res.status_code, (200, 302))

                # Verificar borrado lógico activo=0 en DB temporal
                conn = app.get_db_connection()
                garantia_row = conn.execute("SELECT activo FROM garantias WHERE id=?", (garantia_id,)).fetchone()
                self.assertIsNotNone(garantia_row)
                self.assertEqual(garantia_row["activo"], 0)
                conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)


if __name__ == "__main__":
    unittest.main()
