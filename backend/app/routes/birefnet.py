"""
BiRefNet API Routes - Image segmentation and matting endpoints
"""
from flask import Blueprint, request, jsonify, send_file
from PIL import Image
import io
import base64
import time
import traceback
from loguru import logger
from app.services.birefnet_service import birefnet_service

birefnet_bp = Blueprint('birefnet', __name__, url_prefix='/api/birefnet')


@birefnet_bp.route('/models', methods=['GET'])
def get_models():
    """Get available BiRefNet models"""
    try:
        models = birefnet_service.get_available_models()
        return jsonify({
            'success': True,
            'models': models
        })
    except Exception as e:
        logger.error(f"[BiRefNet] get_models failed: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@birefnet_bp.route('/segment', methods=['POST'])
def segment_image():
    """
    Segment image and return mask
    
    Request:
        - image: Image file (multipart/form-data)
        - model_type: "dynamic", "general" or "hr_matting" (default: "dynamic")
        
    Response:
        - mask: Base64 encoded PNG mask
    """
    start_time = time.time()
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        image_file = request.files['image']
        model_type = request.form.get('model_type', 'dynamic')
        
        image = Image.open(image_file).convert('RGB')
        logger.debug(f"[BiRefNet] segment request: model={model_type}, image={image.size}, file={image_file.filename}")
        
        mask = birefnet_service.segment_image(image, model_type)
        
        if mask is None:
            logger.error("[BiRefNet] segment returned None mask")
            return jsonify({'error': 'Segmentation failed - check backend logs'}), 500
        
        buffer = io.BytesIO()
        mask.save(buffer, format='PNG')
        buffer.seek(0)
        mask_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        duration = time.time() - start_time
        logger.info(f"[BiRefNet] segment completed: {duration:.2f}s, mask_size={mask.size}")
        
        return jsonify({
            'success': True,
            'mask': mask_base64,
            'format': 'png'
        })
        
    except Exception as e:
        logger.error(f"[BiRefNet] segment error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@birefnet_bp.route('/remove-background', methods=['POST'])
def remove_background():
    """
    Remove background from image
    
    Request:
        - image: Image file (multipart/form-data)
        - model_type: "dynamic", "general" or "hr_matting" (default: "dynamic")
        
    Response:
        - PNG file with transparent background
    """
    start_time = time.time()
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        image_file = request.files['image']
        model_type = request.form.get('model_type', 'dynamic')
        
        image = Image.open(image_file).convert('RGB')
        logger.debug(f"[BiRefNet] remove-background request: model={model_type}, image={image.size}, file={image_file.filename}")
        
        result = birefnet_service.remove_background(image, model_type)
        
        if result is None:
            logger.error("[BiRefNet] remove_background returned None")
            return jsonify({'error': 'Background removal failed - check backend logs'}), 500
        
        buffer = io.BytesIO()
        result.save(buffer, format='PNG')
        buffer.seek(0)
        
        duration = time.time() - start_time
        logger.info(f"[BiRefNet] remove-background completed: {duration:.2f}s, output={result.size}")
        
        return send_file(
            buffer,
            mimetype='image/png',
            as_attachment=False,
            download_name='result.png'
        )
        
    except Exception as e:
        logger.error(f"[BiRefNet] remove-background error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@birefnet_bp.route('/load-model', methods=['POST'])
def load_model():
    """
    Preload a BiRefNet model
    
    Request:
        - model_type: "dynamic", "general" or "hr_matting"
        
    Response:
        - success status
    """
    start_time = time.time()
    try:
        data = request.get_json()
        model_type = data.get('model_type', 'dynamic')
        logger.debug(f"[BiRefNet] load-model request: model={model_type}")
        
        success = birefnet_service.load_model(model_type)
        
        duration = time.time() - start_time
        if success:
            logger.info(f"[BiRefNet] load-model completed: {duration:.2f}s, model={model_type}")
            return jsonify({
                'success': True,
                'message': f'Model {model_type} loaded successfully'
            })
        else:
            logger.error(f"[BiRefNet] load-model failed: model={model_type}")
            return jsonify({
                'success': False,
                'error': f'Failed to load model {model_type}'
            }), 500
            
    except Exception as e:
        logger.error(f"[BiRefNet] load-model error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
