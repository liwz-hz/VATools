#!/usr/bin/env python3
"""
BiRefNet Test Script - Verify MPS support and capabilities
"""
import torch
import numpy as np
from PIL import Image
from transformers import AutoModelForImageSegmentation
from torchvision import transforms
import time

# Check MPS availability
print("=" * 60)
print("BiRefNet MPS Test")
print("=" * 60)

if torch.backends.mps.is_available():
    device = torch.device("mps")
    print("✓ MPS is available")
else:
    device = torch.device("cpu")
    print("✗ MPS not available, using CPU")

print(f"Using device: {device}")
print()

# Test 1: Load BiRefNet general model
print("Test 1: Loading BiRefNet (general use)...")
model_path = "/Users/lwz/.cache/modelscope/hub/models/birefnet/BiRefNet"
try:
    start = time.time()
    birefnet = AutoModelForImageSegmentation.from_pretrained(
        model_path,
        trust_remote_code=True
    )
    birefnet.to(device)
    # Convert to float32 for MPS compatibility
    if device.type == "mps":
        birefnet = birefnet.float()
    birefnet.eval()
    load_time = time.time() - start
    print(f"✓ Model loaded in {load_time:.2f}s")
except Exception as e:
    print(f"✗ Failed to load model: {e}")
    exit(1)

# Test 2: Inference on a test image
print("\nTest 2: Running inference...")
# Create a simple test image (gradient)
test_img = Image.new('RGB', (512, 512), color='white')
pixels = test_img.load()
for i in range(512):
    for j in range(512):
        pixels[i, j] = (i % 256, j % 256, (i + j) % 256)

# Preprocessing
transform_image = transforms.Compose([
    transforms.Resize((1024, 1024)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

input_tensor = transform_image(test_img).unsqueeze(0).to(device)

try:
    start = time.time()
    with torch.no_grad():
        preds = birefnet(input_tensor)[-1].sigmoid().cpu()
    infer_time = time.time() - start
    print(f"✓ Inference completed in {infer_time:.2f}s")
    print(f"  Output shape: {preds.shape}")
    print(f"  Output range: [{preds.min():.3f}, {preds.max():.3f}]")
except Exception as e:
    print(f"✗ Inference failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 3: Generate mask
print("\nTest 3: Generating segmentation mask...")
try:
    pred = preds[0].squeeze()
    pred_pil = transforms.ToPILImage()(pred)
    pred_pil = pred_pil.resize(test_img.size)
    
    # Save mask
    output_path = "/Users/lwz/Liwz/Code/VATools/backend/workspace/birefnet_test_mask.png"
    pred_pil.save(output_path)
    print(f"✓ Mask saved to: {output_path}")
except Exception as e:
    print(f"✗ Mask generation failed: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Load BiRefNet_HR-matting model
print("\nTest 4: Loading BiRefNet_HR-matting...")
model_path_hr = "/Users/lwz/.cache/modelscope/hub/models/birefnet/BiRefNet_HR-matting"
try:
    start = time.time()
    birefnet_hr = AutoModelForImageSegmentation.from_pretrained(
        model_path_hr,
        trust_remote_code=True
    )
    birefnet_hr.to(device)
    # Convert to float32 for MPS compatibility
    if device.type == "mps":
        birefnet_hr = birefnet_hr.float()
    birefnet_hr.eval()
    load_time_hr = time.time() - start
    print(f"✓ HR-matting model loaded in {load_time_hr:.2f}s")
    
    # Test inference with HR model
    print("  Running HR-matting inference...")
    start = time.time()
    with torch.no_grad():
        preds_hr = birefnet_hr(input_tensor)[-1].sigmoid().cpu()
    infer_time_hr = time.time() - start
    print(f"  ✓ HR-matting inference in {infer_time_hr:.2f}s")
    print(f"    Output shape: {preds_hr.shape}")
except Exception as e:
    print(f"✗ HR-matting model failed: {e}")

print("\n" + "=" * 60)
print("All tests completed!")
print("=" * 60)
