# VATools Development Standards

## Logging & Debuggability

All backend services and routes MUST follow these logging standards:

### 1. Error Logging
- Every `except` block MUST use `logger.error()` with the exception message
- MUST include `traceback.format_exc()` for unexpected errors
- Example:
```python
except Exception as e:
    logger.error(f"[ModuleName] operation failed: {e}")
    logger.error(traceback.format_exc())
    return jsonify({'error': str(e)}), 500
```

### 2. Request Logging
- Log incoming requests with key parameters at DEBUG level
- Log request completion with status code and duration
- Example:
```python
logger.debug(f"[BiRefNet] segment request: model_type={model_type}, image_size={image.size}")
```

### 3. Service-Level Logging
- Model loading: log model path, load time, device type
- Inference: log input dimensions, output dimensions, inference time
- File operations: log file paths, sizes, formats

### 4. Frontend Error Handling
- Always display backend error messages to users (not generic "处理失败")
- Log full error response to console for debugging
- Example:
```typescript
catch (err: any) {
  console.error('BiRefNet error:', err.response?.data)
  setError(err.response?.data?.error || '处理失败')
}
```

### 5. Configuration Logging
- Log model paths and availability on service startup
- Log device type (MPS/CPU) on model load

## Code Quality

- No hardcoded paths in route files - use Config class
- All API endpoints must return structured JSON errors
- Frontend must handle all error states gracefully
