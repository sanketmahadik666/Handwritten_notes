import React, { useState } from 'react';
import {
  Terminal,
  Activity,
  Heart,
  Trash2,
  RefreshCw,
  Wifi,
  WifiOff,
  AlertTriangle,
  Zap,
} from 'lucide-react';
import { SSEEventRecord, SSEConnectionState } from '../types';

interface LiveSSETerminalProps {
  jobId: string;
  events: SSEEventRecord[];
  isConnected: boolean;
  connectionState?: SSEConnectionState;
  retryCount?: number;
  maxRetries?: number;
  secondsRemaining?: number | null;
  nextRetryDelayMs?: number | null;
  heartbeatCount: number;
  lastHeartbeatTime: string | null;
  onClearEvents: () => void;
  onManualReconnect?: () => void;
  onSimulateDrop?: () => void;
}

export const LiveSSETerminal: React.FC<LiveSSETerminalProps> = ({
  jobId,
  events,
  isConnected,
  connectionState = isConnected ? 'connected' : 'disconnected',
  retryCount = 0,
  maxRetries = 10,
  secondsRemaining = null,
  nextRetryDelayMs = null,
  heartbeatCount,
  lastHeartbeatTime,
  onClearEvents,
  onManualReconnect,
  onSimulateDrop,
}) => {
  const [filterType, setFilterType] = useState<string>('all');

  const filteredEvents = events.filter((evt) => {
    if (filterType === 'all') return true;
    if (filterType === 'ocr') return evt.type.includes('ocr');
    if (filterType === 'notes') return evt.type.includes('notes');
    if (filterType === 'system') return evt.type.startsWith('system.');
    return true;
  });

  return (
    <div className="flex flex-col h-full bg-slate-900 text-slate-200 overflow-hidden font-mono text-xs">
      {/* Terminal Title Bar */}
      <div className="bg-slate-950 border-b border-slate-800 px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-emerald-400" />
          <span className="font-bold text-slate-200">
            SSE Stream Monitor: <span className="text-emerald-400">{jobId}</span>
          </span>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Heartbeat Badge */}
          <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-slate-800/90 border border-slate-700 text-[11px]">
            <Heart
              className={`w-3 h-3 ${
                heartbeatCount > 0 ? 'text-rose-500 animate-ping' : 'text-slate-500'
              }`}
            />
            <span className="text-slate-400">15s Heartbeats:</span>
            <span className="text-rose-300 font-bold">{heartbeatCount}</span>
          </div>

          {/* Connection status with Exponential Backoff feedback */}
          <div className="flex items-center gap-2">
            {connectionState === 'connected' && (
              <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-950/80 border border-emerald-700/80 text-emerald-300 text-[11px]">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <Wifi className="w-3 h-3 text-emerald-400" />
                <span>Stream Active</span>
              </div>
            )}

            {connectionState === 'connecting' && (
              <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-blue-950/80 border border-blue-700/80 text-blue-300 text-[11px]">
                <RefreshCw className="w-3 h-3 text-blue-400 animate-spin" />
                <span>Connecting...</span>
              </div>
            )}

            {connectionState === 'reconnecting' && (
              <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-950/80 border border-amber-600/80 text-amber-300 text-[11px]">
                <RefreshCw className="w-3 h-3 text-amber-400 animate-spin" />
                <span>
                  Retrying in {secondsRemaining !== null ? `${secondsRemaining}s` : '...'} (Attempt {retryCount}/{maxRetries})
                </span>
              </div>
            )}

            {connectionState === 'disconnected' && (
              <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-rose-950/80 border border-rose-700/80 text-rose-300 text-[11px]">
                <WifiOff className="w-3 h-3 text-rose-400" />
                <span>Disconnected</span>
              </div>
            )}

            {/* Manual Reconnect Action */}
            {onManualReconnect && connectionState !== 'connected' && (
              <button
                onClick={onManualReconnect}
                className="flex items-center gap-1 px-2.5 py-0.5 text-[11px] font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-full border border-blue-500 transition-colors cursor-pointer"
                title="Bypass exponential backoff timer and reconnect immediately"
              >
                <Zap className="w-3 h-3" />
                <span>Reconnect Now</span>
              </button>
            )}

            {/* Simulate Drop button for testing exponential backoff */}
            {onSimulateDrop && connectionState === 'connected' && (
              <button
                onClick={onSimulateDrop}
                className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium text-amber-300/90 hover:text-amber-200 bg-amber-950/50 hover:bg-amber-900/60 border border-amber-800/60 rounded-full transition-colors cursor-pointer"
                title="Simulate an intermittent network drop to test the exponential backoff reconnection algorithm"
              >
                <AlertTriangle className="w-2.5 h-2.5 text-amber-400" />
                <span>Simulate Drop</span>
              </button>
            )}
          </div>

          {/* Clear button */}
          <button
            onClick={onClearEvents}
            className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 cursor-pointer"
            title="Clear event history"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Network Drop / Reconnection Notification Banner */}
      {connectionState === 'reconnecting' && (
        <div className="bg-amber-950/70 border-b border-amber-800/80 px-4 py-2 flex items-center justify-between gap-3 text-amber-200 text-xs shrink-0">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>
              <strong>Intermittent Network Drop:</strong> Exponential backoff active (initial 1s, factor 2x, max 30s + ±20% jitter). Attempting reconnection in {secondsRemaining ?? 0}s (Attempt {retryCount}/{maxRetries}).
            </span>
          </div>
          {onManualReconnect && (
            <button
              onClick={onManualReconnect}
              className="px-2.5 py-1 text-[11px] font-bold bg-amber-600 hover:bg-amber-500 text-slate-950 rounded transition-colors cursor-pointer shrink-0"
            >
              Retry Now
            </button>
          )}
        </div>
      )}

      {/* Filter Tabs Bar */}
      <div className="bg-slate-950/60 border-b border-slate-800 px-4 py-1.5 flex items-center justify-between text-[11px]">
        <div className="flex items-center gap-2">
          <span className="text-slate-500">Filter:</span>
          {(['all', 'ocr', 'notes', 'system'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilterType(f)}
              className={`px-2 py-0.5 rounded cursor-pointer capitalize transition-colors ${
                filterType === f
                  ? 'bg-slate-800 text-white font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
        <div className="text-slate-500 text-[10px]">
          Showing {filteredEvents.length} of {events.length} events
        </div>
      </div>

      {/* Events Stream Feed */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {filteredEvents.length === 0 ? (
          <div className="py-12 text-center text-slate-500">
            <Activity className="w-8 h-8 mx-auto mb-2 opacity-40 animate-pulse" />
            <p>Listening on /api/jobs/{jobId}/events...</p>
            <p className="text-[10px] text-slate-600 mt-1">
              Events will log in real time as OCR & AI Notes pipeline executes.
            </p>
          </div>
        ) : (
          filteredEvents.map((evt) => {
            const timeStr = new Date(evt.timestamp).toLocaleTimeString();
            let badgeColor = 'bg-blue-900/60 text-blue-300 border-blue-700';

            if (evt.type.startsWith('system.')) {
              if (evt.type.includes('drop') || evt.type.includes('error')) {
                badgeColor = 'bg-amber-900/70 text-amber-300 border-amber-600';
              } else if (evt.type.includes('reconnected') || evt.type.includes('success')) {
                badgeColor = 'bg-emerald-900/70 text-emerald-300 border-emerald-600';
              } else {
                badgeColor = 'bg-slate-800 text-slate-300 border-slate-700';
              }
            } else if (evt.type.includes('complete') || evt.type.includes('finished')) {
              badgeColor = 'bg-emerald-900/60 text-emerald-300 border-emerald-700';
            } else if (evt.type.includes('failed')) {
              badgeColor = 'bg-rose-900/60 text-rose-300 border-rose-700';
            } else if (evt.type.includes('delta')) {
              badgeColor = 'bg-purple-900/60 text-purple-300 border-purple-700';
            }

            return (
              <div
                key={evt.id}
                className="bg-slate-950/70 border border-slate-800/80 rounded-lg p-2.5 shadow-xs transition-colors hover:border-slate-700"
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-slate-500">{timeStr}</span>
                    <span
                      className={`text-[11px] px-2 py-0.5 rounded font-semibold border ${badgeColor}`}
                    >
                      {evt.type}
                    </span>
                  </div>
                  {evt.data?.document_id && (
                    <span className="text-[10px] text-slate-400 font-mono">
                      doc: {evt.data.document_id}
                    </span>
                  )}
                </div>
                <pre className="text-[11px] text-slate-300 whitespace-pre-wrap leading-relaxed overflow-x-auto p-1.5 bg-slate-900/50 rounded border border-slate-800/40">
                  {typeof evt.data === 'string'
                    ? evt.data
                    : JSON.stringify(evt.data, null, 2)}
                </pre>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
