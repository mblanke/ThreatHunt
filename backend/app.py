import os
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from werkzeug.utils import secure_filename
import bcrypt

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

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://admin:secure_password_123@localhost:5432/threat_hunter')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-this-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploaded'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'json', 'txt', 'log'}

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)

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

# Database Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

class Hunt(db.Model):
    __tablename__ = 'hunts'
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.String, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='active')

# Authentication Routes
@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            access_token = create_access_token(identity=user.id)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                'access_token': access_token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            })
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400
            
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Create user
        user = User(username=username, email=email, password_hash=password_hash)
        db.session.add(user)
        db.session.commit()
        
        access_token = create_access_token(identity=user.id)
        
        return jsonify({
            'access_token': access_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        })
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500

# Hunt Management Routes
@app.route('/api/hunts', methods=['GET'])
@jwt_required()
def get_hunts():
    try:
        user_id = get_jwt_identity()
        hunts = Hunt.query.filter_by(created_by=user_id).all()
        
        return jsonify({
            'hunts': [{
                'id': hunt.id,
                'name': hunt.name,
                'description': hunt.description,
                'created_at': hunt.created_at.isoformat(),
                'status': hunt.status
            } for hunt in hunts]
        })
    except Exception as e:
        logger.error(f"Get hunts error: {e}")
        return jsonify({'error': 'Failed to fetch hunts'}), 500

@app.route('/api/hunts', methods=['POST'])
@jwt_required()
def create_hunt():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        hunt = Hunt(
            name=data.get('name'),
            description=data.get('description'),
            created_by=user_id
        )
        
        db.session.add(hunt)
        db.session.commit()
        
        return jsonify({
            'hunt': {
                'id': hunt.id,
                'name': hunt.name,
                'description': hunt.description,
                'created_at': hunt.created_at.isoformat(),
                'status': hunt.status
            }
        })
    except Exception as e:
        logger.error(f"Create hunt error: {e}")
        return jsonify({'error': 'Failed to create hunt'}), 500

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
@app.route("/assets/<path:path>")
def send_assets(path):
    return send_from_directory(os.path.join(app.static_folder, "assets"), path)

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

# Catch-all route for React Router
@app.route("/<path:path>")
def catch_all(path):
    if os.path.exists(os.path.join(app.static_folder, "index.html")):
        return send_from_directory(app.static_folder, "index.html")
    else:
        return jsonify({'error': 'Frontend not built yet'})

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    
    print("=" * 50)
    print("Starting Cyber Threat Hunter Backend...")
    print("API available at: http://localhost:5000")
    print("Database: Connected to PostgreSQL")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)
