import os
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
from app import db
from app.models import File
from app.config import Config

bp = Blueprint('files', __name__, url_prefix='/api/files')

ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'flac', 'aac', 'ogg'}

def allowed_file(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext in ALLOWED_VIDEO_EXTENSIONS or ext in ALLOWED_AUDIO_EXTENSIONS

def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return 'video' if ext in ALLOWED_VIDEO_EXTENSIONS else 'audio'

@bp.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Supported: {", ".join(ALLOWED_VIDEO_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS)}'}), 400
    
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    file_path = os.path.join(Config.UPLOAD_DIR, unique_filename)
    
    file.save(file_path)
    file_size = os.path.getsize(file_path)
    
    if file_size > Config.MAX_FILE_SIZE:
        os.remove(file_path)
        return jsonify({'error': f'File too large. Max size: {Config.MAX_FILE_SIZE // (1024*1024)}MB'}), 400
    
    file_type = get_file_type(filename)
    
    db_file = File(
        filename=unique_filename,
        file_path=file_path,
        file_type=file_type,
        file_size=file_size
    )
    db.session.add(db_file)
    db.session.commit()
    
    return jsonify(db_file.to_dict()), 201

@bp.route('', methods=['GET'])
def get_files():
    files = File.query.order_by(File.created_at.desc()).all()
    return jsonify([f.to_dict() for f in files])

@bp.route('/<int:file_id>', methods=['GET'])
def get_file(file_id):
    file = File.query.get_or_404(file_id)
    return jsonify(file.to_dict())

@bp.route('/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    file = File.query.get_or_404(file_id)
    
    if os.path.exists(file.file_path):
        os.remove(file.file_path)
    
    db.session.delete(file)
    db.session.commit()
    
    return jsonify({'message': 'File deleted successfully'})

@bp.route('/<int:file_id>/download', methods=['GET'])
def download_file(file_id):
    file = File.query.get_or_404(file_id)
    
    if not os.path.exists(file.file_path):
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(file.file_path, as_attachment=True, download_name=file.filename)
