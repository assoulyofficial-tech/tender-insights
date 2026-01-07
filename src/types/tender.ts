// Tender AI Platform — Type Definitions (V1)
// Authoritative schemas matching backend PostgreSQL

export type TenderStatus = 'PENDING' | 'LISTED' | 'ANALYZED' | 'ERROR';
export type TenderType = 'AOON' | 'AOOI' | null;
export type DocumentType = 'AVIS' | 'RC' | 'CPS' | 'ANNEXE' | 'UNKNOWN';

// Provenance tracking for every extracted field
export interface TrackedValue<T> {
  value: T | null;
  source_document: DocumentType | 'WEBSITE' | null;
  source_date: string | null;
}

// Lot structure
export interface TenderLot {
  lot_number: string | null;
  lot_subject: string | null;
  lot_estimated_value: string | null;
  caution_provisoire: string | null;
  // Deep analysis fields (Phase 2)
  caution_definitive_percentage?: string | null;
  estimated_caution_definitive_value?: string | null;
  execution_date?: string | null;
  items?: TenderItem[];
}

// Item within a lot (Deep analysis)
export interface TenderItem {
  item_name: string | null;
  quantity: string | null;
  technical_description_full: string | null;
}

// Multilingual keywords
export interface TenderKeywords {
  keywords_fr: string[];
  keywords_eng: string[];
  keywords_ar: string[];
}

// Avis metadata schema (Phase 1 - Night Shift)
export interface AvisMetadata {
  reference_tender: TrackedValue<string>;
  tender_type: TrackedValue<TenderType>;
  issuing_institution: TrackedValue<string>;
  submission_deadline: {
    date: TrackedValue<string>;
    time: TrackedValue<string>;
  };
  folder_opening_location: TrackedValue<string>;
  subject: TrackedValue<string>;
  total_estimated_value: TrackedValue<string> & { currency?: string | null };
  lots: TenderLot[];
  keywords: TenderKeywords;
}

// Universal fields schema (Phase 2 - User Shift)
export interface UniversalMetadata extends AvisMetadata {
  institution_address: TrackedValue<string>;
  lots: (TenderLot & {
    items: TenderItem[];
  })[];
}

// Document extracted from tender
export interface TenderDocument {
  id: string;
  tender_id: string;
  document_type: DocumentType;
  filename: string;
  raw_text: string | null;
  page_count: number | null;
  extraction_method: 'DIGITAL' | 'OCR';
  extracted_at: string;
}

// Main Tender record
export interface Tender {
  id: string;
  external_reference: string;
  source_url: string;
  status: TenderStatus;
  
  // Scraped at download time
  scraped_at: string;
  download_date: string;
  
  // Avis metadata (Phase 1)
  avis_metadata: AvisMetadata | null;
  
  // Universal metadata (Phase 2 - on demand)
  universal_metadata: UniversalMetadata | null;
  
  // Related documents
  documents?: TenderDocument[];
  
  // Timestamps
  created_at: string;
  updated_at: string;
}

// API Response types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

// Scraper log entry
export interface ScraperLogEntry {
  level: 'info' | 'success' | 'warning' | 'error';
  message: string;
  timestamp?: string;
}

// Scraper stats
export interface ScraperStats {
  total: number;
  downloaded: number;
  failed: number;
  elapsed: number;
}

// Scraper status
export interface ScraperStatus {
  is_running: boolean;
  current_phase: string;
  total_tenders: number;
  downloaded: number;
  failed: number;
  elapsed_seconds: number;
  last_run: string | null;
  logs?: ScraperLogEntry[];
  stats?: ScraperStats;
}

// Search/filter params
export interface TenderSearchParams {
  query?: string;
  status?: TenderStatus;
  date_from?: string;
  date_to?: string;
  page?: number;
  per_page?: number;
}
