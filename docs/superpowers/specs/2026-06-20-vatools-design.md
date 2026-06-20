# VATools 音视频处理工具 - 设计文档

## 项目概述

**VATools** 是一个基于Flask + React的Web应用，专注于音频处理功能，为未来的视频处理和AI功能预留扩展接口。

### 核心特性（MVP）

- 视频→音频提取（支持WAV/MP3/FLAC格式）
- 音频片段编辑（提取片段/删除片段）
- 波形可视化 + 实时试听
- 音源分离（人声、鼓点、贝斯、伴奏）
- 全局日志系统

### 技术栈

- **后端**：Flask + FFmpeg + SQLite3 + Spleeter
- **前端**：React + TypeScript + Material-UI
- **实时通信**：WebSocket (Socket.IO)
- **macOS加速**：MPS (Metal Performance Shaders) / MLX
- **部署**：本地/局域网（单用户）

### 扩展规划

- Phase 2: 高级视频编辑功能
- Phase 3: 基于Qwen的自动字幕生成和语音合成

## 系统架构

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                     前端 React 应用                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │音频提取  │  │音频编辑  │  │音源分离  │  │  设置   │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────┘
                      ↓ REST API + WebSocket
┌─────────────────────────────────────────────────────────┐
│                     Flask 后端                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │路由层    │  │业务逻辑  │  │任务管理  │  │WebSocket │ │
│  │(Blueprint)│  │(Service) │  │(Thread)  │  │(SocketIO)│ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │SQLite3   │  │FFmpeg    │  │文件系统  │              │
│  │(任务状态)│  │(音视频处理)│  │(上传/输出)│              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
```

### 核心组件

1. **前端层**（React）
   - 音频提取模块：视频上传、格式选择、参数配置
   - 音频编辑模块：波形展示、片段选择、试听、操作
   - 音源分离模块：分离类型选择、结果展示
   - 设置模块：工作目录、日志、参数配置

2. **后端层**（Flask）
   - 路由层：REST API endpoints
   - 业务逻辑层：处理核心业务
   - 任务管理：后台线程处理长时间任务
   - WebSocket：推送实时进度

3. **数据层**
   - SQLite3：任务状态、配置信息
   - 文件系统：原始文件、处理后文件

## 数据库设计

### SQLite3 数据表

```sql
-- 任务表：记录所有处理任务
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type VARCHAR(50) NOT NULL,        -- 'audio_extract', 'audio_clip', 'audio_separation'
    status VARCHAR(20) NOT NULL,           -- 'pending', 'processing', 'completed', 'failed'
    input_file VARCHAR(255) NOT NULL,
    output_file VARCHAR(255),
    params TEXT,                           -- JSON格式参数
    progress INTEGER DEFAULT 0,            -- 0-100
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 文件表：记录上传的文件
CREATE TABLE files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_type VARCHAR(20),                 -- 'video', 'audio'
    file_size INTEGER,
    duration REAL,                         -- 音视频时长（秒）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 配置表：系统配置
CREATE TABLE config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 默认配置数据

```sql
INSERT INTO config (key, value) VALUES 
    ('upload_dir', 'uploads'),
    ('workspace_dir', 'workspace'),
    ('max_file_size', '536870912'),        -- 512MB
    ('log_dir', 'logs'),
    ('log_level', 'INFO'),
    ('log_max_size', '10485760'),          -- 10MB
    ('log_retention_days', '30'),
    ('default_audio_format', 'mp3'),
    ('default_bitrate', '192k'),
    ('default_sample_rate', '44100'),
    ('separation_model', 'spleeter'),
    ('acceleration_type', 'auto'),        -- 'auto', 'mps', 'mlx', 'cpu'
    ('separation_output_format', 'wav');
```

## API设计

### REST API 接口

