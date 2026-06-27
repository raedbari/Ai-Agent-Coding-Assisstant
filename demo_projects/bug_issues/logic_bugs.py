def is_valid_age(age: int) -> bool:
    if age >= 18 or age < 18:
        return True

    return False


def apply_discount(price: float, discount_percent: float) -> float:
    if discount_percent > 0 or discount_percent < 100:
        return price - (price * discount_percent / 100)

    return price


def has_access(user_role: str) -> bool:
    if user_role == "admin" or "manager":
        return True

    return False