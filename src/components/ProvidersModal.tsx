import React, { useState } from 'react';
import { X, Sparkles, Check, Plus, Key, Globe, Server } from 'lucide-react';
import { ProviderModel } from '../types';

interface ProvidersModalProps {
  isOpen: boolean;
  onClose: () => void;
  providers: ProviderModel[];
  onAddProvider: (provider: any) => void;
}

export const ProvidersModal: React.FC<ProvidersModalProps> = ({
  isOpen,
  onClose,
  providers,
  onAddProvider,
}) => {
  const [showAddForm, setShowAddForm] = useState(false);
  const [newId, setNewId] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const [newBaseUrl, setNewBaseUrl] = useState('http://localhost:11434/v1');
  const [newModel, setNewModel] = useState('llama3.2');

  if (!isOpen) return null;

  const handleSubmitNew = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newId || !newLabel || !newBaseUrl || !newModel) return;
    onAddProvider({
      id: newId,
      label: newLabel,
      protocol: 'openai_compatible',
      base_url: newBaseUrl,
      model: newModel,
    });
    setShowAddForm(false);
    setNewId('');
    setNewLabel('');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-600 flex items-center justify-center">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">
                AI Note Providers Registry
              </h2>
              <p className="text-xs text-slate-500">
                Manage LLMs utilized for synthesizing Markdown study notes
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
        <div className="p-6 overflow-y-auto space-y-4">
          <div className="space-y-3">
            {providers.map((p) => (
              <div
                key={p.id}
                className="p-4 rounded-xl border border-slate-200 bg-white hover:border-slate-300 transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-slate-900">{p.label}</span>
                    {p.has_api_key && (
                      <span className="text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full font-medium flex items-center gap-1">
                        <Check className="w-3 h-3" /> Ready
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] font-mono text-slate-400 bg-slate-50 px-2 py-0.5 rounded border border-slate-100">
                    {p.protocol}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 font-mono">
                  <div>
                    <span className="text-slate-400 font-sans">Model: </span>
                    <span className="text-slate-800 font-semibold">{p.model}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 font-sans">Endpoint: </span>
                    <span className="text-slate-700 truncate block">{p.base_url}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Add custom provider toggle */}
          {!showAddForm ? (
            <button
              onClick={() => setShowAddForm(true)}
              className="w-full py-2.5 px-4 text-xs font-semibold text-blue-600 border border-dashed border-blue-300 hover:bg-blue-50/50 rounded-xl transition-colors cursor-pointer flex items-center justify-center gap-1.5"
            >
              <Plus className="w-4 h-4" />
              <span>Register Custom OpenAI-Compatible Provider</span>
            </button>
          ) : (
            <form onSubmit={handleSubmitNew} className="p-4 rounded-xl border border-blue-200 bg-blue-50/30 space-y-3 text-xs">
              <div className="font-bold text-slate-800">New Provider Details</div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-600 mb-1">Provider ID</label>
                  <input
                    type="text"
                    required
                    placeholder="my-llm"
                    value={newId}
                    onChange={(e) => setNewId(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-slate-600 mb-1">Label</label>
                  <input
                    type="text"
                    required
                    placeholder="Local vLLM / Ollama"
                    value={newLabel}
                    onChange={(e) => setNewLabel(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-600 mb-1">Base URL</label>
                  <input
                    type="text"
                    required
                    value={newBaseUrl}
                    onChange={(e) => setNewBaseUrl(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg font-mono text-[11px]"
                  />
                </div>
                <div>
                  <label className="block text-slate-600 mb-1">Model Name</label>
                  <input
                    type="text"
                    required
                    value={newModel}
                    onChange={(e) => setNewModel(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg font-mono text-[11px]"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="px-3 py-1.5 text-slate-600 hover:text-slate-800 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg cursor-pointer"
                >
                  Save Provider
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
