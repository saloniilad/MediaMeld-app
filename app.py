from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify
import uuid
from werkzeug.utils import secure_filename
import os
from PyPDF2 import PdfMerger
from generate_merge import merge_pdfs
import threading
import time
from text_to_audio import text_to_speech_file
import subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_FOLDER = 'user_uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def text_to_audio(folder):
    """Generate audio from text description"""
    try:
        desc_file = os.path.join("user_uploads", folder, "desc.txt")
        logger.info(f"Reading description from: {desc_file}")
        
        if not os.path.exists(desc_file):
            logger.error(f"Description file not found: {desc_file}")
            return False
            
        with open(desc_file, "r") as f:
            text = f.read()
        
        logger.info(f"Generating audio for folder: {folder}")
        logger.info(f"Text content: {text[:100]}...")  # Log first 100 chars
        
        text_to_speech_file(text, folder)
        
        # Verify audio file was created
        audio_file = os.path.join("user_uploads", folder, "audio.mp3")
        if os.path.exists(audio_file):
            logger.info(f"Audio file successfully created: {audio_file}")
            return True
        else:
            logger.error(f"Audio file was not created: {audio_file}")
            return False
        
    except Exception as e:
        logger.error(f"Error in text_to_audio for {folder}: {e}")
        return False

def create_reel(folder):
    """Create video reel from images and audio"""
    try:
        input_file = os.path.join("user_uploads", folder, "input.txt")
        audio_file = os.path.join("user_uploads", folder, "audio.mp3")
        output_file = os.path.join("user_uploads", folder, f"{folder}.mp4")  # Save in user folder instead of static/reels
        
        logger.info(f"Creating reel for folder: {folder}")
        logger.info(f"Input file: {input_file}")
        logger.info(f"Audio file: {audio_file}")
        logger.info(f"Output file: {output_file}")
        
        # Check if input file exists
        if not os.path.exists(input_file):
            logger.error(f"Input file not found: {input_file}")
            return False
        
        # Read and log input file contents
        with open(input_file, 'r') as f:
            input_content = f.read()
            logger.info(f"Input file content:\n{input_content}")
        
        # Check ffmpeg availability
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            logger.info("FFmpeg is available")
        except FileNotFoundError:
            logger.error("FFmpeg not found in system PATH")
            return False
        
        # Build ffmpeg command
        if os.path.exists(audio_file):
            logger.info("Creating reel with audio")
            command = [
                'ffmpeg', '-y',  # -y to overwrite existing files
                '-f', 'concat',
                '-safe', '0',
                '-i', input_file,
                '-i', audio_file,
                '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-shortest',
                '-r', '30',
                '-pix_fmt', 'yuv420p',
                output_file
            ]
        else:
            logger.info("Creating reel without audio (audio file not found)")
            command = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', input_file,
                '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
                '-c:v', 'libx264',
                '-shortest',
                '-r', '30',
                '-pix_fmt', 'yuv420p',
                output_file
            ]
        
        logger.info(f"Running FFmpeg command: {' '.join(command)}")
        
        # Run ffmpeg command
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logger.info(f"FFmpeg completed successfully")
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                logger.info(f"Output file created successfully: {output_file} (size: {file_size} bytes)")
                return True
            else:
                logger.error(f"FFmpeg reported success but output file not found: {output_file}")
                return False
        else:
            logger.error(f"FFmpeg failed with return code: {result.returncode}")
            logger.error(f"FFmpeg stderr: {result.stderr}")
            logger.error(f"FFmpeg stdout: {result.stdout}")
            return False
        
    except subprocess.TimeoutExpired:
        logger.error(f"FFmpeg timeout for folder {folder}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error creating reel for {folder}: {e}")
        return False

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
        logger.info(f"Processing create request with files: {list(request.files.keys())}")
        rec_id = request.form.get("uuid")
        desc = request.form.get("text", "")
        input_files = []
        
        logger.info(f"Record ID: {rec_id}")
        logger.info(f"Description: {desc[:100]}...")
        
        # Create user folder
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], rec_id)
        os.makedirs(user_folder, exist_ok=True)
        logger.info(f"Created user folder: {user_folder}")
        
        # Process uploaded files
        for key in request.files:
            file = request.files[key]
            if file and file.filename:
                filename = secure_filename(file.filename)
                filepath = os.path.join(user_folder, filename)
                file.save(filepath)
                input_files.append(filename)
                logger.info(f"Saved file: {filename} to {filepath}")
        
        # Save description
        if desc:
            desc_path = os.path.join(user_folder, "desc.txt")
            with open(desc_path, "w") as f:
                f.write(desc)
            logger.info(f"Saved description to: {desc_path}")
        
        # Create input.txt for ffmpeg
        if input_files:
            input_txt_path = os.path.join(user_folder, "input.txt")
            with open(input_txt_path, "w") as f:
                for filename in input_files:
                    abs_path = os.path.abspath(os.path.join(user_folder, filename))
                    f.write(f"file '{abs_path}'\nduration 1\n")
            logger.info(f"Created input.txt at: {input_txt_path}")
            
            # Process immediately
            try:
                logger.info(f"Starting immediate processing for {rec_id}")
                
                # Generate audio
                audio_success = text_to_audio(str(rec_id))
                logger.info(f"Audio generation result: {audio_success}")
                
                # Create reel
                reel_success = create_reel(str(rec_id))
                logger.info(f"Reel creation result: {reel_success}")
                
                if audio_success and reel_success:
                    logger.info(f"Successfully processed reel for {rec_id}")
                    # Return the reel file for download
                    reel_path = os.path.join(user_folder, f"{rec_id}.mp4")
                    if os.path.exists(reel_path):
                        return send_file(reel_path, as_attachment=True, download_name=f"reel_{rec_id}.mp4")
                    else:
                        logger.error(f"Reel file not found: {reel_path}")
                        return "Error: Reel creation failed", 500
                else:
                    logger.error(f"Failed to process reel for {rec_id}")
                    return "Error: Failed to process reel", 500
                    
            except Exception as e:
                logger.error(f"Error processing reel immediately: {e}")
                return f"Error: {str(e)}", 500
        
        return "Error: No files uploaded", 400

    return render_template("create.html", myid=myid)

