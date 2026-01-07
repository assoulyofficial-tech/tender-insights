"""
Tender AI Platform - Database Models
Matches TypeScript types exactly
"""

from sqlalchemy import (
    Column, String, Text, DateTime, Enum, JSON, ForeignKey, Integer, Boolean
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import uuid
import enum


class TenderStatus(str, enum.Enum):
    PENDING = "PENDING"
    LISTED = "LISTED"
    ANALYZED = "ANALYZED"
    ERROR = "ERROR"


class TenderType(str, enum.Enum):
    AOON = "AOON"
    AOOI = "AOOI"


class DocumentType(str, enum.Enum):
    AVIS = "AVIS"
    RC = "RC"
    CPS = "CPS"
    ANNEXE = "ANNEXE"
    UNKNOWN = "UNKNOWN"


class ExtractionMethod(str, enum.Enum):
    DIGITAL = "DIGITAL"
    OCR = "OCR"


class Tender(Base):
    """Main tender record"""
    __tablename__ = "tenders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_reference = Column(String(255), index=True)
    source_url = Column(Text, nullable=False)
    status = Column(
        Enum(TenderStatus), 
        default=TenderStatus.PENDING, 
        nullable=False,
        index=True
    )
    
    # Scraping metadata
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    download_date = Column(String(10))  # YYYY-MM-DD format
    
    # AI-extracted metadata (Phase 1 - Avis)
    # Stored as JSONB for flexibility with provenance tracking
    avis_metadata = Column(JSONB, nullable=True)
    
    # AI-extracted metadata (Phase 2 - Universal deep analysis)
    universal_metadata = Column(JSONB, nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    documents = relationship("TenderDocument", back_populates="tender", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tender {self.external_reference or self.id}>"


class TenderDocument(Base):
    """Document extracted from tender ZIP"""
    __tablename__ = "tender_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False)
    
    document_type = Column(Enum(DocumentType), default=DocumentType.UNKNOWN)
    filename = Column(String(500), nullable=False)
    
    # Extracted text content
    raw_text = Column(Text, nullable=True)
    page_count = Column(Integer, nullable=True)
    
    # Extraction method used
    extraction_method = Column(Enum(ExtractionMethod), nullable=True)
    
    # File metadata (stored in memory, not on disk)
    file_size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    
    # Timestamps
    extracted_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    tender = relationship("Tender", back_populates="documents")

    def __repr__(self):
        return f"<TenderDocument {self.filename}>"


class ScraperJob(Base):
    """Track scraper execution history"""
    __tablename__ = "scraper_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    target_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    status = Column(String(50), default="RUNNING")  # RUNNING, COMPLETED, FAILED, STOPPED
    
    # Stats
    total_found = Column(Integer, default=0)
    downloaded = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    extracted = Column(Integer, default=0)
    
    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    elapsed_seconds = Column(Integer, nullable=True)
    
    # Current phase for progress tracking
    current_phase = Column(String(100), default="Initializing")
    
    # Error log
    error_log = Column(Text, nullable=True)

    def __repr__(self):
        return f"<ScraperJob {self.target_date} - {self.status}>"
