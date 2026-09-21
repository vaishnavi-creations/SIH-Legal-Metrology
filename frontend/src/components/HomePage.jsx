import React from 'react';
import {
  ArrowRight,
  History,
  Scan,
  CheckCircle2,
  Scale,
  Camera,
  FileText,
  Cpu,
  ShieldCheck,
  Building2,
  Tag,
  Package,
  Calendar,
  IndianRupee,
  PhoneCall,
  Globe,
  Database,
  ArrowDown
} from 'lucide-react';

export function HomePage({ onStartInspect, onViewHistory }) {
  const trustPoints = [
    { label: '2011 Rules & Amendments', icon: Scale },
    { label: 'Deterministic Rule Validation', icon: CheckCircle2 },
    { label: 'OCR + AI Extraction', icon: Cpu },
    { label: 'Auditable Inspection Records', icon: Database },
  ];

  const pipelineStages = [
    {
      num: '01',
      title: 'SCAN',
      desc: 'Upload a packaged commodity label image.',
      icon: Camera,
    },
    {
      num: '02',
      title: 'READ',
      desc: 'RapidOCR engine detects raw text blocks and coordinates.',
      icon: FileText,
    },
    {
      num: '03',
      title: 'EXTRACT',
      desc: 'Normalizes and structures mandatory product declarations.',
      icon: Cpu,
    },
    {
      num: '04',
      title: 'VERIFY',
      desc: 'Evaluates declarations against statutory legal clauses.',
      icon: Scale,
    },
    {
      num: '05',
      title: 'REPORT',
      desc: 'Produces transparent verdicts with full audit records.',
      icon: CheckCircle2,
    },
  ];

  const checks = [
    {
      icon: Building2,
      name: 'Manufacturer / Packer',
      desc: 'Name, complete physical address, and 6-digit postal PIN code.',
      ref: 'Rule 6(1)(a)',
    },
    {
      icon: Tag,
      name: 'Generic Commodity Name',
      desc: 'Clear common or generic identity on the principal display panel.',
      ref: 'Rule 6(1)(b)',
    },
    {
      icon: Package,
      name: 'Net Quantity',
      desc: 'Standard units of weight, volume, or piece count from Second Schedule.',
      ref: 'Rule 6(1)(c) & R11',
    },
    {
      icon: Calendar,
      name: 'Mfg / Packing Date',
      desc: 'Month and year of manufacture, pre-packing, or import.',
      ref: 'Rule 6(1)(d)',
    },
    {
      icon: IndianRupee,
      name: 'Maximum Retail Price',
      desc: 'Retail price declared in INR with mandatory tax-inclusive statement.',
      ref: 'Rule 6(1)(e)',
    },
    {
      icon: Scale,
      name: 'Unit Sale Price',
      desc: 'Standard price per g/ml or kg/L to ensure consumer transparency.',
      ref: 'Rule 6(11)',
    },
    {
      icon: PhoneCall,
      name: 'Consumer Care',
      desc: 'Dedicated grievance phone number and official contact email address.',
      ref: 'Rule 6(1)(n)',
    },
    {
      icon: Globe,
      name: 'Country of Origin',
      desc: 'Country of manufacture required on all imported retail packaging.',
      ref: 'Rule 6(10)',
    },
  ];

  return (
    <div className="space-y-20 pb-20">
      
      {/* 1. HERO SECTION */}
      <section className="bg-[#071A2B] text-white pt-16 pb-20 border-b border-[#0E2A44]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            
            {/* Left Column: Hero Copy & Actions */}
            <div className="lg:col-span-7 space-y-6 text-center lg:text-left">
              
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold tracking-wider uppercase">
                <Scale size={14} />
                <span>LEGAL METROLOGY COMPLIANCE</span>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight leading-[1.12]">
                Know what's on the pack.{' '}
                <span className="text-emerald-400 block mt-1">
                  Know if it complies.
                </span>
              </h1>

              <p className="text-base sm:text-lg text-slate-300 max-w-xl mx-auto lg:mx-0 leading-relaxed font-normal">
                PackSure extracts mandatory declarations from packaged-product labels and verifies them against Legal Metrology requirements.
              </p>

              {/* Primary & Secondary Actions */}
              <div className="pt-3 flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-3.5">
                <button
                  onClick={onStartInspect}
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-6 py-3.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-[#071A2B] font-bold text-sm transition-all shadow-md shadow-emerald-500/20 cursor-pointer"
                >
                  <Scan size={18} />
                  <span>Scan a Product</span>
                  <ArrowRight size={16} />
                </button>

                <button
                  onClick={onViewHistory}
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-[#0B2235] hover:bg-[#122A40] text-slate-200 border border-slate-700/80 font-semibold text-sm transition-colors cursor-pointer"
                >
                  <History size={16} />
                  <span>View Scan History</span>
                </button>
              </div>

            </div>

            {/* Right Column: Realistic Live Compliance Preview Card */}
            <div className="lg:col-span-5 flex justify-center">
              <div className="w-full max-w-md bg-[#0B2235] border border-slate-700/70 rounded-2xl p-5 shadow-2xl space-y-4">
                
                {/* Header of Preview */}
                <div className="flex items-center justify-between border-b border-slate-700/60 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span className="text-xs font-semibold text-slate-300">Live Compliance Preview</span>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">Rule 6 Verification</span>
                </div>

                {/* Simulated Label Card Representation */}
                <div className="bg-white rounded-xl p-4 text-slate-900 space-y-3 shadow-inner">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Sample Commodity</span>
                      <h4 className="font-bold text-sm text-slate-900">Classic Butter Biscuits</h4>
                    </div>
                    <span className="text-xs font-mono font-bold bg-slate-100 text-slate-700 px-2 py-0.5 rounded">100 g</span>
                  </div>

                  {/* Extracted Values Grid */}
                  <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                    <div className="p-2 rounded bg-slate-50 border border-slate-100">
                      <span className="text-[10px] text-slate-500 block">MRP (Taxes Incl.)</span>
                      <span className="font-bold text-slate-900">Rs. 50.00</span>
                    </div>
                    <div className="p-2 rounded bg-slate-50 border border-slate-100">
                      <span className="text-[10px] text-slate-500 block">Unit Sale Price</span>
                      <span className="font-semibold text-slate-900">Rs. 0.50 / 100g</span>
                    </div>
                    <div className="p-2 rounded bg-slate-50 border border-slate-100">
                      <span className="text-[10px] text-slate-500 block">Packed Date</span>
                      <span className="font-semibold text-slate-900">08/2026</span>
                    </div>
                    <div className="p-2 rounded bg-slate-50 border border-slate-100">
                      <span className="text-[10px] text-slate-500 block">Manufacturer</span>
                      <span className="font-semibold text-slate-900 truncate block">Demo Foods Ltd</span>
                    </div>
                  </div>

                  {/* Compliance Verdict Badge */}
                  <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-900">
                      <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
                      <span>PackSure Verification</span>
                    </div>
                    <span className="text-[11px] font-extrabold uppercase font-mono tracking-wider text-emerald-800 bg-white px-2 py-0.5 rounded border border-emerald-200">
                      COMPLIANT
                    </span>
                  </div>
                </div>

                {/* Card Sub-stats */}
                <div className="grid grid-cols-2 gap-3 text-xs text-slate-400">
                  <div className="flex items-center justify-between p-2 rounded bg-[#071A2B] border border-slate-700/60">
                    <span className="text-[11px]">Detection time</span>
                    <span className="font-mono text-slate-200 font-bold">0.42s</span>
                  </div>
                  <div className="flex items-center justify-between p-2 rounded bg-[#071A2B] border border-slate-700/60">
                    <span className="text-[11px]">Rules checked</span>
                    <span className="font-mono text-emerald-400 font-bold">8 of 8</span>
                  </div>
                </div>

              </div>
            </div>

          </div>
        </div>
      </section>

      {/* 2. COMPACT CREDIBILITY STRIP */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="py-4 px-6 rounded-xl bg-white border border-slate-200 shadow-xs flex flex-wrap items-center justify-around gap-6 text-xs text-slate-600 font-medium">
          {trustPoints.map((item, idx) => {
            const Icon = item.icon;
            return (
              <div key={idx} className="flex items-center gap-2">
                <Icon size={16} className="text-emerald-600 shrink-0" />
                <span>{item.label}</span>
              </div>
            );
          })}
        </div>
      </section>

      {/* 3. HOW PACKSURE WORKS (5 CONNECTED STAGES PIPELINE) */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <h2 className="text-3xl font-bold text-slate-900 tracking-tight">
            How PackSure Works
          </h2>
          <p className="text-sm text-slate-600">
            From package image to compliance decision in seconds.
          </p>
        </div>

        {/* 5-Step Connected Pipeline */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 relative">
          {pipelineStages.map((stage, idx) => {
            const Icon = stage.icon;
            return (
              <div
                key={idx}
                className="relative p-5 rounded-xl bg-white border border-slate-200 shadow-xs hover:border-emerald-500/40 transition-colors flex flex-col justify-between space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">
                    {stage.num}
                  </span>
                  <div className="w-8 h-8 rounded-lg bg-slate-50 text-slate-600 flex items-center justify-center">
                    <Icon size={16} />
                  </div>
                </div>

                <div className="space-y-1">
                  <h4 className="text-sm font-bold text-slate-900">{stage.title}</h4>
                  <p className="text-xs text-slate-600 leading-relaxed">{stage.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 4. WHAT PACKSURE CHECKS */}
      <section className="bg-slate-50/80 py-16 border-y border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
          
          <div className="text-center max-w-2xl mx-auto space-y-2">
            <h2 className="text-3xl font-bold text-slate-900 tracking-tight">
              What PackSure Checks
            </h2>
            <p className="text-sm text-slate-600">
              Mandatory declarations required under Chapter II of the Legal Metrology Rules, 2011.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {checks.map((item, idx) => {
              const Icon = item.icon;
              return (
                <div
                  key={idx}
                  className="p-5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-emerald-400/50 transition-colors space-y-2.5 flex flex-col justify-between"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                        <Icon size={18} />
                      </div>
                      <span className="text-[10px] font-mono font-bold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                        {item.ref}
                      </span>
                    </div>

                    <h4 className="text-sm font-bold text-slate-900">
                      {item.name}
                    </h4>

                    <p className="text-xs text-slate-600 leading-relaxed">
                      {item.desc}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

        </div>
      </section>

      {/* 5. ARCHITECTURE SECTION (BUILT FOR TRACEABLE COMPLIANCE) */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <h2 className="text-3xl font-bold text-slate-900 tracking-tight">
            Built for Traceable Compliance
          </h2>
          <p className="text-sm text-slate-600">
            Compliance decisions are evaluated by deterministic statutory rules.
          </p>
        </div>

        {/* Pipeline Diagram */}
        <div className="bg-[#071A2B] text-white rounded-2xl p-6 sm:p-10 border border-[#0E2A44] shadow-xl">
          
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 text-center text-xs">
            <div className="p-3.5 rounded-xl bg-[#0B2235] border border-slate-700 flex flex-col items-center justify-center space-y-1">
              <Camera size={18} className="text-emerald-400" />
              <span className="font-bold text-slate-200 text-[11px]">Product Image</span>
              <span className="text-[10px] text-slate-400">JPEG/PNG</span>
            </div>

            <div className="p-3.5 rounded-xl bg-[#0B2235] border border-slate-700 flex flex-col items-center justify-center space-y-1">
              <Cpu size={18} className="text-emerald-400" />
              <span className="font-bold text-slate-200 text-[11px]">OpenCV</span>
              <span className="text-[10px] text-slate-400">Preprocessing</span>
            </div>

            <div className="p-3.5 rounded-xl bg-[#0B2235] border border-slate-700 flex flex-col items-center justify-center space-y-1">
              <FileText size={18} className="text-emerald-400" />
              <span className="font-bold text-slate-200 text-[11px]">RapidOCR</span>
              <span className="text-[10px] text-slate-400">Text Engine</span>
            </div>

            <div className="p-3.5 rounded-xl bg-[#0B2235] border border-slate-700 flex flex-col items-center justify-center space-y-1">
              <Tag size={18} className="text-emerald-400" />
              <span className="font-bold text-slate-200 text-[11px]">Structured Data</span>
              <span className="text-[10px] text-slate-400">Schema Parser</span>
            </div>

            <div className="p-3.5 rounded-xl bg-[#0B2235] border border-emerald-500/40 flex flex-col items-center justify-center space-y-1">
              <Scale size={18} className="text-emerald-400" />
              <span className="font-bold text-emerald-300 text-[11px]">Rule Engine</span>
              <span className="text-[10px] text-emerald-400/80">Deterministic</span>
            </div>

            <div className="p-3.5 rounded-xl bg-[#0B2235] border border-slate-700 flex flex-col items-center justify-center space-y-1">
              <CheckCircle2 size={18} className="text-emerald-400" />
              <span className="font-bold text-slate-200 text-[11px]">Verdict</span>
              <span className="text-[10px] text-slate-400">Pass / Fail</span>
            </div>

            <div className="p-3.5 rounded-xl bg-[#0B2235] border border-slate-700 flex flex-col items-center justify-center space-y-1 col-span-2 sm:col-span-1">
              <Database size={18} className="text-emerald-400" />
              <span className="font-bold text-slate-200 text-[11px]">Audit Trail</span>
              <span className="text-[10px] text-slate-400">SQLite DB</span>
            </div>
          </div>

          <p className="text-xs text-slate-400 text-center mt-6 max-w-2xl mx-auto leading-relaxed">
            By decoupling character recognition from statutory decision logic, PackSure provides a verifiable, reproducible legal metrology inspection trail.
          </p>

        </div>
      </section>

      {/* 6. FINAL CTA SECTION */}
      <section className="max-w-4xl mx-auto px-4 text-center space-y-5">
        <h3 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
          Ready to inspect a package?
        </h3>
        <p className="text-sm text-slate-600 max-w-md mx-auto">
          Scan any packaged commodity label and verify all mandatory statutory declarations in seconds.
        </p>
        <div>
          <button
            onClick={onStartInspect}
            className="inline-flex items-center gap-2.5 px-7 py-3.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-[#071A2B] font-bold text-sm shadow-md transition-colors cursor-pointer"
          >
            <Scan size={18} />
            <span>Scan a Product</span>
            <ArrowRight size={16} />
          </button>
        </div>
      </section>

    </div>
  );
}
