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


class TestSaveQuotationClean(unittest.TestCase):
    """Pruebas de integración para la ruta /cotizaciones/guardar y la función guardar_cotizacion sin llamadas DDL redundantes."""

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

    def test_crear_cotizacion_nueva(self):
        """Verifica la creación de una cotización nueva mediante POST /cotizaciones/guardar."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            app.ensure_auth_schema(conn)

            # Insertar usuario editor
            conn.execute(
                "INSERT INTO usuarios (username, password_hash, nombre, rol, activo) VALUES (?, ?, ?, ?, 1)",
                ("editor_save_cot", generate_password_hash("pass"), "Editor Save Cot", "editor")
            )
            editor_id = conn.execute("SELECT id FROM usuarios WHERE username='editor_save_cot'").fetchone()["id"]
            conn.commit()
            conn.close()

            with app.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["user_id"] = editor_id
                    sess["user_role"] = "editor"

                payload = {
                    "quotation": {
                        "number": "COT-NEW-001",
                        "date": "2026-01-15",
                        "client": "Cliente Nuevo SAS",
                        "attention": "Dr. Smith",
                        "city": "Cali",
                        "validity": "30 días",
                        "paymentTerms": "Contado",
                        "notes": "Observación de prueba",
                    },
                    "items": [
                        {
                            "title": "Ecógrafo Portátil",
                            "brand": "Mindray",
                            "model": "Z60",
                            "price": 5000.0,
                            "quantity": 2,
                            "showPrice": True,
                            "subtitle": "Breve desc",
                            "descriptionLong": "Larga desc",
                        }
                    ],
                }

                res = client.post(
                    "/cotizaciones/guardar",
                    data=json.dumps(payload),
                    content_type="application/json",
                )
                self.assertEqual(res.status_code, 200)
                data = res.get_json()
                self.assertTrue(data.get("ok"))
                self.assertIsNotNone(data.get("cotizacion_id"))
                self.assertEqual(data.get("numero"), "COT-NEW-001")
                self.assertEqual(data.get("total"), 10000.0)

                # Verificar en DB temporal
                conn = app.get_db_connection()
                cot_row = conn.execute("SELECT * FROM cotizaciones WHERE id=?", (data["cotizacion_id"],)).fetchone()
                self.assertIsNotNone(cot_row)
                self.assertEqual(cot_row["numero"], "COT-NEW-001")
                self.assertEqual(cot_row["cliente"], "Cliente Nuevo SAS")
                self.assertEqual(cot_row["total"], 10000.0)

                item_rows = conn.execute("SELECT * FROM cotizacion_items WHERE cotizacion_id=?", (data["cotizacion_id"],)).fetchall()
                self.assertEqual(len(item_rows), 1)
                self.assertEqual(item_rows[0]["nombre_editado"], "Ecógrafo Portátil")
                self.assertEqual(item_rows[0]["precio_unitario"], 5000.0)
                self.assertEqual(item_rows[0]["cantidad"], 2.0)
                conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_editar_cotizacion_existente(self):
        """Verifica la edición de una cotización existente con reemplazo de ítems y recalculo de total."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            app.DB_PATH = temp_db_path
            conn = app.get_db_connection()
            conn.executescript(init_db.schema)
            app.ensure_auth_schema(conn)

            # Insertar usuario editor
            conn.execute(
                "INSERT INTO usuarios (username, password_hash, nombre, rol, activo) VALUES (?, ?, ?, ?, 1)",
                ("editor_edit_cot", generate_password_hash("pass"), "Editor Edit Cot", "editor")
            )
            editor_id = conn.execute("SELECT id FROM usuarios WHERE username='editor_edit_cot'").fetchone()["id"]

            # Insertar cotización inicial
            conn.execute(
                "INSERT INTO cotizaciones (numero, cliente, ciudad, total, estado_documental, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                ("COT-EXIST-01", "Cliente Viejo", "Bogotá", 1000.0, "borrador", "{}")
            )
            cot_id = conn.execute("SELECT id FROM cotizaciones WHERE numero='COT-EXIST-01'").fetchone()["id"]

            # Insertar ítem viejo
            conn.execute(
                "INSERT INTO cotizacion_items (cotizacion_id, nombre_editado, precio_unitario, cantidad, orden) VALUES (?, ?, ?, ?, ?)",
                (cot_id, "Item Viejo", 1000.0, 1, 0)
            )
            conn.commit()
            conn.close()

            with app.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["user_id"] = editor_id
                    sess["user_role"] = "editor"

                payload = {
                    "quotation": {
                        "dbId": cot_id,
                        "number": "COT-EXIST-01",
                        "date": "2026-02-01",
                        "client": "Cliente Editado SAS",
                        "city": "Medellín",
                    },
                    "items": [
                        {
                            "title": "Item Nuevo 1",
                            "price": 300.0,
                            "quantity": 1,
                        },
                        {
                            "title": "Item Nuevo 2",
                            "price": 400.0,
                            "quantity": 2,
                        },
                    ],
                }

                res = client.post(
                    "/cotizaciones/guardar",
                    data=json.dumps(payload),
                    content_type="application/json",
                )
                self.assertEqual(res.status_code, 200)
                data = res.get_json()
                self.assertTrue(data.get("ok"))
                self.assertEqual(data.get("total"), 1100.0)

                # Verificar actualización en DB temporal
                conn = app.get_db_connection()
                cot_row = conn.execute("SELECT * FROM cotizaciones WHERE id=?", (cot_id,)).fetchone()
                self.assertEqual(cot_row["cliente"], "Cliente Editado SAS")
                self.assertEqual(cot_row["total"], 1100.0)

                item_rows = conn.execute("SELECT * FROM cotizacion_items WHERE cotizacion_id=? ORDER BY orden", (cot_id,)).fetchall()
                self.assertEqual(len(item_rows), 2)
                self.assertEqual(item_rows[0]["nombre_editado"], "Item Nuevo 1")
                self.assertEqual(item_rows[1]["nombre_editado"], "Item Nuevo 2")
                conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_editar_cotizacion_con_entrega_y_garantia_asociadas(self):
        """Verifica que la edición de una cotización propague la estructura a entregas y garantías asociadas."""
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
                ("editor_sync_cot", generate_password_hash("pass"), "Editor Sync Cot", "editor")
            )
            editor_id = conn.execute("SELECT id FROM usuarios WHERE username='editor_sync_cot'").fetchone()["id"]

            # Insertar cotización consolidada
            conn.execute(
                "INSERT INTO cotizaciones (numero, cliente, ciudad, total, estado_documental, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                ("COT-SYNC-01", "Cliente Original", "Bogotá", 2000.0, "consolidada", "{}")
            )
            cot_id = conn.execute("SELECT id FROM cotizaciones WHERE numero='COT-SYNC-01'").fetchone()["id"]

            # Insertar entrega ligada
            conn.execute(
                "INSERT INTO entregas (cotizacion_id, numero_entrega, cliente_nombre, payload_json, estado) VALUES (?, ?, ?, ?, ?)",
                (cot_id, "ENT-SYNC-01", "Cliente Original", json.dumps({"document": {"client": "Cliente Original"}, "items": []}), "borrador")
            )
            entrega_id = conn.execute("SELECT id FROM entregas WHERE numero_entrega='ENT-SYNC-01'").fetchone()["id"]

            # Insertar garantía ligada
            conn.execute(
                "INSERT INTO garantias (cotizacion_id, numero_garantia, cliente_nombre, payload_json, activo) VALUES (?, ?, ?, ?, 1)",
                (cot_id, "GAR-SYNC-01", "Cliente Original", json.dumps({"document": {"client": "Cliente Original"}, "items": []}))
            )
            garantia_id = conn.execute("SELECT id FROM garantias WHERE numero_garantia='GAR-SYNC-01'").fetchone()["id"]

            conn.commit()
            conn.close()

            with app.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["user_id"] = editor_id
                    sess["user_role"] = "editor"

                payload = {
                    "quotation": {
                        "dbId": cot_id,
                        "number": "COT-SYNC-01",
                        "date": "2026-02-01",
                        "client": "Cliente Sincronizado SAS",
                        "city": "Bucaramanga",
                    },
                    "items": [
                        {
                            "title": "Equipo Sync",
                            "price": 2500.0,
                            "quantity": 1,
                        }
                    ],
                }

                res = client.post(
                    "/cotizaciones/guardar",
                    data=json.dumps(payload),
                    content_type="application/json",
                )
                self.assertEqual(res.status_code, 200)

                # Verificar sincronización de ítems en la entrega y garantía ligadas
                conn = app.get_db_connection()
                ent_row = conn.execute("SELECT payload_json FROM entregas WHERE id=?", (entrega_id,)).fetchone()
                ent_payload = json.loads(ent_row["payload_json"])
                self.assertEqual(ent_payload["items"][0]["title"], "Equipo Sync")
                self.assertEqual(ent_payload["totals"]["grandTotal"], 2500.0)

                gar_row = conn.execute("SELECT payload_json FROM garantias WHERE id=?", (garantia_id,)).fetchone()
                gar_payload = json.loads(gar_row["payload_json"])
                self.assertEqual(gar_payload["items"][0]["title"], "Equipo Sync")
                self.assertEqual(gar_payload["totals"]["grandTotal"], 2500.0)

                conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)


if __name__ == "__main__":
    unittest.main()
