import React, { useState, useRef, useEffect } from 'react';
import {
  UploadCloud,
  Camera,
  Image as ImageIcon,
  X,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Tag,
  Sparkles,
  FileCheck,
  Cpu,
  Scale,
  Plus,
  Trash2
} from 'lucide-react';
import { formatFileSize } from '../utils/formatters';

const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024; // 15 MB
const ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp'];
const MAX_IMAGES = 6;

const VALID_ROLES = [
  { value: 'front', label: 'Front View (Principal Display)' },
  { value: 'back', label: 'Back View (Information Panel)' },
  { value: 'left', label: 'Left Side View' },
  { value: 'right', label: 'Right Side View' },
  { value: 'top', label: 'Top View' },
  { value: 'bottom', label: 'Bottom View' },
  { value: 'label', label: 'Nutrition / Detail Label' },
  { value: 'other', label: 'Other Package Face' },
];

export function ImageUploader({ onStartScan, isScanning }) {
  const [images, setImages] = useState([]);
  const [isImported, setIsImported] = useState(false);
  const [commodityType, setCommodityType] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  const fileInputRef = useRef(null);
  const addMoreInputRef = useRef(null);
  const imagesRef = useRef(images);
  imagesRef.current = images;

  // Clean up all object URLs when component unmounts to prevent memory leaks
  useEffect(() => {
    return () => {
      imagesRef.current.forEach(img => {
        if (img.previewUrl) {
          URL.revokeObjectURL(img.previewUrl);
        }
      });
    };
  }, []);

  const addFiles = (fileList) => {
    setErrorMsg(null);
    if (!fileList || fileList.length === 0) return;

    const remainingSlots = MAX_IMAGES - images.length;
    if (remainingSlots <= 0) {
      setErrorMsg(`Maximum limit of ${MAX_IMAGES} images reached.`);
      return;
    }

    const filesArray = Array.from(fileList);
    if (filesArray.length > remainingSlots) {
      setErrorMsg(`Only ${remainingSlots} more image(s) could be added (max ${MAX_IMAGES}).`);
    }

    const filesToProcess = filesArray.slice(0, remainingSlots);
    const newItems = [];
    const usedRoles = new Set(images.map(img => img.role));
    const rolePriority = ['front', 'back', 'label', 'left', 'right', 'top', 'bottom', 'other'];

    for (const file of filesToProcess) {
      const ext = '.' + (file.name.split('.').pop() || '').toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        setErrorMsg(`Unsupported file type (${ext}) for "${file.name}". Please select JPG, PNG, or WebP.`);
        continue;
      }

      if (file.size > MAX_FILE_SIZE_BYTES) {
        setErrorMsg(`"${file.name}" (${formatFileSize(file.size)}) exceeds maximum allowed limit of 15 MB.`);
        continue;
      }

      if (file.size === 0) {
        setErrorMsg(`"${file.name}" is empty (0 bytes). Please choose a valid image.`);
        continue;
      }

      // Pick next sensible default role
      let assignedRole = 'other';
      for (const r of rolePriority) {
        if (!usedRoles.has(r)) {
          assignedRole = r;
          usedRoles.add(r);
          break;
        }
      }

      newItems.push({
        id: `img_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
        file,
        previewUrl: URL.createObjectURL(file),
        role: assignedRole,
        sequence: images.length + newItems.length + 1
      });
    }

    if (newItems.length > 0) {
      setImages(prev => {
        const combined = [...prev, ...newItems];
        return combined.map((img, idx) => ({ ...img, sequence: idx + 1 }));
      });
    }

    if (fileInputRef.current) fileInputRef.current.value = '';
    if (addMoreInputRef.current) addMoreInputRef.current.value = '';
  };

  const handleFileChange = (e) => {
    if (e.target.files) {
      addFiles(e.target.files);
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
    if (e.dataTransfer.files) {
      addFiles(e.dataTransfer.files);
    }
  };

  const removeImage = (idToRemove) => {
    setErrorMsg(null);
    setImages(prev => {
      const target = prev.find(img => img.id === idToRemove);
      if (target && target.previewUrl) {
        URL.revokeObjectURL(target.previewUrl);
      }

      const filtered = prev.filter(img => img.id !== idToRemove);
      const renumbered = filtered.map((img, idx) => ({ ...img, sequence: idx + 1 }));

      // If the removed image was front and no remaining image has front, assign front to the first image
      if (renumbered.length > 0 && !renumbered.some(img => img.role === 'front')) {
        renumbered[0] = { ...renumbered[0], role: 'front' };
      }

      return renumbered;
    });
  };

  const handleRoleChange = (id, newRole) => {
    setImages(prev => prev.map(img => (img.id === id ? { ...img, role: newRole } : img)));
  };

  const clearAllImages = () => {
    images.forEach(img => {
      if (img.previewUrl) URL.revokeObjectURL(img.previewUrl);
    });
    setImages([]);
    setErrorMsg(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (addMoreInputRef.current) addMoreInputRef.current.value = '';
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (images.length === 0) {
      setErrorMsg('Please select or drag at least one image of a packaged commodity to inspect.');
      return;
    }
    // Backward-compatible invocation: passes primary file first, while also providing the image queue
    const primaryFile = images[0].file;
    onStartScan(primaryFile, isImported, commodityType, images);
  };

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
          Upload 1 to 6 packaging face views to extract mandatory declarations and verify Legal Metrology compliance with multi-image evidence fusion.
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
                    {images.length === 0 ? 'Upload Product Label(s)' : 'Package Face Views'}
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
                    {images.length === 0
                      ? 'Drop 1 to 6 package face images or browse from your device'
                      : `${images.length} of ${MAX_IMAGES} view${images.length > 1 ? 's' : ''} queued for multi-image evidence fusion`}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {images.length > 0 && (
                    <button
                      type="button"
                      onClick={clearAllImages}
                      className="text-xs font-semibold text-rose-600 hover:text-rose-800 px-2.5 py-1 rounded hover:bg-rose-50 transition-colors cursor-pointer"
                    >
                      Clear All
                    </button>
                  )}
                  <span className="text-[11px] font-mono font-bold uppercase text-slate-500 bg-slate-100 px-2 py-1 rounded">
                    {images.length > 0 ? `${images.length}/${MAX_IMAGES} Views` : 'Max 15 MB / View'}
                  </span>
                </div>
              </div>

              {/* Upload Dropzone (When No Images Selected) */}
              {images.length === 0 ? (
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
                    multiple
                    accept=".jpg,.jpeg,.png,.webp"
                    onChange={handleFileChange}
                    className="hidden"
                  />

                  <div className="w-16 h-16 rounded-2xl bg-emerald-50 border border-emerald-100 text-emerald-600 flex items-center justify-center mb-4 shadow-sm group-hover:scale-105 transition-transform">
                    <Camera size={32} />
                  </div>

                  <h3 className="text-base sm:text-lg font-bold text-navy-900">
                    Upload Package Face Views
                  </h3>

                  <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-md">
                    Drop package images here or{' '}
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
                    Select 1 to 6 views (Front, Back, Sides, Label) • JPG, PNG, WEBP • Max 15 MB each
                  </p>
                </div>
              ) : (
                /* Multi-Image Queue Display */
                <div className="space-y-4">
                  <div className="space-y-3">
                    {images.map((img) => (
                      <div
                        key={img.id}
                        className="p-3.5 sm:p-4 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-white transition-colors flex items-center gap-3.5 sm:gap-4 shadow-2xs"
                      >
                        {/* Sequence Badge */}
                        <div className="shrink-0 flex flex-col items-center justify-center w-8 h-8 rounded-lg bg-navy-950 text-emerald-400 font-mono text-xs font-bold shadow-2xs">
                          <span>#{img.sequence}</span>
                        </div>

                        {/* Thumbnail */}
                        <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-lg bg-navy-950 border border-slate-200 overflow-hidden shrink-0 flex items-center justify-center shadow-xs">
                          {img.previewUrl ? (
                            <img
                              src={img.previewUrl}
                              alt={`View #${img.sequence}`}
                              className="w-full h-full object-contain p-1"
                            />
                          ) : (
                            <ImageIcon size={24} className="text-slate-400" />
                          )}
                        </div>

                        {/* File Details & Role Selector */}
                        <div className="flex-1 min-w-0 space-y-1.5">
                          <div className="flex items-center gap-2">
                            <h4 className="text-xs sm:text-sm font-bold text-navy-950 truncate max-w-xs sm:max-w-md">
                              {img.file.name}
                            </h4>
                            <span className="text-[10px] font-mono text-slate-400 hidden sm:inline">
                              {formatFileSize(img.file.size)}
                            </span>
                          </div>

                          <div className="flex flex-wrap items-center gap-2">
                            <label className="text-[11px] font-bold text-slate-600 uppercase tracking-wider shrink-0">
                              Package Role:
                            </label>
                            <select
                              value={img.role}
                              onChange={(e) => handleRoleChange(img.id, e.target.value)}
                              className="text-xs font-semibold px-2.5 py-1 rounded-lg border border-slate-200 bg-white text-navy-950 focus:outline-none focus:border-emerald-500 shadow-2xs cursor-pointer"
                            >
                              {VALID_ROLES.map((r) => (
                                <option key={r.value} value={r.value}>
                                  {r.label}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>

                        {/* Remove Action */}
                        <button
                          type="button"
                          onClick={() => removeImage(img.id)}
                          className="p-2 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer shrink-0"
                          title="Remove view"
                          aria-label={`Remove view #${img.sequence}`}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    ))}
                  </div>

                  {/* Add More Views Control (if under 6 images) */}
                  {images.length < MAX_IMAGES && (
                    <div className="pt-2">
                      <input
                        ref={addMoreInputRef}
                        type="file"
                        multiple
                        accept=".jpg,.jpeg,.png,.webp"
                        onChange={handleFileChange}
                        className="hidden"
                      />
                      <button
                        type="button"
                        onClick={() => addMoreInputRef.current && addMoreInputRef.current.click()}
                        className="w-full py-3 px-4 rounded-xl border-2 border-dashed border-slate-300 hover:border-emerald-500 hover:bg-emerald-50/30 text-slate-600 hover:text-emerald-800 text-xs sm:text-sm font-semibold transition-all flex items-center justify-center gap-2 cursor-pointer"
                      >
                        <Plus size={16} className="text-emerald-600" />
                        <span>Add Another Package View ({images.length}/{MAX_IMAGES})</span>
                      </button>
                    </div>
                  )}

                  {images.length >= MAX_IMAGES && (
                    <p className="text-[11px] text-center text-slate-400 font-mono pt-1">
                      Maximum of {MAX_IMAGES} package face views reached.
                    </p>
                  )}
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
                  disabled={images.length === 0 || isScanning}
                  className={`w-full inline-flex items-center justify-center gap-3 px-8 py-3.5 rounded-xl font-bold text-sm sm:text-base transition-all duration-200 shadow-md ${
                    images.length > 0 && !isScanning
                      ? 'bg-emerald-500 hover:bg-emerald-400 text-navy-950 shadow-emerald-500/25 hover:shadow-emerald-500/40 transform hover:-translate-y-0.5 cursor-pointer'
                      : 'bg-slate-200 text-slate-400 cursor-not-allowed border border-slate-300'
                  }`}
                >
                  <span>
                    {images.length > 1
                      ? `Scan Product (${images.length} Package Views)`
                      : 'Scan Product'}
                  </span>
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
                  <span>Upload all available package faces (Front, Back, Sides)</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 size={16} className="text-emerald-600 mt-0.5 shrink-0" />
                  <span>Ensure text and declarations are sharp and readable</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 size={16} className="text-emerald-600 mt-0.5 shrink-0" />
                  <span>Avoid glare, blur, and deep shadows across angles</span>
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
                <span className="px-2 py-1 bg-slate-100 rounded text-navy-950">VIEWS</span>
                <span className="text-slate-300">→</span>
                <span className="px-2 py-1 bg-slate-100 rounded text-navy-950">OCR</span>
                <span className="text-slate-300">→</span>
                <span className="px-2 py-1 bg-slate-100 rounded text-navy-950">FUSION</span>
                <span className="text-slate-300">→</span>
                <span className="px-2 py-1 bg-slate-100 rounded text-navy-950">VERIFY</span>
                <span className="text-slate-300">→</span>
                <span className="px-2 py-1 bg-emerald-100 text-emerald-900 rounded">REPORT</span>
              </div>

              <p className="text-[11px] text-slate-500 leading-relaxed pt-1">
                Multi-face image evidence is normalized and corroborated across package views against the Legal Metrology Rules, 2011.
              </p>
            </div>

            {/* Card 3: Trust Indicators */}
            <div className="bg-slate-50/80 rounded-2xl border border-slate-200/80 p-5 space-y-3">
              <div className="flex items-center gap-2.5 text-xs text-slate-700 font-semibold">
                <Cpu size={15} className="text-emerald-600 shrink-0" />
                <span>Multi-Image Evidence Fusion</span>
              </div>
              <div className="flex items-center gap-2.5 text-xs text-slate-700 font-semibold">
                <Scale size={15} className="text-emerald-600 shrink-0" />
                <span>Deterministic rule validation</span>
              </div>
              <div className="flex items-center gap-2.5 text-xs text-slate-700 font-semibold">
                <FileCheck size={15} className="text-emerald-600 shrink-0" />
                <span>Cross-image corroboration audit</span>
              </div>
            </div>

          </div>

        </div>

      </form>

    </div>
  );
}
