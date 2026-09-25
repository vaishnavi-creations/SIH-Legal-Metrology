import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import { ComplianceBadge } from './ComplianceBadge';
import { ConfirmModal } from './ConfirmModal';
import { HistoryDetailModal } from './HistoryDetailModal';
import { formatDate, formatCurrency, getFullImageUrl } from '../utils/formatters';
import {
  History,
  Search,
  Filter,
  Trash2,
  Eye,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  AlertCircle,
  Package,
  Calendar,
  IndianRupee,
  Scale,
  ShieldCheck,
  Layers,
  AlertTriangle
} from 'lucide-react';

const PAGE_SIZE = 10;
const STATUS_FILTERS = ['ALL', 'COMPLIANT', 'NON_COMPLIANT', 'NOT_APPLICABLE', 'INSUFFICIENT_DATA'];

export function HistoryList() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Selected item for detail modal
  const [selectedFileId, setSelectedFileId] = useState(null);

  // Item pending deletion
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchHistory = (targetPage = page, targetStatus = statusFilter) => {
    setLoading(true);
    setError(null);

    const statusParam = targetStatus === 'ALL' ? null : targetStatus;
    apiService.getScanHistory(targetPage, PAGE_SIZE, statusParam)
      .then((data) => {
        setItems(data.items || []);
        setTotal(data.total || 0);
        setPage(data.page || 1);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load inspection history.');
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchHistory(page, statusFilter);
  }, [page, statusFilter]);

  const handleFilterChange = (filter) => {
    setStatusFilter(filter);
    setPage(1);
  };

  const handleDeleteConfirm = () => {
    if (!deleteTarget) return;

    setIsDeleting(true);
    apiService.deleteScan(deleteTarget.file_id)
      .then(() => {
        setIsDeleting(false);
        setDeleteTarget(null);
        fetchHistory(page, statusFilter);
      })
      .catch((err) => {
        setIsDeleting(false);
        alert(`Failed to delete record: ${err.message}`);
      });
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const filteredItems = items.filter((item) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      (item.product_name && item.product_name.toLowerCase().includes(q)) ||
      (item.original_filename && item.original_filename.toLowerCase().includes(q)) ||
      (item.file_id && item.file_id.toLowerCase().includes(q))
    );
  });

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-6">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <History size={18} />
            </div>
            <h2 className="text-xl sm:text-2xl font-extrabold text-navy-900 tracking-tight">
              Inspection Audit History
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Permanent statutory audit records stored with full bounding boxes and decision rationale.
          </p>
        </div>

        <button
          onClick={() => fetchHistory(page, statusFilter)}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white border border-slate-200 text-xs font-bold text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs self-start md:self-auto cursor-pointer"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin text-emerald-600' : ''} />
          <span>Refresh Records</span>
        </button>
      </div>

      {/* Filter Tabs & Search Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 sm:p-5 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        
        {/* Status Filter Buttons */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs font-bold text-slate-500 mr-1 flex items-center gap-1">
            <Filter size={13} />
            Filter:
          </span>
          {STATUS_FILTERS.map((f) => {
            const isActive = statusFilter === f;
            return (
              <button
                key={f}
                onClick={() => handleFilterChange(f)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all duration-150 cursor-pointer ${
                  isActive
                    ? 'bg-navy-900 text-white shadow-xs'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-navy-900'
                }`}
              >
                {f.replace('_', ' ')}
              </button>
            );
          })}
        </div>

        {/* Search Input */}
        <div className="flex items-center gap-3">
          <div className="relative w-full sm:w-60">
            <Search size={14} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search product or file..."
              className="w-full pl-8 pr-3 py-1.5 rounded-xl border border-slate-200 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-emerald-500 bg-slate-50/50"
            />
          </div>

          <div className="text-xs font-semibold text-slate-500 whitespace-nowrap hidden lg:block">
            Showing <span className="font-bold text-navy-900">{filteredItems.length}</span> of <span className="font-bold text-navy-900">{total}</span>
          </div>
        </div>

      </div>

      {/* Error Notice */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs sm:text-sm flex items-center gap-3 shadow-2xs">
          <AlertCircle size={18} className="text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Table Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-16 text-center text-slate-500 text-sm font-medium space-y-2">
            <RefreshCw size={28} className="mx-auto text-emerald-600 animate-spin" />
            <p className="font-bold text-navy-900">Loading audit records...</p>
            <p className="text-xs text-slate-400">Connecting to SQLite persistence database</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="p-16 text-center text-slate-500 space-y-3">
            <Package size={40} className="mx-auto text-slate-300" />
            <h3 className="text-base font-bold text-navy-900">No Scan Records Found</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto leading-relaxed">
              {statusFilter !== 'ALL'
                ? `No inspection sessions currently match "${statusFilter}". Try switching to ALL.`
                : 'No inspection sessions have been stored yet. Launch a New Inspection to audit your first package.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs sm:text-sm">
              <thead className="bg-slate-50/80 text-slate-600 font-bold border-b border-slate-200 text-[11px] uppercase tracking-wider">
                <tr>
                  <th className="py-3.5 px-4 sm:px-6">Product / File</th>
                  <th className="py-3.5 px-4">Scanned At</th>
                  <th className="py-3.5 px-4">MRP</th>
                  <th className="py-3.5 px-4">Net Quantity</th>
                  <th className="py-3.5 px-4">Compliance</th>
                  <th className="py-3.5 px-4">Violations</th>
                  <th className="py-3.5 px-4 sm:px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredItems.map((item) => {
                  const thumbUrl = item.image_url ? getFullImageUrl(item.image_url) : null;

                  return (
                    <tr key={item.file_id} className="hover:bg-slate-50/70 transition-colors">
                      
                      {/* Product Name & Thumbnail */}
                      <td className="py-3.5 px-4 sm:px-6">
                        <div className="flex items-center gap-3">
                          {thumbUrl ? (
                            <img
                              src={thumbUrl}
                              alt="Thumbnail"
                              className="w-11 h-11 rounded-lg object-cover border border-slate-200 shrink-0 bg-slate-100"
                              onError={(e) => {
                                e.target.onerror = null;
                                e.target.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40"><rect fill="%23071A2B" width="40" height="40"/><text fill="%2394a3b8" x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-size="8">IMG</text></svg>';
                              }}
                            />
                          ) : (
                            <div className="w-11 h-11 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-400 shrink-0">
                              <Package size={18} />
                            </div>
                          )}

                          <div className="min-w-0 max-w-xs">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="font-bold text-navy-900 truncate" title={item.product_name || item.original_filename}>
                                {item.product_name || 'Unnamed Package'}
                              </span>
                              {item.inspection_type === 'multi' && (
                                <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-200 shrink-0">
                                  <Layers size={10} className="text-blue-500" />
                                  {item.image_count || 1} {item.image_count === 1 ? 'view' : 'views'}
                                </span>
                              )}
                              {item.is_conflicted && (
                                <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-300 shrink-0" title="Cross-image declaration conflict detected">
                                  <AlertTriangle size={10} className="text-amber-600" />
                                  Conflict
                                </span>
                              )}
                            </div>
                            <div className="text-[11px] text-slate-500 font-mono truncate mt-0.5 flex items-center gap-1.5" title={item.file_id}>
                              <span>{item.original_filename || item.file_id}</span>
                              {item.inspection_type === 'multi' && item.image_roles && item.image_roles.length > 0 && (
                                <span className="text-[10px] text-slate-400 font-sans truncate">
                                  • {item.image_roles.join(', ')}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Upload Date */}
                      <td className="py-3.5 px-4 text-slate-600 whitespace-nowrap text-xs">
                        {formatDate(item.uploaded_at)}
                      </td>

                      {/* MRP */}
                      <td className="py-3.5 px-4 text-navy-900 font-bold whitespace-nowrap">
                        {item.mrp !== null && item.mrp !== undefined ? formatCurrency(item.mrp) : '—'}
                      </td>

                      {/* Net Qty */}
                      <td className="py-3.5 px-4 text-slate-700 whitespace-nowrap font-medium">
                        {item.net_quantity || '—'}
                      </td>

                      {/* Compliance Status */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <ComplianceBadge status={item.compliance_status} size="small" />
                      </td>

                      {/* Violations / Warnings Count */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="flex items-center gap-1.5 text-xs">
                          <span className={`font-mono font-bold px-2 py-0.5 rounded ${
                            item.violations_count > 0 ? 'bg-rose-100 text-rose-800' : 'bg-slate-100 text-slate-600'
                          }`}>
                            {item.violations_count} viol.
                          </span>
                          <span className="font-medium text-slate-300">/</span>
                          <span className="text-slate-500 font-mono text-[11px]">
                            {item.warnings_count} warn.
                          </span>
                        </div>
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-4 sm:px-6 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => setSelectedFileId(item.file_id)}
                            className="p-2 text-slate-600 hover:text-emerald-700 hover:bg-emerald-50 rounded-lg transition-colors cursor-pointer"
                            title="View Full Audit Details"
                          >
                            <Eye size={16} />
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeleteTarget(item)}
                            className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                            title="Delete Record"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </td>

                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        {total > 0 && (
          <div className="bg-slate-50/80 px-6 py-4 border-t border-slate-200 flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">
              Page <span className="font-bold text-navy-900">{page}</span> of{' '}
              <span className="font-bold text-navy-900">{totalPages}</span>
            </span>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1 || loading}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-bold text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed shadow-2xs cursor-pointer"
              >
                <ChevronLeft size={14} />
                <span>Prev</span>
              </button>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages || loading}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-bold text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed shadow-2xs cursor-pointer"
              >
                <span>Next</span>
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Deep Inspection Detail Modal */}
      <HistoryDetailModal
        fileId={selectedFileId}
        isOpen={Boolean(selectedFileId)}
        onClose={() => setSelectedFileId(null)}
      />

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={Boolean(deleteTarget)}
        title="Delete Inspection Record?"
        message={`Are you sure you want to permanently delete the audit record for "${deleteTarget?.product_name || deleteTarget?.original_filename || deleteTarget?.file_id}"?`}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
        isDeleting={isDeleting}
      />

    </div>
  );
}
