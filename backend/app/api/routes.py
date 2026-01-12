"""
Tender AI Platform - API Routes
FastAPI endpoints for frontend integration
"""

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel
from uuid import UUID

from app.core.database import get_db
from app.models import Tender, TenderDocument, ScraperJob, TenderStatus, DocumentType as ModelDocumentType
from app.services.scraper import TenderScraper, ScraperProgress, WebsiteMetadata, DownloadedTender
from app.services.extractor import (
    DocumentType as ExtractorDocumentType,
    extract_best_documents_for_phase1_lazy,
    ExtractionResult,
    ExtractionMethod,
)
from app.services.phase1_merge import merge_phase1_metadata, is_metadata_complete
from app.services.ai_pipeline import ai_service

router = APIRouter()

# Global scraper state
_scraper_instance: Optional[TenderScraper] = None
_current_job_id: Optional[str] = None


# ============================
# PYDANTIC MODELS
# ============================

class ScraperRunRequest(BaseModel):
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None    # YYYY-MM-DD (defaults to start_date)


class ScraperStatusResponse(BaseModel):
    is_running: bool
    current_phase: str
    total_tenders: int
    downloaded: int
    failed: int
    elapsed_seconds: float
    last_run: Optional[str] = None


class TenderListParams(BaseModel):
    q: Optional[str] = None
    status: Optional[TenderStatus] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    page: int = 1
    per_page: int = 50


class AskAIRequest(BaseModel):
    question: str


class AskAIResponse(BaseModel):
    answer: str
    citations: List[dict]


# ============================
# HEALTH CHECK
# ============================

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================
# SCRAPER ENDPOINTS
# ============================

