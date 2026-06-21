# Audio Auto-Subtitle Feature Design

## Overview

Add a new "Auto Subtitle" tab to VATools that transcribes audio files into timestamped subtitles using the Qwen3-ASR model via mlx-audio. Users can preview, edit, and export subtitles in SRT/VTT/JSON formats.

## Constraints

- **No network downloads**: Models must be loaded from local filesystem only. Never download from HuggingFace or any remote source.
- **Local dependencies first**: Use locally installed package versions. All dependencies pinned in `requirements.txt`.
- **Default model**: `Qwen3-ASR-1.7B-8bit` at `/Users/lwz/.cache/modelscope/hub/models/mlx-community/Qwen3-ASR-1.7B-8bit`
- **Configurable model directory**: Default path `/Users/lwz/.cache/modelscope/hub/models/mlx-community`, overridable in Settings.

## Architecture

### New Files

| File | Purpose |
|------|---------|
| `backend/app/services/audio_subtitle.py` | ASR service: model scanning, transcription, subtitle generation |
| `frontend/src/components/AudioSubtitle.tsx` | React component for the subtitle tab |

### Modified Files

| File | Changes |
|------|---------|
| `frontend/src/App.tsx` | Add "Auto Subtitle" tab (index 3, shift Settings to 4) |
| `frontend/src/services/api.ts` | Add `startSubtitle()`, `getSubtitleStatus()`, `getSubtitleResult()`, `exportSubtitle()` |
| `backend/app/config.py` | Add `ASR_MODEL_DIR` config |
| `backend/app/routes/audio.py` | Add subtitle routes |
| `backend/app/__init__.py` | No change (audio blueprint already registered) |
| `frontend/src/components/Settings.tsx` | Add ASR model directory config section |
| `backend/requirements.txt` | Add `mlx-audio==0.4.4` and other missing deps |

### Data Flow

```
User uploads audio
  → POST /api/audio/subtitle (audio_file_id, model, language)
  → Task created (task_type='audio_subtitle')
  → Background thread: load_model(local_path) → generate_transcription(format="json")
  → Segments stored as JSON file
  → Task completed, frontend fetches result
  → GET /api/audio/subtitle/<task_id>/result → segments JSON
  → Frontend displays editable subtitle list
  → POST /api/audio/subtitle/<task_id>/export (format=srt|vtt, edited_segments)
  → Returns downloadable file
```

## Backend Design

### Service: `audio_subtitle.py`

**Functions:**

- `scan_asr_models(model_dir: str) -> dict`: Scans `ASR_MODEL_DIR` for directories containing `config.json` + `model.safetensors`. Returns `{model_name: path}`.

- `get_asr_status() -> dict`: Returns available models, mlx-audio installation status, current config.

- `start_audio_subtitle(audio_file_id: int, model: str, language: str) -> tuple[int, str|None]`: Creates Task, spawns background thread. Returns `(task_id, error)`.

- `process_audio_subtitle(task_id: int, app)`: Background thread function.
  1. Load model from local path using `mlx_audio.stt.utils.load_model(local_path)`
  2. Call `generate_transcription(model=model, audio=audio_path, format="json")`
  3. Parse segments (text, start, end)
  4. Save segments as JSON file in workspace
  5. Update task status to completed

- `generate_subtitle_file(segments: list, format: str, output_path: str)`: Converts segments to SRT/VTT/TXT format and writes file.

**Model loading:**
- Module-level cache: `_model_cache = {}` to avoid reloading on subsequent calls
- Load using absolute local path, never model name that triggers download
- Pass `local_files_only=True` where applicable

### API Routes (added to `audio.py`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/audio/subtitle` | Start subtitle recognition. Body: `{audio_file_id, model?, language?}` |
| `GET` | `/api/audio/subtitle/status` | Get ASR feature status and available models |
| `GET` | `/api/audio/subtitle/<task_id>/result` | Get transcription result (segments JSON) |
| `POST` | `/api/audio/subtitle/<task_id>/export` | Export subtitle file. Body: `{format, segments?}` |

**Export endpoint** accepts optional `segments` array (edited by user in frontend) to override the original result. If not provided, uses the original segments from the task. The SRT/VTT file is generated on-the-fly from the provided segments and returned as a downloadable blob response.

### Task Storage

- `task_type`: `'audio_subtitle'`
- `params`: `{"audio_file_id": 1, "model": "Qwen3-ASR-1.7B-8bit", "language": "auto"}`
- `output_file`: Path to the segments JSON file
- Result JSON structure:
  ```json
  {
    "text": "full transcription text",
    "segments": [
      {"id": 1, "start": 0.0, "end": 2.5, "text": "Hello world"},
      {"id": 2, "start": 2.5, "end": 5.0, "text": "This is a test"}
    ],
    "language": "zh"
  }
  ```

### Configuration

In `config.py`:
```python
ASR_MODEL_DIR = '/Users/lwz/.cache/modelscope/hub/models/mlx-community'
ASR_DEFAULT_MODEL = 'Qwen3-ASR-1.7B-8bit'
```

Configurable via Settings (stored in DB as `asr_model_dir`).

## Frontend Design

### AudioSubtitle.tsx

**Layout sections (top to bottom):**

1. **Upload area**: Dropzone for audio files (MP3/WAV/FLAC). Same pattern as AudioSeparator.

2. **Settings panel** (shown after upload, before processing):
   - Model dropdown: populated from `/api/audio/subtitle/status`
   - Language dropdown: Auto / Chinese / English / Japanese / Korean / etc.
   - "Start Recognition" button

3. **Progress panel** (during processing):
   - LinearProgress bar
   - Status text

4. **Result panel** (after completion):
   - Editable subtitle list table:
     - Column 1: Index (#)
     - Column 2: Time range (editable start/end time fields)
     - Column 3: Subtitle text (editable TextField)
     - Column 4: Actions (delete row)
   - "Add Row" button to insert new subtitle entries
   - Export buttons: Download SRT / Download VTT / Download JSON

### Settings.tsx Addition

New "ASR Settings" accordion section:
- ASR model directory path TextField (with folder icon)
- "Scan Models" button
- List of detected ASR models

### API Functions (api.ts)

```typescript
export const startSubtitle = (audioFileId: number, model?: string, language?: string) =>
  api.post('/audio/subtitle', { audio_file_id: audioFileId, model, language })

export const getSubtitleStatus = () =>
  api.get('/audio/subtitle/status')

export const getSubtitleResult = (taskId: number) =>
  api.get(`/audio/subtitle/${taskId}/result`)

export const exportSubtitle = (taskId: number, format: string, segments?: any[]) =>
  api.post(`/audio/subtitle/${taskId}/export`, { format, segments }, { responseType: 'blob' })
```

## Dependencies

Add to `requirements.txt`:
```
mlx-audio==0.4.4
```

All other dependencies (mlx, mlx-lm, transformers, etc.) are transitive dependencies of mlx-audio and already installed.

## Error Handling

- Model not found: Return clear error with configured model directory path
- mlx-audio not installed: Status endpoint reports unavailable, frontend shows install instructions
- Audio format unsupported: Validate before processing, return 400
- Transcription fails: Task marked as failed with error message, socket notification sent
