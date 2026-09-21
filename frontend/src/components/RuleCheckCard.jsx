import React from 'react';
import { ComplianceBadge } from './ComplianceBadge';
import { BookOpen } from 'lucide-react';

export function RuleCheckCard({ check }) {
  const isFailed = check.status === 'FAIL';
  const isWarning = check.status === 'WARNING';
  const isInsufficient = check.status === 'INSUFFICIENT_DATA';
  const isPass = check.status === 'PASS';

  // Subtle restrained styling
  const cardBorderClass = isFailed
    ? 'border-rose-200/90 hover:border-rose-300'
    : isWarning || isInsufficient
    ? 'border-amber-200/90 hover:border-amber-300'
    : 'border-slate-200/90 hover:border-emerald-300';

  const detectedVal = check.extracted_value !== undefined && check.extracted_value !== null
    ? (typeof check.extracted_value === 'object'
        ? JSON.stringify(check.extracted_value)
        : String(check.extracted_value))
    : null;

  const title = check.field_checked
    ? check.field_checked.replace(/_/g, ' ').toUpperCase()
    : 'STATUTORY REQUIREMENT';

  return (
    <div className={`rounded-xl border ${cardBorderClass} bg-white shadow-2xs transition-all duration-150 p-4 sm:p-5 space-y-3.5`}>
      
      {/* Top: Status + Rule ID + Title on left, Statutory Reference on right */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2.5 flex-wrap">
          <ComplianceBadge status={check.status} size="small" />
          <span className="font-mono text-xs font-bold text-navy-900 bg-slate-100 px-2 py-0.5 rounded">
            {check.rule_id}
          </span>
          <h4 className="text-xs sm:text-sm font-bold text-navy-950 uppercase tracking-wide">
            {title}
          </h4>
        </div>

        <div className="flex items-center gap-1.5 text-xs text-slate-600 font-mono">
          <BookOpen size={13} className="text-slate-400" />
          <span className="font-semibold text-slate-700">{check.legal_reference}</span>
        </div>
      </div>

      {/* Clean Two-Column Section: Detected on Label vs Statutory Requirement */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
        
        {/* Column 1: Detected on Label */}
        <div className={`p-3 rounded-lg border ${
          isFailed
            ? 'bg-rose-50/40 border-rose-100'
            : isWarning || isInsufficient
            ? 'bg-amber-50/40 border-amber-100'
            : 'bg-slate-50/80 border-slate-100'
        }`}>
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
            Detected on Label
          </span>
          {detectedVal ? (
            <span className="text-xs font-mono font-bold text-navy-900 break-words">
              {detectedVal}
            </span>
          ) : (
            <span className="text-xs text-rose-700 font-semibold italic">
              Not detected on label
            </span>
          )}
        </div>

        {/* Column 2: Statutory Requirement */}
        <div className="p-3 rounded-lg bg-slate-50/80 border border-slate-100">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
            Statutory Requirement
          </span>
          <span className="text-xs text-slate-700 font-medium leading-relaxed block">
            {check.expected_requirement || 'Mandatory declaration under Legal Metrology Rules, 2011'}
          </span>
        </div>

      </div>

      {/* Statutory Rationale */}
      {check.explanation && (
        <div className={`p-3 rounded-lg text-xs leading-relaxed ${
          isFailed
            ? 'bg-rose-50/60 border border-rose-200/70 text-rose-950 font-medium'
            : isWarning || isInsufficient
            ? 'bg-amber-50/60 border border-amber-200/70 text-amber-950 font-medium'
            : 'bg-emerald-50/50 border border-emerald-200/60 text-emerald-950'
        }`}>
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-0.5">
            Statutory Rationale
          </span>
          <span className="block">{check.explanation}</span>
        </div>
      )}

    </div>
  );
}
