import threading
from flask import Flask, request, render_template_string, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageOps
import os
import time
import arabic_reshaper
import gc  # ייבוא Garbage Collector

app = Flask(__name__)

# הגדרות נתיבים
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
LOGO_PATH = "logo.png"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ---------------- JOB SYSTEM ----------------
jobs = {}

def load_logo():
    try:
        # טעינה ב-RGBA רק ללוגו כי הוא זקוק לשקיפות
        img = Image.open(LOGO_PATH).convert("RGBA")
        img.load() # טעינה פיזית לזיכרון כעת
        return img
    except:
        return Image.new("RGBA", (100, 100), (255, 255, 255, 0))

LOGO_IMAGE = load_logo()

def get_font(size):
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

# ---------------- IMAGE PROCESSING LOGIC (STABLE VERSION) ----------------
def process_image(input_path, text1, text2, index, logo_position="top_left"):
    image = None
    try:
        # 1. טעינה חכמה - הקטנה מיד בפתיחה לחסכון בזיכרון
        with Image.open(input_path) as raw_img:
            # תיקון סיבוב תמונה לפי EXIF
            image = ImageOps.exif_transpose(raw_img)
            # המרה ל-RGB בלבד (חוסך ערוץ שקיפות כבד)
            image = image.convert("RGB")
            # 2. שינוי גודל מיידי למקסימום 1600px (יחס השמירה נשמר)
            image.thumbnail((1600, 1600), Image.LANCZOS)
        
        width, height = image.size
        is_portrait = height > width

        # --- לוגו ---
        # שינוי גודל הלוגו יחסית לתמונה המוקטנת
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
        
        # הדבקה ישירה על ה-RGB (משתמש בערוץ ה-Alpha של הלוגו כמסיכה)
        image.paste(logo, pos, logo)
        logo.close() # שחרור זיכרון הלוגו הזמני

        # --- טקסט ---
        draw = ImageDraw.Draw(image)
        font_size = int(height * 0.042)
        font = get_font(font_size)

        lines = [rtl(t) for t in [text1, text2] if t and t.strip()]

        if lines:
            line_data = []
            max_text_width = 0
            ascent, descent = font.getmetrics()
            
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_w = bbox[2] - bbox[0]
                line_h = ascent + descent 
                line_data.append({'line': line, 'width': line_w, 'height': line_h, 'offset_x': bbox[0]})
                max_text_width = max(max_text_width, line_w)

            # חישוב הפס הלבן
            line_spacing = 6
            total_text_height = sum(d['height'] for d in line_data) + (line_spacing * (len(lines) - 1))
            padding_x, padding_y = 60, 10 
            box_width, box_height = max_text_width + padding_x * 2, total_text_height + padding_y * 2
            x1, y1 = (width - box_width) // 2, height - box_height - 40 

            # 3. ציור ישיר ללא alpha_composite (שימוש ב-rounded_rectangle על התמונה המקורית)
            draw.rounded_rectangle(
                [x1, y1, x1 + box_width, y1 + box_height], 
                radius=12, 
                fill=(255, 255, 255)
            )

            # ציור הטקסט
            current_y = y1 + padding_y
            for d in line_data:
                tx = (width - d['width']) // 2
                draw.text((tx - d['offset_x'], current_y), d['line'], fill=(0, 0, 0), font=font)
                current_y += d['height'] + line_spacing

        # 4. שמירה אופטימלית ללא עומס (איכות 85 היא איזון מעולה)
        filename = f"result_{index}_{int(time.time())}.jpg"
        out_path = os.path.join(OUTPUT_FOLDER, filename)
        image.save(out_path, "JPEG", quality=85)
        
        return "/output/" + filename

    finally:
        # 5. ניקוי אגרסיבי של אובייקטים
        if image:
            image.close()
            del image
        del draw
        gc.collect() # שחרור זיכרון למערכת ההפעלה

# ---------------- BACKGROUND WORKER (ENHANCED STABILITY) ----------------
def background_worker(job_id, saved_paths, text1_list, text2_list, logo_pos_list):
    for i, path in enumerate(saved_paths):
        try:
            # עיבוד לינארי - תמונה אחת בכל רגע נתון בזיכרון
            t1 = text1_list[i] if i < len(text1_list) else ""
            t2 = text2_list[i] if i < len(text2_list) else ""
            pos = logo_pos_list[i] if i < len(logo_pos_list) else "top_left"
            
            result_url = process_image(path, t1, t2, i, pos)
            
            if job_id in jobs:
                jobs[job_id]["results"].append(result_url)
                jobs[job_id]["done"] += 1
        except Exception as e:
            print(f"CRITICAL ERROR processing {path}: {e}")
            # חובה לעדכן התקדמות גם בשגיאה כדי שה-Frontend לא יתקע
            if job_id in jobs:
                jobs[job_id]["done"] += 1
        finally:
            # 6. מחיקת קובץ זמני מיידית בכל מצב
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

