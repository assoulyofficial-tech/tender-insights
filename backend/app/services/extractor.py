"""
Tender AI Platform - Document Text Extraction Service
Supports PDF (digital/scanned), DOCX, XLSX - all in-memory
"""

import io
import re
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
from loguru import logger

# Document processing
import pypdf
from docx import Document as DocxDocument
import openpyxl
import pandas as pd


class DocumentType(str, Enum):
    AVIS = "AVIS"
    RC = "RC"
    CPS = "CPS"
    ANNEXE = "ANNEXE"
    UNKNOWN = "UNKNOWN"


class ExtractionMethod(str, Enum):
    DIGITAL = "DIGITAL"
    OCR = "OCR"


@dataclass
class ExtractionResult:
    """Result of text extraction from a document"""
    filename: str
    document_type: DocumentType
    text: str
    page_count: Optional[int]
    extraction_method: ExtractionMethod
    file_size_bytes: int
    mime_type: str
    success: bool
    error: Optional[str] = None


# Classification keywords for document type detection
CLASSIFICATION_KEYWORDS = {
    DocumentType.AVIS: [
        "avis de consultation",
        "avis d'appel d'offres",
        "aoon",
        "aooi",
        "avis d'appel"
    ],
    DocumentType.RC: [
        "règlement de consultation",
        "reglement de consultation",
        "référence de consultation",
        "reference de consultation"
    ],
    DocumentType.CPS: [
        "cahier des prescriptions spéciales",
        "cahier des prescriptions speciales",
        "cps"
    ],
    DocumentType.ANNEXE: [
        "annexe",
        "additif",
        "avenant",
        "modification"
    ]
}


def detect_mime_type(filename: str) -> str:
    """Detect MIME type from filename extension"""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    mime_map = {
        'pdf': 'application/pdf',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'odt': 'application/vnd.oasis.opendocument.text',
        'rtf': 'application/rtf',
        'txt': 'text/plain',
    }
    
    return mime_map.get(ext, 'application/octet-stream')


def classify_document(text: str, filename: str = "") -> DocumentType:
    """
    Classify document type by scanning content keywords
    Follows spec: scan first page only, classify by content not filename
    """
    # Get first page content (approximate: first 3000 chars)
    first_page = text[:3000].lower()
    
    # Also check filename as secondary hint
    filename_lower = filename.lower()
    
    # Check each document type
    for doc_type, keywords in CLASSIFICATION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in first_page:
                return doc_type
            # Filename is secondary
            if keyword.replace(' ', '') in filename_lower.replace(' ', '').replace('_', ''):
                return doc_type
    
    return DocumentType.UNKNOWN


def extract_pdf_text(file_bytes: io.BytesIO) -> Tuple[str, int, ExtractionMethod]:
    """
    Extract text from PDF
    Uses pypdf for digital PDFs, falls back to OCR for scanned
    """
    file_bytes.seek(0)
    reader = pypdf.PdfReader(file_bytes)
    page_count = len(reader.pages)
    
    text_parts = []
    has_text = False
    
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text_parts.append(page_text)
        if page_text.strip():
            has_text = True
    
    full_text = "\n\n".join(text_parts)
    
    # Check if we got meaningful text
    # If text is too sparse, it's likely a scanned document
    if not has_text or len(full_text.strip()) < 100:
        # Trigger OCR
        return extract_pdf_ocr(file_bytes, page_count)
    
    return full_text, page_count, ExtractionMethod.DIGITAL


def extract_pdf_ocr(file_bytes: io.BytesIO, page_count: int) -> Tuple[str, int, ExtractionMethod]:
    """
    OCR extraction for scanned PDFs using PaddleOCR
    Only called when digital extraction fails
    """
    try:
        from paddleocr import PaddleOCR
        import fitz  # PyMuPDF for PDF to image conversion
        
        logger.info("Using PaddleOCR for scanned document")
        
        # Initialize PaddleOCR (CPU mode)
        ocr = PaddleOCR(use_angle_cls=True, lang='fr', use_gpu=False, show_log=False)
        
        file_bytes.seek(0)
        doc = fitz.open(stream=file_bytes.read(), filetype="pdf")
        
        all_text = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render page to image
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
            img_bytes = pix.tobytes("png")
            
            # OCR the image
            result = ocr.ocr(img_bytes, cls=True)
            
            if result and result[0]:
                page_text = "\n".join([line[1][0] for line in result[0]])
                all_text.append(f"--- Page {page_num + 1} ---\n{page_text}")
        
        doc.close()
        return "\n\n".join(all_text), page_count, ExtractionMethod.OCR
        
    except ImportError as e:
        logger.warning(f"OCR dependencies not available: {e}")
        return "[OCR REQUIRED - Dependencies not installed]", page_count, ExtractionMethod.OCR
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return f"[OCR FAILED: {str(e)}]", page_count, ExtractionMethod.OCR


