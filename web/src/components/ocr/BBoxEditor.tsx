"use client";

/**
 * BBoxEditor — محرر المربعات حول الكلمات (canvas-based).
 *
 * القدرات:
 *  - رسم مربع جديد حول أي كلمة (سحب بالفأرة)
 *  - سحب المربعات الموجودة وتغيير حجمها من 8 مقابض
 *  - النقر على مربع لتحديده وتحرير نصه
 *  - حذف المربع المحدد
 *  - تلوين الثقة (heatmap): أخضر >=90%، أصفر >=70%، أحمر <70%،
 *    رمادي = ثقة غير معروفة (0.0 — سياسة ocr-core: لا تُختلق أبدًا)
 *
 * الإحداثيات دائمًا بزوايا الصورة (x1, y1, x2, y2) بالبكسل الأصلي،
 * ومستقلة عن التكبير/التصغير المعروض.
 */

import { useCallback, useEffect, useRef, useState } from "react";

export type BBox = { x1: number; y1: number; x2: number; y2: number };

export type Snippet = {
  id: number;
  bbox: BBox;
  text: string;
  ocrText: string;
  confidence: number;
  status: "pending" | "approved" | "rejected";
  level: string;
  category: string;
};

type DragState = {
  id: number | null;
  mode: "move" | "resize" | "create" | null;
  handle: number; // 0..7 for resize handles
  startX: number;
  startY: number;
  origBbox: BBox;
};

const HANDLE = 6;
const MIN_SIZE = 8;

function confidenceFill(conf: number, selected: boolean): string {
  // 0.0 = unknown -> neutral gray (never invent confidence)
  if (selected) return "rgba(59, 130, 246, 0.35)"; // blue
  if (conf === 0) return "rgba(148, 163, 184, 0.30)";
  if (conf >= 0.9) return "rgba(34, 197, 94, 0.30)"; // green
  if (conf >= 0.7) return "rgba(234, 179, 8, 0.30)"; // yellow
  return "rgba(239, 68, 68, 0.35)"; // red
}

function confidenceStroke(conf: number, selected: boolean): string {
  if (selected) return "#3b82f6";
  if (conf === 0) return "#94a3b8";
  if (conf >= 0.9) return "#22c55e";
  if (conf >= 0.7) return "#eab308";
  return "#ef4444";
}

