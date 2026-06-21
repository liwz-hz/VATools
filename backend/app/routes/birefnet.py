"""
BiRefNet API Routes - Image segmentation and matting endpoints
"""
from flask import Blueprint, request, jsonify, send_file
from PIL import Image
import io
import base64
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
        - model_type: "general" or "hr_matting" (default: "general")
        
    Response:
        - mask: Base64 encoded PNG mask
    """
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        image_file = request.files['image']
        model_type = request.form.get('model_type', 'general')
        
        # Load image
        image = Image.open(image_file).convert('RGB')
        
        # Segment
        mask = birefnet_service.segment_image(image, model_type)
        
        if mask is None:
            return jsonify({'error': 'Segmentation failed'}), 500
        
        # Convert to base64
        buffer = io.BytesIO()
        mask.save(buffer, format='PNG')
        buffer.seek(0)
        mask_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return jsonify({
            'success': True,
            'mask': mask_base64,
            'format': 'png'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@birefnet_bp.route('/remove-background', methods=['POST'])
def remove_background():
    """
    Remove background from image
    
    Request:
        - image: Image file (multipart/form-data)
        - model_type: "general" or "hr_matting" (default: "general")
        
    Response:
        - PNG file with transparent background
    """
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        image_file = request.files['image']
        model_type = request.form.get('model_type', 'general')
        
        # Load image
        image = Image.open(image_file).convert('RGB')
        
        # Remove background
        result = birefnet_service.remove_background(image, model_type)
        
        if result is None:
            return jsonify({'error': 'Background removal failed'}), 500
        
        # Return as PNG
        buffer = io.BytesIO()
        result.save(buffer, format='PNG')
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='image/png',
            as_attachment=False,
            download_name='result.png'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@birefnet_bp.route('/load-model', methods=['POST'])
def load_model():
    """
    Preload a BiRefNet model
    
    Request:
        - model_type: "general" or "hr_matting"
        
    Response:
        - success status
    """
    try:
        data = request.get_json()
        model_type = data.get('model_type', 'general')
        
        success = birefnet_service.load_model(model_type)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Model {model_type} loaded successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to load model {model_type}'
            }), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
