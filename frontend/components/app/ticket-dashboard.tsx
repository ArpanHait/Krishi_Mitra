'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  CheckCircle2,
  Clock,
  Headset,
  MessageSquare,
  RefreshCw,
  ShieldAlert,
  X,
} from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';

export interface Ticket {
  ticket_id: string;
  farmer_name: string;
  topic: string;
  summary: string;
  urgency: 'Low' | 'Medium' | 'High' | 'Emergency';
  status: 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'OFFICER_REPLIED';
  language?: string;
  preferred_followup?: string;
  officer_response?: string;
  has_unread_reply?: number;
  created_at: string;
  updated_at: string;
}

interface TicketDashboardProps {
  buttonStyle?: 'icon-only' | 'header-button';
}

export function TicketDashboard({ buttonStyle = 'icon-only' }: TicketDashboardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [pendingCount, setPendingCount] = useState<number>(0);
  const [hasUnreadReplies, setHasUnreadReplies] = useState<boolean>(false);
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const fetchPendingCount = useCallback(async () => {
    try {
      const res = await fetch('/api/escalations/pending-count');
      if (res.ok) {
        const data = await res.json();
        setPendingCount(data.count || 0);
        setHasUnreadReplies(!!data.has_unread_replies);
      }
    } catch (err) {
      console.error('Failed to fetch pending count:', err);
    }
  }, []);

  const fetchTickets = useCallback(async (isInitial = false) => {
    try {
      if (isInitial) {
        setIsLoading(true);
      }
      setIsRefreshing(true);
      const res = await fetch('/api/escalations');
      if (res.ok) {
        const data: Ticket[] = await res.json();
        setTickets(data);
        setHasUnreadReplies(data.some((t) => t.has_unread_reply === 1));
      }
    } catch (err) {
      console.error('Failed to fetch tickets:', err);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchPendingCount();
    // 30-second interval as requested
    const interval = setInterval(fetchPendingCount, 30000);
    return () => clearInterval(interval);
  }, [fetchPendingCount]);

  useEffect(() => {
    if (isOpen) {
      fetchTickets(true);
    }
  }, [isOpen, fetchTickets]);

  const handleMarkRead = async (ticket_id: string) => {
    try {
      await fetch('/api/escalations/mark-read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticket_id }),
      });
      setTickets((prev) =>
        prev.map((t) => (t.ticket_id === ticket_id ? { ...t, has_unread_reply: 0 } : t))
      );
      fetchPendingCount();
    } catch (err) {
      console.error('Failed to mark ticket as read:', err);
    }
  };

  const handleResolveTicket = async (ticket_id: string) => {
    try {
      const res = await fetch('/api/escalations/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticket_id }),
      });
      if (res.ok) {
        fetchTickets(false);
        fetchPendingCount();
        setSelectedTicket(null);
      }
    } catch (err) {
      console.error('Failed to resolve ticket:', err);
    }
  };

  const handleSelectTicketCard = (e: React.MouseEvent, ticket: Ticket) => {
    e.stopPropagation();
    if (ticket.has_unread_reply === 1) {
      handleMarkRead(ticket.ticket_id);
    }
    setSelectedTicket(ticket);
  };

  const closeDetailModal = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setSelectedTicket(null);
  };

  const getUrgencyBadge = (urgency: string) => {
    switch (urgency) {
      case 'Emergency':
        return 'bg-red-500/30 text-red-200 border-red-400/50';
      case 'High':
        return 'bg-orange-500/30 text-orange-200 border-orange-400/50';
      case 'Medium':
        return 'bg-yellow-500/30 text-yellow-200 border-yellow-400/50';
      default:
        return 'bg-emerald-500/30 text-emerald-200 border-emerald-400/50';
    }
  };

  const modalContent = (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsOpen(false);
          }}
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 15 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 15 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="relative flex max-h-[80vh] w-full max-w-xl flex-col overflow-hidden rounded-3xl border border-[#52b788]/40 bg-[#0c2419]/45 text-white shadow-2xl backdrop-blur-xl"
            style={{
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.15)',
            }}
          >
            {/* Top glow accent line */}
            <div
              className="pointer-events-none absolute inset-x-0 top-0 h-px"
              style={{
                background:
                  'linear-gradient(90deg, transparent 0%, rgba(82,183,136,0.7) 50%, transparent 100%)',
              }}
            />

            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/15 bg-white/5 px-6 py-4 backdrop-blur-md">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#52b788]/40 bg-[#52b788]/20 text-[#74c69d]">
                  <Headset className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-white">Escalation Support Tickets</h2>
                  <p className="text-xs text-slate-200">Farmer Support Officer Dashboard</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => fetchTickets(false)}
                  disabled={isRefreshing}
                  className="rounded-xl border border-white/15 bg-white/10 p-2 text-slate-200 transition-all hover:bg-white/20 hover:text-white"
                  title="Refresh"
                >
                  <RefreshCw
                    className={`h-4 w-4 transition-transform duration-500 ${isRefreshing ? 'animate-spin' : ''}`}
                  />
                </button>
                <button
                  onClick={() => setIsOpen(false)}
                  className="rounded-xl border border-white/15 bg-white/10 p-2 text-slate-200 transition-all hover:bg-white/20 hover:text-white"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Content List (Step-2 Green Pulse Cards) */}
            <div className="flex-1 space-y-4 overflow-y-auto p-6">
              {isLoading && tickets.length === 0 ? (
                <div className="flex h-40 items-center justify-center text-sm font-medium text-slate-300">
                  Loading tickets...
                </div>
              ) : tickets.length === 0 ? (
                <div className="flex h-40 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-white/20 bg-white/5 p-8 text-center backdrop-blur-md">
                  <CheckCircle2 className="h-8 w-8 text-[#74c69d]" />
                  <p className="text-sm font-medium text-white">No active escalations</p>
                  <p className="text-xs text-slate-300">All farmer support tickets are resolved.</p>
                </div>
              ) : (
                <AnimatePresence mode="popLayout">
                  {tickets.map((t) => {
                    const isUnread = t.has_unread_reply === 1 || t.status === 'OFFICER_REPLIED';
                    return (
                      <motion.div
                        key={t.ticket_id}
                        layout
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        transition={{ duration: 0.2 }}
                        onClick={(e) => handleSelectTicketCard(e, t)}
                        className={`flex cursor-pointer flex-col gap-3 rounded-2xl p-4 backdrop-blur-md transition-all hover:scale-[1.01] ${
                          isUnread
                            ? 'animate-pulse border-2 border-emerald-500 bg-emerald-950/40 shadow-lg shadow-emerald-500/20 hover:border-emerald-400'
                            : 'border border-white/15 bg-black/20 hover:border-white/30 hover:bg-black/30'
                        }`}
                      >
                        {/* Top row: ID, Urgency, Status */}
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-bold text-[#74c69d]">
                              #{t.ticket_id}
                            </span>
                            <span
                              className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold tracking-wide uppercase ${getUrgencyBadge(
                                t.urgency
                              )}`}
                            >
                              {t.urgency}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            {t.status === 'OFFICER_REPLIED' || isUnread ? (
                              <span className="flex items-center gap-1.5 text-[11px] font-bold text-[#74c69d]">
                                <span className="h-2 w-2 animate-ping rounded-full bg-[#74c69d]" />
                                OFFICER REPLIED
                              </span>
                            ) : t.status === 'OPEN' ? (
                              <span className="flex items-center gap-1.5 text-[11px] font-semibold text-rose-400">
                                <span className="h-2 w-2 animate-ping rounded-full bg-rose-500" />
                                OPEN
                              </span>
                            ) : (
                              <span className="flex items-center gap-1 text-[11px] font-semibold text-[#74c69d]">
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                RESOLVED
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Details */}
                        <div>
                          <h3 className="text-sm font-semibold text-white">{t.topic}</h3>
                          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-200">
                            {t.summary}
                          </p>
                        </div>

                        {/* Officer Reply Teaser */}
                        {t.officer_response && (
                          <div className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-900/30 px-3 py-2 text-xs text-[#74c69d]">
                            <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                            <span className="truncate">Reply: {t.officer_response}</span>
                          </div>
                        )}

                        {/* Meta info */}
                        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 pt-3 text-[11px] text-slate-300">
                          <span>
                            Farmer: <strong className="text-white">{t.farmer_name}</strong>
                          </span>
                          <span>
                            Follow-up:{' '}
                            <strong className="text-[#74c69d]">
                              {t.preferred_followup || 'Phone Call'}
                            </strong>
                          </span>
                          <span className="flex items-center gap-1 text-[10px] text-slate-400">
                            <Clock className="h-3 w-3" />
                            {new Date(t.created_at).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>
                        </div>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );

  const detailModalContent = (
    <AnimatePresence>
      {selectedTicket && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/30 p-4 backdrop-blur-sm"
          onClick={closeDetailModal}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: 'spring', damping: 25, stiffness: 350 }}
            onClick={(e) => e.stopPropagation()}
            className="relative flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-3xl border border-emerald-500/50 bg-[#081c13]/90 text-white shadow-2xl backdrop-blur-2xl"
            style={{
              boxShadow: '0 30px 60px -12px rgba(0,0,0,0.7), inset 0 1px 0 rgba(255,255,255,0.2)',
            }}
          >
            {/* Top Glow Accent Line */}
            <div
              className="pointer-events-none absolute inset-x-0 top-0 h-px"
              style={{
                background:
                  'linear-gradient(90deg, transparent 0%, rgba(82,183,136,0.9) 50%, transparent 100%)',
              }}
            />

            {/* Pop-up Header */}
            <div className="flex items-center justify-between border-b border-white/15 bg-white/5 px-6 py-4 backdrop-blur-md">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-emerald-500/40 bg-emerald-500/20 text-[#74c69d]">
                  <MessageSquare className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-base font-bold text-white">
                      Ticket #{selectedTicket.ticket_id}
                    </h2>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${getUrgencyBadge(
                        selectedTicket.urgency
                      )}`}
                    >
                      {selectedTicket.urgency}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300">
                    Farmer: <strong className="text-white">{selectedTicket.farmer_name}</strong>
                  </p>
                </div>
              </div>
              <button
                onClick={closeDetailModal}
                className="rounded-xl border border-white/15 bg-white/10 p-2 text-slate-200 transition-all hover:bg-white/20 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Pop-up Body Content */}
            <div className="flex-1 space-y-4 overflow-y-auto p-6">
              {/* Topic */}
              <div>
                <span className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
                  Topic / Crop Issue
                </span>
                <h3 className="mt-0.5 text-base font-bold text-white">{selectedTicket.topic}</h3>
              </div>

              {/* Raised Problem Summary */}
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur-md">
                <span className="text-[11px] font-semibold text-slate-300">
                  Farmer Raised Issue Summary:
                </span>
                <p className="mt-1 text-xs leading-relaxed text-slate-200">
                  {selectedTicket.summary}
                </p>
              </div>

              {/* Officer Text Message Response Box */}
              {selectedTicket.officer_response ? (
                <div className="rounded-2xl border border-emerald-500/40 bg-emerald-950/50 p-4 shadow-inner">
                  <div className="flex items-center gap-2 text-xs font-bold text-[#74c69d]">
                    <Headset className="h-4 w-4" />
                    <span>Support Officer Official Response:</span>
                  </div>
                  <p className="mt-2 text-xs leading-relaxed font-medium whitespace-pre-wrap text-slate-100">
                    {selectedTicket.officer_response}
                  </p>
                </div>
              ) : (
                <div className="flex items-center gap-2 rounded-2xl border border-yellow-500/30 bg-yellow-950/20 p-4 text-xs text-yellow-200">
                  <ShieldAlert className="h-4 w-4 shrink-0 text-yellow-400" />
                  <span>Awaiting response from Support Officer (`prabhashhait@gmail.com`).</span>
                </div>
              )}
            </div>

            {/* Pop-up Action Footer */}
            <div className="flex items-center gap-3 border-t border-white/15 bg-white/5 px-6 py-4 backdrop-blur-md">
              {/* Only show "Mark as Resolved" button AFTER officer has replied */}
              {selectedTicket.status !== 'RESOLVED' &&
              (selectedTicket.status === 'OFFICER_REPLIED' || selectedTicket.officer_response) ? (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleResolveTicket(selectedTicket.ticket_id);
                  }}
                  className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-emerald-500/50 bg-[#2d6a4f] py-2.5 text-xs font-bold text-white transition-all hover:bg-emerald-600 active:scale-95"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Mark as Resolved
                </button>
              ) : selectedTicket.status !== 'RESOLVED' ? (
                <div className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 py-2.5 text-xs font-medium text-slate-400">
                  <Clock className="h-3.5 w-3.5" />
                  <span>Awaiting Officer Reply...</span>
                </div>
              ) : null}
              <button
                onClick={closeDetailModal}
                className="rounded-xl border border-white/15 bg-white/10 px-4 py-2.5 text-xs font-semibold text-slate-200 transition-all hover:bg-white/20 hover:text-white"
              >
                Close
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );

  return (
    <>
      {/* Step-1: Main Support Button Trigger with Red Pulse Badge */}
      <div className="relative inline-block">
        <button
          onClick={() => setIsOpen(true)}
          className={
            buttonStyle === 'header-button'
              ? 'flex items-center gap-1.5 rounded-xl border border-emerald-500/30 bg-[#2d6a4f]/80 px-3 py-1.5 text-xs font-semibold text-white shadow-md transition-all hover:bg-[#2d6a4f]'
              : 'flex size-9 items-center justify-center rounded-full border border-white/25 bg-white/20 text-white shadow-sm transition-all hover:scale-105 hover:bg-white/30 active:scale-95'
          }
          title="Support Tickets Dashboard"
        >
          <Headset className="h-4 w-4" />
          {buttonStyle === 'header-button' && <span>Tickets</span>}
        </button>

        {/* Live Red Notification Badge / Red Pulse */}
        {hasUnreadReplies ? (
          <span className="absolute -top-1 -right-1 flex h-4.5 w-4.5 items-center justify-center">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
            <span className="relative inline-flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[9px] font-bold text-white shadow-md">
              !
            </span>
          </span>
        ) : pendingCount > 0 ? (
          <span className="absolute -top-1 -right-1 flex h-4.5 w-4.5 animate-pulse items-center justify-center rounded-full border border-[#184e38] bg-rose-500 text-[10px] font-bold text-white shadow-md">
            {pendingCount}
          </span>
        ) : null}
      </div>

      {/* Render Centered Floating Glassmorphic Modal via Portal */}
      {mounted && createPortal(modalContent, document.body)}
      {mounted && createPortal(detailModalContent, document.body)}
    </>
  );
}