export function BBoxEditor({
  imageUrl,
  snippets,
  selectedId,
  onSelect,
  onSnippetUpdate,
  onSnippetCreate,
  onSnippetDelete,
}: {
  imageUrl: string;
  snippets: Snippet[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  onSnippetUpdate: (id: number, bbox: BBox, text: string) => void;
  onSnippetCreate: (bbox: BBox) => void;
  onSnippetDelete: (id: number) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const dragRef = useRef<DragState>({
    id: null, mode: null, handle: -1, startX: 0, startY: 0,
    origBbox: { x1: 0, y1: 0, x2: 0, y2: 0 },
  });
  const [dragging, setDragging] = useState(false);

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    for (const s of snippets) {
      const { x1, y1, x2, y2 } = s.bbox;
      const selected = s.id === selectedId;
      ctx.fillStyle = confidenceFill(s.confidence, selected);
      ctx.strokeStyle = confidenceStroke(s.confidence, selected);
      ctx.lineWidth = selected ? 2.5 : 1.5;
      ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

      if (selected) {
        // 8 resize handles: 4 corners + 4 edge midpoints
        const hx = [x1, (x1 + x2) / 2, x2, x2, x2, (x1 + x2) / 2, x1, x1];
        const hy = [y1, y1, y1, (y1 + y2) / 2, y2, y2, y2, (y1 + y2) / 2];
        ctx.fillStyle = "#3b82f6";
        for (let i = 0; i < 8; i++) {
          ctx.fillRect(hx[i] - HANDLE, hy[i] - HANDLE, HANDLE * 2, HANDLE * 2);
        }
      }
    }
  }, [snippets, selectedId]);

  useEffect(() => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      imgRef.current = img;
      const canvas = canvasRef.current;
      if (canvas) {
        canvas.width = img.width;
        canvas.height = img.height;
        redraw();
      }
    };
    img.src = imageUrl;
  }, [imageUrl, redraw]);

  useEffect(() => {
    redraw();
  }, [redraw]);

  function getMousePos(e: React.MouseEvent): [number, number] {
    const canvas = canvasRef.current;
    if (!canvas) return [0, 0];
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return [
      (e.clientX - rect.left) * scaleX,
      (e.clientY - rect.top) * scaleY,
    ];
  }

  function hitHandle(x: number, y: number, bbox: BBox): number {
    const { x1, y1, x2, y2 } = bbox;
    const hx = [x1, (x1 + x2) / 2, x2, x2, x2, (x1 + x2) / 2, x1, x1];
    const hy = [y1, y1, y1, (y1 + y2) / 2, y2, y2, y2, (y1 + y2) / 2];
    for (let i = 0; i < 8; i++) {
      if (Math.abs(x - hx[i]) <= HANDLE && Math.abs(y - hy[i]) <= HANDLE) return i;
    }
    return -1;
  }

  function hitTest(x: number, y: number): { id: number; mode: "move" | "resize"; handle: number } | null {
    for (const s of [...snippets].reverse()) {
      const handle = s.id === selectedId ? hitHandle(x, y, s.bbox) : -1;
      if (handle >= 0) return { id: s.id, mode: "resize", handle };
      const { x1, y1, x2, y2 } = s.bbox;
      if (x >= x1 && x <= x2 && y >= y1 && y <= y2) {
        return { id: s.id, mode: "move", handle: -1 };
      }
    }
    return null;
  }

  function onPointerDown(e: React.MouseEvent) {
    const [x, y] = getMousePos(e);
    const hit = hitTest(x, y);
    if (hit) {
      onSelect(hit.id);
      const s = snippets.find((s) => s.id === hit.id);
      if (!s) return;
      dragRef.current = {
        id: hit.id, mode: hit.mode, handle: hit.handle,
        startX: x, startY: y, origBbox: { ...s.bbox },
      };
      setDragging(true);
    } else {
      onSelect(null);
      dragRef.current = {
        id: null, mode: "create", handle: -1,
        startX: x, startY: y, origBbox: { x1: x, y1: y, x2: x, y2: y },
      };
      setDragging(true);
    }
  }

  function onPointerMove(e: React.MouseEvent) {
    const drag = dragRef.current;
    if (!dragging || !drag.mode) return;
    const [x, y] = getMousePos(e);
    const dx = x - drag.startX;
    const dy = y - drag.startY;
    const o = drag.origBbox;

    if (drag.mode === "move" && drag.id !== null) {
      onSnippetUpdate(drag.id, {
        x1: o.x1 + dx, y1: o.y1 + dy, x2: o.x2 + dx, y2: o.y2 + dy,
      }, snippets.find((s) => s.id === drag.id)?.text ?? "");
    } else if (drag.mode === "resize" && drag.id !== null) {
      // apply only the dragged edge(s)
      let { x1, y1, x2, y2 } = o;
      if (drag.handle === 0 || drag.handle === 6 || drag.handle === 7) x1 = Math.min(x, x2 - MIN_SIZE);
      if (drag.handle === 2 || drag.handle === 3 || drag.handle === 4) x2 = Math.max(x, x1 + MIN_SIZE);
      if (drag.handle === 0 || drag.handle === 1 || drag.handle === 2) y1 = Math.min(y, y2 - MIN_SIZE);
      if (drag.handle === 4 || drag.handle === 5 || drag.handle === 6) y2 = Math.max(y, y1 + MIN_SIZE);
      onSnippetUpdate(drag.id, { x1, y1, x2, y2 },
        snippets.find((s) => s.id === drag.id)?.text ?? "");
    } else if (drag.mode === "create") {
      // live dashed preview while creating
      const canvas = canvasRef.current;
      if (!canvas) return;
      redraw();
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const bx = Math.min(drag.startX, x);
      const by = Math.min(drag.startY, y);
      ctx.strokeStyle = "#22c55e";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 4]);
      ctx.strokeRect(bx, by, Math.abs(x - drag.startX), Math.abs(y - drag.startY));
      ctx.setLineDash([]);
    }
  }

  function onPointerUp(e: React.MouseEvent) {
    const drag = dragRef.current;
    if (drag.mode === "create") {
      const [x, y] = getMousePos(e);
      const bbox = {
        x1: Math.round(Math.min(drag.startX, x)),
        y1: Math.round(Math.min(drag.startY, y)),
        x2: Math.round(Math.max(drag.startX, x)),
        y2: Math.round(Math.max(drag.startY, y)),
      };
      if (bbox.x2 - bbox.x1 > MIN_SIZE && bbox.y2 - bbox.y1 > MIN_SIZE) {
        onSnippetCreate(bbox);
      } else {
        redraw();
      }
    }
    dragRef.current = { id: null, mode: null, handle: -1, startX: 0, startY: 0,
      origBbox: { x1: 0, y1: 0, x2: 0, y2: 0 } };
    setDragging(false);
  }

  return (
    <div className="relative inline-block max-w-full">
      <canvas
        ref={canvasRef}
        onMouseDown={onPointerDown}
        onMouseMove={onPointerMove}
        onMouseUp={onPointerUp}
        onMouseLeave={onPointerUp}
        className="cursor-crosshair border border-slate-700 rounded-lg max-w-full h-auto select-none"
        data-testid="bbox-canvas"
      />
      {selectedId !== null && (
        <button
          onClick={() => {
            onSnippetDelete(selectedId);
            onSelect(null);
          }}
          className="absolute top-2 left-2 bg-red-600 hover:bg-red-500 text-white text-xs px-3 py-1.5 rounded shadow"
        >
          حذف المربع المحدد
        </button>
      )}
      <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-400">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm" style={{ background: "#22c55e" }} /> ثقة 90%+</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm" style={{ background: "#eab308" }} /> 70-90%</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm" style={{ background: "#ef4444" }} /> أقل من 70%</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm" style={{ background: "#94a3b8" }} /> غير معروفة</span>
      </div>
    </div>
  );
}
