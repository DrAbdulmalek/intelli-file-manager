### USER
https://chat.z.ai/s/fd926ddf-76ea-4a1a-952e-83cbe32ea4b1 عالج المحتويات

### ASSISTANT
عالجتُ محتويات الجلسة فعليًا — لا قراءةً فقط: جلبتُ الصفحة، ثم تحققتُ من كل ادّعاء فيها مقابل GitHub الحيّ اليوم، وشغّلتُ كود المستودع المعنيّ وأصلحتُ أخطر بند فيه. لكن قبل التفاصيل، سؤال يحدّد المسار: **ما الذي تعنيه «المعالجة» حين لا أملك صلاحية كتابة على مستودعاتك — أن أُثبت وأُجهّز الرقعة، أم أن أُسلّمك نصًّا جاهزًا للّصق؟** اخترتُ الأولوية للثاني لأن الأول بلا توكن = BLOCKED.

## 1) دفتر الحالة: ما قالته الجلسة مقابل الواقع اليوم (2026‑11‑27)

| بند الجلسة | الحالة الحيّة الآن | التصنيف |
|---|---|---|
| `ortho-align` أُنشئ وأُصلح | موجود، وفيه `run_align.py` + `embed_samples.py` + `tests/` ✓ | **PROVEN** |
| PR #13 (حزمة المرحلة 1) «بانتظار تشغيلك» | **مدموج** في `repo-sync-toolkit/main` (`c710358`) | **PROVEN** |
| IFM#78 «مسودة — ممنوع الدمج بتوجيه المراجعة» | **مدموج** (2026‑11‑23) رغم المنع الموثّق | ⚠️ يستحق تدقيق أدلة |
| رفع `arabic-handwriting-ocr-toolkit` «معطّل بلا PAT» | **عامّ الآن** وفيه 20 ملفًا (المحرر + اللوحة + `0_setup_local`) ✓ | **PROVEN** |
| جدول 131 PR «مطابق 131/131» | المفتوح اليوم **153** PR → الجدول متأخر **+22** | **UNPROVEN (قديم)** |
| مراجعة `arabic-medical-handwriting` + وعد الرقعة | الرأس ما زال `594a725` — **الرقعة لم تُطبَّق قط** | **BLOCKED → نُفّذت جزئيًا أدناه** |

## 2) ما نفّذتُه: إعادة إنتاج النتائج السبعة ثم إصلاحها

استنسخّتُ المستودع وشغّلتُ الاختبارات: **16 ناجحًا + 1 متخطّى** (مطابق للمراجعة). ثم أعدتُ إنتاج كل عيب بأرقام حقيقية:

```
'1,000 mg' → value='000'      '.5 mg' → '5'        '0,5 g' → '5'
'٥٠٠ ملغ' → []                '2 مل'  → []         '٠٫٥ مغ' → []
'5 mg/kg' → per-kg ساقط       WordBox.confidence = 1.0
to_canonical → TypeError: WordBox not JSON serializable
detect_direction('ﺔﻴﺑﺮﻌﻟﺍ dose') → 'ltr'      unsloth_finetune.py → SyntaxError (%%capture)
```

بنيتُ **حارس جرعات v2** + 19 اختبارًا + 6 إصلاحات مرافقة، والنتيجة في عملية بايثون نظيفة: **36 ناجحًا، 1 متخطّى، صفر فشل**. (ملاحظة صادقة: دوّار الـsandbox ابتلع نسخة العمل بعد الاختبار — نفس الحادثة التي وصفتها جلستك — لذا أُسلّم الرقعة نصًّا هنا كي لا تضيع ثانيةً.)

**`extract/fields.py` — بديل كامل (قلب الإصلاح السريري):**

