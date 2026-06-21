# Audio TTS (Text-to-Speech) Feature Design

## Overview

Add a new "语音合成" tab to VATools that generates speech from text using Qwen3-TTS models via mlx-audio. Supports two modes: emotion-controlled dubbing (CustomVoice) and voice cloning (Base). Includes automatic emotion analysis with manual override for professional dubbing quality.

## Constraints

- **No network downloads**: Models loaded from local filesystem only. Never download from HuggingFace.
- **Local dependencies first**: Use locally installed package versions; pin in `requirements.txt`.
- **Default TTS model**: `Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit` at configured `TTS_MODEL_DIR`
- **Default model directory**: `/Users/lwz/.cache/modelscope/hub/models/mlx-community` (shared with ASR)
- **Follow existing patterns**: threading for background tasks, Socket.IO for progress, MUI components
- **On-demand model loading**: Load model on first use, cache for reuse, no eager loading

## Architecture

### New Files

| File | Purpose |
|------|---------|
| `backend/app/services/audio_tts.py` | TTS service: model loading, emotion analysis, speech generation |
| `backend/tests/test_audio_tts.py` | Unit tests for TTS service |
| `frontend/src/components/AudioTTS.tsx` | React component for the TTS tab |

### Modified Files

| File | Changes |
|------|---------|
| `frontend/src/App.tsx` | Add "语音合成" tab |
| `frontend/src/services/api.ts` | Add TTS API functions |
| `backend/app/routes/audio.py` | Add TTS routes |
| `backend/app/config.py` | Add `TTS_MODEL_DIR`, `TTS_DEFAULT_MODEL` |
| `backend/app/routes/config.py` | Add TTS config to `DEFAULT_CONFIG` |
| `frontend/src/components/Settings.tsx` | Add TTS settings section |

### Data Flow

```
User selects mode (emotion dubbing / voice clone)
  → Enters text + uploads reference audio (clone mode)
  → POST /api/audio/tts → Task created (task_type='audio_tts')
  → Background thread:
      1. Load CustomVoice or Base model (cached)
      2. Split text into sentences
      3. Analyze emotion per sentence (rules + manual override)
      4. Generate audio per sentence with instruct parameter
      5. Concatenate all audio segments
      6. Save as WAV
  → Task completed → frontend fetches result
  → Audio player for preview + download button
```

## Backend Design

### Service: `audio_tts.py`

**Functions:**

- `get_tts_status() -> dict`: Returns available TTS models, mlx-audio status, supported speakers.

- `get_supported_speakers() -> list`: Loads CustomVoice model (if cached) and returns speaker list. Falls back to hardcoded list: `['serena', 'vivian', 'uncle_fu', 'ryan', 'aiden', 'ono_anna', 'sohee', 'eric', 'dylan']`.

- `analyze_emotion(text: str) -> list[dict]`: Rule-based emotion analysis.
  - Splits text by sentence-ending punctuation (`。！？.!?`)
  - For each sentence, checks keywords/patterns:
    - `！` / `哈哈` / `太好了` / `太棒了` → `"用兴奋开心的语气说"`
    - `？` / `为什么` / `怎么` / `难道` → `"用疑问好奇的语气说"`
    - `...` / `唉` / `算了` / `可惜` → `"用低沉无奈的语气说"`
    - `不要` / `滚` / `够了` / `可恶` → `"用愤怒强烈的语气说"`
    - `请` / `谢谢` / `麻烦` → `"用礼貌温和的语气说"`
    - Default → `"用自然平和的语气说"`
  - Returns: `[{sentence: str, instruct: str}, ...]`

- `start_tts(params: dict) -> tuple[int, str|None]`: Creates Task, spawns background thread. Returns `(task_id, error)`.

- `process_tts(task_id: int, app)`: Background thread:
  1. Determine mode (custom_voice / voice_clone)
  2. Load appropriate model from local path
  3. If voice_clone mode: load reference audio, get ref_text via ASR if not provided
  4. Split text into sentences, apply emotion analysis
  5. For each sentence, call `model.generate()` with appropriate parameters
  6. Concatenate audio arrays with short silence gaps (0.3s)
  7. Save concatenated audio as WAV
  8. Update task status

- `_load_tts_model(model_name: str)`: Loads model with module-level cache. Uses absolute local path.

- `_concatenate_audio(audio_arrays: list, sample_rate: int, gap_seconds: float) -> np.ndarray`: Joins audio segments with silence gaps.

