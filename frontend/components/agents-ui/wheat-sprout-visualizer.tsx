'use client';

import React, { useEffect, useRef, useState } from 'react';
import type { LocalAudioTrack, RemoteAudioTrack } from 'livekit-client';
import {
  type TrackReferenceOrPlaceholder,
  useMultibandTrackVolume,
} from '@livekit/components-react';

export type AgentVisualizerState =
  | 'ready'
  | 'connecting'
  | 'listening'
  | 'speaking'
  | 'disconnected';

interface WheatSproutVisualizerProps {
  state: AgentVisualizerState;
  audioTrack?: TrackReferenceOrPlaceholder | LocalAudioTrack | RemoteAudioTrack;
  barCount?: number;
  isChatOpen?: boolean;
  className?: string;
}

// 8 curved Wheat stalk base heights (matching Image 1 & Image 3)
const BASE_HEIGHTS = [40, 60, 85, 120, 120, 85, 60, 40];

// Stalk widths (centre stalks thicker)
const STALK_WIDTHS = [16, 18, 20, 24, 24, 20, 18, 16];

// Wheat grain tip triangle component (matching Image 1 & Image 3)
function WheatGrainTip({ isCentre }: { isCentre: boolean }) {
  return (
    <div className="mb-1 flex flex-col items-center gap-0.5">
      {/* Top small grain triangle */}
      <div
        className="h-0 w-0 border-r-[4px] border-b-[6px] border-l-[4px] border-r-transparent border-b-[#e9c46a] border-l-transparent"
        style={{ filter: isCentre ? 'drop-shadow(0 0 3px #e9c46a)' : 'none' }}
      />
      {/* Main grain triangle */}
      <div
        className="h-0 w-0 border-r-[6px] border-b-[8px] border-l-[6px] border-r-transparent border-b-[#f4a261] border-l-transparent"
        style={{ filter: isCentre ? 'drop-shadow(0 0 4px #f4a261)' : 'none' }}
      />
    </div>
  );
}

export function WheatSproutVisualizer({
  state,
  audioTrack,
  barCount = 8,
  isChatOpen = false,
  className = '',
}: WheatSproutVisualizerProps) {
  const volumes = useMultibandTrackVolume(audioTrack, {
    bands: barCount,
    loPass: 100,
    hiPass: 600,
  });

  const [heights, setHeights] = useState<number[]>(() => [...BASE_HEIGHTS]);
  const rafRef = useRef<number | null>(null);
  const stateRef = useRef(state);
  const volRef = useRef<Float32Array | number[]>(volumes ?? []);

  stateRef.current = state;
  volRef.current = volumes ?? [];

  useEffect(() => {
    const animate = () => {
      const now = Date.now();
      const s = stateRef.current;
      const vols = volRef.current;

      const next = Array.from({ length: barCount }, (_, i) => {
        const base = BASE_HEIGHTS[i % BASE_HEIGHTS.length];
        const rawVol = (vols[i] ?? 0) as number;

        if (s === 'speaking') {
          // Dynamic bouncing synced directly to audio volume intensity & wave phase
          const wavePhase = Math.sin(now / 80 + i * 1.8) * 0.5 + 0.5;
          const volBoost = Math.min(1.0, Math.max(0, rawVol)) * 80;
          const bounceHeight = base + wavePhase * 30 + volBoost;
          return Math.min(160, Math.max(35, bounceHeight));
        }

        if (s === 'listening') {
          // Gentle breathing sway
          const breathing = base + Math.sin(now / 350 + i * 0.8) * 10;
          return Math.max(25, breathing);
        }

        if (s === 'connecting') {
          // Wave pulse
          const wave = Math.sin(now / 200 + i * 1.2) * 18 + 40;
          return Math.max(20, wave);
        }

        // Ready / Disconnected ambient flow (never stays static or frozen on landing!)
        const ambientFlow = base + Math.sin(now / 350 + i * 0.7) * 8;
        return Math.max(25, ambientFlow);
      });

      setHeights(next);
      rafRef.current = requestAnimationFrame(animate);
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [barCount]);

  return (
    // Note: opacity: 0.45 = 55% transparent / 45% visible when chat box is open.
    // Change 0.45 below to adjust transparency (e.g., 0.6 = 40% transparent, 0.3 = 70% transparent)
    <div
      className={`relative flex flex-col items-center justify-end py-4 transition-all duration-300 ${
        isChatOpen ? 'pointer-events-none' : ''
      } ${className}`}
      style={{
        opacity: isChatOpen ? 1.0 : 1,
        transition: 'opacity 300ms ease, transform 300ms ease',
      }}
    >
      {/* Ambient Radial Glow behind visualizer */}
      <div
        className="pointer-events-none absolute inset-0 m-auto rounded-full transition-all duration-500"
        style={{
          width: state === 'speaking' ? 260 : 200,
          height: state === 'speaking' ? 260 : 200,
          background:
            state === 'speaking'
              ? 'radial-gradient(circle, rgba(233,196,106,0.25) 0%, rgba(82,183,136,0.15) 50%, transparent 70%)'
              : 'radial-gradient(circle, rgba(82,183,136,0.18) 0%, transparent 70%)',
          filter: 'blur(30px)',
          opacity: isChatOpen ? 0.45 : 1,
        }}
      />

      {/* 8 Wheat Stalks Container */}
      <div
        className="relative flex items-end justify-center gap-2 px-4 sm:gap-3.5"
        style={{
          height: 210,
          opacity: isChatOpen ? 0.45 : 1,
          transition: 'opacity 300ms ease',
        }}
      >
        {Array.from({ length: barCount }).map((_, i) => {
          const h = heights[i] ?? BASE_HEIGHTS[i];
          const w = STALK_WIDTHS[i % STALK_WIDTHS.length];
          const isCentre = i === 3 || i === 4;

          return (
            <div
              key={i}
              className="flex flex-col items-center"
              style={{
                height: `${h}px`,
                transition: 'height 80ms ease-out',
                willChange: 'height',
              }}
            >
              {/* Golden Wheat Grain Pyramid Tip */}
              <WheatGrainTip isCentre={isCentre} />

              {/* Rounded Stalk Stem */}
              <div
                className="w-full flex-1 rounded-t-full shadow-lg"
                style={{
                  width: `${w}px`,
                  background:
                    'linear-gradient(to top, #2d6a4f 0%, #52b788 50%, #f4a261 85%, #e9c46a 100%)',
                  boxShadow:
                    state === 'speaking'
                      ? '0 0 10px 2px rgba(233,196,106,0.35)'
                      : '0 2px 6px rgba(0,0,0,0.25)',
                  opacity: isChatOpen ? 0.45 : 1,
                }}
              />
            </div>
          );
        })}
      </div>

      {/* Soil Bed Base Bar (Image 1 & Image 3) */}
      <div
        className="mt-1 h-[8px] w-full max-w-[340px] rounded-full shadow-md"
        style={{
          background: 'linear-gradient(to right, #261c14, #44331e 50%, #261c14)',
          borderTop: '1px solid rgba(233,196,106,0.3)',
          opacity: isChatOpen ? 0.45 : 1,
        }}
      />
    </div>
  );
}