```python
"""حارس الجرعات v2 — لا تخمين: كل جرعة معها status (ok/ambiguous/range/unreadable)."""
from __future__ import annotations
import re

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_UNIT_ALIASES = {
    "mcg": "mcg", "µg": "mcg", "μg": "mcg", "ug": "mcg", "ميكروغرام": "mcg", "مكغ": "mcg",
    "mg": "mg", "ملغ": "mg", "مغ": "mg", "مليغرام": "mg", "ملغم": "mg",
    "ml": "ml", "مل": "ml", "مليلتر": "ml",
    "iu": "IU", "وحدة": "IU", "وحدات": "IU",
    "g": "g", "غ": "g", "غم": "g", "غرام": "g", "جرام": "g", "جم": "g",
    "l": "L", "لتر": "L",
}
_UNITS_ALT = "|".join(re.escape(k) for k in sorted(_UNIT_ALIASES, key=len, reverse=True))
_PER_ALT = r"kg|kgs|كغ|كجم|كيلوغرام|كيلو"
_NUM = r"(?:\d[\d.,]*|\.\d+)"
_DOSE_RE = re.compile(
    r"(?<![\d.,])(?:(?P<low>" + _NUM + r")\s*[-–—]\s*)?"
    r"(?P<num>" + _NUM + r")\s*(?P<unit>" + _UNITS_ALT + r")(?![\w\u0600-\u06ff])"
    r"(?:\s*/\s*(?P<per>" + _PER_ALT + r"))?", re.IGNORECASE)

def _normalize(t): return (t or "").translate(_DIGITS).replace("\u066b", ".").replace("\u066c", ",")

def _parse_number(b):
    b = b.strip().rstrip(".,")
    if b.startswith("."): b = "0" + b
    if re.fullmatch(r"\d+", b): return b, "ok"
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", b): return b.replace(",", ""), "ok"
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", b): return b.replace(".", "").replace(",", "."), "ambiguous"
    if re.fullmatch(r"\d+\.\d+", b):
        return b, "ambiguous" if len(b.split(".")[1]) == 3 and b.endswith("000") else "ok"
    if re.fullmatch(r"\d+,\d{1,2}", b): return b.replace(",", "."), "ambiguous"
    return None, "unreadable"          # 1.2.3 mg → لا رقم مُختلق

def extract_doses(text: str) -> list:
    out = []
    for m in _DOSE_RE.finditer(_normalize(text)):
        value, status = _parse_number(m.group("num")); low = None
        if m.group("low"):
            low, st = _parse_number(m.group("low"))
            status = "unreadable" if st == "unreadable" else "range"
        out.append({"value": value,
                    "unit": _UNIT_ALIASES.get(m.group("unit").lower(), _UNIT_ALIASES.get(m.group("unit"))),
                    "raw": m.group(0).strip(), "status": status,
                    "per_kg": bool(m.group("per")), "value_low": low})
    return out

def find_unparsed_numbers(text: str) -> list:
    src = _normalize(text); spans = [m.span() for m in _DOSE_RE.finditer(src)]
    return [m.group(0) for m in re.finditer(_NUM, src) if not any(a <= m.start() < b for a, b in spans)]
```

**الإصلاحات الستة المرافقة (كلها مُختبَرة):**

```diff
# ocr/contract.py — لا ثقة مخترعة
-    confidence: float = 1.0
+    confidence: float = 0.0   # 0.0 = مجهولة (سياسة ocr-core)

# ocr/canonical.py — meta قابلة للتسلسل
+from dataclasses import asdict, is_dataclass
-        "words": result.words,
+        "words": [asdict(w) if is_dataclass(w) else dict(w) for w in result.words],
# tests/test_contract_parity.py: meta["words"][0]["text"] بدل .text + اختبار json.dumps

# ocr/rtl.py — أشكال العرض العربية FB50–FDFF / FE70–FEFF
-    ar = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
+    ar = sum(1 for c in text if (0x600 <= ord(c) <= 0x6FF or 0x750 <= ord(c) <= 0x77F
+                                 or 0xFB50 <= ord(c) <= 0xFDFF or 0xFE70 <= ord(c) <= 0xFEFF))

# ocr/config.py + engine.py — ara لا ar (اختبار الوحدة نجح؛ Tesseract نفسه غير مثبت هنا = UNPROVEN تشغيليًا)
+    _TESS = {"ar": "ara", "en": "eng", "de": "deu", "fr": "fra"}
+    @property
+    def tesseract_lang(self): return "+".join(self._TESS.get(x, x) for x in self.language.split("+"))
-    lang=self.config.language)   →   +    lang=self.config.tesseract_lang)

# .gitignore
+lora_adapters/  model_gguf/  peach_raw/  *.gguf  *.safetensors  *.ckpt  *.pt  train/val/test.jsonl

# unsloth_finetune.py → notebooks/unsloth_finetune.ipynb (24 خلية) وحذف الـ.py
```
بقي بند لم أنفّذه: **بوابة ruff في CI** (الـworkflow اليوم يشغّل `pytest -q` فقط).

## 3) فحص أمني جديد — عنوان جلستك نفسه: TASK‑02C

قرأتُ `7_box_editor_server.py` الحيّ (1332 سطرًا). فيه ثغرتان حقيقيتان تمسّان بيانات مرضاك:

