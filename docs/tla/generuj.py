"""Tła slajdów w stylu identyfikacji COI i aplikacji mObywatel.

Wzory z tablicy COI na Behance (materialy/inspo_prezentacja). Podstawą jest znak
ze strony „Pracuj z nami”: koło z gradientem stożkowym (szew pionowo w dół od
środka), pod nim jasny prostokąt od lewej krawędzi koła do jego środka, mały
kwadrat magenta → lawenda przy lewej krawędzi prostokąta i mała szara kulka
z wcięciem. Do tego: ogromne koło magenty na granacie (stopka strony), duże
bladoszare koła na jasnym tle, raster kropek (ekran „Tworzymy nowoczesne
rozwiązania”), nadruk z koszulki i giloszowanie jak w mObywatelu.
Bez logo COI i godła.

Uruchom: uv run --with numpy --with pillow python docs/tla/generuj.py
Wynik: JPG 2560x1440 (slajd 1280x720 w 2x) obok skryptu + podglad.png.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

W, H = 1280, 720  # slajd Marp 16:9
S = 2  # skala renderu
OUT = Path(__file__).resolve().parent
rng = np.random.default_rng(7)

# Paleta (jak w docs/prezentacja.md i decisions.md)
NAVY_DEEP = "#04122f"
NAVY = "#0b1a4f"
NAVY_2 = "#13286e"
ROYAL = "#1f3ea6"
ROYAL_2 = "#2a4cc0"
BLUE_PALE = "#b4cdf5"
LAV = "#eef1fb"
LAV_2 = "#a9b7e8"
SOFT = "#eceff8"
PLUM = "#871c6c"
MAGENTA = "#e10a58"
VIOLET = "#5b2a86"


def rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255.0


# --- siatka współrzędnych w pikselach slajdu (1280x720) ---
ys, xs = np.mgrid[0 : H * S, 0 : W * S].astype(np.float32)
X = (xs + 0.5) / S
Y = (ys + 0.5) / S


def canvas(color: str) -> np.ndarray:
    c = np.empty((H * S, W * S, 3), np.float32)
    c[:] = rgb(color)
    return c


def ramp(t: np.ndarray, stops: list[tuple[float, str]]) -> np.ndarray:
    """Kolor z listy (pozycja 0..1, kolor) dla każdej wartości t."""
    t = np.clip(t, 0.0, 1.0)
    pos = np.array([p for p, _ in stops], np.float32)
    cols = np.stack([rgb(c) for _, c in stops])
    out = np.empty(t.shape + (3,), np.float32)
    for ch in range(3):
        out[..., ch] = np.interp(t, pos, cols[:, ch])
    return out


def linear(angle_deg: float, x0: float, y0: float, length: float) -> np.ndarray:
    """t wzdłuż kierunku (0° = w prawo, 90° = w dół) od punktu (x0, y0)."""
    a = math.radians(angle_deg)
    return ((X - x0) * math.cos(a) + (Y - y0) * math.sin(a)) / length


def conic(cx: float, cy: float, start_deg: float, sweep_deg: float = 360.0) -> np.ndarray:
    """t kątowo wokół (cx, cy), od start_deg zgodnie ze wskazówkami zegara."""
    ang = (np.degrees(np.arctan2(Y - cy, X - cx)) - start_deg) % 360.0
    return ang / sweep_deg


def circle(cx: float, cy: float, r: float) -> np.ndarray:
    d = np.hypot(X - cx, Y - cy)
    return np.clip((r - d) * S + 0.5, 0.0, 1.0)


def rect(x: float, y: float, w: float, h: float) -> np.ndarray:
    m = np.clip(np.minimum(X - x, x + w - X) * S + 0.5, 0, 1)
    n = np.clip(np.minimum(Y - y, y + h - Y) * S + 0.5, 0, 1)
    return m * n


def paint(img: np.ndarray, mask: np.ndarray, color: np.ndarray | str, alpha: float = 1.0) -> None:
    col = rgb(color) if isinstance(color, str) else color
    a = (mask * alpha)[..., None]
    img[:] = img * (1 - a) + col * a


def glow(img: np.ndarray, cx: float, cy: float, r: float, color: str, alpha: float) -> None:
    d = np.hypot(X - cx, Y - cy) / r
    paint(img, np.clip(1 - d, 0, 1) ** 2, color, alpha)


def grain(img: np.ndarray, amount: float) -> None:
    n = rng.normal(0.0, amount, img.shape[:2]).astype(np.float32)[..., None]
    img += n


def save(img: np.ndarray, name: str) -> Path:
    p = OUT / name.replace(".png", ".jpg")
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(p, quality=90, optimize=True)
    print(p.name)
    return p


# --- motywy ---

# Palety znaku: koło (stożek od dołu zgodnie ze wskazówkami), prostokąt, wycięcie w kole, kulka
JASNY = {
    "disc": [(0, "#2f56b8"), (0.25, "#5d7fcb"), (0.5, "#8fa7da"), (0.75, "#c5d2ec"), (1, "#ffffff")],
    "rect": ["#dde6f5", "#c8d6ef"],
    "cut": [(0, "#ffffff"), (0.75, "#a9bde6"), (1, "#ffffff")],
    "sphere": [(0, "#ffffff"), (0.5, "#e6e6e9"), (1, "#a9a9b0")],
}
CIEMNY = {
    "disc": [(0, "#1c3a9c"), (0.25, "#2b4db5"), (0.5, "#4b6bc8"), (0.75, "#8ea4df"), (1, "#dfe6f8")],
    "rect": ["#2c4fb8", "#1a3590"],
    "cut": [(0, "#dfe6f8"), (0.75, "#4f6fcb"), (1, "#dfe6f8")],
    "sphere": [(0, "#c3cbe6"), (0.5, "#6f7fb5"), (1, "#24357a")],
}


def emblem(img, cx, cy, r, pal, rect_end=H, fade_to=None, pixel=True, sphere=True):
    """Znak COI ze strony „Pracuj z nami”, w proporcjach oryginału."""
    top = cy + 0.12 * r
    # prostokąt za kołem: od lewej krawędzi koła do jego środka, w dół
    body = rect(cx - r, top, r, rect_end - top)
    col = ramp(linear(90, 0, top, rect_end - top), [(0, pal["rect"][0]), (1, pal["rect"][1])])
    if fade_to is not None:  # ogon prostokąta rozpływa się w tle
        col = col * (1 - np.clip((Y - top) / (rect_end - top), 0, 1)[..., None] ** 1.2) + rgb(fade_to) * (
            np.clip((Y - top) / (rect_end - top), 0, 1)[..., None] ** 1.2
        )
    paint(img, body, col)
    # koło: stożek z szwem pionowo w dół od środka
    disc = circle(cx, cy, r)
    paint(img, disc, ramp(conic(cx, cy, 90), pal["disc"]))
    # wycięcie: lewa dolna część koła pokazuje prostokąt z własnym „ściśnięciem”
    px, py = cx - 0.5 * r, cy + 0.62 * r
    cut = disc * rect(px, py, cx - px, r)
    paint(img, cut, ramp(conic(px, py, 90), pal["cut"]))
    if pixel:
        size = 0.25 * r
        x, y = cx - r - size, top
        paint(
            img,
            rect(x, y, size, size),
            ramp(linear(135, x + size, y, size * 1.41), [(0, "#d01860"), (0.5, "#c45a91"), (1, "#ece6f2")]),
        )
    if sphere:
        sx, sy, sr = cx - 1.26 * r, cy - r, 0.19 * r
        paint(img, circle(sx, sy, sr), ramp(conic(sx, sy, 0), pal["sphere"]))


def dot_grid(img, x0, x1, step, color, alpha, fade_from_right=True, radius=1.4, top=-40.0, both_ends=False):
    gx = (X - x0) % step - step / 2
    gy = Y % step - step / 2
    d = np.hypot(gx, gy)
    cell_x = X - gx  # środek kropki: kropka cała albo wcale
    dots = np.clip((radius - d) * S + 0.5, 0, 1) * ((cell_x >= x0) & (cell_x <= x1)).astype(np.float32)
    dots *= np.clip((Y - top) / 40.0, 0, 1)
    t = (X - x0) / (x1 - x0)
    fade = np.sin(np.pi * np.clip(t, 0, 1)) if both_ends else (t if fade_from_right else 1 - t)
    paint(img, dots * np.clip(fade, 0, 1) ** 1.5, color, alpha)


def guilloche(img, color, alpha, cx, cy, n=46, gap=11.0, amp=6.0, waves=18):
    """Koncentryczne faliste linie jak zabezpieczenia na mDowodzie."""
    d = np.hypot(X - cx, Y - cy)
    th = np.arctan2(Y - cy, X - cx)
    calm = np.clip(d / 420.0, 0.15, 1.0)  # blisko środka fale łagodniejsze, linie się nie zlewają
    wob = calm * (amp * np.sin(waves * th + d / 40.0) + amp * 0.5 * np.sin((waves + 7) * th))
    v = (d + wob) / gap
    line = np.clip(1 - np.abs(v - np.round(v)) * gap * S / 1.3, 0, 1)
    line *= (v < n).astype(np.float32)
    paint(img, line, color, alpha)


def header_line(img, end):
    """Kreska jak w motywie (szara, magentowy koniec 88 px), kończy się przed formami w rogu."""
    paint(img, rect(80, 44, end - 80, 2), "#d1d4dd")
    paint(img, rect(end - 88, 44, 88, 2), "#e3125a")


# --- tła ---


# --- tła ---


def tytul():
    """Tytuł: granat, znak COI po prawej, w tle ogromne ciemniejsze koło."""
    img = canvas(NAVY)
    paint(img, np.ones_like(X), ramp(linear(0, 0, 0, W), [(0, NAVY_DEEP), (0.6, NAVY), (1, NAVY)]))
    paint(img, circle(1180, 980, 760), ramp(linear(270, 0, 980, 760), [(0, "#102366"), (1, "#0d1d58")]), 0.8)
    emblem(img, 1100, 540, 180, CIEMNY, fade_to=NAVY, sphere=False)
    grain(img, 0.012)
    return save(img, "01-tytul.png")


def sekcja():
    """Przerywnik: stopka strony COI — ogromne koło magenta → fiolet na granacie."""
    img = canvas(NAVY_DEEP)
    paint(img, np.ones_like(X), ramp(linear(0, 0, 0, W), [(0, "#08143a"), (1, "#0b1a4f")]))
    cx, cy, r = 300, 900, 760
    paint(
        img,
        circle(cx, cy, r),
        ramp(
            conic(cx, cy, 90), [(0, "#ff1a55"), (0.25, "#c8105a"), (0.5, "#5e1d72"), (0.75, "#24205f"), (1, "#ff1a55")]
        ),
    )
    glow(img, 0, 720, 520, "#e3125a", 0.35)
    paint(img, rect(80, 44, 1120, 2), "#ffffff", 0.18)
    grain(img, 0.014)
    return save(img, "02-sekcja.png")


def tresc_jasna():
    """Treść, jasna: jak sekcje strony COI — biel, kreska, blada duża kula w rogu."""
    img = canvas("#ffffff")
    paint(img, circle(1240, -40, 300), ramp(linear(135, 1540, -340, 850), [(0, "#f7f8fb"), (1, "#eef0f5")]))
    header_line(img, 900)
    grain(img, 0.006)
    return save(img, "03-tresc-jasna.png")


def tresc_jasna_bok():
    """Liczby/wnioski: ekran „Tworzymy nowoczesne rozwiązania” — raster kropek, znak COI po prawej."""
    img = canvas(SOFT)
    paint(img, np.ones_like(X), ramp(linear(0, 0, 0, W), [(0, "#f6f7fc"), (1, "#e7ecf8")]))
    dot_grid(img, 300, 880, 9, "#9aa8d8", 0.75, radius=1.5, both_ends=True)
    emblem(img, 1120, 300, 170, JASNY)
    grain(img, 0.006)
    return save(img, "04-tresc-jasna-bok.png")


def tresc_ciemna():
    """Treść, ciemna: jak sekcja „Kim jesteśmy” — granat i dwa duże, ledwo jaśniejsze koła."""
    img = canvas(NAVY)
    paint(img, np.ones_like(X), ramp(linear(0, 0, 0, W), [(0, NAVY_DEEP), (0.6, NAVY), (1, NAVY)]))
    paint(img, circle(-100, 900, 620), "#102366", 0.6)
    paint(img, circle(1260, -60, 330), ramp(linear(135, 1590, -390, 900), [(0, "#1a3590"), (1, "#112770")]), 0.9)
    paint(img, rect(80, 44, 820, 2), "#2c3d7a")
    grain(img, 0.012)
    return save(img, "05-tresc-ciemna.png")


def mobywatel():
    """Demo/zrzuty: jasny gradient jak strony mObywatel, z giloszowaniem."""
    img = canvas(LAV)
    paint(img, np.ones_like(X), ramp(linear(25, 0, 0, 1460), [(0, "#f3f5fc"), (0.5, "#dfe6f8"), (1, "#e9def0")]))
    glow(img, 1180, 640, 620, "#c8b4e6", 0.5)
    glow(img, 120, 80, 620, "#d3e0f8", 0.4)
    guilloche(img, "#7f93d6", 0.38, 1240, 760, n=70, gap=10)
    guilloche(img, "#b08ad0", 0.22, -60, -80, n=50, gap=13, waves=11)
    grain(img, 0.006)
    return save(img, "06-mobywatel.png")


def kola():
    """Treść, jasna: duże bladoszare koła i niebieskie koło jak na stronie oferty pracy COI."""
    img = canvas("#ffffff")
    paint(img, circle(1010, 120, 640), ramp(linear(0, 370, 0, 1280), [(0, "#f1f2f6"), (1, "#f8f9fb")]))
    paint(img, circle(1280, 780, 380), ramp(linear(90, 0, 400, 760), [(0, "#eceef4"), (1, "#f4f5f8")]))
    paint(img, circle(1060, 420, 130), ramp(linear(0, 930, 0, 260), [(0, "#4f70c4"), (0.6, "#a8b9e4"), (1, "#dfe6f6")]))
    header_line(img, 1010)
    grain(img, 0.006)
    return save(img, "07-kola.png")


def koniec():
    """Zamknięcie: nadruk z koszulki COI — koło magenta → fiolet, dolna prawa ćwiartka ucięta, stoi na krawędzi."""
    img = canvas(NAVY)
    paint(img, np.ones_like(X), ramp(linear(20, 0, 0, W), [(0, NAVY_DEEP), (0.6, NAVY), (1, "#14307f")]))
    glow(img, 80, 760, 620, "#4b2a8a", 0.5)
    cx, cy, r = 950, 530, 250
    m = circle(cx, cy, r)
    paint(img, m, ramp(conic(cx, cy, 90, 270), [(0, "#ff1f4b"), (0.3, "#c41a6a"), (0.62, "#6d2a93"), (1, "#26307f")]))
    paint(img, m * rect(cx, cy, r, r), ramp(linear(0, cx, 0, r), [(0, "#28308a"), (1, "#141c58")]))
    grain(img, 0.016)
    return save(img, "08-koniec.png")


def podglad(paths: list[Path]) -> None:
    tw, th = 640, 360
    sheet = Image.new("RGB", (tw * 2 + 30, (th + 15) * math.ceil(len(paths) / 2) + 15), "#888888")
    for i, p in enumerate(paths):
        im = Image.open(p).resize((tw, th), Image.LANCZOS)
        sheet.paste(im, (10 + (i % 2) * (tw + 10), 15 + (i // 2) * (th + 15)))
    sheet.save(OUT / "podglad.png", optimize=True)


if __name__ == "__main__":
    podglad([tytul(), sekcja(), tresc_jasna(), tresc_jasna_bok(), tresc_ciemna(), mobywatel(), kola(), koniec()])
