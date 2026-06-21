# SAM 3.1 MLX 演示脚本

## 概述

本演示展示了 **SAM 3.1 (Segment Anything Model 3.1)** 在 Apple Silicon (MLX) 上的能力，包括：

- **开放词汇目标检测** - 使用文本提示检测任意物体
- **实例分割** - 生成精确的物体分割掩码
- **多目标检测** - 同时检测多种类型的物体
- **框引导检测** - 使用边界框指导检测区域
- **视频帧处理** - 处理视频帧（为未来视频跟踪做准备）

## 模型信息

- **模型**: `mlx-community/sam3.1-bf16` (本地)
- **参数量**: ~873M
- **架构**: Sam3VideoModel
- **特性**:
  - MultiplexMaskDecoder: 同时处理16个物体 (2.4-4x 更快跟踪)
  - TriViTDetNeck: 3个并行FPN头 (检测、交互、传播)
  - DecoupledMemoryAttention: 带RoPE的图像交叉注意力
  - 改进的检测精度 (cats基准测试: 0.90 vs 0.87)

## 安装依赖

```bash
source backend/venv/bin/activate
pip install mlx-vlm pillow opencv-python
```

## 运行演示

```bash
cd backend
source venv/bin/activate
python sam_demo.py
```

## 演示内容

### Demo 1: 单目标检测
- **输入**: 视频第一帧
- **提示**: "a person"
- **输出**: 检测到的人物边界框和分割掩码
- **结果**: `demo1_person_detection.jpg`

### Demo 2: 多目标检测
- **输入**: 视频第一帧
- **提示**: ["a person", "clothing", "background"]
- **输出**: 多种物体的检测结果
- **结果**: `demo2_multi_object_detection.jpg`

### Demo 3: 实例分割
- **输入**: 视频第一帧
- **提示**: "a person"
- **输出**: 精确的分割掩码 (PNG格式)
- **结果**: `demo3_instance_segmentation.jpg` + `masks/mask_*.png`

### Demo 4: 框引导检测
- **输入**: 视频第一帧 + 中心区域边界框
- **提示**: "an object"
- **输出**: 指定区域内的物体检测
- **结果**: `demo4_box_guided_detection.jpg`

### Demo 5: 视频帧处理
- **输入**: 测试视频 (5.1秒, 30 FPS)
- **处理**: 提取3帧进行检测
- **输出**: 每帧的检测结果
- **结果**: `demo5_video_frame_*.jpg` + `video_frames/frame_*.jpg`

## 性能数据

在 Apple Silicon (M系列) 上的测试结果：

| 操作 | 耗时 | 说明 |
|------|------|------|
| 模型加载 | 0.23s | 非常快，适合集成 |
| 首次推理 | 8.08s | MLX编译/预热，仅一次 |
| 后续推理 | ~1.3s/帧 | 稳定快速 |
| 多目标检测 (3个提示) | 3.99s | 顺序执行 |
| 视频处理 (3帧) | 4.07s | ~1.3s/帧 |
| **总计** | **19.00s** | 包含所有演示 |

**关键发现**:
- ✅ 模型加载极快 (0.23s)
- ✅ 首次推理后性能稳定 (~1.3s/帧)
- ✅ 检测质量高 (视频帧中检测到4-5个人物)
- ✅ 分割掩码精确 (已保存为PNG)
- ✅ 视频帧处理可行 (为视频跟踪做准备)

## API 接口

### SAM3Demo 类

```python
class SAM3Demo:
    def __init__(self, model_path: str, score_threshold: float = 0.3)
    
    def detect_objects(
        self, 
        image: Image.Image, 
        text_prompt: str
    ) -> DetectionResult
    
    def detect_multiple_objects(
        self,
        image: Image.Image,
        text_prompts: List[str]
    ) -> DetectionResult
    
    def detect_with_box_guidance(
        self,
        image: Image.Image,
        text_prompt: str,
        boxes: np.ndarray  # (N, 4) xyxy格式
    ) -> DetectionResult
    
    def extract_video_frames(
        self,
        video_path: str,
        output_dir: str,
        num_frames: int = 5
    ) -> List[str]
    
    def visualize_detection(
        self,
        image: Image.Image,
        result: DetectionResult,
        output_path: str,
        show_masks: bool = True,
        show_boxes: bool = True
    )
```

### DetectionResult 数据结构

```python
@dataclass
class DetectionResult:
    boxes: np.ndarray   # (N, 4) xyxy格式的边界框
    masks: np.ndarray   # (N, H, W) 二值分割掩码
    scores: np.ndarray  # (N,) 置信度分数
    labels: List[str]   # 物体标签
```

## VATools 集成考虑

### 后端集成路径