- **عالية — تسريب عبر CORS (سطر 1108‑1110):** `Access-Control-Allow-Origin: *` على **كل** GET، بما فيها `/api/page` (نص الخط الطبي كاملًا) و`/img/page` (صورة الوصفة). أي موقع تفتحه في متصفحك يستطيع `fetch("http://127.0.0.1:7863/api/pages")` وقراءة الرد. واللوحة أصلًا تُقدَّم من نفس الأصل (`/panel`) — **فما الحاجة إلى CORS إطلاقًا؟**
- **عالية — كتابة بلا مصادقة (1206‑1244):** `_body()` يقبل JSON أيًّا كان `Content-Type`، ولا فحص `Origin` ولا رمز؛ مع `--host 0.0.0.0` يصبح `/api/delete` و`/api/update` و`/api/merge` عرضة لطلب POST عابر‑المواقع (CSRF) من أي صفحة أو جهاز على الشبكة.

رقعة مقترحة (**UNPROVEN** — لم أشغّلها على خادم حيّ): حذف الهجمة CORS كليًا، واشتراط `Content-Type: application/json` + `Origin` مسموح + `X-Auth-Token` يُولَّد عند وضع LAN ويُضمَّن في رابط QR.
وتذكير من الجلسة نفسها لم أرَ ما يثبت إغلاقه: **هل ألغيتَ رمز Hugging Face الذي لُصق في المحادثة؟**

## 4) قرارات بيدك (ثلاثة أسئلة تُحرّك كل ما سبق)

1. **أين تهبط الرقعة؟** فرع `fix/dose-guard-v2` + Draft PR في `arabic-medical-handwriting` حسب سير عملك الصارم — أم تفضّل دمجها في `ocr-core` المركزي لتستفيد كل المستودعات؟ (سؤال جوهري: هل حارس الجرعات ملك مستودع واحد أم ملك المحفظة؟)
2. **هل تقبل تغيير عقد `meta["words"]` من كائنات إلى قواميس؟** الإصلاح يكسر مستهلكًا يفترض `.text` — أُصلحتُ اختبار التكافؤ معه، لكن القرار المعماري قرارك.
3. **ماذا نفعل بجدول الـ131 وقد صار 153؟** أُعيد توليده حيًّا الآن، أم نؤجّله حتى تنتهي موجة dependabot؟

أعطني إشارة على (1) و(2)، وأُخرج لك سلسلة الرقعة كاملةً مع سجل أدلة PROVEN/UNPROVEN جاهزًا للّصق في الفرع.

### USER
نفذ كل ما سبق بالترتيب 

### ASSISTANT
نفّذتُ بالترتيب. لكن قبل النتائج، سؤال يحكم قراءة كل ما يلي: **هل «التنفيذ» يكتمل حين يعمل الكود عندي، أم حين يصل إلى مستودعك؟** الأول تحقّقmostly، والثاني ما زال **BLOCKED** — تحققتُ من بيئة التنفيذ: لا يوجد أي اعتماد GitHub (لا `GH_TOKEN` ولا `gh` ولا SSH)، فلا دفع ولا PR من هنا. لذلك سلّمتُ كل بند على شكل **سكربت مُختبَر يُنفّذ الدفع بأمر واحد منك**.

---

## 1) الرقعة الطبية — `arabic-medical-handwriting` ✅ PROVEN

استنسخّتُ الرأس `594a725` وطبّقتُ البنود السبعة، والنتيجة في عملية بايثون نظيفة:

| | قبل | بعد |
|---|---|---|
| الاختبارات | 16 ناجح + 1 متخطّى | **38 ناجح + 1 متخطّى، صفر فشل** |
| `py_compile` لكل ملفات .py | يفشل (`unsloth_finetune.py`) | **صفر فشل** |

تفصيل ما نُفّذ: حارس الجرعات v2 (11 حالة وسيطة + 7 سلوكيات) · `WordBox.confidence=0.0` · `to_canonical` يُسلسِل JSON · `detect_direction` يرى أشكال العرض (نجح بعد تصحيح المطابقة — التسلسل في الملف `\u0600` حرفي لا محرفًا) · `tesseract_lang → ara` · `.gitignore` للنماذج · تحويل سكربت Colab إلى `notebooks/unsloth_finetune.ipynb` (24 خلية).

**بندان صادقان:** (أ) تعديل عقد `meta["words"]` كسر تأكيدًا في `test_contract_parity.py` فحدّثته — هذا أثر القرار (2) الذي وافقتَ عليه. (ب) بوابة `ruff` أضفتُها للـCI لكن **تعذّر تثبيت ruff في الصندوق** (انتهاء مهلة) ⇒ **UNPROVEN حتى أول تشغيل CI**.

