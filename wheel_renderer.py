import io
import math
import random
from PIL import Image, ImageDraw, ImageFont

# Vibrant color palette for wheel slices
SLICE_COLORS = [
    (244, 67, 54),    # Red
    (233, 30, 99),    # Pink
    (156, 39, 176),   # Purple
    (103, 58, 183),   # Deep Purple
    (63, 81, 181),    # Indigo
    (33, 150, 243),   # Blue
    (3, 169, 244),    # Light Blue
    (0, 188, 212),    # Cyan
    (0, 150, 136),    # Teal
    (76, 175, 80),    # Green
    (139, 195, 74),   # Light Green
    (205, 220, 57),   # Lime
    (255, 235, 59),   # Yellow
    (255, 193, 7),    # Amber
    (255, 152, 0),    # Orange
    (255, 87, 34),    # Deep Orange
]

def get_font(size: int, bold: bool = True) -> ImageFont.ImageFont:
    font_names = ["segoeuib.ttf", "arialbd.ttf", "arial.ttf", "segoeui.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]
    for font_name in font_names:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None

def truncate_text(text: str, max_chars: int = 15) -> str:
    if len(text) > max_chars:
        return text[:max_chars - 2] + ".."
    return text

def _create_wheel_disc(names: list[str], size: int = 600, radius: int = 250) -> tuple[Image.Image, int]:
    center = size / 2.0
    n_slices = len(names)
    slice_angle = 360.0 / n_slices

    disc = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d_draw = ImageDraw.Draw(disc)

    # 1. Slices
    bbox = [center - radius, center - radius, center + radius, center + radius]
    for i, name in enumerate(names):
        c_start = i * slice_angle
        c_end = c_start + slice_angle
        color = SLICE_COLORS[i % len(SLICE_COLORS)]
        d_draw.pieslice(bbox, start=c_start, end=c_end, fill=color, outline=(25, 25, 25), width=2)

    # 2. Text overlay
    font_size = 22
    if n_slices > 6:
        font_size = 18
    if n_slices > 12:
        font_size = 15
    if n_slices > 20:
        font_size = 12
    font = get_font(font_size, bold=True)

    for i, name in enumerate(names):
        mid_angle_deg = (i * slice_angle) + (slice_angle / 2.0)
        mid_angle_rad = math.radians(mid_angle_deg)
        label_r = radius * 0.62
        x = center + label_r * math.cos(mid_angle_rad)
        y = center + label_r * math.sin(mid_angle_rad)

        display_name = truncate_text(name, 14 if n_slices <= 10 else 10)
        try:
            tb = d_draw.textbbox((0, 0), display_name, font=font)
            tw = tb[2] - tb[0]
            th = tb[3] - tb[1]
        except Exception:
            tw, th = len(display_name) * 8, 16

        txt_img = Image.new("RGBA", (tw + 16, th + 8), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        txt_draw.text((9, 5), display_name, fill=(0, 0, 0, 220), font=font)
        txt_draw.text((8, 4), display_name, fill=(255, 255, 255, 255), font=font)

        rot_angle = -mid_angle_deg
        if 90 < (mid_angle_deg % 360) < 270:
            rot_angle += 180

        rot_txt = txt_img.rotate(rot_angle, expand=True, resample=Image.Resampling.BICUBIC)
        rw, rh = rot_txt.size
        disc.paste(rot_txt, (int(x - rw / 2), int(y - rh / 2)), rot_txt)

    # 3. Outer golden wheel rim
    rim_width = 16
    d_draw.ellipse(
        [center - radius, center - radius, center + radius, center + radius],
        outline=(218, 165, 32), width=rim_width
    )
    d_draw.ellipse(
        [center - radius - rim_width // 2, center - radius - rim_width // 2,
         center + radius + rim_width // 2, center + radius + rim_width // 2],
        outline=(255, 215, 0), width=3
    )

    # 4. Pegs
    n_pegs = max(16, n_slices * 4)
    peg_radius = 4
    for p in range(n_pegs):
        ang = math.radians(p * (360.0 / n_pegs))
        px = center + radius * math.cos(ang)
        py = center + radius * math.sin(ang)
        d_draw.ellipse(
            [px - peg_radius, py - peg_radius, px + peg_radius, py + peg_radius],
            fill=(255, 245, 180), outline=(130, 90, 10), width=1
        )

    # 5. Center Hub
    hub_radius = 58
    d_draw.ellipse(
        [center - hub_radius, center - hub_radius, center + hub_radius, center + hub_radius],
        fill=(218, 165, 32), outline=(255, 235, 120), width=4
    )
    inner_hub = hub_radius - 12
    d_draw.ellipse(
        [center - inner_hub, center - inner_hub, center + inner_hub, center + inner_hub],
        fill=(35, 37, 40)
    )
    hub_font = get_font(13, bold=True)
    d_draw.text((center - 27, center - 14), "WHEEL OF", fill=(255, 215, 0), font=hub_font)
    d_draw.text((center - 12, center + 2), "PEP", fill=(255, 255, 255), font=hub_font)

    return disc, n_pegs

def render_spinning_wheel_gif(names: list[str], winner: str) -> io.BytesIO:
    if not names:
        names = ["Nobody"]
    if winner not in names:
        winner = names[0]

    size = 600
    center = size / 2.0
    radius = 250
    disc, n_pegs = _create_wheel_disc(names, size=size, radius=radius)

    winner_idx = names.index(winner)
    slice_angle = 360.0 / len(names)
    mid_angle = winner_idx * slice_angle + slice_angle / 2.0
    final_angle = (mid_angle + 90.0) % 360.0

    total_rotations = 3.5 * 360.0
    start_angle = final_angle - total_rotations

    num_frames = 36
    frames = []
    durations = []
    bg_color = (43, 45, 49)

    pointer_tip_y = center - radius + 10
    pointer_base_y = pointer_tip_y - 35
    arrow_pts = [
        (center, pointer_tip_y),
        (center - 16, pointer_base_y),
        (center, pointer_base_y + 8),
        (center + 16, pointer_base_y),
    ]

    for f in range(num_frames):
        t = f / (num_frames - 1)
        ease = 1.0 - math.pow(1.0 - t, 3.4)
        cur_angle = start_angle + ease * total_rotations

        rot_disc = disc.rotate(cur_angle, resample=Image.Resampling.BILINEAR)

        frame = Image.new("RGB", (size, size), bg_color)
        frame.paste(rot_disc, (0, 0), rot_disc)
        f_draw = ImageDraw.Draw(frame)

        speed = 1.0 - t
        tick_offset = 0
        if speed > 0.04:
            peg_phase = (cur_angle * n_pegs / 360.0) % 1.0
            if peg_phase < 0.35:
                tick_offset = int(3.5 * (1.0 - peg_phase / 0.35) * speed)

        cur_arrow = [(x + tick_offset, y) for x, y in arrow_pts]
        f_draw.polygon([(x + 2, y + 2) for x, y in cur_arrow], fill=(20, 20, 25))
        f_draw.polygon(cur_arrow, fill=(230, 35, 45), outline=(255, 215, 0), width=2)
        f_draw.ellipse(
            [center - 4 + tick_offset, pointer_base_y + 3, center + 4 + tick_offset, pointer_base_y + 11],
            fill=(255, 255, 255)
        )

        q_frame = frame.quantize(colors=64, method=Image.Quantize.MEDIANCUT)
        frames.append(q_frame)

        if f == num_frames - 1:
            durations.append(4000)
        elif t > 0.88:
            durations.append(130)
        elif t > 0.65:
            durations.append(85)
        else:
            durations.append(45)

    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True
    )
    buf.seek(0)
    return buf
