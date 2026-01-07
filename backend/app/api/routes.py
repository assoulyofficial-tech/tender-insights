"""
Tender AI Platform - API Routes
FastAPI endpoints for frontend integration
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from uuid import UUID
import asyncio

from app.core.database import get_db
from app.models import Tender, TenderDocument, ScraperJob, TenderStatus, DocumentType
from app.services.scraper import TenderScraper, ScraperProgress
from app.services.extractor import extract_all_from_zip
from app.services.ai_pipeline import ai_service

router = APIRouter()

# Global scraper state
_scraper_instance: Optional[TenderScraper] = None
_current_job_id: Optional[str] = None


# ============================
# PYDANTIC MODELS
# ============================

class ScraperRunRequest(BaseModel):
    target_date: Optional[str] = None


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
    """Trigger a manual scraper run"""
    global _scraper_instance, _current_job_id
    
    if _scraper_instance and _scraper_instance.progress.is_running:
        raise HTTPException(400, "Scraper is already running")
    
    # Create job record
    job = ScraperJob(
        target_date=request.target_date or datetime.now().strftime("%Y-%m-%d"),
        status="RUNNING"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    _current_job_id = str(job.id)
    
    # Run scraper in background
    background_tasks.add_task(
        _run_scraper_task,
        str(job.id),
        request.target_date
    )
    
    return {"job_id": str(job.id), "status": "started"}


async def _run_scraper_task(job_id: str, target_date: Optional[str]):
    """Background task to run scraper"""
    global _scraper_instance
    
    from app.core.database import SessionLocal
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
        results = await _scraper_instance.run(target_date)
        
        # Process downloads
        extracted_count = 0
        for result in results:
            if result.success and result.zip_bytes:
                # Create tender record
                tender = Tender(
                    external_reference=f"tender_{result.index}",
                    source_url=result.url,
                    status=TenderStatus.PENDING,
                    download_date=target_date or datetime.now().strftime("%Y-%m-%d")
                )
                db.add(tender)
                db.commit()
                db.refresh(tender)
                
                # Extract files from ZIP
                files = result.get_files()
                extractions = extract_all_from_zip(files)
                
                avis_text = None
                for ext in extractions:
                    doc = TenderDocument(
                        tender_id=tender.id,
                        document_type=DocumentType(ext.document_type.value),
                        filename=ext.filename,
                        raw_text=ext.text,
                        page_count=ext.page_count,
                        extraction_method=ext.extraction_method.value,
                        file_size_bytes=ext.file_size_bytes,
                        mime_type=ext.mime_type
                    )
                    db.add(doc)
                    
                    if ext.document_type.value == "AVIS":
                        avis_text = ext.text
                
                # Run AI extraction on Avis
                if avis_text:
                    metadata = ai_service.extract_avis_metadata(avis_text)
                    if metadata:
                        tender.avis_metadata = metadata
                        tender.status = TenderStatus.LISTED
                        # Try to extract reference from metadata
                        if metadata.get("reference_tender", {}).get("value"):
                            tender.external_reference = metadata["reference_tender"]["value"]
                    else:
                        tender.status = TenderStatus.ERROR
                        tender.error_message = "AI extraction failed"
                else:
                    tender.status = TenderStatus.ERROR
                    tender.error_message = "No Avis document found"
                
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
    for doc in documents:
        extraction_results.append(ExtractionResult(
            filename=doc.filename,
            document_type=DocumentType(doc.document_type.value) if doc.document_type else DocumentType.UNKNOWN,
            text=doc.raw_text or "",
            page_count=doc.page_count,
            extraction_method=ExtractionMethod(doc.extraction_method) if doc.extraction_method else ExtractionMethod.DIGITAL,
            file_size_bytes=doc.file_size_bytes or 0,
            mime_type=doc.mime_type or "",
            success=True
        ))
    
    # Run deep analysis
    universal_metadata = ai_service.extract_universal_metadata(extraction_results)
    
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
    for doc in documents:
        extraction_results.append(ExtractionResult(
            filename=doc.filename,
            document_type=DocumentType(doc.document_type.value) if doc.document_type else DocumentType.UNKNOWN,
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
