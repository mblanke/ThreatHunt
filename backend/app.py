import os
import logging
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
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
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'json', 'txt', 'log'}

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0',
        'service': 'Cyber Threat Hunter API'
    })

@app.route('/')
def index():
    return jsonify({'message': 'Cyber Threat Hunter API', 'status': 'running'})

@app.route('/api/test')
def test():
    return jsonify({'message': 'API is working', 'timestamp': datetime.now().isoformat()})

if __name__ == "__main__":
    print("=" * 50)
    print("Starting Cyber Threat Hunter Backend...")
    print("API available at: http://localhost:5000")
    print("Health check: http://localhost:5000/api/health")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 100MB.'}), 413

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {e}")
    return jsonify({'error': 'Internal server error'}), 500

# Security analysis functions
def analyze_security_tools(csv_path):
    """Analyze CSV for security tools based on process names."""
    try:
        df = pd.read_csv(csv_path)
        
        # Load security tools list
        tools_file = os.path.join('lists', 'security-tools.md')
        if not os.path.exists(tools_file):
            return {'error': 'Security tools list not found'}
        
        with open(tools_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # Extract tool names (simplified)
            tools = set()
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and not line.endswith(':'):
                    if line.lower().endswith('.exe') or '.' not in line:
                        tools.add(line.lower())
        
        # Analyze CSV for tools
        process_col = None
        for col in df.columns:
            if any(keyword in col.lower() for keyword in ['process', 'image', 'executable']):
                process_col = col
                break
        
        if not process_col:
            return {'error': 'No process column found in CSV'}
        
        found_tools = {}
        for _, row in df.iterrows():
            process_name = str(row[process_col]).lower()
            for tool in tools:
                if tool in process_name:
                    host = row.get('host', row.get('hostname', 'unknown'))
                    if tool not in found_tools:
                        found_tools[tool] = set()
                    found_tools[tool].add(host)
        
        # Convert sets to lists for JSON serialization
        result = {tool: list(hosts) for tool, hosts in found_tools.items()}
        return {'tools_found': result, 'total_tools': len(result)}
        
    except Exception as e:
        logger.error(f"Security tools analysis error: {e}")
        return {'error': str(e)}

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

# Security tools analysis endpoint
@app.route('/api/analyze/security-tools/<filename>')
def analyze_security_tools_endpoint(filename):
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        result = analyze_security_tools(filepath)
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Security tools analysis endpoint error: {e}")
        return jsonify({'error': 'Analysis failed'}), 500

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
        
        # CSV specific analysis (only if pandas is available)
        if filename.lower().endswith('.csv') and PANDAS_AVAILABLE:
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
