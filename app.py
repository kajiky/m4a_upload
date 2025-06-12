# M4A Upload Flask App for Cloud Run
from flask import Flask, request, jsonify
import os

app = Flask(__name__)

@app.route('/')
def hello():
    return jsonify({
        'message': 'M4A Upload Service',
        'status': 'running',
        'endpoints': ['/upload', '/health']
    })

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'}), 200

@app.route('/upload', methods=['POST'])
def upload_m4a():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Basic validation for m4a files
    if not file.filename.lower().endswith('.m4a'):
        return jsonify({'error': 'Only M4A files allowed'}), 400
    
    # Here you would process the M4A file
    # For now, just return success
    return jsonify({
        'message': 'File uploaded successfully',
        'filename': file.filename,
        'size': len(file.read())
    })

if __name__ == '__main__':
    # Cloud Run provides PORT environment variable
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
