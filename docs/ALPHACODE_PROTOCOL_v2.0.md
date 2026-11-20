# بروتوكول AlphaCode + IntelliFile للتحسين المستمر — v2.0

**الحالة:** مقترح للمراجعة البشرية. **يعتمد على:** `docs/LOCAL_AGENT_FILE_OPERATIONS.md` (v1، مبني على أدلة لوغ WD)، `docs/OBSERVABILITY.md` (أساس الـobservability الموجود في `src/db/observability/`).

## ما الجديد في v2.0 عن v1

v1 عرّف الوكيل المحلي كمُنفّذ آمن لعمليات الملفات. v2.0 يضيف دوراً ثانياً: **كل تجربة تشغيل حقيقية مصدر أدلة لتطوير IntelliFile نفسه**. كل عملية مسح/تصنيف/تحليل تنتج ثلاثة أنواع من النتائج:

1. **نتيجة تشغيلية** — ماذا وجد الوكيل؟ كيف صنّف؟ ما الأخطاء والمخاطر؟
2. **نتيجة تقييمية** — أين أصاب وأين أخطأ؟ ما دقة التصنيف؟ ما العمليات التي لم يستطع تنفيذها؟
3. **نتيجة هندسية** — ما التحسينات التي تكشفها التجربة؟ ما الاختبارات المطلوبة؟ ما العيوب التي تحتاج إصلاحاً؟

---

## 1. المبادئ الأساسية

`READ-ONLY BY DEFAULT` · `LOCAL-FIRST` · `OFFLINE-CAPABLE` · `EXPLICIT EXTERNAL DATA DISCLOSURE` · `DRY-RUN BEFORE EXECUTION` · `NO DATA LOSS` · `NO OVERWRITE` · `NO SILENT FILE MOVES` · `FULL TRACEABILITY` · `EXPLICIT USER APPROVAL` · `REVERSIBLE OPERATIONS WHERE POSSIBLE` · `EVIDENCE-BASED CLASSIFICATION` · `CONTINUOUS PERFORMANCE IMPROVEMENT`.

يجب الفصل بين: الاكتشاف ← التحليل ← التصنيف ← اكتشاف العلاقات والتكرارات ← اقتراح التنظيم ← التنفيذ ← التحقق ← تقييم الأداء ← اقتراح تطوير IntelliFile. نجاح مرحلة ليس دليلاً على نجاح أخرى.

## 2. سياسة الذكاء الاصطناعي والخدمات الخارجية

### الوضع الافتراضي
- المعالجة المحلية أولاً؛ النموذج الخارجي عند فائدة واضحة فقط.
- لا `Cloud Fallback` صامت. لا إرسال محتويات الملفات دون إفصاح.
- سجّل دائماً: اسم الخدمة/النموذج، نوع البيانات المرسلة، الغرض.

### مستويات البيانات
| المستوى | التعريف | السياسة |
|---|---|---|
| `PUBLIC` | بيانات عامة | يمكن إرسالها |
| `NON_SENSITIVE` | بيانات تشغيلية، أسماء غير حساسة | تُرسل ضمن السياسة المعلنة |
| `PRIVATE` | معلومات شخصية | لا محتوى دون موافقة محددة |
| `SENSITIVE_MEDICAL` | MRI، DICOM، تقارير طبية، بيانات مرضى | **لا تُرسل أبداً** |
| `SECURITY_SECRETS` | كلمات مرور، مفاتيح SSH، tokens، `.env`، شهادات | **لا تُرسل أبداً** |

### تسجيل استخدام الخدمة الخارجية
`provider` · `model` · `request_timestamp` · `purpose` · `data_classification` · `data_fields_sent` · `content_was_sent` · `redaction_applied` · `response_status` · `latency_ms` · `estimated_cost_if_available`. لا تُسجَّل الأسرار أو محتويات الملفات الحساسة في اللوغ.

## 3. المهمة الأولى: مراجعة القدرات قبل أي تعديل

