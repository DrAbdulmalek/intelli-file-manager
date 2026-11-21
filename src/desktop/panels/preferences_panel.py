# -*- coding: utf-8 -*-
"""PreferencesPanel — لوحة تفضيلات التصنيف التعليمية (P1/P2 — مهمة §7)

تعرض للاقتراح الحالي: التصنيف الأصلي، المقترح، السبب، الثقة، عدد
التأكيدات المستقلة، القاعدة المستخدمة، وجود تعارض، ومصدر التفضيل.
وتعرض جدول القواعد المكتسبة مع إدارة كاملة.

حدود سلامة صارمة:
  - هذه اللوحة **لا تنفّذ أي عملية ملف إطلاقًا** — لا نقل، لا حذف.
  - أزرار Accept/Reject/Correct تسجّل قرارات التعلم فقط (تأكيد قاعدة/
    رفض/تصحيح عبر FeedbackEngine) — النقل الفعلي يمر حصرًا عبر مسار
    الموافقة الحالي الموثق (RuleEngine dry-run → execute عبر SafeMover).
  - المحرك معطل → عرض حالة التحذير وتعطيل الأزرار.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.feedback_engine import FeedbackEngine
from src.core.preference_engine import PreferenceEngine

_STATUS_AR = {
    "provisional": "مبدئية",
    "stable": "مستقرة",
    "disabled": "معطلة",
    "deleted": "محذوفة",
}


class PreferencesPanel(QWidget):
    """لوحة التفضيلات — تعلم من تصحيحاتك، بلا أي عملية ملف.

    Signals:
        learning_changed(): تغيرت حالة القواعد (لتحديث العروض الأخرى)
    """

    learning_changed = Signal()

    def __init__(self, engine: PreferenceEngine | None = None,
                 feedback: FeedbackEngine | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.engine = engine
        self.feedback = feedback
        self._current_suggestion: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("تفضيلات التصنيف التعليمية")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "الاقتراح لا ينفّذ أي عملية — النقل يمر عبر مسار الموافقة المعتمد فقط")
        subtitle.setObjectName("PanelSubtitle")
        layout.addWidget(subtitle)

        # ─── الاقتراح الحالي ─────────────────────────────────────────────
        suggestion_box = QGroupBox("الاقتراح الحالي")
        form = QFormLayout(suggestion_box)
        self.lbl_original = QLabel("—")
        self.lbl_suggested = QLabel("—")
        self.lbl_reason = QLabel("—")
        self.lbl_reason.setWordWrap(True)
        self.lbl_confidence = QLabel("—")
        self.lbl_confirmations = QLabel("—")
        self.lbl_rule = QLabel("—")
        self.lbl_conflict = QLabel("—")
        self.lbl_source = QLabel("—")
        form.addRow("التصنيف الأصلي:", self.lbl_original)
        form.addRow("المقترح بعد التفضيلات:", self.lbl_suggested)
        form.addRow("سبب الاقتراح:", self.lbl_reason)
        form.addRow("مستوى الثقة:", self.lbl_confidence)
        form.addRow("تأكيدات مستقلة:", self.lbl_confirmations)
        form.addRow("القاعدة المستخدمة:", self.lbl_rule)
        form.addRow("تعارض:", self.lbl_conflict)
        form.addRow("مصدر التفضيل:", self.lbl_source)
        layout.addWidget(suggestion_box)

        # ─── أزرار القرار (تعلم فقط — لا ملفات) ──────────────────────────
        decision_bar = QHBoxLayout()
        self.btn_accept = QPushButton("✓ قبول (تأكيد القاعدة)")
        self.btn_accept.setToolTip("يسجّل قبولك للاقتراح كتأكيد مستقل — لا نقل ملف")
        self.btn_reject = QPushButton("✗ رفض (بلا تعلم)")
        self.btn_reject.setToolTip("يرفض الاقتراح ولا يولّد أي قاعدة تعلم")
        self.btn_correct = QPushButton("✎ تصحيح (مرشح للمراجعة)")
        self.btn_correct.setToolTip("ينشئ مرشحًا يُطبَّق بعد موافقتك الصريحة")
        for btn in (self.btn_accept, self.btn_reject, self.btn_correct):
            btn.setEnabled(False)
            decision_bar.addWidget(btn)
        decision_bar.addStretch(1)
        layout.addLayout(decision_bar)

        self.btn_accept.clicked.connect(self._on_accept)
        self.btn_reject.clicked.connect(self._on_reject)
        self.btn_correct.clicked.connect(self._on_correct)

        # ─── جدول القواعد ────────────────────────────────────────────────
        rules_box = QGroupBox("القواعد المكتسبة")
        rules_layout = QVBoxLayout(rules_box)
        self.rules_table = QTableWidget(0, 7)
        self.rules_table.setHorizontalHeaderLabels([
            "الحالة", "المطابقة", "النطاق", "الوجهة",
            "تأكيدات مستقلة", "تعارضات", "المصدر",
        ])
        self.rules_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents)
        self.rules_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rules_table.setEditTriggers(QTableWidget.NoEditTriggers)
        rules_layout.addWidget(self.rules_table)

        rule_bar = QHBoxLayout()
        self.btn_disable = QPushButton("⏸ تعطيل القاعدة المحددة")
        self.btn_enable = QPushButton("▶ تفعيل القاعدة المحددة")
        self.btn_delete = QPushButton("🗑 حذف القاعدة المحددة")
        self.btn_undo_learning = QPushButton("↩ تراجع عن آخر تعلم")
        for btn in (self.btn_disable, self.btn_enable, self.btn_delete,
                    self.btn_undo_learning):
            rule_bar.addWidget(btn)
        rule_bar.addStretch(1)
        rules_layout.addLayout(rule_bar)
        layout.addWidget(rules_box)

        self.btn_disable.clicked.connect(self._on_disable)
        self.btn_enable.clicked.connect(self._on_enable)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_undo_learning.clicked.connect(self._on_undo_learning)

        self.refresh()

    # ─── الحقن والعرض ───────────────────────────────────────────────────────

    def set_engines(self, engine: PreferenceEngine,
                    feedback: FeedbackEngine | None = None) -> None:
        self.engine = engine
        self.feedback = feedback
        self.refresh()

    def set_suggestion(self, suggestion: dict | None) -> None:
        """يعرض اقتراحًا من طبقة classifier_preferences (preference layer)."""
        self._current_suggestion = suggestion
        active = bool(suggestion and suggestion.get("active"))
        has = active and suggestion.get("suggested_category")
        self.lbl_original.setText(str(suggestion.get("original_category", "—"))
                                  if suggestion else "—")
        self.lbl_suggested.setText(str(suggestion.get("suggested_category")) if has else "—")
        self.lbl_reason.setText(str(suggestion.get("reason", "—")) if suggestion else "—")
        self.lbl_confidence.setText(str(suggestion.get("confidence_score", "—"))
                                    if has else "—")
        self.lbl_confirmations.setText(str(suggestion.get("independent_confirmations", "—"))
                                       if has else "—")
        self.lbl_rule.setText(str(suggestion.get("rule_id", "—"))[:16] if has else "—")
        if has and suggestion.get("conflicts"):
            self.lbl_conflict.setText(f"نعم ({len(suggestion['conflicts'])})")
        else:
            self.lbl_conflict.setText("لا" if has else "—")
        self.lbl_source.setText(str(suggestion.get("source", "—")) if has else "—")
        for btn in (self.btn_accept, self.btn_reject):
            btn.setEnabled(bool(has) and self.engine is not None and self.engine.active)
        self.btn_correct.setEnabled(
            bool(has) and self.feedback is not None and self.engine is not None
            and self.engine.active)

    def refresh(self) -> None:
        rules = self.engine.list_rules() if self.engine and self.engine.active else []
        self.rules_table.setRowCount(len(rules))
        for row, rule in enumerate(rules):
            match = rule["match"]
            scope = rule["scope"]
            conf = rule["confidence"]
            values = [
                _STATUS_AR.get(rule["status"], rule["status"]),
                f"{match['kind']}={match['value']}",
                scope["kind"] if scope["value"] is None
                else f"{scope['kind']}={scope['value']}",
                rule["destination"]["category"],
                str(conf["independent_sessions"]),
                str(len(rule.get("conflicts", []))),
                rule.get("source", {}).get("origin", ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.rules_table.setItem(row, col, item)

    # ─── قرارات التعلم (بلا ملفات) ──────────────────────────────────────────

    def _selected_rule_id(self) -> str | None:  # noqa: F811 — خاصية بسيطة
        row = self.rules_table.currentRow()
        if row < 0 or self.engine is None:
            return None
        rules = self.engine.list_rules()
        if row >= len(rules):
            return None
        return rules[row]["rule_id"]

    def _on_accept(self) -> None:
        """قبول الاقتراح = تأكيد مستقل للقاعدة — لا نقل ملف."""
        if not (self.engine and self._current_suggestion):
            return
        rule_id = self._current_suggestion.get("rule_id")
        if not rule_id:
            return
        self.engine.confirm_rule(rule_id, session_id="desktop-ui",
                                 file_fingerprint="desktop-accept")
        self.refresh()
        self.learning_changed.emit()

    def _on_reject(self) -> None:
        """رفض الاقتراح — يسجل feedback فقط، لا قاعدة تعلم."""
        if self.feedback is None or not self._current_suggestion:
            return
        self.feedback.capture(
            user_action="reject",
            original_prediction=self._current_suggestion.get("original_category", ""),
            session_id="desktop-ui",
            file_fingerprint="desktop-reject",
            source_rule_id=self._current_suggestion.get("rule_id"),
        )
        self.learning_changed.emit()

    def _on_correct(self) -> None:
        """تصحيح — يفتح حوار قيمة، ينشئ مرشحًا بانتظار موافقة صريحة."""
        if not (self.engine and self.feedback and self._current_suggestion):
            return
        from PySide6.QtWidgets import QInputDialog
        category, ok = QInputDialog.getText(
            self, "تصحيح التصنيف",
            "التصنيف الصحيح (سيُطبَّق بعد موافقتك الصريحة):")
        if not ok or not category.strip():
            return
        self.feedback.capture(
            user_action="correct",
            original_prediction=self._current_suggestion.get("original_category", ""),
            session_id="desktop-ui",
            file_fingerprint="desktop-correct",
            corrected_value=category.strip(),
            source_rule_id=self._current_suggestion.get("rule_id"),
        )
        self.learning_changed.emit()

    # ─── إدارة القواعد ──────────────────────────────────────────────────────

    def _on_disable(self) -> None:
        rule_id = self._selected_rule_id()
        if rule_id and self.engine:
            self.engine.disable_rule(rule_id)
            self.refresh()
            self.learning_changed.emit()

    def _on_enable(self) -> None:
        rule_id = self._selected_rule_id()
        if rule_id and self.engine:
            self.engine.enable_rule(rule_id)
            self.refresh()
            self.learning_changed.emit()

    def _on_delete(self) -> None:
        rule_id = self._selected_rule_id()
        if not (rule_id and self.engine):
            return
        answer = QMessageBox.question(
            self, "حذف القاعدة",
            "حذف منطقي قابل للتراجع — متابعة؟",
            QMessageBox.Yes | QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.engine.delete_rule(rule_id)
            self.refresh()
            self.learning_changed.emit()

    def _on_undo_learning(self) -> None:
        if self.engine and self.engine.active:
            self.engine.revert_last_update()
            self.refresh()
            self.learning_changed.emit()
