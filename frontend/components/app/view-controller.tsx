'use client';

import { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';
import { AnimatePresence, motion } from 'motion/react';
import { useSessionContext } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { AgentSessionView_01 } from '@/components/agents-ui/blocks/agent-session-view-01';
import { MicErrorCard } from '@/components/app/mic-error-card';
import { WelcomeView } from '@/components/app/welcome-view';
import { Button } from '@/components/ui/button';

const MotionWelcomeView = motion.create(WelcomeView);
const MotionSessionView = motion.create(AgentSessionView_01);
const MotionMicErrorCard = motion.create(MicErrorCard);

const VIEW_MOTION_PROPS = {
  variants: {
    visible: { opacity: 1 },
    hidden: { opacity: 0 },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: { duration: 0.4, ease: 'linear' },
};

// ─── Call Ended Screen ───
function CallEndedView({ onNewCall }: { onNewCall: () => void }) {
  return (
    <div className="relative flex min-h-svh w-full flex-col items-center justify-center overflow-hidden">
      {/* Background matching session view */}
      <div
        className="absolute inset-0"
        style={{
          background: 'linear-gradient(160deg, #0a1f15 0%, #0f281e 40%, #122b20 70%, #0d2318 100%)',
        }}
      />

      <div
        className="relative z-10 mx-auto w-full max-w-sm overflow-hidden rounded-3xl p-8 text-center shadow-2xl backdrop-blur-xl"
        style={{
          background: 'rgba(255,255,255,0.05)',
          border: '1px solid rgba(82,183,136,0.15)',
          boxShadow: '0 8px 60px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06)',
        }}
      >
        {/* Top glow line */}
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-px"
          style={{
            background:
              'linear-gradient(90deg, transparent 0%, rgba(82,183,136,0.5) 50%, transparent 100%)',
          }}
        />

        <div
          className="mx-auto mb-5 flex h-20 w-20 items-center justify-center rounded-full text-4xl"
          style={{
            background: 'linear-gradient(135deg, #2d6a4f22 0%, #1b433222 100%)',
            border: '2px solid rgba(82,183,136,0.3)',
          }}
        >
          ✅
        </div>

        <h2 className="text-xl font-extrabold text-white">Call Ended</h2>
        <p className="mt-1 text-sm font-semibold text-[#52b788]">कॉल समाप्त हो गई</p>

        <div className="my-4 h-px w-full bg-gradient-to-r from-transparent via-[#52b788]/20 to-transparent" />

        <p className="text-sm leading-relaxed text-[#95d5b2]">
          Thank you for talking with Krishi Mitra 🌾.
          <br />
          आपकी बातचीत के लिए धन्यवाद!
        </p>

        <Button
          id="start-new-call-btn"
          size="lg"
          onClick={onNewCall}
          className="group relative mt-6 w-full overflow-hidden rounded-full py-5 text-sm font-bold text-white transition-all duration-300"
          style={{
            background: 'linear-gradient(135deg, #2d6a4f 0%, #1b4332 100%)',
            border: '1px solid rgba(82,183,136,0.35)',
            boxShadow: '0 4px 20px rgba(45,106,79,0.45)',
          }}
        >
          <span className="pointer-events-none absolute inset-0 translate-x-[-100%] bg-gradient-to-r from-transparent via-white/10 to-transparent transition-transform duration-700 group-hover:translate-x-[100%]" />
          <span className="relative flex items-center justify-center gap-2">
            <span>🌾</span>
            Start New Call / नई कॉल शुरू करें
          </span>
        </Button>
      </div>

      <div className="absolute bottom-4 left-0 z-10 flex w-full items-center justify-center">
        <p className="text-xs text-[#52b788]/50">Powered by Murf Falcon TTS · LiveKit Agents</p>
      </div>
    </div>
  );
}

interface ViewControllerProps {
  appConfig: AppConfig;
}

export function ViewController({ appConfig }: ViewControllerProps) {
  const { isConnected, start } = useSessionContext();
  const { resolvedTheme } = useTheme();
  const [hasMicError, setHasMicError] = useState(false);
  // Track whether a session was ever started (so we can show "ended" vs "not started")
  const [wasConnected, setWasConnected] = useState(false);

  // Detect when session drops from connected → disconnected
  useEffect(() => {
    if (isConnected) {
      setWasConnected(true);
    }
  }, [isConnected]);

  const hasEnded = wasConnected && !isConnected;

  // Auto-redirect from Call Ended back to Landing page after 3 seconds
  useEffect(() => {
    if (hasEnded) {
      const timer = setTimeout(() => {
        setWasConnected(false);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [hasEnded]);

  const handleStartCall = () => {
    setHasMicError(false);
    setWasConnected(false);
    start();
  };

  return (
    <AnimatePresence mode="wait">
      {/* ─── Microphone permission error ─── */}
      {hasMicError && (
        <MotionMicErrorCard key="mic-error" {...VIEW_MOTION_PROPS} onRetry={handleStartCall} />
      )}

      {/* ─── Call ended screen ─── */}
      {!isConnected && hasEnded && !hasMicError && (
        <motion.div key="call-ended" className="min-h-svh w-full" {...VIEW_MOTION_PROPS}>
          <CallEndedView onNewCall={handleStartCall} />
        </motion.div>
      )}

      {/* ─── Welcome / landing screen ─── */}
      {!isConnected && !hasMicError && !hasEnded && (
        <MotionWelcomeView
          key="welcome"
          {...VIEW_MOTION_PROPS}
          startButtonText={appConfig.startButtonText}
          onStartCall={handleStartCall}
          onMicError={() => setHasMicError(true)}
        />
      )}

      {/* ─── Active session view ─── */}
      {isConnected && (
        <MotionSessionView
          key="session-view"
          {...VIEW_MOTION_PROPS}
          supportsChatInput={appConfig.supportsChatInput}
          supportsVideoInput={appConfig.supportsVideoInput}
          supportsScreenShare={appConfig.supportsScreenShare}
          isPreConnectBufferEnabled={appConfig.isPreConnectBufferEnabled}
          audioVisualizerType={appConfig.audioVisualizerType}
          audioVisualizerColor={
            resolvedTheme === 'dark'
              ? appConfig.audioVisualizerColorDark
              : appConfig.audioVisualizerColor
          }
          audioVisualizerColorShift={appConfig.audioVisualizerColorShift}
          audioVisualizerBarCount={appConfig.audioVisualizerBarCount}
          audioVisualizerGridRowCount={appConfig.audioVisualizerGridRowCount}
          audioVisualizerGridColumnCount={appConfig.audioVisualizerGridColumnCount}
          audioVisualizerRadialBarCount={appConfig.audioVisualizerRadialBarCount}
          audioVisualizerRadialRadius={appConfig.audioVisualizerRadialRadius}
          audioVisualizerWaveLineWidth={appConfig.audioVisualizerWaveLineWidth}
          className="fixed inset-0"
        />
      )}
    </AnimatePresence>
  );
}
