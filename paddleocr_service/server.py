"""
PaddleOCR REST API Service
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

app = Flask(__name__)

# Global OCR pipeline (lazy loaded)
_ocr_pipeline = None
_temp_dir = None

# Poppler path for pdf2image (Windows)
POPPLER_PATH = os.environ.get("POPPLER_PATH", r"C:\poppler-24.08.0\Library\bin")

# PDF conversion DPI (lower = faster, but less accurate)
PDF_DPI = int(os.environ.get("PDF_DPI", "150"))  # Reduced from 200

# Max image dimension (resize large images for speed)
MAX_IMAGE_DIM = int(os.environ.get("MAX_IMAGE_DIM", "1500"))


def get_temp_dir():
    """Get or create a dedicated temp directory for OCR."""
    global _temp_dir
    if _temp_dir is None:
        _temp_dir = tempfile.mkdtemp(prefix="paddleocr_service_")
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


def get_ocr_pipeline():
    """Lazy-load the PaddleOCR pipeline."""
    global _ocr_pipeline
    if _ocr_pipeline is None:
        print("Loading PaddleOCR pipeline (first request may be slow)...")
        try:
            from paddlex import create_pipeline
            _ocr_pipeline = create_pipeline(pipeline="OCR")
            print("PaddleOCR pipeline loaded successfully!")
        except Exception as e:
            print(f"Failed to load PaddleOCR: {e}")
            raise
    return _ocr_pipeline


def extract_text_from_result(result) -> str:
    """Extract text from PaddleOCR result."""
    texts = []
    try:
        for item in result:
            if hasattr(item, 'rec_texts') and item.rec_texts:
                texts.extend(item.rec_texts)
            elif isinstance(item, dict) and 'rec_texts' in item:
                texts.extend(item['rec_texts'])
    except Exception as e:
        print(f"Error extracting text: {e}")
    return "\n".join(texts)


def resize_image_if_needed(image: Image.Image) -> Image.Image:
    """Resize image if too large (speeds up OCR significantly)."""
    w, h = image.size
    if max(w, h) > MAX_IMAGE_DIM:
        ratio = MAX_IMAGE_DIM / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        print(f"[RESIZE] {w}x{h} -> {new_size[0]}x{new_size[1]}")
        return image.resize(new_size, Image.Resampling.LANCZOS)
    return image


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "paddleocr",
        "pipeline_loaded": _ocr_pipeline is not None
    })


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
        print(f"[OCR] Original size: {image.size}")
        
        # Resize if too large
        image = resize_image_if_needed(image)
        
        # Save to temp file (PaddleOCR requires file path)
        temp_dir = get_temp_dir()
        temp_path = os.path.join(temp_dir, f"ocr_{int(time.time() * 1000)}.png")
        image.save(temp_path)
        print(f"[OCR] Saved to temp: {temp_path}")
        
        try:
            # Run OCR
            pipeline = get_ocr_pipeline()
            print(f"[OCR] Running OCR...")
            result = list(pipeline.predict(temp_path))
            text = extract_text_from_result(result)
            print(f"[OCR] Extracted {len(text)} chars")
            
            return jsonify({
                "success": True,
                "text": text,
                "pages": 1,
                "processing_time": round(time.time() - start_time, 2)
            })
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass
                
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
        
        # Convert all pages to images (reduced DPI for speed)
        print(f"[PDF OCR] Converting PDF to images (DPI={PDF_DPI}, poppler: {POPPLER_PATH})...")
        images = convert_from_bytes(pdf_bytes, dpi=PDF_DPI, poppler_path=POPPLER_PATH)
        print(f"[PDF OCR] Converted {len(images)} pages")
        
        all_text = []
        temp_dir = get_temp_dir()
        pipeline = get_ocr_pipeline()
        
        for i, image in enumerate(images):
            print(f"[PDF OCR] Processing page {i + 1}/{len(images)}...")
            
            # Resize if too large
            image = resize_image_if_needed(image)
            
            temp_path = os.path.join(temp_dir, f"pdf_page_{i}_{int(time.time() * 1000)}.png")
            image.save(temp_path)
            
            try:
                result = list(pipeline.predict(temp_path))
                page_text = extract_text_from_result(result)
                all_text.append(f"--- Page {i + 1} ---\n{page_text}")
                print(f"[PDF OCR] Page {i + 1}: {len(page_text)} chars")
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass
        
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
        
        # Convert first page only (reduced DPI for speed)
        print(f"[PDF FIRST] Converting first page (DPI={PDF_DPI}, poppler: {POPPLER_PATH})...")
        images = convert_from_bytes(pdf_bytes, dpi=PDF_DPI, first_page=1, last_page=1, poppler_path=POPPLER_PATH)
        print(f"[PDF FIRST] Got {len(images)} image(s)")
        
        if not images:
            return jsonify({"success": False, "error": "Could not extract first page"}), 500
        
        # Resize if too large
        image = resize_image_if_needed(images[0])
        
        temp_dir = get_temp_dir()
        temp_path = os.path.join(temp_dir, f"pdf_first_{int(time.time() * 1000)}.png")
        image.save(temp_path)
        print(f"[PDF FIRST] Image size: {image.size}, saved to: {temp_path}")
        
        try:
            pipeline = get_ocr_pipeline()
            print(f"[PDF FIRST] Running OCR...")
            result = list(pipeline.predict(temp_path))
            text = extract_text_from_result(result)
            print(f"[PDF FIRST] Extracted {len(text)} chars")
            
            return jsonify({
                "success": True,
                "text": text,
                "pages": 1,
                "processing_time": round(time.time() - start_time, 2)
            })
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
        
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
    print("PaddleOCR Service")
    print("=" * 50)
    print("Starting on http://localhost:8765")
    print("Endpoints:")
    print("  GET  /health           - Health check")
    print("  POST /ocr              - OCR image")
    print("  POST /ocr/pdf          - OCR full PDF")
    print("  POST /ocr/pdf/first-page - OCR first page of PDF")
    print("=" * 50)
    
    # Pre-load the pipeline on startup
    try:
        get_ocr_pipeline()
    except Exception as e:
        print(f"Warning: Could not pre-load pipeline: {e}")
    
    app.run(host='0.0.0.0', port=8765, debug=False, threaded=True)