def extract_docx_text(file_bytes: io.BytesIO) -> Tuple[str, int, ExtractionMethod]:
    """Extract text from DOCX files"""
    file_bytes.seek(0)
    doc = DocxDocument(file_bytes)
    
    paragraphs = [para.text for para in doc.paragraphs]
    
    # Also extract tables
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text for cell in row.cells)
            paragraphs.append(row_text)
    
    return "\n".join(paragraphs), None, ExtractionMethod.DIGITAL


def extract_xlsx_text(file_bytes: io.BytesIO) -> Tuple[str, int, ExtractionMethod]:
    """Extract text from Excel files"""
    file_bytes.seek(0)
    
    try:
        # Try with openpyxl first
        wb = openpyxl.load_workbook(file_bytes, read_only=True, data_only=True)
        
        all_text = []
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            all_text.append(f"=== Sheet: {sheet_name} ===")
            
            for row in sheet.iter_rows(values_only=True):
                row_values = [str(cell) if cell is not None else "" for cell in row]
                if any(row_values):
                    all_text.append(" | ".join(row_values))
        
        wb.close()
        return "\n".join(all_text), None, ExtractionMethod.DIGITAL
        
    except Exception:
        # Fallback to pandas
        file_bytes.seek(0)
        try:
            df = pd.read_excel(file_bytes, sheet_name=None)
            all_text = []
            for sheet_name, sheet_df in df.items():
                all_text.append(f"=== Sheet: {sheet_name} ===")
                all_text.append(sheet_df.to_string())
            return "\n".join(all_text), None, ExtractionMethod.DIGITAL
        except Exception as e:
            return f"[EXCEL EXTRACTION FAILED: {e}]", None, ExtractionMethod.DIGITAL


def extract_text(filename: str, file_bytes: io.BytesIO) -> ExtractionResult:
    """
    Main extraction function - routes to appropriate extractor
    All operations are in-memory (io.BytesIO)
    """
    # Get file size
    file_bytes.seek(0, 2)  # Seek to end
    file_size = file_bytes.tell()
    file_bytes.seek(0)  # Reset
    
    mime_type = detect_mime_type(filename)
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    try:
        # Route to appropriate extractor
        if ext == 'pdf' or mime_type == 'application/pdf':
            text, page_count, method = extract_pdf_text(file_bytes)
            
        elif ext in ('doc', 'docx') or 'word' in mime_type:
            text, page_count, method = extract_docx_text(file_bytes)
            
        elif ext in ('xls', 'xlsx') or 'excel' in mime_type or 'spreadsheet' in mime_type:
            text, page_count, method = extract_xlsx_text(file_bytes)
            
        elif ext == 'txt' or mime_type == 'text/plain':
            file_bytes.seek(0)
            text = file_bytes.read().decode('utf-8', errors='ignore')
            page_count = None
            method = ExtractionMethod.DIGITAL
            
        else:
            return ExtractionResult(
                filename=filename,
                document_type=DocumentType.UNKNOWN,
                text="",
                page_count=None,
                extraction_method=ExtractionMethod.DIGITAL,
                file_size_bytes=file_size,
                mime_type=mime_type,
                success=False,
                error=f"Unsupported file type: {ext}"
            )
        
        # Classify document
        doc_type = classify_document(text, filename)
        
        return ExtractionResult(
            filename=filename,
            document_type=doc_type,
            text=text,
            page_count=page_count,
            extraction_method=method,
            file_size_bytes=file_size,
            mime_type=mime_type,
            success=True
        )
        
    except Exception as e:
        logger.error(f"Extraction failed for {filename}: {e}")
        return ExtractionResult(
            filename=filename,
            document_type=DocumentType.UNKNOWN,
            text="",
            page_count=None,
            extraction_method=ExtractionMethod.DIGITAL,
            file_size_bytes=file_size,
            mime_type=mime_type,
            success=False,
            error=str(e)
        )


def extract_all_from_zip(zip_files: Dict[str, io.BytesIO]) -> List[ExtractionResult]:
    """
    Extract text from all files in a tender ZIP
    
    Args:
        zip_files: Dict mapping filename to BytesIO content
    
    Returns:
        List of ExtractionResult for each file
    """
    results = []
    
    for filename, file_bytes in zip_files.items():
        # Skip hidden files and directories
        if filename.startswith('.') or filename.startswith('__'):
            continue
            
        logger.info(f"Extracting: {filename}")
        result = extract_text(filename, file_bytes)
        results.append(result)
    
    return results
