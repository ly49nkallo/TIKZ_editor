import math
from geometry_helpers import *
HANDLE_SIZE = 4

class Shape:
    color = "black"
    width = 2
    fill_enabled = False
    fill_color = "gray"
    fill_opacity = 1.0  # used in TikZ only
    angle = 0.0         # rotation (deg); not all shapes use it

    def draw(self, canvas): ...
    def to_tikz(self): ...
    def handles(self): return []         # list of (x,y,kind)
    def move_by(self, dx, dy): ...
    def rotate_by(self, ddeg): ...
    def rotate_to(self, deg): ...
    def on_handle_drag(self, kind, x, y): ...

# ============================== Primitives ==============================

class LineSeg(Shape):
    def __init__(self, p0, p1, color="black", width=2,
                 fill_enabled=False, fill_color="gray", fill_opacity=1.0):
        self.p0 = p0
        self.p1 = p1
        self.color = color
        self.width = width
        self.fill_enabled = False
        self.fill_color = fill_color
        self.fill_opacity = fill_opacity
        self._ids = []

    def center(self):
        return ((self.p0[0] + self.p1[0]) / 2, (self.p0[1] + self.p1[1]) / 2)

    def draw(self, canvas):
        for iid in self._ids:
            canvas.delete(iid)
        self._ids = [canvas.create_line(*self.p0, *self.p1,
                                        fill=self.color, width=self.width)]
        return self._ids

    def to_tikz(self):
        (x0, y0), (x1, y1) = self.p0, self.p1
        opts = [f"draw={self.color}", f"line width={self.width}pt"]
        return rf"\draw[{', '.join(opts)}] ({fmt(x0)},{fmt(y0)}) -- ({fmt(x1)},{fmt(y1)});"

    def handles(self):
        cx, cy = self.center()
        # rotation handle 36 px above center in local "up" direction
        rx, ry = cx, cy - 36
        return [(*self.p0, "p0"), (*self.p1, "p1"), (cx, cy, "move"), (rx, ry, "rotate")]

    def move_by(self, dx, dy):
        self.p0 = (self.p0[0] + dx, self.p0[1] + dy)
        self.p1 = (self.p1[0] + dx, self.p1[1] + dy)

    def rotate_by(self, ddeg):
        cx, cy = self.center()
        self.p0 = rotate_point(*self.p0, cx, cy, ddeg)
        self.p1 = rotate_point(*self.p1, cx, cy, ddeg)

    def rotate_to(self, deg):
        # not storing absolute angle; noop
        pass

    def on_handle_drag(self, kind, x, y):
        if kind == "p0":
            self.p0 = (x, y)
        elif kind == "p1":
            self.p1 = (x, y)
        elif kind == "move":
            pass  # handled by move_by
        elif kind == "rotate":
            pass  # handled in controller


class Arrow(LineSeg):
    """A line with an arrowhead at the end."""
    def draw(self, canvas):
        # reuse LineSeg draw but add an arrowhead polygon
        for iid in getattr(self, '_ids', []):
            canvas.delete(iid)
        self._ids = []
        # main shaft
        shaft = canvas.create_line(*self.p0, *self.p1, fill=self.color, width=self.width)
        self._ids.append(shaft)
        # compute simple triangular arrowhead
        x0, y0 = self.p0; x1, y1 = self.p1
        ang = math.atan2(y1 - y0, x1 - x0)
        head_len = max(8, 6 + self.width * 1.5)
        left = (x1 - head_len * math.cos(ang - math.pi/6), y1 - head_len * math.sin(ang - math.pi/6))
        right = (x1 - head_len * math.cos(ang + math.pi/6), y1 - head_len * math.sin(ang + math.pi/6))
        poly = canvas.create_polygon(x1, y1, left[0], left[1], right[0], right[1], fill=self.color, outline=self.color)
        self._ids.append(poly)
        return self._ids

    def to_tikz(self):
        (x0, y0), (x1, y1) = self.p0, self.p1
        opts = [f"draw={self.color}", f"line width={self.width}pt", "->"]
        return rf"\draw[{', '.join(opts)}] ({fmt(x0)},{fmt(y0)}) -- ({fmt(x1)},{fmt(y1)});"


