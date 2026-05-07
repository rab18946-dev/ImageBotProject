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
        if not text:
            return ""
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except:
        return text

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

    if logo_position == "top_left": pos = (margin, margin)
    elif logo_position == "top_right": pos = (width - logo.width - margin, margin)
    elif logo_position == "bottom_left": pos = (margin, height - logo.height - margin)
    elif logo_position == "bottom_right": pos = (width - logo.width - margin, height - logo.height - margin)
    else: pos = (margin, margin)

    image.paste(logo, pos, logo)
    draw = ImageDraw.Draw(image)

    base_font_size = int(height * 0.055)
    font = get_font(base_font_size)

    lines = []
    if text1: lines.append(rtl(text1))
    if text2 and text2.strip(): lines.append(rtl(text2))

    if not lines:
        image_to_save = image.convert("RGB")
        filename = f"result_{index}.jpg"
        out = os.path.join(OUTPUT_FOLDER, filename)
        image_to_save.save(out, "JPEG", quality=90, optimize=True)
        return "/output/" + filename

    # חישוב גבהים בלבד לצורך יצירת התיבה (שימוש ב-anchor יטפל במיקום האופקי)
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])

    avg_line_height = sum(line_heights) / len(line_heights)
    spacing = int(avg_line_height * 0.2)
    total_text_height = sum(line_heights) + (spacing * (len(lines) - 1))

    # רוחב התיבה (נשאר יחסי לרוחב התמונה כדי שיהיה מקום לטקסט)
    box_width = int(width * 0.8)
    padding_y = int(avg_line_height * 0.4)
    box_height = total_text_height + (padding_y * 2)

    radius = int(box_height * 0.25)
    bottom_margin = int(height * 0.05)

    x1 = (width - box_width) // 2
    x2 = x1 + box_width
    y2 = height - bottom_margin
    y1 = y2 - box_height

    # ציור המלבן
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rounded_rectangle([(x1, y1), (x2, y2)], radius=radius, fill=(255, 255, 255, 255))
    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)

    # ✅ התיקון הקריטי: שימוש ב-anchor="mm" ומרכז התיבה
    center_x = x1 + box_width // 2
    current_y = y1 + padding_y + (line_heights[0] // 2)

    for i, line in enumerate(lines):
        # draw.text עם anchor="mm" ממקם את מרכז הטקסט בדיוק בנקודה שניתנה
        draw.text((center_x, current_y), line, fill=(0, 0, 0, 255), font=font, anchor="mm")
        if i < len(lines) - 1:
            current_y += (line_heights[i] // 2) + spacing + (line_heights[i+1] // 2)

    image_to_save = image.convert("RGB")
    filename = f"result_{index}.jpg"
    out = os.path.join(OUTPUT_FOLDER, filename)
    image_to_save.save(out, "JPEG", quality=90, optimize=True)
    return "/output/" + filename

HTML = """
<!DOCTYPE html>
<html lang="he">
<head>
<meta charset="UTF-8">
<title>מערכת בצילא דמהימנותא</title>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@100..900&display=swap" rel="stylesheet">
<style>
body { font-family: 'Heebo', sans-serif; direction: rtl; text-align: center; background: #f6f1e6; margin: 0; }
.header { background: linear-gradient(135deg, #f7e7b0, #f3e6c2); padding: 15px; border-bottom: 1px solid #d4af37; }
.row { display: flex; gap: 10px; align-items: center; background: white; margin: 15px auto; padding: 15px; width: 90%; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
input[type="text"] { padding: 8px; border: 1px solid #ddd; border-radius: 6px; flex: 1; }
button { padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; font-weight: bold; }
.main-btn { background: #D4AF37; color: white; }
#gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 15px; padding: 20px; }
#gallery img { width: 100%; border-radius: 8px; }
</style>
</head>
<body>
<div class="header">
    <img src="/logo" width="120">
    <h2>מערכת בצילא דמהימנותא</h2>
</div>
<div style="margin: 20px;">
    <button class="main-btn" onclick="processAll()">עבד תמונות</button>
    <button style="background:#fff; border:1px solid #ccc;" onclick="location.reload()">רענן</button>
</div>
<div id="rows"></div>
<button onclick="addRow()" style="background:#eee;">+ הוסף שורה</button>
<div id="loader" style="display:none; margin:20px;">⏳ מעבד...</div>
<div id="gallery"></div>
<script>
function addRow(){
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
        <input type="file" multiple>
        <input type="text" placeholder="שורה 1">
        <input type="text" placeholder="שורה 2">
        <select><option value="top_left">שמאל למעלה</option><option value="top_right">ימין למעלה</option><option value="bottom_left">שמאל למטה</option><option value="bottom_right" selected>ימין למטה</option></select>
        <button class="delete-btn" onclick="this.parentElement.remove()">🗑</button>
    `;
    document.getElementById("rows").appendChild(row);
}
async function sendToServer(rows){
    let formData = new FormData();
    rows.forEach(row=>{
        const files = row.querySelector("input[type=file]").files;
        const inputs = row.querySelectorAll("input[type=text]");
        const pos = row.querySelector("select").value;
        for(let i=0; i<files.length; i++){
            formData.append("images", files[i]);
            formData.append("text1", inputs[0].value);
            formData.append("text2", inputs[1].value);
            formData.append("logo_position", pos);
        }
    });
    document.getElementById("loader").style.display = "block";
    let res = await fetch("/process", {method:"POST", body:formData});
    let data = await res.json();
    document.getElementById("loader").style.display = "none";
    data.images.forEach(img=>{
        document.getElementById("gallery").innerHTML += `<div><img src="${img}"><br><a href="${img}" download>הורד</a></div>`;
    });
}
function processAll(){ sendToServer(document.querySelectorAll(".row")); }
window.onload = addRow;
</script>
</body>
</html>
"""

@app.route("/")
def home(): return render_template_string(HTML)

@app.route("/logo")
def logo(): return send_file(LOGO_PATH)

@app.route("/output/<filename>")
def serve_output(filename): return send_file(os.path.join(OUTPUT_FOLDER, filename))

@app.route("/process", methods=["POST"])
def process():
    files = request.files.getlist("images")
    text1_list = request.form.getlist("text1")
    text2_list = request.form.getlist("text2")
    logo_pos_list = request.form.getlist("logo_position")
    run_id = str(int(time.time() * 1000))
    results = []
    for i, file in enumerate(files):
        path = os.path.join(UPLOAD_FOLDER, f"{run_id}_{i}_{file.filename}")
        file.save(path)
        t1 = text1_list[i] if i < len(text1_list) else ""
        t2 = text2_list[i] if i < len(text2_list) else ""
        pos = logo_pos_list[i] if i < len(logo_pos_list) else "bottom_right"
        results.append(process_image(path, t1, t2, i, pos))
    return jsonify({"images": results})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
