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
            
        with open(desc_file, "r", encoding='utf-8') as f:
            text = f.read().strip()
        
        if not text:
            logger.error(f"Description file is empty: {desc_file}")
            return False
        
        logger.info(f"Generating audio for folder: {folder}")
        logger.info(f"Text content: {text}")
        
        # Check if audio already exists
        audio_file = os.path.join("user_uploads", folder, "audio.mp3")
        if os.path.exists(audio_file) and os.path.getsize(audio_file) > 0:
            logger.info(f"Audio file already exists: {audio_file}")
            return True
        
        # Generate new audio
        try:
            result = text_to_speech_file(text, folder)
            logger.info(f"text_to_speech_file returned: {result}")
            
            # Wait a moment for file to be written
            import time
            time.sleep(1)
            
            # Verify audio file was created
            if os.path.exists(audio_file) and os.path.getsize(audio_file) > 0:
                file_size = os.path.getsize(audio_file)
                logger.info(f"Audio file successfully created: {audio_file} (size: {file_size} bytes)")
                return True
            else:
                logger.error(f"Audio file was not created or is empty: {audio_file}")
                return False
                
        except Exception as tts_error:
            logger.error(f"Error in text_to_speech_file: {tts_error}")
            # Check if file was created despite the error
            if os.path.exists(audio_file) and os.path.getsize(audio_file) > 0:
                logger.info(f"Audio file exists despite error - continuing")
                return True
            return False
        
    except Exception as e:
        logger.error(f"Unexpected error in text_to_audio for {folder}: {e}")
        # Check if audio file exists anyway
        audio_file = os.path.join("user_uploads", folder, "audio.mp3")
        if os.path.exists(audio_file) and os.path.getsize(audio_file) > 0:
            logger.info(f"Audio file exists despite error - returning True")
            return True
        return False

