import React, { useState } from 'react';
import { Copy, Check, ShieldCheck, Hash } from 'lucide-react';

interface RawTextViewProps {
  rawText: string;
  sha256?: string | null;
  docId: string;
}

export const RawTextView: React.FC<RawTextViewProps> = ({ rawText, sha256, docId }) => {
  const [copied, setCopied] = useState(false);

  const lines = rawText.split('\n');
  const wordCount = rawText.trim() ? rawText.trim().split(/\s+/).length : 0;
  const charCount = rawText.length;

  const handleCopy = () => {
    navigator.clipboard.writeText(rawText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 overflow-hidden">
      {/* Stats bar */}
      <div className="bg-white border-b border-slate-200 px-4 py-2.5 flex items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-4 text-slate-600">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
            <span className="font-medium text-slate-800">Immutable OCR Raw</span>
          </div>
          <span>•</span>
          <span>{lines.length} lines</span>
          <span>•</span>
          <span>{wordCount} words</span>
          <span>•</span>
          <span>{charCount} chars</span>
        </div>

        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-3 py-1 text-xs font-medium text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg transition-colors cursor-pointer"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-600" />
              <span className="text-emerald-600 font-semibold">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5 text-slate-500" />
              <span>Copy Raw</span>
            </>
          )}
        </button>
      </div>

      {/* SHA256 info banner */}
      {sha256 && (
        <div className="bg-slate-100 border-b border-slate-200 px-4 py-1.5 text-[11px] font-mono text-slate-500 flex items-center gap-2">
          <Hash className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-slate-600 font-semibold">SHA-256:</span>
          <span className="truncate">{sha256}</span>
        </div>
      )}

      {/* Line-numbered raw view */}
      <div className="flex-1 overflow-y-auto p-4 max-w-4xl mx-auto w-full">
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          <table className="w-full text-xs font-mono">
            <tbody>
              {lines.map((line, idx) => (
                <tr key={idx} className="hover:bg-blue-50/40 border-b border-slate-100 last:border-0">
                  <td className="w-12 py-2 pl-3 pr-2 text-right text-slate-400 select-none bg-slate-50/50 border-r border-slate-100">
                    {idx + 1}
                  </td>
                  <td className="py-2 px-3 text-slate-900 whitespace-pre-wrap leading-relaxed">
                    {line || <span className="text-slate-300 italic">(empty line)</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
