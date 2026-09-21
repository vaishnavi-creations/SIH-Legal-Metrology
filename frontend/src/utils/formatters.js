/**
 * Utilities for formatting dates, currency, and file sizes.
 */

const STATIC_BASE = import.meta.env.VITE_BACKEND_STATIC_URL || 'http://localhost:8000';

export function formatDate(isoString) {
  if (!isoString) return 'N/A';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (e) {
    return isoString;
  }
}

export function formatCurrency(amount, currency = 'INR') {
  if (amount === null || amount === undefined) return 'N/A';
  try {
    if (currency === 'INR') {
      return `₹${Number(amount).toFixed(2)}`;
    }
    return `${currency} ${Number(amount).toFixed(2)}`;
  } catch (e) {
    return `${amount}`;
  }
}

export function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

export function getFullImageUrl(urlPath) {
  if (!urlPath) return null;
  if (urlPath.startsWith('http://') || urlPath.startsWith('https://')) {
    return urlPath;
  }
  const cleanPath = urlPath.startsWith('/') ? urlPath : `/${urlPath}`;
  return `${STATIC_BASE}${cleanPath}`;
}