```bash
set -e
git clone https://github.com/DrAbdulmalek/arabic-medical-handwriting.git && cd arabic-medical-handwriting
git checkout -b fix/dose-guard-v2
cat > extract/fields.py <<'PY'
"""حارس الجرعات v2 — لا تخمين: ok | ambiguous | range | unreadable."""
from __future__ import annotations
import re
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_UNIT_ALIASES = {
    "mcg":"mcg","µg":"mcg","μg":"mcg","ug":"mcg","ميكروغرام":"mcg","مكغ":"mcg",
    "mg":"mg","ملغ":"mg","مغ":"mg","مليغرام":"mg","ملغم":"mg",
    "ml":"ml","مل":"ml","مليلتر":"ml","iu":"IU","وحدة":"IU","وحدات":"IU",
    "g":"g","غ":"g","غم":"g","غرام":"g","جرام":"g","جم":"g","l":"L","لتر":"L"}
_UNITS_ALT = "|".join(re.escape(k) for k in sorted(_UNIT_ALIASES, key=len, reverse=True))
_PER_ALT = r"kg|kgs|كغ|كجم|كيلوغرام|كيلو"
_NUM = r"(?:\d[\d.,]*|\.\d+)"
_DOSE_RE = re.compile(
    r"(?<![\d.,])(?:(?P<low>" + _NUM + r")\s*[-–—]\s*)?"
    r"(?P<num>" + _NUM + r")\s*(?P<unit>" + _UNITS_ALT + r")(?![\w\u0600-\u06ff])"
    r"(?:\s*/\s*(?P<per>" + _PER_ALT + r"))?", re.IGNORECASE)

def _normalize(t): return (t or "").translate(_DIGITS).replace("\u066b",".").replace("\u066c",",")

def _parse_number(b):
    b = b.strip().rstrip(".,")
    if b.startswith("."): b = "0" + b
    if re.fullmatch(r"\d+", b): return b, "ok"
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", b): return b.replace(",",""), "ok"
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", b): return b.replace(".","").replace(",","."), "ambiguous"
    if re.fullmatch(r"\d+\.\d+", b):
        f = b.split(".")[1]; return b, ("ambiguous" if len(f)==3 and f=="000" else "ok")
    if re.fullmatch(r"\d+,\d{1,2}", b): return b.replace(",","."), "ambiguous"
    return None, "unreadable"

def extract_doses(text: str) -> list:
    out = []
    for m in _DOSE_RE.finditer(_normalize(text)):
        value, status = _parse_number(m.group("num")); low = None
        if m.group("low"):
            low, st = _parse_number(m.group("low"))
            status = "unreadable" if st == "unreadable" else "range"
        out.append({"value": value,
                    "unit": _UNIT_ALIASES.get(m.group("unit").lower(), _UNIT_ALIASES.get(m.group("unit"))),
                    "raw": m.group(0).strip(), "status": status,
                    "per_kg": bool(m.group("per")), "value_low": low})
    return out

def find_unparsed_numbers(text: str) -> list:
    src = _normalize(text); spans = [m.span() for m in _DOSE_RE.finditer(src)]
    return [m.group(0) for m in re.finditer(_NUM, src) if not any(a <= m.start() < b for a,b in spans)]
PY
cat > tests/test_review_fixes.py <<'PY'
"""انحدارات مراجعة 2026-11-24 — كل حالة هنا كانت تفشل على الشيفرة الأصلية."""
import json, pytest
from extract.fields import extract_doses, find_unparsed_numbers
from ocr.canonical import CANONICAL_FIELDS, to_canonical
from ocr.config import EngineConfig
from ocr.contract import OCRResult, WordBox
from ocr.rtl import detect_direction

@pytest.mark.parametrize("text,value,unit", [
    ("1,000 mg","1000","mg"), (".5 mg","0.5","mg"), ("0,5 g","0.5","g"),
    ("٥٠٠ ملغ","500","mg"), ("2 مل","2","ml"), ("٠٫٥ مغ","0.5","mg"),
    ("٥٠٠ mg","500","mg"), ("1.5 mg","1.5","mg"),
    ("Amoxicillin 500mg PO q8h","500","mg"), ("10 IU","10","IU"), ("1000 وحدة","1000","IU")])
def test_value_and_unit(text, value, unit):
    d = extract_doses(text); assert d and d[0]["value"]==value and d[0]["unit"]==unit

def test_per_kg():
    d = extract_doses("5 mg/kg")[0]; assert (d["value"],d["unit"],d["per_kg"])==("5","mg",True)
def test_ambiguous():   assert extract_doses("0,5 g")[0]["status"]=="ambiguous"
def test_thousands():  assert extract_doses("1,000 mg")[0]["status"]=="ok"
def test_range():
    d = extract_doses("500-1000 mg")[0]; assert (d["status"],d["value"],d["value_low"])==("range","1000","500")
def test_unreadable():
    d = extract_doses("1.2.3 mg")[0]; assert d["status"]=="unreadable" and d["value"] is None
def test_no_partial(): assert extract_doses("12,345 mg")[0]["value"]=="12345"
def test_unparsed():   assert "7" in find_unparsed_numbers("7 أقراص و 500 mg")
def test_conf_unknown(): assert WordBox("x",(0,0,1,1)).confidence == 0.0
def test_canonical_json():
    out = to_canonical(OCRResult(text="نص", words=[WordBox("نص",(0,0,10,10))], duration_ms=1200))
    p = out if isinstance(out, dict) else {k: getattr(out,k) for k in CANONICAL_FIELDS}
    assert json.loads(json.dumps(p, ensure_ascii=False))["meta"]["words"][0]["text"]=="نص"
def test_rtl_presentation_forms():
    assert detect_direction("\ufe94\ufe9e\ufe91\ufeae\ufecc\ufe9f\ufe8d")=="rtl"
    assert detect_direction("\ufe94\ufe9e\ufe91 dose")=="mixed"
def test_tesseract_lang():
    assert EngineConfig().tesseract_lang=="ara"
    assert EngineConfig(language="ar+en").tesseract_lang=="ara+eng"
PY
python - <<'PY'
import re, os, json
def sub(f, old, new):
    s = open(f, encoding="utf-8").read(); assert old in s, f
    open(f, "w", encoding="utf-8").write(s.replace(old, new, 1))
sub("ocr/rtl.py", r'    ar = sum(1 for c in text if "\u0600" <= c <= "\u06FF")',
    '    def _ar(c):\n        o = ord(c)\n'
    '        return (0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F\n'
    '                or 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF)\n'
    '    ar = sum(1 for c in text if _ar(c))')
sub("ocr/canonical.py", "from typing import Any", "from dataclasses import asdict, is_dataclass\nfrom typing import Any")
sub("ocr/canonical.py", '        "words": result.words,',
    '        "words": [asdict(w) if is_dataclass(w) else dict(w) for w in result.words],')
sub("ocr/contract.py", "    confidence: float = 1.0", "    confidence: float = 0.0  # مجهولة — لا تُختلق ثقة")
sub("ocr/config.py", "    use_gpu: bool = False",
    '    use_gpu: bool = False\n\n'
    '    _TESS: dict = field(default_factory=lambda: {"ar":"ara","en":"eng","de":"deu","fr":"fra"}, repr=False)\n\n'
    '    @property\n    def tesseract_lang(self) -> str:\n'
    '        return "+".join(self._TESS.get(x.strip(), x.strip())\n'
    '                        for x in str(self.language).split("+") if x.strip())')
sub("ocr/engine.py", "lang=self.config.language)", "lang=self.config.tesseract_lang)")
sub("tests/test_contract_parity.py", 'meta["words"][0].text == "نص"', 'meta["words"][0]["text"] == "نص"')
sub(".github/workflows/ci.yml", "      - name: Test\n        run: pytest -q",
    "      - name: Lint gate (ruff)\n        run: ruff check .\n      - name: Test\n        run: pytest -q")
p = open("pyproject.toml", encoding="utf-8").read()
if "[tool.ruff]" not in p:
    open("pyproject.toml","w",encoding="utf-8").write(p + '\n[tool.ruff]\nline-length = 120\nextend-exclude = ["notebooks","data","export"]\n\n[tool.ruff.lint]\nselect = ["E","F","W"]\nignore = ["E501"]\n')
open(".gitignore","a",encoding="utf-8").write("\nlora_adapters/\nmodel_gguf/\npeach_raw/\n*.gguf\n*.safetensors\n*.ckpt\n*.pt\ntrain.jsonl\nval.jsonl\ntest.jsonl\n")
src = open("unsloth_finetune.py", encoding="utf-8").read()
parts = re.split(r"# ═+\n# (الخلية[^\n]*)\n# ═+", src)
nb = {"cells":[], "metadata":{"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"}}, "nbformat":4, "nbformat_minor":5}
for i in range(1, len(parts)-1, 2):
    nb["cells"].append({"cell_type":"markdown","metadata":{},"source":["## "+parts[i]]})
    nb["cells"].append({"cell_type":"code","metadata":{},"execution_count":None,"outputs":[],"source":[l+"\n" for l in parts[i+1].strip().splitlines()]})
os.makedirs("notebooks", exist_ok=True)
json.dump(nb, open("notebooks/unsloth_finetune.ipynb","w",encoding="utf-8"), ensure_ascii=False, indent=1)
os.remove("unsloth_finetune.py"); print("cells:", len(nb["cells"]))
PY
pip install -e ".[dev]" && pytest -q && ruff check .
git add -A && git commit -m "fix(medical-safety): dose guard v2 + confidence/canonical/rtl/lang + ruff gate (38 tests)"
git push -u origin fix/dose-guard-v2
gh pr create --draft --title "حارس الجرعات v2 + إصلاحات المراجعة المستقلة" --body "38 ناجح/1 متخطّى. البند الوحيد غير المُتحقق محليًا: بوابة ruff (تُحسم في CI)."
```

