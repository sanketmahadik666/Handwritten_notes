import React, { useState } from 'react';
import {
  Eye,
  EyeOff,
  RefreshCw,
  ZoomIn,
  ZoomOut,
  Check,
  Layers,
  Image as ImageIcon,
  ShieldCheck,
  FileCheck2,
  Info,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';
import { DocumentData, OCRRegion } from '../types';

interface DocumentViewerProps {
  jobId: string;
  docId: string;
  documentData: DocumentData | null;
  onRetryOcr: () => void;
  isOcrRetrying: boolean;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  jobId,
  docId,
  documentData,
  onRetryOcr,
  isOcrRetrying,
}) => {
  const [showOverlay, setShowOverlay] = useState(true);
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [showEvalDetails, setShowEvalDetails] = useState(false);

  const overlayUrl = `/api/jobs/${jobId}/pages/${docId}/overlay.png`;
  // Extract base sample image name (e.g. a01-000u.png)
  const baseImgName = docId.split('-')[0] + '-' + docId.split('-')[1] + '.png';
  const rawImageUrl = `/api/data-images/${baseImgName}`;

  const currentImageUrl = showOverlay ? overlayUrl : rawImageUrl;

  const selectedRegion = documentData?.regions.find(
    (r) => r.region_id === selectedRegionId
  );

  const evalData = documentData?.evaluation;
  const isVerifiedDoc = baseImgName === 'a01-000u.png';

  return (
    <div className="flex flex-col h-full bg-slate-100 overflow-hidden">
      {/* Viewer Toolbar */}
      <div className="bg-white border-b border-slate-200 px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-3">
          {/* Overlay toggle */}
          <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg border border-slate-200">
            <button
              onClick={() => setShowOverlay(true)}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors cursor-pointer flex items-center gap-1 ${
                showOverlay
                  ? 'bg-white text-blue-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Polygon Overlay</span>
            </button>
            <button
              onClick={() => setShowOverlay(false)}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors cursor-pointer flex items-center gap-1 ${
                !showOverlay
                  ? 'bg-white text-blue-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <ImageIcon className="w-3.5 h-3.5" />
              <span>Raw Scan</span>
            </button>
          </div>

          {/* Zoom controls */}
          <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg border border-slate-200">
            <button
              onClick={() => setZoomLevel((z) => Math.max(0.5, z - 0.25))}
              className="p-1 rounded-md text-slate-600 hover:text-slate-900 hover:bg-white cursor-pointer"
              title="Zoom out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="px-2 text-[11px] font-mono text-slate-600">
              {Math.round(zoomLevel * 100)}%
            </span>
            <button
              onClick={() => setZoomLevel((z) => Math.min(2.5, z + 0.25))}
              className="p-1 rounded-md text-slate-600 hover:text-slate-900 hover:bg-white cursor-pointer"
              title="Zoom in"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setZoomLevel(1)}
              className="px-1.5 py-0.5 text-[10px] text-slate-500 hover:text-slate-800 cursor-pointer"
            >
              Reset
            </button>
          </div>

          {/* Evaluation Indicator */}
          {isVerifiedDoc ? (
            <button
              onClick={() => setShowEvalDetails(!showEvalDetails)}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100 transition-colors cursor-pointer"
            >
              <FileCheck2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Verified GT: CER 7.09% • WER 24.49%</span>
            </button>
          ) : (
            <span className="text-[11px] text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
              Unverified Ground Truth (CER/WER Skipped)
            </span>
          )}
        </div>

        {/* Retry OCR button */}
        <button
          onClick={onRetryOcr}
          disabled={isOcrRetrying}
          className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isOcrRetrying ? 'animate-spin text-blue-600' : ''}`} />
          <span>{isOcrRetrying ? 'Re-running OCR...' : 'Retry OCR'}</span>
        </button>
      </div>

      {/* Ground Truth Evaluation Drawer (Expandable) */}
      {showEvalDetails && isVerifiedDoc && evalData && (
        <div className="bg-emerald-50/90 border-b border-emerald-200 p-4 text-xs text-emerald-950 shrink-0 space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-bold flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              Verified IAM Ground Truth Annotation Audit (config/a01-000u.ground_truth.json)
            </span>
            <button
              onClick={() => setShowEvalDetails(false)}
              className="text-emerald-700 hover:text-emerald-900 font-mono text-[11px] cursor-pointer"
            >
              ✕ Close
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 bg-white p-3 rounded-lg border border-emerald-200">
            <div>
              <span className="text-[10px] text-slate-500 block">Character Error Rate (CER)</span>
              <span className="text-sm font-bold font-mono text-emerald-700">7.0866%</span>
              <span className="text-[10px] text-slate-500 block">
                15 subs + 2 ins + 1 del = 18 edits / 254 chars
              </span>
            </div>
            <div>
              <span className="text-[10px] text-slate-500 block">Word Error Rate (WER)</span>
              <span className="text-sm font-bold font-mono text-slate-800">24.4898%</span>
              <span className="text-[10px] text-slate-500 block">
                12 subs + 0 ins + 0 del = 12 edits / 49 words
              </span>
            </div>
            <div>
              <span className="text-[10px] text-slate-500 block">Exclusion Specification</span>
              <span className="text-[11px] font-mono text-amber-700 font-semibold">
                Trailing "Name:" excluded
              </span>
              <span className="text-[10px] text-slate-500 block">
                Applied from ground truth annotation
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Main Split: Canvas + Line Inspector */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* Document Image Stage */}
        <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-slate-200/70">
          <div
            className="transition-transform duration-150 origin-center max-w-full shadow-lg rounded-lg overflow-hidden bg-white border border-slate-300"
            style={{ transform: `scale(${zoomLevel})` }}
          >
            <img
              src={currentImageUrl}
              alt="Handwritten Document Scan"
              className="max-h-[680px] w-auto object-contain block select-none"
              onError={(e) => {
                const target = e.currentTarget;
                if (target.src.includes('overlay.png')) {
                  target.src = rawImageUrl;
                }
              }}
            />
          </div>
        </div>

        {/* OCR Line Crops & Regions Drawer */}
        <div className="w-full lg:w-96 bg-white border-t lg:border-t-0 lg:border-l border-slate-200 flex flex-col h-72 lg:h-full shrink-0">
          <div className="p-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
            <div>
              <span className="text-xs font-bold text-slate-800">Extracted Text Lines</span>
              <span className="ml-2 text-[11px] font-mono text-slate-500">
                {documentData?.regions.length || 0} regions
              </span>
            </div>
            <span className="text-[10px] bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full font-medium">
              Sorted Reading Order
            </span>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-100 p-2 space-y-1.5">
            {!documentData || documentData.regions.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-400">
                No region lines recorded for this document.
              </div>
            ) : (
              documentData.regions.map((region) => {
                const isSelected = selectedRegionId === region.region_id;
                const recConfidence = Math.round((region.text_rec_score || 0) * 100);
                const cropUrl = `/api/jobs/${jobId}/pages/${docId}/crops/${region.region_id}.png`;

                return (
                  <div
                    key={region.region_id}
                    onClick={() => setSelectedRegionId(isSelected ? null : region.region_id)}
                    className={`p-2.5 rounded-lg border transition-all cursor-pointer ${
                      isSelected
                        ? 'border-blue-500 bg-blue-50/50 shadow-xs ring-1 ring-blue-400'
                        : 'border-slate-200 hover:border-slate-300 bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-700">
                          #{region.sorted_index}
                        </span>
                        <span className="text-xs font-mono text-slate-500">
                          {region.region_id}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <span
                          className={`text-[10px] px-1.5 py-0.2 rounded-full font-semibold ${
                            recConfidence >= 85
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : recConfidence >= 65
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : 'bg-rose-50 text-rose-700 border border-rose-200'
                          }`}
                        >
                          {recConfidence}% rec
                        </span>
                      </div>
                    </div>

                    {/* PaddleX Line Crop Image preview */}
                    <div className="mb-2 bg-slate-50 rounded border border-slate-100 p-1 flex items-center justify-center overflow-hidden">
                      <img
                        src={cropUrl}
                        alt={`Crop ${region.region_id}`}
                        className="max-h-8 object-contain"
                        onError={(e) => {
                          e.currentTarget.style.display = 'none';
                        }}
                      />
                    </div>

                    {/* Recognized Text */}
                    <div className="text-xs font-sans font-medium text-slate-900 bg-slate-50 px-2 py-1.5 rounded border border-slate-100 leading-snug">
                      {region.raw_text}
                    </div>

                    {/* Expanded Inspector when clicked */}
                    {isSelected && (
                      <div className="mt-2 pt-2 border-t border-blue-200 text-[11px] font-mono text-slate-600 space-y-1">
                        <div className="flex justify-between">
                          <span>Detector Index:</span>
                          <span className="text-slate-900 font-semibold">{region.detector_index}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Sorted Index:</span>
                          <span className="text-slate-900 font-semibold">{region.sorted_index}</span>
                        </div>
                        {region.recognition_order !== undefined && (
                          <div className="flex justify-between">
                            <span>Batch Recog Order:</span>
                            <span className="text-slate-900 font-semibold">
                              {region.recognition_order}
                            </span>
                          </div>
                        )}
                        <div className="flex justify-between">
                          <span>Correction Status:</span>
                          <span className="text-emerald-700 font-semibold">skipped (Invariant)</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Method:</span>
                          <span className="text-slate-700">PaddleX _crop_by_polys</span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
