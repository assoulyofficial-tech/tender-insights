# -*- coding: utf-8 -*-
"""
Tender AI Platform - AI Pipeline Service
DeepSeek integration for metadata extraction
"""

import json
import re
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from openai import OpenAI
from loguru import logger

from app.core.config import settings
from app.services.extractor import DocumentType, ExtractionResult


def _load_prompt(filename: str) -> str:
    """Load a prompt from the prompts directory"""
    prompt_path = Path(__file__).parent / "prompts" / filename
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


@dataclass
class AvisMetadata:
    """Structured Avis metadata matching schema spec"""
    reference_tender: Dict[str, Any]
    tender_type: Dict[str, Any]
    issuing_institution: Dict[str, Any]
    submission_deadline: Dict[str, Any]
    folder_opening_location: Dict[str, Any]
    subject: Dict[str, Any]
    total_estimated_value: Dict[str, Any]
    lots: List[Dict[str, Any]]
    keywords: Dict[str, List[str]]


# Lazy-loaded prompts from external files to avoid encoding issues
AVIS_EXTRACTION_PROMPT = None
PRIMARY_METADATA_PROMPT = None
UNIVERSAL_EXTRACTION_PROMPT = None
ASK_AI_PROMPT = None


def get_avis_extraction_prompt() -> str:
    """Get the AVIS_EXTRACTION_PROMPT, loading from file if needed"""
    global AVIS_EXTRACTION_PROMPT
    if AVIS_EXTRACTION_PROMPT is None:
        AVIS_EXTRACTION_PROMPT = _load_prompt("avis_extraction_prompt.txt")
    return AVIS_EXTRACTION_PROMPT


def get_primary_metadata_prompt() -> str:
    """Get the PRIMARY_METADATA_PROMPT, loading from file if needed"""
    global PRIMARY_METADATA_PROMPT
    if PRIMARY_METADATA_PROMPT is None:
        PRIMARY_METADATA_PROMPT = _load_prompt("primary_metadata_extraction_prompt.txt")
    return PRIMARY_METADATA_PROMPT


def get_universal_extraction_prompt() -> str:
    """Get the UNIVERSAL_EXTRACTION_PROMPT, loading from file if needed"""
    global UNIVERSAL_EXTRACTION_PROMPT
    if UNIVERSAL_EXTRACTION_PROMPT is None:
        UNIVERSAL_EXTRACTION_PROMPT = _load_prompt("universal_extraction_prompt.txt")
    return UNIVERSAL_EXTRACTION_PROMPT


def get_ask_ai_prompt() -> str:
    """Get the ASK_AI_PROMPT, loading from file if needed"""
    global ASK_AI_PROMPT
    if ASK_AI_PROMPT is None:
        ASK_AI_PROMPT = _load_prompt("ask_ai_prompt.txt")
    return ASK_AI_PROMPT



