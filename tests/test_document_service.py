import os
import sqlite3
import tempfile
import unittest

from db.schema import ensure_auth_schema
from services.document_service import load_entrega_payload, load_garantia_payload


class TestDocumentServiceLoaders(unittest.TestCase):
    """Pruebas unitarias directas para los lectores de servicios documentales."""

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

    def tearDown(self):
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

    def test_load_entrega_payload_existing_and_non_existing(self):
        """Verifica la carga de payload de entrega existente y no existente."""
        conn = sqlite3.connect(self.temp_db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("CREATE TABLE cotizaciones (id INTEGER PRIMARY KEY AUTOINCREMENT)")
            ensure_auth_schema(conn)

            # Probar ID inexistente
            row, payload = load_entrega_payload(conn, 999)
            self.assertIsNone(row)
            self.assertIsNone(payload)

            # Insertar registro de entrega de prueba
            cursor = conn.execute("""
                INSERT INTO entregas (
                    cotizacion_id, numero_entrega, fecha_entrega, cliente_nombre,
                    cliente_documento, recibe_nombre, entrega_nombre, entrega_documento_texto,
                    texto_intro, total, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                10, "ENT-100", "2026-04-01", "Cliente Test",
                "DOC-123", "Juan Recibe", "Pedro Entrega", "Doc Texto",
                "Intro Texto", 1500.00, '{"document": {"number": "ENT-100"}, "items": []}'
            ))
            entrega_id = cursor.lastrowid
            conn.commit()

            row, payload = load_entrega_payload(conn, entrega_id)
            self.assertIsNotNone(row)
            self.assertIsNotNone(payload)
            self.assertEqual(payload["document"]["dbId"], entrega_id)
            self.assertEqual(payload["document"]["number"], "ENT-100")
            self.assertEqual(payload["document"]["client"], "Cliente Test")
        finally:
            conn.close()

    def test_load_garantia_payload_existing_and_non_existing(self):
        """Verifica la carga de payload de garantía existente (activo=1) e inactiva/no existente."""
        conn = sqlite3.connect(self.temp_db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("CREATE TABLE cotizaciones (id INTEGER PRIMARY KEY AUTOINCREMENT)")
            ensure_auth_schema(conn)

            # Probar ID inexistente
            row, payload = load_garantia_payload(conn, 999)
            self.assertIsNone(row)
            self.assertIsNone(payload)

            # Insertar garantía activa
            cursor = conn.execute("""
                INSERT INTO garantias (
                    cotizacion_id, numero_garantia, fecha_emision, fecha_vencimiento,
                    cliente_nombre, cliente_documento, texto_garantia, total, payload_json, activo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                10, "GAR-100", "2026-04-01", "2027-04-01",
                "Cliente Test", "DOC-123", "Garantia Texto", 1500.00,
                '{"document": {"number": "GAR-100"}, "items": []}', 1
            ))
            garantia_id = cursor.lastrowid

            # Insertar garantía inactiva (activo=0)
            conn.execute("""
                INSERT INTO garantias (
                    cotizacion_id, numero_garantia, fecha_emision, fecha_vencimiento,
                    cliente_nombre, cliente_documento, texto_garantia, total, payload_json, activo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                10, "GAR-999", "2026-04-01", "2027-04-01",
                "Cliente Inactivo", "DOC-000", "Garantia Inactiva", 500.00, None, 0
            ))
            conn.commit()

            # Garantía activa debe cargar correctamente
            row, payload = load_garantia_payload(conn, garantia_id)
            self.assertIsNotNone(row)
            self.assertIsNotNone(payload)
            self.assertEqual(payload["document"]["dbId"], garantia_id)
            self.assertEqual(payload["document"]["number"], "GAR-100")

            # Garantía inactiva (activo=0) debe retornar None, None
            inactiva_row, inactiva_payload = load_garantia_payload(conn, garantia_id + 1)
            self.assertIsNone(inactiva_row)
            self.assertIsNone(inactiva_payload)
        finally:
            conn.close()