@router.post("/api/scraper/run")
async def run_scraper(
    request: ScraperRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Trigger a manual scraper run
    
    Args:
        start_date: Start of date range (YYYY-MM-DD), defaults to yesterday
        end_date: End of date range (YYYY-MM-DD), defaults to start_date
    """
    global _scraper_instance, _current_job_id
    
    if _scraper_instance and _scraper_instance.progress.is_running:
        raise HTTPException(400, "Scraper is already running")
    
    # Default dates
    start = request.start_date or datetime.now().strftime("%Y-%m-%d")
    end = request.end_date or start
    
    # Create job record
    job = ScraperJob(
        target_date=f"{start} to {end}",
        status="RUNNING"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    _current_job_id = str(job.id)
    
    # Run scraper in a separate thread (required for Playwright on Windows)
    import threading
    scraper_thread = threading.Thread(
        target=_run_scraper_sync,
        args=(str(job.id), start, end),
        daemon=True
    )
    scraper_thread.start()
    
    return {"job_id": str(job.id), "status": "started", "date_range": f"{start} to {end}"}


def _run_scraper_sync(job_id: str, start_date: str, end_date: str):
    """
    Run scraper in a separate thread with its own event loop.
    This is required on Windows because Playwright needs ProactorEventLoop
    but uvicorn uses SelectorEventLoop.
    """
    global _scraper_instance
    
    # Create a new event loop for this thread (with ProactorEventLoop on Windows)
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(_run_scraper_async(job_id, start_date, end_date))
    finally:
        loop.close()


async def _run_scraper_async(job_id: str, start_date: str, end_date: str):
    """Async scraper logic with LAZY DOWNLOAD + LAZY OCR optimization"""
    global _scraper_instance
    
    from app.core.database import SessionLocal
    from loguru import logger
    db = SessionLocal()
    
    try:
        job = db.query(ScraperJob).filter(ScraperJob.id == job_id).first()
        if not job:
            return
        
        def on_progress(progress: ScraperProgress):
            job.current_phase = progress.phase
            job.total_found = progress.total
            job.downloaded = progress.downloaded
            job.failed = progress.failed
            db.commit()
        
        _scraper_instance = TenderScraper(on_progress=on_progress)
        results = await _scraper_instance.run(start_date, end_date)
        
        # Handle case where no tenders were found
        if not results:
            job.status = "COMPLETED"
            job.total_found = 0
            job.downloaded = 0
            job.extracted = 0
            job.completed_at = datetime.utcnow()
            job.elapsed_seconds = int(_scraper_instance.progress.elapsed_seconds)
            db.commit()
            return
        
        # Process downloads using website-first + LAZY fallback workflow
        extracted_count = 0
        for result in results:
            if not result.success:
                continue

            web_meta = result.website_metadata

            tender = Tender(
                external_reference=web_meta.reference_tender if web_meta and web_meta.reference_tender else f"tender_{result.index}",
                source_url=result.url,
                status=TenderStatus.PENDING,
                download_date=start_date or datetime.now().strftime("%Y-%m-%d"),
            )
            db.add(tender)
            db.commit()
            db.refresh(tender)

            merged_metadata = None
            tender_ref = web_meta.reference_tender if web_meta else None

            # 1) WEBSITE (consultation text) first - always try this
            if web_meta and web_meta.consultation_text:
                logger.info(f"Extracting from WEBSITE for {tender_ref or tender.id}")
                website_metadata = ai_service.extract_primary_metadata(
                    web_meta.consultation_text,
                    source_label="WEBSITE",
                )
                merged_metadata = website_metadata
            
            # 2) Check if we need document fallback
            needs_fallback = not is_metadata_complete(merged_metadata)
            
            if needs_fallback and result.zip_bytes:
                logger.info(f"Website data incomplete, using document fallbacks for {tender_ref or tender.id}")
                files = result.get_files()
                
                # Extract documents with LAZY OCR (classify first, OCR only when needed)
                extractions, _classifications = extract_best_documents_for_phase1_lazy(
                    files, 
                    tender_ref,
                    current_metadata=merged_metadata  # Pass current state to know what's missing
                )
                
                # Store the best document for later deep analysis
                doc_to_store = (
                    extractions.get(ExtractorDocumentType.AVIS)
                    or extractions.get(ExtractorDocumentType.RC)
                    or extractions.get(ExtractorDocumentType.CPS)
                )
                
                if doc_to_store and doc_to_store.success:
                    db_doc = TenderDocument(
                        tender_id=tender.id,
                        document_type=ModelDocumentType(doc_to_store.document_type.value),
                        filename=doc_to_store.filename,
                        raw_text=doc_to_store.text,
                        page_count=doc_to_store.page_count,
                        extraction_method=doc_to_store.extraction_method.value,
                        file_size_bytes=doc_to_store.file_size_bytes,
                        mime_type=doc_to_store.mime_type,
                    )
                    db.add(db_doc)

                # AVIS → RC → CPS fallbacks (stop when complete)
                for label, dt in [
                    ("AVIS", ExtractorDocumentType.AVIS),
                    ("RC", ExtractorDocumentType.RC),
                    ("CPS", ExtractorDocumentType.CPS),
                ]:
                    if is_metadata_complete(merged_metadata):
                        logger.info(f"All fields complete, stopping fallback at {label}")
                        break
                        
                    ext = extractions.get(dt)
                    if ext and ext.success and ext.text:
                        logger.info(f"Merging from {label} for {tender_ref or tender.id}")
                        fb = ai_service.extract_primary_metadata(ext.text, source_label=label)
                        merged_metadata = merge_phase1_metadata(merged_metadata, fb)

            elif needs_fallback and not result.zip_bytes:
                logger.warning(f"Website incomplete but no ZIP available for {tender_ref or tender.id}")

            if merged_metadata:
                # Persist website contact raw so Phase-2 can structure it
                if web_meta and web_meta.contact_administratif:
                    merged_metadata.setdefault("website_extended", {})
                    merged_metadata["website_extended"]["contact_administratif"] = {
                        "value": web_meta.contact_administratif,
                        "source_document": "WEBSITE",
                        "source_date": None,
                    }

                # Ensure tender.external_reference aligns with extracted reference when available
                ref_val = None
                if isinstance(merged_metadata.get("reference_tender"), dict):
                    ref_val = merged_metadata["reference_tender"].get("value")
                if ref_val:
                    tender.external_reference = ref_val
                elif web_meta and web_meta.reference_tender:
                    tender.external_reference = web_meta.reference_tender

                tender.avis_metadata = merged_metadata
                tender.status = TenderStatus.LISTED
            else:
                tender.status = TenderStatus.ERROR
                tender.error_message = "Phase 1 extraction failed (website + documents)"

            db.commit()
            extracted_count += 1
        
        # Finalize job
        job.status = "COMPLETED"
        job.extracted = extracted_count
        job.completed_at = datetime.utcnow()
        job.elapsed_seconds = int(_scraper_instance.progress.elapsed_seconds)
        db.commit()
        
    except Exception as e:
        job.status = "FAILED"
        job.error_log = str(e)
        job.completed_at = datetime.utcnow()
        db.commit()
        raise
    finally:
        _scraper_instance = None
        db.close()


@router.get("/api/scraper/status", response_model=ScraperStatusResponse)
def get_scraper_status(db: Session = Depends(get_db)):
    """Get current scraper status"""
    global _scraper_instance
    
    # Get last completed job
    last_job = db.query(ScraperJob).filter(
        ScraperJob.status.in_(["COMPLETED", "FAILED"])
    ).order_by(desc(ScraperJob.completed_at)).first()
    
    if _scraper_instance and _scraper_instance.progress.is_running:
        p = _scraper_instance.progress
        return ScraperStatusResponse(
            is_running=True,
            current_phase=p.phase,
            total_tenders=p.total,
            downloaded=p.downloaded,
            failed=p.failed,
            elapsed_seconds=p.elapsed_seconds,
            last_run=last_job.completed_at.isoformat() if last_job else None
        )
    
    return ScraperStatusResponse(
        is_running=False,
        current_phase="Idle",
        total_tenders=0,
        downloaded=0,
        failed=0,
        elapsed_seconds=0,
        last_run=last_job.completed_at.isoformat() if last_job else None
    )


@router.post("/api/scraper/stop")
def stop_scraper():
    """Stop running scraper"""
    global _scraper_instance
    
    if _scraper_instance and _scraper_instance.progress.is_running:
        _scraper_instance.stop()
        return {"stopped": True}
    
    return {"stopped": False, "message": "No scraper running"}


# ============================
# TENDER ENDPOINTS
# ============================

@router.get("/api/tenders")
def list_tenders(
    q: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    db: Session = Depends(get_db)
):
    """List tenders with optional filters"""
    query = db.query(Tender)
    
    # Apply filters
    if status:
        query = query.filter(Tender.status == status)
    
    if date_from:
        query = query.filter(Tender.download_date >= date_from)
    
    if date_to:
        query = query.filter(Tender.download_date <= date_to)
    
    if q:
        # Search in JSON metadata
        search_filter = f"%{q}%"
        query = query.filter(
            Tender.external_reference.ilike(search_filter) |
            Tender.avis_metadata['subject']['value'].astext.ilike(search_filter) |
            Tender.avis_metadata['issuing_institution']['value'].astext.ilike(search_filter)
        )
    
    # Pagination
    total = query.count()
    query = query.order_by(desc(Tender.created_at))
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    items = query.all()
    
    return {
        "items": [_tender_to_dict(t) for t in items],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }


@router.get("/api/tenders/{tender_id}")
def get_tender(tender_id: str, db: Session = Depends(get_db)):
    """Get single tender with documents"""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(404, "Tender not found")
    
    result = _tender_to_dict(tender)
    result["documents"] = [
        {
            "id": str(doc.id),
            "document_type": doc.document_type.value if doc.document_type else None,
            "filename": doc.filename,
            "page_count": doc.page_count,
            "extraction_method": doc.extraction_method,
            "file_size_bytes": doc.file_size_bytes
        }
        for doc in tender.documents
    ]
    
    return result


@router.post("/api/tenders/{tender_id}/analyze")
def analyze_tender(tender_id: str, db: Session = Depends(get_db)):
    """Trigger deep analysis (Phase 2) for a tender"""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(404, "Tender not found")
    
    # Get all documents
    documents = tender.documents
    if not documents:
        raise HTTPException(400, "No documents available for analysis")
    
    # Convert to ExtractionResult format for AI service
    from app.services.extractor import ExtractionResult, ExtractionMethod
    
    extraction_results = []
    from app.services.extractor import DocumentType as ExtractorDocumentType

    for doc in documents:
        extraction_results.append(ExtractionResult(
            filename=doc.filename,
            document_type=ExtractorDocumentType(doc.document_type.value) if doc.document_type else ExtractorDocumentType.UNKNOWN,
            text=doc.raw_text or "",
            page_count=doc.page_count,
            extraction_method=ExtractionMethod(doc.extraction_method) if doc.extraction_method else ExtractionMethod.DIGITAL,
            file_size_bytes=doc.file_size_bytes or 0,
            mime_type=doc.mime_type or "",
            success=True
        ))
    
    # Extract website contact info if available (to be structured by AI)
    website_contact_raw = None
    if tender.avis_metadata:
        website_extended = tender.avis_metadata.get("website_extended", {})
        contact_info = website_extended.get("contact_administratif", {})
        if contact_info and contact_info.get("value"):
            website_contact_raw = contact_info.get("value")
    
    # Run deep analysis with website contact
    universal_metadata = ai_service.extract_universal_metadata(
        extraction_results,
        website_contact_raw=website_contact_raw
    )
    
    if universal_metadata:
        tender.universal_metadata = universal_metadata
        tender.status = TenderStatus.ANALYZED
        db.commit()
        db.refresh(tender)
        return _tender_to_dict(tender)
    else:
        raise HTTPException(500, "Deep analysis failed")


@router.post("/api/tenders/{tender_id}/ask", response_model=AskAIResponse)
def ask_ai_about_tender(
    tender_id: str,
    request: AskAIRequest,
    db: Session = Depends(get_db)
):
    """Ask AI about a specific tender (Phase 3)"""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(404, "Tender not found")
    
    documents = tender.documents
    if not documents:
        raise HTTPException(400, "No documents available")
    
    # Convert to ExtractionResult format
    from app.services.extractor import ExtractionResult, ExtractionMethod
    
    extraction_results = []
    from app.services.extractor import DocumentType as ExtractorDocumentType

    for doc in documents:
        extraction_results.append(ExtractionResult(
            filename=doc.filename,
            document_type=ExtractorDocumentType(doc.document_type.value) if doc.document_type else ExtractorDocumentType.UNKNOWN,
            text=doc.raw_text or "",
            page_count=doc.page_count,
            extraction_method=ExtractionMethod(doc.extraction_method) if doc.extraction_method else ExtractionMethod.DIGITAL,
            file_size_bytes=doc.file_size_bytes or 0,
            mime_type=doc.mime_type or "",
            success=True
        ))
    
    result = ai_service.ask_ai(request.question, extraction_results)
    
    if result:
        return AskAIResponse(**result)
    else:
        raise HTTPException(500, "AI query failed")


def _tender_to_dict(tender: Tender) -> dict:
    """Convert Tender model to dict"""
    return {
        "id": str(tender.id),
        "external_reference": tender.external_reference,
        "source_url": tender.source_url,
        "status": tender.status.value if tender.status else None,
        "scraped_at": tender.scraped_at.isoformat() if tender.scraped_at else None,
        "download_date": tender.download_date,
        "avis_metadata": tender.avis_metadata,
        "universal_metadata": tender.universal_metadata,
        "error_message": tender.error_message,
        "created_at": tender.created_at.isoformat() if tender.created_at else None,
        "updated_at": tender.updated_at.isoformat() if tender.updated_at else None
    }
