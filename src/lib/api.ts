// Tender AI Platform — API Client
// Connects React frontend to Python FastAPI backend

import type { 
  Tender, 
  ScraperStatus, 
  ApiResponse, 
  PaginatedResponse,
  TenderSearchParams 
} from '@/types/tender';

// Backend URL - configure this for your local setup
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class TenderApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string, 
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.detail || data.message || `HTTP ${response.status}`,
        };
      }

      return { success: true, data };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Network error';
      console.error(`API Error [${endpoint}]:`, message);
      return { success: false, error: message };
    }
  }

  // ============================
  // SCRAPER ENDPOINTS
  // ============================

  /**
   * Trigger manual scraper run with date range
   * @param startDate - Start date (YYYY-MM-DD), defaults to yesterday
   * @param endDate - End date (YYYY-MM-DD), defaults to startDate
   */
  async triggerScraper(startDate?: string, endDate?: string): Promise<ApiResponse<{ job_id: string; date_range: string }>> {
    return this.request('/api/scraper/run', {
      method: 'POST',
      body: JSON.stringify({ start_date: startDate, end_date: endDate }),
    });
  }

  /**
   * Get current scraper status
   */
  async getScraperStatus(): Promise<ApiResponse<ScraperStatus>> {
    return this.request('/api/scraper/status');
  }

  /**
   * Stop running scraper
   */
  async stopScraper(): Promise<ApiResponse<{ stopped: boolean }>> {
    return this.request('/api/scraper/stop', { method: 'POST' });
  }

  // ============================
  // TENDER ENDPOINTS
  // ============================

  /**
   * List tenders with optional filters
   */
  async listTenders(params: TenderSearchParams = {}): Promise<ApiResponse<PaginatedResponse<Tender>>> {
    const queryParams = new URLSearchParams();
    if (params.query) queryParams.set('q', params.query);
    if (params.status) queryParams.set('status', params.status);
    if (params.date_from) queryParams.set('date_from', params.date_from);
    if (params.date_to) queryParams.set('date_to', params.date_to);
    if (params.page) queryParams.set('page', String(params.page));
    if (params.per_page) queryParams.set('per_page', String(params.per_page));

    const query = queryParams.toString();
    return this.request(`/api/tenders${query ? `?${query}` : ''}`);
  }

  /**
   * Get single tender by ID
   */
  async getTender(id: string): Promise<ApiResponse<Tender>> {
    return this.request(`/api/tenders/${id}`);
  }

  /**
   * Trigger deep analysis for a tender (Phase 2)
   */
  async analyzeTender(id: string): Promise<ApiResponse<Tender>> {
    return this.request(`/api/tenders/${id}/analyze`, { method: 'POST' });
  }

  // ============================
  // ASK AI ENDPOINT (Phase 3)
  // ============================

  /**
   * Ask AI about a specific tender
   */
  async askAI(tenderId: string, question: string): Promise<ApiResponse<{
    answer: string;
    citations: { document: string; page?: number }[];
  }>> {
    return this.request(`/api/tenders/${tenderId}/ask`, {
      method: 'POST',
      body: JSON.stringify({ question }),
    });
  }

  // ============================
  // HEALTH CHECK
  // ============================

  async healthCheck(): Promise<ApiResponse<{ status: string; version: string }>> {
    return this.request('/health');
  }
}

// Singleton instance
export const api = new TenderApiClient();

// Export for custom configuration
export { TenderApiClient };
