"""
SAM 3.1 Image Segmentation Service
Provides object detection, segmentation, and extraction capabilities
"""
import os
import io
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from loguru import logger
import traceback

# MLX and SAM imports
import mlx.core as mx
from mlx_vlm.utils import load_model
from mlx_vlm.models.sam3.generate import Sam3Predictor
from mlx_vlm.models.sam3_1.processing_sam3_1 import Sam31Processor

from app.config import Config


class SAMService:
    """SAM 3.1 Model Service for image segmentation"""
    
    _instance = None
    _model = None
    _processor = None
    _predictor = None
    
    @classmethod
    def get_instance(cls) -> 'SAMService':
        """Singleton pattern to ensure single model instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self.model_path = Config.SAM_MODEL_DIR
        self.score_threshold = Config.SAM_SCORE_THRESHOLD
    
    def load_model(self) -> bool:
        """Load SAM model if not already loaded"""
        if self._predictor is not None:
            return True
        
        try:
            logger.info(f"Loading SAM model from: {self.model_path}")
            
            model_path = Path(self.model_path)
            if not model_path.exists():
                logger.error(f"Model path does not exist: {self.model_path}")
                return False
            
            self._model = load_model(model_path)
            self._processor = Sam31Processor.from_pretrained(str(model_path))
            self._predictor = Sam3Predictor(
                self._model,
                self._processor,
                score_threshold=self.score_threshold
            )
            
            logger.info("SAM model loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"[SAM] Failed to load model: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self._predictor is not None
    
    def detect_objects(
        self,
        image: Image.Image,
        text_prompt: str
    ) -> Optional[Dict]:
        """
        Detect objects in image using text prompt
        
        Args:
            image: PIL Image
            text_prompt: Text description (e.g., "a person")
            
        Returns:
            Dict with boxes, masks, scores or None if failed
        """
        if not self.load_model():
            return None
        
        try:
            result = self._predictor.predict(image, text_prompt=text_prompt)
            
            return {
                'boxes': np.array(result.boxes).tolist(),
                'masks': np.array(result.masks).tolist(),
                'scores': np.array(result.scores).tolist(),
                'labels': [text_prompt] * len(result.scores)
            }
        except Exception as e:
            logger.error(f"[SAM] Detection failed: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def extract_object(
        self,
        image: Image.Image,
        mask: np.ndarray,
        box: Optional[List[float]] = None
    ) -> Optional[Image.Image]:
        """
        Extract object from image using mask
        
        Args:
            image: Original PIL Image
            mask: Binary mask (H, W)
            box: Optional bounding box to crop [x1, y1, x2, y2]
            
        Returns:
            Extracted object as PIL Image with transparency or None
        """
        try:
            img_array = np.array(image.convert('RGBA'))
            W, H = image.size
            
            # Resize mask if needed
            if mask.shape != (H, W):
                mask_pil = Image.fromarray(mask.astype(np.float32))
                mask_pil = mask_pil.resize((W, H), Image.Resampling.NEAREST)
                mask = np.array(mask_pil)
            
            # Create binary mask
            binary_mask = mask > 0
            
            # Apply mask to alpha channel
            img_array[:, :, 3] = (binary_mask * 255).astype(np.uint8)
            
            result = Image.fromarray(img_array)
            
            # Crop to bounding box if provided
            if box is not None:
                x1, y1, x2, y2 = [int(v) for v in box]
                result = result.crop((x1, y1, x2, y2))
            
            return result
            
        except Exception as e:
            logger.error(f"[SAM] Extraction failed: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def remove_background(
        self,
        image: Image.Image,
        text_prompt: str = "a person"
    ) -> Optional[Image.Image]:
        """
        Remove background from image, keeping only detected objects
        
        Args:
            image: PIL Image
            text_prompt: What to keep (default: "a person")
            
        Returns:
            Image with background removed or None
        """
        detection = self.detect_objects(image, text_prompt)
        
        if not detection or len(detection['masks']) == 0:
            logger.warning("No objects detected for background removal")
            return None
        
        # Combine all masks
        combined_mask = np.zeros_like(detection['masks'][0])
        for mask in detection['masks']:
            combined_mask = np.maximum(combined_mask, mask)
        
        return self.extract_object(image, combined_mask)
    
    def create_visualization(
        self,
        image: Image.Image,
        detection: Dict,
        show_masks: bool = True,
        show_boxes: bool = True
    ) -> Image.Image:
        """
        Create visualization with boxes and masks overlay
        
        Args:
            image: Original PIL Image
            detection: Detection result dict
            show_masks: Whether to show segmentation masks
            show_boxes: Whether to show bounding boxes
            
        Returns:
            Visualization as PIL Image
        """
        import cv2
        
        img_array = np.array(image)
        overlay = img_array.copy()
        
        colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
        ]
        
        W, H = image.size
        
        for i in range(len(detection['scores'])):
            color = colors[i % len(colors)]
            score = detection['scores'][i]
            label = detection['labels'][i] if i < len(detection['labels']) else "object"
            
            # Draw mask
            if show_masks and i < len(detection['masks']):
                mask = np.array(detection['masks'][i])
                
                if mask.shape != (H, W):
                    mask_pil = Image.fromarray(mask.astype(np.float32))
                    mask_pil = mask_pil.resize((W, H), Image.Resampling.NEAREST)
                    mask = np.array(mask_pil)
                
                binary_mask = mask > 0
                overlay[binary_mask] = (
                    overlay[binary_mask] * 0.5 +
                    np.array(color) * 0.5
                ).astype(np.uint8)
            
            # Draw box
            if show_boxes and i < len(detection['boxes']):
                x1, y1, x2, y2 = [int(v) for v in detection['boxes'][i]]
                
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 3)
                
                label_text = f"{label}: {score:.2f}"
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.6
                thickness = 2
                
                (text_w, text_h), baseline = cv2.getTextSize(
                    label_text, font, font_scale, thickness
                )
                
                cv2.rectangle(
                    overlay,
                    (x1, y1 - text_h - 10),
                    (x1 + text_w, y1),
                    color,
                    -1
                )
                
                cv2.putText(
                    overlay,
                    label_text,
                    (x1, y1 - 5),
                    font,
                    font_scale,
                    (255, 255, 255),
                    thickness
                )
        
        return Image.fromarray(overlay)


# Global service instance
sam_service = SAMService.get_instance()