```python
# 文件管理
POST   /api/files/upload           # 上传文件
GET    /api/files                  # 获取文件列表
GET    /api/files/<id>             # 获取文件详情
DELETE /api/files/<id>             # 删除文件
GET    /api/files/<id>/download    # 下载文件

# 音频提取
POST   /api/audio/extract          # 从视频提取音频
       请求体: {
           "video_file_id": 1,
           "output_format": "mp3",     # wav/mp3/flac
           "bitrate": "192k"           # 可选
       }
       返回: {"task_id": "abc123"}

# 音频编辑
POST   /api/audio/clip             # 音频片段处理
       请求体: {
           "audio_file_id": 1,
           "operation": "extract",     # extract/delete
           "start_time": 10.5,         # 秒
           "end_time": 25.3
       }
       返回: {"task_id": "def456"}

# 音源分离
POST   /api/audio/separate         # 音源分离
       请求体: {
           "audio_file_id": 1,
           "stems": ["vocals", "drums", "bass", "other"]
       }
       返回: {"task_id": "ghi789"}

# 任务管理
GET    /api/tasks                  # 获取任务列表
GET    /api/tasks/<id>             # 获取任务详情
DELETE /api/tasks/<id>             # 取消任务

# 配置管理
GET    /api/config                 # 获取所有配置
PUT    /api/config                 # 更新配置
POST   /api/config/reset           # 恢复默认配置
```

### WebSocket 事件

```python
# 服务端推送
'task_progress'     # 任务进度更新
    数据: {"task_id": "abc123", "progress": 45, "status": "processing"}

'task_completed'    # 任务完成
    数据: {"task_id": "abc123", "output_file": "output.mp3"}

'task_failed'       # 任务失败
    数据: {"task_id": "abc123", "error": "错误信息"}
```

## 前端组件设计

### 页面布局

```
顶部标签页：[音频提取] [音频编辑] [音源分离] [设置]

【音频提取】页面：
┌─────────────────────────────────────┐
│  拖拽上传视频文件                    │
│  ┌─────────────────────────────┐    │
│  │  支持格式：mp4, avi, mov...  │    │
│  └─────────────────────────────┘    │
│  输出格式：[wav ▼] [mp3] [flac]     │
│  [开始提取]                          │
│  提取进度：███████░░░ 70%            │
│  ✓ 提取完成：output.mp3 [进入编辑]   │
└─────────────────────────────────────┘

【音频编辑】页面：
┌─────────────────────────────────────┐
│  选择音频：[选择文件] 或 [最近提取]  │
├─────────────────────────────────────┤
│  波形显示区                          │
│  ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁                   │
│  |━━━━━━━━|━━━━━━━━|                │
│  ←滑块选择片段→                     │
├─────────────────────────────────────┤
│  00:10 ══════════════════════ 02:30 │
│  选区：00:10 - 00:35                │
│  [▶试听] [提取片段] [删除片段]      │
├─────────────────────────────────────┤
│  导出格式：[原格式 ▼] [wav] [mp3]   │
│  [导出结果]                          │
└─────────────────────────────────────┘

【音源分离】页面：
┌─────────────────────────────────────┐
│  选择音频：[选择文件]               │
├─────────────────────────────────────┤
│  分离类型：                          │
│  ☑ 人声    ☑ 鼓点                   │
│  ☑ 贝斯    ☑ 其他伴奏               │
│  [开始分离]                          │
├─────────────────────────────────────┤
│  分离结果：                          │
│  ✓ vocals.wav    [▶播放] [编辑]     │
│  ✓ drums.wav     [▶播放] [编辑]     │
│  ✓ bass.wav      [▶播放] [编辑]     │
│  ✓ other.wav     [▶播放] [编辑]     │
└─────────────────────────────────────┘

【设置】页面：
┌─────────────────────────────────────┐
│  工作目录设置                        │
│  ├─ 上传目录：[/path/to/uploads] [选择]
│  ├─ 输出目录：[/path/to/workspace] [选择]
│  └─ 最大文件大小：[512] MB          │
├─────────────────────────────────────┤
│  日志设置                            │
│  ├─ 日志目录：[/path/to/logs] [选择]
│  ├─ 日志级别：[INFO ▼]              │
│  ├─ 日志大小：[10] MB               │
│  └─ 保留天数：[30] 天               │
├─────────────────────────────────────┤
│  音频设置                            │
│  ├─ 默认格式：[mp3 ▼]               │
│  ├─ 默认比特率：[192k ▼]            │
│  └─ 采样率：[44100 Hz ▼]           │
├─────────────────────────────────────┤
│  音源分离设置                        │
│  ├─ 分离模型：[spleeter ▼]          │
│  ├─ 加速方式：[自动检测 ▼]           │
│  │   (可选: MPS/MLX/CPU)             │
│  └─ 输出格式：[wav ▼]               │
├─────────────────────────────────────┤
│  [恢复默认] [保存配置]               │
└─────────────────────────────────────┘
```

### 核心组件

