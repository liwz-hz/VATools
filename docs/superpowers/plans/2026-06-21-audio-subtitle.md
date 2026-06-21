# Audio Auto-Subtitle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Auto Subtitle" feature to VATools that transcribes audio to timestamped subtitles using Qwen3-ASR via mlx-audio, with editable preview and SRT/VTT export.

**Architecture:** Backend service loads local Qwen3-ASR model via mlx-audio Python API, runs transcription in a background thread (matching existing task pattern), returns structured segments (text + timestamps). Frontend displays an editable subtitle list table with export to SRT/VTT/JSON.

**Tech Stack:** Flask, mlx-audio 0.4.4, React 18, MUI 5, TypeScript, Vite

## Global Constraints

- Models loaded from local filesystem only — never download from HuggingFace or any remote source
- Use locally installed package versions; pin all deps in `requirements.txt`
- Default ASR model: `Qwen3-ASR-1.7B-8bit` at configured `ASR_MODEL_DIR`
- Default `ASR_MODEL_DIR`: `/Users/lwz/.cache/modelscope/hub/models/mlx-community`
- Follow existing patterns: threading for background tasks, Socket.IO for progress, MUI components

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/services/audio_subtitle.py` | Create | ASR model scanning, transcription, subtitle file generation |
| `backend/tests/test_audio_subtitle.py` | Create | Unit tests for subtitle service |
| `frontend/src/components/AudioSubtitle.tsx` | Create | Subtitle tab UI component |
| `backend/app/routes/audio.py` | Modify | Add 4 subtitle API routes |
| `backend/app/config.py` | Modify | Add `ASR_MODEL_DIR`, `ASR_DEFAULT_MODEL` |
| `backend/app/routes/config.py` | Modify | Add ASR config to `DEFAULT_CONFIG` |
| `backend/requirements.txt` | Modify | Add `mlx-audio==0.4.4` |
| `frontend/src/services/api.ts` | Modify | Add 4 subtitle API functions |
| `frontend/src/App.tsx` | Modify | Add "Auto Subtitle" tab |
| `frontend/src/components/Settings.tsx` | Modify | Add ASR settings section |

---

### Task 1: Backend Config — Add ASR Configuration

**Files:**
- Modify: `backend/app/config.py:27-30`
- Modify: `backend/app/routes/config.py:10-25`

**Interfaces:**
- Produces: `Config.ASR_MODEL_DIR` (str), `Config.ASR_DEFAULT_MODEL` (str) — used by Task 2

- [ ] **Step 1: Add ASR config to `config.py`**

Add after line 30 (after `SEPARATION_MODEL_DIR`):

```python
    ASR_MODEL_DIR = '/Users/lwz/.cache/modelscope/hub/models/mlx-community'
    ASR_DEFAULT_MODEL = 'Qwen3-ASR-1.7B-8bit'
```

- [ ] **Step 2: Add ASR config to `DEFAULT_CONFIG` in `routes/config.py`**

Add to the `DEFAULT_CONFIG` dict (after `separation_model_dir`):

```python
    'asr_model_dir': AppConfig.ASR_MODEL_DIR,
    'asr_default_model': AppConfig.ASR_DEFAULT_MODEL,
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py backend/app/routes/config.py
git commit -m "feat: add ASR model configuration"
```

---

### Task 2: Backend Service — ASR Model Scanning & Status

**Files:**
- Create: `backend/app/services/audio_subtitle.py`
- Create: `backend/tests/test_audio_subtitle.py`

**Interfaces:**
- Consumes: `Config.ASR_MODEL_DIR` from Task 1
- Produces: `scan_asr_models(model_dir) -> dict`, `get_asr_status() -> dict` — used by Task 3 and Task 4

- [ ] **Step 1: Write failing test for `scan_asr_models`**

Create `backend/tests/test_audio_subtitle.py`:

```python
import pytest
import os
import json
import tempfile
from pathlib import Path
from app import create_app, db
from app.models import File, Task


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_scan_asr_models_finds_valid_models():
    with tempfile.TemporaryDirectory() as tmpdir:
        model_dir = Path(tmpdir) / 'Qwen3-ASR-1.7B-8bit'
        model_dir.mkdir()
        (model_dir / 'config.json').write_text('{}')
        (model_dir / 'model.safetensors').write_text('')

        from app.services.audio_subtitle import scan_asr_models
        result = scan_asr_models(tmpdir)

        assert 'Qwen3-ASR-1.7B-8bit' in result
        assert result['Qwen3-ASR-1.7B-8bit'] == str(model_dir)


