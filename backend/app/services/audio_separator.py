import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from flask import current_app
from app import db, socketio
from app.models import Task, File
from app.config import Config
from loguru import logger
from sqlalchemy.orm import scoped_session, sessionmaker
import json

# 支持的音源分离引擎
SEPARATION_ENGINES = {
    'spleeter': {
        'name': 'Spleeter',
        'models': {
            '2stems': {
                'description': '人声/伴奏分离（2轨）',
                'stems': ['vocals', 'accompaniment'],
                'files': ['model.data-00000-of-00001', 'model.index', 'model.meta']
            },
            '4stems': {
                'description': '人声/鼓点/贝斯/伴奏分离（4轨）',
                'stems': ['vocals', 'drums', 'bass', 'other'],
                'files': ['model.data-00000-of-00001', 'model.index', 'model.meta']
            }
        }
    },
    'demucs': {
        'name': 'Demucs',
        'models': {
            'htdemucs_ft': {
                'description': 'Hybrid Transformer Demucs (快速版)',
                'stems': ['vocals', 'drums', 'bass', 'other'],
                'files': ['f7e0c4bc-ba3fe64a.th', 'd12395a8-e57c48e6.th']
            },
            'htdemucs': {
                'description': 'Hybrid Transformer Demucs',
                'stems': ['vocals', 'drums', 'bass', 'other'],
                'files': ['955717e8-8726e21a.th']
            }
        }
    }
}

# 常见模型搜索路径
MODEL_SEARCH_PATHS = [
    # UVR 默认路径（macOS）
    '/Applications/Ultimate Vocal Remover.app/Contents/Resources/models',
    '~/Library/Application Support/Ultimate Vocal Remover/models',
    '~/Library/Application Support/UVR/models',
    '~/UVR_models',
    '~/Documents/UVR_models',
    # Spleeter 默认路径
    '~/.spleeter/models',
    # Demucs 默认路径
    '~/.cache/demucs',
    '~/.torch/models',
    # 用户自定义
    '~/models/audio_separation',
]

def scan_for_models():
    """扫描系统中已安装的音源分离模型"""
    found_models = {
        'spleeter': {},
        'demucs': {}
    }
    
    for base_path in MODEL_SEARCH_PATHS:
        expanded_path = Path(base_path).expanduser()
        if not expanded_path.exists():
            continue
        
        # 扫描 Spleeter 模型
        spleeter_dir = expanded_path / 'spleeter' if expanded_path.name != 'spleeter' else expanded_path
        if spleeter_dir.exists():
            for model_name in ['2stems', '4stems']:
                model_path = spleeter_dir / model_name
                if model_path.exists() and check_spleeter_model(model_path):
                    found_models['spleeter'][model_name] = str(model_path)
        
        # 直接扫描目录
        for model_name in ['2stems', '4stems']:
            model_path = expanded_path / model_name
            if model_path.exists() and check_spleeter_model(model_path):
                found_models['spleeter'][model_name] = str(model_path)
        
        # 扫描 UVR Demucs 模型（v3_v4_repo 目录结构）
        uvr_demucs_dir = expanded_path / 'Demucs_Models' / 'v3_v4_repo'
        if uvr_demucs_dir.exists():
            for model_name in ['htdemucs_ft', 'htdemucs']:
                if check_uvr_demucs_model(uvr_demucs_dir, model_name):
                    found_models['demucs'][model_name] = str(uvr_demucs_dir)
        
        # 扫描普通 Demucs 目录
        demucs_dir = expanded_path / 'demucs' if expanded_path.name != 'demucs' else expanded_path
        if demucs_dir.exists():
            for model_name in ['htdemucs_ft', 'htdemucs']:
                if check_demucs_model(demucs_dir, model_name):
                    found_models['demucs'][model_name] = str(demucs_dir)
        
        # 直接扫描 Demucs 模型文件
        for model_file in expanded_path.glob('*.th'):
            if 'htdemucs' in model_file.name:
                found_models['demucs']['htdemucs'] = str(expanded_path)
                break
    
    return found_models

def check_spleeter_model(model_path: Path) -> bool:
    """检查 Spleeter 模型是否完整"""
    required_files = ['model.meta', 'model.index']
    for file in required_files:
        if not (model_path / file).exists():
            return False
    return True