قبل أي نقل أو تطوير، تقرير يجيب عن 20 سؤالاً (اكتشاف الملفات، آلية الاجتياز، استخدام `path_policy.py`، استبعاد المخفي، الروابط الرمزية، تحديد النوع، الامتداد أم المحتوى أم السياق، التحليل الدلالي، تحديد المجلد النهائي، العربية وUnicode، المسافات والرموز والأسماء بشرطة، التكرارات، الإصدارات، الملفات الحساسة، آلية النقل، `SafeMover` كبوابة وحيدة، التحقق بعد النقل، التراجع، ما يسجله اللوغ وما لا يسجله).

**لكل إجابة:** اسم الملف والمسار والدالة/الكلاس، وصف السلوك الفعلي، دليل من الكود أو الاختبارات، درجة الثقة. **التصنيفات:** `PROVEN` · `PARTIALLY_PROVEN` · `UNPROVEN` · `CONTRADICTED` · `BLOCKED`. لا تُنسب للمشروع ميزة غير موجودة؛ لا تكتفي بقراءة README — افحص التنفيذ والاختبارات.

## 4. اكتشاف الملفات وتحليلها

لا تعتمد على الامتداد وحده. أربع طبقات أدلة:

**A. Metadata:** الاسم، الامتداد، MIME، magic bytes، الحجم، التواريخ، المجلد الأب، الصلاحيات عند الحاجة، معلومات نظام الملفات عند الحاجة.

**B. تحليل الاسم:** الكلمات، التواريخ، الإصدارات، المشروع، اللغة، `Final`/`Draft`/`Backup`/`Scan`/`Report`/`Invoice`، مؤشرات التكرار.

**C. تحليل المحتوى (عندما آمن ومسموح):** عينة محدودة، عناوين وكلمات مفتاحية، اكتشاف اللغة، طبيعة المستند، العلاقات، التمييز بين النص الأصلي ونتائج OCR (OCR ليس دليلاً مؤكداً دون تقييم موثوقية).

**D. تحليل السياق:** المجلد الأب، الملفات المجاورة، بنية المشروع، المجموعات المترابطة. لا تتجاوز جذر المسح الذي حدده المستخدم.

## 5. التصنيف الهرمي

- **Level 1 — الفئة الرئيسية:** Documents · Images · Videos · Audio · Archives · Software · Programming · Books · Research · Finance · Administration · Education · Personal · Medical · Engineering · Unknown.
- **Level 2 — الفئة الفرعية:** مثال — Documents: Reports/Contracts/Invoices/Correspondence/Forms/Presentations/Notes/Manuals؛ Programming: Source Code/Configuration/Documentation/Build Artifacts/Dependencies/Backups؛ Images: Photos/Screenshots/Scanned Documents/Diagrams/Graphics.
- **Level 3 — المشروع/السياق:** مثال — `Medical/Orthopaedics/Research/Books/Translations/Clinical`.

لا مجلدات عشوائية؛ لا مجلد جديد لكل ملف.

## 6. العلاقات والتكرارات

الأنواع: `EXACT_DUPLICATE` · `SIMILAR_FILENAME` · `SIMILAR_CONTENT` · `DIFFERENT_VERSION` · `RELATED_FILE` · `EXTRACTED_FROM_ARCHIVE` · `OCR_DERIVATIVE` · `ORIGINAL_TRANSLATION_PAIR`.

SHA-256 للتحقق الحقيقي عند الحاجة. تشابه الاسم ليس دليلاً على التطابق. لا حذف للمكررات، لا دمج تلقائي. كل مجموعة مترابطة تأخذ `Relationship Group ID` في التقرير.

## 7. درجات الثقة

لكل تصنيف: `category` · `subcategory` · `project` · `confidence` · `evidence` · `alternative_categories` · `classification_method` · `requires_review`.

| المدى | المعنى |
|---|---|
| 0.90–1.00 | أدلة قوية متعددة |
| 0.75–0.89 | تصنيف مرجّح |
| 0.50–0.74 | تصنيف مبدئي |
| 0.00–0.49 | غير مؤكد |

لا تختلق درجة ثقة، ولا ترفعها لمجرد اتفاق نماذج تستخدم الأدلة نفسها. عند نقص الأدلة: `UNKNOWN / NEEDS_REVIEW`.

## 8. سياسة المسارات

السياسة الموحدة: `src/core/path_policy.py`. لا آلية اجتياز مستقلة، لا `rglob` يتجاوز السياسة.

