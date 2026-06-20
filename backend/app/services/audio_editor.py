import os
import threading
from datetime import datetime
from pathlib import Path
from app import db, socketio
from app.models import Task, File
from app.utils.ffmpeg_utils import clip_audio, get_audio_duration
from app.config import Config
from loguru import logger

def process_audio_clip(task_id):
    with db.app.app_context():
        task = Task.query.get(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return
        
        task.status = 'processing'
        db.session.commit()
        
        try:
            params = task.get_params()
            audio_file = File.query.get(params['audio_file_id'])
            
            if not audio_file or not os.path.exists(audio_file.file_path):
                raise Exception(f"Audio file not found: {task.input_file}")
            
            operation = params['operation']
            start_time = params['start_time']
            end_time = params['end_time']
            output_format = params.get('output_format', 'mp3')
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if operation == 'extract':
                output_filename = f"{timestamp}_clip_{Path(audio_file.filename).stem}.{output_format}"
                output_path = os.path.join(Config.WORKSPACE_DIR, 'edited', output_filename)
                
                socketio.emit('task_progress', {
                    'task_id': task.id,
                    'progress': 10,
                    'status': 'processing'
                })
                
                success, error = clip_audio(
                    audio_file.file_path,
                    output_path,
                    start_time,
                    end_time,
                    output_format
                )
                
                if not success:
                    raise Exception(error)
            
            elif operation == 'delete':
                duration = get_audio_duration(audio_file.file_path)
                if duration is None:
                    raise Exception("Could not get audio duration")
                
                output_filename = f"{timestamp}_edited_{Path(audio_file.filename).stem}.{output_format}"
                output_path = os.path.join(Config.WORKSPACE_DIR, 'edited', output_filename)
                
                temp_parts = []
                if start_time > 0:
                    part1_path = output_path.replace('.mp3', '_part1.mp3')
                    success, error = clip_audio(
                        audio_file.file_path,
                        part1_path,
                        0,
                        start_time,
                        output_format
                    )
                    if success:
                        temp_parts.append(part1_path)
                
                if end_time < duration:
                    part2_path = output_path.replace('.mp3', '_part2.mp3')
                    success, error = clip_audio(
                        audio_file.file_path,
                        part2_path,
                        end_time,
                        duration,
                        output_format
                    )
                    if success:
                        temp_parts.append(part2_path)
                
                if len(temp_parts) == 0:
                    raise Exception("Nothing to process")
                elif len(temp_parts) == 1:
                    os.rename(temp_parts[0], output_path)
                else:
                    import subprocess
                    concat_file = output_path + '.txt'
                    with open(concat_file, 'w') as f:
                        for part in temp_parts:
                            f.write(f"file '{part}'\n")
                    
                    cmd = [
                        'ffmpeg',
                        '-f', 'concat',
                        '-safe', '0',
                        '-i', concat_file,
                        '-c', 'copy',
                        '-y',
                        output_path
                    ]
                    
                    subprocess.run(cmd, capture_output=True, check=True)
                    os.remove(concat_file)
                    for part in temp_parts:
                        os.remove(part)
            
            else:
                raise Exception(f"Unknown operation: {operation}")
            
            duration = get_audio_duration(output_path)
            
            output_file = File(
                filename=output_filename,
                file_path=output_path,
                file_type='audio',
                file_size=os.path.getsize(output_path),
                duration=duration
            )
            db.session.add(output_file)
            
            task.output_file = output_path
            task.status = 'completed'
            task.progress = 100
            task.completed_at = datetime.utcnow()
            db.session.commit()
            
            socketio.emit('task_completed', {
                'task_id': task.id,
                'output_file': output_filename,
                'file_id': output_file.id
            })
            
            logger.info(f"Audio clip task {task_id} completed")
            
        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
            db.session.commit()
            
            socketio.emit('task_failed', {
                'task_id': task.id,
                'error': str(e)
            })
            
            logger.error(f"Audio clip task {task_id} failed: {str(e)}")

def start_audio_clip(audio_file_id, operation, start_time, end_time, output_format='mp3'):
    audio_file = File.query.get(audio_file_id)
    if not audio_file:
        return None, "Audio file not found"
    
    task = Task(
        task_type='audio_clip',
        status='pending',
        input_file=audio_file.file_path
    )
    task.set_params({
        'audio_file_id': audio_file_id,
        'operation': operation,
        'start_time': start_time,
        'end_time': end_time,
        'output_format': output_format
    })
    
    db.session.add(task)
    db.session.commit()
    
    thread = threading.Thread(target=process_audio_clip, args=(task.id,))
    thread.start()
    
    return task.id, None
