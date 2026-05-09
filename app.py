import threading
import queue
import os
import time
import gc
import arabic_reshaper
from flask import Flask, request, render_template_string, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageOps

app = Flask(__name__)

# הגדרות נתיבים
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
LOGO_PATH = "logo.png"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ---------------- CONFIG & STABILITY ----------------
MAX_CONCURRENT = 2  # מקסימום 2 תמונות מעובדות בו-זמנית ב-RAM
processing_semaphore = threading.Semaphore(MAX_CONCURRENT)
task_queue = queue.Queue()
jobs = {}

def load_logo():
    try:
        img = Image.open(LOGO_PATH).convert("RGBA")
        img.load()
        return img
    except:
        return Image.new("RGBA", (100, 100), (255, 255, 255, 0))

LOGO_IMAGE = load_logo()

def get_font(size):
    fonts_to_try = ["Assistant-Bold.ttf", "Heebo-Bold.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"]
    for f in fonts_to_try:
        try: return ImageFont.truetype(f, size)
        except: continue
    return ImageFont.load_default()

def rtl(text):
    try: return arabic_reshaper.reshape(text)
    except: return text

# ---------------- IMAGE PROCESSING (STABLE) ----------------
def process_image(input_path, text1, text2, index, logo_position="top_left"):
    image = None
    draw = None
    try:
        # הגבלת מקביליות ברמת הפונקציה
        with processing_semaphore:
            with Image.open(input_path) as raw_img:
                image = ImageOps.exif_transpose(raw_img).convert("RGB")
                # הקטנה מוקדמת - קריטי ליציבות ב-70 תמונות
                image.thumbnail((1400, 1400), Image.LANCZOS)
            
            width, height = image.size
            is_portrait = height > width

            # עיבוד לוגו
            logo = LOGO_IMAGE.copy()
            logo_w = int(width * (0.16 if is_portrait else 0.20))
            ratio = logo_w / logo.size[0]
            logo = logo.resize((logo_w, int(logo.size[1] * ratio)), Image.LANCZOS)

            margin = 40
            pos_map = {
                "top_left": (margin, margin),
                "top_right": (width - logo.width - margin, margin),
                "bottom_left": (margin, height - logo.height - margin),
                "bottom_right": (width - logo.width - margin, height - logo.height - margin)
            }
            image.paste(logo, pos_map.get(logo_position, (margin, margin)), logo)
            logo.close()

            # עיבוד טקסט (ציור ישיר על RGB)
            draw = ImageDraw.Draw(image)
            font_size = int(height * 0.042)
            font = get_font(font_size)
            lines = [rtl(t) for t in [text1, text2] if t and t.strip()]

            if lines:
                line_data = []
                max_w = 0
                ascent, descent = font.getmetrics()
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    w = bbox[2] - bbox[0]
                    line_data.append({'line': line, 'w': w, 'h': ascent + descent, 'offset_x': bbox[0]})
                    max_w = max(max_w, w)

                box_w, box_h = max_w + 120, sum(d['h'] for d in line_data) + 20
                x1, y1 = (width - box_w) // 2, height - box_h - 40
                draw.rounded_rectangle([x1, y1, x1 + box_w, y1 + box_h], radius=12, fill=(255, 255, 255))
                
                curr_y = y1 + 10
                for d in line_data:
                    draw.text(((width - d['w']) // 2 - d['offset_x'], curr_y), d['line'], fill=(0, 0, 0), font=font)
                    curr_y += d['h'] + 6

            filename = f"res_{int(time.time())}_{index}.jpg"
            out_path = os.path.join(OUTPUT_FOLDER, filename)
            # שמירה באיכות אופטימלית ללא עומס
            image.save(out_path, "JPEG", quality=85)
            return "/output/" + filename

    finally:
        # ניקוי אגרסיבי של זיכרון
        if image: image.close()
        del image
        del draw
        gc.collect()

# ---------------- WORKER (LINEAR & STABLE) ----------------
def background_worker():
    while True:
        try:
            # Timeout למניעת תקיעה
            task = task_queue.get(timeout=3)
            if task is None: break
            
            job_id, paths, texts1, texts2, positions = task
            
            for i, path in enumerate(paths):
                try:
                    res = process_image(path, texts1[i], texts2[i], i, positions[i])
                    if job_id in jobs:
                        jobs[job_id]["results"].append(res)
                        jobs[job_id]["done"] += 1
                except Exception as e:
                    print(f"Error: {e}")
                    if job_id in jobs: jobs[job_id]["done"] += 1
                finally:
                    if os.path.exists(path): os.remove(path)
            
            task_queue.task_done()
        except queue.Empty:
            continue

threading.Thread(target=background_worker, daemon=True).start()

# ---------------- ROUTES ----------------
@app.route("/")
def home(): return render_template_string(HTML)

@app.route("/logo")
def logo(): return send_file(LOGO_PATH)

@app.route("/output/<filename>")
def serve_output(filename): return send_file(os.path.join(OUTPUT_FOLDER, filename))

@app.route("/process", methods=["POST"])
def process():
    # מניעת הצפה של ה-Queue
    if task_queue.qsize() > 200:
        time.sleep(1)

    files = request.files.getlist("images")
    t1, t2, pos = request.form.getlist("text1"), request.form.getlist("text2"), request.form.getlist("logo_position")
    
    job_id = str(int(time.time() * 1000))
    paths = []
    for i, f in enumerate(files):
        p = os.path.join(UPLOAD_FOLDER, f"t_{job_id}_{i}.jpg")
        f.save(p)
        paths.append(p)

    jobs[job_id] = {"total": len(files), "done": 0, "results": []}
    task_queue.put((job_id, paths, t1, t2, pos))

    return jsonify({"job_id": job_id})

@app.route("/progress/<job_id>")
def progress(job_id):
    job = jobs.get(job_id)
    if not job: return jsonify({"error": "N/A"}), 404
    
    finished = job["done"] >= job["total"]
    data = {
        "progress": int((job["done"]/job["total"])*100),
        "finished": finished,
        "results": job["results"],
        "done": job["done"],
        "total": job["total"]
    }
    
    if finished:
        # ניקוי הדרגתי של Job מהזיכרון
        def cleanup(jid):
            time.sleep(180)
            jobs.pop(jid, None)
        threading.Thread(target=cleanup, args=(job_id,), daemon=True).start()
        
    return jsonify(data)

# ---------------- UI (RESTORED) ----------------
HTML = """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>מערכת בצילא דמהימנותא</title>
    <link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Heebo', sans-serif; background: #f6f1e6; margin: 0; text-align: center; }
        .header { background: linear-gradient(135deg, #f7e7b0, #f3e6c2); padding: 20px; border-bottom: 2px solid #D4AF37; }
        .row { display: flex; gap: 10px; align-items: center; background: white; margin: 15px auto; padding: 15px; width: 90%; max-width: 1000px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        input[type="text"] { padding: 8px; border: 1px solid #ddd; border-radius: 6px; flex: 1; }
        .main-btn { background: #D4AF37; color: white; padding: 12px 30px; border: none; border-radius: 8px; cursor: pointer; font-size: 1.1rem; margin: 20px; }
        #gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; padding: 20px; }
        .card { background: white; padding: 10px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .card img { width: 100%; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="header"><img src="/logo" width="150"><h2>מערכת עיבוד יציבה</h2></div>
    <button class="main-btn" onclick="processAll()">🚀 עבד את כל התמונות</button>
    <button onclick="location.reload()">🔄 רענן</button>
    <div id="rows"></div>
    <button onclick="addRow()">+ הוסף שורה</button>
    <div id="loader" style="margin:20px; font-weight:bold;"></div>
    <div id="gallery"></div>

    <script>
    function addRow(){
        const d = document.createElement("div"); d.className = "row";
        d.innerHTML = `<input type="file" multiple accept="image/*"><input type="text" placeholder="שורה 1"><input type="text" placeholder="שורה 2">
        <select><option value="top_left">שמאל למעלה</option><option value="top_right">ימין למעלה</option><option value="bottom_left">שמאל למטה</option><option value="bottom_right">ימין למטה</option></select>
        <button onclick="this.parentElement.remove()">🗑</button>`;
        document.getElementById("rows").appendChild(d);
    }
    async function processAll(){
        let fd = new FormData();
        let rows = document.querySelectorAll(".row");
        rows.forEach(r => {
            let files = r.querySelector("input[type=file]").files;
            let t1 = r.querySelectorAll("input[type=text]")[0].value;
            let t2 = r.querySelectorAll("input[type=text]")[1].value;
            let pos = r.querySelector("select").value;
            for(let f of files){
                fd.append("images", f); fd.append("text1", t1); fd.append("text2", t2); fd.append("logo_position", pos);
            }
        });
        document.getElementById("loader").innerText = "מעלה...";
        let res = await fetch("/process", {method:"POST", body:fd});
        let {job_id} = await res.json();
        let intv = setInterval(async () => {
            let r = await fetch("/progress/"+job_id);
            let d = await r.json();
            document.getElementById("loader").innerText = `מעבד: ${d.done}/${d.total} (${d.progress}%)`;
            if(d.finished){
                clearInterval(intv);
                document.getElementById("loader").innerText = "הושלם!";
                d.results.forEach(u => document.getElementById("gallery").innerHTML += `<div class="card"><img src="${u}"><a href="${u}" download>הורד</a></div>`);
            }
        }, 1000);
    }
    window.onload = addRow;
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
