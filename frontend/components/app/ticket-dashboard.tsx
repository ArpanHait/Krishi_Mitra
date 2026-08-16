'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Activity,
  Bot,
  CheckCircle2,
  Clock,
  Cloud,
  Headset,
  MessageSquare,
  PhoneCall,
  PhoneOff,
  PlugZap,
  RefreshCw,
  ShoppingCart,
  TrendingUp,
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

export interface CallLog {
  call_id: string;
  caller_id: string;
  call_type: 'BROWSER' | 'SIP_OUTBOUND';
  topic: string;
  duration_seconds: number;
  outcome: 'SUCCESS' | 'FAILED';
  failure_reason?: string | null;
  created_at: string;
}

export interface ApiToolStats {
  total: number;
  successful: number;
  failed: number;
}

export interface AgentResponseStats {
  name: string;
  icon: string;
  total: number;
  successful: number;
  failed: number;
}

export interface AnalyticsData {
  total_calls: number;
  successful_calls: number;
  declined_calls?: number;
  system_failed_calls?: number;
  failed_calls: number;
  success_rate: number;
  recent_logs: CallLog[];
  tool_stats?: Record<'mandi' | 'weather', ApiToolStats>;
  agent_stats?: AgentResponseStats[];
}

interface TicketDashboardProps {
  buttonStyle?: 'icon-only' | 'header-button';
}

