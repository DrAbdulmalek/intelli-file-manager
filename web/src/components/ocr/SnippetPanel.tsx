"use client";

/**
 * SnippetPanel — لوحة القصاصات: الصورة + محرر المربعات + تحرير النص.
 *
 * سير العمل:
 *  1. أدخل مسار صورة وحمّل قصاصاتها من /api/snippets?source_image=...
 *  2. ارسم مربعًا جديدًا حول كلمة، أو اسحب/كبّر المربعات الموجودة
 *  3. صحّح النص في اللوحة اليمنى (مع اقتراحات المسرد الطبي)
 *  4. اعتمد القصاصة للتدريب أو احذفها
 *  5. صدّر المعتمد إلى JSONL (خطوة HuggingFace منفصلة صريحة)
 */

import { useCallback, useEffect, useState } from "react";
import { BBoxEditor, type BBox, type Snippet } from "./BBoxEditor";
import { GlossarySuggest } from "./GlossarySuggest";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8421";

export function SnippetPanel({ initialImageUrl = "" }: { initialImageUrl?: string }) {
  const [imageUrl, setImageUrl] = useState(initialImageUrl);
  const [loadedPath, setLoadedPath] = useState(initialImageUrl);
  const [snippets, setSnippets] = useState<Snippet[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const loadSnippets = useCallback(async (path: string) => {
    if (!path.trim()) return;
    setBusy(true);
    setMessage("");
    try {
      const res = await fetch(
        `${API}/api/snippets?source_image=${encodeURIComponent(path)}`,
        { headers: apiHeaders() },
      );
      const body = await res.json();
      setSnippets(normalizeSnippets(body.items ?? []));
      setSelectedId(null);
    } catch {
      setMessage("فشل تحميل القصاصات — تأكد أن خادم API يعمل على المنفذ 8421");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (loadedPath) void loadSnippets(loadedPath);
  }, [loadedPath, loadSnippets]);

  const active = snippets.find((s) => s.id === selectedId) ?? null;

  const updateActive = useCallback((id: number, bbox: BBox, text: string) => {
    setSnippets((prev) => prev.map((s) => (s.id === id ? { ...s, bbox, text } : s)));
  }, []);

  async function persistSnippet(id: number, bbox: BBox, text: string) {
    try {
      await fetch(`${API}/api/snippets/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...apiHeaders() },
        body: JSON.stringify({
          bbox: { x1: Math.round(bbox.x1), y1: Math.round(bbox.y1), x2: Math.round(bbox.x2), y2: Math.round(bbox.y2) },
          text,
        }),
      });
    } catch {
      setMessage("تعذر الحفظ — سيُفقد التغيير عند إعادة التحميل");
    }
  }

  // persist debounced on drag end: BBoxEditor fires updates continuously; we
  // save on pointer-up via onUpdateCommit below.
  async function handleCreate(bbox: BBox) {
    try {
      const res = await fetch(`${API}/api/snippets`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...apiHeaders() },
        body: JSON.stringify({
          source_image: loadedPath,
          bbox,
          level: "word",
          text: "",
          ocr_text: "",
          confidence: 0,
          language: "ar",
          category: "general",
        }),
      });
      const created = await res.json();
      setSnippets((prev) => [
        ...prev,
        {
          id: created.id,
          bbox: { x1: created.bbox[0], y1: created.bbox[1], x2: created.bbox[2], y2: created.bbox[3] },
          text: created.text ?? "",
          ocrText: created.ocr_text ?? "",
          confidence: created.confidence ?? 0,
          status: created.status ?? "pending",
          level: created.level ?? "word",
          category: created.category ?? "general",
        },
      ]);
      setSelectedId(created.id);
    } catch {
      setMessage("فشل إنشاء القصاصة");
    }
  }

  async function handleDelete(id: number) {
    setSnippets((prev) => prev.filter((s) => s.id !== id));
    try {
      await fetch(`${API}/api/snippets/${id}`, { method: "DELETE", headers: apiHeaders() });
    } catch {
      setMessage("تعذر الحذف على الخادم");
    }
  }

  async function handleApprove(id: number) {
    const s = snippets.find((x) => x.id === id);
    await persistSnippet(id, s?.bbox ?? { x1: 0, y1: 0, x2: 0, y2: 0 }, s?.text ?? "");
    await fetch(`${API}/api/snippets/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...apiHeaders() },
      body: JSON.stringify({ verified_by: "web-editor" }),
    });
    setSnippets((prev) => prev.map((x) => (x.id === id ? { ...x, status: "approved" } : x)));
  }

  async function handleExport() {
    setBusy(true);
    try {
      const res = await fetch(`${API}/api/snippets/export-hf`, {
        method: "POST", headers: apiHeaders(),
      });
      const body = await res.json();
      setMessage(`تم التصدير: ${body.export_path}`);
    } catch {
      setMessage("فشل التصدير");
    } finally {
      setBusy(false);
    }
  }

  const approvedCount = snippets.filter((s) => s.status === "approved").length;

  return (
    <div className="space-y-4" dir="rtl">
      {/* شريط تحميل الصورة */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={imageUrl}
          onChange={(e) => setImageUrl(e.target.value)}
          placeholder="مسار الصورة الأصلية (مثال: /home/user/scan1.png)"
          className="flex-1 min-w-[280px] bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500"
          dir="ltr"
        />
        <button
          onClick={() => setLoadedPath(imageUrl)}
          disabled={busy || !imageUrl.trim()}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-sm rounded-md"
        >
          تحميل القصاصات
        </button>
        <button
          onClick={handleExport}
          disabled={busy || approvedCount === 0}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-sm rounded-md"
        >
          تصدير المعتمد ({approvedCount})
        </button>
      </div>

      {message && (
        <div className="text-xs bg-amber-500/10 border border-amber-500/30 text-amber-200 rounded px-3 py-2" dir="rtl">
          {message}
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-4">
        {/* اليمين بصريًا: الصورة + المربعات */}
        <div className="border border-slate-800 rounded-lg p-3 bg-slate-900/50 overflow-auto">
          {loadedPath ? (
            <BBoxEditor
              imageUrl={imageUrlForCanvas(loadedPath)}
              snippets={snippets}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onSnippetUpdate={updateActive}
              onSnippetCreate={handleCreate}
              onSnippetDelete={handleDelete}
            />
          ) : (
            <p className="text-sm text-slate-500 py-16 text-center">
              أدخل مسار صورة ثم اضغط «تحميل القصاصات» لبدء تحرير المربعات.
            </p>
          )}
        </div>

        {/* اليسار بصريًا: تفاصيل القصاصة */}
        <div className="border border-slate-800 rounded-lg p-4 space-y-3 bg-slate-900/50">
          <h3 className="font-bold text-lg">تحرير القصاصة</h3>
          {active ? (
            <>
              <div className="text-xs text-slate-500 flex flex-wrap gap-x-3">
                <span>ID: {active.id}</span>
                <span>الثقة: {active.confidence === 0 ? "غير معروفة" : `${Math.round(active.confidence * 100)}%`}</span>
                <span>الحالة: {active.status === "approved" ? "معتمدة" : active.status === "rejected" ? "مرفوضة" : "معلقة"}</span>
                <span>المستوى: {active.level}</span>
              </div>

              <label className="block">
                <span className="text-sm font-medium">النص الصحيح:</span>
                <textarea
                  value={active.text}
                  onChange={(e) => updateActive(active.id, active.bbox, e.target.value)}
                  onBlur={() => persistSnippet(active.id, active.bbox, active.text)}
                  className="w-full mt-1 p-2 bg-slate-900 border border-slate-700 rounded font-arabic text-slate-100"
                  dir="rtl"
                  rows={3}
                />
              </label>

              <GlossarySuggest
                text={active.text}
                onPick={(s) => {
                  updateActive(active.id, active.bbox, s);
                  void persistSnippet(active.id, active.bbox, s);
                }}
              />

              <div className="flex gap-2 pt-2">
                <button
                  onClick={() => handleApprove(active.id)}
                  className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded"
                >
                  اعتماد للتدريب
                </button>
                <button
                  onClick={() => handleDelete(active.id)}
                  className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded"
                >
                  حذف
                </button>
              </div>
            </>
          ) : (
            <p className="text-slate-500 text-sm">
              انقر على أي مربع لتحريره، أو ارسم مربعًا جديدًا حول كلمة بسحب الفأرة على الصورة.
            </p>
          )}

          <hr className="border-slate-800" />
          <div className="text-xs text-slate-600">
            القصاصات: {snippets.length} (معتمدة: {approvedCount})
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------
function apiHeaders(): Record<string, string> {
  const key = process.env.NEXT_PUBLIC_API_KEY;
  return key ? { "X-API-Key": key } : {};
}

/** Server bbox arrays [x1,y1,x2,y2] -> editor objects. */
function normalizeSnippets(items: Array<Record<string, unknown>>): Snippet[] {
  return items.map((item) => {
    const bboxRaw = item.bbox as number[] | { x1: number; y1: number; x2: number; y2: number };
    const bbox = Array.isArray(bboxRaw)
      ? { x1: bboxRaw[0], y1: bboxRaw[1], x2: bboxRaw[2], y2: bboxRaw[3] }
      : bboxRaw;
    return {
      id: item.id as number,
      bbox,
      text: (item.text as string) ?? "",
      ocrText: (item.ocr_text as string) ?? "",
      confidence: (item.confidence as number) ?? 0,
      status: (item.status as Snippet["status"]) ?? "pending",
      level: (item.level as string) ?? "word",
      category: (item.category as string) ?? "general",
    };
  });
}

/** Local file paths cannot be loaded by the browser directly; images are
 * served by the sandboxed FastAPI endpoint /api/file/serve. */
function imageUrlForCanvas(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  return `${API}/api/file/serve?filepath=${encodeURIComponent(path)}`;
}