# ---------------- ROUTES (STABLE) ----------------
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

    if not files or files[0].filename == '':
        return jsonify({"error": "No files"}), 400

    job_id = str(int(time.time() * 1000))
    saved_paths = []
    
    # שמירה זמנית לדיסק (לא לזיכרון)
    for i, file in enumerate(files):
        path = os.path.join(UPLOAD_FOLDER, f"temp_{job_id}_{i}.jpg")
        file.save(path)
        saved_paths.append(path)

    jobs[job_id] = {"total": len(files), "done": 0, "results": []}

    # הרצה ב-Thread נפרד
    thread = threading.Thread(target=background_worker, args=(job_id, saved_paths, text1_list, text2_list, logo_pos_list))
    thread.start()

    return jsonify({"job_id": job_id})

@app.route("/progress/<job_id>")
def get_progress(job_id):
    job = jobs.get(job_id)
    if not job: return jsonify({"error": "Not found"}), 404
    
    done = job["done"]
    total = job["total"]
    percent = int((done / total) * 100) if total > 0 else 0
    finished = (done >= total)
    
    if finished:
        # שליחת תוצאות וניקוי ה-Job מהזיכרון לאחר שליחה
        results = job["results"]
        # פונקציית ניקוי מושהית למניעת מחיקה לפני שה-JS קורא
        def delayed_cleanup():
            time.sleep(60)
            jobs.pop(job_id, None)
        threading.Thread(target=delayed_cleanup, daemon=True).start()
        
        return jsonify({"progress": 100, "done": done, "total": total, "finished": True, "results": results})
    
    return jsonify({"progress": percent, "done": done, "total": total, "finished": False, "results": []})

# ---------------- UI (ללא שינוי) ----------------
HTML = """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<title>מערכת בצילא דמהימנותא</title>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@100..900&display=swap" rel="stylesheet">
<style>
body { font-family: 'Heebo', Arial, sans-serif; text-align: center; margin: 0; background: #f6f1e6; color: #1a1a1a; }
.header { background: linear-gradient(135deg, #f7e7b0, #f3e6c2); padding: 14px 24px; border-bottom: 1px solid rgba(212,175,55,0.25); box-shadow: 0 3px 10px rgba(0,0,0,0.05); }
.header h2 { margin: 4px 0 0; font-size: 22px; color: #5a4300; }
button { padding: 10px 16px; cursor: pointer; font-weight: 600; border: none; border-radius: 12px; transition: 0.2s; }
.main-btn { background: linear-gradient(135deg, #D4AF37, #f2d572, #b8962e); color: white; box-shadow: 0 8px 25px rgba(212,175,55,0.45); margin: 20px; }
.row { display: flex; gap: 10px; align-items: center; background: white; margin: 14px auto; padding: 16px; width: 92%; max-width: 950px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
.row input[type="text"] { padding: 9px; border: 1px solid #e8d9a8; border-radius: 10px; flex: 1; }
#gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; padding: 20px; }
#gallery div { background: white; padding: 10px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
#gallery img { width: 100%; border-radius: 8px; }
</style>
</head>
<body>
<div class="header"><img src="/logo" width="160"><h2>מערכת בצילא דמהימנותא</h2></div>
<button class="main-btn" onclick="processAll()">עבד את כל התמונות</button>
<div id="rows"></div>
<button onclick="addRow()">+ הוסף שורה</button>
<div id="loader" style="margin: 20px; font-weight: bold;"></div>
<div id="gallery"></div>

<script>
function addRow(){
    const div = document.createElement("div");
    div.className = "row";
    div.innerHTML = `<input type="file" multiple accept="image/*"><input type="text" placeholder="שורה 1"><input type="text" placeholder="שורה 2"><select><option value="top_left">שמאל למעלה</option><option value="top_right">ימין למעלה</option><option value="bottom_left">שמאל למטה</option><option value="bottom_right">ימין למטה</option></select><button style="background:#ff4444; color:white" onclick="this.parentElement.remove()">🗑</button>`;
    document.getElementById("rows").appendChild(div);
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
    if(!hasFiles) return alert("בחר תמונות");
    document.getElementById("loader").innerText = "מעלה תמונות...";
    let res = await fetch("/process", {method:"POST", body:formData});
    let {job_id} = await res.json();
    let interval = setInterval(async ()=>{
        let r = await fetch("/progress/" + job_id);
        let d = await r.json();
        document.getElementById("loader").innerText = `מעבד: ${d.done} / ${d.total} (${d.progress}%)`;
        if(d.finished){
            clearInterval(interval);
            document.getElementById("loader").innerText = "הושלם!";
            d.results.forEach(img=>{
                document.getElementById("gallery").innerHTML += `<div><img src="${img}"><a href="${img}" download>הורד</a></div>`;
            });
        }
    }, 1000);
}
function processAll(){ sendToServer(document.querySelectorAll(".row")); }
window.onload = addRow;
</script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
