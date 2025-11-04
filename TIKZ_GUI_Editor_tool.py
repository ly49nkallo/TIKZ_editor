#!/usr/bin/env python3
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from geometry_helpers import *
from shapes import *
# =========================== Geometry helpers ===========================


# ============================== Shape base ==============================


# ============================== Main App ===============================

class TikzDesigner(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TikZ Designer (Edit/Rotate + Fills)")
        self.geometry("1180x740")
        self.minsize(980, 560)

        # State
        # tools: cursor, line, quad, rect, ellipse, circle
        self.tool = tk.StringVar(value="cursor")
        self.snap_enabled = tk.BooleanVar(value=True)
        self.grid_enabled = tk.BooleanVar(value=True)
        self.grid_step = tk.IntVar(value=20)
        self.color = tk.StringVar(value="black")
        self.width = tk.IntVar(value=2)
        self.fill_enabled = tk.BooleanVar(value=False)
        self.fill_color = tk.StringVar(value="gray")
        self.fill_opacity = tk.DoubleVar(value=1.0)

        self.shapes = []
        # action history: list of actions to support undo. Each action is a dict
        # with a 'type' key and other keys depending on type. Supported types:
        #  - 'add': {type:'add', 'shape': shape, 'index': index}
        #  - 'remove': {type:'remove', 'shape': shape, 'index': index}
        #  - 'clear': {type:'clear', 'shapes': [shapes...]}
        self.actions = []
        self._clicks = []         # staging for drawing tools
        self._temp_item = None
        self._helper_items = []
        # transient UI item id for drag feedback
        self._transient_item = None
        # pending modify snapshot while dragging
        self._modify_pending = None

        # Cursor/selection
        self.selected = None      # (shape, handles_cache)
        self._cursor_mode = None  # 'move'|'rotate'|'handle'
        self._active_handle = None
        self._drag_start = None   # (x,y)
        self._rotate_base_angle = None  # deg at drag start
        self._rotate_center = None
        # transient overlay timer id for tool hint
        self._tool_overlay_after = None

        self._build_ui()
        self._bind_events()
        self._draw_grid()
        # Ensure the side-panel reflects the initial tool selection
        try:
            self._update_tool_ui(self.tool.get())
        except Exception:
            pass
        try:
            self._apply_cursor_for_tool(self.tool.get())
        except Exception:
            pass
        # Update status with helpful context based on current tool/grid/snap
        self.status.set("Cursor: click a shape to select, drag to move. Use the round handle to rotate.")
        # Trace variable changes to show helpful status messages
        try:
            # tkinter 8.6+: trace_add
            self.tool.trace_add('write', lambda *a: self._on_tool_change())
            self.snap_enabled.trace_add('write', lambda *a: self._on_snap_change())
            self.grid_enabled.trace_add('write', lambda *a: self._on_grid_change())
        except Exception:
            # older tkinter fallback
            try:
                self.tool.trace('w', lambda *a: self._on_tool_change())
            except Exception:
                pass

    # -------------------- UI --------------------
    def _build_ui(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        side = ttk.Frame(self, padding=8)
        side.grid(row=0, column=0, sticky="nsw")
        side.columnconfigure(0, weight=1)

        ttk.Label(side, text="Tools", font=("TkDefaultFont", 10, "bold")).grid(sticky="w")
        tool_frame = ttk.Frame(side)
        tool_frame.grid(sticky="ew")
        mk = lambda text, val: ttk.Radiobutton(tool_frame, text=text, value=val, variable=self.tool)
        mk("Cursor (Edit)", "cursor").grid(sticky="w")
        mk("Line", "line").grid(sticky="w")
        mk("Arrow", "arrow").grid(sticky="w")
        mk("Quad Bézier", "quad").grid(sticky="w")
        mk("Rectangle", "rect").grid(sticky="w")
        mk("Ellipse", "ellipse").grid(sticky="w")
        mk("Circle", "circle").grid(sticky="w")
        mk("Text (node)", "text").grid(sticky="w")
        mk("Dot", "dot").grid(sticky="w")

        ttk.Separator(side).grid(sticky="ew", pady=6)

        # Text tool options (grouped so we can hide/show them)
        self._text_group = ttk.Frame(side)
        self._text_group.columnconfigure(0, weight=1)
        ttk.Label(self._text_group, text="Text", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.text_value = tk.StringVar(value="Hello")
        self.text_size = tk.IntVar(value=12)
        self._text_entry = ttk.Entry(self._text_group, textvariable=self.text_value)
        self._text_entry.grid(row=1, column=0, sticky="ew", pady=(2,4))
        ttk.Label(self._text_group, text="Font size (pt)").grid(row=2, column=0, sticky="w")
        self._text_size_spin = ttk.Spinbox(self._text_group, from_=6, to=72, textvariable=self.text_size, width=6)
        self._text_size_spin.grid(row=2, column=1, sticky="w")
        self._text_group.grid(sticky="ew")

        ttk.Label(side, text="Stroke", font=("TkDefaultFont", 10, "bold")).grid(sticky="w")
        ttk.Label(side, text="Color").grid(sticky="w", pady=(2,0))
        # color swatch + dropdown for stroke (store on self so visibility toggling is safe)
        self._stroke_frame = ttk.Frame(side)
        self._stroke_frame.grid(sticky="ew", pady=(0,4))
        self._stroke_swatch = tk.Label(self._stroke_frame, background=self.color.get(), width=2)
        self._stroke_swatch.pack(side="left", padx=(0,6))
        self._stroke_mb = tk.Menubutton(self._stroke_frame, text=self.color.get(), relief="raised")
        menu = tk.Menu(self._stroke_mb, tearoff=0)
        for c in ("black", "gray", "red", "blue", "green", "orange", "purple"):
            menu.add_command(label=c, command=(lambda col=c: (self.color.set(col), self._stroke_mb.config(text=col), self._stroke_swatch.config(background=col))))
        self._stroke_mb.config(menu=menu)
        self._stroke_mb.pack(side="left", fill="x", expand=True)
        ttk.Label(side, text="Width (pt)").grid(sticky="w")
        self._width_spin = ttk.Spinbox(side, from_=1, to=10, textvariable=self.width, width=6)
        self._width_spin.grid(sticky="w")

        ttk.Separator(side).grid(sticky="ew", pady=6)

        ttk.Label(side, text="Fill", font=("TkDefaultFont", 10, "bold")).grid(sticky="w")
        self._fill_check = ttk.Checkbutton(side, text="Enable fill (for rect/ellipse/circle)",
                                           variable=self.fill_enabled)
        self._fill_check.grid(sticky="w")
        ttk.Label(side, text="Fill color").grid(sticky="w", pady=(2,0))
        self._fill_frame = ttk.Frame(side)
        self._fill_frame.grid(sticky="ew", pady=(0,4))
        self._fill_swatch = tk.Label(self._fill_frame, background=self.fill_color.get(), width=2)
        self._fill_swatch.pack(side="left", padx=(0,6))
        self._fill_mb = tk.Menubutton(self._fill_frame, text=self.fill_color.get(), relief="raised")
        f_menu = tk.Menu(self._fill_mb, tearoff=0)
        for c in ("gray", "black", "red", "blue", "green", "orange", "purple"):
            f_menu.add_command(label=c, command=(lambda col=c: (self.fill_color.set(col), self._fill_mb.config(text=col), self._fill_swatch.config(background=col))))
        self._fill_mb.config(menu=f_menu)
        self._fill_mb.pack(side="left", fill="x", expand=True)
        ttk.Label(side, text="Fill opacity (TikZ)").grid(sticky="w")
        self._fill_opacity_spin = ttk.Spinbox(side, from_=0.0, to=1.0, increment=0.05,
                    textvariable=self.fill_opacity, width=6)
        self._fill_opacity_spin.grid(sticky="w")

        ttk.Separator(side).grid(sticky="ew", pady=6)

        ttk.Label(side, text="Grid & Snap", font=("TkDefaultFont", 10, "bold")).grid(sticky="w")
        ttk.Checkbutton(side, text="Show grid", variable=self.grid_enabled,
                        command=self._toggle_grid).grid(sticky="w")
        ttk.Checkbutton(side, text="Snap to grid", variable=self.snap_enabled).grid(sticky="w")
        ttk.Label(side, text="Grid step (px)").grid(sticky="w")
        ttk.Spinbox(side, from_=5, to=100, textvariable=self.grid_step, width=6,
                    command=self._redraw_all).grid(sticky="w")

        ttk.Separator(side).grid(sticky="ew", pady=6)

        ttk.Button(side, text="Undo (Ctrl+Z)", command=self.undo).grid(sticky="ew", pady=2)
        ttk.Button(side, text="Clear", command=self.clear).grid(sticky="ew", pady=2)
        ttk.Button(side, text="Export TikZ", command=self.export_tikz).grid(sticky="ew", pady=(2,0))
        ttk.Button(side, text="History...", command=self._show_history).grid(sticky="ew", pady=(6,0))

        # Canvas
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0, cursor="crosshair")
        self.canvas.grid(row=0, column=1, sticky="nsew", padx=(0,6), pady=6)

        # Status bar
        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status, anchor="w").grid(row=1, column=0, columnspan=2, sticky="ew")

    def _bind_events(self):
        # Drawing / selection
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_motion)
        self.bind("<Escape>", lambda e: self._cancel_temp())
        self.bind("<Control-z>", lambda e: self.undo())
        # Delete selected shape when cursor tool is active
        self.bind("<Delete>", self._on_delete_key)
        self.bind("<BackSpace>", self._on_delete_key)
        self.bind("<Configure>", lambda e: self._maybe_redraw_grid())

    # -------------------- Grid --------------------
    def _toggle_grid(self):
        self._draw_grid()
        self._redraw_all()

    def _maybe_redraw_grid(self):
        if self.grid_enabled.get():
            self._draw_grid()

    # -------------------- Status helpers --------------------
    def _on_tool_change(self):
        t = self.tool.get()
        msgs = {
            'cursor': 'Cursor: click a shape to select; drag to move; use round handle to rotate; Del to delete.',
            'line': 'Line tool: click start, click end to finish.',
            'arrow': 'Arrow tool: click start, click end to finish.',
            'rect': 'Rectangle tool: click first corner, then click opposite corner.',
            'ellipse': 'Ellipse tool: click first corner, then click opposite corner.',
            'circle': 'Circle tool: click center, then click edge to set radius.',
            'quad': 'Quad Bézier: click start, click end, then click/drag to place control.',
            'dot': 'Dot tool: click to place a dot (small filled circle).',
        }
        self.status.set(msgs.get(t, f"Tool: {t} selected."))
        # Update visible UI controls for the selected tool
        try:
            self._update_tool_ui(t)
        except Exception:
            pass
        try:
            self._apply_cursor_for_tool(t)
            self._show_tool_overlay(t)
        except Exception:
            pass

    def _update_tool_ui(self, tool_name):
        """Show/hide side-panel widgets depending on the active tool.

        Previous logic toggled overlapping groups sequentially, which could
        hide widgets enabled by an earlier group. This version computes the
        full desired visible set first, then applies it deterministically.
        """
        # Universe of managed widgets
        all_widgets = [
            self._text_group,
            self._stroke_frame, self._width_spin,
            self._fill_check, self._fill_frame, self._fill_opacity_spin,
        ]

        # Compute which widgets should be visible for the current tool
        show = set()
        if tool_name == 'text':
            show.add(self._text_group)
            # Text nodes don't use stroke/fill controls here
        elif tool_name in ('line', 'arrow', 'quad', 'dot'):
            show.update({self._stroke_frame, self._width_spin})
        elif tool_name in ('rect', 'ellipse', 'circle'):
            show.update({
                self._stroke_frame, self._width_spin,
                self._fill_check, self._fill_frame, self._fill_opacity_spin,
            })
        else:
            # Default (cursor/unknown): hide all optional groups
            pass

        # Apply visibility
        for w in all_widgets:
            try:
                if w in show:
                    w.grid()
                else:
                    w.grid_remove()
            except Exception:
                # Widget may not be gridded yet in some edge cases
                pass

    def _apply_cursor_for_tool(self, tool_name):
        """Set the canvas cursor based on the selected tool."""
        cursor = 'crosshair'
        if tool_name == 'cursor':
            cursor = 'arrow'
        elif tool_name == 'text':
            cursor = 'xterm'
        # else: drawing tools keep crosshair
        try:
            self.canvas.config(cursor=cursor)
        except Exception:
            pass

    def _show_tool_overlay(self, tool_name):
        """Show a short-lived overlay label on the canvas with the active tool."""
        # Cancel any existing hide timer
        if getattr(self, '_tool_overlay_after', None):
            try:
                self.after_cancel(self._tool_overlay_after)
            except Exception:
                pass
            self._tool_overlay_after = None

        # Remove previous overlay items
        try:
            self.canvas.delete('tool-overlay')
        except Exception:
            pass

        # Friendly tool names
        names = {
            'cursor': 'Cursor', 'line': 'Line', 'arrow': 'Arrow', 'rect': 'Rectangle',
            'ellipse': 'Ellipse', 'circle': 'Circle', 'quad': 'Quad', 'dot': 'Dot', 'text': 'Text'
        }
        label = f"Tool: {names.get(tool_name, tool_name.title())}"

        # Create text and a background rectangle behind it
        try:
            text_id = self.canvas.create_text(10, 10, anchor='nw', text=label,
                                              font=("TkDefaultFont", 10),
                                              fill='#222', tags=('tool-overlay',))
            bbox = self.canvas.bbox(text_id)
            if bbox:
                x0, y0, x1, y1 = bbox
                pad = 4
                rect_id = self.canvas.create_rectangle(x0 - pad, y0 - pad, x1 + pad, y1 + pad,
                                                        fill='#ffffe0', outline='#e0dca8', width=1,
                                                        tags=('tool-overlay',))
                self.canvas.tag_raise(text_id, rect_id)
        except Exception:
            pass

        # Schedule auto-hide
        try:
            self._tool_overlay_after = self.after(1200, lambda: self.canvas.delete('tool-overlay'))
        except Exception:
            pass

    def _on_snap_change(self):
        if self.snap_enabled.get():
            self.status.set(f"Snap enabled (step={self.grid_step.get()} px).")
        else:
            self.status.set("Snap disabled.")

    def _on_grid_change(self):
        if self.grid_enabled.get():
            self.status.set(f"Grid shown (step={self.grid_step.get()} px).")
        else:
            self.status.set("Grid hidden.")

    def _draw_grid(self):
        self.canvas.delete("grid")
        if not self.grid_enabled.get():
            return
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 1 or h <= 1:
            self.after(50, self._draw_grid)
            return
        step = self.grid_step.get()
        for x in range(0, w, step):
            self.canvas.create_line(x, 0, x, h, fill="#f0f0f0", tags="grid")
        for y in range(0, h, step):
            self.canvas.create_line(0, y, w, y, fill="#f0f0f0", tags="grid")
        self.canvas.create_line(0, h-1, w, h-1, fill="#e0e0e0", tags="grid")
        self.canvas.create_line(1, 0, 1, h, fill="#e0e0e0", tags="grid")
        # Ensure grid is behind all other canvas items (so shapes stay visible)
        try:
            self.canvas.tag_lower("grid")
        except Exception:
            # older tkinter or unexpected state: noop
            pass

    # ===================== Selection/handles =====================

    def _shape_at(self, x, y):
        """Topmost shape under (x,y) by canvas overlap."""
        ids = set(self.canvas.find_overlapping(x-3, y-3, x+3, y+3))
        for shape in reversed(self.shapes):
            if any(i in ids for i in getattr(shape, "_ids", [])):
                return shape
        return None

    def _draw_handles(self, shape):
        self._clear_helpers()
        if not shape:
            return
        # Draw handles: squares for move/control points, circle for rotate
        for (hx, hy, kind) in shape.handles():
            if kind == "rotate":
                r = 6
                self._helper_items.append(
                    self.canvas.create_oval(hx-r, hy-r, hx+r, hy+r, outline="#339",
                                            width=2, fill="")
                )
            else:
                s = HANDLE_SIZE
                self._helper_items.append(
                    self.canvas.create_rectangle(hx-s, hy-s, hx+s, hy+s,
                                                 outline="#933", fill="#FCC", width=1)
                )

    def _clear_helpers(self):
        for iid in self._helper_items:
            self.canvas.delete(iid)
        self._helper_items.clear()

    # ===================== Drawing tools =====================

    def on_click(self, event):
        x, y = snap(event.x, event.y, self.snap_enabled.get(), self.grid_step.get())
        tool = self.tool.get()

        if tool == "cursor":
            self._cursor_down(x, y)
            return

        # Drawing tools
        if tool == "line":
            self._clicks.append((x, y))
            if len(self._clicks) == 2:
                p0, p1 = self._clicks
                self._add_shape(LineSeg(
                    p0, p1, color=self.color.get(), width=self.width.get(),
                    fill_enabled=False, fill_color=self.fill_color.get(),
                    fill_opacity=self.fill_opacity.get()))
                self._reset_temp("Line added.")
        elif tool == "arrow":
            self._clicks.append((x, y))
            if len(self._clicks) == 2:
                p0, p1 = self._clicks
                self._add_shape(Arrow(
                    p0, p1, color=self.color.get(), width=self.width.get(),
                ))
                self._reset_temp("Arrow added.")
        elif tool == "rect":
            self._clicks.append((x, y))
            if len(self._clicks) == 2:
                p0, p1 = self._clicks
                self._add_shape(RectShape(
                    p0, p1, color=self.color.get(), width=self.width.get(),
                    fill_enabled=self.fill_enabled.get(), fill_color=self.fill_color.get(),
                    fill_opacity=self.fill_opacity.get(), angle=0.0))
                self._reset_temp("Rectangle added.")
        elif tool == "ellipse":
            self._clicks.append((x, y))
            if len(self._clicks) == 2:
                p0, p1 = self._clicks
                self._add_shape(EllipseShape(
                    p0, p1, color=self.color.get(), width=self.width.get(),
                    fill_enabled=self.fill_enabled.get(), fill_color=self.fill_color.get(),
                    fill_opacity=self.fill_opacity.get(), angle=0.0))
                self._reset_temp("Ellipse added.")
        elif tool == "circle":
            self._clicks.append((x, y))
            if len(self._clicks) == 2:
                center, edge = self._clicks
                r = max(0.0, distance(center, edge))
                self._add_shape(CircleShape(
                    center, r, color=self.color.get(), width=self.width.get(),
                    fill_enabled=self.fill_enabled.get(), fill_color=self.fill_color.get(),
                    fill_opacity=self.fill_opacity.get()))
                self._reset_temp(f"Circle added (r={r:.2f}).")
        elif tool == "quad":
            # New flow: click start -> click end -> click/drag to place control
            self._clicks.append((x, y))
            if len(self._clicks) == 1:
                self.status.set(f"Quad: start set at {self._clicks[0]}. Now click end.")
            elif len(self._clicks) == 2:
                self.status.set("Quad: end set. Move mouse to position control, then click to finish.")
            elif len(self._clicks) == 3:
                p0, p1, c = self._clicks[0], self._clicks[1], self._clicks[2]
                self._add_shape(QuadBezier(
                    p0, p1, c, color=self.color.get(), width=self.width.get(),
                    fill_enabled=False, fill_color=self.fill_color.get(),
                    fill_opacity=self.fill_opacity.get()))
                self._reset_temp("Quadratic Bézier added.")
        elif tool == "text":
            # Place a single text node at clicked location
            txt = self.text_value.get()
            size = self.text_size.get()
            node = TextNode((x, y), text=txt, size=size, color=self.color.get())
            self._add_shape(node)
            self._reset_temp(f"Text node added: '{txt}'")
        elif tool == "dot":
            r = self.width.get() # the radius of the dot is determined by the size
            dot_node = CircleShape(
                (x, y), r, color=self.color.get(), width=1,
                fill_enabled=True, fill_color=self.color.get(),
                fill_opacity=1.0)
            self._add_shape(dot_node)
            self._reset_temp("Dot added.")

    def on_motion(self, event):
        x, y = snap(event.x, event.y, self.snap_enabled.get(), self.grid_step.get())
        tool = self.tool.get()

        if tool == "cursor":
            # update cursor hover? (optional)
            return

        self._clear_temp(keep_helper=False)
        if (tool == "line" or tool == "arrow") and len(self._clicks) == 1:
            x0, y0 = self._clicks[0]
            self._temp_item = self.canvas.create_line(x0, y0, x, y, fill="#888", dash=(4,2), width=1)
            self.status.set(f"Line preview: start={self._clicks[0]} → end≈({x},{y})")
        elif tool == "rect" and len(self._clicks) == 1:
            x0, y0 = self._clicks[0]
            self._temp_item = self.canvas.create_polygon(
                *[c for xy in rect_corners_from_p0p1((x0,y0),(x,y),0) for c in xy],
                outline="#888", dash=(4,2), width=1, fill="")
            self.status.set(f"Rectangle preview: corner={self._clicks[0]} → ({x},{y})")
        elif tool == "ellipse" and len(self._clicks) == 1:
            x0, y0 = self._clicks[0]
            cx, cy = (x0+x)/2, (y0+y)/2
            rx, ry = abs(x-x0)/2, abs(y-y0)/2
            pts = poly_from_ellipse(cx, cy, rx, ry, 0, 60)
            self._temp_item = self.canvas.create_polygon(*[c for xy in pts for c in xy],
                                                         outline="#888", dash=(4,2), width=1, fill="")
            self.status.set(f"Ellipse preview: bbox {self._clicks[0]} → ({x},{y})")
        elif tool == "circle" and len(self._clicks) == 1:
            cx, cy = self._clicks[0]
            r = distance((cx, cy), (x, y))
            self._temp_item = self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                                      outline="#888", dash=(4,2), width=1)
            self._helper_items.append(self.canvas.create_line(cx, cy, x, y, fill="#bbb", dash=(2,2)))
            self.status.set(f"Circle preview: center={self._clicks[0]} → r≈{r:.2f}")
        elif tool == "quad":
            if len(self._clicks) == 2:
                p0, p1 = self._clicks
                c = (x, y)
                # preview curve with current control
                pts = []
                for i in range(48):
                    t = i / 47
                    mt = 1 - t
                    px = mt*mt*p0[0] + 2*mt*t*c[0] + t*t*p1[0]
                    py = mt*mt*p0[1] + 2*mt*t*c[1] + t*t*p1[1]
                    pts.extend((px, py))
                self._temp_item = self.canvas.create_line(*pts, fill="#888", dash=(4,2), width=1)
                # control point marker
                self._helper_items.append(self.canvas.create_oval(x-3, y-3, x+3, y+3, outline="#888"))
                self.status.set(f"Quadratic Bézier preview: control=({x},{y}). Click to place.")
            elif len(self._clicks) == 1:
                self.status.set(f"Quad: start={self._clicks[0]}. Move to choose end, click to set.")
            # no preview once 3rd click added (shape is finalized in on_click)
        elif tool == "text":
            # preview text at cursor
            txt = self.text_value.get()
            size = self.text_size.get()
            self._temp_item = self.canvas.create_text(x, y, text=txt, fill=self.color.get(), font=("TkDefaultFont", size))
            self.status.set(f"Text preview: '{txt}' at ({x},{y})")

    def on_drag(self, event):
        if self.tool.get() != "cursor" or not self.selected:
            return
        x, y = snap(event.x, event.y, self.snap_enabled.get(), self.grid_step.get())
        shape, handles = self.selected

        if self._cursor_mode == "move":
            dx = x - self._drag_start[0]
            dy = y - self._drag_start[1]
            self._drag_start = (x, y)
            shape.move_by(dx, dy)
            shape.draw(self.canvas)
            self._draw_handles(shape)
        elif self._cursor_mode == "handle" and self._active_handle:
            kind = self._active_handle
            shape.on_handle_drag(kind, x, y)
            shape.draw(self.canvas)
            self._draw_handles(shape)
        elif self._cursor_mode == "rotate":
            cx, cy = self._rotate_center
            ang = math.degrees(math.atan2(y - cy, x - cx))
            d = ang - self._rotate_base_angle
            # For shapes storing absolute angle: set angle to base + delta;
            # For others: apply incremental rotation.
            if hasattr(shape, "angle"):
                shape.rotate_to((shape.angle + d) % 360 if isinstance(shape, (RectShape, EllipseShape)) else 0)
            # Apply incremental rotation to geometry:
            shape.rotate_by(d)
            self._rotate_base_angle = ang
            shape.draw(self.canvas)
            self._draw_handles(shape)






    def on_release(self, event):
        if self.tool.get() == "cursor":
            self._cursor_mode = None
            self._active_handle = None
            self._drag_start = None
            self._rotate_base_angle = None
            self._rotate_center = None

    # ===================== Cursor helpers =====================

    def _cursor_down(self, x, y):
        # If clicking an existing handle, start handle drag
        if self.selected:
            shape, handles = self.selected
            closest = None
            min_d = 9999
            for (hx, hy, kind) in shape.handles():
                d = distance((x, y), (hx, hy))
                if d < min_d:
                    min_d, closest = d, (hx, hy, kind)
            if closest and min_d <= 10:
                if closest[2] == "rotate":
                    self._cursor_mode = "rotate"
                    self._rotate_center = self._shape_center(shape)
                    self._rotate_base_angle = math.degrees(math.atan2(y - self._rotate_center[1],
                                                                      x - self._rotate_center[0]))
                elif closest[2] == "move":
                    self._cursor_mode = "move"
                    self._drag_start = (x, y)
                else:
                    self._cursor_mode = "handle"
                    self._active_handle = closest[2]
                return

        # Otherwise select a shape or start move
        shp = self._shape_at(x, y)
        if shp:
            self.selected = (shp, shp.handles())
            self._draw_handles(shp)
            self._cursor_mode = "move"
            self._drag_start = (x, y)
            self.status.set("Selected. Drag to move; drag round handle to rotate; press Del to delete selection.")
        else:
            # clicked empty space: clear selection
            self.selected = None
            self._clear_helpers()
            self.status.set("No shape under cursor. Select a tool to draw or click a shape to edit.")

    def _shape_center(self, shape):
        if isinstance(shape, RectShape):
            return shape.center()
        if isinstance(shape, EllipseShape):
            return (shape.cx, shape.cy)
        if isinstance(shape, CircleShape):
            return shape.center
        if isinstance(shape, LineSeg):
            return ((shape.p0[0]+shape.p1[0])/2, (shape.p0[1]+shape.p1[1])/2)
        if isinstance(shape, QuadBezier):
            return ((shape.p0[0]+shape.p1[0]+shape.c[0])/3,
                    (shape.p0[1]+shape.p1[1]+shape.c[1])/3)
        return (0, 0)

    def _on_delete_key(self, event=None):
        """Delete the currently selected shape when cursor tool is active."""
        if self.tool.get() != "cursor":
            # only allow deletion while in cursor/edit mode
            return
        if not self.selected:
            self.status.set("No shape currently selected to delete.")
            return
        shape, _ = self.selected
        # record remove action (store index so undo can re-insert at same place)
        try:
            idx = self.shapes.index(shape)
        except ValueError:
            idx = None
        if idx is None:
            # fallback: try identity-based find
            for i, s in enumerate(self.shapes):
                if s is shape:
                    idx = i
                    break
        self.actions.append({'type': 'remove', 'shape': shape, 'index': idx})
        # remove the shape
        try:
            # remove from shapes list (by identity)
            self.shapes = [s for s in self.shapes if s is not shape]
        except Exception:
            # fallback: attempt remove (if present)
            if shape in self.shapes:
                self.shapes.remove(shape)
        self.selected = None
        self._clear_helpers()
        self._redraw_all()
        self.status.set("Deleted selected shape. Use Undo (Ctrl+Z) to restore.")

    # ===================== Utilities =====================

    def _add_shape(self, shape):
        # append shape and record an 'add' action for undo
        idx = len(self.shapes)
        self.shapes.append(shape)
        self.actions.append({'type': 'add', 'shape': shape, 'index': idx})
        shape.draw(self.canvas)
        self.selected = (shape, shape.handles())
        self._draw_handles(shape)

    def _reset_temp(self, msg):
        self._cancel_temp()
        self.status.set(msg)

    def _cancel_temp(self):
        self._clicks.clear()
        self._clear_temp()
        self._clear_helpers()

    def _clear_temp(self, keep_helper=False):
        if self._temp_item is not None:
            self.canvas.delete(self._temp_item)
            self._temp_item = None
        if not keep_helper:
            self._clear_helpers()

    def _redraw_all(self):
        self.canvas.delete("all")
        self._draw_grid()
        for s in self.shapes:
            s.draw(self.canvas)
        if self.selected:
            self._draw_handles(self.selected[0])

    # ===================== Editing =====================

    def undo(self):
        if not self.actions:
            self.status.set("Nothing to undo.")
            return
        act = self.actions.pop()
        t = act.get('type')
        if t == 'add':
            # undo add => remove the shape if present
            shp = act.get('shape')
            try:
                self.shapes = [s for s in self.shapes if s is not shp]
            except Exception:
                if shp in self.shapes:
                    self.shapes.remove(shp)
            self.status.set("Undo: removed the previously added shape.")
        elif t == 'remove':
            # undo remove => re-insert shape at stored index (or append)
            shp = act.get('shape')
            idx = act.get('index')
            if idx is None or idx < 0 or idx > len(self.shapes):
                self.shapes.append(shp)
            else:
                self.shapes.insert(idx, shp)
            self.status.set("Undo: restored the previously removed shape.")
        elif t == 'clear':
            prev = act.get('shapes', [])
            self.shapes = list(prev)
            self.status.set("Undo: restored shapes that were cleared.")
        else:
            self.status.set("Undo: unknown action type (no change).")
        self.selected = None
        self._redraw_all()

    def clear(self):
        if not self.shapes:
            self.status.set("Canvas already clear.")
            return
        if messagebox.askyesno("Clear drawing", "Remove all shapes?"):
            # record clear action so it can be undone
            self.actions.append({'type': 'clear', 'shapes': list(self.shapes)})
            self.shapes.clear()
            self.selected = None
            self._redraw_all()
            self.status.set("Cleared all shapes. Use Undo (Ctrl+Z) to restore.")

    def _action_desc(self, act, idx=None):
        """Return a short human-readable description for an action record."""
        t = act.get('type')
        if t == 'add':
            shp = act.get('shape')
            name = type(shp).__name__ if shp is not None else 'shape'
            i = act.get('index')
            return f"Add {name} (index={i})"
        if t == 'remove':
            shp = act.get('shape')
            name = type(shp).__name__ if shp is not None else 'shape'
            i = act.get('index')
            return f"Remove {name} (from index={i})"
        if t == 'clear':
            cnt = len(act.get('shapes', []))
            return f"Clear all ({cnt} shapes)"
        if t == 'modify':
            shp = act.get('shape')
            name = type(shp).__name__ if shp is not None else 'shape'
            return f"Modify {name}"
        return f"Action: {t}"

    def _show_history(self):
        """Open a simple history dialog listing recent actions and allow "
        undo-to-selected".
        """
        win = tk.Toplevel(self)
        win.title("History")
        win.transient(self)
        win.geometry("420x360")

        ttk.Label(win, text="Action history (oldest → newest):", anchor="w").pack(fill="x", padx=8, pady=(8,2))

        frm = ttk.Frame(win)
        frm.pack(fill="both", expand=True, padx=8, pady=4)

        lb = tk.Listbox(frm, activestyle="none")
        lb.pack(side="left", fill="both", expand=True)
        scr = ttk.Scrollbar(frm, orient="vertical", command=lb.yview)
        scr.pack(side="right", fill="y")
        lb.config(yscrollcommand=scr.set)

        # Populate listbox with action descriptions (oldest first)
        for i, act in enumerate(self.actions):
            lb.insert("end", f"{i}: {self._action_desc(act, i)}")

        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=8, pady=(4,8))

        def undo_to_selected():
            sel = lb.curselection()
            if not sel:
                messagebox.showinfo("History", "Please select an action to undo to.")
                return
            target_index = sel[0]  # 0 = oldest
            # Keep actions up through target_index (inclusive), undo newer ones
            target_len = target_index + 1
            # If user selected the newest action, nothing to do
            if len(self.actions) <= target_len:
                messagebox.showinfo("History", "Already at or before selected action.")
                return
            # Repeatedly undo until history length equals target_len
            while len(self.actions) > target_len:
                self.undo()
            win.destroy()

        ttk.Button(btns, text="Undo to selected", command=undo_to_selected).pack(side="left")
        ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

    # ===================== Export =====================

    def tikz_code(self):
        lines = []
        lines.append(r"\begin{tikzpicture}[x=1pt,y=-1pt]")
        for s in self.shapes:
            lines.append("  " + s.to_tikz())
        lines.append(r"\end{tikzpicture}")
        return "\n".join(lines)

    def export_tikz(self):
        if not self.shapes:
            messagebox.showinfo("Export TikZ", "No shapes to export yet.")
            return

        code = self.tikz_code()

        win = tk.Toplevel(self)
        win.title("Export TikZ")
        win.geometry("840x520")
        win.transient(self)

        ttk.Label(win, text="Paste into LaTeX (requires \\usepackage{tikz}).",
                  foreground="#444").pack(anchor="w", padx=8, pady=(8,0))

        txt = tk.Text(win, wrap="none", font=("Courier New", 11))
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", code)

        btns = ttk.Frame(win); btns.pack(fill="x", padx=8, pady=(0,8))
        def copy_clip():
            self.clipboard_clear(); self.clipboard_append(code); self.update()
            messagebox.showinfo("Copied", "TikZ code copied to clipboard.")
        def save_file():
            path = filedialog.asksaveasfilename(
                defaultextension=".tex",
                filetypes=[("TeX files", "*.tex"), ("All files", "*.*")]
            )
            if not path: return
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("% Requires: \\usepackage{tikz}\n")
                    f.write(code)
                messagebox.showinfo("Saved", f"Saved TikZ to:\n{path}")
            except Exception as e:
                messagebox.showerror("Save failed", str(e))
        ttk.Button(btns, text="Copy to Clipboard", command=copy_clip).pack(side="left")
        ttk.Button(btns, text="Save .tex…", command=save_file).pack(side="left", padx=6)
        ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

# ------------------------------ Run ------------------------------------

if __name__ == "__main__":
    app = TikzDesigner()
    app.mainloop()
