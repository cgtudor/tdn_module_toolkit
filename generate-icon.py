"""
Generate the TDN Module Toolkit icon.
Creates an ouroboros (serpent eating its tail) with "TDN" text in the center.
"""

import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    print("Installing Pillow...")
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageDraw, ImageFont, ImageFilter


def draw_smooth_serpent(draw, img, center, outer_radius, inner_radius, size):
    """Draw a smooth, realistic ouroboros serpent."""

    # Colors
    snake_base = (50, 65, 45)  # Base dark green
    snake_scales = (65, 85, 55)  # Scale color
    snake_highlight = (80, 105, 65)  # Highlights
    snake_dark = (35, 45, 30)  # Dark shadows
    snake_belly = (90, 100, 75)  # Belly lighter color

    mid_radius = (outer_radius + inner_radius) // 2
    ring_width = outer_radius - inner_radius

    # Draw the main body as a smooth thick ring
    # First pass: dark base
    for r in range(inner_radius, outer_radius + 1):
        # Vary color based on radius (lighter toward outside edge, darker inside)
        t = (r - inner_radius) / (outer_radius - inner_radius)
        if t < 0.3:
            color = snake_belly
        elif t < 0.7:
            color = snake_scales
        else:
            color = snake_base

        draw.ellipse([
            center - r, center - r,
            center + r, center + r
        ], outline=color, width=1)

    # Clear the inner circle (will be filled with background)
    # Actually we want to keep it as part of the ring

    # Draw scale pattern - diagonal overlapping scales
    num_scale_rows = 8
    scales_per_row = 36

    for row in range(num_scale_rows):
        # Radius for this row of scales
        row_t = row / (num_scale_rows - 1)
        row_radius = inner_radius + (outer_radius - inner_radius) * row_t
        scale_size = ring_width / (num_scale_rows * 0.8)

        # Offset every other row
        offset = (row % 2) * (360 / scales_per_row / 2)

        for i in range(scales_per_row):
            angle = math.radians(i * (360 / scales_per_row) + offset - 90)

            sx = center + int(row_radius * math.cos(angle))
            sy = center + int(row_radius * math.sin(angle))

            # Draw a small arc/curve for each scale
            scale_angle = math.degrees(angle) + 90

            # Color variation for depth
            if row < num_scale_rows // 3:
                scale_color = snake_belly
            elif row < 2 * num_scale_rows // 3:
                scale_color = snake_scales
            else:
                scale_color = snake_base

            # Slight color variation per scale
            variation = ((i + row) % 3 - 1) * 8
            scale_color = tuple(max(0, min(255, c + variation)) for c in scale_color)

            # Draw scale as small ellipse
            draw.ellipse([
                sx - scale_size, sy - scale_size,
                sx + scale_size, sy + scale_size
            ], fill=scale_color, outline=snake_dark)

    # Draw the head eating the tail at the top
    head_angle = -90
    head_rad = math.radians(head_angle)

    # Position head slightly outside the ring
    head_center_x = center
    head_center_y = center - mid_radius

    head_length = int(ring_width * 1.6)
    head_width = int(ring_width * 1.3)

    # Draw head base (oval)
    head_points = []
    for i in range(36):
        a = math.radians(i * 10)
        hx = head_center_x + int(head_width/2 * math.cos(a))
        hy = head_center_y + int(head_length/2 * math.sin(a)) - head_length//4
        head_points.append((hx, hy))

    draw.polygon(head_points, fill=snake_scales, outline=snake_dark)

    # Snout (triangular/pointed)
    snout_points = [
        (head_center_x - head_width//3, head_center_y - head_length//3),
        (head_center_x, head_center_y - head_length//2 - head_length//4),
        (head_center_x + head_width//3, head_center_y - head_length//3),
    ]
    draw.polygon(snout_points, fill=snake_scales, outline=snake_dark)

    # Draw jaw lines
    jaw_y = head_center_y - head_length//6
    draw.line([
        (head_center_x - head_width//2.5, jaw_y),
        (head_center_x + head_width//2.5, jaw_y)
    ], fill=snake_dark, width=max(2, size//100))

    # Nostrils
    nostril_size = max(2, size // 80)
    nostril_y = head_center_y - head_length//2
    draw.ellipse([
        head_center_x - head_width//5 - nostril_size, nostril_y - nostril_size,
        head_center_x - head_width//5 + nostril_size, nostril_y + nostril_size
    ], fill=snake_dark)
    draw.ellipse([
        head_center_x + head_width//5 - nostril_size, nostril_y - nostril_size,
        head_center_x + head_width//5 + nostril_size, nostril_y + nostril_size
    ], fill=snake_dark)

    # Eyes - positioned on sides of head
    eye_size = max(4, size // 32)
    eye_y = head_center_y - head_length//4
    eye_offset_x = head_width // 3

    # Eye whites/base
    for ex in [-eye_offset_x, eye_offset_x]:
        draw.ellipse([
            head_center_x + ex - eye_size, eye_y - eye_size,
            head_center_x + ex + eye_size, eye_y + eye_size
        ], fill=(180, 160, 60), outline=snake_dark, width=1)

        # Pupil (vertical slit)
        pupil_w = max(2, eye_size // 3)
        draw.ellipse([
            head_center_x + ex - pupil_w, eye_y - eye_size + 2,
            head_center_x + ex + pupil_w, eye_y + eye_size - 2
        ], fill=(20, 20, 15))

        # Eye highlight
        highlight_size = max(1, eye_size // 3)
        draw.ellipse([
            head_center_x + ex - eye_size//2, eye_y - eye_size//2,
            head_center_x + ex - eye_size//2 + highlight_size, eye_y - eye_size//2 + highlight_size
        ], fill=(255, 255, 220))

    # Tail going into mouth
    tail_y = head_center_y + head_length//6
    tail_width = ring_width * 0.6
    tail_points = [
        (head_center_x - tail_width//2, tail_y + ring_width//2),
        (head_center_x - tail_width//3, tail_y),
        (head_center_x, tail_y - ring_width//4),
        (head_center_x + tail_width//3, tail_y),
        (head_center_x + tail_width//2, tail_y + ring_width//2),
    ]
    draw.polygon(tail_points, fill=snake_highlight, outline=snake_dark)

    # Add some scales on the head
    for i in range(3):
        for j in range(2):
            hsx = head_center_x + (j - 0.5) * head_width//2
            hsy = head_center_y - head_length//8 + i * head_length//6
            hs_size = max(3, size // 60)
            draw.ellipse([
                hsx - hs_size, hsy - hs_size,
                hsx + hs_size, hsy + hs_size
            ], fill=snake_highlight, outline=snake_dark)


def create_tdn_icon(size: int = 512) -> Image.Image:
    """Create the TDN icon at the specified size."""

    # Colors
    bg_color = (75, 61, 96)  # Purple background
    gold_dark = (140, 110, 40)  # Dark gold shadow
    gold = (200, 170, 70)  # Gold for text
    gold_light = (240, 215, 120)  # Highlight

    # Create base image
    img = Image.new('RGBA', (size, size), bg_color + (255,))
    draw = ImageDraw.Draw(img)

    center = size // 2

    # Ouroboros dimensions - make it prominent
    outer_radius = int(size * 0.45)
    inner_radius = int(size * 0.28)

    # Draw the serpent
    draw_smooth_serpent(draw, img, center, outer_radius, inner_radius, size)

    # Draw "TDN" text in the center
    font_size = int(size * 0.24)

    fonts_to_try = [
        "C:/Windows/Fonts/timesbd.ttf",  # Times New Roman Bold
        "C:/Windows/Fonts/times.ttf",
        "C:/Windows/Fonts/georgiab.ttf",  # Georgia Bold
        "C:/Windows/Fonts/georgia.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "timesbd.ttf",
        "times.ttf",
    ]

    font = None
    for font_path in fonts_to_try:
        try:
            font = ImageFont.truetype(font_path, font_size)
            break
        except (IOError, OSError):
            continue

    if font is None:
        font = ImageFont.load_default()

    text = "TDN"

    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    text_x = center - text_width // 2
    text_y = center - text_height // 2 - bbox[1]

    # Shadow
    shadow_offset = max(2, size // 100)
    draw.text((text_x + shadow_offset, text_y + shadow_offset), text, font=font, fill=gold_dark)

    # Main text
    draw.text((text_x, text_y), text, font=font, fill=gold)

    # Subtle highlight on top-left of letters
    draw.text((text_x - 1, text_y - 1), text, font=font, fill=gold_light + (60,))

    return img


def create_simple_icon(size: int = 256) -> Image.Image:
    """Create a simplified version for small sizes."""

    bg_color = (75, 61, 96)
    snake_color = (55, 75, 50)
    snake_dark = (40, 50, 35)
    gold = (200, 170, 70)
    gold_dark = (140, 110, 40)

    img = Image.new('RGBA', (size, size), bg_color + (255,))
    draw = ImageDraw.Draw(img)

    center = size // 2
    outer_r = int(size * 0.44)
    inner_r = int(size * 0.26)
    ring_width = outer_r - inner_r

    # Simple thick ring for body
    draw.ellipse([center - outer_r, center - outer_r, center + outer_r, center + outer_r],
                 fill=snake_color, outline=snake_dark, width=max(1, size//50))
    draw.ellipse([center - inner_r, center - inner_r, center + inner_r, center + inner_r],
                 fill=bg_color, outline=snake_dark, width=max(1, size//80))

    # Simple head at top
    head_w = int(ring_width * 1.2)
    head_h = int(ring_width * 1.0)
    head_y = center - (outer_r + inner_r) // 2

    draw.ellipse([
        center - head_w//2, head_y - head_h//2 - head_h//4,
        center + head_w//2, head_y + head_h//2 - head_h//4
    ], fill=snake_color, outline=snake_dark, width=max(1, size//60))

    # Eyes
    eye_size = max(2, size // 30)
    eye_y = head_y - head_h//4
    for ex in [-head_w//4, head_w//4]:
        draw.ellipse([
            center + ex - eye_size, eye_y - eye_size,
            center + ex + eye_size, eye_y + eye_size
        ], fill=(180, 150, 50), outline=snake_dark)

    # TDN text
    font_size = int(size * 0.28)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/timesbd.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size)
        except:
            font = ImageFont.load_default()

    text = "TDN"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_x = center - text_w // 2
    text_y = center - text_h // 2 - bbox[1]

    # Shadow and text
    draw.text((text_x + 1, text_y + 1), text, font=font, fill=gold_dark)
    draw.text((text_x, text_y), text, font=font, fill=gold)

    return img


def save_as_ico(output_path: str):
    """Save icon with multiple sizes, using simplified version for small sizes."""

    sizes_detailed = [256, 128, 64, 48]
    sizes_simple = [32, 24, 16]

    icons = []

    # High detail for large sizes
    detailed = create_tdn_icon(512)
    for s in sizes_detailed:
        resized = detailed.resize((s, s), Image.Resampling.LANCZOS)
        icons.append((s, resized))

    # Simplified for small sizes
    for s in sizes_simple:
        simple = create_simple_icon(s * 4)  # Generate at 4x then downscale
        resized = simple.resize((s, s), Image.Resampling.LANCZOS)
        icons.append((s, resized))

    # Sort by size
    icons.sort(key=lambda x: x[0])

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Save
    images = [img for _, img in icons]
    images[0].save(
        output_path,
        format='ICO',
        sizes=[(s, s) for s, _ in icons],
        append_images=images[1:]
    )


def main():
    print("Generating TDN icon...")

    # Generate high-res preview
    icon = create_tdn_icon(512)
    Path("resources").mkdir(exist_ok=True)
    icon.save("resources/icon_preview.png")
    print("Preview saved: resources/icon_preview.png")

    # Save as ICO with multiple quality levels
    save_as_ico("resources/icon.ico")
    print("Icon saved: resources/icon.ico")

    # Also save the simple version preview
    simple = create_simple_icon(128)
    simple.save("resources/icon_simple_preview.png")
    print("Simple preview saved: resources/icon_simple_preview.png")

    print("\nDone!")


if __name__ == "__main__":
    main()