class QuadBezier(Shape):
    def __init__(self, p0, p1, c, color="black", width=2,
                 fill_enabled=False, fill_color="gray", fill_opacity=1.0):
        self.p0 = p0      # start
        self.p1 = p1      # end
        self.c = c        # control
        self.color = color
        self.width = width
        self.fill_enabled = False
        self.fill_color = fill_color
        self.fill_opacity = fill_opacity
        self._ids = []

    def draw(self, canvas):
        for iid in self._ids:
            canvas.delete(iid)
        # approximate with polyline
        pts = []
        for i in range(64):
            t = i / 63
            mt = 1 - t
            x = mt*mt*self.p0[0] + 2*mt*t*self.c[0] + t*t*self.p1[0]
            y = mt*mt*self.p0[1] + 2*mt*t*self.c[1] + t*t*self.p1[1]
            pts.extend((x, y))
        line = canvas.create_line(*pts, fill=self.color, width=self.width)
        # subtle control point marker
        ctrl = canvas.create_oval(self.c[0]-2, self.c[1]-2, self.c[0]+2, self.c[1]+2,
                                  outline=self.color)
        self._ids = [line, ctrl]
        return self._ids

    def to_tikz(self):
        (x0, y0), (x1, y1), (cx, cy) = self.p0, self.p1, self.c
        opts = [f"draw={self.color}", f"line width={self.width}pt"]
        return (rf"\draw[{', '.join(opts)}] "
                f"({fmt(x0)},{fmt(y0)}) .. controls ({fmt(cx)},{fmt(cy)}) .. "
                f"({fmt(x1)},{fmt(y1)});")

    def handles(self):
        # rotation handle relative to center of endpoints
        cx, cy = ((self.p0[0]+self.p1[0]+self.c[0])/3, (self.p0[1]+self.p1[1]+self.c[1])/3)
        rx, ry = cx, cy - 36
        return [(*self.p0, "p0"), (*self.p1, "p1"), (*self.c, "control"),
                (cx, cy, "move"), (rx, ry, "rotate")]

    def move_by(self, dx, dy):
        self.p0 = (self.p0[0] + dx, self.p0[1] + dy)
        self.p1 = (self.p1[0] + dx, self.p1[1] + dy)
        self.c  = (self.c[0]  + dx, self.c[1]  + dy)

    def rotate_by(self, ddeg):
        cx = (self.p0[0] + self.p1[0] + self.c[0]) / 3
        cy = (self.p0[1] + self.p1[1] + self.c[1]) / 3
        self.p0 = rotate_point(*self.p0, cx, cy, ddeg)
        self.p1 = rotate_point(*self.p1, cx, cy, ddeg)
        self.c  = rotate_point(*self.c,  cx, cy, ddeg)

    def rotate_to(self, deg): pass

    def on_handle_drag(self, kind, x, y):
        if kind in ("p0", "p1", "control"):
            setattr(self, {"p0":"p0", "p1":"p1", "control":"c"}[kind], (x, y))


class RectShape(Shape):
    def __init__(self, p0, p1, color="black", width=2,
                 fill_enabled=False, fill_color="gray", fill_opacity=1.0, angle=0.0):
        self.p0 = p0
        self.p1 = p1
        self.color = color
        self.width = width
        self.fill_enabled = fill_enabled
        self.fill_color = fill_color
        self.fill_opacity = fill_opacity
        self.angle = angle
        self._ids = []

    def center(self):
        return ((self.p0[0] + self.p1[0]) / 2, (self.p0[1] + self.p1[1]) / 2)

    def draw(self, canvas):
        for iid in self._ids:
            canvas.delete(iid)
        corners = rect_corners_from_p0p1(self.p0, self.p1, self.angle)
        flat = [c for xy in corners for c in xy]
        poly = canvas.create_polygon(*flat, outline=self.color, width=self.width,
                                     fill=(self.fill_color if self.fill_enabled else ""))
        self._ids = [poly]
        return self._ids

    def to_tikz(self):
        (x0, y0), (x1, y1) = self.p0, self.p1
        cx, cy = self.center()
        opts = [f"draw={self.color}", f"line width={self.width}pt"]
        if self.fill_enabled:
            opts.append(f"fill={self.fill_color}")
            if self.fill_opacity < 1.0:
                opts.append(f"fill opacity={self.fill_opacity:.2f}")
        if abs(self.angle) > 1e-9:
            # y is flipped in tikz with y=-1pt, so invert angle for visual parity
            opts.append(f"rotate around={-self.angle:.2f}:({fmt(cx)},{fmt(cy)})")
        return (rf"\draw[{', '.join(opts)}] "
            f"({fmt(x0)},{fmt(y0)}) rectangle ({fmt(x1)},{fmt(y1)});")

    def handles(self):
        cx, cy = self.center()
        rx, ry = rotate_point(cx, cy - 40, cx, cy, self.angle)  # rotate handle follows rotation
        return [(cx, cy, "move"), (rx, ry, "rotate")]

    def move_by(self, dx, dy):
        self.p0 = (self.p0[0] + dx, self.p0[1] + dy)
        self.p1 = (self.p1[0] + dx, self.p1[1] + dy)

    def rotate_by(self, ddeg):
        self.angle = (self.angle + ddeg) % 360

    def rotate_to(self, deg):
        self.angle = deg % 360

    def on_handle_drag(self, kind, x, y):
        pass  # move/rotate handled at controller level


