"use client";

/**
 * SnippetPanel — لوحة القصاصات: الصورة + محرر المربعات + تحرير النص.
 *
 * سير العمل:
 *  1. أدخل مسار صورة وحمّل قصاصاتها من /api/snippets?source_image=...
 *  2. ارسم مربعًا جديدًا حول كلمة، أو اسحب/كبّر المربعات الموجودة
 *  3. قسّم مربعًا يضم أكثر من كلمة (S) أو ادمج مربعين متجاورين (M)
 *     حتى تحصل على كلمة واحدة كاملة وصحيحة — مع تراجع/إعادة (Ctrl+Z / Ctrl+Y)
 *  4. صحّح النص في اللوحة اليمنى (مع اقتراحات المسرد الطبي)
 *  5. اعتمد القصاصة للتدريب أو احذفها
 *  6. راجع السطور المجمعة RTL قبل التصدير، ثم صدّر المعتمد إلى JSONL
 *     (خطوة HuggingFace منفصلة صريحة)
 *
 * مزامنة الخادم: التقسيم/الدمج عمليتان خادميتان فوقيتان (PATCH/POST/DELETE
 * عبر العقد الموجود) — التراجع المحلي يعيد العرض فقط؛ عكسهما الطبيعي هو
 * دمجهما معًا أو إعادة تقسيمهما.
 */

import { useCallback, useEffect, useState } from "react";
import { BBoxEditor, type BBox, type Snippet } from "./BBoxEditor";
import { GlossarySuggest } from "./GlossarySuggest";
import { LineReviewPanel } from "./LineReviewPanel";
import { useSnippetHistory } from "@/hooks/useSnippetHistory";
import { splitBBox, mergeBBox } from "@/lib/snippet-ops";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8421";