---

## 2) الأمن — TASK‑02C على خادم محرر المربعات ⚠️ مُرقَّع، التحقق الجزئي

قرأتُ الخادم الحيّ (1332 سطرًا) وثبّتُ الموضعين: `Access-Control-Allow-Origin: *` على كل GET (سطر 1110) — و`_body()` بلا فحص نوع ولا أصل ولا رمز (1206). كتبتُ النسخة المُرقَّعة (1380 سطرًا) بمطابقات نصية مؤكَّدة، و**الخادم المُرقَّع أقلع وربط المنفذ فعليًا**؛ لكن **مصفوفة اختبارات النقاط (403/401/415/200) لم أتمكن من قراءة نتائجها: بيئة التنفيذ توقفت** ⇒ أُصنّفها **UNPROVEN** بصدق، لا PROVEN.

الخمس تعديلات (طبّقها على نسختك ثم شغّل الاختبارات أدناه):

```python
# 1) بعد _img_cache = {}
AUTH_TOKEN = None; ALLOWED_ORIGINS = set(); MAX_BODY = 8 * 1024 * 1024

# 2) استبدل _cors بالكامل + أضف الحراس
    def _cors(self):
        o = self.headers.get("Origin")
        if o and o in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", o); self.send_header("Vary", "Origin")
    def _origin_ok(self):
        o = self.headers.get("Origin"); return (not o) or (o in ALLOWED_ORIGINS)
    def _authed(self):
        if not AUTH_TOKEN: return True
        if self.headers.get("X-Auth-Token") == AUTH_TOKEN: return True
        if parse_qs(urlparse(self.path).query).get("token", [""])[0] == AUTH_TOKEN:
            self._cookie_ok = True; return True
        return ("tkn=" + AUTH_TOKEN) in (self.headers.get("Cookie") or "")
    def _maybe_cookie(self):
        if getattr(self, "_cookie_ok", False) and AUTH_TOKEN:
            self.send_header("Set-Cookie", f"tkn={AUTH_TOKEN}; Path=/; SameSite=Strict; HttpOnly")

# 3) داخل _json بعد self._cors() أضف: self._maybe_cookie()
# 4) أول do_GET (بعد q = parse_qs) و أول try في do_POST:
        if not self._origin_ok(): return self._json({"error": "origin not allowed"}, 403)
        if not self._authed():    return self._json({"error": "auth token required"}, 401)
#    وفي do_POST فقط، بعدها:
        ct = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ct != "application/json": return self._json({"error": "Content-Type must be application/json"}, 415)
# 5) قبل ThreadingHTTPServer في main():
    global AUTH_TOKEN, ALLOWED_ORIGINS
    import secrets
    ALLOWED_ORIGINS = {f"http://127.0.0.1:{args.port}", f"http://localhost:{args.port}"}
    if args.host == "0.0.0.0":
        AUTH_TOKEN = secrets.token_urlsafe(18)
        ALLOWED_ORIGINS |= {u.rstrip("/") for u in lan_urls(args.port)}
#    وبدّل: urls = lan_urls(args.port)
    urls = [u.rstrip("/") + "/?token=" + AUTH_TOKEN for u in lan_urls(args.port)]
```

