import React, { useState } from 'react';
import { Layers, CheckCircle2, Clock, AlertTriangle, FileText, ChevronRight } from 'lucide-react';
import { JobStatusResponse, PageStatusModel } from '../types';

interface JobListProps {
  jobs: { job_id: string; status: string; total_pages: number; created_at: string; sample_preview: string }[];
  selectedJobId: string | null;
  onSelectJob: (jobId: string) => void;
  selectedJob: JobStatusResponse | null;
  selectedDocId: string | null;
  onSelectDoc: (docId: string) => void;
  onNewJobClick: () => void;
}

export const JobList: React.FC<JobListProps> = ({
  jobs,
  selectedJobId,
  onSelectJob,
  selectedJob,
  selectedDocId,
  onSelectDoc,
  onNewJobClick,
}) => {
  const [filterQuery, setFilterQuery] = useState('');

  const filteredJobs = jobs.filter((j) =>
    j.job_id.toLowerCase().includes(filterQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col h-full bg-white border-r border-slate-200">
      {/* Header */}
      <div className="p-3.5 border-b border-slate-200">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-blue-600" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
              Runs & Documents
            </span>
          </div>
          <span className="text-[11px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
            {jobs.length} Runs
          </span>
        </div>
        <input
          type="text"
          placeholder="Filter runs..."
          value={filterQuery}
          onChange={(e) => setFilterQuery(e.target.value)}
          className="w-full text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 text-slate-700"
        />
      </div>

      {/* Runs scrollable list */}
      <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
        {filteredJobs.length === 0 ? (
          <div className="p-6 text-center text-xs text-slate-400">
            No runs found. Launch a new pipeline run.
          </div>
        ) : (
          filteredJobs.map((job) => {
            const isSelected = job.job_id === selectedJobId;
            const formattedDate = new Date(job.created_at).toLocaleDateString(undefined, {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            });

            return (
              <div key={job.job_id} className="transition-colors">
                <button
                  onClick={() => onSelectJob(job.job_id)}
                  className={`w-full text-left p-3 flex items-start justify-between gap-2 hover:bg-slate-50 transition-colors cursor-pointer ${
                    isSelected ? 'bg-blue-50/70 border-l-2 border-blue-600' : ''
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 mb-1">
                      {job.status === 'completed' ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                      ) : job.status === 'processing' ? (
                        <Clock className="w-3.5 h-3.5 text-blue-500 shrink-0 animate-spin" />
                      ) : (
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                      )}
                      <span className="text-xs font-semibold text-slate-800 truncate font-mono">
                        {job.job_id.replace('run-', '')}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-slate-500">
                      <span>{formattedDate}</span>
                      <span>•</span>
                      <span>{job.total_pages} {job.total_pages === 1 ? 'doc' : 'docs'}</span>
                    </div>
                  </div>
                  <ChevronRight className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isSelected ? 'rotate-90 text-blue-600' : ''}`} />
                </button>

                {/* Expanded pages list when this job is selected */}
                {isSelected && selectedJob && (
                  <div className="bg-slate-50/80 px-2 py-1.5 border-t border-slate-100 divide-y divide-slate-100/60 max-h-56 overflow-y-auto">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-2 py-1">
                      Pages in this run ({selectedJob.pages.length})
                    </div>
                    {selectedJob.pages.map((p) => {
                      const isDocSelected = p.document_id === selectedDocId;
                      return (
                        <button
                          key={p.document_id}
                          onClick={() => onSelectDoc(p.document_id)}
                          className={`w-full text-left px-2.5 py-1.5 rounded-md flex items-center justify-between text-xs transition-colors cursor-pointer my-0.5 ${
                            isDocSelected
                              ? 'bg-blue-600 text-white font-medium shadow-xs'
                              : 'text-slate-700 hover:bg-slate-200/60'
                          }`}
                        >
                          <div className="flex items-center gap-2 truncate">
                            <FileText className={`w-3.5 h-3.5 shrink-0 ${isDocSelected ? 'text-white' : 'text-slate-400'}`} />
                            <span className="truncate font-mono text-[11px]">
                              {p.document_id}
                            </span>
                          </div>
                          <span
                            className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${
                              isDocSelected
                                ? 'bg-blue-700 text-white'
                                : p.status === 'notes_ready'
                                ? 'bg-emerald-100 text-emerald-700'
                                : 'bg-blue-100 text-blue-700'
                            }`}
                          >
                            {p.status === 'notes_ready' ? 'Ready' : p.status}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Bottom CTA */}
      <div className="p-3 border-t border-slate-200 bg-slate-50">
        <button
          onClick={onNewJobClick}
          className="w-full py-2 px-3 text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-lg transition-colors cursor-pointer text-center"
        >
          + Ingest Sample or Image
        </button>
      </div>
    </div>
  );
};
