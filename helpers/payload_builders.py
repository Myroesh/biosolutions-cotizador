from datetime import date
from helpers.formatting import add_one_year_safe

def build_initial_entrega_payload(cot_row, cot_payload, numero_entrega):
    quotation = cot_payload.get("quotation", {}) or {}
    items = cot_payload.get("items", []) or []

    fecha_entrega = (quotation.get("date") or "").strip() or date.today().isoformat()
    cliente = (quotation.get("client") or "").strip()
    total = float(cot_row["total"] or 0)

    entrega_items = []
    for idx, item in enumerate(items):
        try:
            quantity = int(float(str(item.get("quantity", "1")).replace(",", "").strip() or 1))
        except ValueError:
            quantity = 1

        if quantity < 1:
            quantity = 1

        try:
            unit_price = float(str(item.get("price", "0")).replace(",", "").strip() or 0)
        except ValueError:
            unit_price = 0

        entrega_items.append({
            "id": item.get("id") or f"ent_item_{idx+1}",
            "title": (item.get("title") or "").strip(),
            "brand": (item.get("brand") or "").strip(),
            "model": (item.get("model") or "").strip(),
            "quantity": quantity,
            "unitPrice": unit_price,
            "totalPrice": round(unit_price * quantity, 2),
            "serials": ["" for _ in range(quantity)]
        })

    return {
        "document": {
            "dbId": None,
            "cotizacionId": cot_row["id"],
            "number": numero_entrega,
            "date": fecha_entrega,
            "client": cliente,
            "clientDocument": "",
            "receivesName": cliente,
            "deliversName": "Daniel André Bosco Saavedra",
            "delivererText": "El señor Daniel André Bosco Saavedra con Cedula de Identidad No.8783262",
            "introText": "Por medio del presente documento se deja constancia de la entrega de los siguientes equipos, en conformidad con lo acordado entre las partes."
        },
        "items": entrega_items,
        "totals": {
            "grandTotal": total
        }
    }


def build_initial_garantia_payload(cot_row, cot_payload, numero_garantia):
    quotation = cot_payload.get("quotation", {}) or {}
    items = cot_payload.get("items", []) or []

    issue_date = (quotation.get("date") or "").strip() or date.today().isoformat()
    expiry_date = add_one_year_safe(issue_date)
    cliente = (quotation.get("client") or "").strip()
    total = float(cot_row["total"] or 0)

    garantia_items = []
    for idx, item in enumerate(items):
        try:
            quantity = int(float(str(item.get("quantity", "1")).replace(",", "").strip() or 1))
        except ValueError:
            quantity = 1

        if quantity < 1:
            quantity = 1

        try:
            unit_price = float(str(item.get("price", "0")).replace(",", "").strip() or 0)
        except ValueError:
            unit_price = 0

        garantia_items.append({
            "id": item.get("id") or f"gar_item_{idx+1}",
            "title": (item.get("title") or "").strip(),
            "brand": (item.get("brand") or "").strip(),
            "model": (item.get("model") or "").strip(),
            "quantity": quantity,
            "unitPrice": unit_price,
            "totalPrice": round(unit_price * quantity, 2),
            "serials": ["" for _ in range(quantity)]
        })

    return {
        "document": {
            "dbId": None,
            "cotizacionId": cot_row["id"],
            "number": numero_garantia,
            "issueDate": issue_date,
            "expiryDate": expiry_date,
            "client": cliente,
            "clientDocument": "",
            "warrantyText": """La garantía no cubre ninguna forma daños al equipo por: caídas, golpes, mal uso del mismo, daños por agua o humedad, ni ningún tipo de daño intencional o producto de la negligencia o impericia del cliente, se recomienda leer el manual cuidadosamente antes del uso
* En caso de mal funcionamiento del equipo la garantía no implica necesariamente la devolución del dinero, sino que la empresa se compromete a reparar el equipo, siendo responsabilidad del cliente el llevarlo a dependencias de la empresa. O de no ser posible la reparación la entrega de un equipo del mismo modelo o calidad similar en el plazo máximo de 30 días hábiles si es que fuera necesaria la importación de este. Guardándose la empresa la posibilidad de devolver el dinero si es que viera esto como más conveniente
* La garantía solo cubre mal funcionamiento del equipo. No equipos cuyo funcionamiento o características no estén de acuerdo al gusto del cliente, ya que se entiende que el cliente compra los equipos en el estado en el que se le ofrecen no pudiendo reclamar después por estos."""
        },
        "items": garantia_items,
        "totals": {
            "grandTotal": total
        }
    }


def copy_serials_between_payloads(source_payload, target_payload):
    if not isinstance(source_payload, dict) or not isinstance(target_payload, dict):
        return target_payload

    source_items = source_payload.get("items", []) or []
    target_items = target_payload.get("items", []) or []

    for idx, source_item in enumerate(source_items):
        if idx >= len(target_items):
            continue

        source_serials = list(source_item.get("serials", []) or [])
        target_quantity = int(target_items[idx].get("quantity") or 1)

        if target_quantity < 1:
            target_quantity = 1

        normalized_serials = []
        for i in range(target_quantity):
            if i < len(source_serials):
                normalized_serials.append((source_serials[i] or "").strip())
            else:
                normalized_serials.append("")

        target_items[idx]["serials"] = normalized_serials

    target_payload["items"] = target_items
    return target_payload


def rebuild_document_items_from_cotizacion_payload(cot_payload, document_payload):
    if not isinstance(cot_payload, dict) or not isinstance(document_payload, dict):
        return document_payload

    cot_items = cot_payload.get("items", []) or []
    existing_items = document_payload.get("items", []) or []

    existing_by_id = {}
    for item in existing_items:
        item_id = (item.get("id") or "").strip()
        if item_id:
            existing_by_id[item_id] = item

    rebuilt_items = []

    for idx, item in enumerate(cot_items):
        item_id = (item.get("id") or f"doc_item_{idx+1}").strip()

        try:
            quantity = int(float(str(item.get("quantity", "1")).replace(",", "").strip() or 1))
        except ValueError:
            quantity = 1

        if quantity < 1:
            quantity = 1

        try:
            unit_price = float(str(item.get("price", "0")).replace(",", "").strip() or 0)
        except ValueError:
            unit_price = 0

        previous_item = existing_by_id.get(item_id, {})
        previous_serials = list(previous_item.get("serials", []) or [])

        normalized_serials = []
        for i in range(quantity):
            if i < len(previous_serials):
                normalized_serials.append((previous_serials[i] or "").strip())
            else:
                normalized_serials.append("")

        rebuilt_items.append({
            "id": item_id,
            "title": (item.get("title") or "").strip(),
            "brand": (item.get("brand") or "").strip(),
            "model": (item.get("model") or "").strip(),
            "quantity": quantity,
            "unitPrice": unit_price,
            "totalPrice": round(unit_price * quantity, 2),
            "serials": normalized_serials
        })

    document_payload["items"] = rebuilt_items
    return document_payload
