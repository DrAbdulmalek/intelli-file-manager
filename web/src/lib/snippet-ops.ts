/**
 * snippet-ops — عمليات تقسيم/دمج/ترتيب قصاصات الكلمات (RTL-aware).
 *
 * المصدر: محادثة DeepSeek (المرحلة 2/3) — مُكيَّف مع نموذج القصاصات الفعلي
 * في هذا المستودع (BBoxEditor/SnippetPanel): bbox {x1,y1,x2,y2}، والحالات
 * pending/approved/rejected (بلا حالة "edited" — التقسيم/الدمج يُنتج قصاصات
 * pending جديدة لأن المعرّفات تُدار خادميًا).
 *
 * دوال نقية (بلا React) — قابلة للاختبار مباشرة (vitest).
 */

export type BBox = { x1: number; y1: number; x2: number; y2: number };

/** قصاصة متوافقة بنيويًا مع Snippet في BBoxEditor (حقول إضافية اختيارية). */
export type SnippetLike = {
  id: number;
  bbox: BBox;
  text: string;
  ocrText: string;
  confidence: number;
  lineIndex?: number | null;
  wordIndex?: number | null;
  source?: string;
};

/**
 * تقسيم مربع عند نقطة X (بكسل بإحداثيات الصورة الأصلية).
 * يعيد نصفي المربع [يسار, يمين] — النص لا يُقسم (يُعاد تحريره يدويًا).
 */
export function splitBBox(bbox: BBox, splitX: number): [BBox, BBox] {
  const { x1, y1, x2, y2 } = bbox;
  // حماية: نقطة التقسيم يجب أن تكون داخل المربع بهامش أدنى بكسلين
  const safeX = Math.max(x1 + 2, Math.min(x2 - 2, Math.round(splitX)));
  return [
    { x1, y1, x2: safeX, y2 },          // النصف الأيسر
    { x1: safeX, y1, x2, y2 },          // النصف الأيمن
  ];
}

/**
 * تقسيم قصاصة إلى قصاصتين (نسخة نقية للاختبارات وسير العمل المحلي).
 * المعرفان الجديدان يأتيان من nextId (في التطبيق الحقيقي الخادم يولدهما).
 */
export function splitSnippet<T extends SnippetLike>(
  snippet: T,
  splitX: number,
  nextId: () => number,
): [T, T] {
  const [leftB, rightB] = splitBBox(snippet.bbox, splitX);

  const left = {
    ...snippet,
    id: nextId(),
    bbox: leftB,
    text: "",       // يُعاد النص للتحرير اليدوي
    ocrText: "",
  } as T;

  const right = {
    ...snippet,
    id: nextId(),
    bbox: rightB,
    text: "",
    ocrText: "",
  } as T;

  return [left, right];
}

/**
 * دمج عدة مربعات في مربع واحد (الحد الأدنى/الأقصى للإحداثيات).
 * النصوص تُدمج بترتيب RTL القرائي (الأيمن أولًا) إن وُجدت.
 */
export function mergeBBox(boxes: BBox[]): BBox {
  return {
    x1: Math.min(...boxes.map((b) => b.x1)),
    y1: Math.min(...boxes.map((b) => b.y1)),
    x2: Math.max(...boxes.map((b) => b.x2)),
    y2: Math.max(...boxes.map((b) => b.y2)),
  };
}

export function mergeSnippets<T extends SnippetLike>(
  snippets: T[],
  nextId: () => number,
): T {
  if (snippets.length < 2) {
    throw new Error("يحتاج الدمج قصاصتين على الأقل");
  }

  // ترتيب قرائي RTL: الأيمن (x2 الأكبر) أولًا — ثم دمج النصوص
  const readingOrder = [...snippets].sort((a, b) => b.bbox.x2 - a.bbox.x2);
  const mergedText = readingOrder
    .map((s) => s.text.trim())
    .filter(Boolean)
    .join(" ");

  const known = snippets.filter((s) => s.confidence > 0);
  // سياسة الثقة: 0.0 = غير معروفة — لا تُختلق؛ إن كانت كلها مجهولة فالناتج 0.0
  const avgConfidence =
    known.length > 0
      ? known.reduce((sum, s) => sum + s.confidence, 0) / known.length
      : 0;

  return {
    ...snippets[0],
    id: nextId(),
    bbox: mergeBBox(snippets.map((s) => s.bbox)),
    text: mergedText,
    ocrText: "",
    confidence: avgConfidence,
  } as T;
}

/**
 * إعادة ترتيب القصاصات حسب RTL (يمين ← يسار) داخل كل سطر.
 * السطر يُستنتج من lineIndex إن وُجد، وإلا من تقدير شريط y (خطوة 50px).
 */
export function sortSnippetsRTL<T extends SnippetLike>(snippets: T[]): T[] {
  const lineOf = (s: T): number =>
    s.lineIndex ?? Math.floor(s.bbox.y1 / 50);

  // 1. رتّب حسب السطر ثم y_min، وداخل السطر: RTL (x2 الأكبر أولًا)
  const sorted = [...snippets].sort((a, b) => {
    const lineA = lineOf(a);
    const lineB = lineOf(b);
    if (lineA !== lineB) return lineA - lineB;
    return b.bbox.x2 - a.bbox.x2;
  });

  // 2. أعد ترقيم الكلمات داخل كل سطر
  const lineMap = new Map<number, number>();
  return sorted.map((s) => {
    const line = lineOf(s);
    const wordIdx = lineMap.get(line) ?? 0;
    lineMap.set(line, wordIdx + 1);
    return { ...s, lineIndex: line, wordIndex: wordIdx } as T;
  });
}

/**
 * حساب نقطة تقسيم مقترحة بناءً على الفراغات البيضاء في الصورة.
 * columnDensities: كثافة الحبر لكل عمود x (0..1) من إحداثيات الصورة.
 */
export function suggestSplitPoint(
  snippet: SnippetLike,
  columnDensities: number[],
  threshold: number = 0.1,
): number | null {
  const { x1, x2 } = snippet.bbox;

  // ابحث عن أخلّى فراغ (عمود بكثافة منخفضة) في النصف الأوسط من المربع
  const start = Math.floor(x1 + (x2 - x1) * 0.3);
  const end = Math.floor(x1 + (x2 - x1) * 0.7);

  let bestX: number | null = null;
  let minDensity = Infinity;

  for (let x = start; x < end; x++) {
    const d = columnDensities[x] ?? 1;
    if (d < threshold && d < minDensity) {
      minDensity = d;
      bestX = x;
    }
  }

  return bestX;
}
