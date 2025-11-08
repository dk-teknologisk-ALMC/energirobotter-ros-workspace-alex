def interval_map(x, x0, x1, y0, y1, clamp=True):

    # x: value
    # [x0, x1]: original interval
    # [y0, y1]: target interval
    # clamp: Boolean to choose to clamp x within [x0, x1] to avoid out-of-bounds mapping. Default is True.

    if x0 == x1:
        return y0  # Avoid division by zero; return y0 by default

    if clamp:
        x = max(min(x, x1), x0)

    return ((y0 * (x1 - x)) + (y1 * (x - x0))) / (x1 - x0)
