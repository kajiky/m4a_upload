# Audio Upload Flask App for Google Cloud Run
from flask import Flask, request, render_template_string, jsonify
import os
import threading
from datetime import datetime
import uuid
import tempfile
import logging

app = Flask(__name__)

# Cloud Run configuration
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# Use /tmp for temporary file storage (Cloud Run writable directory)
UPLOAD_FOLDER = '/tmp/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple HTML template (embedded to avoid template file issues)
UPLOAD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Audio Upload</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; max-width: 500px; margin: 50px auto; padding: 20px; }
        .upload-area { border: 2px dashed #ccc; padding: 40px; text-align: center; margin: 20px 0; }
        .upload-area:hover { border-color: #999; }
        input[type="file"] { margin: 20px 0; }
        button { background: #007cba; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #005a87; }
        .message { padding: 10px; margin: 10px 0; border-radius: 4px; }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    </style>
</head>
<body>
    <h1>Audio File Upload</h1>
    <div class="upload-area">
        <form id="uploadForm" enctype="multipart/form-data">
            <p>Select audio file (M4A, MP3, WAV, AAC)</p>
            <input type="file" name="audio_file" accept=".m4a,.mp3,.wav,.aac" required>
            <br>
            <button type="submit">Upload & Process</button>
        </form>
    </div>
    <div id="message"></div>

    <script>
        document.getElementById('uploadForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const messageDiv = document.getElementById('message');
            
            try {
                messageDiv.innerHTML = '<div class="message">Uploading...</div>';
                
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    messageDiv.innerHTML = `<div class="message success">${result.message}</div>`;
                } else {
                    messageDiv.innerHTML = `<div class="message error">${result.error}</div>`;
                }
            } catch (error) {
                messageDiv.innerHTML = '<div class="message error">Upload failed. Please try again.</div>';
            }
        });
    </script>
</body>
</html>
'''

@app.route('/')
def upload_page():
    """Mobile-optimized upload page"""
    return render_template_string(UPLOAD_TEMPLATE)

@app.route('/health')
def health_check():
    """Health check endpoint for Cloud Run"""
    return jsonify({'status': 'healthy'}), 200

@app.route('/upload', methods=['POST'])
def handle_upload():
    """Handle file upload and trigger processing"""
    try:
        if 'audio_file' not in request.files:
            return jsonify({'error': 'No file selected'}), 400
        
        file = request.files['audio_file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file and allowed_file(file.filename):
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_id = str(uuid.uuid4())[:8]
            filename = f"{timestamp}_{unique_id}_{file.filename}"
            
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            logger.info(f"File uploaded: {filename}")
            
            # Process file in background thread
            threading.Thread(target=process_audio_file, args=(filepath,), daemon=True).start()
            
            return jsonify({
                'success': True, 
                'message': 'File uploaded successfully! Processing started.',
                'filename': filename
            })
        
        return jsonify({'error': 'Invalid file type. Please upload M4A, MP3, WAV, or AAC files.'}), 400
    
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': 'Upload failed. Please try again.'}), 500

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'m4a', 'mp3', 'wav', 'aac'}

def process_audio_file(filepath):
    """Process the uploaded audio file"""
    try:
        logger.info(f"Starting processing: {filepath}")
        
        # Your audio processing logic goes here
        # Examples:
        # - Audio transcription
        # - Format conversion
        # - Audio analysis
        # - Upload to cloud storage
        
        # Simulate processing time
        import time
        time.sleep(2)
        
        logger.info(f"Processing completed: {filepath}")
        
        # Clean up temporary file after processing
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Cleaned up file: {filepath}")
            
    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        # Clean up on error
        if os.path.exists(filepath):
            os.remove(filepath)

if __name__ == '__main__':
    # Cloud Run provides PORT environment variable
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
