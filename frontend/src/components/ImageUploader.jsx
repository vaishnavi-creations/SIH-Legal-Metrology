import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  Camera,
  Image as ImageIcon,
  X,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Lock,
  Globe,
  Tag,
  Sparkles,
  Layers,
  FileCheck,
  Cpu,
  Scale
} from 'lucide-react';
import { formatFileSize } from '../utils/formatters';

const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024; // 15 MB
const ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp'];

export function ImageUploader({ onStartScan, isScanning }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [isImported, setIsImported] = useState(false);
  const [commodityType, setCommodityType] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  const fileInputRef = useRef(null);

  const validateAndSelectFile = (file) => {
    setErrorMsg(null);
    if (!file) return;

    // Check extension
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setErrorMsg(`Unsupported file type (${ext}). Please select a JPG, PNG, or WebP image.`);
      return;
    }

    // Check size
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setErrorMsg(`File size (${formatFileSize(file.size)}) exceeds the maximum allowed limit of 15 MB.`);
      return;
    }

    if (file.size === 0) {
      setErrorMsg('Selected file is empty (0 bytes). Please choose a valid image.');
      return;
    }

    setSelectedFile(file);
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSelectFile(e.target.files[0]);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSelectFile(e.dataTransfer.files[0]);
    }
  };

  const clearSelection = () => {
    setSelectedFile(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
    setErrorMsg(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMsg('Please select or drag an image of a packaged commodity to inspect.');
      return;
    }
    onStartScan(selectedFile, isImported, commodityType);
  };

  const pipelineSteps = [
    { label: 'IMAGE', desc: 'Preprocessed' },
    { label: 'OCR', desc: 'RapidOCR ONNX' },
    { label: 'EXTRACT', desc: 'Fields structured' },
    { label: 'VERIFY', desc: 'Rules 2011' },
    { label: 'REPORT', desc: 'Audit verdict' },
  ];

  return (
    <div className="max-w-7xl mx-auto py-8 sm:py-10 px-4 sm:px-6 lg:px-8 space-y-8">
      
      {/* Page Header */}
      <div className="border-b border-slate-200/80 pb-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold uppercase tracking-wider mb-3">
          <ShieldCheck size={14} className="text-emerald-600" />
          <span>Statutory Compliance Workspace</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-navy-950 tracking-tight">
          New Inspection
        </h1>
        <p className="text-sm sm:text-base text-slate-600 mt-1 max-w-3xl leading-relaxed">
          Upload a packaged product label to extract mandatory declarations and verify Legal Metrology compliance.
        </p>
      </div>

      {/* Main Form: Upload Area (Left) + Right Information Panel */}
      <form onSubmit={handleSubmit}>
        
        {/* Error Notification */}
        {errorMsg && (
          <div className="mb-6 p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3 text-rose-900 text-xs sm:text-sm shadow-2xs">
            <AlertCircle size={18} className="text-rose-600 mt-0.5 shrink-0" />
            <div>
              <p className="font-bold">File Notice</p>
              <p className="text-xs text-rose-800 mt-0.5">{errorMsg}</p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* Left / Main Column: Upload Area (Visual Focus) */}
          <div className="lg:col-span-8 space-y-6">
            
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8 space-y-6">
              
              {/* Upload Card Header */}
              <div className="border-b border-slate-100 pb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-lg sm:text-xl font-bold text-navy-950">
                    Upload Product Label
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
                    Drop your image here or browse from your device
                  </p>
                </div>
                <span className="text-[11px] font-mono font-bold uppercase text-slate-400 bg-slate-100 px-2 py-1 rounded">
                  Max 15 MB
                </span>
              </div>

              {/* Upload Dropzone / Image Preview Area */}
              {!selectedFile ? (
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current && fileInputRef.current.click()}
                  className={`border-2 border-dashed rounded-2xl p-8 sm:p-12 text-center transition-all duration-200 cursor-pointer flex flex-col items-center justify-center min-h-[300px] ${
                    dragOver
                      ? 'border-emerald-500 bg-emerald-50/50 scale-[0.99]'
                      : 'border-slate-300 hover:border-emerald-500 hover:bg-slate-50/70'
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".jpg,.jpeg,.png,.webp"
                    onChange={handleFileChange}
                    className="hidden"
                  />

                  <div className="w-16 h-16 rounded-2xl bg-emerald-50 border border-emerald-100 text-emerald-600 flex items-center justify-center mb-4 shadow-sm group-hover:scale-105 transition-transform">
                    <Camera size={32} />
                  </div>

                  <h3 className="text-base sm:text-lg font-bold text-navy-900">
                    Upload Product Label
                  </h3>

                  <p className="text-xs sm:text-sm text-slate-500 mt-1">
                    Drop your image here or{' '}
                    <span className="text-emerald-600 font-bold hover:underline">
                      browse from your device
                    </span>
                  </p>

                  <div className="mt-5">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        fileInputRef.current && fileInputRef.current.click();
                      }}
                      className="px-6 py-2.5 rounded-xl bg-navy-950 hover:bg-navy-900 text-white font-semibold text-xs sm:text-sm transition-colors shadow-sm cursor-pointer"
                    >
                      Browse Files
                    </button>
                  </div>

                  <p className="text-[11px] font-medium text-slate-400 mt-4">
                    Supported formats: JPG, JPEG, PNG, WEBP • Up to 15 MB
                  </p>
                </div>
              ) : (
                /* Selected File Preview Box */
                <div className="border border-slate-200 rounded-2xl p-6 bg-slate-50/70 flex flex-col sm:flex-row items-center gap-6 min-h-[280px]">
                  
                  {/* Thumbnail */}
                  <div className="w-48 h-48 sm:w-56 sm:h-56 rounded-xl bg-navy-950 border border-slate-200 overflow-hidden shrink-0 flex items-center justify-center shadow-sm relative">
                    {previewUrl ? (
                      <img
                        src={previewUrl}
                        alt="Selected label preview"
                        className="w-full h-full object-contain p-2"
                      />
                    ) : (
                      <ImageIcon size={40} className="text-slate-400" />
                    )}
                  </div>

                  {/* Metadata & Actions */}
                  <div className="space-y-4 flex-1 text-center sm:text-left">
                    <div>
                      <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded">
                        <CheckCircle2 size={12} />
                        Image Ready For Inspection
                      </span>
                      <h4 className="text-base font-bold text-navy-900 mt-2 break-all">
                        {selectedFile.name}
                      </h4>
                      <p className="text-xs text-slate-500 font-mono mt-0.5">
                        {formatFileSize(selectedFile.size)} • {selectedFile.type || 'image'}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2 pt-2">
                      <button
                        type="button"
                        onClick={clearSelection}
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-white border border-rose-200 text-rose-700 text-xs font-semibold hover:bg-rose-50 transition-colors cursor-pointer shadow-2xs"
                      >
                        <X size={14} />
                        <span>Remove Image</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => fileInputRef.current && fileInputRef.current.click()}
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-white border border-slate-200 text-slate-700 text-xs font-semibold hover:bg-slate-50 transition-colors cursor-pointer shadow-2xs"
                      >
                        <UploadCloud size={14} />
                        <span>Change Image</span>
                      </button>
                    </div>
                  </div>

                </div>
              )}

              {/* Optional Details: Commodity Category & Imported Toggle */}
              <div className="pt-4 border-t border-slate-100 space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                    Optional Inspection Context
                  </h4>
                  <span className="text-[11px] text-slate-400">Optional</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Commodity Category */}
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1 flex items-center gap-1.5">
                      <Tag size={13} className="text-slate-400" />
                      <span>Commodity Category</span>
                    </label>
                    <input
                      type="text"
                      value={commodityType}
                      onChange={(e) => setCommodityType(e.target.value)}
                      placeholder="e.g. Biscuits, Food, Soap, Cosmetics"
                      className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:border-emerald-500 bg-slate-50/50"
                    />
                  </div>

                  {/* Imported Commodity Toggle */}
                  <div className="flex items-start gap-3 p-3 rounded-xl border border-slate-200 bg-slate-50/50">
                    <input
                      type="checkbox"
                      id="importedCommodityToggle"
                      checked={isImported}
                      onChange={(e) => setIsImported(e.target.checked)}
                      className="w-4 h-4 rounded text-emerald-600 focus:ring-emerald-500 border-slate-300 mt-0.5 cursor-pointer"
                    />
                    <label htmlFor="importedCommodityToggle" className="text-xs text-slate-700 cursor-pointer">
                      <span className="font-bold text-navy-950 block">Imported Commodity</span>
                      <span className="text-[11px] text-slate-500 block leading-tight mt-0.5">
                        Enables Rule 6(10) importer and Country of Origin checks
                      </span>
                    </label>
                  </div>
                </div>
              </div>

              {/* Primary Action Button */}
              <div className="pt-2">
                <button
                  type="submit"
                  disabled={!selectedFile || isScanning}
                  className={`w-full inline-flex items-center justify-center gap-3 px-8 py-3.5 rounded-xl font-bold text-sm sm:text-base transition-all duration-200 shadow-md ${
                    selectedFile && !isScanning
                      ? 'bg-emerald-500 hover:bg-emerald-400 text-navy-950 shadow-emerald-500/25 hover:shadow-emerald-500/40 transform hover:-translate-y-0.5 cursor-pointer'
                      : 'bg-slate-200 text-slate-400 cursor-not-allowed border border-slate-300'
                  }`}
                >
                  <span>Scan Product</span>
                  <ArrowRight size={18} />
                </button>
              </div>

            </div>

          </div>

          {/* Right Column: Information & Quality Panel */}
          <div className="lg:col-span-4 space-y-5">
            
            {/* Card 1: Inspection Quality */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 shadow-2xs space-y-3.5">
              <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
                <div className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                  <Sparkles size={16} />
                </div>
                <h3 className="font-bold text-sm text-navy-950">
                  Inspection Quality
                </h3>
              </div>

              <ul className="space-y-3 text-xs text-slate-700">
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 size={16} className="text-emerald-600 mt-0.5 shrink-0" />
                  <span>Use a clear, well-lit product image</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 size={16} className="text-emerald-600 mt-0.5 shrink-0" />
                  <span>Keep label text readable</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 size={16} className="text-emerald-600 mt-0.5 shrink-0" />
                  <span>Avoid glare, blur and deep shadows</span>
                </li>
              </ul>
            </div>

            {/* Card 2: Verification Pipeline */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 shadow-2xs space-y-4">
              <div className="border-b border-slate-100 pb-3 flex items-center justify-between">
                <h3 className="font-bold text-sm text-navy-950">
                  Verification Pipeline
                </h3>
                <span className="text-[10px] font-mono text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-bold">
                  5 STAGES
                </span>
              </div>

              {/* Step Sequence */}
              <div className="flex items-center justify-between gap-1 text-[11px] font-mono font-bold text-slate-600">
                <span className="px-2 py-1 bg-slate-100 rounded text-navy-950">IMAGE</span>
                <span className="text-slate-300">→</span>
                <span className="px-2 py-1 bg-slate-100 rounded text-navy-950">OCR</span>
                <span className="text-slate-300">→</span>
                <span className="px-2 py-1 bg-slate-100 rounded text-navy-950">EXTRACT</span>
                <span className="text-slate-300">→</span>
                <span className="px-2 py-1 bg-slate-100 rounded text-navy-950">VERIFY</span>
                <span className="text-slate-300">→</span>
                <span className="px-2 py-1 bg-emerald-100 text-emerald-900 rounded">REPORT</span>
              </div>

              <p className="text-[11px] text-slate-500 leading-relaxed pt-1">
                From image capture to deterministic statutory evaluation against the Legal Metrology (Packaged Commodities) Rules, 2011.
              </p>
            </div>

            {/* Card 3: Trust Indicators */}
            <div className="bg-slate-50/80 rounded-2xl border border-slate-200/80 p-5 space-y-3">
              <div className="flex items-center gap-2.5 text-xs text-slate-700 font-semibold">
                <Cpu size={15} className="text-emerald-600 shrink-0" />
                <span>Local OCR processing</span>
              </div>
              <div className="flex items-center gap-2.5 text-xs text-slate-700 font-semibold">
                <Scale size={15} className="text-emerald-600 shrink-0" />
                <span>Deterministic rule validation</span>
              </div>
              <div className="flex items-center gap-2.5 text-xs text-slate-700 font-semibold">
                <FileCheck size={15} className="text-emerald-600 shrink-0" />
                <span>Audit-ready records</span>
              </div>
            </div>

          </div>

        </div>

      </form>

    </div>
  );
}
