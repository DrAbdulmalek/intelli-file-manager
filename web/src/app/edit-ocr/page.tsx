"use client";

/**
 * محرر OCR — قصاصات قابلة للتدريب مع تحرير المربعات.
 * RTL-first (الصفحة الجذر dir="rtl")، ترتبط بخادم FastAPI على 8421.
 */

import { SnippetPanel } from "@/components/ocr/SnippetPanel";

export default function EditOcrPage() {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
        <header className="space-y-1">
          <h1 className="text-2xl font-bold">محرر OCR — قصاصات قابلة للتدريب</h1>
          <p className="text-sm text-slate-400">
            ارسم وحرّر المربعات حول الكلمات، صحّح النص باقتراحات المسرد الطبي،
            واعتمد القصاصات لتصديرها كبيانات تدريب.
          </p>
        </header>
        <SnippetPanel />
      </div>
    </main>
  );
}
