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


class TestDocSaveRoutesClean(unittest.TestCase):
    """Pruebas de integración para las rutas de guardado de entrega y garantía sin llamadas DDL redundantes."""

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

    def _create_sample_entrega_payload(self, cot_id=1, entrega_id=1):
        return {
            "document": {
                "dbId": entrega_id,
                "cotizacionId": cot_id,
                "number": "ENT-001",
                "date": "2026-01-01",
                "client": "Cliente Inicial",
                "clientDocument": "123456",
                "receivesName": "Juan Recibe",
                "deliversName": "Pedro Entrega",
                "delivererText": "Texto Entrega",
                "introText": "Texto Intro",
            },
            "items": [
                {
                    "id": 1,
                    "name": "Equipo Test",
                    "quantity": 1,
                    "serials": [""],
                }
            ],
        }

    def _create_sample_garantia_payload(self, cot_id=1, garantia_id=1):
        return {
            "document": {
                "dbId": garantia_id,
                "cotizacionId": cot_id,
                "number": "GAR-001",
                "issueDate": "2026-01-01",
                "expiryDate": "2027-01-01",
                "client": "Cliente Inicial",
                "clientDocument": "123456",
                "warrantyText": "Texto Garantia",
            },
            "items": [
                {
                    "id": 1,
                    "name": "Equipo Test",
                    "quantity": 1,
                    "serials": [""],
                }
            ],
        }

    def test_guardar_entrega_updates_db_and_syncs_serials_to_garantia(self):
        """Verifica que /entregas/<id>/guardar actualice el acta y sincronice seriales con la garantía activa."""
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
                ("editor_save_ent", generate_password_hash("pass"), "Editor Save Ent", "editor")
            )
            editor_id = conn.execute("SELECT id FROM usuarios WHERE username='editor_save_ent'").fetchone()["id"]

            # Insertar cotización
            conn.execute(
                "INSERT INTO cotizaciones (numero, cliente, ciudad, total, estado_documental) VALUES (?, ?, ?, ?, ?)",
                ("COT-SAVE-1", "Cliente COT", "Bogotá", 1000.0, "consolidada")
            )
            cot_id = conn.execute("SELECT id FROM cotizaciones WHERE numero='COT-SAVE-1'").fetchone()["id"]

            # Insertar entrega
            entrega_json = json.dumps(self._create_sample_entrega_payload(cot_id=cot_id, entrega_id=1))
            conn.execute(
                "INSERT INTO entregas (cotizacion_id, numero_entrega, cliente_nombre, payload_json, estado) VALUES (?, ?, ?, ?, ?)",
                (cot_id, "ENT-001", "Cliente Inicial", entrega_json, "borrador")
            )
            entrega_id = conn.execute("SELECT id FROM entregas WHERE numero_entrega='ENT-001'").fetchone()["id"]

            # Insertar garantía asociada activa
            garantia_json = json.dumps(self._create_sample_garantia_payload(cot_id=cot_id, garantia_id=1))
            conn.execute(
                "INSERT INTO garantias (cotizacion_id, numero_garantia, cliente_nombre, payload_json, activo) VALUES (?, ?, ?, ?, 1)",
                (cot_id, "GAR-001", "Cliente Inicial", garantia_json)
            )
            garantia_id = conn.execute("SELECT id FROM garantias WHERE numero_garantia='GAR-001'").fetchone()["id"]

            conn.commit()
            conn.close()

            with app.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["user_id"] = editor_id
                    sess["user_role"] = "editor"

                # Guardar entrega actualizando número y serial
                res = client.post(
                    f"/entregas/{entrega_id}/guardar",
                    data={
                        "number": "ENT-UPDATED-99",
                        "date": "2026-02-01",
                        "client": "Cliente Entrega Actualizado",
                        "clientDocument": "999999",
                        "receivesName": "Juan Recibe Nomb",
                        "deliversName": "Pedro Entregador",
                        "delivererText": "Texto Entregador",
                        "introText": "Texto Intro Nomb",
                        "estado": "emitida",
                        "serials[]": ["SERIAL-ENTREGA-12345"],
                    }
                )
                self.assertIn(res.status_code, (200, 302))

                # Verificar actualización de la entrega
                conn = app.get_db_connection()
                ent_row = conn.execute("SELECT * FROM entregas WHERE id=?", (entrega_id,)).fetchone()
                self.assertEqual(ent_row["numero_entrega"], "ENT-UPDATED-99")
                self.assertEqual(ent_row["estado"], "emitida")

                ent_payload = json.loads(ent_row["payload_json"])
                self.assertEqual(ent_payload["items"][0]["serials"][0], "SERIAL-ENTREGA-12345")

                # Verificar sincronización a la garantía
                gar_row = conn.execute("SELECT payload_json FROM garantias WHERE id=?", (garantia_id,)).fetchone()
                gar_payload = json.loads(gar_row["payload_json"])
                self.assertEqual(gar_payload["items"][0]["serials"][0], "SERIAL-ENTREGA-12345")

                conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_guardar_garantia_updates_db_and_syncs_serials_to_entrega(self):
        """Verifica que /garantias/<id>/guardar actualice la garantía y sincronice seriales con el acta de entrega."""
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
                ("editor_save_gar", generate_password_hash("pass"), "Editor Save Gar", "editor")
            )
            editor_id = conn.execute("SELECT id FROM usuarios WHERE username='editor_save_gar'").fetchone()["id"]

            # Insertar cotización
            conn.execute(
                "INSERT INTO cotizaciones (numero, cliente, ciudad, total, estado_documental) VALUES (?, ?, ?, ?, ?)",
                ("COT-SAVE-2", "Cliente COT 2", "Medellín", 2000.0, "consolidada")
            )
            cot_id = conn.execute("SELECT id FROM cotizaciones WHERE numero='COT-SAVE-2'").fetchone()["id"]

            # Insertar entrega
            entrega_json = json.dumps(self._create_sample_entrega_payload(cot_id=cot_id, entrega_id=2))
            conn.execute(
                "INSERT INTO entregas (cotizacion_id, numero_entrega, cliente_nombre, payload_json, estado) VALUES (?, ?, ?, ?, ?)",
                (cot_id, "ENT-002", "Cliente Inicial 2", entrega_json, "borrador")
            )
            entrega_id = conn.execute("SELECT id FROM entregas WHERE numero_entrega='ENT-002'").fetchone()["id"]

            # Insertar garantía
            garantia_json = json.dumps(self._create_sample_garantia_payload(cot_id=cot_id, garantia_id=2))
            conn.execute(
                "INSERT INTO garantias (cotizacion_id, numero_garantia, cliente_nombre, payload_json, activo) VALUES (?, ?, ?, ?, 1)",
                (cot_id, "GAR-002", "Cliente Inicial 2", garantia_json)
            )
            garantia_id = conn.execute("SELECT id FROM garantias WHERE numero_garantia='GAR-002'").fetchone()["id"]

            conn.commit()
            conn.close()

            with app.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["user_id"] = editor_id
                    sess["user_role"] = "editor"

                # Guardar garantía actualizando número y serial
                res = client.post(
                    f"/garantias/{garantia_id}/guardar",
                    data={
                        "number": "GAR-UPDATED-88",
                        "issueDate": "2026-03-01",
                        "expiryDate": "2027-03-01",
                        "client": "Cliente Garantia Actualizado",
                        "clientDocument": "888888",
                        "warrantyText": "Texto Garantia Modificado",
                        "serials[]": ["SERIAL-GARANTIA-99999"],
                    }
                )
                self.assertIn(res.status_code, (200, 302))

                # Verificar actualización de la garantía
                conn = app.get_db_connection()
                gar_row = conn.execute("SELECT * FROM garantias WHERE id=?", (garantia_id,)).fetchone()
                self.assertEqual(gar_row["numero_garantia"], "GAR-UPDATED-88")

                gar_payload = json.loads(gar_row["payload_json"])
                self.assertEqual(gar_payload["items"][0]["serials"][0], "SERIAL-GARANTIA-99999")

                # Verificar sincronización al acta de entrega
                ent_row = conn.execute("SELECT payload_json FROM entregas WHERE id=?", (entrega_id,)).fetchone()
                ent_payload = json.loads(ent_row["payload_json"])
                self.assertEqual(ent_payload["items"][0]["serials"][0], "SERIAL-GARANTIA-99999")

                conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)


if __name__ == "__main__":
    unittest.main()
