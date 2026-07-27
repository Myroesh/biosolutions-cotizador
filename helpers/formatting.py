from datetime import datetime, timedelta

def normalize_image_path_for_db(image_value):
    image_value = (image_value or "").strip()
    if not image_value:
        return ""

    if image_value.startswith("/static/"):
        return image_value.replace("/static/", "", 1)

    if image_value.startswith("static/"):
        return image_value.replace("static/", "", 1)

    return image_value


def build_public_image_url(image_value):
    image_value = normalize_image_path_for_db(image_value)
    if not image_value:
        return ""
    return f"/static/{image_value}"


def add_one_year_safe(date_str):
    if not date_str:
        return ""

    base_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    try:
        return base_date.replace(year=base_date.year + 1).isoformat()
    except ValueError:
        return (base_date + timedelta(days=365)).isoformat()
