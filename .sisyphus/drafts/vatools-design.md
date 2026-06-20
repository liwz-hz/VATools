# Draft: VATools - 音视频处理工具

## Requirements (confirmed)
- **核心功能**: 视频音频分离、音频试听（波形可视化）、音频片段裁剪导出
- **裁剪方式**: 非破坏性，复制生成片段（不是修改原文件）
- **交互方式**: 波形拖选（WaveSurfer.js 区域选择）
- **导出格式**: 用户可选，默认 WAV，可选 MP3、FLAC
- **使用场景**: 本地单机使用，localhost 访问

## Technical Decisions
- **后端**: FastAPI（Python）
- **前端**: React + TypeScript
- **波形可视化**: WaveSurfer.js + Regions Plugin
- **音频处理**: FFmpeg（通过 ffmpeg-python 或 subprocess）
- **部署**: 本地运行，无需用户认证/多用户

## Future Extensions (confirmed)
- FunASR 音频转字幕（自动语音识别）
- CosyVoice 语音合成（TTS）
- 模型来源: 魔塔社区（ModelScope），非 HuggingFace
- 更多音视频处理功能待扩展

## Additional Decisions
- **UI 主题**: 双主题可切换（暗色 + 亮色）
- **前端组件库**: shadcn/ui + Tailwind CSS
- **测试策略**: 后端 pytest + 前端 Vitest
- **前端构建**: Vite
- **音频处理**: FFmpeg (ffmpeg-python) + pydub

## Resolved Questions
- UI 主题 → 双主题可切换
- 组件库 → shadcn/ui + Tailwind
- 测试 → pytest + Vitest

## Scope Boundaries
- INCLUDE: 视频→音频分离、波形试听、片段裁剪导出、美观 UI
- EXCLUDE: 用户认证、多用户、云端部署（初期）
