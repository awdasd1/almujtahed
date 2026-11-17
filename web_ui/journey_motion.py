"""تحريك لوحة رحلة البخاري حركةً مرسومة: سير على الخط، إضاءة المدينة، بطاقة المعلم، وصوت ريح."""
from __future__ import annotations

import heapq
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path(__file__).resolve().parent / "static" / "motion" / "bukhari"
# مواضع المحطات على اللوحة الأصلية ١٥٣٦×١٠٢٤، مرتّبة من كرمينية غربًا مع نزول إلى الحجاز.
_STOPS = (
    ("kalyan", 1392, 388, "left"),
    ("basra", 1188, 444, "above"),
    ("malwiya", 998, 358, "below"),
    ("hadba", 887, 212, "right"),
    ("umayyad", 706, 333, "left"),
    ("kaaba", 800, 619, "right"),
    ("pyramids", 533, 429, "right"),
)
# إزاحة الرجل عن اسم المدينة حتى تبقى الإضاءة ظاهرة.
_FIGURE = {
    "kalyan": (42, -28),
    "basra": (0, -34),
    "malwiya": (-26, -22),
    "hadba": (-30, 28),
    "umayyad": (40, 36),
    "kaaba": (-46, -8),
    "pyramids": (8, -68),
}
_FPS = 12
_TRAVEL = 2.4
_DWELL = 2.6


def is_bukhari_poster(path: Path) -> bool:
    return "بخاري" in path.name


def _ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).is_file():
            return exe
    except Exception:
        pass
    found = shutil.which("ffmpeg")
    if found:
        return found
    for cand in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"):
        if Path(cand).is_file():
            return cand
    return ""


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _glow_sprite(size: int, color: tuple, power: float = 2.0) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    center = (size - 1) / 2
    for y in range(size):
        for x in range(size):
            dist = math.hypot(x - center, y - center) / center
            if dist >= 1:
                continue
            alpha = int(255 * (1 - dist) ** power)
            px[x, y] = (color[0], color[1], color[2], alpha)
    return img


def _stops(width: int, height: int):
    sx = width / 1536
    sy = height / 1024
    return [(name, int(x * sx), int(y * sy), place) for name, x, y, place in _STOPS]


def _snap(orange, x: int, y: int, radius: int = 8):
    h, w = orange.shape
    best = None
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            cx, cy = x + dx, y + dy
            if 0 <= cx < w and 0 <= cy < h and orange[cy, cx]:
                dist = dx * dx + dy * dy
                if best is None or dist < best[0]:
                    best = (dist, cx, cy)
    return (best[1], best[2]) if best else (x, y)


def _astar(orange, start, goal):
    height, width = orange.shape
    start = _snap(orange, *start)
    goal = _snap(orange, *goal)
    if start == goal:
        return [start]
    pending = [(0, start)]
    came = {}
    cost = {start: 0.0}
    seen = 0
    found = None
    while pending and seen < 80000:
        _, cur = heapq.heappop(pending)
        seen += 1
        if abs(cur[0] - goal[0]) + abs(cur[1] - goal[1]) <= 1:
            found = cur
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nxt = (cur[0] + dx, cur[1] + dy)
            if not (0 <= nxt[0] < width and 0 <= nxt[1] < height):
                continue
            step = 1.4 if dx and dy else 1.0
            extra = 0.0 if orange[nxt[1], nxt[0]] else 11.0
            new_cost = cost[cur] + step + extra
            if new_cost >= cost.get(nxt, 1e18):
                continue
            cost[nxt] = new_cost
            came[nxt] = cur
            guess = abs(nxt[0] - goal[0]) + abs(nxt[1] - goal[1])
            heapq.heappush(pending, (new_cost + guess, nxt))
    if found is None:
        return [start, goal]
    path = [found]
    while path[-1] != start:
        path.append(came[path[-1]])
    path.reverse()
    return path


