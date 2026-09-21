import React from 'react';

/**
 * PackSure brand mark:
 * An elegant geometric package silhouette combined with a precision verification checkmark.
 * Minimal, recognizable, professional, and scalable.
 */
export function PackSureLogo({ size = 'md', showTagline = false, light = true }) {
  const iconSizes = {
    sm: 'w-7 h-7',
    md: 'w-8 h-8',
    lg: 'w-10 h-10',
  };

  const textSizes = {
    sm: 'text-base',
    md: 'text-lg',
    lg: 'text-2xl',
  };

  return (
    <div className="flex items-center gap-2.5 select-none">
      {/* Precision Geometric Logo Icon */}
      <div className={`relative ${iconSizes[size]} shrink-0 rounded-lg bg-[#071A2B] border border-emerald-500/40 p-1 flex items-center justify-center shadow-xs`}>
        <svg
          viewBox="0 0 32 32"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full"
        >
          {/* Outer Package / Hexagonal Box Contour */}
          <path
            d="M16 3.5L27 9.5V22.5L16 28.5L5 22.5V9.5L16 3.5Z"
            fill="#0B2235"
            stroke="#18B889"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
          {/* Top Package Flap / Fold Line */}
          <path
            d="M5 9.5L16 15.5L27 9.5"
            stroke="#18B889"
            strokeWidth="1.2"
            strokeOpacity="0.5"
            strokeLinejoin="round"
          />
          {/* Center Vertical Package Fold */}
          <path
            d="M16 15.5V28.5"
            stroke="#18B889"
            strokeWidth="1.2"
            strokeOpacity="0.5"
          />
          {/* Verification Checkmark */}
          <path
            d="M10.5 15.5L14.5 19.5L22 11"
            stroke="#20C997"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      {/* Brand Typography */}
      <div className="flex flex-col leading-tight">
        <span className={`font-bold tracking-tight ${textSizes[size]} ${light ? 'text-white' : 'text-slate-900'}`}>
          Pack<span className="text-emerald-400 font-extrabold">Sure</span>
        </span>
        {showTagline && (
          <span className="text-[11px] font-medium tracking-wide text-slate-400">
            Check. Verify. Comply.
          </span>
        )}
      </div>
    </div>
  );
}
