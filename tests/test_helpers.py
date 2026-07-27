import unittest
import sys
import os

# Asegurar que el directorio raíz esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import (
    normalize_image_path_for_db,
    build_public_image_url,
    add_one_year_safe,
)


class TestHelpers(unittest.TestCase):
    """Pruebas unitarias para funciones puras de utilidad en app.py que no tocan la base de datos."""

    def test_normalize_image_path_for_db_with_leading_slash(self):
        result = normalize_image_path_for_db("/static/uploads/cotizaciones/foto.png")
        self.assertEqual(result, "uploads/cotizaciones/foto.png")

    def test_normalize_image_path_for_db_without_leading_slash(self):
        result = normalize_image_path_for_db("static/uploads/cotizaciones/foto.png")
        self.assertEqual(result, "uploads/cotizaciones/foto.png")

    def test_normalize_image_path_for_db_already_normalized(self):
        result = normalize_image_path_for_db("  uploads/cotizaciones/foto.png ")
        self.assertEqual(result, "uploads/cotizaciones/foto.png")

    def test_normalize_image_path_for_db_empty_or_none(self):
        self.assertEqual(normalize_image_path_for_db(""), "")
        self.assertEqual(normalize_image_path_for_db(None), "")
        self.assertEqual(normalize_image_path_for_db("   "), "")

    def test_build_public_image_url_valid_path(self):
        result = build_public_image_url("/static/uploads/cotizaciones/foto.png")
        self.assertEqual(result, "/static/uploads/cotizaciones/foto.png")

    def test_build_public_image_url_relative_path(self):
        result = build_public_image_url("uploads/cotizaciones/foto.png")
        self.assertEqual(result, "/static/uploads/cotizaciones/foto.png")

    def test_build_public_image_url_empty_or_none(self):
        self.assertEqual(build_public_image_url(""), "")
        self.assertEqual(build_public_image_url(None), "")

    def test_add_one_year_safe_regular_date(self):
        self.assertEqual(add_one_year_safe("2026-02-28"), "2027-02-28")
        self.assertEqual(add_one_year_safe("2023-05-15"), "2024-05-15")

    def test_add_one_year_safe_leap_year(self):
        # El 29 de febrero de año bisiesto al sumar 1 año se convierte en 28 de febrero
        self.assertEqual(add_one_year_safe("2024-02-29"), "2025-02-28")

    def test_add_one_year_safe_empty_or_none(self):
        self.assertEqual(add_one_year_safe(""), "")
        self.assertEqual(add_one_year_safe(None), "")

    def test_add_one_year_safe_invalid_format_raises_value_error(self):
        with self.assertRaises(ValueError):
            add_one_year_safe("fecha-invalida")


if __name__ == "__main__":
    unittest.main()
