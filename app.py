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

# ---------------- JOB SYSTEM ----------------
jobs = {}

def load_logo():
    try:
        return Image.open(LOGO_PATH).convert("RGBA")
    except:
        return Image.new("RGBA", (100, 100), (255, 255, 255, 0))

LOGO_IMAGE = load_logo()

def get_font(size):
    # חיפוש גופן Bold למראה דומיננטי
    fonts_to_try = ["Assistant-Bold.ttf", "Heebo-Bold.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"]
    for f in fonts_to_try:
        try:
            return ImageFont.truetype(f, size)
        except:
            continue
    return ImageFont.load_default()

def rtl(text):
    try:
        return arabic_reshaper.reshape(text)
    except:
        return text

def process_image(input_path, text1, text2, index, logo_position="top_left"):
    with Image.open(input_path) as raw_img:
        image = ImageOps.exif_transpose(raw_img).convert("RGBA")
    
    width, height = image.size
    is_portrait = height > width

    # --- לוגו ---
    logo = LOGO_IMAGE.copy()
    logo_target_width = int(width * (0.16 if is_portrait else 0.20))
    w, h = logo.size
    ratio = logo_target_width / w
    logo = logo.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    margin = 40
    positions = {
        "top_left": (margin, margin),
        "top_right": (width - logo.width - margin, margin),
        "bottom_left": (margin, height - logo.height - margin),
        "bottom_right": (width - logo.width - margin, height - logo.height - margin)
    }
    pos = positions.get(logo_position, (margin, margin))
    image.paste(logo, pos, logo)

    # --- טקסט (Typography) ---
    draw = ImageDraw.Draw(image)
    
    # גודל גופן גדול שתופס את רוב גובה הפס הלבן
    font_size = int(height * 0.042)  
    font = get_font(font_size)

    lines = []
    if text1 and text1.strip(): lines.append(rtl(text1))
    if text2 and text2.strip(): lines.append(rtl(text2))

    if not lines: # אם אין טקסט, נשמור רק את הלוגו
        image_to_save = image.convert("RGB")
        filename = f"result_{index}_{int(time.time())}.jpg"
        out = os.path.join(OUTPUT_FOLDER, filename)
        image_to_save.save(out, "JPEG", quality=95, optimize=True)
        return "/output/" + filename

    line_data = []
    max_text_width = 0
    ascent, descent = font.getmetrics()
    
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        line_h = ascent + descent 
        line_data.append({'line': line, 'width': line_w, 'height': line_h, 'offset_x': bbox[0]})
        if line_w > max_text_width:
            max_text_width = line_w

    # --- עיצוב הפס הלבן (Background Strip) ---
    line_spacing = 6
    total_text_height = sum(d['height'] for d in line_data) + (line_spacing * (len(lines) - 1))

    padding_x = 60 
    padding_y = 10 # גובה מצומצם למראה "פס"
    
    box_width = max_text_width + padding_x * 2
    box_height = total_text_height + padding_y * 2

    x1 = (width - box_width) // 2
    y1 = height - box_height - 40 # מיקום קרוב לתחתית

    # יצירת השכבה הלבנה
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d_overlay = ImageDraw.Draw(overlay)
    d_overlay.rounded_rectangle(
        [x1, y1, x1 + box_width, y1 + box_height],
        radius=12, 
        fill=(255, 255, 255, 255)
    )

    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)

    # --- ציור הטקסט במרכז מושלם ---
    current_y = y1 + padding_y
    for d in line_data:
        tx = (width - d['width']) // 2
        draw.text((tx - d['offset_x'], current_y), 
                  d['line'], fill=(0, 0, 0, 255), font=font)
        current_y += d['height'] + line_spacing

    image_to_save = image.convert("RGB")
    filename = f"result_{index}_{int(time.time())}.jpg"
    out = os.path.join(OUTPUT_FOLDER, filename)
    image_to_save.save(out, "JPEG", quality=95, optimize=True)

    return "/output/" + filename


