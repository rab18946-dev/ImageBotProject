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

# ✅ תיקון 1: טיפול בפיסוק עברי ומניעת שבירת גרשיים
def rtl(text):
    try:
        if not text:
            return ""
        # חיבור אותיות
        reshaped = arabic_reshaper.reshape(text)
        # סידור כיווניות
        bidi_text = get_display(reshaped)
        # החלפת גרשיים טיפוגרפיים בסטנדרטיים למניעת היפוכים ב-Pillow
        return bidi_text.replace("״", '"').replace("׳", "'")
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

    # הכנת השורות
    lines_processed = []
    if text1: lines_processed.append(rtl(text1))
    if text2 and text2.strip(): lines_processed.append(rtl(text2))

    if not lines_processed:
        image_to_save = image.convert("RGB")
        filename = f"result_{index}.jpg"
        out = os.path.join(OUTPUT_FOLDER, filename)
        image_to_save.save(out, "JPEG", quality=90, optimize=True)
        return "/output/" + filename

    # חישוב רוחב מקסימלי לטקסט
    max_text_width = 0
    line_heights = []
    for line in lines_processed:
        bbox = draw.textbbox((0, 0), line, font=font)
        max_text_width = max(max_text_width, bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    avg_line_height = sum(line_heights) / len(line_heights)
    spacing = int(avg_line_height * 0.2)
    total_text_height = sum(line_heights) + (spacing * (len(lines_processed) - 1))

    # ✅ תיקון 2: רוחב תיבה משופר (מינימום 300 פיקסלים)
    box_width = max(300, min(int(width * 0.85), max_text_width + 200))
    padding_y = int(avg_line_height * 0.4)
    box_height = total_text_height + (padding_y * 2)

    x1 = (width - box_width) // 2
    x2 = x1 + box_width
    y2 = height - int(height * 0.05)
    y1 = y2 - box_height

    # ציור המלבן
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d_ov = ImageDraw.Draw(overlay)
    radius = int(box_height * 0.25)
    d_ov.rounded_rectangle([(x1, y1), (x2, y2)], radius=radius, fill=(255, 255, 255, 255))
    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)

    # ✅ תיקון 3: מרכוז טקסט מושלם עם anchor="mm"
    center_x = x1 + box_width // 2
    # נתחיל מהחלק העליון של התיבה + פדינג + חצי מגובה השורה הראשונה
    current_y = y1 + padding_y + (line_heights[0] // 2)

    for i, line in enumerate(lines_processed):
        draw.text((center_x, current_y), line, fill=(0, 0, 0, 255), font=font, anchor="mm")
        if i < len(lines_processed) - 1:
            current_y += (line_heights[i] // 2) + spacing + (line_heights[i+1] // 2)

    image_to_save = image.convert("RGB")
    filename = f"result_{index}.jpg"
    out = os.path.join(OUTPUT_FOLDER, filename)
    image_to_save.save(out, "JPEG", quality=90, optimize=True)
    return "/output/" + filename

# --- Flask & HTML נשארו כמעט זהים עם שיפורים קלים ב-UI ---

HTML = """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>מערכת בצילא דמהימנותא</title>
    <link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Heebo', sans-serif; background: #f6f1e6; margin: 0; text-align: center; }
        .header { background: linear-gradient(135deg, #f7e7b0, #f3e6c2); padding: 20px; border-bottom: 2px solid #d4af37; }
        .container { padding: 20px; }
        .row { background: white; width: 95%; max-width: 900px; margin: 15px auto; padding: 20px; border-radius: 15px; display: flex; align-items: center; gap: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); flex-wrap: wrap; }
        input[type="text"] { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 8px; min-width: 150px; }
        select { padding: 11px; border-radius: 8px; border: 1px solid #ddd; background: #fff; }
        .btn-process { background: #d4af37; color: white; padding: 15px 40px; font-size: 20px; border: none; border-radius: 12px; cursor: pointer; margin: 20px; font-weight: bold; }
        .btn-add { background: #fff; border: 2px dashed #d4af37; color: #d4af37; padding: 10px 25px; border-radius: 10px; cursor: pointer; font-weight: bold; }
        #gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 20px; padding: 30px; }
        .card { background: white; padding: 10px; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
        .card img { width: 100%; border-radius: 8px; }
        #loader { display: none; margin: 20px; font-weight: bold; color: #d4af37; font-size: 1.2em; }
    </style>
</head>
<body>
    <div class="header">
        <img src="/logo" width="160">
        <h1>מערכת בצילא דמהימנותא</h1>
    </div>
    <div class="container">
        <div id="rows"></div>
        <button class="btn-add" onclick="addRow()">+ הוסף שורה</button><br>
        <button class="btn-process" onclick="processAll()">עבד ושמור תמונות</button>
        <div id="loader">⏳ מעבד תמונות ברגע זה...</div>
        <div id="gallery"></div>
    </div>

    <script>
        function addRow() {
            const div = document.createElement('div');
            div.className = 'row';
            div.innerHTML = `
                <input type="file" multiple class="f-files" style="width:200px">
                <input type="text" placeholder="שורה 1 (למשל: כ״ק אדמו״ר)" class="f-t1">
                <input type="text" placeholder="שורה 2 (למשל: שליט״א)" class="f-t2">
                <select class="f-pos">
                    <option value="top_left">לוגו: שמאל-למעלה</option>
                    <option value="top_right">לוגו: ימין-למעלה</option>
                    <option value="bottom_left">לוגו: שמאל-למטה</option>
                    <option value="bottom_right" selected>לוגו: ימין-למטה</option>
                </select>
                <button onclick="this.parentElement.remove()" style="background:none; border:none; cursor:pointer; font-size:20px">🗑️</button>
            `;
            document.getElementById('rows').appendChild(div);
        }

        async function processAll() {
            const rows = document.querySelectorAll('.row');
            const formData = new FormData();
            let totalFiles = 0;

            rows.forEach(row => {
                const files = row.querySelector('.f-files').files;
                for (let i = 0; i < files.length; i++) {
                    formData.append('images', files[i]);
                    formData.append('text1', row.querySelector('.f-t1').value);
                    formData.append('text2', row.querySelector('.f-t2').value);
                    formData.append('logo_position', row.querySelector('.f-pos').value);
                    totalFiles++;
                }
            });

            if (totalFiles === 0) return alert("בחר לפחות תמונה אחת!");

            document.getElementById('loader').style.display = 'block';
            document.getElementById('gallery').innerHTML = '';

            const res = await fetch('/process', { method: 'POST', body: formData });
            const data = await res.json();
            
            document.getElementById('loader').style.display = 'none';
            data.images.forEach(url => {
                document.getElementById('gallery').innerHTML += `
                    <div class="card">
                        <img src="${url}">
                        <a href="${url}" download style="display:block; margin-top:10px; color:#d4af37; text-decoration:none; font-weight:bold">⬇️ הורד</a>
                    </div>`;
            });
        }
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
    t1_list = request.form.getlist("text1")
    t2_list = request.form.getlist("text2")
    pos_list = request.form.getlist("logo_position")
    
    run_id = str(int(time.time() * 1000))
    results = []
    
    for i, file in enumerate(files):
        if not file.filename: continue
        path = os.path.join(UPLOAD_FOLDER, f"{run_id}_{i}_{file.filename}")
        file.save(path)
        
        # התאמת הטקסטים לפי האינדקס
        t1 = t1_list[i] if i < len(t1_list) else ""
        t2 = t2_list[i] if i < len(t2_list) else ""
        pos = pos_list[i] if i < len(pos_list) else "bottom_right"
        
        results.append(process_image(path, t1, t2, i, pos))
        
    return jsonify({"images": results})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
