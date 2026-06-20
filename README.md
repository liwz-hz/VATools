# VATools - 音视频处理工具

基于Flask + React的音视频处理Web应用。

## 功能特性

- 视频→音频提取（WAV/MP3/FLAC）
- 音频片段编辑（提取/删除）
- 波形可视化 + 实时试听
- 音源分离（人声、鼓点、贝斯、伴奏）
- macOS加速支持（MPS/MLX）

## 快速开始

### 后端

```bash
cd backend
pip install -r requirements.txt
python run.py
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

## 系统要求

- Python 3.9+
- Node.js 18+
- FFmpeg 4.0+

## 许可证

MIT
