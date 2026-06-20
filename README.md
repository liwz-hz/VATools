# VATools - 音视频处理工具

基于Flask + React的音视频处理Web应用。

## 功能特性

### 音频处理
- 视频→音频提取（支持WAV/MP3/FLAC格式）
- 音频片段编辑（提取片段/删除片段）
- 波形可视化 + 实时试听
- 音源分离（人声、鼓点、贝斯、伴奏）

### 技术特性
- macOS加速支持（MPS/MLX）
- 实时任务进度推送
- 可配置的工作目录和参数
- 全局日志系统

## 系统要求

- Python 3.9+
- Node.js 18+
- FFmpeg 4.0+ (系统安装)
- SQLite3

## 快速开始

### 一键启动（推荐）

使用提供的启动脚本快速启动所有服务：

```bash
# 克隆项目
git clone <repository-url>
cd VATools

# 一键启动（自动安装依赖并启动服务）
./start.sh
```

启动后访问：
- **前端**: http://localhost:3000
- **后端**: http://localhost:5000

**启动脚本命令：**

```bash
./start.sh           # 启动所有服务
./start.sh start     # 启动所有服务
./start.sh stop      # 停止所有服务
./start.sh restart   # 重启所有服务
./start.sh status    # 查看服务状态
./start.sh logs      # 查看实时日志
./start.sh install   # 仅安装依赖
./start.sh help      # 显示帮助信息
```

### 手动安装（可选）

如果需要手动安装和启动，请按照以下步骤：

#### 1. 克隆项目

```bash
git clone <repository-url>
cd VATools
```

#### 2. 后端设置

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行应用
python run.py
```

后端将在 http://localhost:5000 启动。

#### 3. 前端设置

```bash
cd frontend

# 安装依赖
npm install

# 运行开发服务器
npm run dev
```

前端将在 http://localhost:3000 启动。

## 使用指南

### 音频提取

1. 打开"音频提取"标签页
2. 拖拽或点击上传视频文件
3. 选择输出格式（MP3/WAV/FLAC）
4. 点击"开始提取"
5. 完成后下载或进入编辑

### 音频编辑

1. 打开"音频编辑"标签页
2. 上传音频文件
3. 在波形显示区拖拽选择片段
4. 选择操作（提取片段/删除片段）
5. 点击操作按钮
6. 下载结果

### 音源分离

1. 打开"音源分离"标签页
2. 上传音频文件
3. 勾选要分离的音轨（人声、鼓点、贝斯、伴奏）
4. 点击"开始分离"
5. 下载分离后的音轨

### 配置管理

在"设置"标签页可以配置：
- 工作目录（上传、输出、日志）
- 日志级别和保留策略
- 音频默认参数
- 音源分离加速方式

## API文档

### 文件管理

- `POST /api/files/upload` - 上传文件
- `GET /api/files` - 获取文件列表
- `GET /api/files/<id>` - 获取文件详情
- `DELETE /api/files/<id>` - 删除文件
- `GET /api/files/<id>/download` - 下载文件

### 音频处理

- `POST /api/audio/extract` - 从视频提取音频
- `POST /api/audio/clip` - 音频片段处理
- `POST /api/audio/separate` - 音源分离

### 任务管理

- `GET /api/tasks` - 获取任务列表
- `GET /api/tasks/<id>` - 获取任务详情
- `DELETE /api/tasks/<id>` - 取消任务

### 配置管理

- `GET /api/config` - 获取所有配置
- `PUT /api/config` - 更新配置
- `POST /api/config/reset` - 恢复默认配置

## 开发指南

### 运行测试

```bash
cd backend
python -m pytest tests/ -v
```

### 项目结构

```
VATools/
├── backend/           # Flask后端
│   ├── app/
│   │   ├── models.py
│   │   ├── routes/
│   │   ├── services/
│   │   └── utils/
│   ├── uploads/
│   ├── workspace/
│   └── logs/
├── frontend/          # React前端
│   ├── src/
│   │   ├── components/
│   │   ├── services/
│   │   └── App.tsx
│   └── package.json
└── README.md
```

## macOS加速支持

VATools支持macOS的硬件加速：

### MPS (Metal Performance Shaders)
- PyTorch原生支持
- 自动检测Apple Silicon
- 比CPU快3-5倍

### MLX (Apple Machine Learning Framework)
- Apple官方框架
- 针对Apple Silicon优化
- 部分任务比MPS快1.5-2倍

### 自动检测
默认使用"自动检测"，系统会自动选择最快的可用加速方式。

## 常见问题

### FFmpeg未找到
确保FFmpeg已安装并添加到PATH：
```bash
# macOS
brew install ffmpeg

# 验证
ffmpeg -version
```

### 音源分离失败
- 检查是否有足够的内存（建议至少8GB）
- 尝试切换到CPU模式（在设置中更改加速方式）
- 查看日志文件获取详细错误信息

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！
