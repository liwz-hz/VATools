#!/usr/bin/env python3
"""
SAM 3.1 MLX Demo Script
Demonstrates object detection, instance segmentation, and video frame processing
using the SAM 3.1 model on Apple Silicon (MLX).

Model: mlx-community/sam3.1-bf16 (local)
Capabilities:
  - Open-vocabulary object detection
  - Instance segmentation
  - Multi-object detection
  - Box-guided detection
  - Video frame processing
"""

import os
import sys
import time
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

# Image/Video processing
from PIL import Image
import cv2

# MLX and SAM
import mlx.core as mx
from mlx_vlm.utils import load_model, get_model_path
from mlx_vlm.models.sam3.generate import Sam3Predictor, predict_multi
from mlx_vlm.models.sam3_1.processing_sam3_1 import Sam31Processor


@dataclass
class DetectionResult:
    """Detection result container"""
    boxes: np.ndarray  # (N, 4) xyxy format
    masks: np.ndarray  # (N, H, W) binary masks
    scores: np.ndarray  # (N,) confidence scores
    labels: List[str]  # Object labels


class SAM3Demo:
    """SAM 3.1 Model Demo Class"""
    
    def __init__(self, model_path: str, score_threshold: float = 0.3):
        """
        Initialize SAM 3.1 model
        
        Args:
            model_path: Path to local model directory
            score_threshold: Confidence threshold for detections
        """
        print(f"Loading SAM 3.1 model from: {model_path}")
        start_time = time.time()
        
        self.model_path = Path(model_path)
        self.model = load_model(self.model_path)
        self.processor = Sam31Processor.from_pretrained(str(self.model_path))
        self.predictor = Sam3Predictor(
            self.model, 
            self.processor, 
            score_threshold=score_threshold
        )
        
        load_time = time.time() - start_time
        print(f"✓ Model loaded in {load_time:.2f}s")
        print(f"  Score threshold: {score_threshold}")
    
    def detect_objects(
        self, 
        image: Image.Image, 
        text_prompt: str
    ) -> DetectionResult:
        """
        Detect objects in image using text prompt
        
        Args:
            image: PIL Image
            text_prompt: Text description (e.g., "a person", "a dog")
            
        Returns:
            DetectionResult with boxes, masks, scores
        """
        print(f"\n[Detection] Prompt: '{text_prompt}'")
        start_time = time.time()
        
        result = self.predictor.predict(image, text_prompt=text_prompt)
        
        infer_time = time.time() - start_time
        print(f"✓ Detected {len(result.scores)} objects in {infer_time:.2f}s")
        
        return DetectionResult(
            boxes=np.array(result.boxes),
            masks=np.array(result.masks),
            scores=np.array(result.scores),
            labels=[text_prompt] * len(result.scores)
        )
    
    def detect_multiple_objects(
        self,
        image: Image.Image,
        text_prompts: List[str]
    ) -> DetectionResult:
        """
        Detect multiple object types in image
        
        Args:
            image: PIL Image
            text_prompts: List of text descriptions
            
        Returns:
            DetectionResult with all detections
        """
        print(f"\n[Multi-Detection] Prompts: {text_prompts}")
        start_time = time.time()
        
        result = predict_multi(self.predictor, image, text_prompts)
        
        infer_time = time.time() - start_time
        print(f"✓ Detected {len(result.scores)} objects in {infer_time:.2f}s")
        
        return DetectionResult(
            boxes=np.array(result.boxes),
            masks=np.array(result.masks),
            scores=np.array(result.scores),
            labels=list(result.labels)
        )
    
    def detect_with_box_guidance(
        self,
        image: Image.Image,
        text_prompt: str,
        boxes: np.ndarray
    ) -> DetectionResult:
        """
        Detect objects with bounding box guidance
        
        Args:
            image: PIL Image
            text_prompt: Text description
            boxes: (N, 4) array of xyxy bounding boxes
            
        Returns:
            DetectionResult with refined detections
        """
        print(f"\n[Box-Guided Detection] Prompt: '{text_prompt}', Boxes: {len(boxes)}")
        start_time = time.time()
        
        result = self.predictor.predict(
            image, 
            text_prompt=text_prompt, 
            boxes=boxes
        )
        
        infer_time = time.time() - start_time
        print(f"✓ Detected {len(result.scores)} objects in {infer_time:.2f}s")
        
        return DetectionResult(
            boxes=np.array(result.boxes),
            masks=np.array(result.masks),
            scores=np.array(result.scores),
            labels=[text_prompt] * len(result.scores)
        )
    
    def extract_video_frames(
        self,
        video_path: str,
        output_dir: str,
        num_frames: int = 5
    ) -> List[str]:
        """
        Extract frames from video for processing
        
        Args:
            video_path: Path to video file
            output_dir: Directory to save frames
            num_frames: Number of frames to extract
            
        Returns:
            List of frame file paths
        """
        print(f"\n[Video] Extracting {num_frames} frames from: {video_path}")
        
        os.makedirs(output_dir, exist_ok=True)
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps
        
        print(f"  Video info: {total_frames} frames, {fps:.1f} FPS, {duration:.1f}s")
        
        # Calculate frame indices to extract (evenly spaced)
        frame_indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)
        
        frame_paths = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            
            if ret:
                frame_path = os.path.join(output_dir, f"frame_{idx:05d}.jpg")
                cv2.imwrite(frame_path, frame)
                frame_paths.append(frame_path)
                print(f"  ✓ Saved frame {idx} -> {frame_path}")
        
        cap.release()
        print(f"✓ Extracted {len(frame_paths)} frames")
        
        return frame_paths
    
    def visualize_detection(
        self,
        image: Image.Image,
        result: DetectionResult,
        output_path: str,
        show_masks: bool = True,
        show_boxes: bool = True
    ):
        """
        Visualize detection results on image
        
        Args:
            image: Original PIL Image
            result: DetectionResult
            output_path: Path to save visualization
            show_masks: Whether to overlay segmentation masks
            show_boxes: Whether to draw bounding boxes
        """
        print(f"\n[Visualization] Saving to: {output_path}")
        
        # Convert to numpy for processing
        img_array = np.array(image)
        overlay = img_array.copy()
        
        # Color palette for different objects
        colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
        ]
        
        W, H = image.size
        
        for i in range(len(result.scores)):
            color = colors[i % len(colors)]
            score = result.scores[i]
            label = result.labels[i] if i < len(result.labels) else "object"
            
            # Draw segmentation mask
            if show_masks and i < len(result.masks):
                mask = result.masks[i]
                
                # Resize mask to image size if needed
                if mask.shape != (H, W):
                    mask_pil = Image.fromarray(mask.astype(np.float32))
                    mask_pil = mask_pil.resize((W, H), Image.Resampling.NEAREST)
                    mask = np.array(mask_pil)
                
                # Create binary mask
                binary_mask = mask > 0
                
                # Apply semi-transparent overlay
                overlay[binary_mask] = (
                    overlay[binary_mask] * 0.5 + 
                    np.array(color) * 0.5
                ).astype(np.uint8)
            
            # Draw bounding box
            if show_boxes and i < len(result.boxes):
                x1, y1, x2, y2 = result.boxes[i].astype(int)
                
                # Draw rectangle
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 3)
                
                # Draw label with score
                label_text = f"{label}: {score:.2f}"
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.6
                thickness = 2
                
                # Calculate text size
                (text_w, text_h), baseline = cv2.getTextSize(
                    label_text, font, font_scale, thickness
                )
                
                # Draw text background
                cv2.rectangle(
                    overlay,
                    (x1, y1 - text_h - 10),
                    (x1 + text_w, y1),
                    color,
                    -1
                )
                
                # Draw text
                cv2.putText(
                    overlay,
                    label_text,
                    (x1, y1 - 5),
                    font,
                    font_scale,
                    (255, 255, 255),
                    thickness
                )
        
        # Save result
        result_image = Image.fromarray(overlay)
        result_image.save(output_path)
        print(f"✓ Visualization saved")