@app.route("/gallery")
def gallery():
    # Gallery is now empty since we don't store reels in static/reels anymore
    # You can remove this route or keep it for future use
    return render_template("gallery.html", reels=[])

@app.route("/status")
def status():
    """Debug endpoint to check processing status"""
    status_info = {
        "uploads_folder_exists": os.path.exists("user_uploads"),
        "done_file_exists": os.path.exists("done.txt"),
        "current_working_directory": os.getcwd()
    }
    
    if os.path.exists("user_uploads"):
        try:
            upload_folders = os.listdir("user_uploads")
            status_info["upload_folders"] = upload_folders
            
            # Get details for each folder
            folder_details = {}
            for folder in upload_folders:
                folder_path = os.path.join("user_uploads", folder)
                if os.path.isdir(folder_path):
                    files = os.listdir(folder_path)
                    folder_details[folder] = {
                        "files": files,
                        "has_desc": "desc.txt" in files,
                        "has_input": "input.txt" in files,
                        "has_audio": "audio.mp3" in files,
                        "has_reel": any(f.endswith('.mp4') for f in files)
                    }
            status_info["folder_details"] = folder_details
        except Exception as e:
            status_info["upload_folders_error"] = str(e)
    
    # Check ffmpeg availability
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        status_info["ffmpeg_available"] = True
        status_info["ffmpeg_version"] = result.stdout.split('\n')[0]
    except FileNotFoundError:
        status_info["ffmpeg_available"] = False
        status_info["ffmpeg_error"] = "FFmpeg not found"
    
    return jsonify(status_info)

# Add this route to your app.py for testing
@app.route("/test-ffmpeg")
def test_ffmpeg():
    """Test FFmpeg functionality"""
    try:
        # Test FFmpeg availability
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return jsonify({
                "ffmpeg_available": True,
                "version": result.stdout.split('\n')[0],
                "working_directory": os.getcwd(),
                "can_write_uploads": os.access('user_uploads', os.W_OK),
                "uploads_exists": os.path.exists('user_uploads')
            })
        else:
            return jsonify({
                "ffmpeg_available": False,
                "error": result.stderr,
                "return_code": result.returncode
            })
    except Exception as e:
        return jsonify({
            "ffmpeg_available": False,
            "error": str(e)
        })

# Add this simple test route to create a dummy video
@app.route("/test-create-video")
def test_create_video():
    """Create a simple test video"""
    try:
        test_folder = "test_" + str(uuid.uuid4())
        test_path = os.path.join('user_uploads', test_folder)
        os.makedirs(test_path, exist_ok=True)
        
        # Create a simple test video (solid color)
        command = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', 'color=red:size=1080x1920:duration=2',
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            os.path.join(test_path, 'test_video.mp4')
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        
        test_video_path = os.path.join(test_path, 'test_video.mp4')
        if result.returncode == 0 and os.path.exists(test_video_path):
            file_size = os.path.getsize(test_video_path)
            return jsonify({
                "success": True,
                "message": "Test video created successfully",
                "file_size": file_size,
                "file_exists": True
            })
        else:
            return jsonify({
                "success": False,
                "return_code": result.returncode,
                "stderr": result.stderr,
                "stdout": result.stdout
            })
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })

if __name__ == "__main__":
    # Ensure required directories exist
    os.makedirs('user_uploads', exist_ok=True)
    
    logger.info("Starting MediaMeld application")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Upload folder: {UPLOAD_FOLDER}")
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)