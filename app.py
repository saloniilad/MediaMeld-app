from flask import Flask, render_template, request, send_file, redirect, url_for
import uuid
from werkzeug.utils import secure_filename
import os
from PyPDF2 import PdfMerger
from generate_merge import merge_pdfs
import threading
import time
from text_to_audio import text_to_speech_file
import subprocess

UPLOAD_FOLDER = 'user_uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Background processing function
def process_queue():
    """Background function to process uploaded files and generate reels"""
    while True:
        try:
            print("Processing queue...")
            
            # Ensure directories exist
            os.makedirs("user_uploads", exist_ok=True)
            os.makedirs("static/reels", exist_ok=True)
            
            # Read done folders
            done_file = "done.txt"
            if not os.path.exists(done_file):
                with open(done_file, "w") as f:
                    pass
            
            with open(done_file, "r") as f:
                done_folders = [line.strip() for line in f.readlines()]
            
            # Check for new folders
            if os.path.exists("user_uploads"):
                folders = os.listdir("user_uploads")
                for folder in folders:
                    folder_path = os.path.join("user_uploads", folder)
                    if os.path.isdir(folder_path) and folder not in done_folders:
                        try:
                            print(f"Processing folder: {folder}")
                            
                            # Check if required files exist
                            desc_file = os.path.join(folder_path, "desc.txt")
                            input_file = os.path.join(folder_path, "input.txt")
                            
                            if os.path.exists(desc_file) and os.path.exists(input_file):
                                # Generate audio from description
                                text_to_audio(folder)
                                
                                # Create reel
                                create_reel(folder)
                                
                                # Mark as done
                                with open(done_file, "a") as f:
                                    f.write(folder + "\n")
                                
                                print(f"Successfully processed: {folder}")
                            else:
                                print(f"Missing required files for {folder}")
                                
                        except Exception as e:
                            print(f"Error processing {folder}: {e}")
            
        except Exception as e:
            print(f"Error in process_queue: {e}")
        
        time.sleep(10)  # Check every 10 seconds

def text_to_audio(folder):
    """Generate audio from text description"""
    try:
        desc_file = os.path.join("user_uploads", folder, "desc.txt")
        with open(desc_file, "r") as f:
            text = f.read()
        
        print(f"Generating audio for: {folder}")
        text_to_speech_file(text, folder)
        
    except Exception as e:
        print(f"Error in text_to_audio for {folder}: {e}")

def create_reel(folder):
    """Create video reel from images and audio"""
    try:
        input_file = os.path.join("user_uploads", folder, "input.txt")
        audio_file = os.path.join("user_uploads", folder, "audio.mp3")
        output_file = os.path.join("static", "reels", f"{folder}.mp4")
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        if os.path.exists(audio_file):
            command = f'''ffmpeg -f concat -safe 0 -i {input_file} -i {audio_file} -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black" -c:v libx264 -c:a aac -shortest -r 30 -pix_fmt yuv420p {output_file}'''
        else:
            # Create reel without audio if audio file doesn't exist
            command = f'''ffmpeg -f concat -safe 0 -i {input_file} -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black" -c:v libx264 -shortest -r 30 -pix_fmt yuv420p {output_file}'''
        
        subprocess.run(command, shell=True, check=True)
        print(f"Successfully created reel: {folder}")
        
    except subprocess.CalledProcessError as e:
        print(f"Error creating reel for {folder}: {e}")
    except Exception as e:
        print(f"Unexpected error creating reel for {folder}: {e}")

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

        # Store inside 'pdf_data/<uuid>/'
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
        desc = request.form.get("text", "")
        input_files = []
        
        # Create user folder
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], rec_id)
        os.makedirs(user_folder, exist_ok=True)
        
        # Process uploaded files
        for key in request.files:
            file = request.files[key]
            if file and file.filename:
                filename = secure_filename(file.filename)
                filepath = os.path.join(user_folder, filename)
                file.save(filepath)
                input_files.append(filename)
                print(f"Saved file: {filename}")
        
        # Save description
        if desc:
            with open(os.path.join(user_folder, "desc.txt"), "w") as f:
                f.write(desc)
        
        # Create input.txt for ffmpeg
        if input_files:
            with open(os.path.join(user_folder, "input.txt"), "w") as f:
                for filename in input_files:
                    abs_path = os.path.abspath(os.path.join(user_folder, filename))
                    f.write(f"file '{abs_path}'\nduration 1\n")
            
            # Process immediately instead of waiting for background thread
            try:
                # Generate audio
                text_to_audio(str(rec_id))
                # Create reel
                create_reel(str(rec_id))
                print(f"Immediately processed reel for {rec_id}")
            except Exception as e:
                print(f"Error processing reel immediately: {e}")
        
        return redirect(url_for('gallery'))

    return render_template("create.html", myid=myid)

@app.route("/gallery")
def gallery():
    reels_path = os.path.join('static', 'reels')
    os.makedirs(reels_path, exist_ok=True)
    
    try:
        reels = [f for f in os.listdir(reels_path) if f.endswith(".mp4")]
        reels.sort(reverse=True)  # Show newest first
    except FileNotFoundError:
        reels = []
    
    return render_template("gallery.html", reels=reels)

@app.route("/status")
def status():
    """Debug endpoint to check processing status"""
    status_info = {
        "uploads_folder_exists": os.path.exists("user_uploads"),
        "reels_folder_exists": os.path.exists("static/reels"),
        "done_file_exists": os.path.exists("done.txt")
    }
    
    if os.path.exists("user_uploads"):
        status_info["upload_folders"] = os.listdir("user_uploads")
    
    if os.path.exists("static/reels"):
        status_info["reels"] = os.listdir("static/reels")
    
    if os.path.exists("done.txt"):
        with open("done.txt", "r") as f:
            status_info["processed_folders"] = [line.strip() for line in f.readlines()]
    
    return status_info

if __name__ == "__main__":
    # Start background processing thread
    background_thread = threading.Thread(target=process_queue, daemon=True)
    background_thread.start()
    print("Background processing thread started")
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)