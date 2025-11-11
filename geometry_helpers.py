import math
def snap(x, y, enabled, step):
    if not enabled:
        return x, y
    return round(x / step) * step, round(y / step) * step

def fmt(x):
    return f"{x:.2f}"

def rotate_point(px, py, cx, cy, deg):
    """Rotate (px,py) about (cx,cy) by deg degrees (canvas y grows downward)."""
    th = math.radians(deg)
    s, c = math.sin(th), math.cos(th)
    x, y = px - cx, py - cy
    # Standard rotation in canvas coords:
    rx = x * c - y * s
    ry = x * s + y * c
    return cx + rx, cy + ry

def poly_from_ellipse(cx, cy, rx, ry, deg=0, segments=96):
    pts = []
    for i in range(segments):
        t = 2 * math.pi * i / segments
        x = cx + rx * math.cos(t)
        y = cy + ry * math.sin(t)
        if abs(deg) > 1e-9:
            x, y = rotate_point(x, y, cx, cy, deg)
        pts.append((x, y))
    return pts

def rect_corners_from_p0p1(p0, p1, deg=0):
    x0, y0 = p0
    x1, y1 = p1
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = abs(x1 - x0), abs(y1 - y0)
    corners = [
        (cx - w/2, cy - h/2),
        (cx + w/2, cy - h/2),
        (cx + w/2, cy + h/2),
        (cx - w/2, cy + h/2),
    ]
    if abs(deg) > 1e-9:
        corners = [rotate_point(x, y, cx, cy, deg) for (x, y) in corners]
    return corners

def distance(p, q):
    return math.hypot(p[0]-q[0], p[1]-q[1])

def angle_between(p0, p1):
    """Angle in degrees from p0 to p1 (canvas y grows downward)."""
    return math.degrees(math.atan2(p1[1]-p0[1], p1[0]-p0[0]))