export function TicketDashboard({ buttonStyle = 'icon-only' }: TicketDashboardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'api-tools' | 'tickets' | 'agent-responses'>(
    'api-tools'
  );
  const [activeApiSubTab, setActiveApiSubTab] = useState<'voice' | 'mandi' | 'weather'>('voice');
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData>({
    total_calls: 0,
    successful_calls: 0,
    declined_calls: 0,
    system_failed_calls: 0,
    failed_calls: 0,
    success_rate: 0.0,
    recent_logs: [],
    tool_stats: {
      mandi: { total: 0, successful: 0, failed: 0 },
      weather: { total: 0, successful: 0, failed: 0 },
    },
    agent_stats: [
      { name: 'Krishi Mitra', icon: '🌾', total: 0, successful: 0, failed: 0 },
      { name: 'Fasal Doctor', icon: '👨‍⚕️', total: 0, successful: 0, failed: 0 },
    ],
  });
  const [pendingCount, setPendingCount] = useState<number>(0);
  const [hasUnreadReplies, setHasUnreadReplies] = useState<boolean>(false);
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Call outcome full-button glow pulse state: 'SUCCESS' | 'FAILED' | null
  const [callOutcomeGlow, setCallOutcomeGlow] = useState<'SUCCESS' | 'FAILED' | null>(null);
  const lastSeenCallIdRef = useRef<string | null>(null);
  const lastSyncTimeRef = useRef<number>(0);

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

  const fetchTickets = useCallback(async () => {
    try {
      const res = await fetch('/api/escalations');
      if (res.ok) {
        const data: Ticket[] = await res.json();
        if (data) {
          setTickets(data);
          setHasUnreadReplies(data.some((t) => t.has_unread_reply === 1));
        }
      }
    } catch (err) {
      console.error('Failed to fetch tickets:', err);
    }
  }, []);

  const fetchAnalytics = useCallback(async () => {
    try {
      const res = await fetch('/api/analytics');
      if (res.ok) {
        const data: AnalyticsData = await res.json();
        setAnalytics(data);

        // Check if a new call outcome registered to trigger full-button glow pulse
        if (data.recent_logs && data.recent_logs.length > 0) {
          const newest = data.recent_logs[0];
          if (lastSeenCallIdRef.current && newest.call_id !== lastSeenCallIdRef.current) {
            setCallOutcomeGlow(newest.outcome);
          }
          lastSeenCallIdRef.current = newest.call_id;
        }
      }
    } catch (err) {
      console.error('Failed to fetch analytics:', err);
    }
  }, []);

  // Real-time Server-Sent Events (SSE) listener for 0ms automatic dashboard updates
  useEffect(() => {
    let eventSource: EventSource | null = null;
    try {
      eventSource = new EventSource('/api/events');

      eventSource.addEventListener('new_call_logged', () => {
        fetchAnalytics();
      });

      eventSource.addEventListener('tool_called', () => {
        fetchAnalytics();
      });

      eventSource.addEventListener('agent_response', () => {
        fetchAnalytics();
      });

      eventSource.addEventListener('ticket_updated', () => {
        fetchTickets();
        fetchPendingCount();
      });
    } catch (err) {
      console.error('SSE initialization error:', err);
    }

    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [fetchAnalytics, fetchTickets, fetchPendingCount]);

  const syncEmailsAndFetch = useCallback(
    async (isInitial = false) => {
      const now = Date.now();
      // 3-second minimum cooldown guard to prevent rapid multi-click spam
      if (!isInitial && now - lastSyncTimeRef.current < 3000) {
        return;
      }
      lastSyncTimeRef.current = now;

      try {
        if (isInitial) {
          setIsLoading(true);
        }
        setIsRefreshing(true);

        // 1. Fetch Call Analytics & Pending Count INSTANTLY from SQLite (5ms response)
        await Promise.all([fetchAnalytics(), fetchPendingCount(), fetchTickets()]);

        // 2. Trigger IMAP email sync asynchronously in background without blocking UI
        fetch('/api/escalations/sync-email', { method: 'POST' }).catch((syncErr) =>
          console.error('Background email sync error:', syncErr)
        );
      } catch (err) {
        console.error('Failed to sync and fetch dashboard data:', err);
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [fetchAnalytics, fetchPendingCount, fetchTickets]
  );

  useEffect(() => {
    fetchPendingCount();
    fetchAnalytics();
  }, [fetchPendingCount, fetchAnalytics]);

  useEffect(() => {
    if (isOpen) {
      fetchAnalytics();
      syncEmailsAndFetch(true);
    }
  }, [isOpen, fetchAnalytics, syncEmailsAndFetch]);

  const handleOpenModal = () => {
    setCallOutcomeGlow(null); // Auto-clear full-button glow pulse on open
    fetchAnalytics(); // Force immediate SQLite analytics refresh!
    setIsOpen(true);
  };

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
        syncEmailsAndFetch(false);
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
            className="relative flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-3xl border border-[#52b788]/40 bg-[#0c2419]/80 text-white shadow-2xl backdrop-blur-xl"
            style={{
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.15)',
            }}
          >
            {/* Top glow accent line */}
            <div
              className="pointer-events-none absolute inset-x-0 top-0 h-px"
              style={{
                background:
                  'linear-gradient(90deg, transparent 0%, rgba(82,183,136,0.8) 50%, transparent 100%)',
              }}
            />

            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/15 bg-white/5 px-6 py-4 backdrop-blur-md">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#52b788]/40 bg-[#52b788]/20 text-[#74c69d]">
                  <Activity className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-white">Krishi Control Center</h2>
                  <p className="text-xs text-slate-200">
                    Call Outcome Analytics & Support Tickets Dashboard
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => syncEmailsAndFetch(false)}
                  disabled={isRefreshing}
                  className="rounded-xl border border-white/15 bg-white/10 p-2 text-slate-200 transition-all hover:bg-white/20 hover:text-white"
                  title="Refresh Dashboard"
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

            {/* Top Tab Switcher — 3 tabs */}
            <div className="flex border-b border-white/15 bg-white/5 px-6 pt-2 backdrop-blur-md">
              <button
                onClick={() => setActiveTab('api-tools')}
                className={`flex flex-1 items-center justify-center gap-2 rounded-t-xl border-b-2 py-3 text-xs font-bold transition-all ${
                  activeTab === 'api-tools'
                    ? 'border-[#52b788] bg-[#52b788]/20 text-[#74c69d]'
                    : 'border-transparent text-slate-300 hover:bg-white/5 hover:text-white'
                }`}
              >
                <PlugZap className="h-4 w-4" />
                <span>API Tool Calls</span>
              </button>
              <button
                onClick={() => setActiveTab('tickets')}
                className={`relative flex flex-1 items-center justify-center gap-2 rounded-t-xl border-b-2 py-3 text-xs font-bold transition-all ${
                  activeTab === 'tickets'
                    ? 'border-[#52b788] bg-[#52b788]/20 text-[#74c69d]'
                    : 'border-transparent text-slate-300 hover:bg-white/5 hover:text-white'
                }`}
              >
                <Headset className="h-4 w-4" />
                <span>Support Tickets</span>
                {(hasUnreadReplies || pendingCount > 0) && (
                  <span className="ml-1.5 flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-rose-500 px-1.5 text-[9px] font-extrabold text-white shadow-sm">
                    {hasUnreadReplies ? '!' : pendingCount}
                  </span>
                )}
              </button>
              <button
                onClick={() => setActiveTab('agent-responses')}
                className={`flex flex-1 items-center justify-center gap-2 rounded-t-xl border-b-2 py-3 text-xs font-bold transition-all ${
                  activeTab === 'agent-responses'
                    ? 'border-[#52b788] bg-[#52b788]/20 text-[#74c69d]'
                    : 'border-transparent text-slate-300 hover:bg-white/5 hover:text-white'
                }`}
              >
                <Bot className="h-4 w-4" />
                <span>Agent Responses</span>
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 space-y-4 overflow-y-auto p-6">
              {/* TAB 1: API TOOL CALLS */}
              {activeTab === 'api-tools' && (
                <div className="space-y-5">
                  {/* Sub-tab pill switcher */}
                  <div className="flex gap-2 rounded-2xl border border-white/10 bg-white/5 p-1.5 backdrop-blur-md">
                    {[
                      {
                        key: 'voice' as const,
                        label: 'Voice Call',
                        icon: <PhoneCall className="h-3.5 w-3.5" />,
                      },
                      {
                        key: 'mandi' as const,
                        label: 'Mandi API',
                        icon: <ShoppingCart className="h-3.5 w-3.5" />,
                      },
                      {
                        key: 'weather' as const,
                        label: 'Weather API',
                        icon: <Cloud className="h-3.5 w-3.5" />,
                      },
                    ].map(({ key, label, icon }) => (
                      <button
                        key={key}
                        onClick={() => setActiveApiSubTab(key)}
                        className={`flex flex-1 items-center justify-center gap-1.5 rounded-xl py-2 text-xs font-bold transition-all ${
                          activeApiSubTab === key
                            ? 'bg-[#52b788] text-[#0c2419] shadow-sm'
                            : 'text-slate-300 hover:bg-white/10 hover:text-white'
                        }`}
                      >
                        {icon}
                        <span>{label}</span>
                      </button>
                    ))}
                  </div>

                  {/* Voice Call sub-tab */}
                  {activeApiSubTab === 'voice' && (
                    <div className="space-y-5">
                      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-white/15 bg-white/5 p-3.5 text-center backdrop-blur-md">
                          <p className="text-[10px] font-bold tracking-wider text-slate-300 uppercase">
                            Total Calls
                          </p>
                          <p className="mt-1 text-2xl font-black text-white">
                            {analytics.total_calls}
                          </p>
                        </div>
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-3.5 text-center backdrop-blur-md">
                          <p className="text-[10px] font-bold tracking-wider text-emerald-300 uppercase">
                            Successful
                          </p>
                          <p className="mt-1 text-2xl font-black text-emerald-400">
                            {analytics.successful_calls}
                          </p>
                        </div>
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-amber-500/40 bg-amber-500/10 p-3.5 text-center backdrop-blur-md">
                          <p className="text-[10px] font-bold tracking-wider text-amber-300 uppercase">
                            Declined
                          </p>
                          <p className="mt-1 text-2xl font-black text-amber-400">
                            {analytics.declined_calls ?? 0}
                          </p>
                        </div>
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-rose-500/40 bg-rose-500/10 p-3.5 text-center backdrop-blur-md">
                          <p className="text-[10px] font-bold tracking-wider text-rose-300 uppercase">
                            Failed
                          </p>
                          <p className="mt-1 text-2xl font-black text-rose-400">
                            {analytics.system_failed_calls ?? analytics.failed_calls}
                          </p>
                        </div>
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-emerald-400/40 bg-white/5 p-3.5 text-center backdrop-blur-md">
                          <p className="text-[10px] font-bold tracking-wider text-slate-300 uppercase">
                            Success Rate
                          </p>
                          <p className="mt-1 text-2xl font-black text-emerald-300">
                            {analytics.success_rate}%
                          </p>
                        </div>
                      </div>

                      {/* Recent Call Logs Table */}
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <h3 className="text-sm font-bold text-white">Recent Call Logs</h3>
                          <span className="text-xs text-slate-300">Privacy-Safe Call Metrics</span>
                        </div>
                        <div className="overflow-hidden rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md">
                          {analytics.recent_logs.length === 0 ? (
                            <div className="flex h-32 flex-col items-center justify-center gap-1.5 p-6 text-center text-slate-300">
                              <PhoneCall className="h-6 w-6 text-slate-400" />
                              <p className="text-xs font-medium">No recent call logs recorded</p>
                            </div>
                          ) : (
                            <div className="overflow-x-auto">
                              <table className="w-full text-left text-xs text-slate-200">
                                <thead className="border-b border-white/10 bg-white/5 text-[10px] tracking-wider text-slate-300 uppercase">
                                  <tr>
                                    <th className="px-4 py-3">Call ID</th>
                                    <th className="px-4 py-3">Time</th>
                                    <th className="px-4 py-3">Topic</th>
                                    <th className="px-4 py-3">Duration</th>
                                    <th className="px-4 py-3">Outcome</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-white/10">
                                  {analytics.recent_logs.map((log) => {
                                    const isDeclined =
                                      log.outcome === 'FAILED' &&
                                      log.failure_reason &&
                                      /unanswered|declined|busy|canceled|pick/i.test(
                                        log.failure_reason
                                      );
                                    return (
                                      <tr
                                        key={log.call_id}
                                        className="transition-colors hover:bg-white/5"
                                      >
                                        <td className="px-4 py-3 font-mono font-bold text-[#74c69d]">
                                          {log.call_id}
                                        </td>
                                        <td className="px-4 py-3 font-medium whitespace-nowrap text-slate-300">
                                          {log.created_at
                                            ? new Date(log.created_at).toLocaleTimeString([], {
                                                hour: '2-digit',
                                                minute: '2-digit',
                                              })
                                            : 'Recently'}
                                        </td>
                                        <td className="max-w-[180px] truncate px-4 py-3 font-medium text-white">
                                          {log.topic}
                                        </td>
                                        <td className="px-4 py-3 font-mono text-slate-300">
                                          {log.duration_seconds}s
                                        </td>
                                        <td className="px-4 py-3">
                                          {log.outcome === 'SUCCESS' ? (
                                            <span className="inline-flex items-center gap-1 rounded-md border border-emerald-500/50 bg-emerald-500/20 px-2 py-0.5 text-[10px] font-bold text-emerald-300">
                                              <CheckCircle2 className="h-3 w-3" />
                                              SUCCESS
                                            </span>
                                          ) : isDeclined ? (
                                            <span
                                              title={
                                                log.failure_reason ||
                                                'Call unanswered or declined by user'
                                              }
                                              className="inline-flex items-center gap-1 rounded-md border border-amber-500/50 bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-300"
                                            >
                                              <PhoneOff className="h-3 w-3" />
                                              DECLINED
                                            </span>
                                          ) : (
                                            <span
                                              title={log.failure_reason || 'System Error'}
                                              className="inline-flex items-center gap-1 rounded-md border border-rose-500/50 bg-rose-500/20 px-2 py-0.5 text-[10px] font-bold text-rose-300"
                                            >
                                              <PhoneOff className="h-3 w-3" />
                                              FAILED
                                            </span>
                                          )}
                                        </td>
                                      </tr>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Mandi API sub-tab */}
                  {activeApiSubTab === 'mandi' && (
                    <div className="space-y-4">
                      <div className="flex items-center gap-2">
                        <ShoppingCart className="h-4 w-4 text-[#74c69d]" />
                        <h3 className="text-sm font-bold text-white">Mandi Price API</h3>
                      </div>
                      <div className="grid grid-cols-3 gap-3">
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-white/15 bg-white/5 p-5 text-center backdrop-blur-md">
                          <TrendingUp className="mb-2 h-5 w-5 text-slate-400" />
                          <p className="text-[10px] font-bold tracking-wider text-slate-300 uppercase">
                            Total Requests
                          </p>
                          <p className="mt-1.5 text-3xl font-black text-white">
                            {analytics.tool_stats?.mandi?.total ?? 0}
                          </p>
                        </div>
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-5 text-center backdrop-blur-md">
                          <CheckCircle2 className="mb-2 h-5 w-5 text-emerald-400" />
                          <p className="text-[10px] font-bold tracking-wider text-emerald-300 uppercase">
                            Successful
                          </p>
                          <p className="mt-1.5 text-3xl font-black text-emerald-400">
                            {analytics.tool_stats?.mandi?.successful ?? 0}
                          </p>
                        </div>
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-rose-500/40 bg-rose-500/10 p-5 text-center backdrop-blur-md">
                          <PhoneOff className="mb-2 h-5 w-5 text-rose-400" />
                          <p className="text-[10px] font-bold tracking-wider text-rose-300 uppercase">
                            Failed
                          </p>
                          <p className="mt-1.5 text-3xl font-black text-rose-400">
                            {analytics.tool_stats?.mandi?.failed ?? 0}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Weather API sub-tab */}
                  {activeApiSubTab === 'weather' && (
                    <div className="space-y-4">
                      <div className="flex items-center gap-2">
                        <Cloud className="h-4 w-4 text-[#74c69d]" />
                        <h3 className="text-sm font-bold text-white">Weather API</h3>
                      </div>
                      <div className="grid grid-cols-3 gap-3">
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-white/15 bg-white/5 p-5 text-center backdrop-blur-md">
                          <TrendingUp className="mb-2 h-5 w-5 text-slate-400" />
                          <p className="text-[10px] font-bold tracking-wider text-slate-300 uppercase">
                            Total Requests
                          </p>
                          <p className="mt-1.5 text-3xl font-black text-white">
                            {analytics.tool_stats?.weather?.total ?? 0}
                          </p>
                        </div>
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-5 text-center backdrop-blur-md">
                          <CheckCircle2 className="mb-2 h-5 w-5 text-emerald-400" />
                          <p className="text-[10px] font-bold tracking-wider text-emerald-300 uppercase">
                            Successful
                          </p>
                          <p className="mt-1.5 text-3xl font-black text-emerald-400">
                            {analytics.tool_stats?.weather?.successful ?? 0}
                          </p>
                        </div>
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-rose-500/40 bg-rose-500/10 p-5 text-center backdrop-blur-md">
                          <PhoneOff className="mb-2 h-5 w-5 text-rose-400" />
                          <p className="text-[10px] font-bold tracking-wider text-rose-300 uppercase">
                            Failed
                          </p>
                          <p className="mt-1.5 text-3xl font-black text-rose-400">
                            {analytics.tool_stats?.weather?.failed ?? 0}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: SUPPORT TICKETS (unchanged) */}
              {activeTab === 'tickets' && (
                <div className="space-y-4">
                  {isLoading && tickets.length === 0 ? (
                    <div className="flex h-40 items-center justify-center text-sm font-medium text-slate-300">
                      Loading tickets...
                    </div>
                  ) : tickets.length === 0 ? (
                    <div className="flex h-40 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-white/20 bg-white/5 p-8 text-center backdrop-blur-md">
                      <CheckCircle2 className="h-8 w-8 text-[#74c69d]" />
                      <p className="text-sm font-medium text-white">No active escalations</p>
                      <p className="text-xs text-slate-300">
                        All farmer support tickets are resolved.
                      </p>
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
                                ? 'border border-emerald-400/80 bg-emerald-950/40 shadow-[0_0_20px_rgba(82,183,136,0.3)] ring-1 ring-emerald-400/50'
                                : t.status === 'RESOLVED'
                                  ? 'border border-white/10 bg-white/5 opacity-60'
                                  : 'border border-white/15 bg-white/10 hover:border-white/30'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-xs font-bold text-[#74c69d]">
                                  #{t.ticket_id}
                                </span>
                                <span
                                  className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold tracking-wider uppercase ${getUrgencyBadge(t.urgency)}`}
                                >
                                  {t.urgency}
                                </span>
                              </div>
                              <span
                                className={`text-[11px] font-extrabold tracking-wider uppercase ${
                                  t.status === 'OFFICER_REPLIED'
                                    ? 'animate-pulse text-emerald-300'
                                    : t.status === 'RESOLVED'
                                      ? 'text-slate-400'
                                      : 'text-rose-400'
                                }`}
                              >
                                {t.status === 'OFFICER_REPLIED' ? 'OFFICER REPLIED' : t.status}
                              </span>
                            </div>

                            <div>
                              <h3 className="text-sm font-bold text-white">{t.topic}</h3>
                              <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-200">
                                {t.summary}
                              </p>
                            </div>

                            {t.officer_response && (
                              <div className="mt-1 flex gap-2 rounded-xl border border-emerald-500/40 bg-emerald-900/30 p-3 text-xs backdrop-blur-sm">
                                <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                                <div>
                                  <span className="font-bold text-emerald-300">
                                    Officer Response:
                                  </span>
                                  <p className="mt-0.5 text-slate-100 italic">
                                    &quot;{t.officer_response}&quot;
                                  </p>
                                </div>
                              </div>
                            )}

                            <div className="flex items-center justify-between border-t border-white/10 pt-2 text-[11px] text-slate-300">
                              <span>
                                Farmer: <strong className="text-white">{t.farmer_name}</strong>
                              </span>
                              <span>
                                Follow-up:{' '}
                                <strong className="text-[#74c69d]">
                                  {t.preferred_followup || 'Phone Call'}
                                </strong>
                              </span>
                              <span className="flex items-center gap-1 text-slate-400">
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
              )}

              {/* TAB 3: AGENT RESPONSES */}
              {activeTab === 'agent-responses' && (
                <div className="space-y-5">
                  <div className="flex items-center gap-2">
                    <Bot className="h-4 w-4 text-[#74c69d]" />
                    <h3 className="text-sm font-bold text-white">Agent Response Analytics</h3>
                  </div>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {(analytics.agent_stats || []).map((agent) => {
                      const rate =
                        agent.total > 0 ? Math.round((agent.successful / agent.total) * 100) : 0;
                      return (
                        <div
                          key={agent.name}
                          className="space-y-3 rounded-2xl border border-[#52b788]/30 bg-[#0c2419]/60 p-5 backdrop-blur-md"
                        >
                          <div className="flex items-center gap-3 border-b border-white/10 pb-3">
                            <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-[#52b788]/40 bg-[#52b788]/20 text-lg">
                              {agent.icon}
                            </span>
                            <div>
                              <p className="text-sm font-bold text-white">{agent.name}</p>
                              <p className="text-[10px] text-slate-400">Voice AI Agent</p>
                            </div>
                          </div>
                          <div className="grid grid-cols-3 gap-2">
                            <div className="flex flex-col items-center justify-center rounded-xl border border-white/10 bg-white/5 px-2 py-3 text-center">
                              <p className="text-[9px] font-bold tracking-wider text-slate-400 uppercase">
                                Total
                              </p>
                              <p className="mt-1 text-xl font-black text-white">{agent.total}</p>
                            </div>
                            <div className="flex flex-col items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-2 py-3 text-center">
                              <p className="text-[9px] font-bold tracking-wider text-emerald-400 uppercase">
                                Success
                              </p>
                              <p className="mt-1 text-xl font-black text-emerald-400">
                                {agent.successful}
                              </p>
                            </div>
                            <div className="flex flex-col items-center justify-center rounded-xl border border-rose-500/30 bg-rose-500/10 px-2 py-3 text-center">
                              <p className="text-[9px] font-bold tracking-wider text-rose-400 uppercase">
                                Failed
                              </p>
                              <p className="mt-1 text-xl font-black text-rose-400">
                                {agent.failed}
                              </p>
                            </div>
                          </div>
                          <div className="space-y-1">
                            <div className="flex justify-between text-[10px]">
                              <span className="text-slate-400">Success Rate</span>
                              <span className="font-bold text-emerald-300">{rate}%</span>
                            </div>
                            <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                              <div
                                className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all duration-700"
                                style={{
                                  width: `${rate}%`,
                                }}
                              />
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
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
          onClick={closeDetailModal}
          className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            onClick={(e) => e.stopPropagation()}
            className="flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-3xl border border-[#52b788]/50 bg-[#0c2419]/90 text-white shadow-2xl backdrop-blur-2xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/15 bg-white/5 px-6 py-4">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-bold text-[#74c69d]">
                  #{selectedTicket.ticket_id}
                </span>
                <span
                  className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold tracking-wider uppercase ${getUrgencyBadge(
                    selectedTicket.urgency
                  )}`}
                >
                  {selectedTicket.urgency}
                </span>
              </div>
              <button
                onClick={closeDetailModal}
                className="rounded-xl border border-white/15 bg-white/10 p-1.5 text-slate-200 hover:bg-white/20 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Detail Body */}
            <div className="flex-1 space-y-4 overflow-y-auto p-6 text-xs leading-relaxed text-slate-200">
              <div>
                <label className="text-[10px] font-bold tracking-wider text-slate-300 uppercase">
                  Topic / Crisis
                </label>
                <p className="text-base font-bold text-white">{selectedTicket.topic}</p>
              </div>

              <div>
                <label className="text-[10px] font-bold tracking-wider text-slate-300 uppercase">
                  Sanitized Issue Summary
                </label>
                <p className="mt-1 rounded-xl border border-white/10 bg-white/5 p-3 text-slate-200">
                  {selectedTicket.summary}
                </p>
              </div>

              {selectedTicket.officer_response && (
                <div>
                  <label className="text-[10px] font-bold tracking-wider text-emerald-300 uppercase">
                    Support Officer Response
                  </label>
                  <div className="mt-1 flex gap-2.5 rounded-xl border border-emerald-500/50 bg-emerald-950/60 p-3.5 text-slate-100 shadow-lg">
                    <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                    <p className="font-medium italic">
                      &quot;{selectedTicket.officer_response}&quot;
                    </p>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3 border-t border-white/10 pt-3 text-[11px]">
                <div>
                  <span className="text-slate-300">Farmer:</span>{' '}
                  <strong className="text-white">{selectedTicket.farmer_name}</strong>
                </div>
                <div>
                  <span className="text-slate-300">Follow-up:</span>{' '}
                  <strong className="text-[#74c69d]">
                    {selectedTicket.preferred_followup || 'Phone Call'}
                  </strong>
                </div>
                <div>
                  <span className="text-slate-300">Status:</span>{' '}
                  <strong className="text-emerald-300">{selectedTicket.status}</strong>
                </div>
                <div>
                  <span className="text-slate-300">Created:</span>{' '}
                  <strong className="text-white">
                    {new Date(selectedTicket.created_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </strong>
                </div>
              </div>
            </div>

            {/* Action Footer */}
            <div className="flex items-center justify-between border-t border-white/15 bg-white/5 p-4">
              {selectedTicket.status !== 'RESOLVED' ? (
                <button
                  onClick={() => handleResolveTicket(selectedTicket.ticket_id)}
                  className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-emerald-500/50 bg-[#2d6a4f] py-2.5 text-xs font-bold text-white transition-all hover:bg-emerald-600 active:scale-95"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Mark as Resolved
                </button>
              ) : (
                <div className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 py-2.5 text-xs font-medium text-slate-400">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  <span>Ticket Resolved</span>
                </div>
              )}
              <button
                onClick={closeDetailModal}
                className="ml-3 rounded-xl border border-white/15 bg-white/10 px-4 py-2.5 text-xs font-semibold text-slate-200 transition-all hover:bg-white/20 hover:text-white"
              >
                Close
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );

  // Compute full-button glow pulse styles (Day 8 Requirement)
  const getFullButtonGlowClass = () => {
    if (callOutcomeGlow === 'SUCCESS') {
      return 'ring-2 ring-emerald-400 animate-pulse shadow-[0_0_15px_rgba(52,211,153,0.6)]';
    }
    if (callOutcomeGlow === 'FAILED') {
      return 'ring-2 ring-amber-400 animate-pulse shadow-[0_0_15px_rgba(251,191,36,0.6)]';
    }
    return '';
  };

  return (
    <>
      {/* Step-1: Main Control Center Button Trigger */}
      <div className="relative inline-block">
        <button
          onClick={handleOpenModal}
          className={
            buttonStyle === 'header-button'
              ? `flex items-center gap-1.5 rounded-xl border border-emerald-500/30 bg-[#2d6a4f]/80 px-3 py-1.5 text-xs font-semibold text-white shadow-md transition-all hover:bg-[#2d6a4f] ${getFullButtonGlowClass()}`
              : `flex size-9 items-center justify-center rounded-full border border-white/25 bg-white/20 text-white shadow-sm transition-all hover:scale-105 hover:bg-white/30 active:scale-95 ${getFullButtonGlowClass()}`
          }
          title="Krishi Control Center (Analytics & Tickets)"
        >
          <Activity className="h-4 w-4" />
          {buttonStyle === 'header-button' && <span>Control Center</span>}
        </button>

        {/* Support Tickets Red Notification Corner Badge (Day 7 Preserved) */}
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
