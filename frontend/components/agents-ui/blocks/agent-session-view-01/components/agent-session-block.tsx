'use client';

import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, type MotionProps, motion } from 'motion/react';
import {
  useAgent,
  useLocalParticipant,
  useSessionContext,
  useSessionMessages,
} from '@livekit/components-react';
import { AgentChatTranscript } from '@/components/agents-ui/agent-chat-transcript';
import {
  AgentControlBar,
  type AgentControlBarControls,
} from '@/components/agents-ui/agent-control-bar';
import { Shimmer } from '@/components/ai-elements/shimmer';
import { FloatingMicErrorBar } from '@/components/app/floating-mic-error-bar';
import { cn } from '@/lib/shadcn/utils';
import { TileLayout } from './tile-view';

const MotionMessage = motion.create(Shimmer);

const BOTTOM_VIEW_MOTION_PROPS: MotionProps = {
  variants: {
    visible: { opacity: 1, translateY: '0%' },
    hidden: { opacity: 0, translateY: '100%' },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: { duration: 0.35, delay: 0.4, ease: 'easeOut' },
};

const CHAT_MOTION_PROPS: MotionProps = {
  variants: {
    hidden: { opacity: 0, transition: { ease: 'easeOut', duration: 0.25 } },
    visible: { opacity: 1, transition: { delay: 0.2, ease: 'easeOut', duration: 0.25 } },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
};

const SHIMMER_MOTION_PROPS: MotionProps = {
  variants: {
    visible: { opacity: 1, transition: { ease: 'easeIn', duration: 0.4, delay: 0.7 } },
    hidden: { opacity: 0, transition: { ease: 'easeIn', duration: 0.4, delay: 0 } },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
};

interface FadeProps {
  top?: boolean;
  bottom?: boolean;
  className?: string;
}

export function Fade({ top = false, bottom = false, className }: FadeProps) {
  return (
    <div
      className={cn(
        'from-background pointer-events-none h-4 bg-linear-to-b to-transparent',
        top && 'bg-linear-to-b',
        bottom && 'bg-linear-to-t',
        className
      )}
    />
  );
}

// ─── Compact State Pill (matching demo design) ───
// Small rounded-full pill with colored dot + state text
function StatePill({
  agentState,
  chatOpen = false,
}: {
  agentState: string | undefined;
  chatOpen?: boolean;
}) {
  const config = (() => {
    switch (agentState) {
      case 'connecting':
      case 'initializing':
        return {
          bg: 'rgba(245,158,11,0.15)',
          border: 'rgba(245,158,11,0.3)',
          dotColor: '#f59e0b',
          dotAnim: 'animate-ping',
          text: 'Connecting to Krishi Mitra... Please wait',
        };
      case 'listening':
        return {
          bg: 'rgba(52,211,153,0.15)',
          border: 'rgba(52,211,153,0.3)',
          dotColor: '#34d399',
          dotAnim: 'animate-pulse',
          text: 'Listening to you... Speak now',
        };
      case 'speaking':
        return {
          bg: 'rgba(94,234,212,0.12)',
          border: 'rgba(94,234,212,0.3)',
          dotColor: '#5eead4',
          dotAnim: 'animate-bounce',
          text: 'Agent is speaking... / जवाब दे रहे हैं',
        };
      case 'thinking':
        return {
          bg: 'rgba(168,162,158,0.12)',
          border: 'rgba(168,162,158,0.25)',
          dotColor: '#a8a29e',
          dotAnim: 'animate-pulse',
          text: 'Thinking... / सोच रहे हैं',
        };
      default:
        return {
          bg: 'rgba(100,116,139,0.15)',
          border: 'rgba(100,116,139,0.2)',
          dotColor: '#94a3b8',
          dotAnim: '',
          text: 'Ready — Tap below to start',
        };
    }
  })();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={agentState}
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: 0.25 }}
        className={cn(
          'pointer-events-none absolute left-1/2 z-50 -translate-x-1/2 transition-all duration-300',
          chatOpen ? 'top-3' : 'top-24 md:top-28'
        )}
      >
        <div
          className="flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-semibold shadow-lg backdrop-blur-md"
          style={{
            background: config.bg,
            border: `1px solid ${config.border}`,
            color: config.dotColor,
          }}
        >
          <span
            className={`h-2.5 w-2.5 rounded-full ${config.dotAnim}`}
            style={{ backgroundColor: config.dotColor }}
          />
          <span className="text-slate-200">{config.text}</span>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

export interface AgentSessionView_01Props {
  preConnectMessage?: string;
  supportsChatInput?: boolean;
  supportsVideoInput?: boolean;
  supportsScreenShare?: boolean;
  isPreConnectBufferEnabled?: boolean;
  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerBarCount?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerWaveLineWidth?: number;
  className?: string;
}

export function AgentSessionView_01({
  preConnectMessage = 'Krishi Mitra 🌾 is ready — ask your agricultural question!',
  supportsChatInput = true,
  supportsVideoInput = true,
  supportsScreenShare = true,
  isPreConnectBufferEnabled = true,
  audioVisualizerType,
  audioVisualizerColor,
  audioVisualizerColorShift,
  audioVisualizerBarCount,
  audioVisualizerGridRowCount,
  audioVisualizerGridColumnCount,
  audioVisualizerRadialBarCount,
  audioVisualizerRadialRadius,
  audioVisualizerWaveLineWidth,
  ref,
  className,
  ...props
}: React.ComponentProps<'section'> & AgentSessionView_01Props) {
  const session = useSessionContext();
  const { messages } = useSessionMessages(session);
  const [chatOpen, setChatOpen] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const { state: agentState } = useAgent();

  // Minimal status text below the visualizer
  let dynamicStatusText = preConnectMessage;
  if (agentState === 'listening') {
    dynamicStatusText = 'Listening… / सुन रहे हैं';
  } else if (agentState === 'speaking') {
    dynamicStatusText = 'Krishi Mitra is answering… / जवाब दे रहे हैं';
  } else if (agentState === 'thinking') {
    dynamicStatusText = 'Thinking… / सोच रहे हैं';
  }

  const controls: AgentControlBarControls = {
    leave: true,
    microphone: true,
    chat: supportsChatInput,
    camera: supportsVideoInput,
    screenShare: supportsScreenShare,
  };

  useEffect(() => {
    const lastMessage = messages.at(-1);
    const lastMessageIsLocal = lastMessage?.from?.isLocal === true;
    if (scrollAreaRef.current && lastMessageIsLocal) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.body.classList.toggle('chat-is-open', chatOpen);
    }
    return () => {
      if (typeof document !== 'undefined') {
        document.body.classList.remove('chat-is-open');
      }
    };
  }, [chatOpen]);

  const { isMicrophoneEnabled, localParticipant } = useLocalParticipant();

  const handleRetryMic = async () => {
    try {
      if (typeof navigator !== 'undefined' && navigator.mediaDevices) {
        await navigator.mediaDevices.getUserMedia({ audio: true });
      }
      if (localParticipant) {
        await localParticipant.setMicrophoneEnabled(true);
      }
    } catch (err) {
      console.error('Failed to enable mic on retry:', err);
    } finally {
      if (session.start) {
        session.start();
      }
    }
  };

  return (
    <section
      ref={ref}
      className={cn('relative z-10 h-full w-full overflow-hidden', className)}
      style={{
        background: 'linear-gradient(135deg, #0e2a1e 0%, #1e4d38 50%, #12281c 100%)',
      }}
      {...props}
    >
      {/* ─── State pill or floating mic warning bar ─── */}
      {!isMicrophoneEnabled ? (
        <FloatingMicErrorBar onRetry={handleRetryMic} />
      ) : (
        <StatePill agentState={agentState} chatOpen={chatOpen} />
      )}

      {/* ─── Fade from top edge ─── */}
      <Fade top className="absolute inset-x-4 top-0 z-10 h-32" />

      {/* ─── Chat transcript (Foreground Layer z-[100]) ─── */}
      <div className="absolute top-0 bottom-[135px] z-[100] flex w-full flex-col md:bottom-[170px]">
        <AnimatePresence>
          {chatOpen && (
            <motion.div
              {...CHAT_MOTION_PROPS}
              className="flex h-full w-full flex-col gap-4 space-y-3 transition-opacity duration-300 ease-out"
            >
              <AgentChatTranscript
                agentState={agentState}
                messages={messages}
                className="mx-auto w-full max-w-3xl [&>div>div]:px-4 [&>div>div]:pt-28 md:[&>div>div]:px-6 md:[&>div>div]:pt-32"
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ─── Main tile (visualizer) ─── */}
      <TileLayout
        chatOpen={chatOpen}
        audioVisualizerType={audioVisualizerType}
        audioVisualizerColor={audioVisualizerColor}
        audioVisualizerColorShift={audioVisualizerColorShift}
        audioVisualizerBarCount={audioVisualizerBarCount}
        audioVisualizerRadialBarCount={audioVisualizerRadialBarCount}
        audioVisualizerRadialRadius={audioVisualizerRadialRadius}
        audioVisualizerGridRowCount={audioVisualizerGridRowCount}
        audioVisualizerGridColumnCount={audioVisualizerGridColumnCount}
        audioVisualizerWaveLineWidth={audioVisualizerWaveLineWidth}
      />

      {/* ─── Bottom control area ─── */}
      <motion.div
        {...BOTTOM_VIEW_MOTION_PROPS}
        className="absolute inset-x-3 bottom-0 z-50 md:inset-x-12"
      >
        {/* Status shimmer text */}
        {isPreConnectBufferEnabled && (
          <AnimatePresence>
            <MotionMessage
              key={dynamicStatusText}
              duration={2}
              {...SHIMMER_MOTION_PROPS}
              className="pointer-events-none mx-auto block w-full max-w-2xl pb-3 text-center text-xs font-semibold text-[#95d5b2]"
            >
              {dynamicStatusText}
            </MotionMessage>
          </AnimatePresence>
        )}

        {/* Control bar */}
        <div className="relative mx-auto max-w-2xl pb-3 md:pb-10">
          <Fade bottom className="absolute inset-x-0 top-0 h-4 -translate-y-full" />
          <AgentControlBar
            variant="livekit"
            controls={controls}
            isChatOpen={chatOpen}
            isConnected={session.isConnected}
            onDisconnect={session.end}
            onIsChatOpenChange={setChatOpen}
          />
        </div>
      </motion.div>
    </section>
  );
}