def demo_image_detection(demo: SAM3Demo, image_path: str, output_dir: str):
    """Demo: Single object detection"""
    print("\n" + "="*60)
    print("DEMO 1: Single Object Detection")
    print("="*60)
    
    image = Image.open(image_path)
    print(f"Image size: {image.size}")
    
    # Detect person
    result = demo.detect_objects(image, "a person")
    
    # Visualize
    output_path = os.path.join(output_dir, "demo1_person_detection.jpg")
    demo.visualize_detection(image, result, output_path)
    
    return result


def demo_multi_object_detection(demo: SAM3Demo, image_path: str, output_dir: str):
    """Demo: Multiple object detection (sequential)"""
    print("\n" + "="*60)
    print("DEMO 2: Multi-Object Detection (Sequential)")
    print("="*60)
    
    image = Image.open(image_path)
    
    # Detect multiple objects sequentially (workaround for predict_multi bug)
    prompts = ["a person", "clothing", "background"]
    all_boxes = []
    all_masks = []
    all_scores = []
    all_labels = []
    
    for prompt in prompts:
        print(f"\n--- Detecting: {prompt} ---")
        result = demo.detect_objects(image, prompt)
        
        if len(result.boxes) > 0:
            all_boxes.extend(result.boxes)
            all_masks.extend(result.masks)
            all_scores.extend(result.scores)
            all_labels.extend([prompt] * len(result.boxes))
    
    # Combine results
    combined_result = DetectionResult(
        boxes=np.array(all_boxes) if all_boxes else np.array([]),
        masks=np.array(all_masks) if all_masks else np.array([]),
        scores=np.array(all_scores) if all_scores else np.array([]),
        labels=all_labels
    )
    
    print(f"\n✓ Total detections: {len(combined_result.scores)}")
    
    # Visualize
    output_path = os.path.join(output_dir, "demo2_multi_object_detection.jpg")
    demo.visualize_detection(image, combined_result, output_path)
    
    return combined_result


