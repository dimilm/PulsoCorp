def calc_discount_pct(current_price: float | None, fair_value: float | None) -> float | None:
    if not current_price or not fair_value:
        return None
    return ((current_price - fair_value) / fair_value) * 100


def calc_target_distance_pct(current_price: float | None, target: float | None) -> float | None:
    if not current_price or not target:
        return None
    return ((target - current_price) / current_price) * 100
