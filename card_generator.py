import io
import os
from PIL import Image, ImageDraw, ImageFont


def get_system_font(size: int, bold: bool = False):
    """Finds a nice font from system or falls back cleanly."""
    candidate_paths = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/SFProText-Bold.ttf" if bold else "/System/Library/Fonts/SFProText-Regular.ttf",
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def generate_progress_card(
    current: float,
    goal: float,
    title: str = "COMMUNITY FUNDING GOAL",
    currency_symbol: str = "$",
    subtitle: str = None
) -> io.BytesIO:
    """
    Renders the clean, modern Discord card featuring the vivid green progress bar
    and an explicit 'GOAL TO HIT' display.
    """
    width = 820
    height = 240
    scale = 2
    sw, sh = width * scale, height * scale
    
    # Colors
    bg_color = (20, 22, 26)           # Sleek Discord Dark #14161A
    card_border = (40, 44, 52)        # Border #282C34
    track_color = (32, 35, 42)        # Empty bar #20232A
    track_border = (48, 52, 62)
    text_white = (255, 255, 255)
    text_muted = (156, 163, 175)      # Neutral grey #9CA3AF
    
    # Vivid Green Bar Palette
    green_primary = (34, 197, 94)     # Emerald #22C55E
    green_light = (74, 222, 128)      # Light Emerald #4ADE80
    green_border = (22, 163, 74)
    
    pct = (current / goal * 100) if goal > 0 else 0
    is_completed = current >= goal and goal > 0
    
    img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    font_title = get_system_font(22 * scale, bold=True)
    font_amount = get_system_font(34 * scale, bold=True)
    font_goal_target = get_system_font(21 * scale, bold=True)
    font_badge = get_system_font(20 * scale, bold=True)
    font_sub = get_system_font(16 * scale, bold=False)
    font_status = get_system_font(17 * scale, bold=True)
    
    # Outer Rounded Card
    margin = 10 * scale
    draw.rounded_rectangle(
        [margin, margin, sw - margin, sh - margin],
        radius=20 * scale,
        fill=bg_color,
        outline=card_border,
        width=2 * scale
    )
    
    pad_x = 40 * scale
    
    # Top Title
    draw.text((pad_x, 32 * scale), title.upper(), font=font_title, fill=text_white)
    
    # Percentage Badge (top right)
    pct_str = f"{pct:.1f}%"
    pct_bbox = draw.textbbox((0, 0), pct_str, font=font_badge)
    pct_w = pct_bbox[2] - pct_bbox[0]
    pct_h = pct_bbox[3] - pct_bbox[1]
    
    badge_pad_x = 16 * scale
    badge_pad_y = 6 * scale
    badge_w = pct_w + (badge_pad_x * 2)
    badge_h = pct_h + (badge_pad_y * 2)
    badge_x = sw - pad_x - badge_w
    badge_y = 36 * scale
    
    badge_bg = (18, 38, 25)
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
        radius=10 * scale,
        fill=badge_bg,
        outline=green_primary,
        width=2 * scale
    )
    draw.text((badge_x + badge_pad_x, badge_y + badge_pad_y - 2 * scale), pct_str, font=font_badge, fill=green_light)
    
    # Current Amount: e.g. "$0.00"
    current_str = f"{currency_symbol}{current:,.2f}"
    draw.text((pad_x, 68 * scale), current_str, font=font_amount, fill=green_primary)
    
    curr_bbox = draw.textbbox((pad_x, 68 * scale), current_str, font=font_amount)
    
    # Explicit "GOAL TO HIT: $500.00"
    goal_to_hit_str = f"GOAL TO HIT: {currency_symbol}{goal:,.2f}"
    draw.text((curr_bbox[2] + 16 * scale, 79 * scale), f"•  {goal_to_hit_str}", font=font_goal_target, fill=(209, 213, 219))
    
    # Progress Bar Track coordinates
    bar_x1 = pad_x
    bar_y1 = 132 * scale
    bar_x2 = sw - pad_x
    bar_y2 = 168 * scale
    bar_h = bar_y2 - bar_y1
    bar_r = bar_h // 2
    total_bar_w = bar_x2 - bar_x1
    
    # Dark track
    draw.rounded_rectangle(
        [bar_x1, bar_y1, bar_x2, bar_y2],
        radius=bar_r,
        fill=track_color,
        outline=track_border,
        width=1 * scale
    )
    
    # Vivid Green fill inside bar
    clamped_pct = min(pct, 100.0)
    if clamped_pct > 0:
        fill_w = int(total_bar_w * (clamped_pct / 100.0))
        fill_w = max(fill_w, bar_h)
        fill_x2 = min(bar_x1 + fill_w, bar_x2)
        
        draw.rounded_rectangle(
            [bar_x1, bar_y1, fill_x2, bar_y2],
            radius=bar_r,
            fill=green_primary,
            outline=green_border,
            width=1 * scale
        )
        
    # Bottom Status Details
    remaining = max(0.0, goal - current)
    if is_completed:
        status_text = f"GOAL REACHED! ({currency_symbol}{current:,.2f} / {currency_symbol}{goal:,.2f})"
        draw.text((pad_x, 184 * scale), status_text, font=font_status, fill=green_light)
    else:
        status_text = f"REMAINING: {currency_symbol}{remaining:,.2f}"
        draw.text((pad_x, 184 * scale), status_text, font=font_status, fill=green_light)
        
    if subtitle:
        sub_bbox = draw.textbbox((0, 0), subtitle, font=font_sub)
        sub_w = sub_bbox[2] - sub_bbox[0]
        draw.text((sw - pad_x - sub_w, 185 * scale), subtitle, font=font_sub, fill=text_muted)
        
    # Anti-aliased downsampling
    img = img.resize((width, height), Image.Resampling.LANCZOS)
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
