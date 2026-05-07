from flask import Flask, request, render_template_string, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageOps
import os
import time

import arabic_reshaper
from bidi.algorithm import get_display

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
LOGO_PATH = "logo.png"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def load_logo():
    try:
        return Image.open(LOGO_PATH).convert("RGBA")
    except:
        return Image.new("RGBA", (100, 100), (255, 255, 255, 0))

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

def rtl(text):
    try:
        reshaped_text = arabic_reshaper.reshape(text)
        return get_display(reshaped_text)
    except:
        return text


def process_image(input_path, text1, text2, index, logo_position="top_left"):
    image = ImageOps.exif_transpose(Image.open(input_path)).convert("RGBA")
    width, height = image.size
    is_portrait = height > width

    logo = LOGO_IMAGE.copy()
    logo_target_width = int(width * (0.15 if is_portrait else 0.18))
    w, h = logo.size
    ratio = logo_target_width / w
    logo = logo.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    margin = int(width * 0.02)

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

    base_font_size = int(height * 0.055)
    font = get_font(base_font_size)

    lines = [rtl(text1)]
    if text2 and text2.strip():
        lines.append(rtl(text2))

    line_widths = []
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    max_text_width = max(line_widths)
    avg_line_height = sum(line_heights) / len(line_heights)
    spacing = int(avg_line_height * 0.2)

    total_text_height = sum(line_heights) + (spacing * (len(lines) - 1))

    padding_x = int(max_text_width * 0.15)
    padding_y = int(avg_line_height * 0.4)

    box_width = max_text_width + (padding_x * 2)
    box_height = total_text_height + (padding_y * 2)

    max_allowed_width = int(width * 0.85)
    if box_width > max_allowed_width:
        box_width = max_allowed_width

    radius = int(box_height * 0.25)
    bottom_margin = int(height * 0.05)

    x1 = (width - box_width) // 2
    x2 = x1 + box_width
    y2 = height - bottom_margin
    y1 = y2 - box_height

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rounded_rectangle(
        [(x1, y1), (x2, y2)],
        radius=radius,
        fill=(255, 255, 255, 255)
    )

    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)

    current_y = y1 + padding_y
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        tx = x1 + (box_width - tw) // 2
        draw.text((tx, current_y), line, fill=(0, 0, 0, 255), font=font)
        current_y += line_heights[i] + spacing

    image_to_save = image.convert("RGB")
    filename = f"result_{index}.jpg"
    out = os.path.join(OUTPUT_FOLDER, filename)
    image_to_save.save(out, "JPEG", quality=90, optimize=True)

    return "/output/" + filename


HTML = """ ... (לא שונה בכלל) ... """

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
        t1 = text1_list[i] if i < len(text1_list) else ""
        t2 = text2_list[i] if i < len(text2_list) else ""
        pos = logo_pos_list[i] if i < len(logo_pos_list) else "top_left"
        result = process_image(path, t1, t2, i, pos)
        results.append(result)
    return jsonify({"images": results, "run_id": run_id})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
