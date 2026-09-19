import React, { useState } from 'react';
import { DocumentData } from '../types';
import { LineInspectionPanel } from './LineInspectionPanel';
import { LayoutGrid, ZoomIn } from 'lucide-react';

interface CropViewerProps {
  jobId: string;
  docId: string;
  documentData: DocumentData | null;
}

export const CropViewer: React.FC<CropViewerProps> = ({
  jobId,
  docId,
  documentData,
}) => {
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);

  if (!documentData || !documentData.regions.length) {
    return (
      <div className="p-8 text-center text-sm text-slate-500">
        No crops available for this document.
      </div>
    );
  }

  const selectedRegion = documentData.regions.find(r => r.region_id === selectedRegionId);

  return (
    <div className="flex h-full bg-slate-50 overflow-hidden">
      {/* Crop Grid */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="flex items-center gap-2 mb-4">
          <LayoutGrid className="w-5 h-5 text-blue-600" />
          <h2 className="text-lg font-bold text-slate-800">Extracted Line Crops</h2>
          <span className="text-xs bg-slate-200 text-slate-700 px-2 py-0.5 rounded-full font-mono">
            {documentData.regions.length} items
          </span>
        </div>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {documentData.regions.map((region) => {
            const isSelected = selectedRegionId === region.region_id;
            const cropUrl = `/api/jobs/${jobId}/pages/${docId}/crops/${region.region_id}.png`;
            
            return (
              <div 
                key={region.region_id}
                onClick={() => setSelectedRegionId(isSelected ? null : region.region_id)}
                className={`flex flex-col bg-white rounded-xl border overflow-hidden cursor-pointer transition-all hover:shadow-md ${
                  isSelected ? 'border-blue-500 ring-2 ring-blue-500/20 shadow-md' : 'border-slate-200'
                }`}
              >
                <div className="h-24 bg-slate-100 flex items-center justify-center p-2 relative group">
                  <img 
                    src={cropUrl} 
                    alt={region.region_id} 
                    className="max-h-full max-w-full object-contain"
                    onError={(e) => { e.currentTarget.style.display = 'none'; }}
                  />
                  <div className="absolute inset-0 bg-blue-900/10 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <ZoomIn className="w-6 h-6 text-blue-700" />
                  </div>
                </div>
                <div className="p-2 border-t border-slate-100 bg-white">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-[10px] font-bold bg-slate-100 text-slate-700 px-1.5 rounded font-mono">
                      #{region.sorted_index}
                    </span>
                    <span className={`text-[10px] font-semibold px-1.5 rounded-full ${
                      (region.text_rec_score || 0) > 0.85 ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
                    }`}>
                      {Math.round((region.text_rec_score || 0) * 100)}%
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-900 font-medium truncate" title={region.raw_text}>
                    {region.raw_text}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      
      {/* Side Panel for Details */}
      {selectedRegion && (
        <div className="w-80 shrink-0 border-l border-slate-200 bg-white overflow-y-auto">
          <LineInspectionPanel 
            region={selectedRegion}
            jobId={jobId}
            docId={docId}
            onClose={() => setSelectedRegionId(null)}
          />
        </div>
      )}
    </div>
  );
};