- استبعد: `.git` · `.ssh` · `.config` · `.venv` · `venv` · `node_modules` · `pycache`.
- المخفي مستثنى افتراضياً. الروابط الرمزية لا تُتبع. لا عبور mount points دون سياسة صريحة.
- المجلدات المستثناة لا تُدخل حتى لو طُلب تضمين المخفي — **إلا** إذا اختار المستخدم بنفسه جذر مسح تحت مجلد مخفي، فيُسمح بمسح محتوياته وفق السياسة النسبية للجذر.
- الجذر يحدده المستخدم، لا الوكيل. سجّل عدد المستثناة وأسبابها دون كشف خصوصية لازمة.

## 9. حماية الملفات الحساسة

`.env` · مفاتيح SSH/الخاصة · قواعد كلمات المرور · بروفايلات المتصفح · tokens · الشهادات · السجلات المالية · وثائق الهوية · السجلات الطبية · قواعد بيانات التطبيقات:

لا تُقرأ محتوياتها للتصنيف، لا تُنقل تلقائياً، لا تُرسل خارجياً. تُوضع في `SENSITIVE / REVIEW_REQUIRED`. لا محتوى في اللوغ، لا نسخ إضافية.

## 10. تحديد الوجهة

لكل ملف: `source_path` · `proposed_category` · `proposed_subcategory` · `project` · `destination_directory` · `final_destination_path` · `confidence` · `evidence` · `reason` · `collision_status` · `sensitivity_status` · `recommended_action` · `requires_approval`.

انتبه للفرق بين `/Documents/Reports/` (مجلد) و`/Documents/Reports/report.pdf` (الملف نفسه) — `final_destination_path` يشير للملف. لا طبقات مجلدات مكررة.

## 11. أسماء الملفات

دعم: العربية، الإنجليزية، المسافات، الأقواس، الرموز، Unicode، الأسماء الطويلة، الأسماء التي تبدأ بشرطة. لا تقسيم مسارات على المسافات، لا shell string concatenation، لا تغيير الاسم دون ضرورة وموافقة، لا افتراض أن تطبيع Unicode أو تغيير الحالة آمن على كل الأنظمة.

## 12. سياسة التضارب

الهدف موجود؟ لا استبدال، لا حذف، لا دمج، لا نقل داخل المجلد الهدف غير مقصود. اسم بديل ممكن مع إعادة التحقق أثناء التنفيذ الفعلي. تضارب أثناء التنفيذ: `STOP + LOG + REPORT`.

## 13. تنفيذ العمليات

ممنوع كآليات مستقلة: `mv` · `cp` · `rm` · `os.replace` · `shutil.move` · `shutil.copy`. **`SafeMover` هي بوابة التنفيذ الوحيدة** للعمليات التي يدعمها المشروع — وهي ملفّي فقط (انظر `docs/SAFE_MOVER_HARDENING.md`). لا التفاف بأوامر خام؛ العملية غير المدعومة تحتاج تطويراً آمناً مختبراً داخل بنية IntelliFile أولاً.

قبل التنفيذ: الخطة ← المصدر ← الوجهة ← التضارب ← السلامة ← SHA-256 عند الحاجة ← موافقة المستخدم ← دفعة صغيرة ← تحقق ← سجل ← بيانات تراجع. إن لم تُضمن السلامة: توقف.

## 14. Tree Manifest

`scripts/tree_manifest.py` موجود ومختبَر (snapshot/verify، يرى المخفي والفارغ، لا يتبع الروابط، يفشل صراحة عند الفقد أو عدم اكتمال القراءة). لا تُعد التحقق ناجحاً إلا بنتيجة واضحة كاملة؛ أي اختلاف يوقف الدفعة.

## 15. نظام اللوغات — أساس التطوير

لا لوغ مختصر («Done»/«تم بنجاح»). لكل جلسة `session_id` وسجل مستقل لكل مرحلة:

