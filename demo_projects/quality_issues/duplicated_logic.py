def format_user_name(first_name: str, last_name: str) -> str:
    full_name = first_name.strip() + " " + last_name.strip()

    if len(full_name) > 50:
        full_name = full_name[:50]

    return full_name.lower().title()


def format_customer_name(first_name: str, last_name: str) -> str:
    full_name = first_name.strip() + " " + last_name.strip()

    if len(full_name) > 50:
        full_name = full_name[:50]

    return full_name.lower().title()


def calculate_total(items: list[float], tax_rate: float) -> float:
    total = 0

    for item in items:
        total = total + item

    if tax_rate > 0:
        total = total + (total * tax_rate)

    return total