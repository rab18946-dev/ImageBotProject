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

# ---------- LOGO ----------
def load_logo():
    try:
        return Image.open(LOGO_PATH).convert("RGBA")
    except:
        return Image.new("RGBA", (100, 100), (255, 255, 255, 0))

LOGO_IMAGE = load_logo()

# ---------- FONT ----------
def get_font(size):
    return ImageFont.truetype("Assistant-Bold.ttf", size)

# ---------- RTL FIX ----------
def rtl(text):
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped)
    return bidi_text.replace("״", '"').replace("׳", "'")

# ---------- IMAGE PROCESS ----------
def process_image(input_path, text1, text2, index, logo_position="top_left"):

    image = ImageOps.exif_transpose(Image.open(input_path)).convert("RGBA")
    width, height = image.size

    # memory protection
    image.thumbnail((2200, 2200))

    # ---------- LOGO ----------
    logo = LOGO_IMAGE.copy()
    logo_target_width = int(width * 0.18)
    w, h = logo.size
    ratio = logo_target_width / w
    logo = logo.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    margin = int(width * 0.02)

    positions = {
        "top_left": (margin, margin),
        "top_right": (width - logo.width - margin, margin),
        "bottom_left": (margin, height - logo.height - margin),
        "bottom_right": (width - logo.width - margin, height - logo.height - margin),
    }

    image.paste(logo, positions.get(logo_position, (margin, margin)), logo)

    draw = ImageDraw.Draw(image)

    # ---------- TEXT ----------
    font = get_font(int(height * 0.055))

    lines = []
    if text1:
        lines.append(rtl(text1))
    if text2:
        lines.append(rtl(text2))

    if not lines:
        out = os.path.join(OUTPUT_FOLDER, f"result_{index}.jpg")
        image.convert("RGB").save(out, "JPEG", quality=90)
        image.close()
        return "/output/" + os.path.basename(out)

    line_data = []
    max_w = 0

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        line_data.append((line, w, h))
        max_w = max(max_w, w)

    avg_h = sum(h for _, _, h in line_data) / len(line_data)
    spacing = int(avg_h * 0.25)

    total_h = sum(h for _, _, h in line_data) + spacing * (len(lines) - 1)

    box_w = max(350, min(int(width * 0.8), max_w + 200))
    box_h = total_h + int(avg_h)

    x1 = (width - box_w) // 2
    y2 = height - int(height * 0.05)
    y1 = y2 - box_h

    # ---------- BACKGROUND BOX ----------
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(
        [(x1, y1), (x1 + box_w, y2)],
        radius=30,
        fill=(255, 255, 255, 255)
    )

    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)

    # ---------- DRAW TEXT ----------
    current_y = y1 + int(avg_h * 0.5)

    for line, tw, th in line_data:
        tx = x1 + (box_w - tw) // 2
        draw.text((tx, current_y), line, font=font, fill=(0, 0, 0))
        current_y += th + spacing

    # ---------- SAVE + CLEAN ----------
    out = os.path.join(OUTPUT_FOLDER, f"result_{index}.jpg")
    image.convert("RGB").save(out, "JPEG", quality=90)

    image.close()
    del image

    return "/output/" + os.path.basename(out)

# ---------- API ----------
@app.route("/process", methods=["POST"])
def process():

    files = request.files.getlist("images")
    t1_list = request.form.getlist("text1")
    t2_list = request.form.getlist("text2")
    pos_list = request.form.getlist("logo_position")

    run_id = str(int(time.time() * 1000))
    results = []

    for i, file in enumerate(files):

        path = os.path.join(UPLOAD_FOLDER, f"{run_id}_{i}.jpg")
        file.save(path)

        t1 = t1_list[i] if i < len(t1_list) else ""
        t2 = t2_list[i] if i < len(t2_list) else ""
        pos = pos_list[i] if i < len(pos_list) else "bottom_right"

        results.append(process_image(path, t1, t2, i, pos))

    return jsonify({"images": results})
