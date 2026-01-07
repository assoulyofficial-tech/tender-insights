"""
Tender AI Platform - AI Pipeline Service
DeepSeek integration for metadata extraction
"""

import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from openai import OpenAI
from loguru import logger

from app.core.config import settings
from app.services.extractor import DocumentType, ExtractionResult


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


# System prompt for Avis extraction (Phase 1)
AVIS_EXTRACTION_PROMPT = """You are a deterministic extraction engine for Moroccan government tender documents (Avis de consultation).

## STRICT OPERATING MODE

You MUST NOT:
- Infer missing data
- Guess values
- Normalize currencies
- Translate text
- Summarize technical descriptions
- Invent lots, items, deadlines, or percentages

If a value is not explicitly stated: return null. No exceptions.

## EXTRACTION TASK

Extract the following fields from the Avis document text. Each field must include provenance tracking.

## OUTPUT SCHEMA (JSON)

```json
{
  "reference_tender": {
    "value": "<exact reference string or null>",
    "source_document": "AVIS",
    "source_date": null
  },
  "tender_type": {
    "value": "<AOON or AOOI or null>",
    "source_document": "AVIS",
    "source_date": null
  },
  "issuing_institution": {
    "value": "<full legal name or null>",
    "source_document": "AVIS",
    "source_date": null
  },
  "submission_deadline": {
    "date": {
      "value": "<DD/MM/YYYY or null>",
      "source_document": "AVIS",
      "source_date": null
    },
    "time": {
      "value": "<HH:MM or null>",
      "source_document": "AVIS",
      "source_date": null
    }
  },
  "folder_opening_location": {
    "value": "<location string or null>",
    "source_document": "AVIS",
    "source_date": null
  },
  "subject": {
    "value": "<full subject text or null>",
    "source_document": "AVIS",
    "source_date": null
  },
  "total_estimated_value": {
    "value": "<amount with currency or null>",
    "currency": "<MAD or other or null>",
    "source_document": "AVIS",
    "source_date": null
  },
  "lots": [
    {
      "lot_number": "<number or null>",
      "lot_subject": "<subject or null>",
      "lot_estimated_value": "<value or null>",
      "caution_provisoire": "<amount or null>"
    }
  ],
  "keywords": {
    "keywords_fr": ["<10 French keywords extracted from procurement subject>"],
    "keywords_eng": ["<10 English translations of the keywords>"],
    "keywords_ar": ["<10 Arabic translations of the keywords>"]
  }
}
```

## KEYWORD GENERATION RULES

Generate exactly 10 keywords per language based on:
- Procurement subject
- Technical items mentioned
- Sector-specific terms

Keywords power the search engine. Do not invent concepts not in the document.

## EXTRACTION RULES

1. Preserve original wording exactly
2. Do not cleanup or normalize reference numbers
3. If lot information is partial, extract what exists
4. If no lots are explicitly numbered, return empty array
5. tender_type must be exactly "AOON" or "AOOI" if stated, else null

Return ONLY the JSON object, no explanations."""


# System prompt for deep analysis (Phase 2)
UNIVERSAL_EXTRACTION_PROMPT = """You are a legal-technical extraction engine for Moroccan government tender documents.

## OPERATING MODE: STRICT EXTRACTION

You MUST NOT hallucinate, infer, guess, merge, or simplify.
If something is missing → null.
If something is unclear → null.

## INPUT DOCUMENTS PRIORITY

1. Latest Annexe (overrides all)
2. CPS (Cahier des Prescriptions Spéciales)
3. RC (Règlement de Consultation)  
4. Avis (lowest authority)

## OUTPUT SCHEMA (JSON)

```json
{
  "reference_tender": "<string or null>",
  "tender_type": "<AOON or AOOI or null>",
  "issuing_institution": "<string or null>",
  "institution_address": "<string or null>",
  "submission_deadline": {
    "date": "<DD/MM/YYYY or null>",
    "time": "<HH:MM or null>"
  },
  "folder_opening_location": "<string or null>",
  "subject": "<string or null>",
  "total_estimated_value": "<string or null>",
  "lots": [
    {
      "lot_number": "<string>",
      "lot_subject": "<string>",
      "lot_estimated_value": "<string or null>",
      "caution_provisoire": "<string or null>",
      "caution_definitive_percentage": "<string or null>",
      "estimated_caution_definitive_value": "<computed or null>",
      "execution_date": "<string or null>",
      "items": [
        {
          "item_name": "<exact name>",
          "quantity": "<number with unit>",
          "technical_description_full": "<VERBATIM technical specs>"
        }
      ]
    }
  ]
}
```

## COMPUTATION RULES

Only compute estimated_caution_definitive_value if:
- lot_estimated_value exists AND
- caution_definitive_percentage exists

Otherwise → null. Never assume percentages.

## LANGUAGE RULES

- Preserve original language
- Do NOT translate
- Do NOT summarize
- Technical descriptions must be VERBATIM

Return ONLY the JSON object."""


