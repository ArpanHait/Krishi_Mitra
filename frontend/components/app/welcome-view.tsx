'use client';

import React from 'react';
import { WheatSproutVisualizer } from '@/components/agents-ui/wheat-sprout-visualizer';
import { Button } from '@/components/ui/button';

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
  onMicError?: () => void;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  onMicError,
  ref,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  const [isConnecting, setIsConnecting] = React.useState(false);

  const handleStart = async () => {
    setIsConnecting(true);
    try {
      if (
        typeof window !== 'undefined' &&
        navigator.mediaDevices &&
        navigator.mediaDevices.getUserMedia
      ) {
        await navigator.mediaDevices.getUserMedia({ audio: true });
      }
      onStartCall();
    } catch (err: unknown) {
      setIsConnecting(false);
      console.error('Microphone permission rejected:', err);
      if (onMicError) {
        onMicError();
      } else {
        alert(
          'Microphone Access Blocked 🎙️\n\nPlease enable microphone access in your browser settings to talk with Krishi Mitra.'
        );
      }
    }
  };

  return (
    <div
      ref={ref}
      className="relative flex min-h-svh w-full transform-gpu flex-col items-center justify-center p-3 pt-32 pb-8 will-change-[opacity,transform] sm:p-6 sm:pt-36 md:pt-40"
      style={{
        background: 'linear-gradient(135deg, #0f2e1e 0%, #1e4d38 50%, #12281c 100%)',
      }}
    >
      {/* Central Glass Card */}
      <main className="my-auto w-full max-w-2xl">
        <div
          className="relative flex transform-gpu flex-col items-center overflow-hidden rounded-3xl p-6 shadow-2xl backdrop-blur-xl transition-all duration-300 sm:p-8"
          style={{
            background: 'rgba(255, 255, 255, 0.08)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            boxShadow: '0 0 50px rgba(82, 183, 136, 0.18)',
          }}
        >
          {/* Status Badge Pill */}
          <div className="mb-4 flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900/80 px-4 py-1.5 text-xs font-semibold text-slate-200 shadow">
            <span
              className={`h-2.5 w-2.5 rounded-full transition-all duration-300 ${
                isConnecting ? 'animate-pulse bg-emerald-400' : 'bg-slate-400'
              }`}
            />
            <span>
              {isConnecting
                ? 'Connecting to Krishi Mitra...'
                : 'Ready — Tap below to start conversation'}
            </span>
          </div>

          {/* 8-Stalk Wheat Visualizer Area */}
          <div className="my-2 w-full max-w-sm">
            <WheatSproutVisualizer state={isConnecting ? 'connecting' : 'ready'} barCount={8} />
          </div>

          {/* Transcript Preview Box */}
          <div
            className="mt-4 flex max-h-44 w-full flex-col gap-2.5 overflow-y-auto rounded-2xl p-4 text-slate-800 shadow-inner"
            style={{
              background: 'rgba(255, 255, 255, 0.94)',
              backdropFilter: 'blur(12px)',
            }}
          >
            <div className="flex items-center justify-between border-b border-slate-200 pb-1 text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
              <span className="flex items-center gap-1.5">💬 Live Transcript Stream</span>
              <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                Hinglish UI / Voice Engine Linked
              </span>
            </div>

            <div className="flex flex-col gap-2 text-xs sm:text-sm">
              <div className="flex items-start gap-2 text-slate-700">
                <span className="mt-0.5 shrink-0 rounded-lg bg-[#2d6a4f] px-2 py-0.5 text-[11px] font-bold text-white">
                  Krishi Mitra
                </span>
                <p className="leading-relaxed">
                  <span className="font-semibold">Namaste!</span> Main Krishi Mitra hoon. Aaj aapki
                  fasal, mitti ya sarkari yojnaon me kaise madad kar sakta hoon?
                </p>
              </div>
            </div>
          </div>

          {/* Primary Action Button */}
          <div className="mt-6 flex w-full flex-col items-center">
            <Button
              id="start-conversation-btn"
              size="lg"
              disabled={isConnecting}
              onClick={handleStart}
              className="w-full transform-gpu rounded-2xl bg-gradient-to-r from-[#2d6a4f] to-[#52b788] py-6 text-base font-bold text-white shadow-xl transition-all duration-300 will-change-transform hover:from-emerald-600 hover:to-teal-500 hover:shadow-emerald-500/25 active:scale-95 sm:w-auto sm:px-10"
            >
              {isConnecting ? (
                <>
                  <span className="inline-block animate-spin text-lg">⏳</span>
                  Connecting voice pipeline...
                </>
              ) : (
                <>
                  <span className="text-lg">🎙️</span>
                  {startButtonText}
                </>
              )}
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
};
