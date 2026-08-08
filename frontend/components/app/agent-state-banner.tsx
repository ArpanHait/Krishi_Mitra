'use client';

import React from 'react';
import type { LocalAudioTrack, RemoteAudioTrack } from 'livekit-client';
import { WheatSproutVisualizer } from '@/components/agents-ui/wheat-sprout-visualizer';
import { Button } from '@/components/ui/button';

export type AgentStateMode = 'ready' | 'connecting' | 'listening' | 'speaking' | 'call_ended';

interface AgentStateBannerProps {
  state: AgentStateMode;
  onStartCall: () => void;
  audioTrack?: LocalAudioTrack | RemoteAudioTrack;
  className?: string;
}

export function AgentStateBanner({
  state,
  onStartCall,
  audioTrack,
  className = '',
}: AgentStateBannerProps) {
  return (
    <div
      className={`mx-auto w-full max-w-lg rounded-2xl border border-[#2d6a4f]/20 bg-white/95 p-6 text-center shadow-xl backdrop-blur-md transition-all duration-300 dark:bg-[#1b4332]/90 ${className}`}
    >
      {/* 1. READY STATE */}
      {state === 'ready' && (
        <div className="flex flex-col items-center gap-4">
          <div className="flex size-16 items-center justify-center rounded-full border border-[#2d6a4f]/30 bg-[#f4f9f4] text-3xl shadow-inner dark:bg-[#2d6a4f]/30">
            🌾
          </div>
          <div>
            <h2 className="text-xl font-bold text-[#1b4332] dark:text-emerald-300">
              Krishi Mitra 🌾 (कृषि मित्र)
            </h2>
            <p className="mt-1 text-sm font-medium text-[#2d6a4f]/80 dark:text-emerald-200/80">
              Your Voice-First Agricultural Assistant
            </p>
          </div>
          <Button
            size="lg"
            onClick={onStartCall}
            className="mt-2 w-full max-w-xs rounded-full bg-[#2d6a4f] font-semibold text-white shadow-lg transition-all duration-200 hover:bg-[#1b4332] hover:shadow-emerald-900/20"
          >
            Start Conversation / बात शुरू करें
          </Button>
        </div>
      )}

      {/* 2. CONNECTING STATE */}
      {state === 'connecting' && (
        <div className="flex flex-col items-center gap-4 py-2">
          <div className="relative flex items-center justify-center">
            <div className="size-14 animate-spin rounded-full border-4 border-[#2d6a4f]/20 border-t-[#2d6a4f]" />
            <span className="absolute text-xl">🌾</span>
          </div>
          <div>
            <span className="mb-2 inline-block rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">
              Connecting / जुड़ रहे हैं...
            </span>
            <p className="text-base font-semibold text-[#1b4332] dark:text-emerald-200">
              Connecting to Krishi Mitra... Please wait.
            </p>
          </div>
        </div>
      )}

      {/* 3. LISTENING STATE */}
      {state === 'listening' && (
        <div className="flex flex-col items-center gap-4 py-2">
          <div className="relative flex items-center justify-center">
            <div className="absolute size-16 animate-ping rounded-full bg-[#52b788]/20" />
            <div className="relative z-10 flex size-14 items-center justify-center rounded-full bg-[#2d6a4f] text-2xl text-white shadow-md">
              🎙️
            </div>
          </div>
          <div>
            <span className="mb-2 inline-block rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
              Listening / सुन रहे हैं
            </span>
            <p className="text-base font-semibold text-[#1b4332] dark:text-emerald-200">
              Listening to you... Speak now.
            </p>
          </div>
          <WheatSproutVisualizer state="listening" barCount={7} />
        </div>
      )}

      {/* 4. SPEAKING STATE */}
      {state === 'speaking' && (
        <div className="flex flex-col items-center gap-3">
          <span className="inline-block rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
            Speaking / बोल रहे हैं
          </span>
          <p className="text-base font-semibold text-[#1b4332] dark:text-emerald-200">
            Krishi Mitra is speaking...
          </p>
          <WheatSproutVisualizer state="speaking" audioTrack={audioTrack} barCount={7} />
        </div>
      )}

      {/* 5. CALL ENDED STATE */}
      {state === 'call_ended' && (
        <div className="flex flex-col items-center gap-4 py-2">
          <div className="flex size-16 items-center justify-center rounded-full border border-amber-200 bg-amber-50 text-3xl dark:border-amber-800 dark:bg-amber-950/40">
            🤝
          </div>
          <div>
            <span className="mb-2 inline-block rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-900/60 dark:text-amber-300">
              Call Ended / बातचीत समाप्त
            </span>
            <p className="text-sm font-medium text-gray-600 dark:text-gray-300">
              Thank you for consulting Krishi Mitra! Hope your farm thrives.
            </p>
          </div>
          <Button
            size="lg"
            onClick={onStartCall}
            className="mt-2 w-full max-w-xs rounded-full bg-[#2d6a4f] font-semibold text-white shadow-lg transition-all duration-200 hover:bg-[#1b4332] hover:shadow-emerald-900/20"
          >
            Start New Call / नई कॉल शुरू करें
          </Button>
        </div>
      )}
    </div>
  );
}
