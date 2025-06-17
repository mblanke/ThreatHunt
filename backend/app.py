import os
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import pandas as pd
import magic
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="../frontend/dist")
CORS(app)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.config['UPLOAD_FOLDER'] = 'uploaded'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'json', 'txt', 'log'}

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def validate_file_content(filepath):
    """Validate file content using python-magic"""
    try:
        mime = magic.Magic(mime=True)
        file_mime = mime.from_file(filepath)
        allowed_mimes = ['text/plain', 'text/csv', 'application/json']
        return file_mime in allowed_mimes
    except Exception as e:
        logger.error(f"File validation error: {e}")
        return False

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 100MB.'}), 413

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {e}")
    return jsonify({'error': 'Internal server error'}), 500

# API Routes
@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    })

@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        file.save(filepath)
        
        # Validate file content
        if not validate_file_content(filepath):
            os.remove(filepath)
            return jsonify({'error': 'Invalid file content'}), 400
        
        logger.info(f"File uploaded successfully: {filename}")
        return jsonify({
            'message': 'File uploaded successfully',
            'filename': filename,
            'size': os.path.getsize(filepath)
        })
    
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'error': 'Upload failed'}), 500

@app.route('/api/analyze/<filename>')
def analyze_file(filename):
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        # Basic file analysis
        file_stats = os.stat(filepath)
        analysis = {
            'filename': filename,
            'size': file_stats.st_size,
            'created': datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
            'modified': datetime.fromtimestamp(file_stats.st_mtime).isoformat()
        }
        
        # CSV specific analysis
        if filename.lower().endswith('.csv'):
            try:
                df = pd.read_csv(filepath)
                analysis.update({
                    'rows': len(df),
                    'columns': len(df.columns),
                    'column_names': df.columns.tolist(),
                    'preview': df.head().to_dict('records')
                })
            except Exception as e:
                analysis['csv_error'] = str(e)
        
        return jsonify(analysis)
    
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return jsonify({'error': 'Analysis failed'}), 500

@app.route('/api/files')
def list_files():
    try:
        files = []
        upload_dir = app.config['UPLOAD_FOLDER']
        
        for filename in os.listdir(upload_dir):
            filepath = os.path.join(upload_dir, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                files.append({
                    'name': filename,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        return jsonify({'files': files})
    
    except Exception as e:
        logger.error(f"List files error: {e}")
        return jsonify({'error': 'Failed to list files'}), 500

# Static file serving
@app.route("/assets/<path:path>")
def send_assets(path):
    return send_from_directory(os.path.join(app.static_folder, "assets"), path)

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

# Catch-all route for React Router
@app.route("/<path:path>")
def catch_all(path):
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