# System prompt for Ask AI (Phase 3)
ASK_AI_PROMPT = """You are an expert in Moroccan public procurement law and tender analysis.

## CONTEXT
You have access to the full text of a government tender including:
- Avis de consultation
- Règlement de consultation (RC)
- Cahier des Prescriptions Spéciales (CPS)
- Any annexes or modifications

## YOUR ROLE

Answer questions about this tender with:
1. Expert knowledge of Moroccan procurement regulations
2. Direct citations from the documents
3. Clear, actionable guidance

## LANGUAGE SUPPORT

You understand and respond in:
- French (formal)
- Moroccan Darija (informal Arabic dialect)

Respond in the same language the user asks in.

## CITATION FORMAT

When referencing documents, cite like:
[Document: CPS, Section 5.2]
[Document: Avis, Paragraph 3]

## RULES

1. Only answer based on the provided tender documents
2. If information is not in the documents, say so clearly
3. Do not make legal assumptions
4. Do not provide general advice - be specific to this tender
5. If asked about obligations, cite the exact clause

Be concise but complete."""


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
    
    def extract_avis_metadata(
        self, 
        avis_text: str,
        source_date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Phase 1: Extract Avis metadata
        
        Args:
            avis_text: Raw text from Avis document
            source_date: Date the document was published
        
        Returns:
            Structured metadata dict or None on failure
        """
        if not avis_text or len(avis_text.strip()) < 50:
            logger.warning("Avis text too short for extraction")
            return None
        
        logger.info("Starting Avis metadata extraction...")
        
        response = self._call_ai(
            AVIS_EXTRACTION_PROMPT,
            f"Extract metadata from this Avis document:\n\n{avis_text[:15000]}"  # Limit context
        )
        
        if not response:
            return None
        
        try:
            # Parse JSON from response
            # Handle potential markdown code blocks
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            
            metadata = json.loads(json_str.strip())
            
            # Inject source_date if provided
            if source_date:
                for key in ['reference_tender', 'tender_type', 'issuing_institution', 
                           'folder_opening_location', 'subject', 'total_estimated_value']:
                    if key in metadata and isinstance(metadata[key], dict):
                        metadata[key]['source_date'] = source_date
            
            logger.info("Avis metadata extraction complete")
            return metadata
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Response was: {response[:500]}")
            return None
    
    def extract_universal_metadata(
        self,
        documents: List[ExtractionResult]
    ) -> Optional[Dict[str, Any]]:
        """
        Phase 2: Deep analysis extraction
        Called on user click
        
        Args:
            documents: All extracted documents for a tender
        
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
        
        logger.info("Starting universal metadata extraction...")
        
        response = self._call_ai(
            UNIVERSAL_EXTRACTION_PROMPT,
            f"Extract universal metadata from these tender documents:\n\n{full_context[:30000]}"
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
        documents: List[ExtractionResult]
    ) -> Optional[Dict[str, Any]]:
        """
        Phase 3: Answer user questions about tender
        
        Args:
            question: User's question (French or Darija)
            documents: All tender documents
        
        Returns:
            Dict with answer and citations
        """
        # Build context
        context_parts = []
        for doc in documents:
            if doc.text:
                context_parts.append(
                    f"=== Document: {doc.document_type.value} ({doc.filename}) ===\n{doc.text[:5000]}"
                )
        
        full_context = "\n\n".join(context_parts)
        
        user_message = f"""TENDER DOCUMENTS:

{full_context[:25000]}

---

USER QUESTION:
{question}"""
        
        response = self._call_ai(
            ASK_AI_PROMPT,
            user_message,
            max_tokens=2048
        )
        
        if not response:
            return None
        
        # Parse citations from response
        citations = []
        import re
        citation_pattern = r'\[Document:\s*([^,\]]+)(?:,\s*([^\]]+))?\]'
        matches = re.findall(citation_pattern, response)
        for match in matches:
            citations.append({
                "document": match[0].strip(),
                "section": match[1].strip() if match[1] else None
            })
        
        return {
            "answer": response,
            "citations": citations
        }


# Singleton instance
ai_service = AIService()
