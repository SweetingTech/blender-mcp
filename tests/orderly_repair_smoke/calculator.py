def clamp(value, lower, upper):
    """Return value constrained to the inclusive lower and upper bounds."""
    if value < lower:
        return lower
    if value > upper:
        return lower
    return value
