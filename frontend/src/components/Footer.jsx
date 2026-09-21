import React from 'react';
import { PackSureLogo } from './PackSureLogo';
import { ShieldCheck, Scale, ExternalLink } from 'lucide-react';

export function Footer({ onTabChange }) {
  return (
    <footer className="bg-navy-900 border-t border-navy-800 text-slate-400 text-xs py-10 mt-16 select-none">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Upper Row: Brand, Tagline, Navigation */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-6 pb-8 border-b border-navy-800/80">
          
          <div className="flex flex-col sm:flex-row items-center gap-4 text-center sm:text-left">
            <PackSureLogo size="md" showTagline={true} light={true} />
            <div className="hidden sm:block h-8 w-px bg-navy-800"></div>
            <p className="text-xs text-slate-400 max-w-sm">
              AI-powered statutory compliance verification for packaged commodities across India.
            </p>
          </div>

          {/* Navigation Links */}
          <nav className="flex flex-wrap items-center justify-center gap-6 text-sm font-medium text-slate-300">
            <button
              onClick={() => onTabChange('home')}
              className="hover:text-emerald-400 transition-colors"
            >
              Home
            </button>
            <button
              onClick={() => onTabChange('inspect')}
              className="hover:text-emerald-400 transition-colors"
            >
              New Inspection
            </button>
            <button
              onClick={() => onTabChange('history')}
              className="hover:text-emerald-400 transition-colors"
            >
              Scan History
            </button>
            <button
              onClick={() => onTabChange('about')}
              className="hover:text-emerald-400 transition-colors"
            >
              About Rules
            </button>
          </nav>
        </div>

        {/* Lower Row: Statutory Context & Copyright */}
        <div className="pt-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px] text-slate-500">
          
          <div className="flex items-center gap-2">
            <Scale size={14} className="text-emerald-500 shrink-0" />
            <span>
              Evaluated strictly under the <span className="text-slate-400 font-medium">Legal Metrology (Packaged Commodities) Rules, 2011</span> and 2021/2022 Amendment Gazettes.
            </span>
          </div>

          <div className="flex items-center gap-4 text-slate-500">
            <span>PackSure LegalTech Platform</span>
            <span>•</span>
            <span>Zero Hallucination Deterministic Engine</span>
          </div>

        </div>

      </div>
    </footer>
  );
}
