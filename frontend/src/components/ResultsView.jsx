import React, { useState } from 'react';
import { ComplianceBadge } from './ComplianceBadge';
import { ProductAttributes } from './ProductAttributes';
import { RuleCheckCard } from './RuleCheckCard';
import { getFullImageUrl } from '../utils/formatters';
import {
  ArrowLeft,
  AlertOctagon,
  AlertTriangle,
  Eye,
  FileText,
  ShieldCheck,
  Maximize2,
  X,
  Search,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Clock,
  Layers
} from 'lucide-react';

const ROLE_NAMES = {
  front: 'Front View',
  back: 'Back View',
  left: 'Left Side',
  right: 'Right Side',
  top: 'Top View',
  bottom: 'Bottom View',
  label: 'Label Panel',
  other: 'Package Face',
};

function formatRole(role) {
  if (!role) return null;
  return ROLE_NAMES[role.toLowerCase()] || `${role.charAt(0).toUpperCase() + role.slice(1)} View`;
}

function formatConflictValue(val) {
  if (val === null || val === undefined) return '';
  if (typeof val === 'number') {
    return String(val);
  }
  if (typeof val === 'string') {
    return val;
  }
  if (typeof val === 'object') {
    if (val.value !== undefined) {
      if (val.currency === 'INR' || val.currency === undefined) {
        return val.unit ? `${val.value} ${val.unit}` : `₹${val.value}`;
      }
      return `${val.currency} ${val.value}`;
    }
    if (val.name) return val.name;
    if (val.raw_text) return val.raw_text;
    try {
      return JSON.stringify(val);
    } catch {
      return String(val);
    }
  }
  return String(val);
}

