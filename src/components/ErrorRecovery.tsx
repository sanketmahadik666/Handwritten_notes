import React from 'react';
import { AlertOctagon, RotateCcw, XCircle, ArrowRight } from 'lucide-react';

interface ErrorRecoveryProps {
  status: string;
  errorMsg?: string;
  onRetryOcr?: () => void;
  onRetryNotes?: () => void;
  onSkip?: () => void;
  isRetrying?: boolean;
}

export const ErrorRecovery: React.FC<ErrorRecoveryProps> = ({
  status,
  errorMsg,
  onRetryOcr,
  onRetryNotes,
  onSkip,
  isRetrying = false,
}) => {
  const isOcrError = status === 'ocr_failed' || status === 'failed';
  const isNotesError = status === 'notes_failed';

  if (!isOcrError && !isNotesError) return null;

  return (
    <div className="m-4 bg-rose-50 border-l-4 border-rose-500 rounded-r-lg shadow-sm p-4 animate-in slide-in-from-top-2">
      <div className="flex items-start">
        <div className="shrink-0">
          <AlertOctagon className="h-5 w-5 text-rose-600" aria-hidden="true" />
        </div>
        <div className="ml-3 flex-1">
          <h3 className="text-sm font-semibold text-rose-800">
            {isOcrError ? 'OCR Processing Failed' : 'Notes Generation Failed'}
          </h3>
          <div className="mt-1 text-xs text-rose-700">
            <p>
              {errorMsg || 'An unexpected error occurred during processing. The system halted execution for this page.'}
            </p>
          </div>
          <div className="mt-4 flex gap-3">
            {isOcrError && onRetryOcr && (
              <button
                type="button"
                onClick={onRetryOcr}
                disabled={isRetrying}
                className="inline-flex items-center gap-1.5 rounded-md bg-rose-100 px-3 py-1.5 text-xs font-semibold text-rose-800 hover:bg-rose-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 disabled:opacity-50 transition-colors cursor-pointer"
              >
                <RotateCcw className={`w-3.5 h-3.5 ${isRetrying ? 'animate-spin' : ''}`} />
                Retry OCR
              </button>
            )}
            {isNotesError && onRetryNotes && (
              <button
                type="button"
                onClick={onRetryNotes}
                disabled={isRetrying}
                className="inline-flex items-center gap-1.5 rounded-md bg-rose-100 px-3 py-1.5 text-xs font-semibold text-rose-800 hover:bg-rose-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 disabled:opacity-50 transition-colors cursor-pointer"
              >
                <RotateCcw className={`w-3.5 h-3.5 ${isRetrying ? 'animate-spin' : ''}`} />
                Retry Notes
              </button>
            )}
            {onSkip && (
              <button
                type="button"
                onClick={onSkip}
                className="inline-flex items-center gap-1.5 rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-xs ring-1 ring-inset ring-slate-300 hover:bg-slate-50 transition-colors cursor-pointer"
              >
                <ArrowRight className="w-3.5 h-3.5" />
                Skip Page
              </button>
            )}
          </div>
        </div>
        {onSkip && (
          <div className="ml-auto pl-3">
            <div className="-mx-1.5 -my-1.5">
              <button
                type="button"
                onClick={onSkip}
                className="inline-flex rounded-md bg-rose-50 p-1.5 text-rose-500 hover:bg-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-600 focus:ring-offset-2 focus:ring-offset-rose-50 cursor-pointer"
              >
                <span className="sr-only">Dismiss</span>
                <XCircle className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
