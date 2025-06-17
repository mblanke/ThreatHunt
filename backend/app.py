import os
import logging
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from datetime import datetime

# Try to import flask-cors
try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False
    print("Warning: flask-cors not available")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="../frontend/dist")

# Enable CORS
if CORS_AVAILABLE:
    CORS(app)
else:
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
        return response

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploaded'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'json', 'txt', 'log'}

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

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
        'version': '1.0.0',
        'service': 'Cyber Threat Hunter API'
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
        
        logger.info(f"File uploaded successfully: {filename}")
        return jsonify({
            'message': 'File uploaded successfully',
            'filename': filename,
            'size': os.path.getsize(filepath)
        })
    
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'error': 'Upload failed'}), 500

@app.route('/api/files')
def list_files():
    try:
        files = []
        upload_dir = app.config['UPLOAD_FOLDER']
        
        if os.path.exists(upload_dir):
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

@app.route('/api/stats')
def get_stats():
    try:
        upload_dir = app.config['UPLOAD_FOLDER']
        files_count = 0
        if os.path.exists(upload_dir):
            files_count = len([f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))])
        
        return jsonify({
            'filesUploaded': files_count,
            'analysesCompleted': files_count,
            'threatsDetected': 0
        })
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({'error': 'Failed to get stats'}), 500

# Static file serving for React app
@app.route("/")
def index():
    if os.path.exists(os.path.join(app.static_folder, "index.html")):
        return send_from_directory(app.static_folder, "index.html")
    else:
        return jsonify({
            'message': 'Cyber Threat Hunter API', 
            'status': 'running',
            'endpoints': [
                'GET /api/health',
                'POST /api/upload',
                'GET /api/files',
                'GET /api/stats'
            ]
        })

if __name__ == "__main__":
    print("=" * 50)
    print("Starting Cyber Threat Hunter Backend...")
    print("API available at: http://localhost:5000")
    print("Health check: http://localhost:5000/api/health")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)
        # Basic security tools detection
        tools_found = []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().lower()
            
            # Common security tools to detect
            security_tools = [
                'windows defender', 'antimalware', 'avast', 'norton', 'mcafee',
                'crowdstrike', 'carbon black', 'sentinelone', 'cylance',
                'kaspersky', 'bitdefender', 'sophos', 'trend micro',
                'openvpn', 'nordvpn', 'expressvpn', 'cisco anyconnect'
            ]
            
            for tool in security_tools:
                if tool in content:
                    tools_found.append(tool)
        
        return jsonify({
            'filename': filename,
            'tools_found': tools_found,
            'total_tools': len(tools_found)
        })
    
    except Exception as e:
        logger.error(f"Security tools analysis error: {e}")
        return jsonify({'error': 'Analysis failed'}), 500

@app.route('/api/stats')
def get_stats():
    try:
        upload_dir = app.config['UPLOAD_FOLDER']
        files_count = len([f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))])
        
        return jsonify({
            'filesUploaded': files_count,
            'analysesCompleted': files_count,
            'threatsDetected': 0
        })
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({'error': 'Failed to get stats'}), 500

# Static file serving for React app
@app.route("/assets/<path:path>")
def send_assets(path):
    return send_from_directory(os.path.join(app.static_folder, "assets"), path)

@app.route("/")
def index():
    if os.path.exists(os.path.join(app.static_folder, "index.html")):
        return send_from_directory(app.static_folder, "index.html")
    else:
        return jsonify({'message': 'Cyber Threat Hunter API', 'status': 'running'})

# Catch-all route for React Router
@app.route("/<path:path>")
def catch_all(path):
    if os.path.exists(os.path.join(app.static_folder, "index.html")):
        return send_from_directory(app.static_folder, "index.html")
    else:
        return jsonify({'error': 'Frontend not built yet'})

if __name__ == "__main__":
    print("=" * 50)
    print("Starting Cyber Threat Hunter Backend...")
    print("API available at: http://localhost:5000")
    print("Health check: http://localhost:5000/api/health")
    print("Available endpoints:")
    print("  POST /api/upload - Upload files")
    print("  GET /api/files - List uploaded files")
    print("  GET /api/analyze/<filename> - Analyze file")
    print("  GET /api/security-tools/<filename> - Detect security tools")
    print("  GET /api/stats - Get statistics")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)
                })
            except Exception as e:
                analysis['csv_error'] = str(e)
        elif filename.lower().endswith('.csv'):
            # Basic CSV analysis without pandas
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    analysis.update({
                        'rows': len(lines) - 1,  # Subtract header
                        'columns': len(lines[0].split(',')) if lines else 0,
                        'preview': lines[:6] if lines else []
                    })
            except Exception as e:
                analysis['csv_error'] = str(e)
        
        return jsonify(analysis)
    
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return jsonify({'error': 'Analysis failed'}), 500

# Stats endpoint
@app.route('/api/stats')
def get_stats():
    try:
        upload_dir = app.config['UPLOAD_FOLDER']
        files_count = len([f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))])
        
        return jsonify({
            'filesUploaded': files_count,
            'analysesCompleted': files_count,  # Simplified
            'threatsDetected': 0  # Placeholder
        })
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({'error': 'Failed to get stats'}), 500

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