| النوع | أبرز الحقول |
|---|---|
| A. `SESSION_LOG` | session_id, agent_version, IntelliFile_version, OS, filesystem, scan_root, execution_mode, duration, final_status |
| B. `DISCOVERY_LOG` | file_id, file_type, detected_mime/signature, size, discovery_method, parent_context, scan_status, exclusion_reason, read_status |
| C. `CLASSIFICATION_LOG` | file_id, predicted_category/subcategory, project, confidence, evidence_types, alternatives, method, model_name, duration, review_required |
| D. `RELATIONSHIP_LOG` | relationship_group_id, file_ids, relationship_type, similarity_method, hash_match, version_relationship, confidence |
| E. `ORGANIZATION_PLAN_LOG` | plan_id, file_id, source/destination/final_destination, reason, confidence, collision_status, sensitivity_status, requires_approval |
| F. `EXECUTION_LOG` | operation_id, plan_id, approval_reference, operation_type, pre/post_operation_hash, result, error_code, verification_status, rollback_reference |
| G. `ERROR_LOG` | error_id, component, function, error_type, error_message_redacted, errno, reproducibility, severity, recovery_status |
| H. `PERFORMANCE_LOG` | total/processed/classified/unclassified/excluded/unreadable/sensitive_files, bytes_scanned, avg times (classification/file/hashing/OCR/AI), peak_memory, cache_hits/misses |
| I. `USER_FEEDBACK_LOG` | file_id, original_prediction, corrected_classification, feedback, confidence_before/after |
| J. `ENGINEERING_FINDINGS_LOG` | finding_id, component, affected_function, observed vs expected behavior, reproduction_steps, evidence, severity, frequency, root_cause_status, proposed_fix, proposed_test, regression_risk, status |

حالات الـfinding: `NEW` · `INVESTIGATING` · `REPRODUCED` · `CONFIRMED` · `PROPOSED` · `FIXED` · `TESTED` · `VERIFIED` · `DEFERRED` · `BLOCKED`. لا يتحول المشتبه به إلى Bug مؤكد دون إعادة إنتاج أو دليل كافٍ.

## 16. جودة اللوغات والخصوصية

مجموعتان منفصلتان:
- **OPERATIONAL LOGS** — محلية مفصلة (قد تتضمن مسارات حقيقية لإعادة الإنتاج)، **خارج Git**.
- **ENGINEERING LOGS** — منقّحة للمراجعة: File IDs بدل الأسماء الشخصية، مسارات منقّحة، error codes، خطوات إعادة إنتاج ببيانات اختبار، إحصاءات مجمعة.

لا رفع للسجلات التشغيلية إلى GitHub؛ لا أسماء مستخدمين أو مسارات شخصية أو أسماء ملفات طبية في المستودع. تدوير واحتفاظ بسياسة واضحة، ولا حذف سجل قبل التأكد من النسخة المطلوبة.

## 17. قياس الأداء

- **التصنيف:** Accuracy, Precision, Recall, F1, Macro F1, Per-category F1, Unknown rate, Confidence calibration — لا دقة حقيقية دون Ground Truth موثوق.
- **التكرارات:** detection rate, false positive/negative rate, version detection quality.
- **التشغيل:** files/sec, avg processing, memory, CPU, hashing/OCR overhead, failure/recovery rate.
- **السلامة:** unauthorized traversal attempts, symlink failures, collision detection failures, verification failures, unapproved operation attempts, integrity incidents — كل محاولة تجاوز حادثة مستقلة.

## 18. من التجربة إلى تطوير IntelliFile

ابحث عن: أخطاء التصنيف والوجهة، سوء فهم السياق، ضعف العربية/Unicode، الأسماء الطويلة، المسافات والرموز، ضعف التكرارات/الإصدارات، مشاكل Path Policy وSafeMover، ضعف التحقق بعد النقل، نقص الاختبارات، الأداء والذاكرة، الملفات الكبيرة، قصور اللوغات، صعوبة إعادة الإنتاج.

لكل مشكلة: دليل، المكون المسؤول، الأثر، إصلاح مقترح، اختبار يمنع التكرار، مخاطر الإصلاح. لا تعديل تلقائي لـIntelliFile في هذه المرحلة، لا رفع لـGitHub، ولا إعادة تصميم من جلسة واحدة.

## 19. دورة التحسين