def test_scan_asr_models_ignores_incomplete():
    with tempfile.TemporaryDirectory() as tmpdir:
        model_dir = Path(tmpdir) / 'incomplete-model'
        model_dir.mkdir()
        (model_dir / 'config.json').write_text('{}')

        from app.services.audio_subtitle import scan_asr_models
        result = scan_asr_models(tmpdir)

        assert len(result) == 0


def test_scan_asr_models_nonexistent_dir():
    from app.services.audio_subtitle import scan_asr_models
    result = scan_asr_models('/nonexistent/path')
    assert result == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source venv/bin/activate && python -m pytest tests/test_audio_subtitle.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.audio_subtitle'`

- [ ] **Step 3: Implement `scan_asr_models` and `get_asr_status`**

Create `backend/app/services/audio_subtitle.py`:

```python
import os
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from flask import current_app
from app import db, socketio
from app.models import Task, File
from app.config import Config
from loguru import logger
from sqlalchemy.orm import scoped_session, sessionmaker

_model_cache = {}


def scan_asr_models(model_dir: str = None) -> dict:
    if model_dir is None:
        model_dir = _get_asr_model_dir()

    model_path = Path(model_dir).expanduser()
    if not model_path.exists():
        return {}

    models = {}
    for entry in model_path.iterdir():
        if not entry.is_dir():
            continue
        if not (entry / 'config.json').exists():
            continue
        has_model = (entry / 'model.safetensors').exists()
        has_index = (entry / 'model.safetensors.index.json').exists()
        if has_model or has_index:
            config_data = {}
            try:
                config_data = json.loads((entry / 'config.json').read_text())
            except (json.JSONDecodeError, OSError):
                pass
            model_type = config_data.get('model_type', '')
            if 'asr' in model_type.lower() or 'asr' in entry.name.lower():
                models[entry.name] = str(entry)

    return models


def _get_asr_model_dir() -> str:
    try:
        from app.models import Config as ConfigModel
        config = ConfigModel.query.filter_by(key='asr_model_dir').first()
        if config and config.value:
            return config.value
    except Exception:
        pass
    return Config.ASR_MODEL_DIR


def get_asr_status() -> dict:
    model_dir = _get_asr_model_dir()
    models = scan_asr_models(model_dir)

    mlx_audio_available = False
    try:
        import mlx_audio
        mlx_audio_available = True
    except ImportError:
        pass

    return {
        'model_dir': model_dir,
        'models': {name: {'path': path} for name, path in models.items()},
        'mlx_audio_available': mlx_audio_available,
        'default_model': Config.ASR_DEFAULT_MODEL,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && python -m pytest tests/test_audio_subtitle.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/audio_subtitle.py backend/tests/test_audio_subtitle.py
git commit -m "feat: add ASR model scanning and status service"
```

---

### Task 3: Backend Service — Subtitle Transcription & Export

**Files:**
- Modify: `backend/app/services/audio_subtitle.py`
- Modify: `backend/tests/test_audio_subtitle.py`

**Interfaces:**
- Consumes: `scan_asr_models()`, `_get_asr_model_dir()` from Task 2
- Produces: `start_audio_subtitle(audio_file_id, model, language) -> tuple[int, str|None]`, `process_audio_subtitle(task_id, app)`, `generate_subtitle_file(segments, format, output_path)`, `format_timestamp(seconds) -> str` — used by Task 4

- [ ] **Step 1: Write failing tests for subtitle generation**

Append to `backend/tests/test_audio_subtitle.py`:

