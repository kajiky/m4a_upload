# Audio Upload Flask App for Google Cloud Run
from flask import Flask, request, render_template_string, jsonify
from google.cloud import storage
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

BUCKET_NAME = "terry_app_bucket" 
storage_client = storage.Client()


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#PAGE TEMPLATE
UPLOAD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audio Upload</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: url('/static/background_alpine.jpg') no-repeat center center fixed;
            background-size: cover;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
}
        
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 400px;
            text-align: center;
        }
        
        h1 {
            color: #333;
            margin-bottom: 30px;
            font-size: 24px;
        }
        
        .upload-area {
            border: 3px dashed #ddd;
            border-radius: 15px;
            padding: 40px 20px;
            margin-bottom: 20px;
            transition: all 0.3s ease;
            cursor: pointer;
        }
        
        .upload-area:hover, .upload-area.dragover {
            border-color: #667eea;
            background-color: #f8f9ff;
        }
        
        .upload-icon {
            font-size: 48px;
            color: #ddd;
            margin-bottom: 15px;
        }
        
        .upload-text {
            color: #666;
            font-size: 16px;
            margin-bottom: 15px;
        }
        
        input[type="file"] {
            display: none;
        }
        
        .file-info {
            background: #f0f4ff;
            border-radius: 10px;
            padding: 15px;
            margin: 15px 0;
            display: none;
        }
        
        .upload-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 40px;
            border-radius: 25px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            transition: transform 0.2s ease;
            margin-top: 20px;
        }
        
        .upload-btn:hover {
            transform: translateY(-2px);
        }
        
        .upload-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        
        .progress-bar {
            width: 100%;
            height: 6px;
            background: #f0f0f0;
            border-radius: 3px;
            margin: 20px 0;
            display: none;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            border-radius: 3px;
            width: 0%;
            transition: width 0.3s ease;
        }
        
        .status-message {
            margin-top: 20px;
            padding: 15px;
            border-radius: 10px;
            display: none;
        }
        
        .success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        /* Mobile optimizations */
        @media (max-width: 480px) {
            .container {
                padding: 30px 20px;
                margin: 10px;
            }
            
            .upload-area {
                padding: 30px 15px;
            }
            
            h1 {
                font-size: 22px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>TERRY APP TESTING</h1>
        
        <form id="uploadForm" enctype="multipart/form-data">
            <div class="upload-area" onclick="document.getElementById('fileInput').click()">
                <div class="upload-icon">📱</div>
                <div class="upload-text">Tap to select audio file</div>
                <div style="font-size: 14px; color: #999;">Supports: M4A/MP3</div>
            </div>
            
            <input type="file" id="fileInput" name="audio_file" accept=".m4a,.mp3,.wav,.aac,audio/*">
            
            <div class="file-info" id="fileInfo">
                <strong>Selected:</strong> <span id="fileName"></span><br>
                <span id="fileSize"></span>
            </div>
            
            <div class="progress-bar" id="progressBar">
                <div class="progress-fill" id="progressFill"></div>
            </div>
            
            <button type="submit" class="upload-btn" id="uploadBtn" disabled>
                Upload & Process
            </button>
        </form>
        
        <div class="status-message" id="statusMessage"></div>
    </div>

    <script>
        const fileInput = document.getElementById('fileInput');
        const fileInfo = document.getElementById('fileInfo');
        const fileName = document.getElementById('fileName');
        const fileSize = document.getElementById('fileSize');
        const uploadBtn = document.getElementById('uploadBtn');
        const uploadForm = document.getElementById('uploadForm');
        const progressBar = document.getElementById('progressBar');
        const progressFill = document.getElementById('progressFill');
        const statusMessage = document.getElementById('statusMessage');
        const uploadArea = document.querySelector('.upload-area');

        // File selection handler
        fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                fileName.textContent = file.name;
                fileSize.textContent = `Size: ${(file.size / 1024 / 1024).toFixed(2)} MB`;
                fileInfo.style.display = 'block';
                uploadBtn.disabled = false;
            }
        });

        // Drag and drop functionality
        uploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', function(e) {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                fileInput.files = files;
                const event = new Event('change', { bubbles: true });
                fileInput.dispatchEvent(event);
            }
        });

        // Form submission
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData();
            formData.append('audio_file', fileInput.files[0]);
            
            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Uploading...';
            progressBar.style.display = 'block';
            statusMessage.style.display = 'none';
            
            // Simulate progress
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += Math.random() * 30;
                if (progress > 90) progress = 90;
                progressFill.style.width = progress + '%';
                
                if (progress >= 90) {
                    clearInterval(progressInterval);
                }
            }, 200);
            
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                clearInterval(progressInterval);
                progressFill.style.width = '100%';
                
                setTimeout(() => {
                    progressBar.style.display = 'none';
                    statusMessage.style.display = 'block';
                    
                    if (data.success) {
                        statusMessage.className = 'status-message success';
                        statusMessage.textContent = data.message;
                        
                        // Reset form after success
                        setTimeout(() => {
                            uploadForm.reset();
                            fileInfo.style.display = 'none';
                            uploadBtn.disabled = true;
                            uploadBtn.textContent = 'Upload & Process';
                            statusMessage.style.display = 'none';
                        }, 3000);
                    } else {
                        statusMessage.className = 'status-message error';
                        statusMessage.textContent = data.error || 'Upload failed';
                        uploadBtn.disabled = false;
                        uploadBtn.textContent = 'Upload & Process';
                    }
                }, 500);
            })
            .catch(error => {
                console.error('Error:', error);
                clearInterval(progressInterval);
                statusMessage.style.display = 'block';
                statusMessage.className = 'status-message error';
                statusMessage.textContent = 'Upload failed. Please try again.';
                uploadBtn.disabled = false;
                uploadBtn.textContent = 'Upload & Process';
                progressBar.style.display = 'none';
            });
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
    """Process and upload audio file to Cloud Storage"""
    try:
        logger.info(f"Starting processing: {filepath}")
        
        # Extract filename
        filename = os.path.basename(filepath)
        
        # Upload to Cloud Storage
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"audio-uploads/{filename}")
        
        # Upload the file
        with open(filepath, 'rb') as file_data:
            blob.upload_from_file(file_data)
        
        logger.info(f"File uploaded to Cloud Storage: gs://{BUCKET_NAME}/audio-uploads/{filename}")
        
        # Your additional processing logic here
        # Example: transcription, analysis, etc.
        
        # Clean up local temp file
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Local temp file cleaned up: {filepath}")
            
    except Exception as e:
        logger.error(f"Processing/Upload error: {str(e)}")
        # Clean up on error
        if os.path.exists(filepath):
            os.remove(filepath)

if __name__ == '__main__':
    # Cloud Run provides PORT environment variable
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
