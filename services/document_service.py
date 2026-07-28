import json
from helpers.payload_builders import (
    copy_serials_between_payloads,
    rebuild_document_items_from_cotizacion_payload,
)


def load_entrega_payload(conn, entrega_id):
    row = conn.execute("""
        SELECT *
        FROM entregas
        WHERE id = ?
    """, (entrega_id,)).fetchone()

    if not row:
        return None, None

    payload_json = (row["payload_json"] or "").strip()
    payload = None

    if payload_json:
        try:
            payload = json.loads(payload_json)
        except Exception as e:
            print("WARNING load_entrega_payload:", e)
            payload = None

    if not isinstance(payload, dict):
        payload = {
            "document": {
                "dbId": row["id"],
                "cotizacionId": row["cotizacion_id"],
                "number": row["numero_entrega"] or "",
                "date": row["fecha_entrega"] or "",
                "client": row["cliente_nombre"] or "",
                "clientDocument": row["cliente_documento"] or "",
                "receivesName": row["recibe_nombre"] or "",
                "deliversName": row["entrega_nombre"] or "",
                "delivererText": row["entrega_documento_texto"] or "",
                "introText": row["texto_intro"] or ""
            },
            "items": [],
            "totals": {
                "grandTotal": float(row["total"] or 0)
            }
        }

    payload.setdefault("document", {})
    payload.setdefault("items", [])
    payload.setdefault("totals", {})

    payload["document"]["dbId"] = row["id"]
    payload["document"]["cotizacionId"] = row["cotizacion_id"]
    payload["document"]["number"] = payload["document"].get("number") or (row["numero_entrega"] or "")
    payload["document"]["date"] = payload["document"].get("date") or (row["fecha_entrega"] or "")
    payload["document"]["client"] = payload["document"].get("client") or (row["cliente_nombre"] or "")
    payload["document"]["clientDocument"] = payload["document"].get("clientDocument") or (row["cliente_documento"] or "")
    payload["document"]["receivesName"] = payload["document"].get("receivesName") or (row["recibe_nombre"] or "")
    payload["document"]["deliversName"] = payload["document"].get("deliversName") or (row["entrega_nombre"] or "")
    payload["document"]["delivererText"] = payload["document"].get("delivererText") or (row["entrega_documento_texto"] or "")
    payload["document"]["introText"] = payload["document"].get("introText") or (row["texto_intro"] or "")
    payload["totals"]["grandTotal"] = float(payload["totals"].get("grandTotal") or row["total"] or 0)

    return row, payload


def load_garantia_payload(conn, garantia_id):
    row = conn.execute("""
        SELECT *
        FROM garantias
        WHERE id = ?
          AND activo = 1
    """, (garantia_id,)).fetchone()

    if not row:
        return None, None

    payload_json = (row["payload_json"] or "").strip()
    payload = None

    if payload_json:
        try:
            payload = json.loads(payload_json)
        except Exception as e:
            print("WARNING load_garantia_payload:", e)
            payload = None

    if not isinstance(payload, dict):
        payload = {
            "document": {
                "dbId": row["id"],
                "cotizacionId": row["cotizacion_id"],
                "number": row["numero_garantia"] or "",
                "issueDate": row["fecha_emision"] or "",
                "expiryDate": row["fecha_vencimiento"] or "",
                "client": row["cliente_nombre"] or "",
                "clientDocument": row["cliente_documento"] or "",
                "warrantyText": row["texto_garantia"] or ""
            },
            "items": [],
            "totals": {
                "grandTotal": float(row["total"] or 0)
            }
        }

    payload.setdefault("document", {})
    payload.setdefault("items", [])
    payload.setdefault("totals", {})

    payload["document"]["dbId"] = row["id"]
    payload["document"]["cotizacionId"] = row["cotizacion_id"]
    payload["document"]["number"] = payload["document"].get("number") or (row["numero_garantia"] or "")
    payload["document"]["issueDate"] = payload["document"].get("issueDate") or (row["fecha_emision"] or "")
    payload["document"]["expiryDate"] = payload["document"].get("expiryDate") or (row["fecha_vencimiento"] or "")
    payload["document"]["client"] = payload["document"].get("client") or (row["cliente_nombre"] or "")
    payload["document"]["clientDocument"] = payload["document"].get("clientDocument") or (row["cliente_documento"] or "")
    payload["document"]["warrantyText"] = payload["document"].get("warrantyText") or (row["texto_garantia"] or "")
    payload["totals"]["grandTotal"] = float(payload["totals"].get("grandTotal") or row["total"] or 0)

    return row, payload


