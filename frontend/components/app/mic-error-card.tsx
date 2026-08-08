'use client';

import React from 'react';
import { Button } from '@/components/ui/button';

interface MicErrorCardProps {
  onRetry: () => void;
  className?: string;
}

export function MicErrorCard({ onRetry, className = '' }: MicErrorCardProps) {
  return (
    <div className={`relative flex min-h-svh w-full items-center justify-center ${className}`}>
      {/* Dark green immersive background matching welcome page */}
      <div
        className="absolute inset-0"
        style={{
          background: 'linear-gradient(135deg, #0a2218 0%, #1b4332 40%, #2d6a4f 70%, #1b4332 100%)',
        }}
      />

      <div
        className="relative z-10 mx-auto w-full max-w-sm overflow-hidden rounded-3xl p-8 text-center shadow-2xl backdrop-blur-xl"
        style={{
          background: 'rgba(255,255,255,0.06)',
          border: '1px solid rgba(239,68,68,0.3)',
          boxShadow:
            '0 8px 60px rgba(0,0,0,0.45), 0 0 0 1px rgba(239,68,68,0.15), inset 0 1px 0 rgba(255,255,255,0.06)',
        }}
      >
        {/* Top border glow */}
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-px"
          style={{
            background:
              'linear-gradient(90deg, transparent 0%, rgba(239,68,68,0.5) 50%, transparent 100%)',
          }}
        />

        {/* Icon */}
        <div
          className="relative mx-auto mb-5 flex h-20 w-20 items-center justify-center rounded-full text-4xl"
          style={{
            background:
              'linear-gradient(135deg, rgba(239,68,68,0.2) 0%, rgba(185,28,28,0.15) 100%)',
            border: '2px solid rgba(239,68,68,0.35)',
          }}
        >
          🎙️
        </div>

        <h3 className="text-xl font-extrabold text-white">Microphone Access Blocked</h3>
        <p className="mt-1 text-sm font-medium text-red-300">माइक की अनुमति अवरुद्ध है</p>

        <div className="my-4 h-px w-full bg-gradient-to-r from-transparent via-red-500/20 to-transparent" />

        <p className="text-sm leading-relaxed text-[#95d5b2]">
          Please enable microphone access in your browser address bar settings to talk with Krishi
          Mitra.
        </p>

        {/* Browser tip */}
        <div
          className="mt-4 rounded-xl px-4 py-3 text-xs font-medium text-[#e9c46a]"
          style={{ background: 'rgba(212,163,115,0.1)', border: '1px solid rgba(212,163,115,0.2)' }}
        >
          💡 Click the 🔒 lock or camera icon in your browser address bar, then select{' '}
          <strong>&quot;Allow Microphone&quot;</strong>.
        </div>

        <Button
          id="retry-connection-btn"
          size="lg"
          onClick={onRetry}
          className="group relative mt-5 w-full overflow-hidden rounded-full py-5 text-sm font-bold text-white transition-all duration-300"
          style={{
            background: 'linear-gradient(135deg, #2d6a4f 0%, #1b4332 100%)',
            border: '1px solid rgba(82,183,136,0.35)',
            boxShadow: '0 4px 20px rgba(45,106,79,0.45)',
          }}
        >
          <span className="pointer-events-none absolute inset-0 translate-x-[-100%] bg-gradient-to-r from-transparent via-white/10 to-transparent transition-transform duration-700 group-hover:translate-x-[100%]" />
          <span className="relative">🔄 Retry Connection / पुनः प्रयास करें</span>
        </Button>
      </div>
    </div>
  );
}
