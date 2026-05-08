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
    try:
        return Image.open(LOGO_PATH).convert("RGBA")
    except:
        # יצירת לוגו ריק זמני למקרה שהקובץ חסר כדי למנוע קריסה
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
        return arabic_reshaper.reshape(text)
    except:
        return text

def process_image(input_path, text1, text2, index, logo_position="top_left"):
    # לוגיקה מהקוד העיקרי (כולל טיפול ב-EXIF)
    image = ImageOps.exif_transpose(Image.open(input_path)).convert("RGBA")
    width, height = image.size
    is_portrait = height > width

    # --- לוגו ---
    logo = LOGO_IMAGE.copy()
    logo_target_width = int(width * (0.16 if is_portrait else 0.20))
    w, h = logo.size
    ratio = logo_target_width / w
    logo = logo.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    margin = 40
    if logo_position == "top_left": pos = (margin, margin)
    elif logo_position == "top_right": pos = (width - logo.width - margin, margin)
    elif logo_position == "bottom_left": pos = (margin, height - logo.height - margin)
    elif logo_position == "bottom_right": pos = (width - logo.width - margin, height - logo.height - margin)
    else: pos = (margin, margin)
    image.paste(logo, pos, logo)

    # --- טקסט ותיבה (דיוק מרכוז מהקוד העיקרי) ---
    draw = ImageDraw.Draw(image)
    font_size = int(height * 0.033)  
    font = get_font(font_size)

    lines = [rtl(text1)]
    if text2 and text2.strip():
        lines.append(rtl(text2))

    # חישוב נתונים לכל שורה למרכוז מדויק (מהקוד העיקרי)
    line_data = []
    max_text_width = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        line_data.append({'line': line, 'width': w, 'height': h, 'offset_x': bbox[0], 'offset_y': bbox[1]})
        if w > max_text_width:
            max_text_width = w

    line_spacing = 10
    total_text_height = sum(d['height'] for d in line_data) + (line_spacing * (len(lines) - 1))

    # ריווח פנימי (Padding)
    padding_x = 42 
    padding_y = 14

    box_width = max_text_width + padding_x * 2
    box_height = total_text_height + padding_y * 2

    # מיקום התיבה - ממורכז למטה
    x1 = (width - box_width) // 2
    y1 = height - box_height - 50 

    # יצירת השכבה של התיבה
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d_overlay = ImageDraw.Draw(overlay)
    d_overlay.rounded_rectangle(
        [x1, y1, x1 + box_width, y1 + box_height],
        radius=18, 
        fill=(255, 255, 255, 255)
    )

    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)

    # מרכוז הטקסט בתוך התיבה הלבנה (הלוגיקה היציבה)
    current_y = y1 + (box_height - total_text_height) // 2
    for d in line_data:
        tx = (width - d['width']) // 2
        draw.text((tx - d['offset_x'], current_y - d['offset_y']), d['line'], fill=(0, 0, 0, 255), font=font)
        current_y += d['height'] + line_spacing

    # שמירה באיכות גבוהה
    image_to_save = image.convert("RGB")
    filename = f"result_{index}_{int(time.time())}.jpg"
    out = os.path.join(OUTPUT_FOLDER, filename)
    image_to_save.save(out, "JPEG", quality=95, optimize=True)

    return "/output/" + filename

