"""
Steins;Gate Nixie Clock / Divergence Meter - desktop widget.

Run:  python steins_gate_nixie.py

  - Drag with left mouse to move it anywhere
  - Double-click: cathode spin (clock) / new random world line (meter)
  - Click the little lab pin on the right to flip between Clock and Meter
  - Right-click for the menu (mode, world lines, 12/24h, size, always-on-top)

The Future Gadget Lab pin is embedded in this file, so it works standalone.
(Drop a fgl_pin.png next to the script if you ever want to swap the image.)
Menu > Clear glass switches between see-through and dark tinted tubes.
"""
import base64
import io
import math
import os
import random
import tkinter as tk
from datetime import datetime

try:                                # Pillow is optional (smoother pin scaling)
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

TUBES = 8
ROLL_FRAMES = 30
ROLL_MS = 45

BG = "#010101"                  # see-through on Windows
GLASS_OUT = "#0a0403"
GLASS_BODY = "#170706"
GLASS_INNER = "#1f0a08"
BASE_DARK = "#080302"
MESH_BG = "#0f0504"
MESH_LINE = "#3a0f07"
GLOW_1, GLOW_2 = "#1f0905", "#2e0f08"
UNLIT = "#6e200d"
LIT_OUT, LIT_MID, LIT_CORE = "#c8561a", "#f2a22a", "#ffe07a"

SIZES = {"Small": 0.45, "Medium": 0.6, "Large": 0.85, "Huge": 1.0}

WORLD_LINES = {
    "Steins Gate  1.048596": 1.048596,
    "Alpha  0.571024": 0.571024,
    "Beta  1.130426": 1.130426,
    "Gamma  2.615074": 2.615074,
    "Start  0.337187": 0.337187,
}


def ell(cx, cy, rx, ry, n=10, a0=-90):
    """Closed ellipse as points (overlapped at the end so smoothing closes it)."""
    return [(cx + rx * math.cos(math.radians(a0 + 360 * k / n)),
             cy + ry * math.sin(math.radians(a0 + 360 * k / n)))
            for k in range(n + 3)]


# Wire digits on a 0..1 box: list of (points, smooth) strokes.
DIGITS = {
    0: [(ell(.5, .5, .5, .5, 12), True)],
    1: [([(.5, 0), (.5, 1)], False),
        ([(0, .24), (1, .24)], False),
        ([(.5, 0), (0, .24)], False)],
    2: [([(.04, .22), (.3, .02), (.7, .02), (.96, .22), (.85, .46)], True),
        ([(.85, .46), (.04, 1), (1, 1)], False)],
    3: [([(0, 0), (1, 0)], False),
        ([(1, 0), (.45, .48)], False),
        ([(0, .48), (.55, .48)], False),
        ([(.42, .48), (.85, .55), (1, .75), (.85, .95), (.5, 1), (.1, .93), (0, .8)], True)],
    4: [([(.75, 1), (.75, 0), (0, .68), (1, .68)], False)],
    5: [([(.95, 0), (.08, 0), (.04, .46)], False),
        ([(.04, .46), (.5, .42), (.92, .55), (1, .76), (.85, .95), (.5, 1),
          (.08, .92), (0, .8)], True)],
    6: [(ell(.5, .7, .5, .3, 10), True),
        ([(0, .7), (1, .7)], False),
        ([(.8, 0), (.45, .22), (.18, .48), (.05, .7)], True)],
    7: [([(0, 0), (1, 0), (.38, 1)], False)],
    8: [(ell(.5, .26, .4, .26, 10), True),
        (ell(.5, .74, .5, .26, 10), True)],
    9: [(ell(.5, .3, .5, .3, 10), True),
        ([(0, .3), (1, .3)], False),
        ([(1, .3), (.62, 1)], False)],
}


