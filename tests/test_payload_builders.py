import os
import sys
import unittest
from datetime import date

# Asegurar que el directorio raíz esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import (
    build_initial_entrega_payload,
    build_initial_garantia_payload,
    copy_serials_between_payloads,
    rebuild_document_items_from_cotizacion_payload,
)


class TestPayloadBuilders(unittest.TestCase):
    """Pruebas unitarias puras para la construcción y manipulación de payloads de entregas y garantías."""

    def setUp(self):
        self.sample_cot_row = {"id": 10, "total": 2500.50}
        self.sample_cot_payload = {
            "quotation": {
                "date": "2026-03-15",
                "client": "Hospital Central Bio",
            },
            "items": [
                {
                    "id": "item_101",
                    "title": "Centrífuga Digital",
                    "brand": "BioBrand",
                    "model": "C-2000",
                    "quantity": "2",
                    "price": "1,250.25",
                }
            ],
        }

    def test_build_initial_entrega_payload_structure(self):
        """Verifica la estructura básica de entrega con datos completos."""
        result = build_initial_entrega_payload(
            self.sample_cot_row, self.sample_cot_payload, "ENT-001"
        )

        doc = result["document"]
        self.assertIsNone(doc["dbId"])
        self.assertEqual(doc["cotizacionId"], 10)
        self.assertEqual(doc["number"], "ENT-001")
        self.assertEqual(doc["date"], "2026-03-15")
        self.assertEqual(doc["client"], "Hospital Central Bio")
        self.assertEqual(doc["receivesName"], "Hospital Central Bio")
        self.assertEqual(doc["deliversName"], "Daniel André Bosco Saavedra")
        self.assertTrue(isinstance(doc["introText"], str) and len(doc["introText"]) > 0)

        self.assertEqual(result["totals"]["grandTotal"], 2500.50)

        items = result["items"]
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["id"], "item_101")
        self.assertEqual(item["title"], "Centrífuga Digital")
        self.assertEqual(item["brand"], "BioBrand")
        self.assertEqual(item["model"], "C-2000")
        self.assertEqual(item["quantity"], 2)
        self.assertEqual(item["unitPrice"], 1250.25)
        self.assertEqual(item["totalPrice"], round(2 * 1250.25, 2))
        self.assertEqual(len(item["serials"]), item["quantity"])
        self.assertEqual(item["serials"], ["", ""])

    def test_build_initial_garantia_payload_structure_and_dates(self):
        """Verifica la estructura de garantía, incluyendo issueDate, expiryDate y warrantyText."""
        result = build_initial_garantia_payload(
            self.sample_cot_row, self.sample_cot_payload, "GAR-001"
        )

        doc = result["document"]
        self.assertIsNone(doc["dbId"])
        self.assertEqual(doc["cotizacionId"], 10)
        self.assertEqual(doc["number"], "GAR-001")
        self.assertEqual(doc["issueDate"], "2026-03-15")
        self.assertEqual(doc["expiryDate"], "2027-03-15")
        self.assertEqual(doc["client"], "Hospital Central Bio")
        self.assertTrue(
            isinstance(doc["warrantyText"], str) and len(doc["warrantyText"]) > 0
        )

        self.assertEqual(result["totals"]["grandTotal"], 2500.50)

        items = result["items"]
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["quantity"], 2)
        self.assertEqual(item["unitPrice"], 1250.25)
        self.assertEqual(item["totalPrice"], round(2 * 1250.25, 2))
        self.assertEqual(len(item["serials"]), item["quantity"])

    def test_quantity_normalization_and_serials_length(self):
        """Verifica la conversión y normalización de cantidades raras, nulas o negativas."""
        cot_payload = {
            "quotation": {"date": "2026-01-01", "client": "Cliente Pruebas"},
            "items": [
                {"title": "Item Cero", "quantity": "0", "price": "100"},
                {"title": "Item Negativo", "quantity": "-5", "price": "200"},
                {"title": "Item Float", "quantity": "3.5", "price": "50"},
                {"title": "Item Invalido", "quantity": "abc", "price": "80"},
            ],
        }

        result = build_initial_entrega_payload(self.sample_cot_row, cot_payload, "ENT-002")
        items = result["items"]
        self.assertEqual(len(items), 4)

        # Cantidad <= 0 se fuerza a 1
        self.assertEqual(items[0]["quantity"], 1)
        self.assertEqual(len(items[0]["serials"]), 1)

        self.assertEqual(items[1]["quantity"], 1)
        self.assertEqual(len(items[1]["serials"]), 1)

        # Float "3.5" int(float("3.5")) da 3
        self.assertEqual(items[2]["quantity"], 3)
        self.assertEqual(len(items[2]["serials"]), 3)

        # Texto inválido "abc" se captura y fuerza a 1
        self.assertEqual(items[3]["quantity"], 1)
        self.assertEqual(len(items[3]["serials"]), 1)

    def test_total_price_calculation_and_rounding(self):
        """Verifica que totalPrice sea exactamente quantity * unitPrice redondeado a 2 decimales."""
        cot_payload = {
            "quotation": {"date": "2026-01-01", "client": "Cliente Pruebas"},
            "items": [
                {"title": "Item Precios", "quantity": "3", "price": "33.3333"},
            ],
        }

        result = build_initial_garantia_payload(self.sample_cot_row, cot_payload, "GAR-002")
        item = result["items"][0]
        self.assertEqual(item["quantity"], 3)
        self.assertEqual(item["unitPrice"], 33.3333)
        self.assertEqual(item["totalPrice"], round(3 * 33.3333, 2))

    def test_empty_date_defaults_to_today(self):
        """Verifica que si la fecha en quotation está vacía o None se use date.today().isoformat()."""
        cot_payload_empty_date = {
            "quotation": {"date": "", "client": "Cliente Sin Fecha"},
            "items": [],
        }
        today_iso = date.today().isoformat()

        res_ent = build_initial_entrega_payload(
            self.sample_cot_row, cot_payload_empty_date, "ENT-003"
        )
        self.assertEqual(res_ent["document"]["date"], today_iso)

        res_gar = build_initial_garantia_payload(
            self.sample_cot_row, cot_payload_empty_date, "GAR-003"
        )
        self.assertEqual(res_gar["document"]["issueDate"], today_iso)

    def test_items_without_id_generates_fallback_id(self):
        """Verifica que si un ítem no tiene id, se le asigne una clave id por defecto basada en la posición."""
        cot_payload = {
            "quotation": {"date": "2026-01-01", "client": "Cliente Pruebas"},
            "items": [
                {"title": "Item Sin ID", "quantity": "1", "price": "100"},
            ],
        }

        res_ent = build_initial_entrega_payload(self.sample_cot_row, cot_payload, "ENT-004")
        self.assertEqual(res_ent["items"][0]["id"], "ent_item_1")

        res_gar = build_initial_garantia_payload(self.sample_cot_row, cot_payload, "GAR-004")
        self.assertEqual(res_gar["items"][0]["id"], "gar_item_1")

    def test_copy_serials_between_payloads_normal_and_edge_cases(self):
        """Verifica la copia de seriales entre dos payloads y manejo de casos raros o nulos."""
        source = {
            "items": [
                {"quantity": 2, "serials": ["SN-100", "SN-101"]},
                {"quantity": 1, "serials": ["SN-200"]},
            ]
        }
        target = {
            "items": [
                {"quantity": 3, "serials": ["", "", ""]},
                {"quantity": 1, "serials": [""]},
            ]
        }

        res = copy_serials_between_payloads(source, target)
        self.assertEqual(res["items"][0]["serials"], ["SN-100", "SN-101", ""])
        self.assertEqual(res["items"][1]["serials"], ["SN-200"])

        # Casos no dict o vacíos
        self.assertIsNone(copy_serials_between_payloads(None, None))
        self.assertEqual(copy_serials_between_payloads(source, "invalid"), "invalid")

    def test_rebuild_document_items_from_cotizacion_payload_normal_and_edge_cases(self):
        """Verifica el re-ensamblado de ítems de cotización manteniendo seriales previos por ID."""
        cot_payload = {
            "items": [
                {"id": "item_1", "title": "Equipo Actualizado", "quantity": "2", "price": "500"},
                {"id": "item_2", "title": "Accesorio Nuevo", "quantity": "1", "price": "50"},
            ]
        }
        doc_payload = {
            "items": [
                {"id": "item_1", "title": "Equipo Viejo", "quantity": 1, "serials": ["SN-ORIGINAL"]},
            ]
        }

        res = rebuild_document_items_from_cotizacion_payload(cot_payload, doc_payload)
        items = res["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "Equipo Actualizado")
        self.assertEqual(items[0]["serials"], ["SN-ORIGINAL", ""])
        self.assertEqual(items[1]["title"], "Accesorio Nuevo")
        self.assertEqual(items[1]["serials"], [""])

        # Caso no dict
        self.assertEqual(rebuild_document_items_from_cotizacion_payload("invalid", doc_payload), doc_payload)


if __name__ == "__main__":
    unittest.main()