1. **创建 SAM 服务模块** (`backend/app/services/sam_service.py`)
   ```python
   class SAMService:
       def __init__(self):
           self.model = None
       
       def load_model(self, model_path: str):
           # 延迟加载模型
           
       def detect_objects(self, image_path: str, prompt: str):
           # 返回检测结果
           
       def segment_objects(self, image_path: str, prompt: str):
           # 返回分割掩码
   ```

2. **添加 API 路由** (`backend/app/routes/sam.py`)
   ```python
   @bp.route('/sam/detect', methods=['POST'])
   def detect():
       # 接收图片和提示，返回检测结果
       
   @bp.route('/sam/segment', methods=['POST'])
   def segment():
       # 接收图片和提示，返回分割掩码
   ```

3. **配置项** (`backend/app/config.py`)
   ```python
   SAM_MODEL_DIR = '/Users/lwz/.cache/modelscope/hub/models/mlx-community/sam3___1-bf16'
   SAM_SCORE_THRESHOLD = 0.3
   ```

### 前端集成路径

1. **新增 SAM 页面** (`frontend/src/components/SAMProcessor.tsx`)
   - 图片上传
   - 文本提示输入
   - 检测结果可视化
   - 分割掩码显示

2. **API 调用** (`frontend/src/services/api.ts`)
   ```typescript
   export const detectObjects = async (imageId: number, prompt: string) => {
       return api.post('/sam/detect', { image_id: imageId, prompt })
   }
   ```

### 性能优化建议

1. **模型缓存**: 首次加载后保持模型在内存中
2. **批量处理**: 支持批量图片检测
3. **异步处理**: 使用后台任务处理长时间检测
4. **结果缓存**: 缓存检测结果避免重复计算

## 视频处理能力

### 当前能力

- ✅ 视频帧提取
- ✅ 逐帧检测
- ✅ 逐帧分割

### 未来扩展 (SAM 3.1 原生支持)

SAM 3.1 的 `Sam3VideoModel` 架构原生支持：

1. **视频目标跟踪** - 跨帧跟踪同一物体
2. **时序一致性** - 保持检测结果的时序连贯
3. **遮挡处理** - 处理物体遮挡情况
4. **多目标跟踪** - 同时跟踪多个物体

**实现路径**:
```python
# 未来可以添加视频跟踪功能
def track_objects_in_video(
    self,
    video_path: str,
    text_prompt: str,
    output_video_path: str
):
    """
    在视频中跟踪物体
    
    Args:
        video_path: 输入视频路径
        text_prompt: 要跟踪的物体描述
        output_video_path: 输出视频路径 (带标注)
    """
    # 使用 SAM 3.1 的视频跟踪能力
    # 参考: https://github.com/facebookresearch/sam3
```

## 输出文件说明

```
workspace/sam_demo_output/
├── first_frame.jpg                      # 视频第一帧
├── demo1_person_detection.jpg           # Demo 1: 人物检测可视化
├── demo2_multi_object_detection.jpg     # Demo 2: 多目标检测可视化
├── demo3_instance_segmentation.jpg      # Demo 3: 实例分割可视化
├── demo4_box_guided_detection.jpg       # Demo 4: 框引导检测可视化
├── demo5_video_frame_00.jpg             # Demo 5: 视频帧0检测结果
├── demo5_video_frame_01.jpg             # Demo 5: 视频帧1检测结果
├── demo5_video_frame_02.jpg             # Demo 5: 视频帧2检测结果
├── masks/                               # 分割掩码目录
│   ├── mask_00.png                      # 第1个物体的掩码
│   ├── mask_01.png                      # 第2个物体的掩码
│   ├── mask_02.png                      # 第3个物体的掩码
│   └── mask_03.png                      # 第4个物体的掩码
└── video_frames/                        # 提取的视频帧目录
    ├── frame_00000.jpg                  # 第0帧
    ├── frame_00075.jpg                  # 第75帧
    └── frame_00151.jpg                  # 第151帧
```

## 参考资料

- **SAM 3.1 官方仓库**: https://github.com/facebookresearch/sam3
- **SAM-MLX 转换仓库**: https://github.com/SOSONAGI/SAM-MLX
- **模型下载**: https://huggingface.co/mlx-community/sam3.1-bf16
- **MLX 框架**: https://github.com/ml-explore/mlx

## 注意事项

1. **首次推理较慢**: 首次检测需要约8秒 (MLX编译)，后续推理约1.3秒/帧
2. **内存占用**: 模型加载后约占 3-4GB 内存
3. **图片大小**: 建议输入图片大小在 512x512 到 1024x1024 之间
4. **文本提示**: 使用英文提示效果最佳 (如 "a person", "a dog")
5. **置信度阈值**: 默认 0.3，可根据需要调整

## 下一步

1. ✅ 完成演示脚本
2. ⏳ 集成到 VATools 后端
3. ⏳ 添加前端界面
4. ⏳ 实现视频跟踪功能
5. ⏳ 性能优化 (批量处理、缓存)
