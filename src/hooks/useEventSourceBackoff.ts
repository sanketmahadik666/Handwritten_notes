import { useState, useEffect, useRef, useCallback } from 'react';
import { SSEConnectionState, SSEBackoffInfo, SSEEventRecord } from '../types';

interface UseEventSourceBackoffOptions {
  url: string | null;
  jobId: string | null;
  eventTypes?: string[];
  initialDelayMs?: number;
  maxDelayMs?: number;
  backoffFactor?: number;
  maxRetries?: number;
  jitterFactor?: number;
  onEvent?: (record: SSEEventRecord) => void;
  onSystemLog?: (message: string, level: 'info' | 'warn' | 'error' | 'success') => void;
}

const DEFAULT_EVENT_TYPES = [
  'job.started',
  'page.ocr_started',
  'page.ocr_complete',
  'page.notes_started',
  'page.notes_delta',
  'page.notes_complete',
  'page.failed',
  'job.finished',
];

export function useEventSourceBackoff({
  url,
  jobId,
  eventTypes = DEFAULT_EVENT_TYPES,
  initialDelayMs = 1000,
  maxDelayMs = 30000,
  backoffFactor = 2,
  maxRetries = 10,
  jitterFactor = 0.2,
  onEvent,
  onSystemLog,
}: UseEventSourceBackoffOptions) {
  const [connectionState, setConnectionState] = useState<SSEConnectionState>('disconnected');
  const [retryCount, setRetryCount] = useState(0);
  const [nextRetryDelayMs, setNextRetryDelayMs] = useState<number | null>(null);
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);
  const [lastConnectedTime, setLastConnectedTime] = useState<string | null>(null);
  const [lastErrorTime, setLastErrorTime] = useState<string | null>(null);
  const [heartbeatCount, setHeartbeatCount] = useState(0);
  const [lastHeartbeatTime, setLastHeartbeatTime] = useState<string | null>(null);

  // References to handle timers and instances across renders
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const countdownIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const retryCountRef = useRef(0);
  const isManuallyClosedRef = useRef(false);

  // Keep references to callbacks to prevent recreation loops
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;
  const onSystemLogRef = useRef(onSystemLog);
  onSystemLogRef.current = onSystemLog;

  const clearTimers = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
    setNextRetryDelayMs(null);
    setSecondsRemaining(null);
  }, []);

  const closeCurrentConnection = useCallback(() => {
    if (esRef.current) {
      try {
        esRef.current.close();
      } catch (err) {
        // ignore
      }
      esRef.current = null;
    }
  }, []);

  // Calculate exponential backoff delay with jitter
  const calculateBackoff = (attempt: number): number => {
    // delay = min(initialDelay * (backoffFactor ^ attempt), maxDelay)
    const exponential = initialDelayMs * Math.pow(backoffFactor, attempt);
    const capped = Math.min(exponential, maxDelayMs);

    // Apply uniform random jitter within +/- jitterFactor
    // e.g. with jitterFactor = 0.2, range is [0.8 * capped, 1.2 * capped]
    const jitterMultiplier = 1 + (Math.random() * 2 - 1) * jitterFactor;
    const randomized = Math.round(capped * jitterMultiplier);

    return Math.max(500, Math.min(randomized, maxDelayMs + 2000));
  };

  // Schedule reconnection with exponential backoff
  const scheduleReconnect = useCallback(() => {
    clearTimers();
    closeCurrentConnection();

    const currentAttempt = retryCountRef.current;

    if (currentAttempt >= maxRetries) {
      setConnectionState('disconnected');
      onSystemLogRef.current?.(
        `SSE reconnection halted: reached maximum retry limit (${maxRetries}). Please reconnect manually.`,
        'error'
      );
      return;
    }

    const delayMs = calculateBackoff(currentAttempt);
    const delaySec = Math.ceil(delayMs / 1000);

    retryCountRef.current = currentAttempt + 1;
    setRetryCount(retryCountRef.current);
    setConnectionState('reconnecting');
    setNextRetryDelayMs(delayMs);
    setSecondsRemaining(delaySec);

    onSystemLogRef.current?.(
      `Network drop detected on SSE stream. Exponential backoff retry #${retryCountRef.current}/${maxRetries} in ${delaySec}s (${delayMs}ms)...`,
      'warn'
    );

    // Live countdown timer for the user interface
    let timeLeft = delaySec;
    countdownIntervalRef.current = setInterval(() => {
      timeLeft -= 1;
      if (timeLeft <= 0) {
        if (countdownIntervalRef.current) {
          clearInterval(countdownIntervalRef.current);
          countdownIntervalRef.current = null;
        }
        setSecondsRemaining(0);
      } else {
        setSecondsRemaining(timeLeft);
      }
    }, 1000);

    // Execution timeout for reconnection
    reconnectTimeoutRef.current = setTimeout(() => {
      clearTimers();
      if (!isManuallyClosedRef.current && url) {
        initiateConnection();
      }
    }, delayMs);
  }, [clearTimers, closeCurrentConnection, maxRetries, initialDelayMs, backoffFactor, maxDelayMs, jitterFactor, url]);

  // Establish the EventSource connection
  const initiateConnection = useCallback(() => {
    if (!url) return;

    clearTimers();
    closeCurrentConnection();
    isManuallyClosedRef.current = false;

    setConnectionState((prev) => (prev === 'reconnecting' ? 'reconnecting' : 'connecting'));

    try {
      const es = new EventSource(url);
      esRef.current = es;

      es.onopen = () => {
        setConnectionState('connected');
        const nowStr = new Date().toISOString();
        setLastConnectedTime(nowStr);

        // If we were reconnecting, reset retry count and notify success
        if (retryCountRef.current > 0) {
          onSystemLogRef.current?.(
            `SSE connection restored after ${retryCountRef.current} backoff attempt(s). Stream active.`,
            'success'
          );
        } else {
          onSystemLogRef.current?.(`Connected to SSE stream for job ${jobId || ''}.`, 'info');
        }

        retryCountRef.current = 0;
        setRetryCount(0);
        clearTimers();

        // Start heartbeat counter for active stream
        heartbeatIntervalRef.current = setInterval(() => {
          setHeartbeatCount((c) => c + 1);
          setLastHeartbeatTime(new Date().toISOString());
        }, 15000);
      };

      es.onerror = () => {
        const errorTime = new Date().toISOString();
        setLastErrorTime(errorTime);

        // Native EventSource tries its own unthrottled reconnect unless closed.
        // We explicitly close it and handle reconnection with our exponential backoff.
        scheduleReconnect();
      };

      // Register standard application events
      eventTypes.forEach((type) => {
        es.addEventListener(type, (evt: MessageEvent) => {
          try {
            const parsed = JSON.parse(evt.data);
            const record: SSEEventRecord = {
              id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
              timestamp: new Date().toISOString(),
              type,
              job_id: jobId || parsed.job_id || '',
              data: parsed,
            };
            onEventRef.current?.(record);
          } catch (err) {
            // Handle plain-text event data if any
            const record: SSEEventRecord = {
              id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
              timestamp: new Date().toISOString(),
              type,
              job_id: jobId || '',
              data: { raw: evt.data },
            };
            onEventRef.current?.(record);
          }
        });
      });
    } catch (err: any) {
      setLastErrorTime(new Date().toISOString());
      scheduleReconnect();
    }
  }, [url, jobId, clearTimers, closeCurrentConnection, eventTypes, scheduleReconnect]);

  // Manual immediate reconnection by user
  const manualReconnect = useCallback(() => {
    retryCountRef.current = 0;
    setRetryCount(0);
    clearTimers();
    onSystemLogRef.current?.('Manual reconnection triggered. Connecting immediately...', 'info');
    initiateConnection();
  }, [clearTimers, initiateConnection]);

  // Disconnect cleanly
  const disconnect = useCallback(() => {
    isManuallyClosedRef.current = true;
    clearTimers();
    closeCurrentConnection();
    setConnectionState('disconnected');
    retryCountRef.current = 0;
    setRetryCount(0);
  }, [clearTimers, closeCurrentConnection]);

  // Simulate network drop for verifying exponential backoff resilience
  const simulateDrop = useCallback(() => {
    onSystemLogRef.current?.(
      'Simulated intermittent network drop triggered. Initiating exponential backoff reconnection flow...',
      'warn'
    );
    scheduleReconnect();
  }, [scheduleReconnect]);

  // Effect to manage connection when URL or Job ID changes
  useEffect(() => {
    if (!url) {
      disconnect();
      return;
    }

    retryCountRef.current = 0;
    setRetryCount(0);
    initiateConnection();

    return () => {
      clearTimers();
      closeCurrentConnection();
    };
  }, [url, jobId]);

  const backoffInfo: SSEBackoffInfo = {
    state: connectionState,
    retryCount,
    maxRetries,
    nextRetryDelayMs,
    secondsRemaining,
    lastConnectedTime,
    lastErrorTime,
  };

  return {
    connectionState,
    isConnected: connectionState === 'connected',
    isReconnecting: connectionState === 'reconnecting',
    isConnecting: connectionState === 'connecting',
    retryCount,
    maxRetries,
    secondsRemaining,
    nextRetryDelayMs,
    heartbeatCount,
    lastHeartbeatTime,
    backoffInfo,
    manualReconnect,
    simulateDrop,
    disconnect,
  };
}