def sync_entrega_serials_to_garantia(conn, cotizacion_id, source_entrega_payload):
    garantia = conn.execute("""
        SELECT id
        FROM garantias
        WHERE cotizacion_id = ?
          AND activo = 1
        ORDER BY id DESC
        LIMIT 1
    """, (cotizacion_id,)).fetchone()

    if not garantia:
        return

    garantia_row, garantia_payload = load_garantia_payload(conn, garantia["id"])
    if not garantia_row or not garantia_payload:
        return

    garantia_payload = copy_serials_between_payloads(source_entrega_payload, garantia_payload)

    conn.execute("""
        UPDATE garantias
        SET payload_json = ?
        WHERE id = ?
    """, (
        json.dumps(garantia_payload, ensure_ascii=False),
        garantia_row["id"]
    ))


def sync_garantia_serials_to_entrega(conn, cotizacion_id, source_garantia_payload):
    entrega = conn.execute("""
        SELECT id
        FROM entregas
        WHERE cotizacion_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (cotizacion_id,)).fetchone()

    if not entrega:
        return

    entrega_row, entrega_payload = load_entrega_payload(conn, entrega["id"])
    if not entrega_row or not entrega_payload:
        return

    entrega_payload = copy_serials_between_payloads(source_garantia_payload, entrega_payload)

    conn.execute("""
        UPDATE entregas
        SET payload_json = ?
        WHERE id = ?
    """, (
        json.dumps(entrega_payload, ensure_ascii=False),
        entrega_row["id"]
    ))


def sync_entrega_structure_from_cotizacion(conn, cotizacion_id, cot_payload, total):
    entrega = conn.execute("""
        SELECT id
        FROM entregas
        WHERE cotizacion_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (cotizacion_id,)).fetchone()

    if not entrega:
        return

    entrega_row, entrega_payload = load_entrega_payload(conn, entrega["id"])
    if not entrega_row or not entrega_payload:
        return

    entrega_payload = rebuild_document_items_from_cotizacion_payload(cot_payload, entrega_payload)
    entrega_payload.setdefault("totals", {})
    entrega_payload["totals"]["grandTotal"] = float(total or 0)

    conn.execute("""
        UPDATE entregas
        SET total = ?, payload_json = ?
        WHERE id = ?
    """, (
        float(total or 0),
        json.dumps(entrega_payload, ensure_ascii=False),
        entrega_row["id"]
    ))


def sync_garantia_structure_from_cotizacion(conn, cotizacion_id, cot_payload, total):
    garantia = conn.execute("""
        SELECT id
        FROM garantias
        WHERE cotizacion_id = ?
          AND activo = 1
        ORDER BY id DESC
        LIMIT 1
    """, (cotizacion_id,)).fetchone()

    if not garantia:
        return

    garantia_row, garantia_payload = load_garantia_payload(conn, garantia["id"])
    if not garantia_row or not garantia_payload:
        return

    garantia_payload = rebuild_document_items_from_cotizacion_payload(cot_payload, garantia_payload)
    garantia_payload.setdefault("totals", {})
    garantia_payload["totals"]["grandTotal"] = float(total or 0)

    conn.execute("""
        UPDATE garantias
        SET total = ?, payload_json = ?
        WHERE id = ?
    """, (
        float(total or 0),
        json.dumps(garantia_payload, ensure_ascii=False),
        garantia_row["id"]
    ))