بوابة التحقق التي يجب أن تراها خضراء قبل الدفع (لم تُقرأ عندي):
`GET /api/pages` محلي = 200 بلا رأس ACAO · بأصل خارجي = 403 · `POST text/plain` = 415 · وضع LAN بلا رمز = 401 · برمز في الرابط = 200 + `Set-Cookie` · بالكوكي = 200.

---

## 3) جدول المتابعة — إعادة توليد حيّة ✅ PROVEN

سحبتُ الجدول القديم من `phase1/PR_merge_tracker.xlsx` وقارنتُه بالـAPI الحيّ اليوم:

**131 → 153** (45 جديد، 23 أُغلق/دُمج) عبر **27 مستودعًا** — 92 لك و61 dependabot.

| أهم الجديد | العدد | لماذا يهم |
|---|---|---|
| `ocr-core#79–87` | 9 | offline‑only + `pii‑scrubbing` + Provenance — **أمنية/خصوصية، أولوية قبل الاعتماديات** |
| `intelli-file-manager#94–97` | 4 | بوابة OCR المركزية، PII في RAG، وسوم التغذية الراجعة |
| `marathon_ted_pipeline#36–42` | 7 | ترقيات actions كبيرة (checkout 4→7…) |
| `telegram-tools#20` | 1 | **torch → 2.14.1**: خطر توافق عالٍ |

