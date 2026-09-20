import React, { useState } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github-dark-dimmed.css';
import { Sparkles, Copy, Check, RefreshCw, FileText, Code, Download, Clock } from 'lucide-react';

interface NotesViewProps {
  notesMarkdown: string;
  onRetryNotes: () => void;
  isGeneratingNotes: boolean;
  notesDelta: string | null;
}

export const NotesView: React.FC<NotesViewProps> = ({
  notesMarkdown,
  onRetryNotes,
  isGeneratingNotes,
  notesDelta,
}) => {
  const [viewMode, setViewMode] = useState<'rendered' | 'raw'>('rendered');
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(notesMarkdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col h-full bg-white overflow-hidden">
      {/* Action Header */}
      <div className="border-b border-slate-200 px-4 py-2.5 flex items-center justify-between gap-3 bg-slate-50/50">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg border border-slate-200 text-xs">
            <button
              onClick={() => setViewMode('rendered')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors cursor-pointer flex items-center gap-1 ${
                viewMode === 'rendered'
                  ? 'bg-white text-blue-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Study Notes</span>
            </button>
            <button
              onClick={() => setViewMode('raw')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors cursor-pointer flex items-center gap-1 ${
                viewMode === 'raw'
                  ? 'bg-white text-blue-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Code className="w-3.5 h-3.5" />
              <span>Markdown Source</span>
            </button>
          </div>

          {/* Stats */}
          {notesMarkdown && (
            <div className="hidden sm:flex items-center gap-3 text-[11px] text-slate-400 font-mono">
              <span>{notesMarkdown.split(/\s+/).filter(Boolean).length} words</span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                ~{Math.max(1, Math.round(notesMarkdown.split(/\s+/).filter(Boolean).length / 200))} min read
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Copy Button */}
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1 text-xs font-medium text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg transition-colors cursor-pointer"
            title="Copy Markdown"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-600" />
                <span className="text-emerald-600 font-semibold">Copied!</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5 text-slate-500" />
                <span>Copy</span>
              </>
            )}
          </button>

          {/* Regenerate AI Notes */}
          <button
            onClick={onRetryNotes}
            disabled={isGeneratingNotes}
            className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors cursor-pointer shadow-xs disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isGeneratingNotes ? 'animate-spin' : ''}`} />
            <span>{isGeneratingNotes ? 'Synthesizing...' : 'Regenerate Notes'}</span>
          </button>

          {/* Download as .md */}
          {notesMarkdown && (
            <button
              onClick={() => {
                const blob = new Blob([notesMarkdown], { type: 'text/markdown' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'study_notes.md';
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="flex items-center gap-1.5 px-3 py-1 text-xs font-medium text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg transition-colors cursor-pointer"
              title="Download Markdown"
            >
              <Download className="w-3.5 h-3.5 text-slate-500" />
              <span className="hidden sm:inline">.md</span>
            </button>
          )}
        </div>
      </div>

      {/* Generation Stream Progress Alert */}
      {isGeneratingNotes && (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-blue-100 px-4 py-2.5 flex items-center gap-2 text-xs text-blue-700">
          <Sparkles className="w-4 h-4 text-blue-600 shrink-0 animate-pulse" />
          <span className="font-medium">{notesDelta || 'Synthesizing structured Markdown study notes from raw OCR tokens...'}</span>
          <div className="ml-auto w-24 h-1.5 bg-blue-200 rounded-full overflow-hidden">
            <div className="h-full bg-blue-600 rounded-full animate-pulse" style={{ width: '60%' }}></div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6 max-w-4xl mx-auto w-full">
        {viewMode === 'rendered' ? (
          <div className="prose prose-slate max-w-none prose-headings:font-bold prose-h1:text-2xl prose-h2:text-xl prose-h2:text-blue-900 prose-h2:border-b prose-h2:border-slate-100 prose-h2:pb-2 prose-h2:mb-4 prose-p:text-sm prose-p:leading-relaxed prose-li:text-sm prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:bg-slate-100 prose-code:text-rose-600 prose-code:before:content-none prose-code:after:content-none prose-pre:p-0 prose-pre:bg-transparent prose-table:border prose-table:border-slate-200 prose-th:bg-slate-50 prose-th:p-2 prose-th:border prose-th:border-slate-200 prose-td:p-2 prose-td:border prose-td:border-slate-200">
            <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
              {notesMarkdown || '*No study notes generated yet. Click Regenerate Notes above.*'}
            </Markdown>
          </div>
        ) : (
          <div className="relative">
            <pre className="p-4 bg-slate-900 text-slate-100 rounded-xl text-xs font-mono leading-relaxed overflow-x-auto selection:bg-blue-600">
              {notesMarkdown}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};