1. **音频提取组件** (`AudioExtractor`)
   - 文件上传区（拖拽上传）
   - 输出格式选择（WAV/MP3/FLAC）
   - 参数配置（比特率、采样率）
   - 提取按钮 + 实时进度
   - 提取完成后：下载 / 进入编辑

2. **音频编辑组件** (`AudioEditor`)
   - 文件选择器（支持音频文件）
   - 波形可视化
   - 片段选择器（拖拽选择）
   - 实时试听播放器
   - 操作按钮（提取片段/删除片段）
   - 完成后：下载结果

3. **音源分离组件** (`AudioSeparator`)
   - 文件选择器
   - 分离类型选择（人声、鼓点、贝斯、伴奏）
   - 分离进度显示
   - 结果列表（播放、编辑）

4. **设置组件** (`Settings`)
   - 工作目录配置
   - 日志配置
   - 音频参数配置
   - 音源分离配置

## 文件存储结构

### 目录结构

```
VATools/
├── backend/                 # Flask后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py       # 配置文件
│   │   ├── models.py       # 数据库模型
│   │   ├── routes/         # API路由
│   │   │   ├── __init__.py
│   │   │   ├── files.py
│   │   │   ├── audio.py
│   │   │   └── config.py
│   │   ├── services/       # 业务逻辑
│   │   │   ├── __init__.py
│   │   │   ├── audio_extractor.py
│   │   │   ├── audio_editor.py
│   │   │   └── audio_separator.py
│   │   └── utils/          # 工具函数
│   │       ├── __init__.py
│   │       ├── ffmpeg_utils.py
│   │       └── logger.py
│   ├── uploads/            # 上传文件临时目录
│   ├── workspace/          # 工作目录（提取、分离结果）
│   │   ├── audio/          # 音频提取结果
│   │   ├── separated/      # 音源分离结果
│   │   └── edited/         # 编辑结果
│   ├── logs/               # 日志目录
│   │   ├── app.log
│   │   ├── ffmpeg.log
│   │   └── separation.log
│   ├── vatooldb.db         # SQLite数据库
│   ├── requirements.txt
│   └── run.py              # 启动文件
│
├── frontend/               # React前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── AudioExtractor.tsx
│   │   │   ├── AudioEditor.tsx
│   │   │   ├── AudioSeparator.tsx
│   │   │   ├── Settings.tsx
│   │   │   └── WaveformViewer.tsx
│   │   ├── pages/
│   │   │   └── Home.tsx
│   │   ├── services/       # API调用
│   │   │   └── api.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
│
└── README.md
```

### 文件命名规则

```
上传文件：uploads/<timestamp>_<original_filename>
提取文件：workspace/audio/<timestamp>_<original_name>.<format>
分离文件：workspace/separated/<timestamp>_<stem_type>.wav
编辑文件：workspace/edited/<timestamp>_<operation>.<format>
```

## 配置管理

### 配置文件

```python
# backend/app/config.py
class Config:
    # 工作目录
    UPLOAD_DIR = 'uploads'
    WORKSPACE_DIR = 'workspace'
    MAX_FILE_SIZE = 512 * 1024 * 1024  # 512MB
    
    # 日志配置
    LOG_DIR = 'logs'
    LOG_LEVEL = 'INFO'
    LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5
    LOG_RETENTION_DAYS = 30
    
    # 音频配置
    DEFAULT_AUDIO_FORMAT = 'mp3'
    DEFAULT_BITRATE = '192k'
    DEFAULT_SAMPLE_RATE = 44100
    
    # 音源分离配置
    SEPARATION_MODEL = 'spleeter'
    ACCELERATION_TYPE = 'auto'  # 'auto', 'mps', 'mlx', 'cpu'
    SEPARATION_OUTPUT_FORMAT = 'wav'
    
    # macOS加速
    # MPS: Metal Performance Shaders (PyTorch原生支持)
    # MLX: Apple机器学习框架 (需要mlx库)
```

### 配置加载逻辑

1. 启动时加载默认配置
2. 从SQLite读取用户配置并覆盖
3. 提供API接口修改配置
4. 配置变更立即生效

### macOS加速支持

**加速方式**：

1. **MPS (Metal Performance Shaders)**
   - PyTorch原生支持
   - 自动检测Apple Silicon芯片
   - 无需额外配置
   - 代码示例：
     ```python
     import torch
     device = torch.device('mps' if torch.backends.mps.is_available() else 'cpu')
     ```

