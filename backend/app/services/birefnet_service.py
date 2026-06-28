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


class BiRefNetService:
    """Service for BiRefNet image segmentation"""
    
    def __init__(self):
        self.device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.models = {}
        self.model_paths = {
            "dynamic": "/Users/lwz/.cache/modelscope/hub/models/birefnet/BiRefNet_dynamic",
            "general": "/Users/lwz/.cache/modelscope/hub/models/birefnet/BiRefNet",
            "hr_matting": "/Users/lwz/.cache/modelscope/hub/models/birefnet/BiRefNet_HR-matting",
        }
        
    def load_model(self, model_type: str = "general") -> bool:
        """Load BiRefNet model"""
        if model_type in self.models:
            return True
            
        if model_type not in self.model_paths:
            print(f"Unknown model type: {model_type}")
            return False
            
        model_path = self.model_paths[model_type]
        if not Path(model_path).exists():
            print(f"Model not found: {model_path}")
            return False
        
        try:
            print(f"Loading BiRefNet {model_type} model...")
            start = time.time()
            
            model = AutoModelForImageSegmentation.from_pretrained(
                model_path,
                trust_remote_code=True
            )
            model.to(self.device)
            
            # Convert to float32 for MPS compatibility
            if self.device.type == "mps":
                model = model.float()
                
            model.eval()
            
            self.models[model_type] = model
            load_time = time.time() - start
            print(f"✓ Model loaded in {load_time:.2f}s")
            return True
            
        except Exception as e:
            print(f"✗ Failed to load model: {e}")
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
        
        # Determine input size based on model
        if model_type == "dynamic":
            # Use native resolution, round to multiple of 8 for optimal performance
            w, h = original_size
            input_size = (self._round_to_multiple(h, 8), self._round_to_multiple(w, 8))
            print(f"Dynamic mode: using native resolution {input_size}")
        elif model_type == "hr_matting":
            input_size = (2048, 2048)
        else:
            input_size = (1024, 1024)
        
        # Preprocessing
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
            print(f"Inference: {infer_time:.2f}s")
            
            # Convert to PIL Image
            pred = preds[0].squeeze()
            mask = transforms.ToPILImage()(pred)
            
            # Resize to output size
            if output_size:
                mask = mask.resize(output_size, Image.Resampling.BILINEAR)
            else:
                mask = mask.resize(original_size, Image.Resampling.BILINEAR)
            
            return mask
            
        except Exception as e:
            print(f"Segmentation failed: {e}")
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
        mask = self.segment_image(image, model_type)
        if mask is None:
            return None
        
        # Convert to RGBA
        image_rgba = image.convert("RGBA")
        
        # Apply mask as alpha channel
        mask_array = np.array(mask)
        image_array = np.array(image_rgba)
        image_array[:, :, 3] = mask_array
        
        return Image.fromarray(image_array)
    
    def get_available_models(self) -> list:
        """Get list of available models"""
        available = []
        for model_type, model_path in self.model_paths.items():
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


# Global service instance
birefnet_service = BiRefNetService()
