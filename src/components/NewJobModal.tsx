import React, { useState, useEffect } from 'react';
import { X, Radio, Sparkles, Check, FileText } from 'lucide-react';
import { SampleImageItem, ProviderModel } from '../types';

interface NewJobModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (sampleFiles: string[], providerId: string) => void;
  providers: ProviderModel[];
  defaultProviderId: string;
}

export const NewJobModal: React.FC<NewJobModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  providers,
  defaultProviderId,
}) => {
  const [samples, setSamples] = useState<SampleImageItem[]>([]);
  const [selectedSamples, setSelectedSamples] = useState<string[]>(['a01-000u.png']);
  const [selectedProvider, setSelectedProvider] = useState<string>(defaultProviderId);
  const [isLoadingSamples, setIsLoadingSamples] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setIsLoadingSamples(true);
      fetch('/api/samples')
        .then((res) => res.json())
        .then((data) => {
          setSamples(data);
          setIsLoadingSamples(false);
        })
        .catch(() => setIsLoadingSamples(false));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const toggleSample = (name: string) => {
    if (selectedSamples.includes(name)) {
      if (selectedSamples.length > 1) {
        setSelectedSamples(selectedSamples.filter((s) => s !== name));
      }
    } else {
      setSelectedSamples([...selectedSamples, name]);
    }
  };

  const handleLaunch = () => {
    onSubmit(selectedSamples, selectedProvider);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center">
              <Radio className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">
                Launch OCR & Study Notes Job
              </h2>
              <p className="text-xs text-slate-500">
                Process handwritten IAM English documents with PP-OCRv6 and AI Notes
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Provider Selection */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
              1. Choose Notes Synthesis Provider
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              {providers.map((p) => {
                const isSelected = selectedProvider === p.id;
                return (
                  <div
                    key={p.id}
                    onClick={() => setSelectedProvider(p.id)}
                    className={`p-3 rounded-xl border transition-all cursor-pointer ${
                      isSelected
                        ? 'border-blue-600 bg-blue-50/60 ring-1 ring-blue-600'
                        : 'border-slate-200 hover:border-slate-300 bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold text-slate-900">{p.label.split(' ')[0]}</span>
                      {isSelected && <Check className="w-3.5 h-3.5 text-blue-600" />}
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono truncate">{p.model}</div>
                    <div className="mt-2 text-[10px] text-slate-400">
                      {p.has_api_key ? 'Key Configured' : 'Local / Free Tier'}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Sample Scans Selection */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                2. Select IAM Handwritten Document Scans
              </label>
              <span className="text-xs text-slate-500">
                {selectedSamples.length} selected
              </span>
            </div>

            {isLoadingSamples ? (
              <div className="p-8 text-center text-xs text-slate-400">Loading sample scans...</div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 max-h-56 overflow-y-auto p-1">
                {samples.map((sample) => {
                  const isChecked = selectedSamples.includes(sample.name);
                  return (
                    <div
                      key={sample.name}
                      onClick={() => toggleSample(sample.name)}
                      className={`p-2 rounded-xl border transition-all cursor-pointer flex flex-col items-center text-center ${
                        isChecked
                          ? 'border-blue-600 bg-blue-50/50 shadow-xs'
                          : 'border-slate-200 hover:border-slate-300 bg-white'
                      }`}
                    >
                      <div className="w-full h-16 bg-slate-100 rounded-lg mb-1.5 overflow-hidden flex items-center justify-center">
                        <img
                          src={sample.path}
                          alt={sample.name}
                          className="w-full h-full object-cover"
                        />
                      </div>
                      <span className="text-xs font-mono font-medium text-slate-800 truncate w-full">
                        {sample.name}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <span className="text-xs text-slate-500">
            Sends <code className="font-mono text-slate-700">POST /api/jobs</code> & connects SSE
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 cursor-pointer"
            >
              Cancel
            </button>
            <button
              onClick={handleLaunch}
              className="px-5 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-xs transition-colors cursor-pointer"
            >
              Start Pipeline Run
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
