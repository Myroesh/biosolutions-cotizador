# Reglas de Desarrollo y Arquitectura - Biosolutions Cotizador

Este documento establece las normas permanentes de desarrollo, aislamiento y seguridad que deben cumplir todos los agentes y desarrolladores que colaboren en el codebase de `biosolutions-cotizador`.

---

## 1. Aislamiento e Inmutabilidad de la Base de Datos
- **Base de Datos Real:** Prohibido modificar, migrar o ejecutar pruebas unitarias/integración directamente sobre `biosolutions.db`.
- **Uso de Bases Temporales en Tests:** Toda suite de pruebas debe configurar `app.DB_PATH` apuntando a un archivo SQLite temporal creado con `tempfile.NamedTemporaryFile(suffix=".db")` y limpiado adecuadamente en `tearDown()` o bloques `finally`.
- **Verificación de Inmutabilidad:** Cada suite de pruebas debe validar en su `tearDown()` que la fecha de modificación (`mtime`) y el tamaño (`size`) del archivo real `biosolutions.db` permanezcan 100% inalterados.

---

## 2. Arquitectura DDL e Inicialización Centralizada
- **Inicialización Única:** La creación y migración del esquema relacional (tablas `usuarios`, `cotizaciones`, `cotizacion_items`, `entregas`, `garantias` y columnas JSON/auditoría) se realiza exclusivamente dentro de `init_db_schema()`.
- **Hooks WSGI / HTTP:** La inicialización automática se invoca centralizadamente mediante el decorador `@app.before_request` en `app.py`.
- **Controladores Limpios:** Prohibido llamar a funciones DDL internas (`ensure_auth_schema`, `ensure_payload_json_column`, `ensure_documentos_schema`, etc.) dentro de las funciones de ruta HTTP decoradas con `@app.route`.

---

## 3. Integridad del Frontend y Lógica de Negocio
- **Frontend Protegido:** Prohibido modificar archivos JavaScript de cliente (`static/app.js`) o plantillas HTML (`templates/`) a menos que el usuario lo solicite explícitamente.
- **Sincronización Bidireccional:** Preservar la lógica de sincronización de datos y números de serie entre cotizaciones, actas de entrega y certificados de garantía (`sync_entrega_serials_to_garantia`, `sync_garantia_serials_to_entrega`, `sync_entrega_structure_from_cotizacion`, `sync_garantia_structure_from_cotizacion`).

---

## 4. Archivos Excluidos y Seguridad del Repositorio
- **Archivos Sensibles:** No agregar al control de versiones (`git`) los siguientes tipos de archivo:
  - Bases de datos SQLite (`*.db`, `*.sqlite`, `*.sqlite3`).
  - Archivos de respaldo o exportaciones (`backups/`, `exports/`, `*.zip`).
  - Entornos virtuales (`venv/`, `.venv/`).
  - Archivos compilados o caché (`__pycache__/`, `*.pyc`, `.pytest_cache/`).
  - Variables de entorno o secretos (`.env`, `.env.*`, `*.pem`, `*.key`).
  - Imágenes cargadas dinámicamente (`static/uploads/cotizaciones/*`).

---

## 5. Protocolo Obligatorio de Verificación
- Antes de dar por finalizada cualquier tarea o proponer un cambio al usuario, se debe ejecutar la suite completa de pruebas:
  ```bash
  ./venv/bin/python -m unittest discover -s tests -v
  ```
- Todas las pruebas deben ejecutarse sin errores ni fallos (`OK`).
