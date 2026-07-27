import json
import os
import sys
import tempfile
import unittest
from werkzeug.security import generate_password_hash

# Asegurar que el directorio raíz esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app
import init_db


class TestGenerationRoutesClean(unittest.TestCase):
    """Pruebas de integración para las rutas de generación de entrega y garantía desde una cotización sin llamadas DDL redundantes."""

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

    def _create_sample_payload(self, cot_number="COT-TEST"):
        return {
            "document": {
                "number": cot_number,
                "date": "2026-01-01",
                "client": "Cliente Prueba",
                "clientDocument": "12345678",
                "city": "Bogotá",
                "total": 1500.0,
            },
            "items": [
                {
                    "id": 1,
                    "name": "Equipo Medico",
                    "brand": "Brand",
                    "model": "Mod1",
                    "quantity": 1,
                    "unitPrice": 1500.0,
                    "totalPrice": 1500.0,
                }
            ],
        }

    def test_generar_entrega_desde_cotizacion_consolidada(self):
        """Verifica la generación de un acta de entrega a partir de una cotización consolidada."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            app.ensure_auth_schema(conn)

            # Insertar editor
            conn.execute(
                "INSERT INTO usuarios (username, password_hash, nombre, rol, activo) VALUES (?, ?, ?, ?, 1)",
                ("editor_gen", generate_password_hash("pass"), "Editor Gen", "editor")
            )
            editor_id = conn.execute("SELECT id FROM usuarios WHERE username='editor_gen'").fetchone()["id"]

            # Insertar cotización consolidada
            sample_json = json.dumps(self._create_sample_payload("COT-GEN-ENT"))
            conn.execute(
                "INSERT INTO cotizaciones (numero, cliente, ciudad, total, estado_documental, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                ("COT-GEN-ENT", "Cliente Gen", "Bogotá", 1500.0, "consolidada", sample_json)
            )
            conn.commit()
            cot_id = conn.execute("SELECT id FROM cotizaciones WHERE numero='COT-GEN-ENT'").fetchone()["id"]
            conn.close()

            with app.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["user_id"] = editor_id
                    sess["user_role"] = "editor"

                res = client.post(f"/cotizaciones/{cot_id}/generar-entrega")
                self.assertIn(res.status_code, (200, 302))

                # Verificar creación de entrega en DB temporal
                conn = app.get_db_connection()
                entrega_row = conn.execute("SELECT * FROM entregas WHERE cotizacion_id=?", (cot_id,)).fetchone()
                self.assertIsNotNone(entrega_row)
                self.assertEqual(entrega_row["cotizacion_id"], cot_id)
                self.assertEqual(entrega_row["estado"], "borrador")
                conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_generar_garantia_desde_cotizacion_consolidada(self):
        """Verifica la generación de un certificado de garantía a partir de una cotización consolidada."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            app.ensure_auth_schema(conn)

            # Insertar editor
            conn.execute(
                "INSERT INTO usuarios (username, password_hash, nombre, rol, activo) VALUES (?, ?, ?, ?, 1)",
                ("editor_gar", generate_password_hash("pass"), "Editor Gar", "editor")
            )
            editor_id = conn.execute("SELECT id FROM usuarios WHERE username='editor_gar'").fetchone()["id"]

            # Insertar cotización consolidada
            sample_json = json.dumps(self._create_sample_payload("COT-GEN-GAR"))
            conn.execute(
                "INSERT INTO cotizaciones (numero, cliente, ciudad, total, estado_documental, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                ("COT-GEN-GAR", "Cliente Gar", "Bogotá", 1500.0, "consolidada", sample_json)
            )
            conn.commit()
            cot_id = conn.execute("SELECT id FROM cotizaciones WHERE numero='COT-GEN-GAR'").fetchone()["id"]
            conn.close()

            with app.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["user_id"] = editor_id
                    sess["user_role"] = "editor"

                res = client.post(f"/cotizaciones/{cot_id}/generar-garantia")
                self.assertIn(res.status_code, (200, 302))

                # Verificar creación de garantía en DB temporal
                conn = app.get_db_connection()
                garantia_row = conn.execute("SELECT * FROM garantias WHERE cotizacion_id=?", (cot_id,)).fetchone()
                self.assertIsNotNone(garantia_row)
                self.assertEqual(garantia_row["cotizacion_id"], cot_id)
                self.assertEqual(garantia_row["activo"], 1)
                conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_generacion_rechazada_si_cotizacion_en_borrador(self):
        """Verifica que no se generen entregas ni garantías si la cotización está en borrador."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            app.ensure_auth_schema(conn)

            # Insertar editor
            conn.execute(
                "INSERT INTO usuarios (username, password_hash, nombre, rol, activo) VALUES (?, ?, ?, ?, 1)",
                ("editor_draft", generate_password_hash("pass"), "Editor Draft", "editor")
            )
            editor_id = conn.execute("SELECT id FROM usuarios WHERE username='editor_draft'").fetchone()["id"]

            # Insertar cotización en borrador
            sample_json = json.dumps(self._create_sample_payload("COT-DRAFT"))
            conn.execute(
                "INSERT INTO cotizaciones (numero, cliente, ciudad, total, estado_documental, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                ("COT-DRAFT", "Cliente Draft", "Bogotá", 1500.0, "borrador", sample_json)
            )
            conn.commit()
            cot_id = conn.execute("SELECT id FROM cotizaciones WHERE numero='COT-DRAFT'").fetchone()["id"]
            conn.close()

            with app.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["user_id"] = editor_id
                    sess["user_role"] = "editor"

                # Intentar generar entrega -> 302 (redirect con error flash)
                res_ent = client.post(f"/cotizaciones/{cot_id}/generar-entrega")
                self.assertIn(res_ent.status_code, (200, 302))

                # Intentar generar garantía -> 302 (redirect con error flash)
                res_gar = client.post(f"/cotizaciones/{cot_id}/generar-garantia")
                self.assertIn(res_gar.status_code, (200, 302))

                # Verificar que NO se crearon entregas ni garantías
                conn = app.get_db_connection()
                ent_count = conn.execute("SELECT COUNT(1) as cnt FROM entregas WHERE cotizacion_id=?", (cot_id,)).fetchone()["cnt"]
                gar_count = conn.execute("SELECT COUNT(1) as cnt FROM garantias WHERE cotizacion_id=?", (cot_id,)).fetchone()["cnt"]
                self.assertEqual(ent_count, 0)
                self.assertEqual(gar_count, 0)
                conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)


if __name__ == "__main__":
    unittest.main()