```python
def test_format_timestamp():
    from app.services.audio_subtitle import format_timestamp
    assert format_timestamp(0) == '00:00:00,000'
    assert format_timestamp(1.5) == '00:00:01,500'
    assert format_timestamp(3661.123) == '01:01:01,123'


def test_generate_subtitle_file_srt():
    import tempfile
    from app.services.audio_subtitle import generate_subtitle_file

    segments = [
        {'id': 1, 'start': 0.0, 'end': 2.5, 'text': 'Hello world'},
        {'id': 2, 'start': 2.5, 'end': 5.0, 'text': 'Test subtitle'},
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
        output_path = f.name

    try:
        generate_subtitle_file(segments, 'srt', output_path)
        content = Path(output_path).read_text()
        assert '1\n' in content
        assert 'Hello world' in content
        assert '00:00:00,000 --> 00:00:02,500' in content
        assert '2\n' in content
        assert 'Test subtitle' in content
    finally:
        os.unlink(output_path)


def test_generate_subtitle_file_vtt():
    import tempfile
    from app.services.audio_subtitle import generate_subtitle_file

    segments = [
        {'id': 1, 'start': 0.0, 'end': 2.5, 'text': 'Hello world'},
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
        output_path = f.name

    try:
        generate_subtitle_file(segments, 'vtt', output_path)
        content = Path(output_path).read_text()
        assert 'WEBVTT' in content
        assert 'Hello world' in content
        assert '00:00:00.000 --> 00:00:02.500' in content
    finally:
        os.unlink(output_path)


def test_start_subtitle_missing_file(app):
    with app.app_context():
        from app.services.audio_subtitle import start_audio_subtitle
        task_id, error = start_audio_subtitle(999)
        assert task_id is None
        assert error is not None


def test_start_subtitle_creates_task(app):
    with app.app_context():
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mp3', delete=False) as f:
            temp_path = f.name

        try:
            audio_file = File(
                filename='test.mp3',
                file_path=temp_path,
                file_type='audio',
                file_size=1000
            )
            db.session.add(audio_file)
            db.session.commit()

            from app.services.audio_subtitle import start_audio_subtitle
            task_id, error = start_audio_subtitle(audio_file.id)

            assert task_id is not None
            assert error is None

            task = db.session.get(Task, task_id)
            assert task.task_type == 'audio_subtitle'
            assert task.status == 'pending'
            params = task.get_params()
            assert params['audio_file_id'] == audio_file.id
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && python -m pytest tests/test_audio_subtitle.py -v`
Expected: FAIL — `ImportError: cannot import name 'format_timestamp'`

- [ ] **Step 3: Implement subtitle generation functions**

Append to `backend/app/services/audio_subtitle.py`:

