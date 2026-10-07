"use client";

/**
 * GlossarySuggest — اقتراحات المسرد الطبي أثناء تحرير نص القصاصة.
 *
 * يستدعي /api/glossary/suggest (offline، بلا LLM) مع debounce، ويعرض
 * الاقتراحات كأزرار — النقر يستبدل النص الحالي بالاقتراح.
 */

import { useEffect, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8421/api";

export function GlossarySuggest({
  text,
  onPick,
}: {
  text: string;
  onPick: (suggestion: string) => void;
}) {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const lastQueryRef = useRef<string>("");

  useEffect(() => {
    const query = text.trim();
    if (!query || query === lastQueryRef.current) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setLoading(true);
      try {
        const res = await fetch(
          `${API_BASE}/glossary/suggest?text=${encodeURIComponent(query)}&limit=8`,
          { signal: controller.signal },
        );
        if (res.ok) {
          const body = await res.json();
          lastQueryRef.current = query;
          setSuggestions(body.suggestions ?? []);
        }
      } catch {
        /* aborted or offline — suggestions stay as-is */
      } finally {
        setLoading(false);
      }
    }, 350);
    return () => clearTimeout(timer);
  }, [text]);

  if (!suggestions.length && !loading) return null;

  return (
    <div>
      <span className="text-sm font-medium text-slate-300">
        اقتراحات المسرد الطبي {loading && <span className="text-xs text-slate-500">(جارٍ البحث…)</span>}
      </span>
      <div className="flex flex-wrap gap-2 mt-1">
        {suggestions.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onPick(s)}
            className="px-2 py-1 text-xs bg-sky-500/10 hover:bg-sky-500/30 text-sky-200 border border-sky-500/30 rounded"
            dir="auto"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
