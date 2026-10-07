import { describe, expect, it } from "vitest";
import {
  splitBBox,
  splitSnippet,
  mergeBBox,
  mergeSnippets,
  sortSnippetsRTL,
  suggestSplitPoint,
  type SnippetLike,
} from "@/lib/snippet-ops";

const makeSnippet = (overrides: Partial<SnippetLike> = {}): SnippetLike => ({
  id: 1,
  bbox: { x1: 100, y1: 50, x2: 200, y2: 80 },
  text: "",
  ocrText: "",
  confidence: 0.9,
  lineIndex: 0,
  wordIndex: 0,
  source: "projection",
  ...overrides,
});

describe("splitBBox", () => {
  it("يقسم المربع عند نقطة X إلى نصفين متجاورين", () => {
    const [left, right] = splitBBox({ x1: 100, y1: 50, x2: 200, y2: 80 }, 150);
    expect(left).toEqual({ x1: 100, y1: 50, x2: 150, y2: 80 });
    expect(right).toEqual({ x1: 150, y1: 50, x2: 200, y2: 80 });
  });

  it("يحترم الحد الأدنى (2px) عند التقسيم قرب الحافة", () => {
    const [, right] = splitBBox({ x1: 100, y1: 50, x2: 200, y2: 80 }, 101);
    expect(right.x1).toBe(102);
  });
});

describe("splitSnippet", () => {
  it("ينتج قصاصتين بمعرفين مختلفين ونص فارغ للتحرير", () => {
    const s = makeSnippet({ text: "كلمتان" });
    let counter = 100;
    const [left, right] = splitSnippet(s, 150, () => counter++);

    expect(left.bbox.x1).toBe(100);
    expect(left.bbox.x2).toBe(150);
    expect(right.bbox.x1).toBe(150);
    expect(right.bbox.x2).toBe(200);
    expect(left.id).not.toBe(right.id);
    // بعد التقسيم يجب إعادة تحرير النص يدويًا (لا نص موروثًا خاطئًا)
    expect(left.text).toBe("");
    expect(right.text).toBe("");
  });
});

describe("mergeBBox / mergeSnippets", () => {
  it("يدمج مربعين في BBox يحيط بهما", () => {
    const merged = mergeBBox([
      { x1: 10, y1: 50, x2: 50, y2: 80 },
      { x1: 60, y1: 55, x2: 120, y2: 85 },
    ]);
    expect(merged).toEqual({ x1: 10, y1: 50, x2: 120, y2: 85 });
  });

  it("يدمج النصوص بترتيب RTL القرائي (الأيمن أولًا)", () => {
    const right = makeSnippet({ id: 1, bbox: { x1: 200, y1: 50, x2: 300, y2: 80 }, text: "السلام" });
    const left = makeSnippet({ id: 2, bbox: { x1: 100, y1: 50, x2: 190, y2: 80 }, text: "عليكم" });
    const merged = mergeSnippets([left, right], () => 999);
    expect(merged.text).toBe("السلام عليكم");
  });

  it("الثقة 0.0 (مجهولة) لا تُختلق — تبقى مجهولة إذا كانت كلها كذلك", () => {
    const a = makeSnippet({ id: 1, confidence: 0 });
    const b = makeSnippet({ id: 2, confidence: 0, bbox: { x1: 210, y1: 50, x2: 300, y2: 80 } });
    const merged = mergeSnippets([a, b], () => 999);
    expect(merged.confidence).toBe(0);
  });

  it("يمنع الدمج إذا كان أقل من قصاصتين", () => {
    expect(() => mergeSnippets([makeSnippet()], () => 1)).toThrow();
  });
});

describe("sortSnippetsRTL", () => {
  it("يرتب الكلمات داخل السطر من اليمين لليسار ويعيد الترقيم", () => {
    const snippets = [
      makeSnippet({ id: 1, bbox: { x1: 10, y1: 50, x2: 50, y2: 80 }, lineIndex: 0 }),
      makeSnippet({ id: 2, bbox: { x1: 200, y1: 50, x2: 250, y2: 80 }, lineIndex: 0 }),
      makeSnippet({ id: 3, bbox: { x1: 100, y1: 50, x2: 150, y2: 80 }, lineIndex: 0 }),
    ];

    const sorted = sortSnippetsRTL(snippets);

    // RTL: الأول = x2 الأكبر (يمين)
    expect(sorted[0].id).toBe(2);
    expect(sorted[1].id).toBe(3);
    expect(sorted[2].id).toBe(1);
    // إعادة الترقيم داخل السطر
    expect(sorted.map((s) => s.wordIndex)).toEqual([0, 1, 2]);
  });
});

describe("suggestSplitPoint", () => {
  it("يجد أخلّى عمود في النصف الأوسط", () => {
    const s = makeSnippet({ bbox: { x1: 100, y1: 50, x2: 200, y2: 80 } });
    const densities = new Array(300).fill(0.8);
    densities[150] = 0.0; // فراغ في المنتصف
    expect(suggestSplitPoint(s, densities)).toBe(150);
  });

  it("يعيد null إذا لا فراغ", () => {
    const s = makeSnippet();
    const densities = new Array(300).fill(0.9);
    expect(suggestSplitPoint(s, densities)).toBeNull();
  });
});
