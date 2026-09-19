import React from 'react';
import { OCRRegion } from '../types';
import { ShieldCheck, X, Activity, Maximize, Crop } from 'lucide-react';

interface LineInspectionPanelProps {
  region: OCRRegion;
  jobId: string;
  docId: string;
  onClose?: () => void;
}

export const LineInspectionPanel: React.FC<LineInspectionPanelProps> = ({
  region,
  jobId,
  docId,
  onClose,
}) => {
  const cropUrl = `/api/jobs/${jobId}/pages/${docId}/crops/${region.region_id}.png`;
  const confidence = Math.round((region.text_rec_score || 0) * 100);

  return (
    <div className="flex flex-col h-full bg-white text-sm">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-slate-200 bg-slate-50">
        <div className="flex items-center gap-2">
          <Crop className="w-4 h-4 text-slate-500" />
          <h3 className="font-semibold text-slate-800">Region Details</h3>
        </div>
        {onClose && (
          <button onClick={onClose} className="p-1 hover:bg-slate-200 rounded text-slate-500 transition-colors">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <div className="p-4 space-y-5 overflow-y-auto">
        
        {/* Identifiers */}
        <div>
          <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Identifiers</div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-slate-50 p-2 rounded border border-slate-100">
              <span className="block text-slate-500 mb-0.5">Region ID</span>
              <span className="font-mono font-medium text-slate-800">{region.region_id}</span>
            </div>
            <div className="bg-slate-50 p-2 rounded border border-slate-100">
              <span className="block text-slate-500 mb-0.5">Sorted Index</span>
              <span className="font-mono font-medium text-slate-800">#{region.sorted_index}</span>
            </div>
          </div>
        </div>

        {/* Confidence & Text */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] uppercase font-bold text-slate-400">Raw Text</span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
              confidence >= 85 ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
            }`}>
              {confidence}% Confidence
            </span>
          </div>
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-slate-900 font-medium">
            {region.raw_text}
          </div>
        </div>

        {/* Crop Preview */}
        <div>
          <div className="text-[10px] uppercase font-bold text-slate-400 mb-1.5">Image Crop</div>
          <div className="bg-slate-900 rounded-lg p-2 flex items-center justify-center overflow-hidden border border-slate-800 relative group">
            <img 
              src={cropUrl} 
              alt="Crop" 
              className="max-w-full max-h-32 object-contain"
            />
            <div className="absolute top-2 right-2 bg-black/50 p-1 rounded text-white opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              <Maximize className="w-3 h-3" />
            </div>
          </div>
        </div>

        {/* Geometry */}
        <div>
          <div className="text-[10px] uppercase font-bold text-slate-400 mb-1.5">Geometry</div>
          <div className="bg-slate-50 rounded border border-slate-100 p-2">
            <div className="text-xs text-slate-500 mb-1 flex justify-between">
              <span>Polygon Points:</span>
              <span className="font-mono text-slate-700">{region.raw_polygon.length}</span>
            </div>
            <div className="max-h-24 overflow-y-auto text-[10px] font-mono text-slate-600 bg-white p-2 rounded border border-slate-100">
              {region.raw_polygon.map((p, i) => (
                <div key={i}>[{p[0]}, {p[1]}]</div>
              ))}
            </div>
          </div>
        </div>

        {/* Integrity */}
        <div>
          <div className="text-[10px] uppercase font-bold text-slate-400 mb-1.5">Integrity</div>
          <div className="bg-emerald-50 text-emerald-800 border border-emerald-200 p-2.5 rounded-lg flex items-start gap-2 text-xs">
            <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold block mb-0.5">Immutable Invariant</span>
              <span className="text-emerald-700/80">Text remains uncorrected. OCR correction is skipped to preserve raw evaluation validity.</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
