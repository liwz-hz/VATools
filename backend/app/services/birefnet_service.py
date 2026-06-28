"""
BiRefNet Service - High-quality image segmentation and matting
"""
import torch
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Optional, Tuple
from transformers import AutoModelForImageSegmentation
from torchvision import transforms
import time
import traceback
from loguru import logger


class BiRefNetService:
    """Service for BiRefNet image segmentation"""
    
    def __init__(self):
        self.device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.models = {}
        logger.info(f"[BiRefNet] Service initialized, device={self.device}")
    
    def _get_model_paths(self):
        """Get model paths from config, allowing runtime changes"""
        from app.config import Config
        base_dir = Config.BIREFNET_MODEL_DIR
        
        try:
            from app.models import Config as ConfigModel
            config = ConfigModel.query.filter_by(key='birefnet_model_dir').first()
            if config and config.value:
                base_dir = config.value
        except Exception:
            pass
        
        return {
            "dynamic": f"{base_dir}/BiRefNet_dynamic",
            "general": f"{base_dir}/BiRefNet",
            "hr_matting": f"{base_dir}/BiRefNet_HR-matting",
        }
        
    def load_model(self, model_type: str = "general") -> bool:
        """Load BiRefNet model"""
        if model_type in self.models:
            logger.debug(f"[BiRefNet] Model '{model_type}' already loaded")
            return True
        
        model_paths = self._get_model_paths()
        if model_type not in model_paths:
            logger.error(f"[BiRefNet] Unknown model type: {model_type}")
            return False
        
        model_path = model_paths[model_type]
        if not Path(model_path).exists():
            logger.error(f"[BiRefNet] Model path not found: {model_path}")
            return False
        
        try:
            logger.info(f"[BiRefNet] Loading model '{model_type}' from {model_path}")
            start = time.time()
            
            model = AutoModelForImageSegmentation.from_pretrained(
                model_path,
                trust_remote_code=True
            )
            model.to(self.device)
            
            if self.device.type == "mps":
                model = model.float()
                logger.debug("[BiRefNet] Converted model to float32 for MPS")
                
            model.eval()
            
            self.models[model_type] = model
            load_time = time.time() - start
            logger.info(f"[BiRefNet] Model '{model_type}' loaded in {load_time:.2f}s on {self.device}")
            return True
            
        except Exception as e:
            logger.error(f"[BiRefNet] Failed to load model '{model_type}': {e}")
            logger.error(traceback.format_exc())
            return False
    
    def segment_image(
        self,
        image: Image.Image,
        model_type: str = "dynamic",
        output_size: Optional[Tuple[int, int]] = None
    ) -> Optional[Image.Image]:
        """
        Segment image and return mask
        
        Args:
            image: PIL Image to segment
            model_type: "dynamic", "general" or "hr_matting"
            output_size: Optional output size (width, height), defaults to input size
            
        Returns:
            PIL Image mask (grayscale) or None if failed
        """
        if not self.load_model(model_type):
            return None
        
        model = self.models[model_type]
        original_size = image.size
        
        if model_type == "dynamic":
            w, h = original_size
            valid_h = self._nearest_valid_dynamic_dim(h)
            valid_w = self._nearest_valid_dynamic_dim(w)
            input_size = (valid_h, valid_w)
            logger.debug(f"[BiRefNet] Dynamic mode: input={original_size}, processing={input_size}")
        elif model_type == "hr_matting":
            input_size = (2048, 2048)
        else:
            input_size = (1024, 1024)
        
        logger.debug(f"[BiRefNet] segment_image: model={model_type}, input_size={input_size}, original={original_size}")
        
        transform = transforms.Compose([
            transforms.Resize(input_size),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        
        input_tensor = transform(image).unsqueeze(0).to(self.device)
        
        try:
            start = time.time()
            with torch.no_grad():
                preds = model(input_tensor)[-1].sigmoid().cpu()
            infer_time = time.time() - start
            
            pred = preds[0].squeeze()
            mask = transforms.ToPILImage()(pred)
            
            if output_size:
                mask = mask.resize(output_size, Image.Resampling.BILINEAR)
            else:
                mask = mask.resize(original_size, Image.Resampling.BILINEAR)
            
            logger.info(f"[BiRefNet] Segmentation done: {infer_time:.2f}s, output={mask.size}")
            return mask
            
        except Exception as e:
            logger.error(f"[BiRefNet] Segmentation failed: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def remove_background(
        self,
        image: Image.Image,
        model_type: str = "dynamic"
    ) -> Optional[Image.Image]:
        """
        Remove background from image
        
        Args:
            image: PIL Image
            model_type: "dynamic", "general" or "hr_matting"
            
        Returns:
            PIL Image with transparent background or None if failed
        """
        logger.debug(f"[BiRefNet] remove_background: model={model_type}, image_size={image.size}")
        
        mask = self.segment_image(image, model_type)
        if mask is None:
            logger.error("[BiRefNet] remove_background failed: segmentation returned None")
            return None
        
        image_rgba = image.convert("RGBA")
        mask_array = np.array(mask)
        image_array = np.array(image_rgba)
        image_array[:, :, 3] = mask_array
        
        logger.info(f"[BiRefNet] Background removed: output_size={image.size}")
        return Image.fromarray(image_array)
    
    def get_available_models(self) -> list:
        """Get list of available models"""
        available = []
        for model_type, model_path in self._get_model_paths().items():
            if Path(model_path).exists():
                available.append({
                    "type": model_type,
                    "path": model_path,
                    "loaded": model_type in self.models
                })
        return available
    
    def _round_to_multiple(self, value: int, multiple: int) -> int:
        """Round value to nearest multiple"""
        return round(value / multiple) * multiple
    
    def _nearest_valid_dynamic_dim(self, dim: int) -> int:
        """
        Find nearest valid dimension for BiRefNet dynamic model.
        The Pv2 backbone uses OverlapPatchEmbed with stride chain 4→2→2→2,
        producing x4 feature map at ~1/32 resolution. The input dim must be
        exactly divisible by the x4 feature map size for einops rearrange.
        """
        def compute_x4(d):
            # PyTorch Conv2d output: floor((d + 2*pad - kernel) / stride) + 1
            x = (d + 2*3 - 7) // 4 + 1   # patch_embed1: kernel=7, stride=4, pad=3
            x = (x + 2*1 - 3) // 2 + 1   # patch_embed2: kernel=3, stride=2, pad=1
            x = (x + 2*1 - 3) // 2 + 1   # patch_embed3: kernel=3, stride=2, pad=1
            x = (x + 2*1 - 3) // 2 + 1   # patch_embed4: kernel=3, stride=2, pad=1
            return x
        
        def is_valid(d):
            if d < 64:
                return False
            x4 = compute_x4(d)
            return x4 > 0 and d % x4 == 0
        
        if is_valid(dim):
            return dim
        
        for offset in range(1, 500):
            if is_valid(dim + offset):
                return dim + offset
            if is_valid(dim - offset):
                return dim - offset
        
        return dim


birefnet_service = BiRefNetService()
