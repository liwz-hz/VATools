"""
Image Processing Routes
Handles image upload, segmentation, and extraction operations
"""
import os
import io
import base64
import traceback
from flask import Blueprint, request, jsonify, send_file
from PIL import Image
from loguru import logger

from app.services.sam_service import sam_service
from app.config import Config

bp = Blueprint('image', __name__, url_prefix='/api/image')


@bp.route('/status', methods=['GET'])
def get_status():
    """Get SAM model status"""
    try:
        is_loaded = sam_service.is_loaded()
        model_exists = os.path.exists(sam_service.model_path)
        
        return jsonify({
            'available': is_loaded or model_exists,
            'loaded': is_loaded,
            'model_path': sam_service.model_path,
            'score_threshold': sam_service.score_threshold
        })
    except Exception as e:
        logger.error(f"[SAM] Status check failed: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'available': False, 'error': str(e)}), 500


@bp.route('/load', methods=['POST'])
def load_model():
    """Load SAM model"""
    try:
        success = sam_service.load_model()
        if success:
            return jsonify({'status': 'loaded', 'message': 'Model loaded successfully'})
        else:
            return jsonify({'status': 'failed', 'message': 'Failed to load model'}), 500
    except Exception as e:
        logger.error(f"[SAM] Model loading failed: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/detect', methods=['POST'])
def detect_objects():
    """
    Detect objects in uploaded image
    
    Request:
        - image: Image file (multipart/form-data)
        - prompt: Text prompt for detection (form field)
        
    Response:
        - boxes: List of [x1, y1, x2, y2]
        - masks: List of binary masks (base64 encoded PNG)
        - scores: List of confidence scores
        - labels: List of labels
        - visualization: Visualization image (base64 encoded)
    """
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        image_file = request.files['image']
        prompt = request.form.get('prompt', 'a person')
        
        # Load image
        image = Image.open(image_file).convert('RGB')
        
        # Detect objects
        detection = sam_service.detect_objects(image, prompt)
        
        if detection is None:
            return jsonify({'error': 'Detection failed'}), 500
        
        # Encode masks as base64 PNG
        import numpy as np
        masks_b64 = []
        for mask in detection['masks']:
            mask_array = np.array(mask)
            mask_image = Image.fromarray((mask_array * 255).astype(np.uint8))
            buffer = io.BytesIO()
            mask_image.save(buffer, format='PNG')
            masks_b64.append(base64.b64encode(buffer.getvalue()).decode())
        
        # Create visualization
        viz_image = sam_service.create_visualization(image, detection)
        viz_buffer = io.BytesIO()
        viz_image.save(viz_buffer, format='JPEG', quality=85)
        viz_b64 = base64.b64encode(viz_buffer.getvalue()).decode()
        
        return jsonify({
            'boxes': detection['boxes'],
            'masks': masks_b64,
            'scores': detection['scores'],
            'labels': detection['labels'],
            'visualization': viz_b64,
            'num_objects': len(detection['scores'])
        })
        
    except Exception as e:
        logger.error(f"[SAM] Detection failed: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@bp.route('/extract', methods=['POST'])
def extract_object():
    """
    Extract object from image using mask
    
    Request:
        - image: Image file (multipart/form-data)
        - mask: Binary mask (base64 encoded PNG)
        - box: Optional bounding box [x1, y1, x2, y2] (JSON string)
        
    Response:
        - Extracted object as PNG file
    """
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        if 'mask' not in request.form:
            return jsonify({'error': 'No mask provided'}), 400
        
        image_file = request.files['image']
        mask_b64 = request.form['mask']
        box_str = request.form.get('box')
        
        # Load image
        image = Image.open(image_file).convert('RGB')
        
        # Decode mask
        import numpy as np
        mask_data = base64.b64decode(mask_b64)
        mask_image = Image.open(io.BytesIO(mask_data))
        mask = np.array(mask_image).astype(float) / 255.0
        
        # Parse box if provided
        box = None
        if box_str:
            import json
            box = json.loads(box_str)
        
        # Extract object
        extracted = sam_service.extract_object(image, mask, box)
        
        if extracted is None:
            return jsonify({'error': 'Extraction failed'}), 500
        
        # Return as PNG
        buffer = io.BytesIO()
        extracted.save(buffer, format='PNG')
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='image/png',
            as_attachment=True,
            download_name='extracted_object.png'
        )
        
    except Exception as e:
        logger.error(f"[SAM] Extraction failed: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@bp.route('/remove-background', methods=['POST'])
def remove_background():
    """
    Remove background from image
    
    Request:
        - image: Image file (multipart/form-data)
        - prompt: What to keep (default: "a person")
        
    Response:
        - Image with background removed (PNG with transparency)
    """
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        image_file = request.files['image']
        prompt = request.form.get('prompt', 'a person')
        
        # Load image
        image = Image.open(image_file).convert('RGB')
        
        # Remove background
        result = sam_service.remove_background(image, prompt)
        
        if result is None:
            return jsonify({'error': 'Background removal failed'}), 500
        
        # Return as PNG
        buffer = io.BytesIO()
        result.save(buffer, format='PNG')
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='image/png',
            as_attachment=True,
            download_name='no_background.png'
        )
        
    except Exception as e:
        logger.error(f"[SAM] Background removal failed: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