def _route(image: Image.Image, stops) -> list:
    try:
        import numpy as np
    except Exception:
        return _straight(stops)
    arr = np.asarray(image)
    red = arr[:, :, 0].astype(np.int16)
    green = arr[:, :, 1].astype(np.int16)
    blue = arr[:, :, 2].astype(np.int16)
    orange = (red > 185) & (green > 55) & (green < 185) & (blue < 110) & (red > green + 30)
    height, width = orange.shape
    orange[: int(height * 0.08), :] = False
    orange[int(height * 0.9):, :] = False
    orange[:, : int(width * 0.24)] = False
    step = 4
    small = orange[::step, ::step]
    points = []
    for index in range(len(stops) - 1):
        a = (stops[index][1] // step, stops[index][2] // step)
        b = (stops[index + 1][1] // step, stops[index + 1][2] // step)
        leg = _astar(small, a, b)
        if index:
            leg = leg[1:]
        for cx, cy in leg:
            points.append((cx * step + step // 2, cy * step + step // 2))
    if len(points) < 8:
        return _straight(stops)
    return _smooth(points)


def _straight(stops) -> list:
    points = []
    for index in range(len(stops) - 1):
        x0, y0 = stops[index][1], stops[index][2]
        x1, y1 = stops[index + 1][1], stops[index + 1][2]
        for step in range(24):
            t = step / 24
            points.append((int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t)))
    points.append((stops[-1][1], stops[-1][2]))
    return points


def _smooth(points: list) -> list:
    if len(points) < 5:
        return points
    smoothed = []
    for index in range(len(points)):
        window = points[max(0, index - 2): index + 3]
        smoothed.append((
            sum(p[0] for p in window) // len(window),
            sum(p[1] for p in window) // len(window),
        ))
    return smoothed


def _lengths(points: list):
    total = 0.0
    marks = [0.0]
    for index in range(1, len(points)):
        total += math.hypot(points[index][0] - points[index - 1][0], points[index][1] - points[index - 1][1])
        marks.append(total)
    return total, marks


def _point_at(points, marks, dist: float):
    if dist <= 0:
        return points[0]
    if dist >= marks[-1]:
        return points[-1]
    for index in range(1, len(marks)):
        if marks[index] >= dist:
            span = marks[index] - marks[index - 1]
            t = 0 if span <= 0 else (dist - marks[index - 1]) / span
            x0, y0 = points[index - 1]
            x1, y1 = points[index]
            return (int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t))
    return points[-1]


def _cut_points(points, marks, dist: float):
    kept = [points[0]]
    for index in range(1, len(marks)):
        if marks[index] < dist:
            kept.append(points[index])
        else:
            kept.append(_point_at(points, marks, dist))
            break
    return kept


def _card_origin(x, y, place, card_w, card_h, width, height):
    if place == "left":
        px, py = x - card_w - 18, y - card_h // 2
    elif place == "right":
        px, py = x + 26, y - card_h // 2
    elif place == "above":
        px, py = x - card_w // 2, y - card_h - 22
    elif place == "above-right":
        px, py = x + 12, y - card_h - 6
    else:
        px, py = x - card_w // 2, y + 26
    return max(6, min(width - card_w - 6, px)), max(6, min(height - card_h - 6, py))


def _with_alpha(image: Image.Image, alpha: float) -> Image.Image:
    if alpha >= 0.99:
        return image
    faded = image.copy()
    band = faded.getchannel("A").point(lambda p: int(p * alpha))
    faded.putalpha(band)
    return faded


def _timeline(stops, route, marks):
    """يعيد لقطات الحركة: موضع السائر، المحطة المضاءة، وشفافية بطاقتها."""
    nearest = []
    for _name, x, y, _place in stops:
        best_i, best_d = 0, 1e18
        for index, (px, py) in enumerate(route):
            dist = (px - x) ** 2 + (py - y) ** 2
            if dist < best_d:
                best_i, best_d = index, dist
        nearest.append(marks[best_i])
    frames = []
    travel_n = int(_TRAVEL * _FPS)
    dwell_n = int(_DWELL * _FPS)
    for index in range(len(stops)):
        if index == 0:
            for _ in range(dwell_n):
                frames.append((nearest[0], 0, 1.0))
            continue
        start, end = nearest[index - 1], nearest[index]
        for step in range(travel_n):
            dist = start + (end - start) * _ease((step + 1) / travel_n)
            frames.append((dist, index, 0.0))
        for step in range(dwell_n):
            t = (step + 1) / dwell_n
            if t < 0.28:
                alpha = t / 0.28
            elif t > 0.78:
                alpha = (1 - t) / 0.22
            else:
                alpha = 1.0
            frames.append((end, index, alpha))
    return frames


def render_bukhari_video(image_path: Path) -> bytes:
    ffmpeg = _ffmpeg()
    if not ffmpeg:
        raise RuntimeError("محرك الفيديو غير متوفر")
    if not (ASSETS / "traveler.png").is_file():
        raise RuntimeError("أصول حركة الرحلة غير موجودة")
    base = Image.open(image_path).convert("RGB")
    if base.width > 1280:
        height = int(base.height * 1280 / base.width)
        height -= height % 2
        base = base.resize((1280, max(2, height)), Image.Resampling.LANCZOS)
    if base.width % 2 or base.height % 2:
        base = base.crop((0, 0, base.width - base.width % 2, base.height - base.height % 2))
    stops = _stops(*base.size)
    route = _route(base, stops)
    _total, marks = _lengths(route)
    frames = _timeline(stops, route, marks)
    traveler = Image.open(ASSETS / "traveler.png").convert("RGBA")
    sprite_h = max(84, int(base.height * 0.115))
    sprite_w = max(1, int(traveler.width * sprite_h / traveler.height))
    traveler = traveler.resize((sprite_w, sprite_h), Image.Resampling.LANCZOS)
    cards = {}
    card_w = max(168, int(base.width * 0.16))
    for name, _x, _y, _place in stops:
        card = Image.open(ASSETS / f"{name}.png").convert("RGBA")
        card_h = max(1, int(card.height * card_w / card.width))
        cards[name] = card.resize((card_w, card_h), Image.Resampling.LANCZOS)
    glow = _glow_sprite(150, (255, 176, 64), 2.2)
    core = _glow_sprite(46, (255, 236, 190), 1.4)
    shadow = Image.new("RGBA", (sprite_w, 22), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((8, 2, sprite_w - 8, 18), fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(2))
    folder = Path(tempfile.mkdtemp(prefix="bukhari-motion-"))
    try:
        for index, (dist, stop_index, card_alpha) in enumerate(frames):
            frame = base.copy()
            overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            walked = _cut_points(route, marks, dist)
            if len(walked) >= 2:
                draw.line(walked, fill=(255, 150, 40, 150), width=14)
                draw.line(walked, fill=(255, 214, 120, 230), width=4)
            name, sx, sy, place = stops[stop_index]
            here = _point_at(route, marks, dist)
            overlay.paste(glow, (sx - glow.width // 2, sy - glow.height // 2 - 8), glow)
            ring = int(18 + 6 * math.sin(index / 3))
            draw.ellipse((sx - ring, sy - ring, sx + ring, sy + ring), outline=(255, 220, 140, 230), width=4)
            overlay.paste(core, (here[0] - core.width // 2, here[1] - core.height // 2), core)
            frame.paste(overlay, (0, 0), overlay)
            if card_alpha > 0.02:
                card = cards[name]
                origin = _card_origin(sx, sy, place, card.width, card.height, frame.width, frame.height)
                frame.paste(_with_alpha(card, card_alpha), origin, _with_alpha(card, card_alpha))
            park_x, park_y = _FIGURE.get(name, (0, -16))
            blend = card_alpha if card_alpha > 0 else 0.0
            shift_x = int(park_x * blend)
            shift_y = int(-16 + (park_y + 16) * blend)
            scale = base.width / 1536
            foot_x = here[0] - sprite_w // 2 + int(shift_x * scale)
            foot_y = here[1] - sprite_h + 8 + int(shift_y * scale)
            frame.paste(shadow, (foot_x, foot_y + sprite_h - 16), shadow)
            frame.paste(traveler, (foot_x, foot_y), traveler)
            frame.save(folder / f"f{index:04d}.jpg", quality=86)
        duration = len(frames) / _FPS
        dest = folder / "journey.mp4"
        audio = (
            f"anoisesrc=color=pink:sample_rate=44100:duration={duration:.2f},"
            "highpass=f=220,lowpass=f=780,tremolo=f=0.16:d=0.45,volume=0.55"
        )
        proc = subprocess.run(
            [
                ffmpeg, "-y",
                "-framerate", str(_FPS), "-i", str(folder / "f%04d.jpg"),
                "-f", "lavfi", "-i", audio,
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                "-c:a", "aac", "-b:a", "128k", "-shortest", str(dest),
            ],
            capture_output=True, text=True, timeout=180,
        )
        if proc.returncode != 0 or not dest.is_file():
            tail = (proc.stderr or "")[-400:]
            raise RuntimeError("تعذر تركيب مقطع الرحلة: " + tail)
        return dest.read_bytes()
    finally:
        shutil.rmtree(folder, ignore_errors=True)
