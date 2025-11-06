def speed_color(v):
    try:
        digits = ''.join(ch for ch in str(v) if ch.isdigit())
        v = int(digits) if digits else None
    except Exception:
        v = None
    if v is None: return "#9e9e9e"
    if v <= 30: return "#1a9850"
    if v <= 50: return "#66bd63"
    if v <= 70: return "#fee08b"
    if v <= 90: return "#fdae61"
    return "#d73027"
