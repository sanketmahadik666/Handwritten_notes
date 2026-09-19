import React, { useState } from 'react';
import Markdown from 'react-markdown';
import { Sparkles, Copy, Check, RefreshCw, FileText, Code } from 'lucide-react';

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
        </div>
      </div>

      {/* Generation Stream Progress Alert */}
      {isGeneratingNotes && (
        <div className="bg-blue-50 border-b border-blue-100 px-4 py-2 flex items-center gap-2 text-xs text-blue-700 animate-pulse">
          <Sparkles className="w-4 h-4 text-blue-600 shrink-0" />
          <span>{notesDelta || 'Synthesizing structured Markdown study notes from raw OCR tokens...'}</span>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6 max-w-4xl mx-auto w-full">
        {viewMode === 'rendered' ? (
          <div className="prose prose-slate max-w-none prose-headings:font-bold prose-h1:text-xl prose-h2:text-base prose-h2:text-blue-900 prose-h2:border-b prose-h2:border-slate-100 prose-h2:pb-1.5 prose-p:text-sm prose-p:leading-relaxed prose-li:text-sm prose-code:text-xs prose-code:bg-slate-100 prose-code:px-1 prose-code:py-0.5 prose-code:rounded">
            <Markdown>{notesMarkdown || '*No study notes generated yet. Click Regenerate Notes above.*'}</Markdown>
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