def check_demucs_model(model_dir: Path, model_name: str) -> bool:
    """检查 Demucs 模型是否存在"""
    if model_name == 'htdemucs_ft':
        return (model_dir / 'f7e0c4bc-ba3fe64a.th').exists()
    elif model_name == 'htdemucs':
        return (model_dir / '955717e8-8726e21a.th').exists()
    return False

def check_uvr_demucs_model(uvr_dir: Path, model_name: str) -> bool:
    """检查 UVR Demucs 模型是否存在（通过配置文件）"""
    config_file = uvr_dir / f'{model_name}.yaml'
    if not config_file.exists():
        return False
    
    # 解析配置文件获取模型ID列表
    try:
        import yaml
        with open(config_file) as f:
            config = yaml.safe_load(f)
        
        model_ids = config.get('models', [])
        # 检查所有模型文件是否存在
        for model_id in model_ids:
            # UVR 模型文件格式：{model_id}-{hash}.th
            matching_files = list(uvr_dir.glob(f'{model_id}-*.th'))
            if not matching_files:
                return False
        
        return True
    except:
        return False

def get_model_dir():
    """获取配置的模型目录"""
    # 从配置读取
    model_dir = getattr(Config, 'SEPARATION_MODEL_DIR', None)
    if model_dir and Path(model_dir).exists():
        return model_dir
    
    # 尝试从数据库配置读取
    try:
        from app.models import Config as ConfigModel
        config = ConfigModel.query.filter_by(key='separation_model_dir').first()
        if config and Path(config.value).exists():
            return config.value
    except:
        pass
    
    return None

def get_available_models():
    """获取所有可用的模型"""
    # 如果配置了模型目录，优先使用
    configured_dir = get_model_dir()
    if configured_dir:
        models = scan_model_directory(Path(configured_dir))
        if models:
            return models
    
    # 否则扫描整个系统
    return scan_for_models()

def scan_model_directory(model_dir: Path):
    """扫描指定目录的模型"""
    models = {
        'spleeter': {},
        'demucs': {}
    }
    
    # 扫描 Spleeter 模型
    for model_name in ['2stems', '4stems']:
        model_path = model_dir / model_name
        if model_path.exists() and check_spleeter_model(model_path):
            models['spleeter'][model_name] = str(model_path)
    
    # 扫描 UVR Demucs 模型（v3_v4_repo 目录结构）
    uvr_demucs_dir = model_dir / 'Demucs_Models' / 'v3_v4_repo'
    if uvr_demucs_dir.exists():
        for model_name in ['htdemucs_ft', 'htdemucs']:
            if check_uvr_demucs_model(uvr_demucs_dir, model_name):
                models['demucs'][model_name] = str(uvr_demucs_dir)
    
    # 扫描普通 Demucs 模型
    for model_name in ['htdemucs_ft', 'htdemucs']:
        if check_demucs_model(model_dir, model_name):
            models['demucs'][model_name] = str(model_dir)
    
    return models

def check_engine_available(engine: str) -> tuple:
    """检查音源分离引擎是否可用"""
    if engine == 'spleeter':
        try:
            from spleeter.separator import Separator
            return True, None
        except ImportError:
            return False, "Spleeter 未安装。安装: pip install spleeter==2.4.0"
    elif engine == 'demucs':
        try:
            import torch
            return True, None
        except ImportError:
            return False, "PyTorch 未安装。安装: pip install torch"
    
    return False, f"不支持的引擎: {engine}"

def get_separation_status():
    """获取音源分离功能完整状态"""
    status = {
        'configured_model_dir': get_model_dir(),
        'engines': {},
        'available_models': get_available_models(),
        'search_paths': [str(Path(p).expanduser()) for p in MODEL_SEARCH_PATHS]
    }
    
    for engine_id, engine_info in SEPARATION_ENGINES.items():
        available, error = check_engine_available(engine_id)
        status['engines'][engine_id] = {
            'name': engine_info['name'],
            'available': available,
            'error': error if not available else None,
            'models': {}
        }
        
        if available:
            for model_id, model_info in engine_info['models'].items():
                model_path = status['available_models'].get(engine_id, {}).get(model_id)
                status['engines'][engine_id]['models'][model_id] = {
                    'description': model_info['description'],
                    'stems': model_info['stems'],
                    'available': model_path is not None,
                    'path': model_path
                }
    
    return status

def update_task_progress(task, session, progress, status):
    """更新任务进度（数据库 + socket通知）"""
    task.progress = progress
    session.commit()
    
    socketio.emit('task_progress', {
        'task_id': task.id,
        'progress': progress,
        'status': status
    }, namespace='/')
    
    logger.info(f"Task {task.id}: 进度 {progress}% - {status}")