export function SnippetPanel({ initialImageUrl = "" }: { initialImageUrl?: string }) {
  const [imageUrl, setImageUrl] = useState(initialImageUrl);
  const [loadedPath, setLoadedPath] = useState(initialImageUrl);
  const {
    snippets, setAll, mutate, undo, redo, canUndo, canRedo,
  } = useSnippetHistory<Snippet>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [reviewLines, setReviewLines] = useState<ReviewLine[] | null>(null);

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
      setAll(normalizeSnippets(body.items ?? []));
      setSelectedId(null);
      setReviewLines(null);
    } catch {
      setMessage("فشل تحميل القصاصات — تأكد أن خادم API يعمل على المنفذ 8421");
    } finally {
      setBusy(false);
    }
  }, [setAll]);

  useEffect(() => {
    if (loadedPath) void loadSnippets(loadedPath);
  }, [loadedPath, loadSnippets]);

  const active = snippets.find((s) => s.id === selectedId) ?? null;

  const updateActive = useCallback((id: number, bbox: BBox, text: string) => {
    mutate((prev) => prev.map((s) => (s.id === id ? { ...s, bbox, text } : s)));
  }, [mutate]);

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
      mutate((prev) => [
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
    mutate((prev) => prev.filter((s) => s.id !== id));
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
    mutate((prev) => prev.map((x) => (x.id === id ? { ...x, status: "approved" as const } : x)));
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

  // ------------------------------------------------------------------
  // تقسيم / دمج — كلمة كلمة بشكل كامل وصحيح (مزامنة خادمية فورية)
  // ------------------------------------------------------------------

  /** تقسيم القصاصة المحددة عند نقطة X (افتراضيًا المنتصف). */
  async function splitSelected(atX?: number) {
    if (!active) return;
    const splitX = Math.round(atX ?? (active.bbox.x1 + active.bbox.x2) / 2);
    const [leftB, rightB] = splitBBox(active.bbox, splitX);
    if (leftB.x2 - leftB.x1 < 4 || rightB.x2 - rightB.x1 < 4) {
      setMessage("المربع أضيق من أن يُقسَّم (الحد 4 بكسل لكل نصف)");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      // 1) الأصل يصير النصف الأيسر (نصه يُمسح — النصف لم يعد الكلمة كاملة)
      await persistSnippet(active.id, leftB, "");
      // 2) النصف الأيمن قصاصة جديدة على الخادم
      const res = await fetch(`${API}/api/snippets`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...apiHeaders() },
        body: JSON.stringify({
          source_image: loadedPath,
          bbox: rightB,
          level: active.level ?? "word",
          text: "",
          ocr_text: active.ocrText ?? "",
          confidence: 0, // مقسومة يدويًا — ثقة المحرك لم تعد صالحة (لا تُختلق)
          language: "ar",
          category: active.category ?? "general",
        }),
      });
      const created = await res.json();
      mutate((prev) => [
        ...prev.map((s) =>
          s.id === active.id
            ? { ...s, bbox: leftB, text: "", status: "pending" as const }
            : s,
        ),
        {
          id: created.id,
          bbox: { x1: created.bbox[0], y1: created.bbox[1], x2: created.bbox[2], y2: created.bbox[3] },
          text: "",
          ocrText: created.ocr_text ?? "",
          confidence: 0,
          status: (created.status ?? "pending") as Snippet["status"],
          level: created.level ?? "word",
          category: created.category ?? "general",
        },
      ]);
      setSelectedId(created.id);
      setMessage("قُسّمت القصاصة — حرّر نص كل نصف (في RTL ابدأ بالأيمن)");
    } catch {
      setMessage("فشل التقسيم على الخادم");
    } finally {
      setBusy(false);
    }
  }

  /** أقرب جار في نفس السطر (تداخل رأسي ≥50%) — للدمج. */
  function findMergeNeighbor(target: Snippet): Snippet | null {
    let best: Snippet | null = null;
    let bestGap = Infinity;
    for (const s of snippets) {
      if (s.id === target.id) continue;
      const overlap =
        Math.min(target.bbox.y2, s.bbox.y2) - Math.max(target.bbox.y1, s.bbox.y1);
      const minH = Math.min(target.bbox.y2 - target.bbox.y1, s.bbox.y2 - s.bbox.y1);
      if (minH <= 0 || overlap / minH < 0.5) continue;
      const gap =
        s.bbox.x1 > target.bbox.x2
          ? s.bbox.x1 - target.bbox.x2
          : target.bbox.x1 > s.bbox.x2
            ? target.bbox.x1 - s.bbox.x2
            : 0;
      if (gap < bestGap) {
        bestGap = gap;
        best = s;
      }
    }
    return best;
  }

  /** دمج القصاصة المحددة مع أقرب جار في نفس السطر. */
  async function mergeWithNeighbor() {
    if (!active) return;
    const neighbor = findMergeNeighbor(active);
    if (!neighbor) {
      setMessage("لا توجد قصاصة مجاورة في نفس السطر للدمج");
      return;
    }
    const mergedB = mergeBBox([active.bbox, neighbor.bbox]);
    // ترتيب قرائي RTL: الأيمن (x2 الأكبر) أولًا
    const [first, second] =
      active.bbox.x2 >= neighbor.bbox.x2 ? [active, neighbor] : [neighbor, active];
    const mergedText = [first.text.trim(), second.text.trim()]
      .filter(Boolean)
      .join(" ");
    setBusy(true);
    setMessage("");
    try {
      await persistSnippet(active.id, mergedB, mergedText);
      await fetch(`${API}/api/snippets/${neighbor.id}`, {
        method: "DELETE", headers: apiHeaders(),
      });
      mutate((prev) =>
        prev
          .filter((s) => s.id !== neighbor.id)
          .map((s) =>
            s.id === active.id
              ? { ...s, bbox: mergedB, text: mergedText, status: "pending" as const }
              : s,
          ),
      );
      setSelectedId(active.id);
      setMessage(`دُمجت القصاصتان (${active.id} + ${neighbor.id}) — راجع النص المدمج`);
    } catch {
      setMessage("فشل الدمج على الخادم");
    } finally {
      setBusy(false);
    }
  }

  // اختصارات لوحة المفاتيح — e.code مستقل عن تخطيط اللوحة (عربي/إنجليزي)
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "TEXTAREA" || t.tagName === "INPUT")) return;
      if ((e.ctrlKey || e.metaKey) && e.code === "KeyZ" && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if (
        ((e.ctrlKey || e.metaKey) && e.code === "KeyZ" && e.shiftKey) ||
        ((e.ctrlKey || e.metaKey) && e.code === "KeyY")
      ) {
        e.preventDefault();
        redo();
      } else if (e.code === "KeyS" && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        void splitSelected();
      } else if (e.code === "KeyM" && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        void mergeWithNeighbor();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, snippets, undo, redo]);

  // ------------------------------------------------------------------
  // مراجعة السطور قبل التصدير (المرحلة 3 — line_aggregator)
  // ------------------------------------------------------------------

  async function loadReviewLines() {
    if (!loadedPath) {
      setMessage("حمّل صورة أولًا");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(
        `${API}/api/snippets/lines?source_image=${encodeURIComponent(loadedPath)}&approved_only=true`,
        { headers: apiHeaders() },
      );
      const body = await res.json();
      setReviewLines(body.lines ?? []);
      setMessage(`معاينة السطور: ${body.count ?? 0} سطر / ${body.words ?? 0} كلمة`);
    } catch {
      setMessage("فشل جلب معاينة السطور");
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
          onClick={() => void loadReviewLines()}
          disabled={busy || !loadedPath}
          className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white text-sm rounded-md"
        >
          مراجعة السطور
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

              {/* أدوات كلمة-كلمة: تقسيم / دمج / تراجع / إعادة */}
              <div className="flex flex-wrap gap-2 pt-1">
                <button
                  onClick={() => void splitSelected()}
                  disabled={busy}
                  title="قسّم المربع المحدد نصفين (S) — لعزل كلمة التصقت بأخرى"
                  className="px-3 py-1.5 bg-sky-700 hover:bg-sky-600 disabled:opacity-40 text-white text-sm rounded"
                >
                  تقسيم (S)
                </button>
                <button
                  onClick={() => void mergeWithNeighbor()}
                  disabled={busy}
                  title="ادمج مع أقرب جار في نفس السطر (M) — لكلمة انشطرت مربعين"
                  className="px-3 py-1.5 bg-indigo-700 hover:bg-indigo-600 disabled:opacity-40 text-white text-sm rounded"
                >
                  دمج (M)
                </button>
                <button
                  onClick={undo}
                  disabled={!canUndo || busy}
                  title="تراجع محلي (Ctrl+Z) — عمليات الخادم تُعكس بدمج/تقسيم مقابل"
                  className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-white text-sm rounded"
                >
                  ↩ تراجع
                </button>
                <button
                  onClick={redo}
                  disabled={!canRedo || busy}
                  title="إعادة (Ctrl+Y)"
                  className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-white text-sm rounded"
                >
                  ↪ إعادة
                </button>
              </div>

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
              حدد مربعًا ثم S للتقسيم أو M للدمج — حتى تصبح كل قصاصة كلمة واحدة كاملة.
            </p>
          )}

          <hr className="border-slate-800" />
          <div className="text-xs text-slate-600">
            القصاصات: {snippets.length} (معتمدة: {approvedCount})
          </div>
        </div>
      </div>

      {/* مراجعة السطور المجمعة RTL قبل التصدير */}
      {reviewLines !== null && (
        <LineReviewPanel
          lines={reviewLines}
          onExport={handleExport}
          isExporting={busy}
          previewStats={{
            total_approved: approvedCount,
            unique_images: 1,
            avg_confidence:
              reviewLines.length > 0
                ? reviewLines.reduce((a, l) => a + l.avg_confidence, 0) / reviewLines.length
                : 0,
            with_text: reviewLines.filter((l) => l.text.trim()).length,
          }}
        />
      )}
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

/** شكل السطر القادم من /api/snippets/lines (line_aggregator). */
type ReviewLine = {
  line_index: number;
  bbox: number[];
  text: string;
  words: Array<{ bbox: number[]; text: string; confidence: number; word_index: number }>;
  avg_confidence: number;
  direction: string;
};

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
