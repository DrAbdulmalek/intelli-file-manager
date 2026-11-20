"use client";
import { useState } from "react";

type Word = {
  bbox: number[];
  text: string;
  confidence: number;
  word_index: number;
};

type Line = {
  line_index: number;
  bbox: number[];
  text: string;
  words: Word[];
  avg_confidence: number;
  direction: string;
};

type Props = {
  lines: Line[];
  onExport: () => void;
  isExporting: boolean;
  previewStats?: {
    total_approved: number;
    unique_images: number;
    avg_confidence: number;
    with_text: number;
  };
};

export function LineReviewPanel({
  lines, onExport, isExporting, previewStats,
}: Props) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const toggleLine = (idx: number) => {
    const next = new Set(expanded);
    if (next.has(idx)) next.delete(idx);
    else next.add(idx);
    setExpanded(next);
  };

  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-800" dir="rtl">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-lg">مراجعة السطور قبل التصدير</h3>
        <button
          onClick={onExport}
          disabled={isExporting || lines.length === 0}
          className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50
                     disabled:cursor-not-allowed rounded text-white"
        >
          {isExporting ? "جارٍ التصدير..." : "تصدير Dataset"}
        </button>
      </div>

      {previewStats && (
        <div className="grid grid-cols-4 gap-2 mb-4 text-xs">
          <div className="bg-gray-800 p-2 rounded">
            معتمد: <span className="font-mono text-green-400">
              {previewStats.total_approved}
            </span>
          </div>
          <div className="bg-gray-800 p-2 rounded">
            صور: <span className="font-mono">
              {previewStats.unique_images}
            </span>
          </div>
          <div className="bg-gray-800 p-2 rounded">
            متوسطة الثقة: <span className="font-mono text-blue-400">
              {(previewStats.avg_confidence * 100).toFixed(0)}%
            </span>
          </div>
          <div className="bg-gray-800 p-2 rounded">
            بنص: <span className="font-mono">{previewStats.with_text}</span>
          </div>
        </div>
      )}

      <div className="space-y-2 max-h-[500px] overflow-auto">
        {lines.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-4">
            لا سطور بعد — اعتمد بعض القصاصات أولًا
          </p>
        ) : (
          lines.map((line) => (
            <div
              key={line.line_index}
              className="bg-gray-800 rounded p-3 cursor-pointer
                         hover:bg-gray-700/60 transition"
              onClick={() => toggleLine(line.line_index)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">
                    سطر {line.line_index + 1}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    line.direction === "rtl"
                      ? "bg-purple-900/50 text-purple-300"
                      : "bg-blue-900/50 text-blue-300"
                  }`}>
                    {line.direction.toUpperCase()}
                  </span>
                  <span className="text-xs text-gray-500">
                    {line.words.length} كلمة
                  </span>
                  <span className="text-xs text-gray-500">
                    ثقة: {(line.avg_confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <span className="text-xs text-gray-500">
                  {expanded.has(line.line_index) ? "▲" : "▼"}
                </span>
              </div>

              <p className="mt-2 font-arabic text-lg" dir="rtl">
                {line.text || "(فارغ)"}
              </p>

              {expanded.has(line.line_index) && (
                <div className="mt-3 space-y-1 border-t border-gray-700 pt-2">
                  {line.words.map((w, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between
                                 text-xs bg-gray-900 rounded p-1.5"
                    >
                      <span className="font-arabic text-gray-300" dir="rtl">
                        {w.text}
                      </span>
                      <span className="text-gray-600 font-mono">
                        [{w.bbox.join(", ")}] •{" "}
                        {(w.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
