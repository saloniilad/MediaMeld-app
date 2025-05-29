from flask import Flask, render_template, request, send_file, redirect, url_for
import uuid
from werkzeug.utils import secure_filename
import os
from PyPDF2 import PdfMerger
from generate_merge import merge_pdfs


UPLOAD_FOLDER = 'user_uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
 

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/createpdf", methods=["GET", "POST"])
def create_pdf():
    myid = str(uuid.uuid4())
    PDF_UPLOAD_ROOT = "pdf_data"
    if request.method == "POST":
        rec_id = request.form.get("uuid")
        desc = request.form.get("text", "")
        input_files = []

        # 🟢 Store inside 'user_uploads/pdf/<uuid>/'
        user_folder = os.path.join(PDF_UPLOAD_ROOT, rec_id)
        os.makedirs(user_folder, exist_ok=True)

        for key in request.files:
            file = request.files[key]
            if file and file.filename.endswith('.pdf'):
                filename = secure_filename(file.filename)
                filepath = os.path.join(user_folder, filename)
                file.save(filepath)
                input_files.append(filepath)

        with open(os.path.join(user_folder, "desc.txt"), "w") as f:
            f.write(desc)

        if input_files:
            merged_path = os.path.join(user_folder, "merged.pdf")
            merge_pdfs(input_files, merged_path)
            return send_file(merged_path, as_attachment=True)

    return render_template("createpdf.html", myid=myid)


@app.route("/create", methods=["GET", "POST"])
def create():
    myid = uuid.uuid1()
    if request.method == "POST":
        print(request.files.keys())
        rec_id = request.form.get("uuid")
        desc = request.form.get("text")
        input_files = []
        for key, value in request.files.items():
            print(key, value)
            # Upload the file
            file = request.files[key]
            if file:
                filename = secure_filename(file.filename)
                if(not(os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], rec_id)))):
                    os.mkdir(os.path.join(app.config['UPLOAD_FOLDER'], rec_id))
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], rec_id,  filename))
                input_files.append(file.filename)
                print(file.filename)
            # Capture the description and save it to a file
            with open(os.path.join(app.config['UPLOAD_FOLDER'], rec_id, "desc.txt"), "w") as f:
                f.write(desc)
        for fl in input_files:
            with open(os.path.join(app.config['UPLOAD_FOLDER'], rec_id,  "input.txt"), "a") as f:
                f.write(f"file '{fl}'\nduration 1\n")


    return render_template("create.html", myid=myid)

@app.route("/gallery")
def gallery():
    reels = os.listdir("static/reels")
    print(reels)
    return render_template("gallery.html", reels=reels)

app.run(debug=True)