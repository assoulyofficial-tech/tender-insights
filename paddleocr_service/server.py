"""
Tesseract OCR REST API Service
Runs as a standalone service on port 8765
"""

import os
import io
import time
import tempfile
import atexit
import shutil
from flask import Flask, request, jsonify
from PIL import Image
import pytesseract

app = Flask(__name__)

# Global temp directory
_temp_dir = None

# Tesseract path (Windows)
TESSERACT_PATH = os.environ.get("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# Poppler path for pdf2image (Windows)
POPPLER_PATH = os.environ.get("POPPLER_PATH", r"C:\poppler-24.08.0\Library\bin")

# PDF conversion DPI - keep high for quality
PDF_DPI = int(os.environ.get("PDF_DPI", "200"))

# Tesseract config for best accuracy
# Use French + Arabic + English
TESSERACT_LANG = os.environ.get("TESSERACT_LANG", "fra+ara+eng")
TESSERACT_CONFIG = "--oem 3 --psm 3"


def get_temp_dir():
    """Get or create a dedicated temp directory for OCR."""
    global _temp_dir
    if _temp_dir is None:
        _temp_dir = tempfile.mkdtemp(prefix="tesseract_service_")
        atexit.register(cleanup_temp_dir)
    return _temp_dir


def cleanup_temp_dir():
    """Clean up temp directory on exit."""
    global _temp_dir
    if _temp_dir and os.path.exists(_temp_dir):
        try:
            shutil.rmtree(_temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"Warning: Could not clean temp dir: {e}")


def ocr_image_tesseract(image: Image.Image) -> str:
    """Run Tesseract OCR on an image."""
    try:
        text = pytesseract.image_to_string(
            image, 
            lang=TESSERACT_LANG,
            config=TESSERACT_CONFIG
        )
        return text.strip()
    except Exception as e:
        print(f"[OCR ERROR] Tesseract failed: {e}")
        raise


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    # Test tesseract is working
    try:
        version = pytesseract.get_tesseract_version()
        return jsonify({
            "status": "ok",
            "service": "tesseract",
            "version": str(version),
            "languages": TESSERACT_LANG
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "service": "tesseract",
            "error": str(e)
        }), 500


@app.route('/ocr', methods=['POST'])
def ocr_image():
    """OCR a single image."""
    start_time = time.time()
    
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "Empty filename"}), 400
    
    try:
        # Read image
        image_bytes = file.read()
        print(f"[OCR] Received image: {len(image_bytes)} bytes")
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        print(f"[OCR] Image size: {image.size}")
        
        # Run OCR
        print(f"[OCR] Running Tesseract...")
        text = ocr_image_tesseract(image)
        print(f"[OCR] Extracted {len(text)} chars")
        
        return jsonify({
            "success": True,
            "text": text,
            "pages": 1,
            "processing_time": round(time.time() - start_time, 2)
        })
                
    except Exception as e:
        import traceback
        print(f"[OCR ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"{type(e).__name__}: {str(e)}"
        }), 500


@app.route('/ocr/pdf', methods=['POST'])
def ocr_pdf():
    """OCR all pages of a PDF."""
    start_time = time.time()
    
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "Empty filename"}), 400
    
    try:
        from pdf2image import convert_from_bytes
        
        # Read PDF
        pdf_bytes = file.read()
        print(f"[PDF OCR] Received PDF: {len(pdf_bytes)} bytes")
        
        # Convert all pages to images
        print(f"[PDF OCR] Converting PDF to images (DPI={PDF_DPI}, poppler: {POPPLER_PATH})...")
        images = convert_from_bytes(pdf_bytes, dpi=PDF_DPI, poppler_path=POPPLER_PATH)
        print(f"[PDF OCR] Converted {len(images)} pages")
        
        all_text = []
        
        for i, image in enumerate(images):
            print(f"[PDF OCR] Processing page {i + 1}/{len(images)}, size: {image.size}...")
            page_text = ocr_image_tesseract(image)
            all_text.append(f"--- Page {i + 1} ---\n{page_text}")
            print(f"[PDF OCR] Page {i + 1}: {len(page_text)} chars")
        
        return jsonify({
            "success": True,
            "text": "\n\n".join(all_text),
            "pages": len(images),
            "processing_time": round(time.time() - start_time, 2)
        })
        
    except Exception as e:
        import traceback
        print(f"[PDF OCR ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"{type(e).__name__}: {str(e)}"
        }), 500


@app.route('/ocr/pdf/first-page', methods=['POST'])
def ocr_pdf_first_page():
    """OCR only the first page of a PDF."""
    start_time = time.time()
    
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "Empty filename"}), 400
    
    try:
        from pdf2image import convert_from_bytes
        
        # Read PDF
        pdf_bytes = file.read()
        print(f"[PDF FIRST] Received PDF: {len(pdf_bytes)} bytes")
        
        # Convert first page only
        print(f"[PDF FIRST] Converting first page (DPI={PDF_DPI}, poppler: {POPPLER_PATH})...")
        images = convert_from_bytes(pdf_bytes, dpi=PDF_DPI, first_page=1, last_page=1, poppler_path=POPPLER_PATH)
        print(f"[PDF FIRST] Got {len(images)} image(s)")
        
        if not images:
            return jsonify({"success": False, "error": "Could not extract first page"}), 500
        
        image = images[0]
        print(f"[PDF FIRST] Image size: {image.size}")
        
        print(f"[PDF FIRST] Running Tesseract OCR...")
        text = ocr_image_tesseract(image)
        print(f"[PDF FIRST] Extracted {len(text)} chars")
        
        return jsonify({
            "success": True,
            "text": text,
            "pages": 1,
            "processing_time": round(time.time() - start_time, 2)
        })
        
    except Exception as e:
        import traceback
        print(f"[PDF FIRST ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"{type(e).__name__}: {str(e)}"
        }), 500


if __name__ == '__main__':
    print("=" * 50)
    print("Tesseract OCR Service")
    print("=" * 50)
    print(f"Tesseract path: {TESSERACT_PATH}")
    print(f"Poppler path: {POPPLER_PATH}")
    print(f"Languages: {TESSERACT_LANG}")
    print("Starting on http://localhost:8765")
    print("Endpoints:")
    print("  GET  /health           - Health check")
    print("  POST /ocr              - OCR image")
    print("  POST /ocr/pdf          - OCR full PDF")
    print("  POST /ocr/pdf/first-page - OCR first page of PDF")
    print("=" * 50)
    
    # Test tesseract on startup
    try:
        version = pytesseract.get_tesseract_version()
        print(f"Tesseract version: {version}")
    except Exception as e:
        print(f"Warning: Could not verify Tesseract: {e}")
    
    app.run(host='0.0.0.0', port=8765, debug=False, threaded=True)
