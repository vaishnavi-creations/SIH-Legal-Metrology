import React, { useEffect, useState } from 'react';
import { PackSureLogo } from './PackSureLogo';
import { apiService } from '../services/api';
import { User, Menu, X } from 'lucide-react';

export function Navbar({ activeTab, onTabChange }) {
  const [backendOnline, setBackendOnline] = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    let isMounted = true;
    apiService.checkHealth()
      .then(() => {
        if (isMounted) setBackendOnline(true);
      })
      .catch(() => {
        if (isMounted) setBackendOnline(false);
      });
    return () => { isMounted = false; };
  }, []);

  const navItems = [
    { id: 'home', label: 'Home' },
    { id: 'inspect', label: 'New Inspection' },
    { id: 'history', label: 'Scan History' },
    { id: 'about', label: 'About' },
  ];

  const handleNavClick = (id) => {
    onTabChange(id);
    setMobileMenuOpen(false);
  };

  return (
    <header className="bg-[#071A2B] border-b border-[#0E2A44] text-white sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          
          {/* Left: PackSure Brand */}
          <div
            onClick={() => handleNavClick('home')}
            className="cursor-pointer transition-opacity hover:opacity-95"
          >
            <PackSureLogo size="md" showTagline={false} light={true} />
          </div>

          {/* Center: Premium SaaS Navigation */}
          <nav className="hidden md:flex items-center space-x-8 h-full">
            {navItems.map((item) => {
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item.id)}
                  className={`relative h-full flex items-center text-sm font-medium transition-colors cursor-pointer ${
                    isActive
                      ? 'text-white font-semibold'
                      : 'text-slate-300 hover:text-white'
                  }`}
                >
                  <span>{item.label}</span>
                  {isActive && (
                    <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-400 rounded-full shadow-[0_0_8px_rgba(24,184,137,0.6)]"></span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Right: Subtle System Status & User Profile */}
          <div className="hidden sm:flex items-center space-x-4">
            
            {/* Unobtrusive Micro Status Indicator */}
            <div className="flex items-center gap-2 text-xs text-slate-400 font-medium">
              <span className={`w-2 h-2 rounded-full ${
                backendOnline === true ? 'bg-emerald-400 ring-2 ring-emerald-400/20' : backendOnline === false ? 'bg-rose-400' : 'bg-slate-500'
              }`} />
              <span className="text-[12px] text-slate-400">
                {backendOnline === true ? 'API Live' : backendOnline === false ? 'API Offline' : 'Connecting...'}
              </span>
            </div>

            <div className="h-4 w-px bg-slate-700"></div>

            {/* Profile Avatar / Menu Icon */}
            <div
              className="w-8 h-8 rounded-full bg-[#0B2235] border border-slate-700/80 flex items-center justify-center text-slate-300 hover:text-white hover:border-emerald-500/50 transition-colors cursor-pointer"
              title="PackSure Inspection Officer"
            >
              <User size={15} />
            </div>

          </div>

          {/* Mobile Hamburger Button */}
          <div className="flex md:hidden items-center">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg text-slate-300 hover:text-white hover:bg-[#0B2235]"
              aria-label="Toggle Navigation"
            >
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>

        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-[#071A2B] border-b border-[#0E2A44] px-4 pt-2 pb-5 space-y-2">
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium text-left ${
                  isActive
                    ? 'bg-emerald-500/10 text-emerald-400 font-semibold'
                    : 'text-slate-300 hover:bg-[#0B2235]'
                }`}
              >
                <span>{item.label}</span>
                {isActive && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>}
              </button>
            );
          })}

          <div className="pt-3 mt-2 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400 px-2">
            <span>System Status:</span>
            <span className="flex items-center gap-1.5 font-medium text-slate-300">
              <span className={`w-2 h-2 rounded-full ${backendOnline ? 'bg-emerald-400' : 'bg-rose-400'}`} />
              {backendOnline ? 'API Connected' : 'API Offline'}
            </span>
          </div>
        </div>
      )}
    </header>
  );
}
