'use client';

import React, { useState } from 'react';
import { TicketDashboard } from '@/components/app/ticket-dashboard';

interface AppHeaderProps {
  hidden?: boolean;
  className?: string;
}

export function AppHeader({ hidden = false, className = '' }: AppHeaderProps) {
  const [selectedLang, setSelectedLang] = useState<'hinglish' | 'english' | 'hindi' | 'bengali'>(
    'hinglish'
  );

  return (
    <header
      className={`fixed top-0 left-0 z-50 w-full p-4 transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] md:p-6 ${
        hidden
          ? 'pointer-events-none -translate-y-full scale-95 opacity-0'
          : 'translate-y-0 scale-100 opacity-100'
      } ${className}`}
    >
      <div className="mx-auto flex max-w-4xl flex-col items-center justify-between gap-3 rounded-2xl border border-white/15 bg-[#184e38]/60 px-5 py-3.5 shadow-2xl backdrop-blur-xl sm:flex-row">
        {/* Left: Brand Icon, Title & Track Pill */}
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#e9c46a] to-[#f4a261] text-xl font-bold text-[#261c14] shadow-md">
            🌾
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight text-white sm:text-lg">
                Krishi Mitra{' '}
                <span className="font-serif font-normal text-[#e9c46a]">(कृषि मित्र)</span>
              </h1>
              <span className="rounded-full border border-[#52b788]/40 bg-[#2d6a4f]/70 px-2.5 py-0.5 text-[10px] font-semibold tracking-wider text-[#74c69d] uppercase">
                Farm & Field Track
              </span>
            </div>
            <p className="text-xs font-medium text-slate-200">
              Voice-First Agricultural Assistant for Indian Farmers
            </p>
          </div>
        </div>

        {/* Right: Language Selector Pills & Ticket Dashboard */}
        <div className="flex items-center gap-3">
          <TicketDashboard buttonStyle="header-button" />

          <div className="flex rounded-xl border border-white/15 bg-black/40 p-1 text-xs">
            <button
              onClick={() => setSelectedLang('hinglish')}
              className={`rounded-lg px-3 py-1 font-semibold transition-all ${
                selectedLang === 'hinglish'
                  ? 'bg-[#2d6a4f] text-white shadow-md'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              Hinglish
            </button>
            <button
              onClick={() => setSelectedLang('english')}
              className={`rounded-lg px-3 py-1 font-semibold transition-all ${
                selectedLang === 'english'
                  ? 'bg-[#2d6a4f] text-white shadow-md'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              English
            </button>
            <button
              onClick={() => setSelectedLang('hindi')}
              className={`rounded-lg px-3 py-1 font-semibold transition-all ${
                selectedLang === 'hindi'
                  ? 'bg-[#2d6a4f] text-white shadow-md'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              हिन्दी
            </button>
            <button
              onClick={() => setSelectedLang('bengali')}
              className={`rounded-lg px-3 py-1 font-semibold transition-all ${
                selectedLang === 'bengali'
                  ? 'bg-[#2d6a4f] text-white shadow-md'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              বাংলা
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