class EllipseShape(Shape):
    def __init__(self, p0, p1, color="black", width=2,
                 fill_enabled=False, fill_color="gray", fill_opacity=1.0, angle=0.0):
        # p0, p1 are bbox corners at creation; convert to cx,cy,rx,ry
        cx, cy = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        rx, ry = abs(p1[0] - p0[0]) / 2, abs(p1[1] - p0[1]) / 2
        self.cx, self.cy, self.rx, self.ry = cx, cy, rx, ry
        self.color = color
        self.width = width
        self.fill_enabled = fill_enabled
        self.fill_color = fill_color
        self.fill_opacity = fill_opacity
        self.angle = angle
        self._ids = []

    def draw(self, canvas):
        for iid in self._ids:
            canvas.delete(iid)
        pts = poly_from_ellipse(self.cx, self.cy, self.rx, self.ry, self.angle, segments=108)
        flat = [c for xy in pts for c in xy]
        poly = canvas.create_polygon(*flat, outline=self.color, width=self.width,
                                     fill=(self.fill_color if self.fill_enabled else ""))
        self._ids = [poly]
        return self._ids

    def to_tikz(self):
        cx, cy, rx, ry = self.cx, self.cy, self.rx, self.ry
        opts = [f"draw={self.color}", f"line width={self.width}pt"]
        if self.fill_enabled:
            opts.append(f"fill={self.fill_color}")
            if self.fill_opacity < 1.0:
                opts.append(f"fill opacity={self.fill_opacity:.2f}")
        if abs(self.angle) > 1e-9:
            opts.append(f"rotate around={-self.angle:.2f}:({fmt(cx)},{fmt(cy)})")
        return (rf"\draw[{', '.join(opts)}] "
                f"({fmt(cx)},{fmt(cy)}) ellipse [x radius={fmt(rx)}, y radius={fmt(ry)}];")

    def handles(self):
        cx, cy = self.cx, self.cy
        rx, ry = rotate_point(cx, cy - 40, cx, cy, self.angle)
        return [(cx, cy, "move"), (rx, ry, "rotate")]

    def move_by(self, dx, dy):
        self.cx += dx; self.cy += dy

    def rotate_by(self, ddeg):
        self.angle = (self.angle + ddeg) % 360

    def rotate_to(self, deg):
        self.angle = deg % 360

    def on_handle_drag(self, kind, x, y):
        pass


class CircleShape(Shape):
    def __init__(self, center, radius, color="black", width=2,
                 fill_enabled=False, fill_color="gray", fill_opacity=1.0):
        self.center = center
        self.radius = radius
        self.color = color
        self.width = width
        self.fill_enabled = fill_enabled
        self.fill_color = fill_color
        self.fill_opacity = fill_opacity
        self._ids = []

    def draw(self, canvas):
        for iid in self._ids:
            canvas.delete(iid)
        cx, cy = self.center
        r = self.radius
        circ = canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                  outline=self.color, width=self.width,
                                  fill=(self.fill_color if self.fill_enabled else ""))
        self._ids = [circ]
        return self._ids

    def to_tikz(self):
        cx, cy, r = self.center[0], self.center[1], self.radius
        opts = [f"draw={self.color}", f"line width={self.width}pt"]
        if self.fill_enabled:
            opts.append(f"fill={self.fill_color}")
            if self.fill_opacity < 1.0:
                opts.append(f"fill opacity={self.fill_opacity:.2f}")
        return rf"\draw[{', '.join(opts)}] ({fmt(cx)},{fmt(cy)}) circle [radius={fmt(r)}];"

    def handles(self):
        cx, cy = self.center
        edge = (cx + self.radius, cy)
        rot = (cx, cy - 40)  # rotation N/A but keep for consistency (does nothing)
        return [(cx, cy, "move"), (*edge, "radius"), (*rot, "rotate")]

    def move_by(self, dx, dy):
        self.center = (self.center[0] + dx, self.center[1] + dy)

    def rotate_by(self, ddeg): pass
    def rotate_to(self, deg): pass

    def on_handle_drag(self, kind, x, y):
        if kind == "radius":
            self.radius = max(0.0, distance(self.center, (x, y)))


