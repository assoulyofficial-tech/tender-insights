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


# System prompt for Avis extraction (Phase 1) - French language
AVIS_EXTRACTION_PROMPT = """Tu es un moteur d'extraction déterministe pour les documents de marchés publics marocains (Avis de consultation).

## MODE OPÉRATOIRE STRICT

Tu NE DOIS PAS:
- Inférer des données manquantes
- Deviner des valeurs
- Normaliser les devises
- Traduire le texte
- Résumer les descriptions techniques
- Inventer des lots, articles, délais ou pourcentages

Si une valeur n'est pas explicitement indiquée: retourne null. Sans exception.

## TÂCHE D'EXTRACTION

Extrait les champs suivants du document Avis. Chaque champ doit inclure le suivi de provenance.

## SCHÉMA DE SORTIE (JSON)

```json
{
  "reference_tender": {
    "value": "<chaîne de référence exacte ou null>",
    "source_document": "AVIS",
    "source_date": null
  },
  "tender_type": {
    "value": "<type exact tel qu'indiqué dans le document ou null>",
    "source_document": "AVIS",
    "source_date": null
  },
  "issuing_institution": {
    "value": "<nom légal complet ou null>",
    "source_document": "AVIS",
    "source_date": null
  },
  "submission_deadline": {
    "date": {
      "value": "<JJ/MM/AAAA ou null>",
      "source_document": "AVIS",
      "source_date": null
    },
    "time": {
      "value": "<HH:MM ou null>",
      "source_document": "AVIS",
      "source_date": null
    }
  },
  "folder_opening_location": {
    "value": "<lieu ou null>",
    "source_document": "AVIS",
    "source_date": null
  },
  "subject": {
    "value": "<texte complet du sujet ou null>",
    "source_document": "AVIS",
    "source_date": null
  },
  "total_estimated_value": {
    "value": "<montant avec devise ou null>",
    "currency": "<MAD ou autre ou null>",
    "source_document": "AVIS",
    "source_date": null
  },
  "lots": [
    {
      "lot_number": "<numéro ou null>",
      "lot_subject": "<sujet ou null>",
      "lot_estimated_value": "<valeur ou null>",
      "caution_provisoire": "<montant ou null>"
    }
  ],
  "keywords": {
    "keywords_fr": ["<10 mots-clés français extraits du sujet>"],
    "keywords_eng": ["<10 traductions anglaises des mots-clés>"],
    "keywords_ar": ["<10 traductions arabes des mots-clés>"]
  }
}
```

## RÈGLES POUR LE TYPE D'APPEL D'OFFRES (tender_type)

Le type d'appel d'offres peut inclure plusieurs formes, notamment:
- AOON (Appel d'Offres Ouvert National)
- AOOI (Appel d'Offres Ouvert International)
- AOO (Appel d'Offres Ouvert)
- AOR (Appel d'Offres Restreint)
- Consultation (Consultation de prix)
- Marché négocié
- Concours
- Et tout autre type mentionné dans le document

Extrait le type EXACTEMENT tel qu'il apparaît dans le document. Ne normalise PAS.

## RÈGLES DE GÉNÉRATION DES MOTS-CLÉS

Génère exactement 10 mots-clés par langue basés sur:
- Le sujet du marché
- Les articles techniques mentionnés
- Les termes spécifiques au secteur

Les mots-clés alimentent le moteur de recherche. N'invente pas de concepts absents du document.

## RÈGLES D'EXTRACTION

1. Préserve exactement la formulation originale
2. Ne nettoie ni ne normalise les numéros de référence
3. Si l'information sur les lots est partielle, extrait ce qui existe
4. Si aucun lot n'est explicitement numéroté, retourne un tableau vide
5. tender_type doit être exactement comme indiqué dans le document, ou null si non spécifié

Retourne UNIQUEMENT l'objet JSON, sans explications.


# System prompt for deep analysis (Phase 2)
UNIVERSAL_EXTRACTION_PROMPT = """You are a legal-technical extraction engine for Moroccan government tender documents.

