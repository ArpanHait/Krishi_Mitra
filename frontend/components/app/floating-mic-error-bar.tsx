'use client';

import React, { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';

interface FloatingMicErrorBarProps {
  onRetry: () => void;
  className?: string;
}

export function FloatingMicErrorBar({ onRetry, className = '' }: FloatingMicErrorBarProps) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    setVisible(true);
    const timer = setTimeout(() => {
      setVisible(false);
    }, 5000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div
      className={`fixed top-20 left-1/2 z-[150] w-full max-w-xl -translate-x-1/2 px-4 transition-all duration-500 md:top-24 ${
        visible
          ? 'translate-y-0 scale-100 opacity-100'
          : 'pointer-events-none -translate-y-4 scale-95 opacity-0'
      } ${className}`}
    >
      <div className="flex flex-col items-center justify-between gap-3 rounded-2xl border border-rose-500/50 bg-rose-950/95 px-5 py-3 shadow-2xl backdrop-blur-2xl sm:flex-row">
        <div className="flex items-center gap-3 text-left">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-xl border border-rose-500/40 bg-rose-500/30 text-lg shadow-inner">
            🎙️
          </div>
          <div>
            <h4 className="text-xs font-bold text-white sm:text-sm">
              Microphone Access Blocked 🎙️
            </h4>
            <p className="text-[11px] leading-tight text-rose-200">
              Please enable microphone access in your browser address bar settings.
            </p>
          </div>
        </div>

        <Button
          size="sm"
          onClick={() => {
            setVisible(true);
            onRetry();
          }}
          className="shrink-0 rounded-xl bg-gradient-to-r from-rose-600 to-red-700 px-4 py-2 text-xs font-bold text-white shadow-lg hover:from-rose-500 hover:to-red-600"
        >
          Retry Connection / पुनः प्रयास करें
        </Button>
      </div>
    </div>
  );
}