class TextNode(Shape):
    """A simple text node placed at a point; exported as a TikZ \node."""
    def __init__(self, pos, text="Hello", size=12, color="black"):
        self.pos = pos
        self.text = text
        self.size = size
        self.color = color
        self._ids = []

    def draw(self, canvas):
        for iid in getattr(self, '_ids', []):
            canvas.delete(iid)
        x, y = self.pos
        # Use create_text for visual; anchor=center
        tid = canvas.create_text(x, y, text=self.text, fill=self.color, font=("TkDefaultFont", self.size))
        self._ids = [tid]
        return self._ids

    def to_tikz(self):
        x, y = self.pos
        # Escape percent and backslashes in text minimally
        t = self.text.replace('\\', '\\\\').replace('%', '\\%')
        return rf"\node[draw=none] at ({fmt(x)},{fmt(y)}) {{{t}}};"

    def handles(self):
        return [(self.pos[0], self.pos[1], "move")]

    def move_by(self, dx, dy):
        self.pos = (self.pos[0] + dx, self.pos[1] + dy)

    def rotate_by(self, ddeg):
        pass

    def on_handle_drag(self, kind, x, y):
        if kind == "move":
            self.pos = (x, y)
            
class Dot(CircleShape):
    """A small filled circle, typically used as a point marker."""
    def __init__(self, center, radius=3, color="black"):
        super().__init__(center, radius, color=color, width=1,
                         fill_enabled=True, fill_color=color, fill_opacity=1.0)
        
    def handles(self):
        cx, cy = self.center
        return [(cx, cy, "move")]
    
    
class ArcShape(Shape):
    """A circular arc defined by center, radius, start angle, end angle."""
    def __init__(self, center, radius, start_angle, end_angle,
                 color="black", width=2,
                 fill_enabled=False, fill_color="gray", fill_opacity=1.0):
        self.center = center
        self.radius = radius
        self.start_angle = start_angle
        self.end_angle = end_angle
        self.color = color
        self.width = width
        self.fill_enabled = fill_enabled
        self.fill_color = fill_color
        self.fill_opacity = fill_opacity
        self._ids = []
        
    def draw(self, canvas):
        for iid in self._ids:
            canvas.delete(iid)
        cx, cy = self.center
        r = self.radius
        # use TkInter canvas arc (bbox x0,y0,x1,y1, start=deg, extent=deg)
        start = -self.start_angle  # Tkinter y-axis is inverted
        extent = -(self.end_angle - self.start_angle)
        assert isinstance(cx, int)
        assert isinstance(cy, int)
        assert isinstance(r, float), f"{type(r)}, {r}"
        arc_id = canvas.create_arc(cx - r, cy - r, cx + r,
                                      cy + r, start=start, extent=extent,
                                      style='arc', outline=self.color, width=self.width)
        self._ids = [arc_id]
        return self._ids
    
    def to_tikz(self):
        cx, cy, r = self.center[0], self.center[1], self.radius
        sa, ea = self.start_angle, self.end_angle
        opts = [f"draw={self.color}", f"line width={self.width}pt"]
        return (rf"\draw[{', '.join(opts)}] "
                f"({fmt(cx)},{fmt(cy)}) ++({fmt(sa)}:{fmt(r)}) arc [start angle={fmt(sa)}, "
                f"end angle={fmt(ea)}, radius={fmt(r)}];")
        
    def handles(self):
        cx, cy = self.center
        start_rad = math.radians(self.start_angle)
        end_rad = math.radians(self.end_angle)
        sx = cx + self.radius * math.cos(start_rad)
        sy = cy + self.radius * math.sin(start_rad)
        ex = cx + self.radius * math.cos(end_rad)
        ey = cy + self.radius * math.sin(end_rad)
        return [(cx, cy, "move"), (sx, sy, "start"), (ex, ey, "end")]
    
    def move_by(self, dx, dy):
        self.center = (self.center[0] + dx, self.center[1] + dy)
    def rotate_by(self, ddeg):
        self.start_angle = (self.start_angle + ddeg) % 360
        self.end_angle = (self.end_angle + ddeg) % 360
        
    def rotate_to(self, deg):
        # rotate so that start_angle becomes deg
        delta = (deg - self.start_angle) % 360
        self.start_angle = deg % 360
        self.end_angle = (self.end_angle + delta) % 360
    
    def on_handle_drag(self, kind, x, y):
        cx, cy = self.center
        if kind == "move":
            self.center = (x, y)
        elif kind == "start":
            angle = math.degrees(math.atan2(y - cy, x - cx)) % 360
            self.start_angle = angle
        elif kind == "end":
            angle = math.degrees(math.atan2(y - cy, x - cx)) % 360
            self.end_angle = angle
    