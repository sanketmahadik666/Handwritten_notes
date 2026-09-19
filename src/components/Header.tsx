import React from 'react';
import {
  FileText,
  Radio,
  BarChart3,
  Activity,
  Folder,
  RefreshCw,
  Sparkles,
  ShieldCheck,
} from 'lucide-react';
import { HealthResponse } from '../types';

interface HeaderProps {
  currentView: 'workspace' | 'benchmark' | 'health' | 'artifacts';
  onSelectView: (view: 'workspace' | 'benchmark' | 'health' | 'artifacts') => void;
  health: HealthResponse | null;
  onRefreshHealth: () => void;
  onOpenProviders: () => void;
  onNewJob: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentView,
  onSelectView,
  health,
  onRefreshHealth,
  onOpenProviders,
  onNewJob,
}) => {
  const isHealthy = health?.status === 'healthy';

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Logo & Title */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-sm">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-slate-900 leading-tight">
                Handwritten Notes OCR
              </h1>
              <span className="text-[11px] font-semibold bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full border border-blue-200">
                Phase 7 Service
              </span>
            </div>
            <p className="text-xs text-slate-500 truncate max-w-xs sm:max-w-sm">
              IAM Handwritten English Dataset • B.Tech Research & Benchmark System
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-semibold">
          <button
            onClick={() => onSelectView('workspace')}
            className={`px-3 py-1.5 rounded-lg transition-colors cursor-pointer flex items-center gap-1.5 ${
              currentView === 'workspace'
                ? 'bg-white text-blue-700 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Radio className="w-3.5 h-3.5" />
            <span>Workspace</span>
          </button>

          <button
            onClick={() => onSelectView('benchmark')}
            className={`px-3 py-1.5 rounded-lg transition-colors cursor-pointer flex items-center gap-1.5 ${
              currentView === 'benchmark'
                ? 'bg-white text-blue-700 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Benchmark</span>
          </button>

          <button
            onClick={() => onSelectView('health')}
            className={`px-3 py-1.5 rounded-lg transition-colors cursor-pointer flex items-center gap-1.5 ${
              currentView === 'health'
                ? 'bg-white text-blue-700 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Health & Doctor</span>
          </button>

          <button
            onClick={() => onSelectView('artifacts')}
            className={`px-3 py-1.5 rounded-lg transition-colors cursor-pointer flex items-center gap-1.5 ${
              currentView === 'artifacts'
                ? 'bg-white text-blue-700 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Folder className="w-3.5 h-3.5" />
            <span>Artifacts</span>
          </button>
        </nav>

        {/* Action Controls */}
        <div className="flex items-center gap-2.5">
          {/* Provider button */}
          <button
            onClick={onOpenProviders}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg transition-colors cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            <span className="hidden sm:inline">AI Providers</span>
          </button>

          {/* New Job CTA */}
          <button
            onClick={onNewJob}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-xs transition-colors cursor-pointer"
          >
            <Radio className="w-3.5 h-3.5" />
            <span>Run Pipeline Job</span>
          </button>
        </div>
      </div>
    </header>
  );
};
