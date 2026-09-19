import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Header } from './components/Header';
import { JobList } from './components/JobList';
import { DocumentViewer } from './components/DocumentViewer';
import { NotesView } from './components/NotesView';
import { RawTextView } from './components/RawTextView';
import { CropViewer } from './components/CropViewer';
import { ErrorRecovery } from './components/ErrorRecovery';
import { LiveSSETerminal } from './components/LiveSSETerminal';
import { BenchmarkDashboard } from './components/BenchmarkDashboard';
import { HealthScreen } from './components/HealthScreen';
import { ArtifactBrowser } from './components/ArtifactBrowser';
import { ErrorBoundary } from './components/ErrorBoundary';
import { NewJobModal } from './components/NewJobModal';
import { ProvidersModal } from './components/ProvidersModal';
import { useEventSourceBackoff } from './hooks/useEventSourceBackoff';
import {
  HealthResponse,
  ProviderListResponse,
  JobStatusResponse,
  DocumentData,
  SSEEventRecord,
} from './types';
import { Eye, BookOpen, ShieldCheck, Terminal, LayoutGrid } from 'lucide-react';

export default function App() {
  const [currentView, setCurrentView] = useState<'workspace' | 'benchmark' | 'health' | 'artifacts'>('workspace');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [providerData, setProviderData] = useState<ProviderListResponse | null>(null);
  const [jobs, setJobs] = useState<{ job_id: string; status: string; total_pages: number; created_at: string; sample_preview: string }[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<JobStatusResponse | null>(null);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);

  const [documentData, setDocumentData] = useState<DocumentData | null>(null);
  const [rawText, setRawText] = useState<string>('');
  const [notesMarkdown, setNotesMarkdown] = useState<string>('');

  const [activeTab, setActiveTab] = useState<'viewer' | 'crops' | 'notes' | 'raw' | 'terminal'>('viewer');
  const [isNewJobOpen, setIsNewJobOpen] = useState(false);
  const [isProvidersOpen, setIsProvidersOpen] = useState(false);

  // SSE event stream and processing states
  const [sseEvents, setSseEvents] = useState<SSEEventRecord[]>([]);
  const [isGeneratingNotes, setIsGeneratingNotes] = useState(false);
  const [notesDelta, setNotesDelta] = useState<string | null>(null);
  const [isOcrRetrying, setIsOcrRetrying] = useState(false);

  // 1. Fetch initial health, providers, and jobs
  const fetchHealth = () => {
    fetch('/api/health')
      .then((res) => res.json())
      .then(setHealth)
      .catch(console.error);
  };

  const fetchProviders = () => {
    fetch('/api/providers')
      .then((res) => res.json())
      .then(setProviderData)
      .catch(console.error);
  };

  const fetchJobs = () => {
    fetch('/api/jobs')
      .then((res) => res.json())
      .then((data) => {
        setJobs(data);
        if (data.length > 0 && !selectedJobId) {
          setSelectedJobId(data[0].job_id);
        }
      })
      .catch(console.error);
  };

  useEffect(() => {
    fetchHealth();
    fetchProviders();
    fetchJobs();
  }, []);

  // 2. Load artifacts whenever selectedDocId changes
  const loadDocumentArtifacts = useCallback((jobId: string, docId: string) => {
    // Document JSON
    fetch(`/api/jobs/${jobId}/pages/${docId}/document.json`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setDocumentData(data))
      .catch(() => setDocumentData(null));

    // Raw TXT
    fetch(`/api/jobs/${jobId}/pages/${docId}/raw.txt`)
      .then((res) => (res.ok ? res.text() : ''))
      .then(setRawText)
      .catch(() => setRawText(''));

    // Notes MD
    fetch(`/api/jobs/${jobId}/pages/${docId}/notes.md`)
      .then((res) => (res.ok ? res.text() : ''))
      .then(setNotesMarkdown)
      .catch(() => setNotesMarkdown(''));
  }, []);

  // 3. When selectedJobId changes, load job details
  useEffect(() => {
    if (!selectedJobId) return;

    fetch(`/api/jobs/${selectedJobId}`)
      .then((res) => res.json())
      .then((job: JobStatusResponse) => {
        setSelectedJob(job);
        if (job.pages && job.pages.length > 0) {
          setSelectedDocId(job.pages[0].document_id);
        }
      })
      .catch(console.error);
  }, [selectedJobId]);

  // 4. Handle incoming SSE events from backoff-managed stream
  const handleSSEEvent = useCallback(
    (record: SSEEventRecord) => {
      setSseEvents((prev) => [record, ...prev].slice(0, 100));

      const { type, data } = record;
      
      setSelectedJob((prevJob) => {
        if (!prevJob) return prevJob;
        const newJob = { ...prevJob, pages: [...prevJob.pages] };
        
        if (data?.document_id) {
          const pageIndex = newJob.pages.findIndex(p => p.document_id === data.document_id);
          if (pageIndex !== -1) {
            const page = { ...newJob.pages[pageIndex] };
            if (type === 'page.ocr_started') page.status = 'ocr_running';
            else if (type === 'page.ocr_complete') page.status = 'ocr_complete';
            else if (type === 'page.ocr_failed') page.status = 'ocr_failed';
            else if (type === 'page.notes_queued') page.status = 'notes_queued';
            else if (type === 'page.notes_started') page.status = 'notes_running';
            else if (type === 'page.notes_complete') page.status = 'notes_ready';
            else if (type === 'page.notes_failed') page.status = 'notes_failed';
            else if (type === 'page.failed') page.status = 'failed';
            newJob.pages[pageIndex] = page;
          }
        }
        
        if (type === 'job.finished') newJob.status = 'completed';
        else if (type === 'job.failed') newJob.status = 'failed';
        
        return newJob;
      });

      if (type === 'page.notes_started') {
        setIsGeneratingNotes(true);
        setNotesDelta(null);
      } else if (type === 'page.notes_delta') {
        setNotesDelta(data?.delta || '');
      } else if (type === 'page.notes_complete') {
        setIsGeneratingNotes(false);
        setNotesDelta(null);
        // Refresh notes
        if (selectedJobId && selectedDocId && data?.document_id === selectedDocId) {
          loadDocumentArtifacts(selectedJobId, selectedDocId);
        }
      } else if (type === 'job.finished') {
        setIsGeneratingNotes(false);
        setIsOcrRetrying(false);
        fetchJobs();
      }
    },
    [selectedJobId, selectedDocId, loadDocumentArtifacts]
  );

  // 5. System log messages (network drops, exponential backoff retries, reconnections)
  const handleSystemLog = useCallback(
    (message: string, level: 'info' | 'warn' | 'error' | 'success') => {
      const record: SSEEventRecord = {
        id: `sys-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
        timestamp: new Date().toISOString(),
        type:
          level === 'warn'
            ? 'system.network_drop'
            : level === 'success'
            ? 'system.reconnected'
            : level === 'error'
            ? 'system.error'
            : 'system.info',
        job_id: selectedJobId || 'workspace',
        data: { message, level, timestamp: new Date().toISOString() },
      };
      setSseEvents((prev) => [record, ...prev].slice(0, 100));
    },
    [selectedJobId]
  );

  // 6. Connect to SSE stream with Exponential Backoff strategy
  const sseUrl = selectedJobId ? `/api/jobs/${selectedJobId}/events` : null;

  const {
    connectionState,
    isConnected: isSseConnected,
    retryCount: sseRetryCount,
    maxRetries: sseMaxRetries,
    secondsRemaining: sseSecondsRemaining,
    nextRetryDelayMs: sseNextRetryDelayMs,
    heartbeatCount,
    lastHeartbeatTime,
    manualReconnect: handleManualReconnect,
    simulateDrop: handleSimulateDrop,
  } = useEventSourceBackoff({
    url: sseUrl,
    jobId: selectedJobId,
    initialDelayMs: 1000,
    maxDelayMs: 30000,
    backoffFactor: 2,
    maxRetries: 10,
    jitterFactor: 0.2,
    onEvent: handleSSEEvent,
    onSystemLog: handleSystemLog,
  });

  useEffect(() => {
    if (selectedJobId && selectedDocId) {
      loadDocumentArtifacts(selectedJobId, selectedDocId);
    }
  }, [selectedJobId, selectedDocId, loadDocumentArtifacts]);

  // Actions
  const handleCancelJob = useCallback(async (jobId: string) => {
    try {
      await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' });
      if (selectedJobId === jobId) {
        setSelectedJobId(null);
        setSelectedJob(null);
        setSelectedDocId(null);
        setDocumentData(null);
      }
      fetchJobs();
    } catch (err) {
      console.error('Failed to cancel job:', err);
    }
  }, [selectedJobId]);

  const handleRetryNotes = () => {
    if (!selectedJobId || !selectedDocId) return;
    setIsGeneratingNotes(true);
    fetch(`/api/jobs/${selectedJobId}/pages/${selectedDocId}/retry-notes`, {
      method: 'POST',
    }).catch(console.error);
  };

  const handleRetryOcr = () => {
    if (!selectedJobId || !selectedDocId) return;
    setIsOcrRetrying(true);
    fetch(`/api/jobs/${selectedJobId}/pages/${selectedDocId}/retry-ocr`, {
      method: 'POST',
    }).catch(console.error);
  };

  const handleLaunchNewJob = (sampleFiles: string[], providerId: string) => {
    setIsNewJobOpen(false);
    fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider_id: providerId,
        file_paths: sampleFiles,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.job_id) {
          fetchJobs();
          setSelectedJobId(data.job_id);
          setActiveTab('terminal');
        }
      })
      .catch(console.error);
  };

  const handleAddProvider = (newProv: any) => {
    fetch('/api/providers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newProv),
    })
      .then(() => fetchProviders())
      .catch(console.error);
  };

  const handleUpdateProvider = (id: string, updates: any) => {
    fetch(`/api/providers/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
      .then(() => fetchProviders())
      .catch(console.error);
  };

  return (
    <div className="flex flex-col h-screen bg-slate-100 text-slate-900 overflow-hidden">
      {/* Top Header */}
      <Header
        currentView={currentView}
        onSelectView={setCurrentView}
        health={health}
        onRefreshHealth={fetchHealth}
        onOpenProviders={() => setIsProvidersOpen(true)}
        onNewJob={() => setIsNewJobOpen(true)}
        activeJobId={selectedJobId}
        activeJobStatus={selectedJob?.status}
      />

      {/* Main Content Area based on currentView */}
      <ErrorBoundary fallbackTitle="View Rendering Error">
        {currentView === 'benchmark' && <BenchmarkDashboard />}
        {currentView === 'health' && <HealthScreen />}
        {currentView === 'artifacts' && <ArtifactBrowser />}
      </ErrorBoundary>

      {currentView === 'workspace' && (
        <div className="flex-1 flex overflow-hidden">
          {/* Left: Job Runs & Pages list (fixed width) */}
          <aside className="w-72 sm:w-80 shrink-0 h-full">
            <JobList
              jobs={jobs}
              selectedJobId={selectedJobId}
              onSelectJob={(id) => setSelectedJobId(id)}
              selectedJob={selectedJob}
              selectedDocId={selectedDocId}
              onSelectDoc={(id) => setSelectedDocId(id)}
              onNewJobClick={() => setIsNewJobOpen(true)}
              onCancelJob={handleCancelJob}
            />
          </aside>

          {/* Center & Right: Document Inspector & Tabs */}
          <main className="flex-1 flex flex-col h-full overflow-hidden bg-white">
            {/* Main Navigation Tabs */}
            <div className="bg-white border-b border-slate-200 px-4 flex items-center justify-between">
              <div className="flex space-x-1">
                <button
                  onClick={() => setActiveTab('viewer')}
                  className={`flex items-center gap-1.5 py-3 px-3.5 text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
                    activeTab === 'viewer'
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>OCR Visualizer & Polygons</span>
                </button>

                <button
                  onClick={() => setActiveTab('crops')}
                  className={`flex items-center gap-1.5 py-3 px-3.5 text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
                    activeTab === 'crops'
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                  <span>Line Crops</span>
                </button>

                <button
                  onClick={() => setActiveTab('notes')}
                  className={`flex items-center gap-1.5 py-3 px-3.5 text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
                    activeTab === 'notes'
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <BookOpen className="w-3.5 h-3.5" />
                  <span>Study Notes (Markdown)</span>
                  {isGeneratingNotes && (
                    <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping" />
                  )}
                </button>

                <button
                  onClick={() => setActiveTab('raw')}
                  className={`flex items-center gap-1.5 py-3 px-3.5 text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
                    activeTab === 'raw'
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Raw OCR Text (Immutable)</span>
                </button>

                <button
                  onClick={() => setActiveTab('terminal')}
                  className={`flex items-center gap-1.5 py-3 px-3.5 text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
                    activeTab === 'terminal'
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <Terminal className="w-3.5 h-3.5" />
                  <span>SSE Event Stream</span>
                  {connectionState === 'connected' && (
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="Stream Active" />
                  )}
                  {connectionState === 'reconnecting' && (
                    <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" title={`Reconnecting (${sseSecondsRemaining}s)`} />
                  )}
                  {connectionState === 'connecting' && (
                    <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" title="Connecting..." />
                  )}
                  {connectionState === 'disconnected' && (
                    <span className="w-2 h-2 rounded-full bg-rose-500" title="Disconnected" />
                  )}
                </button>
              </div>

              {selectedDocId && (
                <div className="hidden md:flex items-center gap-2 text-xs text-slate-500 font-mono">
                  <span className="text-slate-400">Viewing:</span>
                  <span className="font-semibold text-slate-700">{selectedDocId}</span>
                </div>
              )}
            </div>

            {/* Error Recovery Banner */}
            {selectedJob && selectedDocId && (() => {
              const page = selectedJob.pages.find(p => p.document_id === selectedDocId);
              if (page && (page.status === 'ocr_failed' || page.status === 'notes_failed' || page.status === 'failed')) {
                return (
                  <ErrorRecovery 
                    status={page.status} 
                    onRetryOcr={handleRetryOcr}
                    onRetryNotes={handleRetryNotes}
                    isRetrying={isOcrRetrying || isGeneratingNotes}
                  />
                );
              }
              return null;
            })()}

            {/* Active Tab Views */}
            <div className="flex-1 overflow-hidden">
              {activeTab === 'viewer' && selectedJobId && selectedDocId && (
                <DocumentViewer
                  jobId={selectedJobId}
                  docId={selectedDocId}
                  documentData={documentData}
                  onRetryOcr={handleRetryOcr}
                  isOcrRetrying={isOcrRetrying}
                />
              )}

              {activeTab === 'crops' && selectedJobId && selectedDocId && (
                <CropViewer
                  jobId={selectedJobId}
                  docId={selectedDocId}
                  documentData={documentData}
                />
              )}

              {activeTab === 'notes' && (
                <NotesView
                  notesMarkdown={notesMarkdown}
                  onRetryNotes={handleRetryNotes}
                  isGeneratingNotes={isGeneratingNotes}
                  notesDelta={notesDelta}
                />
              )}

              {activeTab === 'raw' && selectedDocId && (
                <RawTextView
                  rawText={rawText}
                  sha256={
                    selectedJob?.pages.find((p) => p.document_id === selectedDocId)?.raw_sha256
                  }
                  docId={selectedDocId}
                />
              )}

              {activeTab === 'terminal' && selectedJobId && (
                <LiveSSETerminal
                  jobId={selectedJobId}
                  events={sseEvents}
                  isConnected={isSseConnected}
                  connectionState={connectionState}
                  retryCount={sseRetryCount}
                  maxRetries={sseMaxRetries}
                  secondsRemaining={sseSecondsRemaining}
                  nextRetryDelayMs={sseNextRetryDelayMs}
                  heartbeatCount={heartbeatCount}
                  lastHeartbeatTime={lastHeartbeatTime}
                  onClearEvents={() => setSseEvents([])}
                  onManualReconnect={handleManualReconnect}
                  onSimulateDrop={handleSimulateDrop}
                />
              )}
            </div>
          </main>
        </div>
      )}


      {/* Modals */}
      <NewJobModal
        isOpen={isNewJobOpen}
        onClose={() => setIsNewJobOpen(false)}
        onSubmit={handleLaunchNewJob}
        providers={providerData?.providers || []}
        defaultProviderId={providerData?.default_provider_id || 'gemini-flash'}
      />

      <ProvidersModal
        isOpen={isProvidersOpen}
        onClose={() => setIsProvidersOpen(false)}
        providers={providerData?.providers || []}
        onAddProvider={handleAddProvider}
        onUpdateProvider={handleUpdateProvider}
      />
    </div>
  );
}
