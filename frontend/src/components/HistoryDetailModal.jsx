import React, { useEffect, useState } from 'react';
import { apiService } from '../services/api';
import { ComplianceBadge } from './ComplianceBadge';
import { ProductAttributes } from './ProductAttributes';
import { RuleCheckCard } from './RuleCheckCard';
import { getFullImageUrl, formatDate } from '../utils/formatters';
import { X, Loader2, AlertCircle, FileText, Scale, Eye, AlertOctagon, AlertTriangle } from 'lucide-react';

export function HistoryDetailModal({ fileId, isOpen, onClose }) {
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('checklist'); // 'checklist' | 'ocr'

  useEffect(() => {
    if (!isOpen || !fileId) return;

    setLoading(true);
    setError(null);

    apiService.getScanDetail(fileId)
      .then((data) => {
        setDetail(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to retrieve scan record.');
        setLoading(false);
      });
  }, [fileId, isOpen]);

  if (!isOpen) return null;

  const report = detail?.compliance_report || {};
  const structured = detail?.structured_data || {};
  const checks = report?.checks || [];
  const violations = report?.violations || [];
  const warnings = report?.warnings || [];

  const imageUrl = detail?.image_url ? getFullImageUrl(detail.image_url) : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-navy-950/70 backdrop-blur-xs overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full border border-slate-200 overflow-hidden my-auto max-h-[92vh] flex flex-col">
        
        {/* Header */}
        <div className="px-6 py-4 bg-navy-950 text-white flex items-center justify-between shrink-0 border-b border-navy-800">
          <div className="flex items-center gap-2.5">
            <Scale size={20} className="text-emerald-400" />
            <div>
              <h3 className="font-bold text-sm sm:text-base">
                Inspection Audit Trail
              </h3>
              <p className="text-[11px] text-slate-400 font-mono">
                {fileId} • {detail?.uploaded_at ? formatDate(detail.uploaded_at) : ''}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-navy-800 transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {loading ? (
            <div className="py-16 text-center">
              <Loader2 size={32} className="mx-auto text-emerald-600 animate-spin mb-2" />
              <p className="text-xs text-slate-500 font-medium">Fetching inspection audit record...</p>
            </div>
          ) : error ? (
            <div className="p-4 rounded-lg bg-red-50 border border-red-200 text-red-800 text-sm flex items-center gap-3">
              <AlertCircle size={20} className="text-red-500 shrink-0" />
              <span>{error}</span>
            </div>
          ) : detail ? (
            <>
              {/* Verdict Summary Card */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2.5">
                    <ComplianceBadge status={detail.compliance_status} size="normal" />
                    <span className="text-xs font-semibold text-slate-500">
                      File: {detail.original_filename || 'package.jpg'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-700 mt-2 font-medium">
                    {detail.summary || report?.summary || 'Statutory evaluation completed.'}
                  </p>
                </div>

                <div className="flex gap-2 shrink-0">
                  <span className="px-2.5 py-1 rounded bg-white text-xs font-bold text-emerald-700 border border-emerald-200 shadow-2xs">
                    {report?.rules_passed ?? (detail.compliance_status === 'COMPLIANT' ? 8 : 6)} Passed
                  </span>
                  <span className="px-2.5 py-1 rounded bg-white text-xs font-bold text-red-700 border border-red-200 shadow-2xs">
                    {detail.violations_count ?? violations.length} Violations
                  </span>
                </div>
              </div>

              {/* Image & Extracted Attributes Grid */}
              <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
                
                {/* Photo */}
                {imageUrl && (
                  <div className="md:col-span-5 bg-slate-900 rounded-lg p-2 border border-slate-200 flex items-center justify-center max-h-64 overflow-hidden">
                    <img
                      src={imageUrl}
                      alt="Preprocessed Package"
                      className="max-h-60 w-auto object-contain rounded"
                    />
                  </div>
                )}

                {/* Structured Attributes */}
                <div className={imageUrl ? "md:col-span-7" : "md:col-span-12"}>
                  <ProductAttributes data={structured} />
                </div>

              </div>

              {/* Violations / Warnings Banner if present */}
              {violations.length > 0 && (
                <div className="p-4 rounded-xl bg-red-50/80 border border-red-200 space-y-2">
                  <h4 className="text-xs font-bold text-red-900 flex items-center gap-1.5 uppercase tracking-wider">
                    <AlertOctagon size={14} className="text-red-600" />
                    Statutory Violations ({violations.length})
                  </h4>
                  <div className="divide-y divide-red-100 text-xs text-red-900">
                    {violations.map((v, i) => (
                      <div key={i} className={i > 0 ? "pt-2 mt-2" : ""}>
                        <span className="font-mono font-bold mr-2 text-red-800">{v.rule_id}</span>
                        <span className="font-semibold text-slate-700 mr-2">[{v.legal_reference}]</span>
                        <span>{v.message}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tabs: Itemized Rules vs OCR Text */}
              <div className="border border-slate-200 rounded-xl overflow-hidden shadow-2xs">
                <div className="px-4 py-2 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                  <div className="flex space-x-2">
                    <button
                      onClick={() => setActiveTab('checklist')}
                      className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-colors cursor-pointer ${
                        activeTab === 'checklist'
                          ? 'bg-navy-900 text-white shadow-2xs'
                          : 'text-slate-600 hover:bg-slate-200/60'
                      }`}
                    >
                      Statutory Rule Checklist ({checks.length})
                    </button>
                    <button
                      onClick={() => setActiveTab('ocr')}
                      className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-colors cursor-pointer ${
                        activeTab === 'ocr'
                          ? 'bg-navy-900 text-white shadow-2xs'
                          : 'text-slate-600 hover:bg-slate-200/60'
                      }`}
                    >
                      Raw OCR Text
                    </button>
                  </div>
                </div>

                <div className="p-4">
                  {activeTab === 'checklist' ? (
                    <div className="space-y-2">
                      {checks.length === 0 ? (
                        <p className="text-xs text-slate-400 italic py-3 text-center">
                          No itemized rule results stored.
                        </p>
                      ) : (
                        checks.map((check, idx) => (
                          <RuleCheckCard key={idx} check={check} />
                        ))
                      )}
                    </div>
                  ) : (
                    <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 font-mono text-xs text-slate-800 whitespace-pre-wrap max-h-72 overflow-y-auto">
                      {detail.ocr_text || 'No text extracted.'}
                    </div>
                  )}
                </div>

              </div>

            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="bg-slate-50 px-6 py-3 border-t border-slate-200 flex justify-end shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs sm:text-sm font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-100 transition-colors"
          >
            Close Audit Trail
          </button>
        </div>

      </div>
    </div>
  );
}