# ---------------- UI (The Design you provided) ----------------
HTML = """
<!DOCTYPE html>
<html lang="he">
<head>
<meta charset="UTF-8">
<title>מערכת בצילא דמהימנותא</title>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@100..900&display=swap" rel="stylesheet">
<style>
body { font-family: 'Heebo', Arial, sans-serif; direction: rtl; text-align: center; margin: 0; min-height: 100vh; background: #f6f1e6; color: #1a1a1a; }
.header { background: linear-gradient(135deg, #f7e7b0, #f3e6c2); padding: 14px 24px; border-bottom: 1px solid rgba(212,175,55,0.25); box-shadow: 0 3px 10px rgba(0,0,0,0.05); }
.header h2 { margin: 4px 0 0; font-size: 22px; color: #5a4300; }
button { padding: 10px 16px; cursor: pointer; font-family: 'Heebo', sans-serif; font-weight: 600; border: none; border-radius: 12px; transition: 0.2s; }
button:hover { transform: translateY(-2px); }
.main-btn { background: linear-gradient(135deg, #D4AF37, #f2d572, #b8962e); color: white; box-shadow: 0 8px 25px rgba(212,175,55,0.45); margin-bottom: 20px; }
.refresh-btn { background: white; border: 1px solid #e8d9a8; color: #7a5c00; margin-left: 8px; }
.add-btn { background: #fffdf7; border: 1px solid #e8d9a8; color: #7a5c00; margin-top: 20px; }
.row { display: flex; gap: 10px; align-items: center; background: white; margin: 14px auto; padding: 16px; width: 92%; max-width: 950px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); border: 1px solid #f0e6c8; }
.row input[type="text"] { padding: 9px; border: 1px solid #e8d9a8; border-radius: 10px; flex: 1; background: #fffdf7; }
select { padding: 8px; border-radius: 10px; border: 1px solid #e8d9a8; background: #fffdf7; }
.delete-btn { background: #c62828; color: white; }
#gallery { margin-top: 25px; display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 15px; padding: 20px; }
#gallery div { background: white; padding: 12px; border-radius: 12px; box-shadow: 0 6px 18px rgba(0,0,0,0.08); border-bottom: 3px solid #D4AF37; }
#gallery img { width: 100%; border-radius: 8px; }
#loader { margin-top: 20px; font-weight: 600; color: #7a5c00; font-size: 1.1rem; }
</style>
</head>
<body>

<div class="header">
    <img src="/logo" width="160">
    <h2>מערכת בצילא דמהימנותא</h2>
</div>

<div style="margin-top: 25px;">
    <button class="main-btn" onclick="processAll()">עבד את כל התמונות</button>
    <button class="refresh-btn" onclick="location.reload()">רענן</button>
</div>

<div id="rows"></div>
<button class="add-btn" onclick="addRow()">+ הוסף שורה</button>

<div id="loader"></div>
<div id="gallery"></div>

<script>
function addRow(){
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
        <input type="file" multiple accept="image/*">
        <input type="text" placeholder="שורה 1">
        <input type="text" placeholder="שורה 2">
        <select>
            <option value="top_left">שמאל למעלה</option>
            <option value="top_right">ימין למעלה</option>
            <option value="bottom_left">שמאל למטה</option>
            <option value="bottom_right">ימין למטה</option>
        </select>
        <button class="delete-btn" onclick="this.parentElement.remove()">🗑</button>
    `;
    document.getElementById("rows").appendChild(row);
}

async function sendToServer(rows){
    let formData = new FormData();
    let hasFiles = false;

    rows.forEach(row=>{
        const files = row.querySelector("input[type=file]").files;
        const inputs = row.querySelectorAll("input[type=text]");
        const pos = row.querySelector("select").value;

        for(let i=0;i<files.length;i++){
            formData.append("images", files[i]);
            formData.append("text1", inputs[0].value);
            formData.append("text2", inputs[1].value);
            formData.append("logo_position", pos);
            hasFiles = true;
        }
    });

    if(!hasFiles) { alert("נא לבחור לפחות תמונה אחת"); return; }

    document.getElementById("loader").innerText = "מתחיל עיבוד...";
    document.getElementById("gallery").innerHTML = "";

    let res = await fetch("/process", {method:"POST", body:formData});
    let data = await res.json();
    let jobId = data.job_id;

    let interval = setInterval(async ()=>{
        let r = await fetch("/progress/" + jobId);
        let d = await r.json();

        document.getElementById("loader").innerText = "⏳ מעבד במקצועיות... " + d.progress + "%";

        if(d.finished){
            clearInterval(interval);
            document.getElementById("loader").innerText = "✅ העיבוד הושלם!";

            let g = document.getElementById("gallery");
            g.innerHTML = "";

            d.results.forEach(img=>{
                g.innerHTML += `
                <div>
                    <img src="${img}">
                    <a href="${img}" download style="text-decoration:none; color:#b8962e; font-weight:bold; display:block; margin-top:8px;">⬇️ הורד תמונה</a>
                </div>`;
            });
        }
    }, 800);
}

function processAll(){
    sendToServer(document.querySelectorAll(".row"));
}

window.onload = addRow;
</script>

</body>
</html>
"""

# ---------------- ROUTES ----------------
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

    job_id = str(int(time.time() * 1000))
    jobs[job_id] = {"total": len(files), "done": 0, "results": []}

    for i, file in enumerate(files):
        if file.filename == '': continue
        path = os.path.join(UPLOAD_FOLDER, f"{job_id}_{i}.jpg")
        file.save(path)

        t1 = text1_list[i] if i < len(text1_list) else ""
        t2 = text2_list[i] if i < len(text2_list) else ""
        pos = logo_pos_list[i] if i < len(logo_pos_list) else "top_left"

        result = process_image(path, t1, t2, i, pos)
        jobs[job_id]["results"].append(result)
        jobs[job_id]["done"] += 1
        
        try: os.remove(path)
        except: pass

    return jsonify({"job_id": job_id})

@app.route("/progress/<job_id>")
def progress(job_id):
    job = jobs.get(job_id)
    if not job: return jsonify({"error": "not found"}), 404
    percent = int((job["done"] / job["total"]) * 100) if job["total"] > 0 else 0
    return jsonify({
        "progress": percent, "done": job["done"], "total": job["total"],
        "finished": job["done"] == job["total"],
        "results": job["results"] if job["done"] == job["total"] else []
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