def create_reel(folder):
    """Create video reel from images and audio"""
    try:
        input_file = os.path.join("user_uploads", folder, "input.txt")
        audio_file = os.path.join("user_uploads", folder, "audio.mp3")
        output_file = os.path.join("user_uploads", folder, f"{folder}.mp4")
        
        logger.info(f"Creating reel for folder: {folder}")
        logger.info(f"Input file: {input_file}")
        logger.info(f"Audio file: {audio_file}")
        logger.info(f"Output file: {output_file}")
        
        # Check if input file exists
        if not os.path.exists(input_file):
            logger.error(f"Input file not found: {input_file}")
            return False
        
        # Read and validate input file contents
        with open(input_file, 'r') as f:
            input_content = f.read()
            logger.info(f"Input file content:\n{input_content}")
        
        # Validate that all image files in input.txt actually exist
        lines = input_content.strip().split('\n')
        image_files = []
        for line in lines:
            if line.startswith('file '):
                # Extract file path (remove 'file ' and quotes)
                file_path = line[5:].strip().strip("'\"")
                if os.path.exists(file_path):
                    image_files.append(file_path)
                    logger.info(f"Image file exists: {file_path}")
                else:
                    logger.error(f"Image file not found: {file_path}")
                    return False
        
        if not image_files:
            logger.error("No valid image files found in input.txt")
            return False
        
        # Check ffmpeg availability
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)
            logger.info("FFmpeg is available")
        except FileNotFoundError:
            logger.error("FFmpeg not found in system PATH")
            return False
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg version check timed out")
            return False
        
        # Convert paths to use forward slashes for FFmpeg (works on both Windows and Unix)
        normalized_input_file = input_file.replace('\\', '/')
        normalized_audio_file = audio_file.replace('\\', '/')
        normalized_output_file = output_file.replace('\\', '/')
        
        # Build ffmpeg command
        if os.path.exists(audio_file):
            logger.info("Creating reel with audio")
            command = [
                'ffmpeg', '-y',  # -y to overwrite existing files
                '-f', 'concat',
                '-safe', '0',
                '-i', normalized_input_file,
                '-i', normalized_audio_file,
                '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-shortest',
                '-r', '30',
                '-pix_fmt', 'yuv420p',
                normalized_output_file
            ]
        else:
            logger.info("Creating reel without audio (audio file not found)")
            command = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', normalized_input_file,
                '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
                '-c:v', 'libx264',
                '-shortest',
                '-r', '30',
                '-pix_fmt', 'yuv420p',
                normalized_output_file
            ]
        
        logger.info(f"Running FFmpeg command: {' '.join(command)}")
        
        # Run ffmpeg command with detailed error capture
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=300)
            
            # Log both stdout and stderr regardless of return code
            if result.stdout:
                logger.info(f"FFmpeg stdout: {result.stdout}")
            if result.stderr:
                logger.info(f"FFmpeg stderr: {result.stderr}")
            
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
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"FFmpeg timeout for folder {folder}")
            return False
        
    except Exception as e:
        logger.error(f"Unexpected error creating reel for {folder}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
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
            with open(desc_path, "w", encoding='utf-8') as f:
                f.write(desc)
            logger.info(f"Saved description to: {desc_path}")
        
        # Create input.txt for ffmpeg
        if input_files:
            input_txt_path = os.path.join(user_folder, "input.txt")
            with open(input_txt_path, "w", encoding='utf-8') as f:
                for i, filename in enumerate(input_files):
                    abs_path = os.path.abspath(os.path.join(user_folder, filename))
                    # Convert Windows backslashes to forward slashes for FFmpeg compatibility
                    normalized_path = abs_path.replace('\\', '/')
                    f.write(f"file '{normalized_path}'\n")
                    f.write(f"duration 3\n")  # 3 seconds per image
                    # Add outpoint for last image to avoid ffmpeg issues
                    if i == len(input_files) - 1:
                        f.write(f"file '{normalized_path}'\n")
            logger.info(f"Created input.txt at: {input_txt_path}")
            
            # Log the content of input.txt for debugging
            with open(input_txt_path, 'r', encoding='utf-8') as f:
                input_content = f.read()
                logger.info(f"Input.txt content:\n{input_content}")
            
            # Process immediately
            try:
                logger.info(f"Starting immediate processing for {rec_id}")
                
                # Generate audio (check if it exists first)
                audio_success = text_to_audio(str(rec_id))
                logger.info(f"Audio generation result: {audio_success}")
                
                # Always try to create reel, regardless of audio success
                reel_success = create_reel(str(rec_id))
                logger.info(f"Reel creation result: {reel_success}")
                
                if reel_success:  # Only require reel creation to succeed
                    logger.info(f"Successfully processed reel for {rec_id}")
                    # Return the reel file for download
                    reel_path = os.path.join(user_folder, f"{rec_id}.mp4")
                    if os.path.exists(reel_path):
                        return send_file(reel_path, as_attachment=True, download_name=f"reel_{rec_id}.mp4")
                    else:
                        logger.error(f"Reel file not found: {reel_path}")
                        return f"Error: Reel file not found at {reel_path}", 500
                else:
                    error_msg = f"Processing failed - Audio: {audio_success}, Reel: {reel_success}"
                    logger.error(error_msg)
                    
                    # Additional debugging info
                    debug_info = []
                    desc_file = os.path.join(user_folder, "desc.txt")
                    input_file = os.path.join(user_folder, "input.txt")
                    audio_file = os.path.join(user_folder, "audio.mp3")
                    
                    debug_info.append(f"Description file exists: {os.path.exists(desc_file)}")
                    debug_info.append(f"Input file exists: {os.path.exists(input_file)}")
                    debug_info.append(f"Audio file exists: {os.path.exists(audio_file)}")
                    
                    if os.path.exists(desc_file):
                        with open(desc_file, 'r', encoding='utf-8') as f:
                            desc_content = f.read()
                            debug_info.append(f"Description content length: {len(desc_content)}")
                    
                    if os.path.exists(input_file):
                        with open(input_file, 'r', encoding='utf-8') as f:
                            input_content = f.read()
                            debug_info.append(f"Input file content: {input_content}")
                    
                    debug_str = " | ".join(debug_info)
                    logger.error(f"Debug info: {debug_str}")
                    
                    return f"Error: {error_msg} | Debug: {debug_str}", 500
                    
            except Exception as e:
                logger.error(f"Error processing reel immediately: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
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

@app.route("/test-input-format")
def test_input_format():
    """Test the input.txt format with a simple example"""
    try:
        test_folder = "input_test_" + str(uuid.uuid4())
        test_path = os.path.join('user_uploads', test_folder)
        os.makedirs(test_path, exist_ok=True)
        
        # Create a simple test image
        test_image = os.path.join(test_path, "test.jpg")
        img_command = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', 'color=green:size=1080x1920:duration=0.1',
            '-vframes', '1',
            test_image
        ]
        
        subprocess.run(img_command, capture_output=True, text=True)
        
        if not os.path.exists(test_image):
            return jsonify({"error": "Could not create test image"})
        
        # Create input.txt
        input_file = os.path.join(test_path, "input.txt")
        abs_path = os.path.abspath(test_image).replace('\\', '/')
        
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(f"file '{abs_path}'\n")
            f.write(f"duration 3\n")
            f.write(f"file '{abs_path}'\n")  # Duplicate last frame
        
        # Read back to verify
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Test ffmpeg with this input
        output_file = os.path.join(test_path, "test_output.mp4")
        command = [
            'ffmpeg', '-y',
            '-f', 'concat', '-safe', '0',
            '-i', input_file,
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
            '-c:v', 'libx264', '-r', '30', '-pix_fmt', 'yuv420p',
            output_file
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        
        return jsonify({
            "test_folder": test_folder,
            "input_content": content,
            "image_exists": os.path.exists(test_image),
            "ffmpeg_return_code": result.returncode,
            "ffmpeg_stderr": result.stderr,
            "ffmpeg_stdout": result.stdout,
            "output_created": os.path.exists(output_file),
            "output_size": os.path.getsize(output_file) if os.path.exists(output_file) else 0
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e)
        })

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

@app.route("/test-audio")
def test_audio():
    """Test audio generation"""
    try:
        test_folder = "test_audio_" + str(uuid.uuid4())
        test_path = os.path.join('user_uploads', test_folder)
        os.makedirs(test_path, exist_ok=True)
        
        # Create a test description
        test_text = "Hello, this is a test audio generation."
        desc_file = os.path.join(test_path, "desc.txt")
        with open(desc_file, 'w', encoding='utf-8') as f:
            f.write(test_text)
        
        # Test audio generation
        audio_success = text_to_audio(test_folder)
        
        # Check if audio file was created
        audio_file = os.path.join(test_path, "audio.mp3")
        audio_exists = os.path.exists(audio_file)
        audio_size = os.path.getsize(audio_file) if audio_exists else 0
        
        return jsonify({
            "success": audio_success,
            "audio_file_exists": audio_exists,
            "audio_file_size": audio_size,
            "test_folder": test_folder,
            "desc_content": test_text
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })

@app.route("/debug-processing")
def debug_processing():
    """Debug the entire processing pipeline"""
    try:
        test_folder = "debug_" + str(uuid.uuid4())
        test_path = os.path.join('user_uploads', test_folder)
        os.makedirs(test_path, exist_ok=True)
        
        debug_info = {
            "test_folder": test_folder,
            "test_path": test_path,
            "steps": {}
        }
        
        # Step 1: Create test description
        test_text = "This is a debug test for reel generation."
        desc_file = os.path.join(test_path, "desc.txt")
        with open(desc_file, 'w', encoding='utf-8') as f:
            f.write(test_text)
        debug_info["steps"]["1_desc_created"] = os.path.exists(desc_file)
        
        # Step 2: Create dummy input.txt (since we don't have images)
        input_file = os.path.join(test_path, "input.txt")
        # Create a simple colored image first
        temp_image = os.path.join(test_path, "temp.png")
        
        # Create temporary image using ffmpeg
        img_command = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', 'color=blue:size=1080x1920:duration=0.1',
            '-vframes', '1',
            temp_image
        ]
        
        img_result = subprocess.run(img_command, capture_output=True, text=True)
        debug_info["steps"]["2_temp_image_created"] = os.path.exists(temp_image)
        
        if os.path.exists(temp_image):
            with open(input_file, 'w', encoding='utf-8') as f:
                f.write(f"file '{os.path.abspath(temp_image)}'\n")
                f.write(f"duration 2\n")
            debug_info["steps"]["3_input_txt_created"] = os.path.exists(input_file)
        
        # Step 3: Test audio generation
        audio_success = text_to_audio(test_folder)
        debug_info["steps"]["4_audio_generation"] = audio_success
        
        audio_file = os.path.join(test_path, "audio.mp3")
        debug_info["steps"]["4_audio_file_exists"] = os.path.exists(audio_file)
        
        # Step 4: Test reel creation
        if os.path.exists(input_file):
            reel_success = create_reel(test_folder)
            debug_info["steps"]["5_reel_creation"] = reel_success
            
            reel_file = os.path.join(test_path, f"{test_folder}.mp4")
            debug_info["steps"]["5_reel_file_exists"] = os.path.exists(reel_file)
            if os.path.exists(reel_file):
                debug_info["steps"]["5_reel_file_size"] = os.path.getsize(reel_file)
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "debug_info": debug_info if 'debug_info' in locals() else {}
        })

if __name__ == "__main__":
    # Ensure required directories exist
    os.makedirs('user_uploads', exist_ok=True)
    
    logger.info("Starting MediaMeld application")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Upload folder: {UPLOAD_FOLDER}")
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)