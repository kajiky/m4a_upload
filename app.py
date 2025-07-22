# Fixed Audio Upload Flask App - Bypass 32MB Cloud Run limit with signed URLs
from flask import Flask, request, render_template_string, jsonify
from google.cloud import storage
from google.auth import impersonated_credentials
import google.auth
import os
from datetime import datetime, timedelta
import uuid
import logging



#Comment to try GCP trigger 

app = Flask(__name__)

# Configuration - removed MAX_CONTENT_LENGTH since we'll use direct uploads
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

BUCKET_NAME = "terry_app_bucket"

source_credentials, project_id = google.auth.default()
target_credentials = impersonated_credentials.Credentials(
    source_credentials=source_credentials,
    target_principal="audio-upload-sa@eastern-stock-462512-j4.iam.gserviceaccount.com",
    target_scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
storage_client = storage.Client(credentials=target_credentials)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'m4a', 'mp3', 'wav', 'aac'}

@app.route('/get_upload_url', methods=['POST'])
def get_upload_url():
    """Generate a signed URL for direct upload to Cloud Storage"""
    try:
        data = request.get_json()
        if not data or 'filename' not in data:
            return jsonify({'error': 'Filename is required'}), 400
        
        original_filename = data['filename']
        
        if not allowed_file(original_filename):
            return jsonify({'error': 'Invalid file type. Please upload M4A, MP3, WAV, or AAC files.'}), 400
        
        # Generate unique filename while preserving extension
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        base_name = original_filename.rsplit('.', 1)[0]
        unique_filename = f"{timestamp}_{unique_id}_{base_name}.{file_extension}"
        
        blob_name = f"audio-uploads/{unique_filename}"
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        
        # Check if file already exists
        if blob.exists():
            return jsonify({'error': 'File already exists, please rename'}), 400
        
        # Generate signed URL for upload (valid for 1 hour)
        upload_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1),
            method="PUT",
            content_type="application/octet-stream"
        )
        
        logger.info(f"Generated upload URL for: {unique_filename}")
        
        return jsonify({
            'upload_url': upload_url,
            'filename': unique_filename,
            'blob_name': blob_name
        })
        
    except Exception as e:
        logger.error(f"Error generating upload URL: {str(e)}")
        return jsonify({'error': f'Failed to generate upload URL: {str(e)}'}), 500