# --- ממשק משתמש (מעוצב מהקוד הראשון) ---
HTML = """
<!DOCTYPE html>
<html lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>מערכת בצילא דמהימנותא</title>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@100..900&display=swap" rel="stylesheet">
<style>
    body { font-family: 'Heebo', sans-serif; direction: rtl; text-align: center; margin: 0; background: #f6f1e6; color: #333; }
    .header { background: linear-gradient(135deg, #f7e7b0, #f3e6c2); padding: 25px; border-bottom: 3px solid #d4af23; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    .header h2 { margin: 0; color: #5d4a1b; font-weight: 800; letter-spacing: 1px; }
    
    .container { max-width: 1100px; margin: 0 auto; padding: 20px; }
    
    .row { display: flex; flex-wrap: wrap; gap: 15px; align-items: center; background: white; margin: 15px auto; padding: 20px; border-radius: 15px; box-shadow: 0 6px 20px rgba(0,0,0,0.05); border: 1px solid #eee; transition: transform 0.2s; }
    .row:hover { transform: translateY(-2px); }
    
    input[type="file"] { flex: 1; min-width: 200px; font-size: 14px; }
    input[type="text"] { padding: 12px; border: 1px solid #ddd; border-radius: 8px; flex: 2; min-width: 150px; font-size: 15px; }
    select { padding: 11px; border: 1px solid #ddd; border-radius: 8px; background: white; cursor: pointer; }
    
    .controls { margin: 30px 0; display: flex; justify-content: center; gap: 15px; }
    
    .main-btn { background: #D4AF37; color: white; padding: 14px 40px; border-radius: 50px; font-size: 20px; font-weight: bold; border: none; cursor: pointer; box-shadow: 0 4px 15px rgba(212, 175, 55, 0.4); transition: all 0.3s; }
    .main-btn:hover { background: #b8962d; transform: scale(1.05); }
    
    .add-btn { background: white; color: #D4AF37; border: 2px solid #D4AF37; padding: 10px 25px; border-radius: 50px; cursor: pointer; font-weight: bold; transition: all 0.3s; }
    .add-btn:hover { background: #fdfaf0; }
    
    .remove-btn { background: #ffeded; color: #ff4d4d; border: 1px solid #ffcccc; padding: 8px 12px; border-radius: 8px; cursor: pointer; }
    
    #loader { display: none; font-size: 18px; margin: 20px; color: #D4AF37; font-weight: bold; }
    
    #gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px; padding: 30px 0; }
    .img-card { background: white; padding: 15px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid #eee; }
    .img-card img { width: 100%; border-radius: 8px; margin-bottom: 10px; }
    .download-link { display: inline-block; background: #5d4a1b; color: white; padding: 8px 20px; border-radius: 5px; text-decoration: none; font-size: 14px; margin-top: 5px; }
</style>
</head>
<body>
<div class="header"><h2>מערכת בצילא דמהימנותא</h2></div>
<div class="container">
    <div class="controls">
        <button class="main-btn" onclick="processAll()">עבד תמונות</button>
    </div>
    
    <div id="rows"></div>
    <button class="add-btn" onclick="addRow()">+ הוסף שורה חדשה</button>
    
    <div id="loader">⏳ מעבד את התמונות, נא להמתין...</div>
    <div id="gallery"></div>
</div>

<script>
function addRow(){
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
        <input type="file" multiple accept="image/*">
        <input type="text" placeholder="שורה 1 (למשל: שם האירוע)">
        <input type="text" placeholder="שורה 2 (למשל: תאריך)">
        <select>
            <option value="top_left">לוגו: שמאל למעלה</option>
            <option value="top_right">לוגו: ימין למעלה</option>
            <option value="bottom_left">לוגו: שמאל למטה</option>
            <option value="bottom_right">לוגו: ימין למטה</option>
        </select>
        <button class="remove-btn" onclick="this.parentElement.remove()">🗑</button>
    `;
    document.getElementById("rows").appendChild(row);
}

async function sendToServer(rows){
    if(rows.length === 0) return;
    
    let formData = new FormData();
    let hasFiles = false;
    
    rows.forEach(row=>{
        const files = row.querySelector("input[type=file]").files;
        const inputs = row.querySelectorAll("input[type=text]");
        const pos = row.querySelector("select").value;
        
        for(let i=0; i<files.length; i++){
            formData.append("images", files[i]);
            formData.append("text1", inputs[0].value);
            formData.append("text2", inputs[1].value);
            formData.append("logo_position", pos);
            hasFiles = true;
        }
    });
    
    if(!hasFiles) { alert("אנא בחר לפחות תמונה אחת"); return; }

    document.getElementById("loader").style.display = "block";
    document.getElementById("gallery").innerHTML = "";

    try {
        let res = await fetch("/process", {method:"POST", body:formData});
        let data = await res.json();
        
        data.images.forEach(img=>{
            const card = document.createElement("div");
            card.className = "img-card";
            card.innerHTML = `<img src="${img}"><br><a href="${img}" download class="download-link">הורד תמונה</a>`;
            document.getElementById("gallery").appendChild(card);
        });
    } catch(e) {
        alert("אירעה שגיאה בעיבוד");
    } finally {
        document.getElementById("loader").style.display = "none";
    }
}

function processAll(){ sendToServer(document.querySelectorAll(".row")); }
window.onload = addRow;
</script>
</body>
</html>
"""

# --- Routes (מהקוד העיקרי) ---
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
        if file.filename == '': continue
        path = os.path.join(UPLOAD_FOLDER, f"{run_id}_{i}_{file.filename}")
        file.save(path)
        
        t1 = text1_list[i] if i < len(text1_list) else ""
        t2 = text2_list[i] if i < len(text2_list) else ""
        pos = logo_pos_list[i] if i < len(logo_pos_list) else "top_left"
        
        result = process_image(path, t1, t2, i, pos)
        results.append(result)
        
    return jsonify({"images": results, "run_id": run_id})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