def demo_instance_segmentation(demo: SAM3Demo, image_path: str, output_dir: str):
    """Demo: Instance segmentation with mask extraction"""
    print("\n" + "="*60)
    print("DEMO 3: Instance Segmentation")
    print("="*60)
    
    image = Image.open(image_path)
    
    # Detect with segmentation
    result = demo.detect_objects(image, "a person")
    
    # Save individual masks
    mask_dir = os.path.join(output_dir, "masks")
    os.makedirs(mask_dir, exist_ok=True)
    
    for i, mask in enumerate(result.masks):
        mask_path = os.path.join(mask_dir, f"mask_{i:02d}.png")
        mask_image = Image.fromarray((mask * 255).astype(np.uint8))
        mask_image.save(mask_path)
        print(f"  ✓ Saved mask {i} -> {mask_path}")
    
    # Visualize with masks
    output_path = os.path.join(output_dir, "demo3_instance_segmentation.jpg")
    demo.visualize_detection(image, result, output_path, show_masks=True)
    
    return result


def demo_box_guided_detection(demo: SAM3Demo, image_path: str, output_dir: str):
    """Demo: Box-guided detection"""
    print("\n" + "="*60)
    print("DEMO 4: Box-Guided Detection")
    print("="*60)
    
    image = Image.open(image_path)
    W, H = image.size
    
    # Define a region of interest (center of image)
    cx, cy = W // 2, H // 2
    box_size = min(W, H) // 3
    boxes = np.array([[
        cx - box_size,
        cy - box_size,
        cx + box_size,
        cy + box_size
    ]])
    
    print(f"Image size: {W}x{H}")
    print(f"ROI box: {boxes[0]}")
    
    # Detect within the box
    result = demo.detect_with_box_guidance(
        image, 
        "an object", 
        boxes
    )
    
    # Visualize
    output_path = os.path.join(output_dir, "demo4_box_guided_detection.jpg")
    demo.visualize_detection(image, result, output_path)
    
    return result


