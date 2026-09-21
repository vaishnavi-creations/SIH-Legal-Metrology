import React, { useEffect, useState } from 'react';
import {
  ArrowLeft,
  ShieldCheck,
  Camera,
  FileText,
  Cpu,
  Scale,
  CheckCircle2,
  Loader2,
  Lock,
  Sparkles,
  Layers
} from 'lucide-react';
import { formatFileSize } from '../utils/formatters';

export function ProcessingState({ file, previewUrl, onCancel }) {
  const [currentStep, setCurrentStep] = useState(1);

  // Progressive simulated pipeline steps while the real API call is resolving
  useEffect(() => {
    const t1 = setTimeout(() => setCurrentStep(2), 700);
    const t2 = setTimeout(() => setCurrentStep(3), 1600);
    const t3 = setTimeout(() => setCurrentStep(4), 2500);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, []);

  const timeline = [
    {
      step: 1,
      title: 'Preprocessing Image',
      desc: 'Enhancing clarity and reading labels',
    },
    {
      step: 2,
      title: 'Reading Text from Image',
      desc: 'Using RapidOCR for accurate text detection',
    },
    {
      step: 3,
      title: 'Extracting Key Information',
      desc: 'MRP, Net Quantity, Dates, Manufacturer etc.',
    },
    {
      step: 4,
      title: 'Checking Legal Metrology Rules',
      desc: 'Validating against statutory requirements',
    },
  ];

  const techCards = [
    {
      code: '01',
      icon: Camera,
      title: 'OpenCV Preprocessing',
      desc: 'Grayscale conversion, CLAHE contrast boost & noise reduction',
    },
    {
      code: '02',
      icon: FileText,
      title: 'RapidOCR Text Engine',
      desc: 'Local ONNX deep text detection and character recognition',
    },
    {
      code: '03',
      icon: Cpu,
      title: 'AI Structured Extraction',
      desc: 'Regex and heuristic extraction of required statutory fields',
    },
    {
      code: '04',
      icon: Scale,
      title: 'Statutory Rule Engine',
      desc: 'Deterministic Legal Metrology (2011) compliance evaluation',
    },
  ];

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-8">
      
      {/* Top Bar: Back & Security Badge */}
      <div className="flex items-center justify-between">
        {onCancel ? (
          <button
            onClick={onCancel}
            className="inline-flex items-center gap-1.5 text-xs sm:text-sm font-semibold text-slate-600 hover:text-navy-900 px-3 py-1.5 rounded-lg bg-white border border-slate-200 shadow-2xs hover:bg-slate-50 transition-colors cursor-pointer"
          >
            <ArrowLeft size={16} />
            <span>Cancel & Return</span>
          </button>
        ) : (
          <div></div>
        )}

        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold shadow-2xs">
          <Lock size={12} className="text-emerald-600" />
          <span>Processing securely...</span>
        </div>
      </div>

      {/* Heading */}
      <div className="text-center max-w-2xl mx-auto space-y-2">
        <h2 className="text-2xl sm:text-3xl font-extrabold text-navy-900 tracking-tight">
          Inspecting Packaged Commodity...
        </h2>
        <p className="text-xs sm:text-sm text-slate-600">
          Running computer vision, optical character recognition, and statutory rule evaluation.
        </p>
      </div>

      {/* Main Processing Card: Dual Column */}
      <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 sm:p-8 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        
        {/* Left Side: Product Image Preview with Scanning Laser */}
        <div className="lg:col-span-5 flex flex-col items-center">
          <div className="relative w-full max-w-[320px] aspect-[4/5] rounded-2xl bg-slate-900 border-2 border-slate-800 overflow-hidden shadow-md flex items-center justify-center">
            
            {previewUrl ? (
              <img
                src={previewUrl}
                alt="Inspecting package label"
                className="w-full h-full object-contain p-2"
              />
            ) : (
              <div className="text-slate-500 text-center p-4">
                <Camera size={40} className="mx-auto mb-2 opacity-50" />
                <span className="text-xs font-mono">Product Image</span>
              </div>
            )}

            {/* Glowing horizontal laser scanning bar */}
            <div className="absolute left-0 right-0 h-1 bg-gradient-to-r from-transparent via-emerald-400 to-transparent shadow-[0_0_15px_#18B889] animate-scanline pointer-events-none z-20"></div>

            {/* Corner Bracket Reticles */}
            <div className="absolute top-3 left-3 w-4 h-4 border-t-2 border-l-2 border-emerald-400 z-10 pointer-events-none"></div>
            <div className="absolute top-3 right-3 w-4 h-4 border-t-2 border-r-2 border-emerald-400 z-10 pointer-events-none"></div>
            <div className="absolute bottom-3 left-3 w-4 h-4 border-b-2 border-l-2 border-emerald-400 z-10 pointer-events-none"></div>
            <div className="absolute bottom-3 right-3 w-4 h-4 border-b-2 border-r-2 border-emerald-400 z-10 pointer-events-none"></div>

            {/* Bottom active badge */}
            <div className="absolute bottom-3 left-1/2 transform -translate-x-1/2 z-20">
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold tracking-wider uppercase bg-navy-950/80 text-emerald-300 border border-emerald-500/40 backdrop-blur-xs flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
                ACTIVE SCAN
              </span>
            </div>
          </div>

          {/* Metadata */}
          {file && (
            <div className="mt-3 text-center space-y-0.5">
              <p className="text-xs font-bold text-navy-900 max-w-[280px] truncate">
                {file.name}
              </p>
              <p className="text-[11px] font-mono text-slate-500">
                {formatFileSize(file.size)} • {file.type || 'image'}
              </p>
            </div>
          )}
        </div>

        {/* Right Side: Vertical 4-Step Progress Timeline */}
        <div className="lg:col-span-7 space-y-6">
          <div className="border-b border-slate-100 pb-3">
            <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-emerald-600">
              PIPELINE EXECUTION
            </span>
            <h3 className="text-base font-bold text-navy-900 mt-0.5">
              Automated Statutory Verification
            </h3>
          </div>

          <div className="space-y-4">
            {timeline.map((item) => {
              const isCompleted = currentStep > item.step;
              const isActive = currentStep === item.step;
              const isPending = currentStep < item.step;

              return (
                <div
                  key={item.step}
                  className={`p-3.5 rounded-xl border transition-all duration-200 flex items-start gap-3.5 ${
                    isActive
                      ? 'bg-emerald-50/70 border-emerald-300 shadow-2xs'
                      : isCompleted
                      ? 'bg-white border-slate-200'
                      : 'bg-slate-50/50 border-slate-100 opacity-60'
                  }`}
                >
                  {/* Status Indicator */}
                  <div className="mt-0.5 shrink-0">
                    {isCompleted ? (
                      <div className="w-6 h-6 rounded-full bg-emerald-500 text-white flex items-center justify-center shadow-xs">
                        <CheckCircle2 size={15} />
                      </div>
                    ) : isActive ? (
                      <div className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center animate-spin">
                        <Loader2 size={15} />
                      </div>
                    ) : (
                      <div className="w-6 h-6 rounded-full bg-slate-200 text-slate-500 font-mono text-xs flex items-center justify-center">
                        {item.step}
                      </div>
                    )}
                  </div>

                  {/* Step Description */}
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <h4 className={`text-xs sm:text-sm font-bold ${
                        isActive ? 'text-emerald-900' : isCompleted ? 'text-navy-900' : 'text-slate-500'
                      }`}>
                        STEP {item.step}: {item.title}
                      </h4>
                      {isActive && (
                        <span className="text-[10px] font-mono font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded">
                          RUNNING
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                      {item.desc}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

      </div>

      {/* Technology Cards */}
      <div className="space-y-3">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 text-center">
          Under the Hood
        </h4>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {techCards.map((t, idx) => {
            const Icon = t.icon;
            return (
              <div
                key={idx}
                className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-2xs hover:border-emerald-300 transition-colors space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                    <Icon size={16} />
                  </div>
                  <span className="text-[10px] font-mono font-bold text-slate-400">
                    {t.code}
                  </span>
                </div>
                <h5 className="text-xs font-bold text-navy-900">{t.title}</h5>
                <p className="text-[11px] text-slate-500 leading-relaxed">{t.desc}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Bottom Message */}
      <div className="pt-4 text-center">
        <p className="text-xs font-semibold text-slate-500 flex items-center justify-center gap-2">
          <Sparkles size={14} className="text-emerald-500" />
          <span>From label to compliance, in seconds.</span>
        </p>
      </div>

    </div>
  );
}