2. **MLX (Apple Machine Learning Framework)**
   - Apple官方机器学习框架
   - 针对Apple Silicon优化
   - 需要安装：`pip install mlx`
   - 适合自定义模型

3. **CPU Fallback**
   - 默认选项
   - 无需GPU
   - 适合所有平台

**自动检测逻辑**：

```python
def get_device():
    if ACCELERATION_TYPE == 'auto':
        if torch.backends.mps.is_available():
            return 'mps'
        return 'cpu'
    return ACCELERATION_TYPE
```

**性能对比**（参考）：
- MPS: 比CPU快 3-5倍
- MLX: 比MPS快 1.5-2倍（特定任务）
- CPU: 基准性能

## 错误处理与日志

### 错误处理策略

1. **文件上传错误**
   - 文件过大：提示"文件超过512MB限制"
   - 格式不支持：提示"支持格式：mp4, avi, mov, mp3, wav..."
   - 上传失败：自动重试 + 错误日志

2. **处理过程错误**
   - FFmpeg失败：显示详细错误信息 + 日志下载
   - 音源分离失败：加速方式切换提示（MPS/MLX → CPU）
   - 任务超时：提示"处理时间过长，请检查文件"

3. **用户体验优化**
   - 实时进度：WebSocket推送处理进度
   - 预估时间：基于文件大小估算完成时间
   - 后台处理：关闭浏览器后任务继续执行
   - 历史记录：最近处理的文件快速访问

### 日志系统

#### 日志文件结构

```
logs/
├── app.log           # 应用主日志
├── app.log.1         # 轮转日志
├── ffmpeg.log        # FFmpeg处理日志
├── separation.log    # 音源分离日志
└── error.log         # 错误专用日志
```

#### 日志格式

```
[2026-06-20 14:30:45] [INFO] [app] 用户上传文件：video.mp4
[2026-06-20 14:30:50] [INFO] [ffmpeg] 开始提取音频：video.mp4 -> audio.mp3
[2026-06-20 14:31:05] [INFO] [ffmpeg] 音频提取完成
[2026-06-20 14:31:10] [ERROR] [separation] 加速初始化失败，切换到CPU模式
```

## 技术栈详细说明

### 后端依赖

```txt
# Web框架
Flask==3.0.0
Flask-CORS==4.0.0
Flask-SocketIO==5.3.5

# 数据库
SQLAlchemy==2.0.23

# 音视频处理
ffmpeg-python==0.2.0

# 音源分离
spleeter==2.4.0

# macOS加速
torch>=2.0.0                  # MPS支持 (Metal Performance Shaders)
mlx>=0.1.0                    # Apple MLX框架（可选）

# WebSocket
python-socketio==5.10.0
eventlet==0.33.3

# 日志
loguru==0.7.2
```

### 前端依赖

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "typescript": "^5.3.0",
    "@mui/material": "^5.15.0",
    "@emotion/react": "^11.11.0",
    "@emotion/styled": "^11.11.0",
    "axios": "^1.6.0",
    "socket.io-client": "^4.7.0",
    "wavesurfer.js": "^7.7.0",
    "react-dropzone": "^14.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "vite": "^5.0.0"
  }
}
```

### 系统依赖

- FFmpeg 4.0+ (系统安装)
- Python 3.9+
- Node.js 18+
- SQLite3

**注意**：版本优先使用本地已安装的版本

## 扩展规划

### Phase 2 - 视频处理功能

```
【视频剪辑】页面：
├─ 视频片段裁剪
├─ 视频格式转换
├─ 视频压缩
└─ 提取视频帧

【视频编辑】页面：
├─ 添加字幕
├─ 添加水印
├─ 视频合并
└─ 转场效果
```

### Phase 3 - AI智能功能

```
【字幕生成】页面：
├─ 语音识别（Qwen-Audio）
├─ 字幕预览编辑
├─ 字幕导出
└─ 多语言翻译

【语音合成】页面：
├─ 文本转语音
├─ 音色选择
└─ 语速/音调调节
```

### 技术扩展准备

- 模块化设计，新功能作为独立模块添加
- API预留扩展接口
- 前端组件可插拔架构
- 配置系统支持新功能参数

### 性能优化方向

- 大文件分片上传
- 任务队列持久化（需要时升级到Celery）
- 缓存机制
- macOS加速优化（MPS/MLX自动检测与切换）