def demo_video_processing(demo: SAM3Demo, video_path: str, output_dir: str):
    """Demo: Video frame processing"""
    print("\n" + "="*60)
    print("DEMO 5: Video Frame Processing")
    print("="*60)
    
    # Extract frames
    frames_dir = os.path.join(output_dir, "video_frames")
    frame_paths = demo.extract_video_frames(
        video_path, 
        frames_dir, 
        num_frames=3
    )
    
    # Process each frame
    results = []
    for i, frame_path in enumerate(frame_paths):
        print(f"\n--- Processing frame {i+1}/{len(frame_paths)} ---")
        
        image = Image.open(frame_path)
        result = demo.detect_objects(image, "a person")
        
        # Visualize
        output_path = os.path.join(
            output_dir, 
            f"demo5_video_frame_{i:02d}.jpg"
        )
        demo.visualize_detection(image, result, output_path)
        
        results.append(result)
    
    return results


def print_performance_summary(results: Dict[str, float]):
    """Print performance summary"""
    print("\n" + "="*60)
    print("PERFORMANCE SUMMARY")
    print("="*60)
    
    for name, duration in results.items():
        print(f"{name:40s}: {duration:.2f}s")
    
    total = sum(results.values())
    print(f"{'Total':40s}: {total:.2f}s")


def main():
    """Main demo execution"""
    print("="*60)
    print("SAM 3.1 MLX Demo")
    print("="*60)
    
    # Configuration
    MODEL_PATH = "/Users/lwz/.cache/modelscope/hub/models/mlx-community/sam3___1-bf16"
    VIDEO_PATH = "/Users/lwz/DaVinci Resolve Media/Video/Women/374dea25-caa4-4b51-801e-1a890370a358.mp4"
    OUTPUT_DIR = "/Users/lwz/Liwz/Code/VATools/backend/workspace/sam_demo_output"
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")
    
    # Initialize model
    performance = {}
    start_time = time.time()
    demo = SAM3Demo(MODEL_PATH, score_threshold=0.3)
    performance["Model Loading"] = time.time() - start_time
    
    # Extract first frame from video for image demos
    print("\nExtracting first frame from video for image demos...")
    cap = cv2.VideoCapture(VIDEO_PATH)
    ret, first_frame = cap.read()
    cap.release()
    
    if not ret:
        print("ERROR: Cannot read video")
        return
    
    first_frame_path = os.path.join(OUTPUT_DIR, "first_frame.jpg")
    cv2.imwrite(first_frame_path, first_frame)
    print(f"✓ First frame saved: {first_frame_path}")
    
    # Run demos
    try:
        # Demo 1: Single object detection
        start_time = time.time()
        demo_image_detection(demo, first_frame_path, OUTPUT_DIR)
        performance["Demo 1: Single Detection"] = time.time() - start_time
        
        # Demo 2: Multi-object detection
        start_time = time.time()
        demo_multi_object_detection(demo, first_frame_path, OUTPUT_DIR)
        performance["Demo 2: Multi-Detection"] = time.time() - start_time
        
        # Demo 3: Instance segmentation
        start_time = time.time()
        demo_instance_segmentation(demo, first_frame_path, OUTPUT_DIR)
        performance["Demo 3: Segmentation"] = time.time() - start_time
        
        # Demo 4: Box-guided detection
        start_time = time.time()
        demo_box_guided_detection(demo, first_frame_path, OUTPUT_DIR)
        performance["Demo 4: Box-Guided"] = time.time() - start_time
        
        # Demo 5: Video processing
        start_time = time.time()
        demo_video_processing(demo, VIDEO_PATH, OUTPUT_DIR)
        performance["Demo 5: Video Processing"] = time.time() - start_time
        
    except Exception as e:
        print(f"\nERROR during demo execution: {e}")
        import traceback
        traceback.print_exc()
    
    # Print performance summary
    print_performance_summary(performance)
    
    print("\n" + "="*60)
    print("Demo completed!")
    print(f"Results saved to: {OUTPUT_DIR}")
    print("="*60)


if __name__ == "__main__":
    main()
