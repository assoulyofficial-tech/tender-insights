# PaddleOCR Service

Standalone PaddleOCR REST API service that runs independently from the main backend.

## Setup

### 1. Create a virtual environment (separate from main project)

```bash
cd paddleocr_service
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Test PaddleOCR installation

```bash
python test_ocr.py
```

This will process a test image and confirm PaddleOCR is working.

### 4. Run the service

```bash
python server.py
```

The service will start on `http://localhost:8765`

## API Endpoints

### Health Check
```
GET /health
```

### OCR Image
```
POST /ocr
Content-Type: multipart/form-data

file: <image file>
lang: "fr" (optional, default: "fr")
```

### OCR PDF (all pages)
```
POST /ocr/pdf
Content-Type: multipart/form-data

file: <pdf file>
lang: "fr" (optional, default: "fr")
```

### OCR PDF First Page Only
```
POST /ocr/pdf/first-page
Content-Type: multipart/form-data

file: <pdf file>
lang: "fr" (optional, default: "fr")
```

## Response Format

```json
{
  "success": true,
  "text": "Extracted text...",
  "pages": 1,
  "processing_time": 1.23
}
```

## Notes

- Keep this service running alongside the main backend
- The service manages its own temp files internally
- All dependencies are isolated from the main project
