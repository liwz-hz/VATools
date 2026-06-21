# 音源分离模型管理指南

## 概述

VATools 使用 Spleeter 进行音源分离，**不会自动下载模型**。您需要手动下载并安装模型。

## 系统要求

- **Python 版本**: 3.9-3.11（Spleeter 不支持 Python 3.12+）
- **依赖**: `pip install spleeter==2.4.0`

## 模型下载

### 方法 1: 手动下载（推荐）

#### 1. 创建模型目录

```bash
# macOS/Linux
mkdir -p ~/.spleeter/models

# Windows
mkdir C:\Users\<你的用户名>\.spleeter\models
```

#### 2. 下载模型

**2stems 模型（人声/伴奏分离）**
```bash
cd ~/.spleeter/models
wget https://github.com/deezer/spleeter/releases/download/v1.4.0/2stems.tar.gz
tar -xzf 2stems.tar.gz
rm 2stems.tar.gz
```

**4stems 模型（人声/鼓点/贝斯/伴奏分离）**
```bash
cd ~/.spleeter/models
wget https://github.com/deezer/spleeter/releases/download/v1.4.0/4stems.tar.gz
tar -xzf 4stems.tar.gz
rm 4stems.tar.gz
```

**5stems 模型（人声/鼓点/贝斯/钢琴/伴奏分离）**
```bash
cd ~/.spleeter/models
wget https://github.com/deezer/spleeter/releases/download/v1.4.0/5stems.tar.gz
tar -xzf 5stems.tar.gz
rm 5stems.tar.gz
```

#### 3. 验证模型

```bash
# 检查目录结构
ls -la ~/.spleeter/models/

# 应该看到：
# 2stems/
#   ├── model.data-00000-of-00001
#   ├── model.index
#   ├── model.meta
#   └── checkpoint
# 4stems/
#   └── ...
# 5stems/
#   └── ...
```

### 方法 2: 使用浏览器下载

如果网络访问 GitHub 受限，可以：

1. 访问 Spleeter 发布页面：
   - https://github.com/deezer/spleeter/releases/tag/v1.4.0

2. 下载需要的模型文件：
   - `2stems.tar.gz` (约 45MB)
   - `4stems.tar.gz` (约 180MB)
   - `5stems.tar.gz` (约 320MB)

3. 解压到 `~/.spleeter/models/` 目录

### 方法 3: 使用镜像源（中国用户）

```bash
# 使用 GitHub 镜像
cd ~/.spleeter/models
wget https://ghproxy.com/https://github.com/deezer/spleeter/releases/download/v1.4.0/4stems.tar.gz
tar -xzf 4stems.tar.gz
```

## 模型说明

| 模型 | 大小 | 分离轨道 | 用途 |
|------|------|---------|------|
| 2stems | ~45MB | 人声、伴奏 | 卡拉OK制作 |
| 4stems | ~180MB | 人声、鼓点、贝斯、其他 | 专业音乐分析 |
| 5stems | ~320MB | 人声、鼓点、贝斯、钢琴、其他 | 完整音乐制作 |

## 自定义模型目录

如果需要将模型存放在其他位置，可以在配置中指定：

### 方法 1: 环境变量

```bash
export SPLEETER_MODEL_DIR=/path/to/your/models
```

### 方法 2: 修改配置文件

编辑 `backend/app/config.py`：

```python
class Config:
    # ... 其他配置 ...
    
    # Spleeter 模型目录（可选）
    SPLEETER_MODEL_DIR = '/path/to/your/models'
```

## 检查模型状态

### API 检查

```bash
# 启动服务后访问
curl http://localhost:5001/api/audio/separation/status
```

返回示例：
```json
{
  "spleeter_installed": true,
  "models": {
    "2stems": {
      "available": true,
      "description": "人声/伴奏分离（2轨）",
      "stems": ["vocals", "accompaniment"],
      "download_url": "https://github.com/deezer/spleeter/releases/download/v1.4.0/2stems.tar.gz"
    },
    "4stems": {
      "available": false,
      "description": "人声/鼓点/贝斯/伴奏分离（4轨）",
      "stems": ["vocals", "drums", "bass", "other"],
      "download_url": "https://github.com/deezer/spleeter/releases/download/v1.4.0/4stems.tar.gz"
    }
  }
}
```

## 常见问题

### Q: 为什么不自动下载模型？

A: 模型文件较大（45-320MB），自动下载可能：
- 消耗大量流量
- 下载失败导致功能不可用
- 下载位置不明确，难以管理

手动下载让您完全控制模型管理。

### Q: 模型下载很慢怎么办？

A: 可以尝试：
1. 使用 GitHub 镜像站点
2. 使用代理下载
3. 离线下载后上传到服务器

### Q: 如何删除已下载的模型？

```bash
rm -rf ~/.spleeter/models/2stems
rm -rf ~/.spleeter/models/4stems
rm -rf ~/.spleeter/models/5stems
```

### Q: 模型文件损坏怎么办？

删除对应模型目录，重新下载解压即可。

### Q: 可以使用其他音源分离模型吗？

当前仅支持 Spleeter。如需其他模型支持（如 Demucs），可以提交 Issue 或 Pull Request。

## 性能优化

### GPU 加速

Spleeter 支持 GPU 加速，需要：
1. 安装 CUDA/cuDNN（NVIDIA GPU）
2. 安装 PyTorch GPU 版本
3. 在设置中选择 GPU 加速模式

### macOS 加速

支持 Apple Silicon GPU 加速：
- MPS (Metal Performance Shaders)
- MLX (Apple Machine Learning Framework)

在设置中选择对应的加速方式即可。

## 技术支持

如遇到问题：
1. 检查 Python 版本（必须是 3.9-3.11）
2. 检查模型文件是否完整
3. 查看日志：`backend/logs/app.log`
4. 提交 Issue：https://github.com/your-repo/vatools/issues