### API Routes (added to `audio.py`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/audio/tts` | Start TTS task. Body: `{text, mode, speaker?, ref_audio_id?, ref_text?, emotions?, speed?, temperature?}` |
| `GET` | `/api/audio/tts/status` | Get TTS feature status and available models |
| `GET` | `/api/audio/tts/speakers` | Get available speaker list |
| `POST` | `/api/audio/tts/analyze` | Preview emotion analysis. Body: `{text}`. Returns sentence-level emotion predictions |

### Task Storage

- `task_type`: `'audio_tts'`
- `params`: `{"text": "...", "mode": "custom_voice", "speaker": "vivian", "emotions": [...], "speed": 1.0, "temperature": 0.9}`
- `output_file`: Path to generated WAV file

### Configuration

In `config.py`:
```python
TTS_MODEL_DIR = '/Users/lwz/.cache/modelscope/hub/models/mlx-community'
TTS_CUSTOM_VOICE_MODEL = 'Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit'
TTS_BASE_MODEL = 'Qwen3-TTS-12Hz-1.7B-Base-8bit'
```

## Frontend Design

### AudioTTS.tsx

**Layout sections (top to bottom):**

1. **Mode toggle**: Segmented control — "情感配音" / "声音克隆"

2. **Emotion Dubbing mode** (shown when selected):
   - Speaker dropdown (populated from `/api/audio/tts/speakers`)
   - Language dropdown: Auto / Chinese / English

3. **Voice Clone mode** (shown when selected):
   - Reference audio Dropzone (MP3/WAV/FLAC)
   - Auto-transcribed text display (calls existing ASR endpoint)
   - "Transcribe" button to trigger ASR

4. **Text input area**:
   - Large multiline TextField (8 rows)
   - "Analyze Emotion" button → calls `/api/audio/tts/analyze`
   - Emotion preview: editable list of sentences with emotion dropdown per sentence
     - Each row: sentence text | emotion instruct (editable Select with presets + custom input)
     - Preset emotions: 自然平和 / 兴奋开心 / 疑问好奇 / 低沉无奈 / 愤怒强烈 / 礼貌温和

5. **Generation controls**:
   - Speed slider: 0.5x - 2.0x (default 1.0)
   - Temperature slider: 0.5 - 1.0 (default 0.9)
   - "Generate Speech" button

6. **Result area**:
   - HTML5 audio player for preview
   - Download button (WAV format)

### Settings.tsx Addition

New "TTS 语音合成设置" section (after ASR settings):
- TTS model directory path (defaults to same as ASR)
- Detected TTS models list

### API Functions (api.ts)

```typescript
export const startTTS = async (params: {
  text: string
  mode: string
  speaker?: string
  ref_audio_id?: number
  ref_text?: string
  emotions?: Array<{sentence: string, instruct: string}>
  speed?: number
  temperature?: number
}) => api.post('/audio/tts', params)

export const getTTSStatus = async () =>
  api.get('/audio/tts/status')

export const getTTSSpeakers = async () =>
  api.get('/audio/tts/speakers')

export const analyzeTTSEmotion = async (text: string) =>
  api.post('/audio/tts/analyze', { text })
```

## Emotion Analysis Rules

The rule engine uses a priority-ordered pattern matching approach:

| Pattern | Keywords/Punctuation | Emotion Instruct |
|---------|---------------------|-----------------|
| Exclamation | `！`, `哈哈`, `太好了`, `太棒了`, `wow` | `用兴奋开心的语气说` |
| Question | `？`, `为什么`, `怎么`, `难道`, `是不是` | `用疑问好奇的语气说` |
| Sighing | `...`, `唉`, `算了`, `可惜`, `哎` | `用低沉无奈的语气说` |
| Anger | `不要`, `滚`, `够了`, `可恶`, `混蛋` | `用愤怒强烈的语气说` |
| Polite | `请`, `谢谢`, `麻烦`, `拜托` | `用礼貌温和的语气说` |
| Default | (none matched) | `用自然平和的语气说` |

Users can override any sentence's emotion via the UI dropdown.

## Audio Concatenation

Generated audio segments are concatenated with:
- 0.3 seconds of silence between sentences
- Normalized amplitude across segments
- Output sample rate: 24000 Hz (model native)

## Error Handling

- Model not found: Clear error with configured model directory path
- mlx-audio not installed: Status endpoint reports unavailable
- Reference audio missing (clone mode): Return 400
- Generation fails: Task marked as failed with error message
