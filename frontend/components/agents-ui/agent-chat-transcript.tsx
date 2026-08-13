'use client';

import { type ComponentProps } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { type AgentState, type ReceivedMessage } from '@livekit/components-react';
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from '@/components/ai-elements/conversation';

/**
 * Props for the AgentChatTranscript component.
 */
export interface AgentChatTranscriptProps extends ComponentProps<'div'> {
  /**
   * The current state of the agent. When 'thinking', displays a loading indicator.
   */
  agentState?: AgentState;
  /**
   * Array of messages to display in the transcript.
   * @defaultValue []
   */
  messages?: ReceivedMessage[];
  /**
   * Additional CSS class names to apply to the conversation container.
   */
  className?: string;
}

/**
 * Rich styled chat transcript with distinct, color-coded bubble cards for user & agent.
 */
export function AgentChatTranscript({
  agentState,
  messages = [],
  className,
  ...props
}: AgentChatTranscriptProps) {
  return (
    <Conversation className={className} {...props}>
      <ConversationContent className="space-y-4 px-2 py-4">
        {messages.map((receivedMessage) => {
          const { id, timestamp, from, message } = receivedMessage;
          const isUser = from?.isLocal === true;
          const timeStr = new Date(timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          });

          return (
            <div
              key={id}
              className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} my-2.5`}
            >
              {isUser ? (
                /* User Question Bubble Card (Right Aligned - Glassmorphism Emerald) */
                <div className="group relative max-w-[85%] rounded-2xl rounded-tr-xs border border-[#52b788]/50 bg-gradient-to-br from-[#2d6a4f]/40 via-[#1b4332]/45 to-[#122c21]/45 px-4.5 py-3.5 shadow-xl backdrop-blur-xl transition-all duration-200 hover:border-[#52b788]/70 sm:max-w-[78%] md:px-5">
                  <div className="mb-1 flex items-center justify-end gap-1.5 text-[11px] font-bold tracking-wide text-[#74c69d]">
                    <span>You / आप</span>
                    <span className="flex size-4.5 items-center justify-center rounded-full bg-[#52b788]/20 text-[10px]">
                      👤
                    </span>
                  </div>
                  <p className="text-sm leading-relaxed font-medium text-white sm:text-base">
                    {message}
                  </p>
                  <div className="mt-1 text-right text-[10px] font-medium text-emerald-200/70">
                    {timeStr}
                  </div>
                </div>
              ) : (
                /* Krishi Mitra Response Bubble Card (Left Aligned - Glassmorphism Gold Accent) */
                <div className="group relative max-w-[90%] rounded-2xl rounded-tl-xs border border-[#e9c46a]/45 bg-gradient-to-br from-[#184e38]/45 via-[#123929]/50 to-[#0b261b]/50 px-5 py-4 shadow-2xl backdrop-blur-xl transition-all duration-200 hover:border-[#e9c46a]/70 sm:max-w-[82%]">
                  <div className="mb-1.5 flex items-center gap-2 text-[11px] font-bold tracking-wide text-[#e9c46a]">
                    <span className="flex size-5 items-center justify-center rounded-lg bg-gradient-to-br from-[#e9c46a] to-[#f4a261] text-xs text-[#261c14] shadow-sm">
                      🌾
                    </span>
                    <span>Krishi Mitra (कृषि मित्र)</span>
                  </div>
                  <p className="text-sm leading-relaxed font-medium text-slate-100 sm:text-base">
                    {message}
                  </p>
                  <div className="mt-1.5 text-right text-[10px] font-medium text-[#e9c46a]/70">
                    {timeStr}
                  </div>
                </div>
              )}
            </div>
          );
        })}
        <AnimatePresence>
          {agentState === 'thinking' && (
            <motion.div
              initial={{ opacity: 0, y: 8, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 5, scale: 0.9 }}
              transition={{ type: 'spring', damping: 20, stiffness: 350 }}
              className="my-2.5 flex justify-start"
            >
              <div className="relative flex items-center justify-center rounded-2xl rounded-tl-xs border border-[#52b788]/50 bg-gradient-to-br from-[#1b4332]/80 via-[#122c21]/90 to-[#0c2419]/90 px-4.5 py-3 shadow-xl backdrop-blur-xl">
                <div className="flex items-center gap-1.5 px-0.5">
                  <span className="h-2.5 w-2.5 animate-bounce rounded-full bg-emerald-300 [animation-delay:-0.32s]" />
                  <span className="h-2.5 w-2.5 animate-bounce rounded-full bg-emerald-300 [animation-delay:-0.16s]" />
                  <span className="h-2.5 w-2.5 animate-bounce rounded-full bg-emerald-300" />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </ConversationContent>
      <ConversationScrollButton />
    </Conversation>
  );
}
