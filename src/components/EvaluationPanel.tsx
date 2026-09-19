import React, { useState } from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  FileCheck2,
  Type,
  Hash,
} from 'lucide-react';
import { DocumentEvaluation } from '../types';

interface EvaluationPanelProps {
  evaluation: DocumentEvaluation | undefined;
  documentId: string;
  isVerified: boolean;
}

export const EvaluationPanel: React.FC<EvaluationPanelProps> = ({
  evaluation,
  documentId,
  isVerified,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!isVerified) {
    return (
      <div className="mx-4 my-3 p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs">
        <div className="flex items-center gap-2 text-amber-800 font-semibold mb-1">
          <AlertTriangle className="w-4 h-4 text-amber-600" />
          <span>Unverified Ground Truth — Evaluation Skipped</span>
        </div>
        <p className="text-amber-700/80 leading-relaxed">
          Document <code className="font-mono bg-amber-100 px-1 py-0.5 rounded text-amber-900">{documentId}</code> does
          not have a verified ground truth annotation. Per project invariants, CER/WER metrics are not computed for
          unverified documents. Only <code className="font-mono bg-amber-100 px-1 py-0.5 rounded text-amber-900">a01-000u.png</code> has
          been verified via <code className="font-mono bg-amber-100 px-1 py-0.5 rounded text-amber-900">config/a01-000u.ground_truth.json</code>.
        </p>
      </div>
    );
  }

  if (!evaluation || evaluation.status !== 'evaluated') {
    return (
      <div className="mx-4 my-3 p-3.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-500">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-slate-400" />
          <span>Evaluation data not yet available for this document.</span>
        </div>
      </div>
    );
  }

  const cer = evaluation.character ? (evaluation.character.rate * 100).toFixed(4) : '—';
  const wer = evaluation.word ? (evaluation.word.rate * 100).toFixed(4) : '—';
  const charAcc = evaluation.character ? ((1 - evaluation.character.rate) * 100).toFixed(4) : '—';

  return (
    <div className="mx-4 my-3">
      {/* Compact summary bar */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl text-xs cursor-pointer hover:bg-emerald-100/70 transition-colors"
      >
        <div className="flex items-center gap-3">
          <FileCheck2 className="w-4 h-4 text-emerald-600" />
          <span className="font-semibold text-emerald-900">Verified Ground Truth Evaluation</span>
          <div className="flex items-center gap-3 ml-4">
            <span className="font-mono font-bold text-emerald-700">CER {cer}%</span>
            <span className="text-emerald-400">•</span>
            <span className="font-mono font-bold text-slate-700">WER {wer}%</span>
            <span className="text-emerald-400">•</span>
            <span className="font-mono font-bold text-blue-700">Acc {charAcc}%</span>
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-emerald-600" />
        ) : (
          <ChevronDown className="w-4 h-4 text-emerald-600" />
        )}
      </button>

      {/* Expanded detail */}
      {isExpanded && (
        <div className="mt-2 bg-white border border-emerald-200 rounded-xl p-5 space-y-5 animate-in slide-in-from-top-1">
          {/* Metric cards */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-emerald-50/50 rounded-lg p-3 border border-emerald-100">
              <div className="flex items-center gap-1.5 mb-2">
                <Type className="w-3.5 h-3.5 text-emerald-600" />
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Character Error Rate</span>
              </div>
              <div className="text-2xl font-bold font-mono text-emerald-700">{cer}%</div>
              {evaluation.character && (
                <div className="text-[11px] text-slate-500 mt-1 font-mono">
                  {evaluation.character.substitutions}S + {evaluation.character.insertions}I + {evaluation.character.deletions}D
                  = {evaluation.character.total_edits} edits / {evaluation.character.reference_length} chars
                </div>
              )}
            </div>

            <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
              <div className="flex items-center gap-1.5 mb-2">
                <Hash className="w-3.5 h-3.5 text-slate-500" />
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Word Error Rate</span>
              </div>
              <div className="text-2xl font-bold font-mono text-slate-800">{wer}%</div>
              {evaluation.word && (
                <div className="text-[11px] text-slate-500 mt-1 font-mono">
                  {evaluation.word.substitutions}S + {evaluation.word.insertions}I + {evaluation.word.deletions}D
                  = {evaluation.word.total_edits} edits / {evaluation.word.reference_length} words
                </div>
              )}
            </div>

            <div className="bg-blue-50/50 rounded-lg p-3 border border-blue-100">
              <div className="flex items-center gap-1.5 mb-2">
                <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Character Accuracy</span>
              </div>
              <div className="text-2xl font-bold font-mono text-blue-700">{charAcc}%</div>
              <div className="text-[11px] text-slate-500 mt-1">
                1 − CER = Accuracy
              </div>
            </div>
          </div>

          {/* Exclusion notice */}
          {evaluation.exclusion && evaluation.exclusion.status !== 'none' && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs">
              <div className="font-semibold text-amber-800 mb-1">Exclusion Applied</div>
              <div className="text-amber-700 space-y-0.5">
                <div><span className="text-amber-500">Reason:</span> {evaluation.exclusion.reason}</div>
                <div><span className="text-amber-500">Source:</span> <code className="font-mono bg-amber-100 px-1 rounded">{evaluation.exclusion.source}</code></div>
                {evaluation.exclusion.excluded_raw_lines && (
                  <div>
                    <span className="text-amber-500">Excluded Lines:</span>{' '}
                    {evaluation.exclusion.excluded_raw_lines.map((l, i) => (
                      <code key={i} className="font-mono bg-amber-100 px-1 rounded mx-0.5">{l}</code>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Normalization policy */}
          <div className="text-[11px] text-slate-400 border-t border-slate-100 pt-3">
            <span className="font-semibold">Normalization:</span> Unicode NFKC • Case-sensitive • Whitespace collapsed • Punctuation preserved
          </div>
        </div>
      )}
    </div>
  );
};