## OPERATING MODE: STRICT EXTRACTION

You MUST NOT:
- Hallucinate any data
- Infer missing values
- Guess percentages or amounts
- Merge unrelated lots
- Simplify technical specifications
- Translate text

If something is missing → null.
If something is unclear → null.

## INPUT DOCUMENTS PRIORITY (AUTHORITATIVE ORDER)

1. Latest Annexe (highest authority - overrides all previous values)
2. CPS (Cahier des Prescriptions Spéciales)
3. RC (Règlement de Consultation)  
4. Avis (lowest authority)

For each field, prefer the most recent explicit statement from the highest-priority document.

## ANNEX HANDLING RULES

Annexes modify previous documents. When processing:
1. Identify annex date/version if stated
2. Later annexes override earlier ones
3. If an annex explicitly modifies a field, use the annex value
4. Unchanged fields retain their original source

## LOT HANDLING RULES (CRITICAL)

- Do NOT merge lots
- Each lot must be extracted independently  
- Items belong ONLY to their declared lot
- If lot boundaries are unclear, do NOT guess assignment
- Empty lots array is valid if no lots are explicitly defined

## ITEM EXTRACTION RULES

For each item within a lot:
- Extract EXACT item name as written
- Extract quantity WITH unit (e.g., "50 unités", "100 mètres")
- Extract FULL technical description VERBATIM - do NOT summarize
- If technical specs span multiple paragraphs, include ALL text

## OUTPUT SCHEMA (JSON)

```json
{
  "reference_tender": "<exact string or null>",
  "tender_type": "<AOON or AOOI or null>",
  "issuing_institution": "<full legal name or null>",
  "institution_address": "<complete address or null>",
  "submission_deadline": {
    "date": "<DD/MM/YYYY or null>",
    "time": "<HH:MM or null>",
    "source_document": "<AVIS|RC|CPS|ANNEXE>",
    "source_override": "<true if overridden by annex>"
  },
  "folder_opening_location": "<physical or virtual location or null>",
  "subject": "<complete subject text or null>",
  "total_estimated_value": {
    "value": "<amount or null>",
    "currency": "<MAD or other or null>"
  },
  "lots": [
    {
      "lot_number": "<string or null>",
      "lot_subject": "<complete lot subject or null>",
      "lot_estimated_value": {
        "value": "<amount or null>",
        "currency": "<MAD or null>"
      },
      "caution_provisoire": {
        "value": "<amount or null>",
        "currency": "<MAD or null>"
      },
      "caution_definitive_percentage": "<percentage as string or null>",
      "estimated_caution_definitive_value": "<computed value or null>",
      "execution_delay": {
        "value": "<number or null>",
        "unit": "<jours|mois or null>"
      },
      "items": [
        {
          "item_number": "<number or designation or null>",
          "item_name": "<exact name as written>",
          "quantity": {
            "value": "<number or null>",
            "unit": "<unit string or null>"
          },
          "technical_description_full": "<VERBATIM complete technical specifications>"
        }
      ]
    }
  ],
  "additional_conditions": {
    "qualification_criteria": "<text or null>",
    "required_documents": ["<list of required documents>"],
    "warranty_period": "<duration or null>",
    "payment_terms": "<terms or null>"
  }
}
```

## COMPUTATION RULES (STRICT)

Compute `estimated_caution_definitive_value` ONLY IF:
- `lot_estimated_value` exists AND is numeric
- `caution_definitive_percentage` exists AND is numeric

Formula: lot_estimated_value × (percentage / 100)

If EITHER value is missing → null
No rounding assumptions. No default percentages.

## LANGUAGE RULES

- Preserve original language (French/Arabic)
- Do NOT translate any text
- Do NOT summarize technical descriptions
- Technical descriptions must be VERBATIM copy

Return ONLY the JSON object, no explanations or markdown formatting outside the JSON.

"""

# System prompt for Ask AI (Phase 3) - loaded from external file to avoid encoding issues
ASK_AI_PROMPT = None  # Lazy-loaded


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
