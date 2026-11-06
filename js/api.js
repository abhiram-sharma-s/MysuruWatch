/**
 * Mysuru RoadWatch — Central API Client
 * Communicates with FastAPI backend endpoints using standard fetch().
 */

const API_CONFIG = {
  // Use current host or default to local FastAPI port 8000
  BASE_URL: (window.location.protocol.startsWith('http')) 
    ? `${window.location.origin}/api` 
    : 'http://localhost:8000/api',
  TIMEOUT_MS: 15000
};

class RoadWatchAPI {
  constructor(baseUrl = API_CONFIG.BASE_URL) {
    this.baseUrl = baseUrl;
  }

  async _request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const errData = await response.json();
          if (errData && errData.detail) errorDetail = errData.detail;
        } catch (_) {}
        throw new Error(errorDetail);
      }
      return await response.json();
    } catch (err) {
      console.warn(`[API Error on ${endpoint}]`, err);
      throw err;
    }
  }

  /**
   * Health check to test backend connection
   */
  async checkHealth() {
    return this._request('/health');
  }

  /**
   * Detect road condition with YOLO & OpenCV
   * Accepts FormData (with file or base64) or JSON object
   */
  async detectRoadDamage(payload) {
    if (payload instanceof FormData) {
      return this._request('/detect', {
        method: 'POST',
        body: payload
      });
    } else {
      return this._request('/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    }
  }

  /**
   * Submit a new road condition report
   */
  async createReport(payload) {
    if (payload instanceof FormData) {
      return this._request('/reports', {
        method: 'POST',
        body: payload
      });
    } else {
      return this._request('/reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    }
  }

  /**
   * Retrieve all reports with optional filters
   */
  async getReports({ status = '', severity = '', search = '', since = '', start_date = '', end_date = '' } = {}) {
    const params = new URLSearchParams();
    if (status && status !== 'all') params.append('status', status);
    if (severity && severity !== 'all') params.append('severity', severity);
    if (search) params.append('search', search);
    if (since) params.append('since', since);
    if (start_date) params.append('start_date', start_date);
    if (end_date) params.append('end_date', end_date);

    const query = params.toString() ? `?${params.toString()}` : '';
    return this._request(`/reports${query}`);
  }

  /**
   * Get direct CSV export download URL
   */
  getCsvExportUrl({ start_date = '', end_date = '', status = '', severity = '', search = '' } = {}) {
    const params = new URLSearchParams();
    if (start_date) params.append('start_date', start_date);
    if (end_date) params.append('end_date', end_date);
    if (status && status !== 'all') params.append('status', status);
    if (severity && severity !== 'all') params.append('severity', severity);
    if (search) params.append('search', search);
    const query = params.toString() ? `?${params.toString()}` : '';
    return `${this.baseUrl}/reports/export/csv${query}`;
  }

  /**
   * Retrieve reports submitted since a specific ISO timestamp
   */
  async getNewReportsSince(sinceIso = '') {
    const query = sinceIso ? `?since=${encodeURIComponent(sinceIso)}` : '';
    return this._request(`/reports/new-since-login${query}`);
  }

  /**
   * Retrieve a single report by ID (e.g., RW-001)
   */
  async getReportById(reportId) {
    return this._request(`/reports/${encodeURIComponent(reportId)}`);
  }

  /**
   * Update report status (New, Verified, In Progress, Resolved)
   */
  async updateReportStatus(reportId, newStatus, notes = '') {
    return this._request(`/reports/${encodeURIComponent(reportId)}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus, notes: notes })
    });
  }
}

// Global API singleton
window.roadWatchApi = new RoadWatchAPI();