```python
def format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f'{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}'


def format_timestamp_vtt(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f'{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}'


def generate_subtitle_file(segments: list, format: str, output_path: str):
    with open(output_path, 'w', encoding='utf-8') as f:
        if format == 'srt':
            for i, seg in enumerate(segments, 1):
                f.write(f"{i}\n")
                f.write(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}\n")
                f.write(f"{seg['text']}\n\n")
        elif format == 'vtt':
            f.write("WEBVTT\n\n")
            for seg in segments:
                f.write(f"{format_timestamp_vtt(seg['start'])} --> {format_timestamp_vtt(seg['end'])}\n")
                f.write(f"{seg['text']}\n\n")
        elif format == 'json':
            json.dump({'segments': segments}, f, ensure_ascii=False, indent=2)


def start_audio_subtitle(audio_file_id: int, model: str = None, language: str = 'auto'):
    audio_file = db.session.get(File, audio_file_id)
    if not audio_file:
        return None, "音频文件未找到"

    if model is None:
        model = Config.ASR_DEFAULT_MODEL

    task = Task(
        task_type='audio_subtitle',
        status='pending',
        input_file=audio_file.file_path
    )
    task.set_params({
        'audio_file_id': audio_file_id,
        'model': model,
        'language': language,
    })

    db.session.add(task)
    db.session.commit()

    app = current_app._get_current_object()
    thread = threading.Thread(target=process_audio_subtitle, args=(task.id, app))
    thread.daemon = True
    thread.start()

    return task.id, None


def process_audio_subtitle(task_id: int, app):
    with app.app_context():
        session = scoped_session(sessionmaker(bind=db.engine))

        try:
            task = session.query(Task).filter_by(id=task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            task.status = 'processing'
            session.commit()

            params = task.get_params()
            audio_file = session.query(File).filter_by(id=params['audio_file_id']).first()

            if not audio_file or not os.path.exists(audio_file.file_path):
                raise Exception(f"音频文件未找到: {task.input_file}")

            model_name = params.get('model', Config.ASR_DEFAULT_MODEL)

            socketio.emit('task_progress', {
                'task_id': task.id,
                'progress': 5,
                'status': '加载模型...'
            }, namespace='/')

            model_path = _resolve_model_path(model_name)
            if not model_path:
                raise Exception(
                    f"未找到 ASR 模型: {model_name}\n"
                    f"请检查模型目录配置: {_get_asr_model_dir()}"
                )

            model = _load_model(model_path)

            socketio.emit('task_progress', {
                'task_id': task.id,
                'progress': 30,
                'status': '开始转录...'
            }, namespace='/')

            from mlx_audio.stt.generate import generate_transcription

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = os.path.join(Config.WORKSPACE_DIR, 'subtitles')
            os.makedirs(output_dir, exist_ok=True)
            json_output = os.path.join(output_dir, f'{timestamp}_result')

            result = generate_transcription(
                model=model,
                audio=audio_file.file_path,
                output_path=json_output,
                format='json',
                verbose=False,
            )

            socketio.emit('task_progress', {
                'task_id': task.id,
                'progress': 80,
                'status': '生成字幕文件...'
            }, namespace='/')

            segments = _parse_result(result)

            json_path = f'{json_output}.json'
            segments_data = {
                'text': result.text if hasattr(result, 'text') else '',
                'segments': segments,
                'language': result.language if hasattr(result, 'language') else 'unknown',
            }
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(segments_data, f, ensure_ascii=False, indent=2)

            task.output_file = json_path
            task.status = 'completed'
            task.progress = 100
            task.completed_at = datetime.now(timezone.utc)
            session.commit()

            socketio.emit('task_completed', {
                'task_id': task.id,
                'output_file': json_path,
            }, namespace='/')

            logger.info(f"Subtitle task {task_id} completed: {len(segments)} segments")

        except Exception as e:
            task = session.query(Task).filter_by(id=task_id).first()
            if task:
                task.status = 'failed'
                task.error_message = str(e)
                session.commit()

                socketio.emit('task_failed', {
                    'task_id': task.id,
                    'error': str(e)
                }, namespace='/')

                logger.error(f"Subtitle task {task_id} failed: {str(e)}")
        finally:
            session.remove()


def _resolve_model_path(model_name: str) -> str:
    model_dir = _get_asr_model_dir()
    model_path = Path(model_dir) / model_name
    if model_path.exists() and (model_path / 'config.json').exists():
        return str(model_path)

    models = scan_asr_models(model_dir)
    if model_name in models:
        return models[model_name]

    return None


def _load_model(model_path: str):
    if model_path in _model_cache:
        return _model_cache[model_path]

    from mlx_audio.stt.utils import load_model
    model = load_model(model_path)
    _model_cache[model_path] = model
    return model


def _parse_result(result) -> list:
    segments = []

    if hasattr(result, 'segments') and result.segments:
        for i, seg in enumerate(result.segments):
            if isinstance(seg, dict):
                segments.append({
                    'id': i + 1,
                    'start': seg.get('start', 0),
                    'end': seg.get('end', 0),
                    'text': seg.get('text', '').strip(),
                })
            else:
                segments.append({
                    'id': i + 1,
                    'start': getattr(seg, 'start', 0) or getattr(seg, 'start_time', 0) or 0,
                    'end': getattr(seg, 'end', 0) or getattr(seg, 'end_time', 0) or 0,
                    'text': (getattr(seg, 'text', '') or '').strip(),
                })
    elif hasattr(result, 'text'):
        segments.append({
            'id': 1,
            'start': 0,
            'end': 0,
            'text': result.text.strip(),
        })

    return segments
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && python -m pytest tests/test_audio_subtitle.py -v`
Expected: All tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/audio_subtitle.py backend/tests/test_audio_subtitle.py
git commit -m "feat: add subtitle transcription, export, and task processing"
```

---

### Task 4: Backend Routes — Subtitle API Endpoints

**Files:**
- Modify: `backend/app/routes/audio.py`
- Modify: `backend/tests/test_audio_subtitle.py`

**Interfaces:**
- Consumes: `start_audio_subtitle()`, `get_asr_status()`, `generate_subtitle_file()` from Task 3
- Produces: 4 API endpoints — used by Task 6 (frontend)

- [ ] **Step 1: Write failing tests for API routes**

Append to `backend/tests/test_audio_subtitle.py`:

```python
def test_subtitle_api_missing_file_id(client):
    response = client.post('/api/audio/subtitle',
                          json={},
                          content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data


def test_subtitle_api_success(client, app):
    with app.app_context():
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mp3', delete=False) as f:
            temp_path = f.name

        try:
            audio_file = File(
                filename='test.mp3',
                file_path=temp_path,
                file_type='audio',
                file_size=1000
            )
            db.session.add(audio_file)
            db.session.commit()
            file_id = audio_file.id
        finally:
            pass

    response = client.post('/api/audio/subtitle',
                          json={'audio_file_id': file_id},
                          content_type='application/json')
    assert response.status_code == 201
    data = response.get_json()
    assert 'task_id' in data

    if os.path.exists(temp_path):
        os.unlink(temp_path)


def test_subtitle_status_api(client):
    response = client.get('/api/audio/subtitle/status')
    assert response.status_code == 200
    data = response.get_json()
    assert 'models' in data
    assert 'mlx_audio_available' in data


def test_subtitle_result_not_found(client):
    response = client.get('/api/audio/subtitle/999/result')
    assert response.status_code == 404


def test_subtitle_export_missing_task(client):
    response = client.post('/api/audio/subtitle/999/export',
                          json={'format': 'srt'},
                          content_type='application/json')
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && python -m pytest tests/test_audio_subtitle.py::test_subtitle_api_missing_file_id -v`
Expected: FAIL — route not found (404)

- [ ] **Step 3: Add subtitle routes to `audio.py`**

Add imports at top of `backend/app/routes/audio.py`:

```python
from app.services.audio_subtitle import (
    start_audio_subtitle,
    get_asr_status,
    generate_subtitle_file,
)
```

Add routes at end of `backend/app/routes/audio.py`:

```python
@bp.route('/subtitle', methods=['POST'])
def subtitle():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    audio_file_id = data.get('audio_file_id')
    model = data.get('model')
    language = data.get('language', 'auto')

    if not audio_file_id:
        return jsonify({'error': 'audio_file_id is required'}), 400

    try:
        audio_file_id = int(audio_file_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'audio_file_id must be a valid integer'}), 400

    task_id, error = start_audio_subtitle(audio_file_id, model, language)

    if error:
        return jsonify({'error': error}), 400

    return jsonify({'task_id': task_id, 'status': 'pending'}), 201


