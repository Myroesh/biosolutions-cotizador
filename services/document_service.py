import json


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
