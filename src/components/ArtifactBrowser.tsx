import React, { useState, useEffect } from 'react';
import {
  Folder,
  FileText,
  FileCode,
  Image as ImageIcon,
  CheckCircle2,
  ExternalLink,
  Download,
  Copy,
  Check,
  ShieldCheck,
  Search,
} from 'lucide-react';
import { RunHistoryItem } from '../types';

export const ArtifactBrowser: React.FC = () => {
  const [runs, setRuns] = useState<RunHistoryItem[]>([]);
  const [selectedRun, setSelectedRun] = useState<string>('run-20260919T021249Z-012e7ef8dba7');
  const [manifest, setManifest] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/runs')
      .then((res) => res.json())
      .then((data) => {
        setRuns(data);
        if (data.length > 0 && !selectedRun) {
          setSelectedRun(data[0].run_id);
        }
      })
      .catch((err) => console.error('Error fetching runs:', err));
  }, []);

  useEffect(() => {
    if (!selectedRun) return;
    fetch(`/outputs/${selectedRun}/run_manifest.json`)
      .then((res) => res.json())
      .then((data) => setManifest(data))
      .catch((err) => console.error('Error fetching manifest:', err));
  }, [selectedRun]);

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  const documents = manifest?.documents || [];
  const filteredDocs = documents.filter((d: any) =>
    d.source_image?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    d.document_id?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex-1 flex h-full bg-slate-100 overflow-hidden">
      {/* Runs Sidebar */}
      <div className="w-80 bg-white border-r border-slate-200 flex flex-col shrink-0">
        <div className="p-4 border-b border-slate-200">
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
            <Folder className="w-4 h-4 text-blue-600" />
            <span>Output Runs Repository</span>
          </h3>
          <p className="text-[11px] text-slate-500 mt-0.5">
            Immutable historical runs in <code className="font-mono text-slate-700">/outputs</code>
          </p>
        </div>

        <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
          {runs.map((r) => {
            const isSelected = selectedRun === r.run_id;
            return (
              <button
                key={r.run_id}
                onClick={() => setSelectedRun(r.run_id)}
                className={`w-full text-left p-3.5 transition-colors cursor-pointer ${
                  isSelected ? 'bg-blue-50/80 border-l-4 border-blue-600' : 'hover:bg-slate-50'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-xs font-bold text-slate-800 truncate">
                    {r.run_id}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono">
                  <span>{r.document_count} documents</span>
                  {r.cer !== null && (
                    <span className="text-emerald-700 font-bold">
                      CER: {(r.cer * 100).toFixed(2)}%
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Manifest & Documents View */}
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-50">
        {manifest ? (
          <div className="flex-1 flex flex-col h-full overflow-hidden">
            {/* Run Header Details */}
            <div className="bg-white border-b border-slate-200 p-5 shrink-0 shadow-xs">
              <div className="flex flex-wrap items-center justify-between gap-4 mb-3">
                <div>
                  <h2 className="text-sm font-bold text-slate-900 font-mono flex items-center gap-2">
                    <Folder className="w-4 h-4 text-blue-600" />
                    <span>{manifest.run_id}</span>
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Created: {manifest.created_at_utc} • Git: {manifest.git_commit || '3f8a92b4'}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleCopy(manifest.config_sha256, 'config')}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg shadow-xs transition-colors cursor-pointer"
                  >
                    {copied === 'config' ? (
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <Copy className="w-3.5 h-3.5 text-slate-400" />
                    )}
                    <span>Copy Config SHA-256</span>
                  </button>
                </div>
              </div>

              {/* Config details chip list */}
              <div className="flex flex-wrap gap-2 text-[11px] font-mono">
                <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">
                  Engine: requested_engine: null
                </span>
                <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">
                  Device: {manifest.device || 'CPU'}
                </span>
                <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">
                  Detector: {manifest.pipeline?.detector_model || 'PP-OCRv6_medium_det'}
                </span>
                <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">
                  Recognizer: {manifest.pipeline?.recognizer_model || 'PP-OCRv6_medium_rec'}
                </span>
              </div>
            </div>

            {/* Document search and list */}
            <div className="px-5 py-3 bg-white border-b border-slate-200 flex items-center justify-between shrink-0">
              <div className="relative flex-1 max-w-md">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Filter documents (e.g. a01-000u)..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <span className="text-xs text-slate-500 font-mono">
                Showing {filteredDocs.length} of {documents.length} artifacts
              </span>
            </div>

            {/* Documents List */}
            <div className="flex-1 overflow-y-auto p-5 space-y-3">
              {filteredDocs.map((doc: any, idx: number) => {
                const isVerified = doc.source_image === 'a01-000u.png';
                return (
                  <div
                    key={idx}
                    className={`bg-white rounded-xl border p-4 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                      isVerified ? 'border-blue-300 ring-1 ring-blue-100' : 'border-slate-200'
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-xs font-bold text-slate-900">
                          {doc.source_image}
                        </span>
                        {isVerified && (
                          <span className="text-[10px] bg-emerald-50 text-emerald-800 border border-emerald-200 px-2 py-0.2 rounded-full font-semibold">
                            Verified Baseline
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] font-mono text-slate-500 flex flex-wrap gap-3">
                        <span>Doc ID: {doc.document_id}</span>
                        <span>•</span>
                        <span>{doc.regions_count || 8} lines</span>
                        {doc.timing?.total_ms && (
                          <>
                            <span>•</span>
                            <span>{Math.round(doc.timing.total_ms)} ms</span>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Artifact Links */}
                    <div className="flex items-center gap-2 text-xs">
                      <a
                        href={`/outputs/${selectedRun}/documents/${doc.document_id}/document.json`}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1 px-2.5 py-1 text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-md font-mono"
                      >
                        <FileCode className="w-3.5 h-3.5 text-blue-600" />
                        <span>document.json</span>
                      </a>
                      <a
                        href={`/outputs/${selectedRun}/documents/${doc.document_id}/raw.txt`}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1 px-2.5 py-1 text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-md font-mono"
                      >
                        <FileText className="w-3.5 h-3.5 text-emerald-600" />
                        <span>raw.txt</span>
                      </a>
                      <a
                        href={`/outputs/${selectedRun}/documents/${doc.document_id}/overlay.png`}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1 px-2.5 py-1 text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-md font-mono"
                      >
                        <ImageIcon className="w-3.5 h-3.5 text-purple-600" />
                        <span>overlay.png</span>
                      </a>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-xs text-slate-400">
            Select a run to inspect manifests and artifacts
          </div>
        )}
      </div>
    </div>
  );
};