class NixieMeter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Nixie")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG)
        try:
            self.root.wm_attributes("-transparentcolor", BG)
        except tk.TclError:
            pass

        self.mode = tk.StringVar(value="clock")
        self.h24 = tk.BooleanVar(value=True)
        self.blink = tk.BooleanVar(value=True)
        self.topmost = tk.BooleanVar(value=True)
        self.clear = tk.BooleanVar(value=False)
        self.size_name = tk.StringVar(value="Medium")
        self.scale = SIZES["Medium"]
        self.meter_value = 1.048596

        self.canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.canvas.pack()
        self.root.geometry("+120+120")

        self.dots_on = True
        self.animating = False
        self.last_clean_hour = None
        self.pin_img = None
        self._press = (0, 0)
        self.display = list(self.target())

        self._build_menu()
        self._bind_events()
        self.build()
        self.tick()

    # ---- Menu / events ------------------------------------------------------
    def _build_menu(self):
        m = tk.Menu(self.root, tearoff=0)
        m.add_radiobutton(label="Clock", variable=self.mode, value="clock",
                          command=lambda: self.set_mode("clock"))
        m.add_radiobutton(label="Divergence meter", variable=self.mode, value="meter",
                          command=lambda: self.set_mode("meter"))
        wl = tk.Menu(m, tearoff=0)
        for label, val in WORLD_LINES.items():
            wl.add_command(label=label, command=lambda v=val: self.set_mode("meter", v))
        wl.add_separator()
        wl.add_command(label="Random world line",
                       command=lambda: self.set_mode("meter", self.random_value()))
        m.add_cascade(label="World lines", menu=wl)
        m.add_separator()
        m.add_checkbutton(label="24-hour time", variable=self.h24)
        m.add_checkbutton(label="Blinking colons", variable=self.blink)
        m.add_checkbutton(label="Clear glass", variable=self.clear,
                          command=self.build)
        sz = tk.Menu(m, tearoff=0)
        for name in SIZES:
            sz.add_radiobutton(label=name, variable=self.size_name, value=name,
                               command=lambda n=name: self.set_size(n))
        m.add_cascade(label="Size", menu=sz)
        m.add_checkbutton(label="Always on top", variable=self.topmost,
                          command=lambda: self.root.attributes(
                              "-topmost", self.topmost.get()))
        m.add_separator()
        m.add_command(label="Quit", command=self.root.destroy)
        self.menu = m

    def _bind_events(self):
        c = self.canvas
        c.bind("<ButtonPress-1>", self._start_drag)
        c.bind("<B1-Motion>", self._drag)
        c.bind("<Double-Button-1>", self._double_click)
        c.bind("<ButtonPress-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))
        c.bind("<ButtonPress-2>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))
        c.tag_bind("pin", "<ButtonRelease-1>", self._pin_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def _start_drag(self, e):
        self._dx, self._dy = e.x, e.y
        self._press = (e.x_root, e.y_root)

    def _drag(self, e):
        x = self.root.winfo_x() + e.x - self._dx
        y = self.root.winfo_y() + e.y - self._dy
        self.root.geometry(f"+{x}+{y}")

    def _double_click(self, e):
        if self.mode.get() == "clock":
            self.roll()
        else:
            self.set_mode("meter", self.random_value())

    def _pin_release(self, e):
        if abs(e.x_root - self._press[0]) < 5 and abs(e.y_root - self._press[1]) < 5:
            if self.mode.get() == "clock":
                self.set_mode("meter", self.random_value())
            else:
                self.set_mode("clock")

    def set_size(self, name):
        self.scale = SIZES[name]
        self.build()

    # ---- Content ------------------------------------------------------------
    @staticmethod
    def random_value():
        return random.choice([random.uniform(0.0, 0.999999),
                              random.uniform(1.0, 1.999999),
                              random.uniform(2.0, 3.999999)])

    def time_string(self):
        now = datetime.now()
        if self.h24.get():
            hs = f"{now.hour:02d}"
        else:
            hs = f"{(now.hour % 12) or 12:2d}"
        return f"{hs}:{now.minute:02d}:{now.second:02d}"

    def target(self):
        if self.mode.get() == "clock":
            return list(self.time_string())
        return list(f"{self.meter_value:.6f}")

    def set_mode(self, name, value=None):
        self.mode.set(name)
        if value is not None:
            self.meter_value = value
        self.roll()

    # ---- Animation / tick ---------------------------------------------------
    def roll(self):
        if self.animating:
            return
        self.animating = True
        self._roll_step(0)

    def _roll_step(self, frame):
        target = self.target()
        settled = frame * TUBES // ROLL_FRAMES
        new = []
        for i, t in enumerate(target):
            if t in ": .":
                new.append(t)
            elif i < settled:
                new.append(t)
            else:
                new.append(str(random.randint(0, 9)))
        self.set_display(new)
        if frame < ROLL_FRAMES:
            self.root.after(ROLL_MS, self._roll_step, frame + 1)
        else:
            self.set_display(target)
            self.animating = False

    def set_display(self, new):
        for i in range(TUBES):
            if new[i] != self.display[i]:
                self.display[i] = new[i]
                self.draw_tube(i)
        self.canvas.tag_raise("glass")

    def tick(self):
        now = datetime.now()
        if not self.animating and self.mode.get() == "clock":
            self.set_display(self.target())
            if now.minute == 0 and now.second == 0 and self.last_clean_hour != now.hour:
                self.last_clean_hour = now.hour
                self.roll()
        dots = (now.microsecond < 500000) if self.blink.get() else True
        if dots != self.dots_on:
            self.dots_on = dots
            for i, ch in enumerate(self.display):
                if ch == ":":
                    self.draw_tube(i)
            self.canvas.tag_raise("glass")
        self.root.after(100, self.tick)

    # ---- Drawing ------------------------------------------------------------
    def build(self):
        s = self.scale
        self.TW, self.TH = 104 * s, 267 * s
        self.gap, self.pad = 4 * s, 10 * s
        self.pin_zone = 54 * s
        self.top = self.pad
        self.tube_x = [self.pad + i * (self.TW + self.gap) for i in range(TUBES)]
        self.W = (self.pad * 2 + TUBES * self.TW + (TUBES - 1) * self.gap
                  + self.pin_zone)
        self.H = self.top + self.TH + self.pad

        DW, DH = 0.56 * self.TW, 0.48 * self.TH
        self.rel = {
            d: [([v for (px, py) in pts for v in ((px - .5) * DW, (py - .5) * DH)], sm)
                for pts, sm in strokes]
            for d, strokes in DIGITS.items()}

        c = self.canvas
        c.config(width=int(self.W), height=int(self.H))
        c.delete("all")
        for x in self.tube_x:
            self._draw_static_tube(x)
        self._draw_pin()
        self.display = list(self.target())
        for i in range(TUBES):
            self.draw_tube(i)
        c.tag_raise("glass")

    @staticmethod
    def _round_poly(x0, y0, x1, y1, rt, rb):
        return [x0 + rt, y0, x1 - rt, y0, x1, y0, x1, y0 + rt,
                x1, y1 - rb, x1, y1, x1 - rb, y1, x0 + rb, y1,
                x0, y1, x0, y1 - rb, x0, y0 + rt, x0, y0]

    def _draw_static_tube(self, x0):
        c, s, TW, TH = self.canvas, self.scale, self.TW, self.TH
        y0, x1, y1 = self.top, x0 + self.TW, self.top + self.TH
        cx = x0 + TW / 2
        # glass body
        clear = self.clear.get()
        c.create_polygon(self._round_poly(x0, y0, x1, y1, 0.34 * TW, 3 * s),
                         smooth=True, fill="" if clear else GLASS_BODY,
                         outline="#9a6a60" if clear else GLASS_OUT,
                         width=max(1, 2 * s))
        if not clear:
            c.create_polygon(self._round_poly(x0 + 5 * s, y0 + 5 * s, x1 - 5 * s,
                                              y0 + 0.86 * TH, 0.3 * TW, 2 * s),
                             smooth=True, fill=GLASS_INNER, outline="")
        # tube base
        c.create_rectangle(x0 + 1, y0 + 0.86 * TH, x1 - 1, y1 - 1, fill=BASE_DARK,
                           outline="")
        for k in range(7):
            px = x0 + 0.14 * TW + k * (0.72 * TW) / 6
            c.create_rectangle(px - 2 * s, y0 + 0.9 * TH, px + 2 * s, y1 - 2 * s,
                               fill="#1e1210", outline="")
        c.create_rectangle(x0 + 0.08 * TW, y0 + 0.865 * TH, x1 - 0.08 * TW,
                           y0 + 0.885 * TH, fill="#2a110d", outline="")
        # mesh anode with warm glow
        mx0, mx1 = x0 + 0.2 * TW, x0 + 0.8 * TW
        my0, my1 = y0 + 0.15 * TH, y0 + 0.80 * TH
        line_col = "#8a3216" if clear else MESH_LINE
        edge_col = "#8a3216" if clear else "#3a120a"
        if not clear:
            c.create_rectangle(mx0, my0, mx1, my1, fill=MESH_BG, outline=edge_col)
            mcx, mcy = (mx0 + mx1) / 2, (my0 + my1) / 2
            c.create_oval(mcx - 0.3 * TW, mcy - 0.3 * TH, mcx + 0.3 * TW,
                          mcy + 0.3 * TH, fill=GLOW_1, outline="")
            c.create_oval(mcx - 0.2 * TW, mcy - 0.22 * TH, mcx + 0.2 * TW,
                          mcy + 0.22 * TH, fill=GLOW_2, outline="")
        c.create_rectangle(mx0, my0, mx1, my1, fill="", outline=edge_col)
        sp = max(3.0, 5 * s)
        gx = mx0 + sp
        while gx < mx1:
            c.create_line(gx, my0, gx, my1, fill=line_col)
            gx += sp
        gy = my0 + sp
        while gy < my1:
            c.create_line(mx0, gy, mx1, gy, fill=line_col)
            gy += sp
        # little red indicator under the mesh
        c.create_line(cx - 0.07 * TW, y0 + 0.74 * TH, cx + 0.07 * TW, y0 + 0.74 * TH,
                      fill="#c8381c", width=max(1, 2 * s))
        # glass edge highlights (raised above the wires later)
        c.create_line(x0 + 7 * s, y0 + 0.2 * TH, x0 + 7 * s, y0 + 0.82 * TH,
                      fill="#6a3a32", width=max(1, 2 * s), tags="glass")
        c.create_line(x1 - 6 * s, y0 + 0.24 * TH, x1 - 6 * s, y0 + 0.8 * TH,
                      fill="#4a2620", width=max(1, 1.5 * s), tags="glass")
        c.create_arc(x0 + 9 * s, y0 + 6 * s, x1 - 9 * s, y0 + 0.62 * TW, start=25,
                     extent=130, style=tk.ARC, outline="#7a4a40",
                     width=max(1, 1.5 * s), tags="glass")

    def draw_tube(self, i):
        c, s = self.canvas, self.scale
        tag = f"d{i}"
        c.delete(tag)
        ch = self.display[i]
        cx = self.tube_x[i] + self.TW / 2
        cy = self.top + 0.46 * self.TH

        # unlit stacked cathode wires
        for d in range(10):
            for rel, smooth in self.rel[d]:
                pts = [v + (cx if k % 2 == 0 else cy) for k, v in enumerate(rel)]
                c.create_line(*pts, fill=UNLIT, width=max(1, 1.3 * s), smooth=smooth,
                              tags=tag)

        if ch.isdigit():
            for width, color in ((6 * s, LIT_OUT), (3.6 * s, LIT_MID), (2 * s, LIT_CORE)):
                for rel, smooth in self.rel[int(ch)]:
                    pts = [v + (cx if k % 2 == 0 else cy) for k, v in enumerate(rel)]
                    c.create_line(*pts, fill=color, width=max(1, width), smooth=smooth,
                                  capstyle=tk.ROUND, joinstyle=tk.ROUND, tags=tag)
        elif ch == ":" and self.dots_on:
            for dy in (-0.09 * self.TH, 0.09 * self.TH):
                self._lit_dot(cx, cy + dy, tag)
        elif ch == ".":
            self._lit_dot(cx, self.top + 0.46 * self.TH + 0.24 * self.TH, tag)

    def _lit_dot(self, x, y, tag):
        c, s = self.canvas, self.scale
        for r, color in ((9 * s, LIT_OUT), (6 * s, LIT_MID), (3.6 * s, LIT_CORE)):
            c.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="", tags=tag)

    # ---- Lab pin ------------------------------------------------------------
    def _draw_pin(self):
        c, s = self.canvas, self.scale
        r = 24 * s
        cx = self.W - self.pad - r - 2 * s
        cy = self.top + 0.1 * self.TH + r
        img = self._load_pin_image(int(2 * r))
        if img is not None:
            self.pin_img = img                      # keep a reference
            c.create_image(cx, cy, image=img, tags="pin")
            return
        # built-in placeholder badge
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#1a1f2b", outline="#b8bcc4",
                      width=max(1, 2 * s), tags="pin")
        c.create_oval(cx - r * 0.78, cy - r * 0.78, cx + r * 0.78, cy + r * 0.78,
                      fill="", outline="#e8731a", width=max(1, 1.5 * s), tags="pin")
        c.create_text(cx, cy, text="FGL", fill="#ffb04a",
                      font=("Arial", max(6, int(9 * s * 1.1)), "bold"), tags="pin")

    def _load_pin_image(self, size):
        # The logo is embedded below; a fgl_pin.png next to the script overrides it.
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fgl_pin.png")
        try:
            if os.path.exists(path):
                with open(path, "rb") as f:
                    raw = f.read()
            else:
                raw = base64.b64decode(FGL_PIN_B64)
            if Image is not None:
                img = Image.open(io.BytesIO(raw)).convert("RGBA")
                img.thumbnail((size, size), getattr(Image, "Resampling", Image).LANCZOS)
                return ImageTk.PhotoImage(img)
            img = tk.PhotoImage(data=base64.b64encode(raw).decode())
            factor = max(1, round(img.width() / max(1, size)))
            return img.subsample(factor) if factor > 1 else img
        except (tk.TclError, OSError, ValueError):
            return None

    def run(self):
        self.root.mainloop()


FGL_PIN_B64 = (
    "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"
    "0lSQNnl5fu5/bj4fjF6xVStLt1b4LctmyNGdeOuJI/C41V+FYihpHMsBPVuyW8c8YnFDejx+ogn/2KLWvTfMmXOhNnjwYHunKYCT"
    "UTfalVL6ffr6861ko1dVVEvRXOKxl3+gZ4/uHHvsIZxx1u2cfOZtSOC7L5/l3TfuYb8eu2EYJrZtb2qpZ7+wA3M4f0hXjju0nMra"
    "MC2KA3w7qZqHX5qLEILuXYo46Yh21G+op20rN4/d2ovPXjySy8/ck4JcD6ZlIxFpRXBi/usv7MHDt+xLPBbDMKRT75f/b+U/m2vF"
    "4knOG9KREff0I8enZ2d5f7fJJCHg03nqzj7s2jGHpnCSFiVBRn25nodG/OAIrdzxuD/Dc9qzWwmP3rY/Aw8q4qi+7bNGbsvwzMbt"
    "0jjpiPYoio2UtmrhDyf1Tu8BhMOnyt8qf2Zlb1tubljLSl2c9aZ55ZCy/V3mmttj0UYRzPGrE6fXiIdfnM/It+/j+8lzeeTJd1i9"
    "toKR749m6fJ1/POUI7jgksG0blHEosWraGxyBtAVxQlFLFvStVMhz951MNJ2rHRDM5x17Vg2pun+7riyF332LSKasDAMm0gsSXmp"
    "hyP7tuHQA9ugKhqLl9eTNBzOmWvO34f7rutBcziClM5I4/9j2d8ybkYQDifYf+8S2rTK56vxazDSgLefC3BmzagtJY/cciBnHN+e"
    "qtowRYU+flgY4oxrxhCKprbwEjsi/KYp6dQ2l/efPpziPAXbssnN8fHpd6udOYe05cyQa+3euYDh/+pJ0khaAb9bMSj5vrDzJffv"
    "vvsiZdCgG/6wPbptIdCFIywppVLkDZ3pd0XcliVtVWhixLs/0alLZ3Jz/Ay/76Us01g0nuSNd75i797/5KH7X+XkfxzKnClvcvMN"
    "55CfG8C2LRAKqqJw62U9aFmqE08Y+P0+7nlmLgtX1COEM7xx4uFtCceSWY+hayrhqEFTc4xunfw8cce+jH/nBI4f2IHLztiDe67d"
    "h3A4irT5W/i3CDYzhFgqVbUhTjumLU8N65Oded7cEQgBuuZgf647fx8uOX1XKqtD5AR1KmsMzr9pPHWNcVRV7DDLm6qAaUqK8r28"
    "eH9/OrXzEI4aJFMmffcr4aCerbDlpnAt82knH7ULBfkaiURSaHoAPGVvCyHswcVdt6q2vdUF8KFDhyrDhw+3K5aN7BqUs6cbkbV+"
    "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"
)


if __name__ == "__main__":
    NixieMeter().run()
