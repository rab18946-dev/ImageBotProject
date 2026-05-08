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
    image = ImageOps.exif_transpose(Image.open(input_path)).convert("RGBA")
    width, height = image.size
    is_portrait = height > width

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

    draw = ImageDraw.Draw(image)
    font_size = int(height * 0.033)  
    font = get_font(font_size)

    lines = [rtl(text1)]
    if text2 and text2.strip():
        lines.append(rtl(text2))

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

    padding_x = 42 
    padding_y = 14
    box_width = max_text_width + padding_x * 2
    box_height = total_text_height + padding_y * 2

    x1 = (width - box_width) // 2
    y1 = height - box_height - 50 

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d_overlay = ImageDraw.Draw(overlay)
    d_overlay.rounded_rectangle(
        [x1, y1, x1 + box_width, y1 + box_height],
        radius=18, 
        fill=(255, 255, 255, 255)
    )

    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)

    current_y = y1 + (box_height - total_text_height) // 2
    for d in line_data:
        tx = (width - d['width']) // 2
        draw.text((tx - d['offset_x'], current_y - d['offset_y']), d['line'], fill=(0, 0, 0, 255), font=font)
        current_y += d['height'] + line_spacing

    image_to_save = image.convert("RGB")
    filename = f"result_{index}_{int(time.time())}.jpg"
    out = os.path.join(OUTPUT_FOLDER, filename)
    image_to_save.save(out, "JPEG", quality=95, optimize=True)

    return "/output/" + filename

# --- UI (HTML/CSS) From the second code provided ---
HTML = """
<!DOCTYPE html>
<html lang="he">
<head>
<meta charset="UTF-8">
<title>מערכת בצילא דמהימנותא</title>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@100..900&display=swap" rel="stylesheet">
<style>
body {
    font-family: 'Heebo', Arial, sans-serif;
    direction: rtl;
    text-align: center;
    margin: 0;
    min-height: 100vh;
    background: #f6f1e6;
    color: #1a1a1a;
}
.header {
    background: linear-gradient(135deg, #f7e7b0, #f3e6c2);
    padding: 14px 24px;
    border-bottom: 1px solid rgba(212,175,55,0.25);
    box-shadow: 0 3px 10px rgba(0,0,0,0.05);
}
.header h2 {
    margin: 4px 0 0;
    font-size: 22px;
    color: #5a4300;
}
button {
    padding: 10px 16px;
    cursor: pointer;
    font-family: 'Heebo', sans-serif;
    font-weight: 600;
    border: none;
    border-radius: 12px;
    transition: 0.2s;
}
button:hover { transform: translateY(-2px); }
.main-btn {
    background: linear-gradient(135deg, #D4AF37, #f2d572, #b8962e);
    color: white;
    box-shadow: 0 8px 25px rgba(212,175,55,0.45);
}
.refresh-btn {
    background: white;
    border: 1px solid #e8d9a8;
    color: #7a5c00;
    margin-left: 8px;
}
.add-btn {
    background: #fffdf7;
    border: 1px solid #e8d9a8;
    color: #7a5c00;
    margin-top: 20px;
}
.row {
    display: flex;
    gap: 10px;
    align-items: center;
    background: white;
    margin: 14px auto;
    padding: 16px;
    width: 92%;
    max-width: 950px;
    border-radius: 16px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.08);
    border: 1px solid #f0e6c8;
}
.row input[type="text"] {
    padding: 9px;
    border: 1px solid #e8d9a8;
    border-radius: 10px;
    flex: 1;
    background: #fffdf7;
}
.row input[type="file"] {
    flex: 1;
}
select {
    padding: 8px;
    border-radius: 10px;
    border: 1px solid #e8d9a8;
    background: #fffdf7;
}
.delete-btn {
    background: #c62828;
    color: white;
}
#gallery {
    margin-top: 25px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 15px;
    padding: 20px;
}
#gallery div {
    background: white;
    padding: 12px;
    border-radius: 12px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.08);
    border-bottom: 3px solid #D4AF37;
}
#gallery img {
    width: 100%;
    border-radius: 8px;
    margin-bottom: 8px;
}
#gallery a {
    text-decoration: none;
    color: #b8962e;
    font-weight: bold;
    font-size: 14px;
}
#loader {
    margin-top: 20px;
    font-weight: 600;
    color: #7a5c00;
}
</style>
</head>
<body>

<div class="header">
    <img src="/logo" width="160">
    <h2>מערכת בצילא דמהימנותא</h2>
</div>

<div style="margin-top: 20px;">
    <button class="main-btn" onclick="processAll()">עבד את כל התמונות</button>
    <button class="refresh-btn" onclick="location.reload()">רענן</button>
</div>

<div id="rows"></div>
<button class="add-btn" onclick="addRow()">+ הוסף שורת תמונות</button>

<div id="loader" style="display:none;">⏳ מעבד תמונות במקצועיות, נא להמתין...</div>
<div id="gallery"></div>

<script>
let currentRunId = null;

function addRow(){
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
        <input type="file" multiple accept="image/*">
        <input type="text" placeholder="שורה 1 (למשל: שם האירוע)">
        <input type="text" placeholder="שורה 2 (למשל: תאריך)">
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

        for(let i=0; i<files.length; i++){
            formData.append("images", files[i]);
            formData.append("text1", inputs[0].value);
            formData.append("text2", inputs[1].value);
            formData.append("logo_position", pos);
            hasFiles = true;
        }
    });

    if(!hasFiles) { alert("נא לבחור לפחות תמונה אחת"); return; }

    document.getElementById("loader").style.display = "block";

    try {
        let res = await fetch("/process", {method:"POST", body:formData});
        let data = await res.json();
        
        const gallery = document.getElementById("gallery");
        if(currentRunId !== data.run_id){
            gallery.innerHTML = "";
            currentRunId = data.run_id;
        }

        data.images.forEach(img=>{
            gallery.innerHTML += `
                <div>
                    <img src="${img}">
                    <a href="${img}" download>⬇️ הורד תמונה</a>
                </div>`;
        });
    } catch(e) {
        alert("שגיאה בעיבוד");
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