@bp.route('/subtitle/status', methods=['GET'])
def subtitle_status():
    status = get_asr_status()
    return jsonify(status)


@bp.route('/subtitle/<int:task_id>/result', methods=['GET'])
def subtitle_result(task_id):
    task = Task.query.get_or_404(task_id)

    if task.task_type != 'audio_subtitle':
        return jsonify({'error': 'Not a subtitle task'}), 400

    if task.status != 'completed' or not task.output_file:
        return jsonify({'error': 'Task not completed'}), 400

    if not os.path.exists(task.output_file):
        return jsonify({'error': 'Result file not found'}), 404

    with open(task.output_file, 'r', encoding='utf-8') as f:
        result = json.load(f)

    return jsonify(result)


@bp.route('/subtitle/<int:task_id>/export', methods=['POST'])
def subtitle_export(task_id):
    task = Task.query.get_or_404(task_id)

    if task.task_type != 'audio_subtitle':
        return jsonify({'error': 'Not a subtitle task'}), 400

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    export_format = data.get('format', 'srt')
    if export_format not in ('srt', 'vtt', 'json'):
        return jsonify({'error': 'Invalid format. Use srt, vtt, or json'}), 400

    segments = data.get('segments')

    if not segments:
        if task.status == 'completed' and task.output_file and os.path.exists(task.output_file):
            with open(task.output_file, 'r', encoding='utf-8') as f:
                result_data = json.load(f)
            segments = result_data.get('segments', [])
        else:
            return jsonify({'error': 'No segments available'}), 400

    import tempfile
    suffix = f'.{export_format}'
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
        temp_path = f.name

    generate_subtitle_file(segments, export_format, temp_path)

    from flask import send_file
    mime_types = {
        'srt': 'text/plain',
        'vtt': 'text/vtt',
        'json': 'application/json',
    }

    return send_file(
        temp_path,
        mimetype=mime_types.get(export_format, 'text/plain'),
        as_attachment=True,
        download_name=f'subtitle.{export_format}'
    )
```

Add missing import at top of `audio.py`:

```python
import os
import json
from app.models import Task
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && python -m pytest tests/test_audio_subtitle.py -v`
Expected: All tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/audio.py backend/tests/test_audio_subtitle.py
git commit -m "feat: add subtitle API routes (start, status, result, export)"
```

---

### Task 5: Backend Dependencies — Update requirements.txt

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add mlx-audio to requirements.txt**

Append to `backend/requirements.txt`:

```
# ASR语音识别
mlx-audio==0.4.4
```

- [ ] **Step 2: Verify mlx-audio is installed in venv**

Run: `cd backend && source venv/bin/activate && pip install mlx-audio==0.4.4`

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add mlx-audio dependency for ASR"
```

---

### Task 6: Frontend — API Functions

**Files:**
- Modify: `frontend/src/services/api.ts`

**Interfaces:**
- Produces: `startSubtitle()`, `getSubtitleStatus()`, `getSubtitleResult()`, `exportSubtitle()` — used by Task 7

- [ ] **Step 1: Add subtitle API functions**

Append to `frontend/src/services/api.ts`:

```typescript
export const startSubtitle = async (audioFileId: number, model?: string, language?: string) => {
  const response = await api.post('/audio/subtitle', {
    audio_file_id: audioFileId,
    model,
    language: language || 'auto',
  })
  return response.data
}

export const getSubtitleStatus = async () => {
  const response = await api.get('/audio/subtitle/status')
  return response.data
}