def process_audio_separation(task_id: int, app):
    """处理音频分离任务"""
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
            
            stems = params.get('stems', ['vocals', 'drums', 'bass', 'other'])
            engine = params.get('engine', 'spleeter')
            
            # 检查引擎
            available, error = check_engine_available(engine)
            if not available:
                raise Exception(error)
            
            # 检查模型目录
            model_dir = get_model_dir()
            if not model_dir:
                # 尝试扫描可用模型
                models = get_available_models()
                if not models.get(engine):
                    raise Exception(
                        "未配置音源分离模型目录！\n\n"
                        "请在设置中配置模型目录，或手动指定模型路径。\n\n"
                        f"已扫描的路径：\n{chr(10).join(MODEL_SEARCH_PATHS)}\n\n"
                        "提示：UVR 模型通常位于 ~/Library/Application Support/Ultimate Vocal Remover/models/"
                    )
            
            task.progress = 10
            session.commit()
            
            socketio.emit('task_progress', {
                'task_id': task.id,
                'progress': 10,
                'status': 'processing'
            }, namespace='/')
            
            logger.info(f"Task {task.id}: 发送进度更新 10%")
            
            # 根据引擎选择处理方式
            if engine == 'spleeter':
                result = process_with_spleeter(task, audio_file, stems, session, model_dir)
            elif engine == 'demucs':
                result = process_with_demucs(task, audio_file, stems, session, model_dir)
            else:
                raise Exception(f"不支持的引擎: {engine}")
            
            task.output_file = ','.join(result['output_files'])
            task.status = 'completed'
            task.progress = 100
            task.completed_at = datetime.now(timezone.utc)
            session.commit()
            
            socketio.emit('task_completed', {
                'task_id': task.id,
                'output_files': result['output_files']
            }, namespace='/')
            
            logger.info(f"Audio separation task {task_id} completed")
            
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
                
                logger.error(f"Audio separation task {task_id} failed: {str(e)}")
        finally:
            session.remove()

def process_with_spleeter(task, audio_file, stems, session, model_dir):
    """使用 Spleeter 处理"""
    from spleeter.separator import Separator
    
    # 确定模型
    if 'vocals' in stems and len(stems) == 1:
        model_name = '2stems'
    else:
        model_name = '4stems'
    
    # 获取模型路径
    models = get_available_models()
    model_path = models.get('spleeter', {}).get(model_name)
    
    if not model_path:
        raise Exception(f"未找到 Spleeter {model_name} 模型")
    
    socketio.emit('task_progress', {
        'task_id': task.id,
        'progress': 30,
        'status': 'processing'
    }, namespace='/')
    
    separator = Separator(str(Path(model_path).parent if Path(model_path).is_file() else model_path), multiprocess=False)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = os.path.join(Config.WORKSPACE_DIR, 'separated', timestamp)
    
    logger.info(f"Starting Spleeter separation with model: {model_name}")
    separator.separate_to_file(
        audio_file.file_path,
        output_dir,
        codec='wav',
        offset=0,
        duration=None
    )
    
    socketio.emit('task_progress', {
        'task_id': task.id,
        'progress': 80,
        'status': 'processing'
    }, namespace='/')
    
    output_files = []
    base_name = Path(audio_file.filename).stem
    
    for stem in stems:
        stem_path = os.path.join(output_dir, base_name, f'{stem}.wav')
        if os.path.exists(stem_path):
            output_filename = f"{timestamp}_{stem}.wav"
            final_path = os.path.join(Config.WORKSPACE_DIR, 'separated', output_filename)
            
            os.makedirs(os.path.dirname(final_path), exist_ok=True)
            os.rename(stem_path, final_path)
            
            file_size = os.path.getsize(final_path)
            output_file = File(
                filename=output_filename,
                file_path=final_path,
                file_type='audio',
                file_size=file_size
            )
            session.add(output_file)
            output_files.append(final_path)  # 返回完整路径而不是文件名
    
    import shutil
    shutil.rmtree(output_dir, ignore_errors=True)
    
    return {'output_files': output_files}

