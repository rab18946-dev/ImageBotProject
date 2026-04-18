from flask import Flask, request, render_template_string, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageOps
import os
import time

import arabic_reshaper

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
LOGO_PATH = "logo.png"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def load_logo():
    return Image.open(LOGO_PATH).convert("RGBA")

LOGO_IMAGE = load_logo()

def compress_and_resize(image, max_size=(1280, 1280), quality=85):
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    image.thumbnail(max_size)
    return image, quality

def get_font(size):
    try:
        return ImageFont.truetype("Assistant-Bold.ttf", size)
    except:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except:
            return ImageFont.load_default()

# ✅ תיקון שביקשת
def rtl(text):
    return arabic_reshaper.reshape(text)

def process_image(input_path, text1, text2, index, logo_position="top_left"):
    image = ImageOps.exif_transpose(Image.open(input_path)).convert("RGBA")

    width, height = image.size
    is_portrait = height > width

    logo = LOGO_IMAGE.copy()

    logo_target_width = int(width * (0.2 if is_portrait else 0.25))
    w, h = logo.size
    ratio = logo_target_width / w
    logo = logo.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    margin = 20

    if logo_position == "top_left":
        pos = (margin, margin)
    elif logo_position == "top_right":
        pos = (width - logo.width - margin, margin)
    elif logo_position == "bottom_left":
        pos = (margin, height - logo.height - margin)
    elif logo_position == "bottom_right":
        pos = (width - logo.width - margin, height - logo.height - margin)
    else:
        pos = (margin, margin)

    image.paste(logo, pos, logo)

    draw = ImageDraw.Draw(image)
    font = get_font(120)

    lines = [rtl(text1)]
    if text2 and text2.strip():
        lines.append(rtl(text2))

    line_sizes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    line_heights = [(b[3] - b[1]) for b in line_sizes]
    line_widths = [(b[2] - b[0]) for b in line_sizes]

    max_text_width = max(line_widths)
    total_height = sum(line_heights) + (20 * (len(lines) - 1))

    padding_x = 80
    padding_y = 50

    box_width = max_text_width + padding_x * 2
    box_height = total_height + padding_y * 2 + 40

    max_width = int(width * 0.95)
    box_width = min(box_width, max_width)

    radius = 40
    bottom_margin = 80

    x1 = (width - box_width) // 2
    x2 = x1 + box_width

    bar_top = height - box_height - bottom_margin
    bar_bottom = height - bottom_margin

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    d.rounded_rectangle(
        [(x1, bar_top), (x2, bar_bottom)],
        radius=radius,
        fill=(255, 255, 255, 255)
    )

    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)

    y = bar_top + padding_y

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x_text = (width - tw) // 2 - bbox[0]

        draw.text((x_text, y), line, fill=(0, 0, 0, 255), font=font)
        y += line_heights[i] + 20

    image_to_save = image.convert("RGB")

    filename = f"result_{index}.jpg"
    out = os.path.join(OUTPUT_FOLDER, filename)
    image_to_save.save(out, "JPEG", quality=85, optimize=True)

    return "/output/" + filename


HTML = """
<!DOCTYPE html>
<html lang="he">
<head>
<meta charset="UTF-8">
<title>מערכת בצילא דמהימנותא</title>
</head>
<body>
<h2>מערכת פעילה</h2>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/logo")
def logo():
    return send_file(LOGO_PATH)

@app.route("/output/<filename>")
def serve_output(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename))

@app.route("/process", methods=["POST"])
def process():
    files = request.files.getlist("images")
    text1_list = request.form.getlist("text1")
    text2_list = request.form.getlist("text2")
    logo_pos_list = request.form.getlist("logo_position")

    run_id = str(int(time.time() * 1000))
    results = []

    for i, file in enumerate(files):
        filename = f"{run_id}_{i}_{file.filename}"
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)

        t1 = text1_list[i]
        t2 = text2_list[i]
        pos = logo_pos_list[i] if i < len(logo_pos_list) else "top_left"

        result = process_image(path, t1, t2, i, pos)
        results.append(result)

    return jsonify({
        "images": results,
        "run_id": run_id
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
