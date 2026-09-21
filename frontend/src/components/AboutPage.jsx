import React from 'react';
import { Scale, BookOpen, ShieldCheck, Cpu, Database, CheckCircle2, AlertCircle } from 'lucide-react';

export function AboutPage({ onStartInspect }) {
  const rules = [
    {
      code: 'Rule 6(1)(a)',
      title: 'Name & Complete Address of Manufacturer / Packer / Importer',
      desc: 'Requires the name and complete physical address including postal PIN code of the manufacturer or packer or importer to be declared on every retail package.'
    },
    {
      code: 'Rule 6(1)(b)',
      title: 'Common or Generic Name of the Commodity',
      desc: 'Mandates clear declaration of the generic or common name contained in the package on the Principal Display Panel (PDP).'
    },
    {
      code: 'Rule 6(1)(c) & Rule 11',
      title: 'Net Quantity in Standard Units of Measurement',
      desc: 'Requires declaration of net quantity in terms of standard units (g, kg, ml, l) from the Second Schedule or by number (count).'
    },
    {
      code: 'Rule 6(1)(d)',
      title: 'Month & Year of Manufacture / Pre-packing / Import',
      desc: 'Mandates declaration of the month and year in which the commodity is manufactured or pre-packed or imported.'
    },
    {
      code: 'Rule 6(1)(e)',
      title: 'Retail Sale Price (MRP)',
      desc: 'Maximum Retail Price stated clearly in Indian Rupees inclusive of all taxes. Stating taxes extra or charging above MRP is explicitly illegal.'
    },
    {
      code: 'Rule 6(11) (2021 Amendment)',
      title: 'Unit Sale Price (USP)',
      desc: 'Mandatory declaration of the price per unit (per g/ml for packages < 1kg/1L, or per kg/l for packages > 1kg/1L) to enable direct price comparison.'
    },
    {
      code: 'Rule 6(1)(n)',
      title: 'Consumer Care Grievance Redressal',
      desc: 'Requires name, address, telephone number, and email address of the person/office who can be contacted by consumers in case of complaint.'
    },
    {
      code: 'Rule 6(10)',
      title: 'Country of Origin (Imported Commodities)',
      desc: 'Mandatory declaration of the country of origin on packages containing imported commodities.'
    }
  ];

  return (
    <div className="max-w-5xl mx-auto py-12 px-4 sm:px-6 lg:px-8 space-y-12">
      
      {/* Header */}
      <div className="text-center max-w-3xl mx-auto space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs font-bold uppercase tracking-wider">
          <Scale size={14} />
          <span>Statutory Framework</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-navy-900 tracking-tight">
          About PackSure & Legal Metrology
        </h1>
        <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
          PackSure is an AI-powered legaltech prototype built to automate statutory packaging audits under the Legal Metrology (Packaged Commodities) Rules, 2011.
        </p>
      </div>

      {/* Core Principles */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-2">
          <div className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <ShieldCheck size={20} />
          </div>
          <h3 className="font-bold text-navy-900 text-base">Zero Hallucination</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Legal Metrology compliance decisions are never delegated to probabilistic text generation. A deterministic rule engine verifies statutory clauses with mathematical precision.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-2">
          <div className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <Cpu size={20} />
          </div>
          <h3 className="font-bold text-navy-900 text-base">Hybrid AI & OCR Pipeline</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Combines OpenCV adaptive image enhancement, local RapidOCR ONNX inference, and resilient schema extraction to parse labels under varying lighting, skew, and print qualities.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-2">
          <div className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <Database size={20} />
          </div>
          <h3 className="font-bold text-navy-900 text-base">Auditable SQLite Logs</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Every inspection session persists full OCR bounding boxes, structured JSON declarations, and timestamped rule evaluations for legal reporting and audit trail reconstruction.
          </p>
        </div>
      </div>

      {/* Statutory Rules Table/List */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8 space-y-6">
        <div className="border-b border-slate-100 pb-4">
          <h2 className="text-xl font-bold text-navy-900">
            Enforced Rules & Statutory References
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Rules under Chapter II of Legal Metrology (Packaged Commodities) Rules, 2011 and official Gazette amendments.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {rules.map((r, i) => (
            <div key={i} className="p-4 rounded-xl bg-slate-50 border border-slate-100 space-y-1.5">
              <span className="text-[10px] font-mono font-bold uppercase text-emerald-700 bg-emerald-100/80 px-2 py-0.5 rounded">
                {r.code}
              </span>
              <h4 className="font-bold text-xs text-navy-900 mt-1">{r.title}</h4>
              <p className="text-[11px] text-slate-600 leading-relaxed">{r.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Regulatory Disclaimer */}
      <div className="p-4 rounded-xl bg-amber-50/80 border border-amber-200 flex items-start gap-3 text-xs text-amber-900">
        <AlertCircle size={18} className="text-amber-600 mt-0.5 shrink-0" />
        <div>
          <h4 className="font-bold">Prototype Notice & Legal Disclaimer</h4>
          <p className="text-[11px] text-amber-800 mt-0.5">
            PackSure is an automated statutory compliance verification prototype designed for quality assurance, retail auditing, and compliance verification. Official legal enforcement determinations remain subject to authorized inspection authorities under the Legal Metrology Act, 2009.
          </p>
        </div>
      </div>

    </div>
  );
}
