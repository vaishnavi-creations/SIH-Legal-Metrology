/**
 * API Service for communicating with the Legal Metrology FastAPI Backend.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson && errJson.detail) {
        if (typeof errJson.detail === 'string') {
          errorDetail = errJson.detail;
        } else if (Array.isArray(errJson.detail)) {
          errorDetail = errJson.detail.map(d => `${d.loc?.join('.')}: ${d.msg}`).join(', ');
        } else {
          errorDetail = JSON.stringify(errJson.detail);
        }
      }
    } catch (e) {
      // response was not JSON
    }
    const error = new Error(errorDetail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export const apiService = {
  /**
   * Health check to test backend availability.
   */
  async checkHealth() {
    const res = await fetch(`${API_BASE}/health`, { method: 'GET' });
    return handleResponse(res);
  },

  /**
   * Run end-to-end package inspection:
   * Uploads image -> Preprocessing -> OCR -> AI Structuring -> Deterministic Rule Engine
   */
  async inspectPackageFile(file, isImported = false, commodityType = '') {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('is_imported', String(isImported));
    if (commodityType && commodityType.trim()) {
      formData.append('commodity_type', commodityType.trim());
    }

    const res = await fetch(`${API_BASE}/compliance/inspect-file`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse(res);
  },

  /**
   * Fetch paginated scan history list with optional status filter.
   */
  async getScanHistory(page = 1, pageSize = 20, status = null) {
    const params = new URLSearchParams();
    params.append('page', String(page));
    params.append('page_size', String(pageSize));
    if (status && status !== 'ALL') {
      params.append('status', status);
    }

    const res = await fetch(`${API_BASE}/history?${params.toString()}`, {
      method: 'GET',
    });
    return handleResponse(res);
  },

  /**
   * Fetch deep audit details for a specific scan by file_id.
   */
  async getScanDetail(fileId) {
    const res = await fetch(`${API_BASE}/history/${encodeURIComponent(fileId)}`, {
      method: 'GET',
    });
    return handleResponse(res);
  },

  /**
   * Delete a scan record by file_id.
   */
  async deleteScan(fileId) {
    const res = await fetch(`${API_BASE}/history/${encodeURIComponent(fileId)}`, {
      method: 'DELETE',
    });
    return handleResponse(res);
  }
};
