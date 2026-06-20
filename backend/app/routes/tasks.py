from flask import Blueprint, jsonify, request
from app import db
from app.models import Task

bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')

@bp.route('', methods=['GET'])
def get_tasks():
    task_type = request.args.get('task_type')
    status = request.args.get('status')
    
    query = Task.query
    
    if task_type:
        query = query.filter_by(task_type=task_type)
    if status:
        query = query.filter_by(status=status)
    
    tasks = query.order_by(Task.created_at.desc()).all()
    return jsonify([t.to_dict() for t in tasks])

@bp.route('/<int:task_id>', methods=['GET'])
def get_task(task_id):
    task = Task.query.get_or_404(task_id)
    return jsonify(task.to_dict())

@bp.route('/<int:task_id>', methods=['DELETE'])
def cancel_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    if task.status in ['completed', 'failed']:
        return jsonify({'error': 'Cannot cancel completed or failed task'}), 400
    
    task.status = 'cancelled'
    task.error_message = 'Task cancelled by user'
    db.session.commit()
    
    return jsonify({'message': 'Task cancelled successfully'})
