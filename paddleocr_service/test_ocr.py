"""
Test script to verify PaddleOCR is working correctly.
Run this before starting the server.
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFont

def create_test_image():
    """Create a simple test image with text."""
    img = Image.new('RGB', (400, 200), color='white')
    draw = ImageDraw.Draw(img)
    
    # Use default font
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    draw.text((50, 50), "Test OCR Image", fill='black', font=font)
    draw.text((50, 100), "PaddleOCR Service", fill='black', font=font)
    
    test_path = "test_image.png"
    img.save(test_path)
    return test_path


def test_paddleocr():
    """Test PaddleOCR installation."""
    print("=" * 50)
    print("Testing PaddleOCR Installation")
    print("=" * 50)
    
    # Step 1: Create test image
    print("\n1. Creating test image...")
    test_path = create_test_image()
    print(f"   Created: {test_path}")
    
    # Step 2: Load PaddleOCR
    print("\n2. Loading PaddleOCR pipeline...")
    try:
        from paddlex import create_pipeline
        pipeline = create_pipeline(pipeline="OCR")
        print("   ✓ Pipeline loaded successfully!")
    except Exception as e:
        print(f"   ✗ Failed to load pipeline: {e}")
        sys.exit(1)
    
    # Step 3: Run OCR
    print("\n3. Running OCR on test image...")
    try:
        result = list(pipeline.predict(test_path))
        
        texts = []
        for item in result:
            if hasattr(item, 'rec_texts') and item.rec_texts:
                texts.extend(item.rec_texts)
        
        print(f"   ✓ OCR completed!")
        print(f"   Extracted text: {' | '.join(texts)}")
    except Exception as e:
        print(f"   ✗ OCR failed: {e}")
        sys.exit(1)
    
    # Step 4: Cleanup
    print("\n4. Cleaning up...")
    try:
        os.unlink(test_path)
        print(f"   ✓ Removed test image")
    except:
        pass
    
    print("\n" + "=" * 50)
    print("✓ All tests passed! PaddleOCR is ready.")
    print("  Run 'python server.py' to start the service.")
    print("=" * 50)


if __name__ == '__main__':
    test_paddleocr()