export function ResultsView({ result, onBackToScan }) {
  const [showImageModal, setShowImageModal] = useState(false);
  const [ocrSearch, setOcrSearch] = useState('');
  const [copied, setCopied] = useState(false);
  const [isOcrExpanded, setIsOcrExpanded] = useState(true);

  if (!result) return null;

  const report = result.compliance_report || {};
  const structured = result.structured_data || {};
  const ocr = result.ocr_result || {};
  const status = report.compliance_status || 'INSUFFICIENT_DATA';

  const processedImagePath = `/uploads/processed/${result.file_id}_preprocessed.png`;
  const fullImageUrl = getFullImageUrl(processedImagePath);

  const violations = report.violations || [];
  const warnings = report.warnings || [];
  const checks = report.checks || [];
  const missing = report.missing_declarations || [];
  const exemptions = report.exemptions_applied || [];

  const passedCount = report.rules_passed ?? checks.filter(c => c.status === 'PASS').length;
  const failedCount = report.rules_failed ?? violations.length;
  const warningCount = warnings.length;

  const productName = structured.product_name || structured.common_or_generic_name || 'Packaged Commodity';

  return (
    <div className="max-w-7xl mx-auto py-8 sm:py-10 px-4 sm:px-6 lg:px-8 space-y-8">
      
      {/* Top Bar with Return Action & Session Meta */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBackToScan}
          className="inline-flex items-center gap-2 text-xs sm:text-sm font-bold text-slate-700 hover:text-navy-950 px-4 py-2 rounded-xl bg-white border border-slate-200 shadow-2xs hover:bg-slate-50 transition-colors cursor-pointer"
        >
          <ArrowLeft size={16} />
          <span>Scan Another Package</span>
        </button>

        <div className="flex items-center gap-2 text-[11px] text-slate-500 font-mono">
          <Clock size={12} className="text-slate-400" />
          <span>Session:</span>
          <span className="font-bold text-slate-700">{result.file_id ? result.file_id.slice(0, 16) : 'Current'}</span>
        </div>
      </div>

      {/* Report Header */}
      <div className="space-y-1">
        <h1 className="text-2xl sm:text-3xl font-extrabold text-navy-950 tracking-tight">
          Inspection Report
        </h1>
        <p className="text-xs sm:text-sm text-slate-500">
          Legal Metrology compliance assessment
        </p>
      </div>

      {/* Executive Summary Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8 space-y-6">
        
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 pb-6 border-b border-slate-100">
          
          {/* Status & Hierarchy */}
          <div className="space-y-3">
            <div>
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 block">
                COMPLIANCE STATUS
              </span>
              <div className="mt-1.5 flex items-center gap-3">
                <ComplianceBadge status={status} size="large" />
              </div>
            </div>

            <div className="text-xs sm:text-sm font-bold text-slate-800">
              <span className={failedCount > 0 ? "text-rose-700" : "text-slate-600"}>
                {failedCount} Failed
              </span>
              {' · '}
              <span className="text-emerald-700">
                {passedCount} Passed
              </span>
              {warningCount > 0 && (
                <>
                  {' · '}
                  <span className="text-amber-700">
                    {warningCount} {warningCount === 1 ? 'Warning' : 'Warnings'}
                  </span>
                </>
              )}
            </div>

            <p className="text-xs sm:text-sm text-slate-600 max-w-2xl leading-relaxed">
              {report.summary || 'Statutory evaluation completed against Chapter II declarations under the Legal Metrology (Packaged Commodities) Rules, 2011.'}
            </p>
          </div>

          {/* Product Summary Tag */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 min-w-[240px] space-y-1">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 block">
              INSPECTED COMMODITY
            </span>
            <div className="text-sm font-bold text-navy-950 break-words" title={productName}>
              {productName}
            </div>
            <div className="text-[11px] text-slate-500 font-mono pt-1">
              Rules Evaluated: <span className="font-bold text-navy-900">{checks.length}</span>
            </div>
          </div>

        </div>

        {/* Key Package Attributes at a Glance */}
        <div className="space-y-2">
          <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 block">
            KEY PACKAGE ATTRIBUTES AT A GLANCE
          </span>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
            <div className="p-2.5 rounded-xl bg-slate-50/80 border border-slate-200/70">
              <span className="text-[10px] font-bold text-slate-500 uppercase block">Product</span>
              <span className="font-bold text-navy-950 truncate block mt-0.5" title={productName}>
                {productName}
              </span>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-50/80 border border-slate-200/70">
              <span className="text-[10px] font-bold text-slate-500 uppercase block">Net Quantity</span>
              <span className="font-bold text-navy-950 truncate block mt-0.5">
                {structured.net_quantity?.value ? `${structured.net_quantity.value} ${structured.net_quantity.unit || ''}` : '—'}
              </span>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-50/80 border border-slate-200/70">
              <span className="text-[10px] font-bold text-slate-500 uppercase block">MRP (Taxes Incl.)</span>
              <span className="font-bold text-emerald-800 truncate block mt-0.5">
                {structured.mrp?.value !== undefined && structured.mrp?.value !== null ? `₹${structured.mrp.value}` : '—'}
              </span>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-50/80 border border-slate-200/70">
              <span className="text-[10px] font-bold text-slate-500 uppercase block">Unit Sale Price</span>
              <span className="font-bold text-navy-950 truncate block mt-0.5">
                {structured.unit_sale_price?.value ? `₹${structured.unit_sale_price.value}/${structured.unit_sale_price.unit || ''}` : (structured.mrp?.unit_sale_price || '—')}
              </span>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-50/80 border border-slate-200/70">
              <span className="text-[10px] font-bold text-slate-500 uppercase block">Manufacturer</span>
              <span className="font-bold text-navy-950 truncate block mt-0.5" title={structured.manufacturer?.name}>
                {structured.manufacturer?.name || '—'}
              </span>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-50/80 border border-slate-200/70">
              <span className="text-[10px] font-bold text-slate-500 uppercase block">Dates</span>
              <span className="font-bold text-navy-950 truncate block mt-0.5" title={[structured.dates?.manufacturing_date, structured.dates?.packaging_date, structured.dates?.expiry_date].filter(Boolean).join(', ')}>
                {[structured.dates?.manufacturing_date, structured.dates?.packaging_date].filter(Boolean).join('/') || structured.dates?.expiry_date || '—'}
              </span>
            </div>
          </div>
        </div>

        {/* Missing Declarations Alert */}
        {missing.length > 0 && (
          <div className="p-3.5 rounded-xl bg-rose-50/80 border border-rose-200 flex items-start gap-2.5 text-xs text-rose-900">
            <AlertOctagon size={16} className="text-rose-600 mt-0.5 shrink-0" />
            <div>
              <span className="font-bold">Missing Statutory Declarations:</span>{' '}
              {missing.map((m, i) => (
                <span key={i} className="inline-block font-mono font-bold text-rose-900 bg-white px-2 py-0.5 rounded border border-rose-200 ml-1.5 mt-0.5">
                  {m}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Statutory Exemptions */}
        {exemptions.length > 0 && (
          <div className="p-3.5 rounded-xl bg-blue-50 border border-blue-200 flex items-start gap-2.5 text-xs text-blue-900">
            <ShieldCheck size={16} className="text-blue-600 mt-0.5 shrink-0" />
            <div>
              <span className="font-bold">Statutory Exemption Applied:</span>{' '}
              {exemptions.join('; ')}
            </div>
          </div>
        )}

        {/* Cross-Image Declaration Conflicts Alert */}
        {(result.is_conflicted || (result.conflicts && result.conflicts.length > 0)) && (
          <div className="p-4 rounded-xl bg-amber-50/90 border border-amber-300 text-amber-950 space-y-3">
            <div className="flex items-center gap-2">
              <AlertTriangle size={18} className="text-amber-600 shrink-0" />
              <h4 className="text-xs sm:text-sm font-bold text-amber-950 uppercase tracking-wide">
                Cross-Image Declaration Conflict{result.conflicts?.length > 1 ? 's' : ''}
              </h4>
              <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800 bg-amber-100 border border-amber-300 px-2 py-0.5 rounded ml-auto">
                Evidence Mismatch
              </span>
            </div>
            <p className="text-xs text-amber-900 leading-relaxed">
              Contradictory statutory declarations were detected across different package face views:
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              {(result.conflicts || []).map((conflict, cIdx) => (
                <div key={cIdx} className="p-3 rounded-lg bg-white border border-amber-200/90 shadow-2xs space-y-2">
                  <div className="flex items-center justify-between border-b border-amber-100 pb-1.5">
                    <span className="text-xs font-bold font-mono uppercase text-navy-950">
                      {conflict.field_name ? conflict.field_name.replace(/_/g, ' ') : 'Declaration'}
                    </span>
                    <span className="text-[10px] font-mono text-amber-800 bg-amber-50 px-1.5 py-0.5 rounded">
                      {conflict.conflict_type || 'VALUE_MISMATCH'}
                    </span>
                  </div>

                  <div className="space-y-1.5">
                    {/* Render each source with its role and detected text/value */}
                    {conflict.sources && conflict.sources.length > 0 ? (
                      conflict.sources.map((src, sIdx) => {
                        const valDisplay = formatConflictValue(src.extracted_value) || src.source_text || '—';
                        const roleDisplay = formatRole(src.source_role);
                        return (
                          <div key={sIdx} className="flex items-center justify-between text-xs gap-2">
                            <span className="text-navy-900 font-bold truncate">
                              {valDisplay}
                            </span>
                            {roleDisplay && (
                              <span className="text-[10px] font-mono font-bold text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded shrink-0">
                                {roleDisplay}
                              </span>
                            )}
                          </div>
                        );
                      })
                    ) : (
                      (conflict.competing_values || []).map((val, vIdx) => (
                        <div key={vIdx} className="text-xs font-bold text-navy-900">
                          {formatConflictValue(val)}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>

      {/* Main Grid: Left = Product Info & Label, Right = Statutory Compliance Checks */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        {/* Left Column (5 Cols): Preprocessed Label + Extracted Product Declarations */}
        <div className="lg:col-span-5 space-y-6">
          
          {/* Label Image Card */}
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
            <div className="px-5 py-3.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <span className="text-xs font-bold text-navy-900 flex items-center gap-1.5">
                <Eye size={14} className="text-emerald-600" />
                <span>Preprocessed Package Label</span>
              </span>
              <button
                type="button"
                onClick={() => setShowImageModal(true)}
                className="text-xs text-emerald-600 hover:text-emerald-800 font-semibold flex items-center gap-1 cursor-pointer"
              >
                <Maximize2 size={12} />
                <span>Zoom</span>
              </button>
            </div>

            <div className="p-4 bg-navy-950 flex items-center justify-center">
              <img
                src={fullImageUrl}
                alt="Preprocessed Package"
                onClick={() => setShowImageModal(true)}
                className="max-h-72 w-auto object-contain rounded-lg cursor-pointer hover:opacity-95 transition-opacity"
                title="Click to zoom"
                onError={(e) => {
                  e.target.onerror = null;
                  e.target.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="150" viewBox="0 0 200 150"><rect fill="%23071A2B" width="200" height="150"/><text fill="%2394a3b8" x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-size="12">Label Preview</text></svg>';
                }}
              />
            </div>
          </div>

          {/* Structured Attributes Card */}
          <ProductAttributes
            data={structured}
            provenance={result.provenance}
            conflicts={result.conflicts}
          />

        </div>

        {/* Right Column (7 Cols): Statutory Compliance Checks */}
        <div className="lg:col-span-7 space-y-6">
          
          {/* Violations Callout if present */}
          {violations.length > 0 && (
            <div className="bg-white rounded-2xl border border-rose-200 overflow-hidden shadow-2xs">
              <div className="px-5 py-3 bg-rose-50/80 border-b border-rose-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <AlertOctagon size={16} className="text-rose-600" />
                  <h4 className="text-xs sm:text-sm font-bold text-rose-900">
                    Statutory Violations Detected ({violations.length})
                  </h4>
                </div>
                <span className="text-[10px] uppercase font-bold text-rose-700 bg-rose-100 px-2 py-0.5 rounded">
                  Requires Rectification
                </span>
              </div>

              <div className="p-4 space-y-3 divide-y divide-rose-100">
                {violations.map((v, i) => (
                  <div key={i} className={i > 0 ? "pt-3" : ""}>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-rose-800 bg-rose-100 px-1.5 py-0.5 rounded">
                        {v.rule_id}
                      </span>
                      <span className="text-xs font-semibold text-slate-700">
                        {v.legal_reference}
                      </span>
                      <span className="text-[10px] uppercase font-bold text-rose-700 border border-rose-300 px-1.5 rounded ml-auto">
                        {v.severity || 'CRITICAL'}
                      </span>
                    </div>
                    <p className="text-xs text-rose-950 font-semibold mt-1 leading-relaxed">
                      {v.message}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Advisory Warnings Callout if present */}
          {warnings.length > 0 && (
            <div className="bg-white rounded-2xl border border-amber-200 overflow-hidden shadow-2xs">
              <div className="px-5 py-3 bg-amber-50/80 border-b border-amber-200 flex items-center gap-2">
                <AlertTriangle size={16} className="text-amber-600" />
                <h4 className="text-xs sm:text-sm font-bold text-amber-900">
                  Advisory Warnings ({warnings.length})
                </h4>
              </div>
              <div className="p-4 space-y-3 divide-y divide-amber-100">
                {warnings.map((w, i) => (
                  <div key={i} className={i > 0 ? "pt-3" : ""}>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-amber-800 bg-amber-100 px-1.5 py-0.5 rounded">
                        {w.rule_id}
                      </span>
                      <span className="text-xs font-semibold text-slate-700">
                        {w.legal_reference}
                      </span>
                    </div>
                    <p className="text-xs text-amber-950 font-medium mt-1">
                      {w.message}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Compliance Checks Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-1">
              <h3 className="text-base font-bold text-navy-950">
                Compliance Checks
              </h3>
              <span className="text-xs text-slate-500 font-mono">
                {checks.length} statutory declarations
              </span>
            </div>

            {checks.length === 0 ? (
              <div className="p-8 text-center text-slate-400 italic bg-white rounded-xl border border-slate-200">
                No statutory checks recorded.
              </div>
            ) : (
              <div className="space-y-3">
                {checks.map((check, idx) => (
                  <RuleCheckCard key={idx} check={check} />
                ))}
              </div>
            )}
          </div>

        </div>

      </div>

      {/* Visually Separated Raw OCR Evidence Section */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        
        {/* Header with Collapsible Toggle */}
        <div
          onClick={() => setIsOcrExpanded(!isOcrExpanded)}
          className="px-6 py-4 bg-slate-50/90 border-b border-slate-200 flex items-center justify-between cursor-pointer select-none hover:bg-slate-100/70 transition-colors"
        >
          <div>
            <div className="flex items-center gap-2">
              <FileText size={16} className="text-emerald-600" />
              <h3 className="font-bold text-sm sm:text-base text-navy-950">
                Raw OCR Evidence
              </h3>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Source text detected during inspection
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500 font-mono hidden sm:inline">
              Confidence: <span className="font-bold text-navy-900">{((ocr.average_confidence || 0) * 100).toFixed(1)}%</span>
            </span>
            <button
              type="button"
              className="p-1 rounded text-slate-400 hover:text-slate-700 transition-colors"
              aria-label="Toggle Raw OCR Section"
            >
              {isOcrExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>
          </div>
        </div>

        {/* Collapsible Content */}
        {isOcrExpanded && (
          <div className="p-6 space-y-4">
            
            {/* Search and Action Bar */}
            <div className="flex items-center justify-between gap-3">
              <div className="relative flex-1 max-w-sm">
                <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={ocrSearch}
                  onChange={(e) => setOcrSearch(e.target.value)}
                  placeholder="Search detected text..."
                  className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-slate-50 focus:outline-none focus:border-emerald-500 text-slate-800"
                />
                {ocrSearch && (
                  <button
                    onClick={() => setOcrSearch('')}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs"
                  >
                    ×
                  </button>
                )}
              </div>

              <button
                type="button"
                onClick={() => {
                  if (ocr.full_text) {
                    navigator.clipboard.writeText(ocr.full_text);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                  }
                }}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors shadow-2xs cursor-pointer"
              >
                {copied ? (
                  <>
                    <Check size={13} className="text-emerald-600" />
                    <span className="text-emerald-700 font-bold">Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy size={13} className="text-slate-500" />
                    <span>Copy Text</span>
                  </>
                )}
              </button>
            </div>

            {/* OCR Raw Monospace Text View */}
            <div className="p-4 bg-slate-50/80 rounded-xl border border-slate-200 font-mono text-xs text-slate-800 whitespace-pre-wrap max-h-96 overflow-y-auto leading-relaxed selection:bg-emerald-200">
              {ocr.full_text ? (
                ocrSearch.trim() ? (
                  ocr.full_text.split(new RegExp(`(${ocrSearch.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')).map((part, i) =>
                    part.toLowerCase() === ocrSearch.toLowerCase() ? (
                      <mark key={i} className="bg-emerald-200 text-emerald-950 font-bold px-0.5 rounded">
                        {part}
                      </mark>
                    ) : (
                      part
                    )
                  )
                ) : (
                  ocr.full_text
                )
              ) : (
                <span className="text-slate-400 italic">No text extracted by OCR engine.</span>
              )}
            </div>

            {/* Evidence Metadata Footer */}
            <div className="text-[11px] text-slate-500 flex flex-wrap items-center justify-between gap-3 px-1 pt-2 border-t border-slate-100">
              <span>
                RapidOCR Average Confidence: <span className="font-bold text-navy-950 font-mono">{((ocr.average_confidence || 0) * 100).toFixed(1)}%</span>
              </span>
              <span>
                Detected Blocks: <span className="font-bold text-navy-950 font-mono">{ocr.block_count || 0}</span>
              </span>
              <span>
                Inference Time: <span className="font-bold text-navy-950 font-mono">{ocr.execution_time_seconds ? `${ocr.execution_time_seconds.toFixed(2)}s` : '0.42s'}</span>
              </span>
            </div>

          </div>
        )}

      </div>

      {/* Full Image Modal */}
      {showImageModal && (
        <div
          onClick={() => setShowImageModal(false)}
          className="fixed inset-0 bg-navy-950/85 backdrop-blur-xs z-50 flex items-center justify-center p-4 cursor-pointer"
        >
          <div className="relative max-w-4xl max-h-[90vh] bg-navy-900 border border-navy-700 rounded-2xl overflow-hidden p-3 shadow-2xl">
            <button
              onClick={() => setShowImageModal(false)}
              className="absolute top-4 right-4 w-8 h-8 rounded-full bg-navy-800 text-white flex items-center justify-center hover:bg-navy-700 z-10"
            >
              <X size={16} />
            </button>
            <img
              src={fullImageUrl}
              alt="Preprocessed Package Large"
              className="max-h-[82vh] w-auto mx-auto object-contain rounded-lg"
            />
            <p className="text-center text-xs text-slate-400 mt-2 font-mono">
              Click anywhere to close
            </p>
          </div>
        </div>
      )}

    </div>
  );
}