class AIService:
    """DeepSeek AI integration for tender analysis"""
    
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        self.model = settings.DEEPSEEK_MODEL
    
    def _call_ai(
        self, 
        system_prompt: str, 
        user_content: str,
        max_tokens: int = 4096
    ) -> Optional[str]:
        """Make AI API call"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=max_tokens,
                temperature=0  # Deterministic extraction
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"AI API call failed: {e}")
            return None
    
    def extract_primary_metadata(
        self,
        source_text: str,
        source_label: str,
        source_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Extract Phase-1 (primary) metadata from any source text.

        source_label must be one of: WEBSITE, AVIS, RC, CPS.
        The prompt enforces that `source_document` matches this label.
        """
        if not source_text or len(source_text.strip()) < 50:
            logger.warning("Source text too short for primary metadata extraction")
            return None

        logger.info(f"Starting primary metadata extraction (source={source_label})...")

        response = self._call_ai(
            get_primary_metadata_prompt(),
            f"SOURCE_LABEL: {source_label}\n\nTEXTE À ANALYSER:\n\n{source_text[:20000]}",
        )

        if not response:
            return None

        try:
            # Parse JSON from response (handle potential markdown code blocks)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            metadata = json.loads(json_str.strip())

            # Inject source_date if provided
            if source_date:
                def _inject(obj: Any):
                    if isinstance(obj, dict) and "source_date" in obj:
                        obj["source_date"] = source_date
                    return obj

                for k, v in list(metadata.items()):
                    if isinstance(v, dict) and "source_date" in v:
                        metadata[k] = _inject(v)
                # submission_deadline nested
                if isinstance(metadata.get("submission_deadline"), dict):
                    sd = metadata["submission_deadline"]
                    if isinstance(sd.get("date"), dict):
                        _inject(sd["date"])
                    if isinstance(sd.get("time"), dict):
                        _inject(sd["time"])

            logger.info("Primary metadata extraction complete")
            return metadata

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Response was: {response[:500]}")
            return None

    def extract_avis_metadata(
        self,
        avis_text: str,
        source_date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Backward compatible wrapper (Phase 1)."""
        return self.extract_primary_metadata(avis_text, source_label="AVIS", source_date=source_date)
    
    def extract_universal_metadata(
        self,
        documents: List[ExtractionResult],
        website_contact_raw: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Phase 2: Deep analysis extraction
        Called on user click
        
        Args:
            documents: All extracted documents for a tender
            website_contact_raw: Raw contact text scraped from website (to be structured by AI)
        
        Returns:
            Universal metadata dict or None
        """
        # Build context from all documents
        context_parts = []
        
        # Order by priority: Annexe, CPS, RC, Avis
        priority_order = [
            DocumentType.ANNEXE,
            DocumentType.CPS,
            DocumentType.RC,
            DocumentType.AVIS
        ]
        
        for doc_type in priority_order:
            for doc in documents:
                if doc.document_type == doc_type and doc.text:
                    context_parts.append(f"=== {doc_type.value}: {doc.filename} ===\n{doc.text[:8000]}")
        
        if not context_parts:
            logger.warning("No documents available for deep analysis")
            return None
        
        full_context = "\n\n".join(context_parts)
        
        # Add website contact info if available
        if website_contact_raw:
            full_context += f"\n\n=== CONTACT ADMINISTRATIF (Site Web - à structurer) ===\n{website_contact_raw}"
        
        logger.info("Starting universal metadata extraction...")
        
        response = self._call_ai(
            get_universal_extraction_prompt(),
            f"Extrait les métadonnées universelles de ces documents d'appel d'offres:\n\n{full_context[:30000]}"
        )
        
        if not response:
            return None
        
        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            
            return json.loads(json_str.strip())
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse deep analysis response: {e}")
            return None
    
    def ask_ai(
        self,
        question: str,
        documents: List[ExtractionResult],
        tender_reference: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Phase 3: Expert Q&A about tender documents
        Supports French, Moroccan Darija, and Modern Standard Arabic
        
        Args:
            question: User's question in any supported language
            documents: All tender documents for context
            tender_reference: Optional tender reference for logging
        
        Returns:
            Dict with answer, citations, detected language, and metadata
        """
        if not question or len(question.strip()) < 3:
            logger.warning("Question too short")
            return {
                "answer": "Veuillez poser une question plus détaillée.",
                "citations": [],
                "language_detected": "fr",
                "error": "question_too_short"
            }
        
        # Build context with document priority ordering
        context_parts = []
        doc_summary = []
        
        # Order documents by type for better context
        priority_order = [
            DocumentType.AVIS,
            DocumentType.RC,
            DocumentType.CPS,
            DocumentType.ANNEXE
        ]
        
        for doc_type in priority_order:
            for doc in documents:
                if doc.document_type == doc_type and doc.text:
                    # Use more context for important documents
                    char_limit = 8000 if doc_type in [DocumentType.CPS, DocumentType.RC] else 5000
                    context_parts.append(
                        f"=== {doc_type.value}: {doc.filename} ===\n{doc.text[:char_limit]}"
                    )
                    doc_summary.append(f"{doc_type.value} ({doc.filename})")
        
        if not context_parts:
            return {
                "answer": "Aucun document disponible pour répondre à cette question.",
                "citations": [],
                "language_detected": None,
                "error": "no_documents"
            }
        
        full_context = "\n\n".join(context_parts)
        
        # Build user message with clear structure
        user_message = f"""DOSSIER D'APPEL D'OFFRES
Documents disponibles: {', '.join(doc_summary)}

--- CONTENU DES DOCUMENTS ---

{full_context[:30000]}

--- FIN DES DOCUMENTS ---

QUESTION DE L'UTILISATEUR:
{question}"""
        
        logger.info(f"Ask AI: Processing question for tender {tender_reference or 'unknown'}")
        
        response = self._call_ai(
            get_ask_ai_prompt(),
            user_message,
            max_tokens=2048
        )
        
        if not response:
            return {
                "answer": "Une erreur s'est produite lors du traitement de votre question. Veuillez réessayer.",
                "citations": [],
                "language_detected": None,
                "error": "ai_call_failed"
            }
        
        # Parse citations with new format [Source: DOC, Section X]
        citations = []
        citation_patterns = [
            r'\[Source:\s*([^,\]]+)(?:,\s*([^\]]+))?\]',  # New format
            r'\[Document:\s*([^,\]]+)(?:,\s*([^\]]+))?\]',  # Legacy format
            r'\*\*\[Source:\s*([^,\]]+)(?:,\s*([^\]]+))?\]\*\*',  # Bold format
        ]
        
        seen_citations = set()
        for pattern in citation_patterns:
            matches = re.findall(pattern, response)
            for match in matches:
                doc_name = match[0].strip()
                section = match[1].strip() if len(match) > 1 and match[1] else None
                
                # Normalize document type
                doc_type_normalized = doc_name.upper()
                for dt in DocumentType:
                    if dt.value in doc_type_normalized or doc_type_normalized in dt.value:
                        doc_type_normalized = dt.value
                        break
                
                citation_key = f"{doc_type_normalized}:{section}"
                if citation_key not in seen_citations:
                    seen_citations.add(citation_key)
                    citations.append({
                        "document": doc_type_normalized,
                        "section": section,
                        "raw": match[0]
                    })
        
        # Detect language from response (simple heuristic)
        language_detected = "fr"  # Default
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', response))
        if arabic_chars > 50:
            # Check for Darija markers (common Darija words)
            darija_markers = ['كيفاش', 'شنو', 'علاش', 'فين', 'واش', 'ديال', 'هاد']
            if any(marker in response for marker in darija_markers):
                language_detected = "darija"
            else:
                language_detected = "ar"
        
        return {
            "answer": response,
            "citations": citations,
            "language_detected": language_detected,
            "documents_used": doc_summary,
            "question": question
        }


# Singleton instance
ai_service = AIService()