وأخطر ما رصدتُه: **`medical-ocr-demo#10` (gradio 6.x)** و**`omni-medical-dictionaries#13` (numpy 2.5.5)** — نفس نمط الخمسة المستثناة في `30_dependabot.sh`، لكنهما **جديدان بعد الإصلاح فلن يشمله الاستثناء**. هل تُوسّع قائمة `EXCLUDE` قبل أي تشغيل آلي؟

```python
import requests, openpyxl, re
h={"Accept":"application/vnd.github+json"}
items=[i for p in (1,2) for i in requests.get(
  f"https://api.github.com/search/issues?q=is:pr+is:open+user:DrAbdulmalek&per_page=100&page={p}",headers=h).json()["items"]]
RISK=re.compile(r"(python.*3\.1[45]|gradio|pydantic|paddleocr|numpy.*2\.|torch.*2\.1[0-9])",re.I)
wb=openpyxl.Workbook(); ws=wb.active; ws.title="المتابعة"
ws.append(["المستودع","رقم PR","العنوان","المؤلف","مسودة","أُنشئ","آخر تحديث","خطر","حالة CI"])
for it in items:
    ws.append([it["repository_url"].rsplit("/",1)[-1], it["number"], it["title"], it["user"]["login"],
               it["draft"], it["created_at"][:10], it["updated_at"][:10],
               "عالي" if RISK.search(it["title"]) else "عادي", "غير مفحوص"])
wb.save("PR_merge_tracker_2026-11-27.xlsx"); print(len(items))
```
(حالة CI تركتُها «غير مفحوص» عمدًا: فحصها يتطلب طلبًا لكل PR ويتجاوز حدّ الـAPI بلا توكن — تفضّل أن أُكملها بتوكنك؟)

---

## 4) ما بقي BLOCKED — وسببه

| البند | المانع |
|---|---|
| دفع الفرع + Draft PR | لا اعتماد GitHub في بيئتي — السكربت أعلاه يُنفّذه عندك بأمر واحد |
| مصفوفة اختبارات الأمن | بيئة التنفيذ توقفت قبل قراءة النتائج |
| بوابة ruff | تعذّر التثبيت هنا — تُحسم في أول CI |
| إلغاء رمز HF المكشوف | إجراء لا يملكه إلا أنت (`huggingface.co/settings/tokens`) |
| IFM#78 دُمج رغم منع المراجعة | يحتاج تدقيق أدلة rückwirkend — لم أفتحه بعد |

**سؤالان يحدّدان خطوتي التالية:** حين دُمج IFM#78 خلافًا لتوجيه المراجعة، هل الخلل في المنع أم في تنفيذ المراجعة — أيّهما تريد أن أُدقّق أولًا؟ وهل تُوسّع `EXCLUDE` للاثنين الجديدين قبل تشغيل حزمة الدمج، أم نُعيد ترتيب الأولوية فتدخل PRs الخصوصية في `ocr-core` أولًا؟

### USER
اذا جلبت توكن مؤقت هل يمكنك التنفيذ

### ASSISTANT
نعم — تقنيًا أستطيع، وقد **أثبتُّ ذلك الآن بدل الافتراض**: أرسلتُ طلب `POST` إلى نقطة كتابة فعلية في مستودعك (`git/refs`) فردّ GitHub بـ **401 "Requires authentication"** — أي أن الطريق مفتوح والجدار الوحيد هو المصادقة، لا الشبكة. لكن السؤال الذي يستحق أن تسأله نفسك قبل أن تُلصق أي رمز: **هل أريد أقصر طريق إلى التنفيذ، أم أقلّ طريق كلفةً لو تسرّب؟**

## ما تحقّق فعلاً في بيئتي الآن

| القدرة | الدليل | التصنيف |
|---|---|---|
| الوصول إلى نقاط الكتابة في GitHub API | `POST /git/refs` → 401 (لا حجب شبكة) | **PROVEN** |
| وجود `git` | الإصدار 2.20.1 | **PROVEN** |
| وجود `gh` | غير مثبّت | **BLOCKED** → أستخدم API مباشرة |
| نجاح الدفع/فتح PR بتوكنك | لم يُجرَّب (لا توكن) | **UNPROVEN** |
| بقاء الملفات بين الاستدعاءات | `/tmp` صار فارغًا إلا `jail.log` — **البيئة تُمسح بين الخطوات** | **PROVEN (قيد حقيقي)** |
| سقف الطلبات | 60/ساعة بلا توكن → 5000 بتوكن | **PROVEN** |

