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

# ---------- לוגו ----------
def load_logo():
    try:
        return Image.open(LOGO_PATH).convert("RGBA")
    except:
        return Image.new("RGBA", (100, 100), (255, 255, 255, 0))

LOGO_IMAGE = load_logo()

# ---------- פונטים ----------
def get_font(size):
    try:
        return ImageFont.truetype("Assistant-Bold.ttf", size)
    except:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except:
            return ImageFont.load_default()

# ---------- עברית (תיקון RTL יציב יותר) ----------
def rtl(text):
    if not text:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped, base_dir="R")
    except:
        return text

# ---------- עיבוד תמונה ----------
def process_image(input_path, text1, text2, index, logo_position="top_left"):
    image = ImageOps.exif_transpose(Image.open(input_path)).convert("RGBA")
    width, height = image.size
    is_portrait = height > width

    # לוגו
    logo = LOGO_IMAGE.copy()
    logo_target_width = int(width * (0.15 if is_portrait else 0.18))

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

    font_size = int(height * 0.055)
    font = get_font(font_size)

    lines = []
    if text1:
        lines.append(rtl(text1))
    if text2:
        lines.append(rtl(text2))

    # אם אין טקסט
    if not lines:
        out = os.path.join(OUTPUT_FOLDER, f"result_{index}.jpg")
        image.convert("RGB").save(out, "JPEG", quality=90)
        return "/output/" + os.path.basename(out)

    # חישוב מידות
    line_data = []
    max_width = 0

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        line_data.append((line, tw, th))
        max_width = max(max_width, tw)

    avg_h = sum(x[2] for x in line_data) / len(line_data)
    spacing = int(avg_h * 0.25)

    total_h = sum(x[2] for x in line_data) + spacing * (len(lines) - 1)

    box_width = max(350, min(int(width * 0.8), max_width + 180))
    padding_y = int(avg_h * 0.5)
    box_height = total_h + padding_y * 2

    x1 = (width - box_width) // 2
    x2 = x1 + box_width
    y2 = height - int(height * 0.05)
    y1 = y2 - box_height

    # רקע טקסט
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    radius = int(box_height * 0.2)
    d.rounded_rectangle(
        [(x1, y1), (x2, y2)],
        radius=radius,
        fill=(255, 255, 255, 255)
    )

    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)

    # ציור טקסט
    y = y1 + padding_y
    for line, tw, th in line_data:
        x = x1 + (box_width - tw) // 2
        draw.text((x, y), line, fill=(0, 0, 0, 255), font=font)
        y += th + spacing

    out = os.path.join(OUTPUT_FOLDER, f"result_{index}.jpg")
    image.convert("RGB").save(out, "JPEG", quality=90)

    return "/output/" + os.path.basename(out)

# ---------- HTML ----------
HTML = """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<title>מערכת עיבוד תמונות</title>
</head>
<body>
<h2>מערכת עיבוד תמונות</h2>

<div id="rows"></div>
<button onclick="addRow()">הוסף</button>
<button onclick="send()">עבד</button>

<script>
function addRow(){
    const div = document.createElement('div');
    div.innerHTML = `
        <input type="file" multiple>
        <input placeholder="טקסט 1">
        <input placeholder="טקסט 2">
        <select>
            <option value="bottom_right">ימין למטה</option>
            <option value="bottom_left">שמאל למטה</option>
            <option value="top_right">ימין למעלה</option>
            <option value="top_left">שמאל למעלה</option>
        </select>
        <br><br>
    `;
    document.getElementById('rows').appendChild(div);
}

async function send(){
    const rows = document.querySelectorAll('#rows > div');
    const fd = new FormData();

    rows.forEach(r=>{
        const files = r.querySelector('input[type=file]').files;
        const t1 = r.querySelectorAll('input')[1].value;
        const t2 = r.querySelectorAll('input')[2].value;
        const pos = r.querySelector('select').value;

        for(let i=0;i<files.length;i++){
            fd.append("images", files[i]);
            fd.append("text1", t1);
            fd.append("text2", t2);
            fd.append("logo_position", pos);
        }
    });

    const res = await fetch("/process",{method:"POST",body:fd});
    const data = await res.json();

    alert("סיום: " + data.images.length);
}
</script>

</body>
</html>
"""

# ---------- Routes ----------
@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/output/<file>")
def output(file):
    return send_file(os.path.join(OUTPUT_FOLDER, file))

@app.route("/process", methods=["POST"])
def process():
    files = request.files.getlist("images")
    t1 = request.form.getlist("text1")
    t2 = request.form.getlist("text2")
    pos = request.form.getlist("logo_position")

    results = []
    run_id = str(int(time.time() * 1000))

    for i, f in enumerate(files):
        path = os.path.join(UPLOAD_FOLDER, f"{run_id}_{i}.jpg")
        f.save(path)

        results.append(
            process_image(
                path,
                t1[i] if i < len(t1) else "",
                t2[i] if i < len(t2) else "",
                i,
                pos[i] if i < len(pos) else "bottom_right"
            )
        )

    return jsonify({"images": results})

# ---------- חשוב לRender ----------
app = app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