export const getSubtitleResult = async (taskId: number) => {
  const response = await api.get(`/audio/subtitle/${taskId}/result`)
  return response.data
}

export const exportSubtitle = async (taskId: number, format: string, segments?: any[]) => {
  const response = await api.post(
    `/audio/subtitle/${taskId}/export`,
    { format, segments },
    { responseType: 'blob' }
  )
  return response
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat: add subtitle API functions to frontend"
```

---

### Task 7: Frontend — AudioSubtitle Component

**Files:**
- Create: `frontend/src/components/AudioSubtitle.tsx`

**Interfaces:**
- Consumes: `uploadFile()`, `startSubtitle()`, `getSubtitleStatus()`, `getSubtitleResult()`, `exportSubtitle()`, `getTask()` from `api.ts`

- [ ] **Step 1: Create AudioSubtitle.tsx**

Create `frontend/src/components/AudioSubtitle.tsx`:

```tsx
import React, { useState, useCallback, useEffect, useRef } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  Box,
  Paper,
  Typography,
  Button,
  LinearProgress,
  Alert,
  TextField,
  IconButton,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material'
import { CloudUpload, Download, Delete, Add } from '@mui/icons-material'
import {
  uploadFile,
  startSubtitle,
  getSubtitleStatus,
  getSubtitleResult,
  exportSubtitle,
  getTask,
} from '../services/api'

interface FileData {
  id: number
  filename: string
}

interface Segment {
  id: number
  start: number
  end: number
  text: string
}

interface AsrModel {
  path: string
}

const AudioSubtitle: React.FC = () => {
  const [uploadedFile, setUploadedFile] = useState<FileData | null>(null)
  const [models, setModels] = useState<Record<string, AsrModel>>({})
  const [selectedModel, setSelectedModel] = useState('')
  const [language, setLanguage] = useState('auto')
  const [mlxAvailable, setMlxAvailable] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [statusText, setStatusText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [segments, setSegments] = useState<Segment[]>([])
  const [taskId, setTaskId] = useState<number | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    loadStatus()
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const loadStatus = async () => {
    try {
      const status = await getSubtitleStatus()
      setModels(status.models || {})
      setMlxAvailable(status.mlx_audio_available || false)
      if (status.default_model && status.models?.[status.default_model]) {
        setSelectedModel(status.default_model)
      } else {
        const modelNames = Object.keys(status.models || {})
        if (modelNames.length > 0) setSelectedModel(modelNames[0])
      }
    } catch (err) {
      console.error('Failed to load ASR status:', err)
    }
  }

  const onDrop = useCallback(async (acceptedFiles: globalThis.File[]) => {
    const file = acceptedFiles[0]
    if (file) {
      try {
        setError(null)
        setSegments([])
        const uploaded = await uploadFile(file)
        setUploadedFile(uploaded)
      } catch (err: unknown) {
        const e = err as { response?: { data?: { error?: string } } }
        setError(e.response?.data?.error || '上传失败')
      }
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'audio/mpeg': ['.mp3'],
      'audio/wav': ['.wav'],
      'audio/flac': ['.flac'],
    },
    maxFiles: 1,
  })

  const handleStart = async () => {
    if (!uploadedFile) return

    setIsProcessing(true)
    setProgress(0)
    setStatusText('开始处理...')
    setError(null)
    setSegments([])

    try {
      const result = await startSubtitle(uploadedFile.id, selectedModel || undefined, language)
      const id = result.task_id
      setTaskId(id)

      pollRef.current = setInterval(async () => {
        try {
          const task = await getTask(id)
          setProgress(task.progress || 0)
          setStatusText(task.status === 'processing' ? '处理中...' : task.status)

          if (task.status === 'completed') {
            if (pollRef.current) clearInterval(pollRef.current)
            setIsProcessing(false)
            setProgress(100)
            setStatusText('完成')
            await loadResult(id)
          } else if (task.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current)
            setIsProcessing(false)
            setError(task.error_message || '处理失败')
          }
        } catch (err) {
          console.error('Failed to poll task:', err)
        }
      }, 2000)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: string } } }
      setError(e.response?.data?.error || '识别失败')
      setIsProcessing(false)
    }
  }

  const loadResult = async (id: number) => {
    try {
      const result = await getSubtitleResult(id)
      setSegments(result.segments || [])
    } catch (err) {
      console.error('Failed to load result:', err)
      setError('加载结果失败')
    }
  }

  const handleSegmentChange = (index: number, field: keyof Segment, value: string | number) => {
    setSegments((prev) => {
      const updated = [...prev]
      updated[index] = { ...updated[index], [field]: value }
      return updated
    })
  }

  const handleDeleteSegment = (index: number) => {
    setSegments((prev) => prev.filter((_, i) => i !== index))
  }

  const handleAddSegment = () => {
    setSegments((prev) => [
      ...prev,
      {
        id: prev.length + 1,
        start: prev.length > 0 ? prev[prev.length - 1].end : 0,
        end: prev.length > 0 ? prev[prev.length - 1].end + 2 : 2,
        text: '',
      },
    ])
  }

  const handleExport = async (format: string) => {
    if (!taskId) return
    try {
      const response = await exportSubtitle(taskId, format, segments)
      const blob = new Blob([response.data])
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `subtitle.${format}`
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Export failed:', err)
      setError('导出失败')
    }
  }

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          选择音频文件
        </Typography>

        <Box
          {...getRootProps()}
          sx={{
            border: '2px dashed #ccc',
            borderRadius: 2,
            p: 4,
            textAlign: 'center',
            cursor: 'pointer',
            bgcolor: isDragActive ? 'action.hover' : 'background.paper',
            mb: 2,
          }}
        >
          <input {...getInputProps()} />
          <CloudUpload sx={{ fontSize: 48, color: 'primary.main', mb: 1 }} />
          <Typography>
            {isDragActive ? '放下文件以上传' : '拖拽音频文件到此处，或点击选择'}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            支持格式：MP3, WAV, FLAC
          </Typography>
        </Box>

        {uploadedFile && (
          <Alert severity="success" sx={{ mb: 2 }}>
            已上传: {uploadedFile.filename}
          </Alert>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
      </Paper>

      {uploadedFile && !isProcessing && segments.length === 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            识别设置
          </Typography>

          {!mlxAvailable && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              mlx-audio 未安装，请运行: pip install mlx-audio==0.4.4
            </Alert>
          )}

          <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
            <FormControl sx={{ minWidth: 250 }}>
              <InputLabel>ASR 模型</InputLabel>
              <Select
                value={selectedModel}
                label="ASR 模型"
                onChange={(e) => setSelectedModel(e.target.value)}
              >
                {Object.keys(models).map((name) => (
                  <MenuItem key={name} value={name}>
                    {name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl sx={{ minWidth: 150 }}>
              <InputLabel>语言</InputLabel>
              <Select
                value={language}
                label="语言"
                onChange={(e) => setLanguage(e.target.value)}
              >
                <MenuItem value="auto">自动检测</MenuItem>
                <MenuItem value="zh">中文</MenuItem>
                <MenuItem value="en">英文</MenuItem>
                <MenuItem value="ja">日文</MenuItem>
                <MenuItem value="ko">韩文</MenuItem>
              </Select>
            </FormControl>
          </Box>

          <Button
            variant="contained"
            color="primary"
            fullWidth
            onClick={handleStart}
            disabled={!mlxAvailable || Object.keys(models).length === 0}
          >
            开始识别
          </Button>
        </Paper>
      )}

      {isProcessing && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            识别中...
          </Typography>
          <LinearProgress variant="determinate" value={progress} sx={{ mb: 1 }} />
          <Typography variant="body2" color="text.secondary">
            {progress}% - {statusText}
          </Typography>
        </Paper>
      )}

      {segments.length > 0 && (
        <Paper sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">
              字幕结果 ({segments.length} 条)
            </Typography>
            <Button startIcon={<Add />} onClick={handleAddSegment} size="small">
              添加字幕
            </Button>
          </Box>

          <TableContainer sx={{ maxHeight: 500 }}>
            <Table stickyHeader size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ width: 50 }}>#</TableCell>
                  <TableCell sx={{ width: 120 }}>开始时间(s)</TableCell>
                  <TableCell sx={{ width: 120 }}>结束时间(s)</TableCell>
                  <TableCell>字幕文本</TableCell>
                  <TableCell sx={{ width: 60 }}>操作</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {segments.map((seg, index) => (
                  <TableRow key={index}>
                    <TableCell>{index + 1}</TableCell>
                    <TableCell>
                      <TextField
                        type="number"
                        size="small"
                        value={seg.start}
                        onChange={(e) => handleSegmentChange(index, 'start', parseFloat(e.target.value) || 0)}
                        inputProps={{ step: 0.1, min: 0 }}
                        sx={{ width: 100 }}
                      />
                    </TableCell>
                    <TableCell>
                      <TextField
                        type="number"
                        size="small"
                        value={seg.end}
                        onChange={(e) => handleSegmentChange(index, 'end', parseFloat(e.target.value) || 0)}
                        inputProps={{ step: 0.1, min: 0 }}
                        sx={{ width: 100 }}
                      />
                    </TableCell>
                    <TableCell>
                      <TextField
                        fullWidth
                        size="small"
                        value={seg.text}
                        onChange={(e) => handleSegmentChange(index, 'text', e.target.value)}
                      />
                    </TableCell>
                    <TableCell>
                      <IconButton size="small" onClick={() => handleDeleteSegment(index)} color="error">
                        <Delete />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
            <Button variant="contained" startIcon={<Download />} onClick={() => handleExport('srt')}>
              导出 SRT
            </Button>
            <Button variant="outlined" startIcon={<Download />} onClick={() => handleExport('vtt')}>
              导出 VTT
            </Button>
            <Button variant="outlined" startIcon={<Download />} onClick={() => handleExport('json')}>
              导出 JSON
            </Button>
          </Box>
        </Paper>
      )}
    </Box>
  )
}

export default AudioSubtitle
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/AudioSubtitle.tsx
git commit -m "feat: add AudioSubtitle component with editable list and export"
```

---

### Task 8: Frontend — Wire Up Tab and Settings

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Settings.tsx`

- [ ] **Step 1: Add tab to App.tsx**

In `frontend/src/App.tsx`, add import:

```typescript
import AudioSubtitle from './components/AudioSubtitle'
```

Add Tab label (after "音源分离", before "设置"):

```tsx
<Tab label="自动字幕" />
```

Update tab indices — change Settings from index 3 to 4:

```tsx
{currentTab === 0 && <AudioExtractor />}
{currentTab === 1 && <AudioEditor />}
{currentTab === 2 && <AudioSeparator />}
{currentTab === 3 && <AudioSubtitle />}
{currentTab === 4 && <Settings />}
```

- [ ] **Step 2: Add ASR settings section to Settings.tsx**

Add imports at top of `Settings.tsx`:

```typescript
import { getSubtitleStatus } from '../services/api'
```

Add state variables inside the `Settings` component:

```typescript
const [asrModels, setAsrModels] = useState<Record<string, any>>({})
```

Add to `useEffect` (alongside `loadConfig()` and `loadEngineStatus()`):

```typescript
loadAsrStatus()
```

Add function inside the component:

```typescript
const loadAsrStatus = async () => {
  try {
    const status = await getSubtitleStatus()
    setAsrModels(status.models || {})
  } catch (err) {
    console.error('Failed to load ASR status:', err)
  }
}
```

Add new Paper section before the save/reset buttons (after the "音源分离设置" Paper):

```tsx
<Paper sx={{ p: 3, mb: 3 }}>
  <Typography variant="h6" gutterBottom>
    ASR 语音识别设置
  </Typography>

  <Grid container spacing={2}>
    <Grid item xs={12}>
      <TextField
        fullWidth
        label="ASR 模型目录路径"
        placeholder="/Users/lwz/.cache/modelscope/hub/models/mlx-community"
        value={config.asr_model_dir || ''}
        onChange={(e) => handleChange('asr_model_dir', e.target.value)}
        helperText="包含 Qwen3-ASR 等模型的目录"
        InputProps={{
          startAdornment: <Folder sx={{ mr: 1, color: 'action.active' }} />
        }}
      />
    </Grid>

    <Grid item xs={12}>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        检测到的 ASR 模型:
      </Typography>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        {Object.keys(asrModels).length > 0 ? (
          Object.keys(asrModels).map((name) => (
            <Chip key={name} label={name} size="small" color="primary" />
          ))
        ) : (
          <Typography variant="body2" color="text.disabled">
            未检测到 ASR 模型
          </Typography>
        )}
      </Box>
    </Grid>

    <Grid item xs={12}>
      <Button
        variant="outlined"
        startIcon={<Search />}
        onClick={loadAsrStatus}
      >
        刷新模型列表
      </Button>
    </Grid>
  </Grid>
</Paper>
```

- [ ] **Step 3: Verify frontend builds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No TypeScript errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/Settings.tsx
git commit -m "feat: wire up Auto Subtitle tab and ASR settings"
```

---

### Task 9: Integration Verification

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && source venv/bin/activate && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Run frontend type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Start backend and verify API**

Run: `cd backend && source venv/bin/activate && python run.py &`

Test endpoints:
```bash
curl http://localhost:5001/api/audio/subtitle/status
```
Expected: JSON with `models`, `mlx_audio_available: true`

- [ ] **Step 4: Start frontend and verify UI**

Run: `cd frontend && npm run dev`

Open http://localhost:3000, verify "自动字幕" tab is visible and clickable.

- [ ] **Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: integration fixes for auto-subtitle feature"
```