`OBSERVE → COLLECT EVIDENCE → CLASSIFY FINDINGS → MEASURE → REPRODUCE → PROPOSE → DESIGN REGRESSION TESTS → USER REVIEW → IMPLEMENT (stage معتمدة منفصلة) → CI + SECURITY REVIEW → VALIDATION → BASELINE COMPARISON`

لكل تحسين: Finding ID، Related Session ID، Related Test ID، Before Metric، Expected After، Actual After، Validation Status. لا ادعاء تحسن دون مقارنة قبلية/بعدية، ولا إصلاح Bug دون اختبار يثبته.

## 20. سياسة التطوير البرمجي

لا تعديل `main` مباشرة، لا كتابة فوق ملفات المستخدم، لا حذف وظائف دون إثبات، لا أدوات موازية تتجاوز Path Policy، لا آليات نقل تتجاوز SafeMover. اختبارات سلبية وإيجابية، توافق مع البنية، مراجعة أمنية، تحديث `AI_WORKLOG.md` و`CHANGELOG.md`، لا دمج PR دون مراجعة وCI. كل تعديل صغير، محدد، قابل للمراجعة والتراجع.

## 21. المهمة الأولى — READ_ONLY_DIAGNOSTICS

ممنوع: نقل، إعادة تسمية، حذف، تعديل ملفات المستخدم أو مستودع IntelliFile، إنشاء مجلدات تنظيم، أوامر تنظيف.

- **المرحلة 1 — حالة القرص WD:** التحقق من مواقع العناصر المعروفة (galaxy s6 tab ~60GB، orthopaedic books ~2.6GB، صور غير لازمة ~1.6GB، Android/، APK، Books/، New folder*، sorted، *_extracted)؛ عدد الملفات والحجم لكل مجلد رئيسي في WD_organized؛ المقارنة مع لوغ التنظيم السابق دون الاعتماد عليه وحده. ما لا يُجد: `NOT VERIFIED` — دون استعادة أو نقل.
- **المرحلة 2 — تشخيص AlphaCode:** 12 محوراً (الاكتشاف، التصنيف، الوجهات، التكرارات، الملفات الكبيرة والحساسة، المسارات، العربية، النقل، التحقق، التراجع، جودة اللوغ) بأدلة من التنفيذ الفعلي.
- **المرحلة 3 — تشخيص IntelliFile:** الكود والاختبارات، بدءاً بـ`src/core/path_policy.py` و`safe_mover.py` وActionLog/UndoLog والclassifier وfile_agent وfile_handler وduplicate detection وsmart_tagger وhybrid/semantic search وemergent_category وtests/ — **دون افتراض وجود ملف بالاسم المذكور دون تحقق**.
- **المرحلة 4 — تقارير الجلسة:** SESSION_REPORT.md، DISCOVERY_SUMMARY.json، CLASSIFICATION_SUMMARY.json، DUPLICATE_ANALYSIS.json، PERFORMANCE_REPORT.json، ENGINEERING_FINDINGS.json، IMPROVEMENT_ROADMAP.md، SESSION_LOG.jsonl — في مجلد جلسة محلي **خارج Git**، بلا محتوى حساس.
- **المرحلة 5 — خطة التطوير:** P0 Critical Safety · P1 Data Integrity · P2 Classification Accuracy · P3 Arabic/Unicode · P4 Performance · P5 Logging/Observability · P6 Advanced AI — لكل تحسين: المشكلة، الدليل، المكون، الأولوية، الحل، الاختبار، المخاطر، معيار النجاح.

## 22. التقرير النهائي

الأقسام: Actual Findings · Unverified Claims · Operational Performance · Classification Quality · Safety Findings · Engineering Findings · Improvement Roadmap · Log Files · Blocked Items.

لا «SUCCESS» إلا بدليل قابل للتحقق، لا ✅ لمجرد انتهاء الأمر. التمييز الإلزامي: `EXECUTED` · `VERIFIED` · `PARTIALLY_VERIFIED` · `NOT_VERIFIED` · `FAILED` · `BLOCKED`.

## 23. شرط الانتقال للمرحلة التالية

بعد المهمة الأولى: **توقف.** لا تنفيذ، لا نقل، لا تعديل IntelliFile. عرض التقرير واللوغات وخطة التطوير وانتظار مراجعة المستخدم وموافقته الصريحة.
