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
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # Save to temp file (PaddleOCR requires file path)
        temp_dir = get_temp_dir()
        temp_path = os.path.join(temp_dir, f"ocr_{int(time.time() * 1000)}.png")
        image.save(temp_path)
        
        try:
            # Run OCR
            pipeline = get_ocr_pipeline()
            result = list(pipeline.predict(temp_path))
            text = extract_text_from_result(result)
            
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
        return jsonify({
            "success": False,
            "error": str(e)
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
        
        # Convert all pages to images
        images = convert_from_bytes(pdf_bytes, dpi=200)
        
        all_text = []
        temp_dir = get_temp_dir()
        pipeline = get_ocr_pipeline()
        
        for i, image in enumerate(images):
            temp_path = os.path.join(temp_dir, f"pdf_page_{i}_{int(time.time() * 1000)}.png")
            image.save(temp_path)
            
            try:
                result = list(pipeline.predict(temp_path))
                page_text = extract_text_from_result(result)
                all_text.append(f"--- Page {i + 1} ---\n{page_text}")
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
        return jsonify({
            "success": False,
            "error": str(e)
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
        
        # Convert first page only
        images = convert_from_bytes(pdf_bytes, dpi=200, first_page=1, last_page=1)
        
        if not images:
            return jsonify({"success": False, "error": "Could not extract first page"}), 500
        
        temp_dir = get_temp_dir()
        temp_path = os.path.join(temp_dir, f"pdf_first_{int(time.time() * 1000)}.png")
        images[0].save(temp_path)
        
        try:
            pipeline = get_ocr_pipeline()
            result = list(pipeline.predict(temp_path))
            text = extract_text_from_result(result)
            
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
        return jsonify({
            "success": False,
            "error": str(e)
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