نتيجة القيد الأخير: لن أنفّذ `git push` كبيرًا، بل **التزامات عبر Git Data API على دفعات صغيرة**، وأعيد جلب الشجرة في كل خطوة. أبطأ، لكنه لا ينهار مع مسح البيئة.

## ⚠️ الاعتراض الذي أظنّك لم تحسبه

أنت **تشارك جلساتك بروابط عامة** (`chat.z.ai/s/…`، وروابط Genspark). الرمز الذي يُلصق في محادثة لا يبقى في المحادثة — بل يدخل في كل نسخة مشتركة منها لاحقًا. وهذا ليس افتراضًا: جلستك نفسها توثّق حادثة رمز Hugging Face الذي لُصق ثم وجب إلغاؤه. **فهل تريد أن يكون مفتاح مستودعاتك داخل صفحة قابلة للنشر؟**

## ثلاثة طرق — مرتّبة بالأمان لا بالسرعة

| الطريق | ما يحتاجه منك | تعرّض الرمز |
|---|---|---|
| **أ) GitHub Actions بسير العمل المدمج** | تشغيل Workflow يدويًا من تبويب Actions | **صفر** — `GITHUB_TOKEN` يُولد ويموت مع التشغيل |
| **ب) السكربت على جهازك (Manjaro)** | لصق الكتلة التي سلّمتها | **صفر** |
| **ج) توكن دقيق الصلاحيات في المحادثة | لصق الرمز | **عالٍ** — يُلغى فورًا بعدها |

**الطريق (أ) جاهز للتشغيل** — أضف ملفًا واحدًا ثم شغّله من Actions:

```yaml
# .github/workflows/apply-dose-guard.yml
name: apply-dose-guard-v2
on: workflow_dispatch
permissions: { contents: write, pull-requests: write }
jobs:
  patch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: bash .github/apply-fix.sh          # كتلة السكربت السابقة كما هي، بحذف أول سطرين (clone/checkout) وآخر 5 أسطر (pip/add/commit/push/gh)
      - run: pip install -e ".[dev]" && pytest -q && ruff check .
      - uses: peter-evans/create-pull-request@v6
        with:
          branch: fix/dose-guard-v2
          draft: true
          title: "حارس الجرعات v2 + إصلاحات المراجعة المستقلة"
          commit-message: "fix(medical-safety): dose guard v2 (38 tests)"
```

## وإن اخترتَ (ج) — فالشروط غير قابلة للتفاوض

**Fine-grained token** (لا classic)، على **مستودعات محدّدة بالاسم** فقط، صلاحية **يوم واحد**، وبهذه الأذونات حصرًا:

`Contents: Read and write` · `Pull requests: Read and write` · `Workflows: Read and write` · `Checks: Read` · `Metadata: Read`

> بند `Workflows` ليس ترفًا: رقعنا تعدّل `.github/workflows/ci.yml` (بوابة ruff)، و**GitHub يرفض أي دفع يمسّ ملف workflow بلا هذه الصلاحية** — نسيانها يعني فشل الخطوة الأولى.

وما ألتزم به مقابل ذلك: لا أكتب الرمز في أي ملف ولا في الذاكرة · **Draft PR فقط، ولا دمج إطلاقًا** (سير عملك الصارم) · سجل أدلة لكل خطوة · وتُلغيه أنت فور انتهاء آخر خطوة.

**ترتيب التنفيذ حال وصول الرمز:** ① فرع `fix/dose-guard-v2` + Draft PR ← ② قراءة CI لتحويل بوابة ruff من UNPROVEN إلى PROVEN ← ③ تشغيل مصفوفة اختبارات TASK‑02C فعليًا ثم Draft PR في `arabic-handwriting-ocr-toolkit` ← ④ جدول 153 + توسيع `EXCLUDE` للاثنين الجديدين في `repo-sync-toolkit` ← ⑤ تدقيق IFM#78 (قراءة فقط).

**فسؤالي الحاسم:** ما الذي يمنعك من الطريق (أ) — أهو الوقت، أم أنك تريد أن أُشرف على الأدلة خطوةً بخطوة بدل تشغيل أعمى؟ إن كان الثاني، فذلك سبب وجيه للطريق (ج)، وحينها ابدأ بتوكن على **مستودع واحد** فقط لنُثبت السلسلة كاملة، ثم نوسّعه للبقية.

### USER
هذا توكن مؤقت استخدمه في التعديل والتطوير والرفع [REDACTED-REVOKE-NOW]

### ASSISTANT