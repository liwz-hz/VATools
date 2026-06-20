from datetime import datetime, timezone
from app import db
import json

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    input_file = db.Column(db.String(255), nullable=False)
    output_file = db.Column(db.String(255))
    params = db.Column(db.Text)
    progress = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)
    
    def set_params(self, params_dict):
        self.params = json.dumps(params_dict)
    
    def get_params(self):
        return json.loads(self.params) if self.params else {}
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_type': self.task_type,
            'status': self.status,
            'input_file': self.input_file,
            'output_file': self.output_file,
            'params': self.get_params(),
            'progress': self.progress,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(20))
    file_size = db.Column(db.Integer)
    duration = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'duration': self.duration,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Config(db.Model):
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'key': self.key,
            'value': self.value,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