@app.route('/confirm_upload', methods=['POST'])
def confirm_upload():
    """Confirm that the upload was successful"""
    try:
        data = request.get_json()
        if not data or 'blob_name' not in data:
            return jsonify({'error': 'Blob name is required'}), 400
        
        blob_name = data['blob_name']
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        
        # Check if the file exists (was uploaded successfully)
        if blob.exists():
            # Get file info
            blob.reload()  # Refresh metadata
            file_size = blob.size
            
            logger.info(f"Upload confirmed: {blob_name}, Size: {file_size / (1024*1024):.2f} MB")
            
            return jsonify({
                'success': True,
                'message': f'File uploaded successfully! Size: {file_size / (1024*1024):.2f} MB',
                'blob_name': blob_name,
                'size_bytes': file_size
            })
        else:
            return jsonify({'error': 'Upload verification failed - file not found'}), 400
            
    except Exception as e:
        logger.error(f"Error confirming upload: {str(e)}")
        return jsonify({'error': f'Upload confirmation failed: {str(e)}'}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

@app.route('/')
def upload_page():
    return render_template_string(UPLOAD_TEMPLATE)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


UPLOAD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Large File Upload - Direct to Cloud Storage</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            max-width: 450px;
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
            height: 8px;
            background: #f0f0f0;
            border-radius: 4px;
            margin: 20px 0;
            display: none;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            border-radius: 4px;
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
        
        .info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }
        
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
        <h1>🎵 Large Audio Upload</h1>
        <p style="color: #666; margin-bottom: 20px;">Direct to Cloud Storage - No size limit!</p>
        
        <div class="upload-area" onclick="document.getElementById('fileInput').click()">
            <div class="upload-icon">☁️</div>
            <div class="upload-text">Select your audio file</div>
            <div style="font-size: 14px; color: #999;">M4A, MP3, WAV, AAC • Any size up to 2GB</div>
        </div>
        
        <input type="file" id="fileInput" accept=".m4a,.mp3,.wav,.aac" required>
        
        <div class="file-info" id="fileInfo">
            <strong>Selected:</strong> <span id="fileName"></span><br>
            <span id="fileSize"></span>
        </div>
        
        <div class="progress-bar" id="progressBar">
            <div class="progress-fill" id="progressFill"></div>
        </div>
        
        <button type="button" class="upload-btn" id="uploadBtn" onclick="uploadFile()" disabled>
            Upload to Cloud Storage
        </button>
        
        <div class="status-message" id="statusMessage"></div>
    </div>

    <script>
        const fileInput = document.getElementById('fileInput');
        const fileInfo = document.getElementById('fileInfo');
        const fileName = document.getElementById('fileName');
        const fileSize = document.getElementById('fileSize');
        const uploadBtn = document.getElementById('uploadBtn');
        const progressBar = document.getElementById('progressBar');
        const progressFill = document.getElementById('progressFill');
        const statusMessage = document.getElementById('statusMessage');
        const uploadArea = document.querySelector('.upload-area');

        let selectedFile = null;

        // File selection handler
        fileInput.addEventListener('change', function(e) {
            selectedFile = e.target.files[0];
            if (selectedFile) {
                fileName.textContent = selectedFile.name;
                fileSize.textContent = `Size: ${(selectedFile.size / 1024 / 1024).toFixed(2)} MB`;
                fileInfo.style.display = 'block';
                uploadBtn.disabled = false;
                
                // Check file size (2GB = 2 * 1024 * 1024 * 1024 bytes)
                if (selectedFile.size > 2 * 1024 * 1024 * 1024) {
                    showMessage('error', 'File too large! Maximum size is 2GB.');
                    uploadBtn.disabled = true;
                } else {
                    hideMessage();
                }
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

        function showMessage(type, message) {
            statusMessage.style.display = 'block';
            statusMessage.className = `status-message ${type}`;
            statusMessage.textContent = message;
        }

        function hideMessage() {
            statusMessage.style.display = 'none';
        }

        function updateProgress(percent) {
            progressFill.style.width = percent + '%';
        }

        // Main upload function using direct Cloud Storage upload
        async function uploadFile() {
            if (!selectedFile) {
                showMessage('error', 'Please select a file first');
                return;
            }

            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Preparing upload...';
            progressBar.style.display = 'block';
            hideMessage();

            try {
                // Step 1: Get signed upload URL
                showMessage('info', 'Getting upload URL...');
                const urlResponse = await fetch('/get_upload_url', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        filename: selectedFile.name
                    })
                });

                if (!urlResponse.ok) {
                    const errorData = await urlResponse.json();
                    throw new Error(errorData.error || 'Failed to get upload URL');
                }

                const urlData = await urlResponse.json();
                const { upload_url, filename, blob_name } = urlData;

                // Step 2: Upload directly to Cloud Storage
                uploadBtn.textContent = 'Uploading to Cloud Storage...';
                showMessage('info', 'Uploading directly to Cloud Storage...');

                const uploadResponse = await fetch(upload_url, {
                    method: 'PUT',
                    body: selectedFile,
                    headers: {
                        'Content-Type': 'application/octet-stream',
                    },
                    // Track upload progress
                });

                if (!uploadResponse.ok) {
                    throw new Error(`Upload failed with status: ${uploadResponse.status}`);
                }

                updateProgress(90);
                
                // Step 3: Confirm upload
                uploadBtn.textContent = 'Confirming upload...';
                const confirmResponse = await fetch('/confirm_upload', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        blob_name: blob_name
                    })
                });

                if (!confirmResponse.ok) {
                    const errorData = await confirmResponse.json();
                    throw new Error(errorData.error || 'Upload confirmation failed');
                }

                const confirmData = await confirmResponse.json();
                updateProgress(100);

                // Success!
                showMessage('success', confirmData.message);
                
                // Reset form after success
                setTimeout(() => {
                    resetForm();
                }, 3000);

            } catch (error) {
                console.error('Upload error:', error);
                showMessage('error', `Upload failed: ${error.message}`);
                uploadBtn.disabled = false;
                uploadBtn.textContent = 'Upload to Cloud Storage';
                progressBar.style.display = 'none';
            }
        }

        function resetForm() {
            fileInput.value = '';
            selectedFile = null;
            fileInfo.style.display = 'none';
            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Upload to Cloud Storage';
            progressBar.style.display = 'none';
            updateProgress(0);
            hideMessage();
        }

        // Simulate upload progress (since we can't track real progress with fetch)
        function simulateProgress() {
            let progress = 0;
            const interval = setInterval(() => {
                progress += Math.random() * 10;
                if (progress > 80) progress = 80; // Stop at 80% until real completion
                updateProgress(progress);
                
                if (progress >= 80) {
                    clearInterval(interval);
                }
            }, 200);
            return interval;
        }
    </script>
</body>
</html>
'''