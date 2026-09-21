import React from 'react';
import { ShieldCheck, AlertOctagon, HelpCircle, CheckCircle2, XCircle, AlertTriangle, MinusCircle } from 'lucide-react';

export function ComplianceBadge({ status, size = 'normal' }) {
  const normalizedStatus = (status || '').toUpperCase();

  const sizeClasses = size === 'large'
    ? 'px-4 py-2 text-sm sm:text-base font-bold tracking-wide'
    : size === 'small'
    ? 'px-2 py-0.5 text-[11px] font-semibold'
    : 'px-3 py-1 text-xs font-semibold';

  const iconSize = size === 'large' ? 20 : size === 'small' ? 13 : 15;

  switch (normalizedStatus) {
    case 'COMPLIANT':
      return (
        <span className={`inline-flex items-center gap-2 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-300 shadow-2xs ${sizeClasses}`}>
          <ShieldCheck size={iconSize} className="text-emerald-600 shrink-0" />
          <span>COMPLIANT</span>
        </span>
      );

    case 'NON_COMPLIANT':
      return (
        <span className={`inline-flex items-center gap-2 rounded-full bg-rose-50 text-rose-800 border border-rose-300 shadow-2xs ${sizeClasses}`}>
          <AlertOctagon size={iconSize} className="text-rose-600 shrink-0" />
          <span>NON-COMPLIANT</span>
        </span>
      );

    case 'INSUFFICIENT_DATA':
      return (
        <span className={`inline-flex items-center gap-2 rounded-full bg-amber-50 text-amber-900 border border-amber-300 shadow-2xs ${sizeClasses}`}>
          <HelpCircle size={iconSize} className="text-amber-600 shrink-0" />
          <span>INSUFFICIENT DATA</span>
        </span>
      );

    case 'PASS':
      return (
        <span className={`inline-flex items-center gap-1.5 rounded-md bg-emerald-50 text-emerald-800 border border-emerald-200/80 font-mono ${sizeClasses}`}>
          <CheckCircle2 size={iconSize} className="text-emerald-600 shrink-0" />
          <span>PASS</span>
        </span>
      );

    case 'FAIL':
      return (
        <span className={`inline-flex items-center gap-1.5 rounded-md bg-rose-50 text-rose-800 border border-rose-200/80 font-mono ${sizeClasses}`}>
          <XCircle size={iconSize} className="text-rose-600 shrink-0" />
          <span>FAIL</span>
        </span>
      );

    case 'WARNING':
      return (
        <span className={`inline-flex items-center gap-1.5 rounded-md bg-amber-50 text-amber-800 border border-amber-200/80 font-mono ${sizeClasses}`}>
          <AlertTriangle size={iconSize} className="text-amber-600 shrink-0" />
          <span>WARNING</span>
        </span>
      );

    case 'NOT_APPLICABLE':
      return (
        <span className={`inline-flex items-center gap-1.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200 font-mono ${sizeClasses}`}>
          <MinusCircle size={iconSize} className="text-slate-400 shrink-0" />
          <span>N/A</span>
        </span>
      );

    default:
      return (
        <span className={`inline-flex items-center gap-1 rounded-md bg-slate-100 text-slate-700 border border-slate-200 ${sizeClasses}`}>
          <span>{status || 'UNKNOWN'}</span>
        </span>
      );
  }
}