def apply_model_with_progress(model, mix, set_progress_bar, device, shifts=1, split=True, overlap=0.25):
    """带进度回调的apply_model包装函数（参考UVR实现）"""
    import torch as th
    from demucs.apply import TensorChunk, center_trim
    from demucs.apply import BagOfModels
    
    if isinstance(model, BagOfModels):
        estimates = None
        totals = [0.] * len(model.sources)
        num_models = len(model.models)
        
        for idx, (sub_model, weight) in enumerate(zip(model.models, model.weights)):
            set_progress_bar(0.15 + 0.7 * (idx / num_models), f'处理子模型 {idx+1}/{num_models}')
            
            original_device = next(iter(sub_model.parameters())).device
            sub_model.to(device)
            sub_model.eval()
            
            out = apply_model_with_progress(sub_model, mix, lambda a, b: None, device, shifts, split, overlap)
            
            sub_model.to(original_device)
            
            for k, inst_weight in enumerate(weight):
                out[:, k, :, :] *= inst_weight
                totals[k] += inst_weight
            
            if estimates is None:
                estimates = out.clone()
            else:
                estimates += out
            del out
        
        for k in range(estimates.shape[1]):
            estimates[:, k, :, :] /= totals[k]
        
        return estimates
    
    model.to(device)
    model.eval()
    
    batch, channels, length = mix.shape
    out = th.zeros(batch, len(model.sources), channels, length, device=mix.device)
    sum_weight = th.zeros(length, device=mix.device)
    
    segment = int(model.samplerate * model.segment)
    stride = int((1 - overlap) * segment)
    offsets = list(range(0, length, stride))
    total_offsets = len(offsets)
    
    weight = th.cat([
        th.arange(1, segment // 2 + 1, device=device),
        th.arange(segment - segment // 2, 0, -1, device=device)
    ])
    weight = (weight / weight.max())
    
    progress_value = [0]
    
    for offset in offsets:
        chunk = TensorChunk(mix, offset, segment)
        padded_chunk = chunk.padded(segment)
        
        with th.no_grad():
            chunk_out = model(padded_chunk.to(device))
        
        chunk_out = center_trim(chunk_out, chunk.shape[-1])
        chunk_length = chunk_out.shape[-1]
        
        out[..., offset:offset + segment] += (weight[:chunk_length] * chunk_out).to(mix.device)
        sum_weight[offset:offset + segment] += weight[:chunk_length].to(mix.device)
        
        progress_value[0] += 1
        if total_offsets > 0:
            set_progress_bar(0.15 + 0.7 * (progress_value[0] / total_offsets), 
                           f'分段处理 {progress_value[0]}/{total_offsets}')
    
    out /= sum_weight
    return out

def process_with_demucs(task, audio_file, stems, session, model_dir):
    """使用 Demucs 处理"""
    import torch
    import soundfile as sf
    import numpy as np
    import gc
    from demucs.pretrained import BagOnlyRepo, LocalRepo
    
    model_name = task.get_params().get('model', 'htdemucs_ft')
    available_models = get_available_models()
    model_path = available_models.get('demucs', {}).get(model_name)
    
    if not model_path:
        raise Exception(f"未找到本地 Demucs {model_name} 模型。请在设置中配置模型路径，或手动下载模型到本地。")
    
    model_path_obj = Path(model_path)
    if not model_path_obj.exists():
        raise Exception(f"模型路径不存在: {model_path}")
    
    config_file = model_path_obj / f'{model_name}.yaml'
    if not config_file.exists():
        raise Exception(f"未找到模型配置文件: {config_file}")
    
    import yaml
    with open(config_file) as f:
        config = yaml.safe_load(f)
    
    model_ids = config.get('models', [])
    missing_models = []
    for model_id in model_ids:
        matching_files = list(model_path_obj.glob(f'{model_id}-*.th'))
        if not matching_files:
            missing_models.append(model_id)
    
    if missing_models:
        raise Exception(
            f"本地模型不完整，缺少模型文件: {', '.join(missing_models)}\n"
            f"请检查模型目录: {model_path}\n"
            f"或从 UVR 安装目录复制模型文件。"
        )
    
    acceleration = Config.ACCELERATION_TYPE
    device = 'cpu'
    
    if acceleration == 'auto':
        if torch.backends.mps.is_available():
            device = 'mps'
        elif torch.cuda.is_available():
            device = 'cuda'
    elif acceleration == 'mps' and torch.backends.mps.is_available():
        device = 'mps'
    elif acceleration == 'cuda' and torch.cuda.is_available():
        device = 'cuda'
    
    logger.info(f"Task {task.id}: 加速设置={acceleration}, 使用设备={device}")
    
    update_task_progress(task, session, 5, f'加载模型 {model_name}')
    
    original_load = torch.load
    def patched_load(*args, **kwargs):
        kwargs['weights_only'] = False
        return original_load(*args, **kwargs)
    torch.load = patched_load
    
    try:
        model_repo = LocalRepo(model_path_obj)
        bag_repo = BagOnlyRepo(model_path_obj, model_repo)
        
        if not bag_repo.has_model(model_name):
            raise Exception(f"本地模型库中未找到 {model_name}")
        
        model_obj = bag_repo.get_model(model_name)
        logger.info(f"Task {task.id}: 模型加载完成, 类型={type(model_obj).__name__}")
        
        model_obj.to(device)
        model_obj.eval()
        
        gc.collect()
        if device == 'mps':
            torch.mps.empty_cache()
        elif device == 'cuda':
            torch.cuda.empty_cache()
        
        update_task_progress(task, session, 10, '读取音频文件...')
        
        import librosa
        wav_np, sr = librosa.load(audio_file.file_path, mono=False, sr=44100)
        logger.info(f"Task {task.id}: 音频读取完成, shape={wav_np.shape}, sr={sr}")
        
        if wav_np.ndim == 1:
            wav_np = np.asfortranarray([wav_np, wav_np])
        
        wav = torch.from_numpy(wav_np).float()
        
        update_task_progress(task, session, 15, '准备音频数据...')
        
        ref = wav.mean(0)
        wav_norm = (wav - ref.mean()) / ref.std()
        
        logger.info(f"Task {task.id}: 音频归一化完成")
        
        def progress_callback(progress, status):
            pct = int(progress * 100)
            update_task_progress(task, session, pct, status)
        
        logger.info(f"Task {task.id}: 开始音源分离...")
        
        sources = apply_model_with_progress(
            model_obj, 
            wav_norm[None],
            progress_callback,
            device,
            shifts=1,
            split=True,
            overlap=0.25
        )
        
        logger.info(f"Task {task.id}: apply_model完成, shape={sources.shape}")
        
        sources = sources[0]
        sources = (sources * ref.std() + ref.mean())
        
        sources[[0, 1]] = sources[[1, 0]]
        
        for i in range(sources.shape[0]):
            rms = torch.sqrt(torch.mean(sources[i]**2)).item()
            logger.info(f"Task {task.id}: Source {i} RMS={rms:.6f}")
        
        gc.collect()
        if device == 'mps':
            torch.mps.empty_cache()
        elif device == 'cuda':
            torch.cuda.empty_cache()
        
        update_task_progress(task, session, 90, '保存文件...')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = os.path.join(Config.WORKSPACE_DIR, 'separated')
        os.makedirs(output_dir, exist_ok=True)
        
        output_files = []
        stem_names = ['drums', 'bass', 'other', 'vocals']
        
        for idx, source in enumerate(sources):
            stem_name = stem_names[idx]
            if stem_name in stems:
                output_filename = f"{timestamp}_{stem_name}.wav"
                final_path = os.path.join(output_dir, output_filename)
                
                source_np = source.cpu().numpy().T
                sf.write(final_path, source_np, 44100)
                
                file_size = os.path.getsize(final_path)
                output_file = File(
                    filename=output_filename,
                    file_path=final_path,
                    file_type='audio',
                    file_size=file_size
                )
                session.add(output_file)
                output_files.append(final_path)
        
        return {'output_files': output_files}
    
    finally:
        torch.load = original_load

def start_audio_separation(audio_file_id: int, stems=None, engine='demucs', model='htdemucs_ft'):
    """启动音频分离任务"""
    if stems is None:
        stems = ['vocals', 'drums', 'bass', 'other']
    
    audio_file = db.session.get(File, audio_file_id)
    if not audio_file:
        return None, "音频文件未找到"
    
    task = Task(
        task_type='audio_separation',
        status='pending',
        input_file=audio_file.file_path
    )
    task.set_params({
        'audio_file_id': audio_file_id,
        'stems': stems,
        'engine': engine,
        'model': model
    })
    
    db.session.add(task)
    db.session.commit()
    
    from flask import current_app
    app = current_app._get_current_object()
    
    # 使用threading.Thread，前端通过轮询查询进度
    thread = threading.Thread(target=process_audio_separation, args=(task.id, app))
    thread.daemon = True
    thread.start()
    
    return task.id, None
