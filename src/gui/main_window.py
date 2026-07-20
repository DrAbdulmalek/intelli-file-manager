# -*- coding: utf-8 -*-
"""
IntelliFile - واجهة المستخدم الرسومية الرئيسية
Main GUI window for the AI-powered file classification application.

Requires: PySide6
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QCoreApplication,
    QDir,
    QFileInfo,
    QFileSystemModel,
    QModelIndex,
    QSettings,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QKeySequence,
    QUrl,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QTextBrowser,
    QToolBar,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Core module imports – gracefully degrade when optional deps are missing
# ---------------------------------------------------------------------------
try:
    from src.core.config import Config, CATEGORIES
    from src.core.classifier import SmartFileClassifier
    from src.core.file_handler import FileHandler
    from src.core.ai_engine import AIEngine
    from src.core.semantic_search import SemanticSearchEngine
    from src.core.voice_controller import VoiceController
    from src.core.rag_engine import RAGEngine
except ImportError:
    # Allow running the file standalone for layout previews
    Config = None
    CATEGORIES = [
        "مستندات", "صور", "فيديو", "صوت",
        "أرشيفات", "برمجة", "أنظمة", "خطوط", "أخرى",
    ]
    SmartFileClassifier = None
    FileHandler = None
    AIEngine = None
    SemanticSearchEngine = None
    VoiceController = None
    RAGEngine = None

logger = logging.getLogger("intellifile.gui")


# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

# Unicode icons used when system icons are unavailable
_ICONS = {
    "files": "\U0001F4C1",
    "search": "\U0001F50D",
    "assistant": "\U0001F916",
    "dashboard": "\U0001F4CA",
    "settings": "\u2699",
    "dark": "\U0001F319",
    "light": "\u2600",
    "classify": "\U0001F4C4",
    "voice": "\U0001F3A4",
    "undo": "\u21A9",
    "redo": "\u21AA",
    "delete": "\U0001F5D1",
    "refresh": "\U0001F504",
    "open": "\U0001F4C2",
    "about": "\u2139",
    "quit": "\U0001F6AA",
    "copy": "\U0001F4CB",
    "rename": "\u270F",
}

# Sidebar page indices
_PAGE_FILE_MANAGER = 0
_PAGE_SEMANTIC_SEARCH = 1
_PAGE_ASSISTANT = 2
_PAGE_DASHBOARD = 3
_PAGE_SETTINGS = 4

# Category display colours (hex)
_CATEGORY_COLORS = {
    "مستندات": "#4A90D9",
    "صور": "#7B68EE",
    "فيديو": "#E74C3C",
    "صوت": "#F39C12",
    "أرشيفات": "#27AE60",
    "برمجة": "#1ABC9C",
    "أنظمة": "#95A5A6",
    "خطوط": "#E67E22",
    "أخرى": "#BDC3C7",
}

_ORG_NAME = "IntelliFile"
_APP_NAME = "IntelliFile"


# ═══════════════════════════════════════════════════════════════════════════
#  STYLESHEETS
# ═══════════════════════════════════════════════════════════════════════════

_DARK_STYLE = """
QMainWindow, QDialog {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', 'Noto Sans Arabic', 'Arial', sans-serif;
    font-size: 13px;
}
QMenuBar {
    background-color: #181825;
    color: #cdd6f4;
    border-bottom: 1px solid #313244;
    padding: 2px;
}
QMenuBar::item {
    padding: 6px 16px;
    background: transparent;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #313244;
}
QMenu {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 32px 6px 16px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #313244;
}
QMenu::separator {
    height: 1px;
    background: #313244;
    margin: 4px 8px;
}
QToolBar {
    background-color: #181825;
    border-bottom: 1px solid #313244;
    padding: 4px;
    spacing: 4px;
}
QStatusBar {
    background-color: #181825;
    color: #a6adc8;
    border-top: 1px solid #313244;
    padding: 2px;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 18px;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #45475a;
    border-color: #585b70;
}
QPushButton:pressed {
    background-color: #585b70;
}
QPushButton:disabled {
    background-color: #1e1e2e;
    color: #585b70;
    border-color: #313244;
}
QPushButton#accentBtn {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    font-weight: bold;
}
QPushButton#accentBtn:hover {
    background-color: #b4d0fb;
}
QLineEdit, QTextEdit, QTextBrowser, QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #585b70;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border-color: #89b4fa;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #cdd6f4;
    margin-right: 6px;
}
QTreeView, QListView, QListWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    alternate-background-color: #181825;
}
QTreeView::item, QListView::item, QListWidget::item {
    padding: 4px;
    border-radius: 3px;
}
QTreeView::item:selected, QListWidget::item:selected {
    background-color: #313244;
    color: #89b4fa;
}
QHeaderView::section {
    background-color: #181825;
    color: #a6adc8;
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #313244;
    font-weight: bold;
}
QTabWidget::pane {
    border: 1px solid #313244;
    border-radius: 6px;
    background-color: #1e1e2e;
}
QTabBar::tab {
    background-color: #181825;
    color: #a6adc8;
    padding: 8px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #1e1e2e;
    color: #89b4fa;
    border-bottom: 2px solid #89b4fa;
}
QProgressBar {
    background-color: #313244;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #cdd6f4;
    min-height: 18px;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 4px;
}
QGroupBox {
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 18px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top right;
    padding: 0 8px;
    color: #89b4fa;
}
QScrollBar:vertical {
    background-color: #1e1e2e;
    width: 10px;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #45475a;
    min-height: 30px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QSplitter::handle {
    background-color: #313244;
    width: 2px;
}
QSplitter::handle:hover {
    background-color: #585b70;
}
QLabel#sectionTitle {
    font-size: 18px;
    font-weight: bold;
    color: #89b4fa;
    padding: 4px 0;
}
QLabel#statValue {
    font-size: 24px;
    font-weight: bold;
    color: #cdd6f4;
}
QLabel#statLabel {
    font-size: 11px;
    color: #a6adc8;
}
"""

_LIGHT_STYLE = """
QMainWindow, QDialog {
    background-color: #eff1f5;
    color: #4c4f69;
}
QWidget {
    background-color: #eff1f5;
    color: #4c4f69;
    font-family: 'Segoe UI', 'Noto Sans Arabic', 'Arial', sans-serif;
    font-size: 13px;
}
QMenuBar {
    background-color: #e6e9ef;
    color: #4c4f69;
    border-bottom: 1px solid #ccd0da;
    padding: 2px;
}
QMenuBar::item {
    padding: 6px 16px;
    background: transparent;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #ccd0da;
}
QMenu {
    background-color: #eff1f5;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 32px 6px 16px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #ccd0da;
}
QMenu::separator {
    height: 1px;
    background: #ccd0da;
    margin: 4px 8px;
}
QToolBar {
    background-color: #e6e9ef;
    border-bottom: 1px solid #ccd0da;
    padding: 4px;
    spacing: 4px;
}
QStatusBar {
    background-color: #e6e9ef;
    color: #6c6f85;
    border-top: 1px solid #ccd0da;
    padding: 2px;
}
QPushButton {
    background-color: #ccd0da;
    color: #4c4f69;
    border: 1px solid #bcc0cc;
    border-radius: 6px;
    padding: 6px 18px;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #bcc0cc;
}
QPushButton:pressed {
    background-color: #acb0be;
}
QPushButton:disabled {
    background-color: #eff1f5;
    color: #bcc0cc;
}
QPushButton#accentBtn {
    background-color: #1e66f5;
    color: #ffffff;
    border: none;
    font-weight: bold;
}
QPushButton#accentBtn:hover {
    background-color: #4788e0;
}
QLineEdit, QTextEdit, QTextBrowser, QComboBox {
    background-color: #ffffff;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #ccd0da;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border-color: #1e66f5;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #4c4f69;
    margin-right: 6px;
}
QTreeView, QListView, QListWidget {
    background-color: #ffffff;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    alternate-background-color: #eff1f5;
}
QTreeView::item, QListView::item, QListWidget::item {
    padding: 4px;
    border-radius: 3px;
}
QTreeView::item:selected, QListWidget::item:selected {
    background-color: #ccd0da;
    color: #1e66f5;
}
QHeaderView::section {
    background-color: #e6e9ef;
    color: #6c6f85;
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #ccd0da;
    font-weight: bold;
}
QTabWidget::pane {
    border: 1px solid #ccd0da;
    border-radius: 6px;
    background-color: #ffffff;
}
QTabBar::tab {
    background-color: #e6e9ef;
    color: #6c6f85;
    padding: 8px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #1e66f5;
    border-bottom: 2px solid #1e66f5;
}
QProgressBar {
    background-color: #ccd0da;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #4c4f69;
    min-height: 18px;
}
QProgressBar::chunk {
    background-color: #1e66f5;
    border-radius: 4px;
}
QGroupBox {
    border: 1px solid #ccd0da;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 18px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top right;
    padding: 0 8px;
    color: #1e66f5;
}
QScrollBar:vertical {
    background-color: #eff1f5;
    width: 10px;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #bcc0cc;
    min-height: 30px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background-color: #acb0be;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QSplitter::handle {
    background-color: #ccd0da;
    width: 2px;
}
QSplitter::handle:hover {
    background-color: #acb0be;
}
QLabel#sectionTitle {
    font-size: 18px;
    font-weight: bold;
    color: #1e66f5;
    padding: 4px 0;
}
QLabel#statValue {
    font-size: 24px;
    font-weight: bold;
    color: #4c4f69;
}
QLabel#statLabel {
    font-size: 11px;
    color: #6c6f85;
}
"""


# ═══════════════════════════════════════════════════════════════════════════
#  WORKER THREADS
# ═══════════════════════════════════════════════════════════════════════════

class ClassifyWorker(QThread):
    """Background thread for batch file classification."""

    progress = Signal(int, int)          # current, total
    result_ready = Signal(list)          # list[dict]
    error_occurred = Signal(str)

    def __init__(self, classifier: "SmartFileClassifier", directory: str,
                 parent=None):
        super().__init__(parent)
        self._classifier = classifier
        self._directory = directory
        self._abort = False

    def run(self) -> None:
        try:
            from pathlib import Path
            results = []
            dir_path = Path(self._directory)
            files = [
                f for f in dir_path.rglob("*")
                if f.is_file() and not f.name.startswith(".")
            ]
            total = len(files)
            for i, item in enumerate(files):
                if self._abort:
                    break
                try:
                    r = self._classifier.classify_file(str(item))
                    if "error" not in r:
                        results.append(r)
                except Exception:
                    continue
                self.progress.emit(i + 1, total)
            self.result_ready.emit(results)
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def abort(self) -> None:
        self._abort = True


class SearchWorker(QThread):
    """Background thread for semantic search indexing / querying."""

    index_progress = Signal(int)         # files indexed
    search_done = Signal(list)           # List[Tuple[str, float]]
    error_occurred = Signal(str)

    def __init__(self, engine: "SemanticSearchEngine", parent=None):
        super().__init__(parent)
        self._engine = engine
        self._mode = "index"             # "index" | "search"
        self._directory: str = ""
        self._query: str = ""
        self._top_k: int = 10
        self._abort = False

    def run(self) -> None:
        try:
            if self._mode == "index":
                count = self._engine.index_files(self._directory)
                self.index_progress.emit(count)
            elif self._mode == "search":
                results = self._engine.search(self._query, self._top_k)
                self.search_done.emit(results)
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def abort(self) -> None:
        self._abort = True


class SummarizeWorker(QThread):
    """Background thread for AI file summarization."""

    result_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, ai_engine: "AIEngine", filepath: str, parent=None):
        super().__init__(parent)
        self._ai = ai_engine
        self._filepath = filepath

    def run(self) -> None:
        try:
            text = self._ai.summarize_file(self._filepath)
            self.result_ready.emit(text)
        except Exception as exc:
            self.error_occurred.emit(str(exc))


class ChatWorker(QThread):
    """Background thread for AI chat / assistant queries."""

    response_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, ai_engine: "AIEngine", message: str,
                 context: str = "", parent=None):
        super().__init__(parent)
        self._ai = ai_engine
        self._message = message
        self._context = context

    def run(self) -> None:
        try:
            reply = self._ai.chat(self._message, self._context)
            self.response_ready.emit(reply)
        except Exception as exc:
            self.error_occurred.emit(str(exc))


class VoiceWorker(QThread):
    """Background thread for voice recognition."""

    command_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, voice: "VoiceController", timeout: int = 10,
                 parent=None):
        super().__init__(parent)
        self._voice = voice
        self._timeout = timeout

    def run(self) -> None:
        try:
            text = self._voice.listen(self._timeout)
            if text:
                cmd = self._voice.parse_command(text)
                self.command_ready.emit(cmd)
        except Exception as exc:
            self.error_occurred.emit(str(exc))


class RAGWorker(QThread):
    """Background thread for RAG queries."""

    result_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, rag: "RAGEngine", question: str, parent=None):
        super().__init__(parent)
        self._rag = rag
        self._question = question

    def run(self) -> None:
        try:
            answer = self._rag.query(self._question)
            self.result_ready.emit(answer)
        except Exception as exc:
            self.error_occurred.emit(str(exc))


# ═══════════════════════════════════════════════════════════════════════════
#  PANEL WIDGETS
# ═══════════════════════════════════════════════════════════════════════════

class _BasePanel(QWidget):
    """Base class shared by all sidebar pages."""

    # Emitted when the panel wants to update the status bar
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)


# ───────────────────────────────────────────────────────────────────────────
#  1. File Manager Panel
# ───────────────────────────────────────────────────────────────────────────

class FileManagerPanel(_BasePanel):
    """مدير الملفات – File browsing, classification, and operations."""

    classify_requested = Signal(str)           # directory path
    file_selected = Signal(str)               # file path

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self._config = config

        # --- Title row ---
        title = QLabel(_ICONS["files"] + "  مدير الملفات")
        title.setObjectName("sectionTitle")
        self._layout.addWidget(title)

        # --- Toolbar row ---
        toolbar = QHBoxLayout()
        self._btn_open = QPushButton(_ICONS["open"] + "  فتح مجلد")
        self._btn_open.setObjectName("accentBtn")
        self._btn_open.clicked.connect(self._open_directory)
        toolbar.addWidget(self._btn_open)

        self._btn_classify = QPushButton(_ICONS["classify"] + "  تصنيف")
        self._btn_classify.clicked.connect(self._classify_directory)
        self._btn_classify.setEnabled(False)
        toolbar.addWidget(self._btn_classify)

        self._btn_undo = QPushButton(_ICONS["undo"] + "  تراجع")
        self._btn_undo.clicked.connect(self._undo_action)
        toolbar.addWidget(self._btn_undo)

        toolbar.addStretch()
        self._layout.addLayout(toolbar)

        # --- Progress ---
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._layout.addWidget(self._progress)

        # --- Splitter: tree + details ---
        self._splitter = QSplitter(Qt.Horizontal)
        self._layout.addWidget(self._splitter, stretch=1)

        # File tree (left)
        self._fs_model = QFileSystemModel()
        self._fs_model.setRootPath(QDir.rootPath())
        self._fs_model.setFilter(
            QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot
        )
        self._tree = QTreeView()
        self._tree.setModel(self._fs_model)
        self._tree.setAnimated(True)
        self._tree.setIndentation(20)
        self._tree.setSortingEnabled(True)
        self._tree.header().setStretchLastSection(True)
        self._tree.header().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        for col in range(1, 4):
            self._tree.header().hideSection(col)
        self._tree.clicked.connect(self._on_tree_clicked)
        self._tree.doubleClicked.connect(self._on_tree_double_clicked)
        self._splitter.addWidget(self._tree)

        # Right panel – file details / classification results
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self._details_label = QLabel("اختر ملفاً لعرض التفاصيل")
        self._details_label.setWordWrap(True)
        self._details_label.setAlignment(Qt.AlignTop)
        self._details_label.setTextFormat(Qt.RichText)
        right_layout.addWidget(self._details_label)

        # Classification results list
        self._results_list = QListWidget()
        self._results_list.itemClicked.connect(self._on_result_clicked)
        right_layout.addWidget(self._results_list, stretch=1)

        self._splitter.addWidget(right_container)
        self._splitter.setSizes([350, 450])

        # Worker reference
        self._classify_worker: Optional[ClassifyWorker] = None
        self._current_dir: Optional[str] = None

    # ── Public helpers ──────────────────────────────────────────────────

    def get_selected_file(self) -> str:
        """Return the path of the currently selected file, or ''."""
        idx = self._tree.currentIndex()
        if idx.isValid():
            return self._fs_model.filePath(idx)
        return ""

    def set_root_path(self, path: str) -> None:
        self._tree.setRootIndex(self._fs_model.index(path))

    def populate_results(self, results: list) -> None:
        """Populate the results list with classification data."""
        self._results_list.clear()
        for r in results:
            cat = r.get("category", "أخرى")
            color = _CATEGORY_COLORS.get(cat, _CATEGORY_COLORS["أخرى"])
            size = _human_size(r.get("size", 0))
            conf = r.get("confidence", 0)
            text = (
                f'<span style="color:{color};">●</span> '
                f'<b>{r.get("name", "")}</b>  '
                f'<span style="color:#a6adc8;">| {cat} | {size} | '
                f'{conf:.0f}%</span>'
            )
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, r.get("path", ""))
            self._results_list.addItem(item)
        self.status_message.emit(
            f"تم تصنيف {len(results)} ملف بنجاح"
        )

    # ── Slots ───────────────────────────────────────────────────────────

    def _open_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "اختر مجلداً", QDir.homePath()
        )
        if path:
            self._current_dir = path
            self.set_root_path(path)
            self._btn_classify.setEnabled(True)
            self.status_message.emit(f"المجلد: {path}")

    def _classify_directory(self) -> None:
        if not self._current_dir:
            QMessageBox.warning(self, "تحذير", "اختر مجلداً أولاً")
            return
        self.classify_requested.emit(self._current_dir)
        self._btn_classify.setEnabled(False)
        self._btn_open.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)

    def start_classification(
        self, classifier: "SmartFileClassifier"
    ) -> None:
        """Kick off a background classification run."""
        self._classify_worker = ClassifyWorker(
            classifier, self._current_dir, parent=self
        )
        self._classify_worker.progress.connect(self._on_classify_progress)
        self._classify_worker.result_ready.connect(self._on_classify_done)
        self._classify_worker.error_occurred.connect(self._on_classify_error)
        self._classify_worker.start()

    def _on_classify_progress(self, current: int, total: int) -> None:
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        self.status_message.emit(
            f"جاري التصنيف... {current}/{total}"
        )

    def _on_classify_done(self, results: list) -> None:
        self._progress.setVisible(False)
        self._btn_classify.setEnabled(True)
        self._btn_open.setEnabled(True)
        self.populate_results(results)

    def _on_classify_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._btn_classify.setEnabled(True)
        self._btn_open.setEnabled(True)
        QMessageBox.critical(self, "خطأ", f"فشل التصنيف:\n{msg}")
        self.status_message.emit("فشل التصنيف")

    def _on_tree_clicked(self, index: QModelIndex) -> None:
        path = self._fs_model.filePath(index)
        info = QFileInfo(path)
        if info.isFile():
            self.file_selected.emit(path)
            ext = info.suffix().lower()
            cat = self._config.get_category(f".{ext}") if ext else "أخرى"
            color = _CATEGORY_COLORS.get(cat, _CATEGORY_COLORS["أخرى"])
            self._details_label.setText(
                f"<h3>{info.fileName()}</h3>"
                f"<p><b>المسار:</b> {info.absolutePath()}</p>"
                f"<p><b>الحجم:</b> {_human_size(info.size())}</p>"
                f"<p><b>التعديل:</b> "
                f"{info.lastModified().toString('yyyy/MM/dd hh:mm')}</p>"
                f'<p><b>التصنيف:</b> <span style="color:{color};">'
                f"{cat}</span></p>"
            )

    def _on_tree_double_clicked(self, index: QModelIndex) -> None:
        path = self._fs_model.filePath(index)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _on_result_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path and Path(path).exists():
            self._tree.setCurrentIndex(self._fs_model.index(path))

    def _undo_action(self) -> None:
        self.status_message.emit("طلب تراجع عن آخر عملية")


# ───────────────────────────────────────────────────────────────────────────
#  2. Semantic Search Panel
# ───────────────────────────────────────────────────────────────────────────

class SemanticSearchPanel(_BasePanel):
    """البحث الدلالي – Semantic search indexing & querying."""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self._config = config

        title = QLabel(_ICONS["search"] + "  البحث الدلالي")
        title.setObjectName("sectionTitle")
        self._layout.addWidget(title)

        # Index controls
        idx_group = QGroupBox("فهرسة الملفات")
        idx_lay = QHBoxLayout(idx_group)
        self._btn_index = QPushButton(_ICONS["classify"] + "  فهرسة مجلد")
        self._btn_index.setObjectName("accentBtn")
        self._btn_index.clicked.connect(self._pick_index_dir)
        idx_lay.addWidget(self._btn_index)

        self._lbl_index_status = QLabel("لم يتم الفهرسة بعد")
        self._lbl_index_status.setWordWrap(True)
        idx_lay.addWidget(self._lbl_index_status, stretch=1)
        self._layout.addWidget(idx_group)

        # Search controls
        search_group = QGroupBox("بحث دلالي")
        search_lay = QHBoxLayout(search_group)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("اكتب استعلام البحث...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.returnPressed.connect(self._do_search)
        search_lay.addWidget(self._search_input)

        self._btn_search = QPushButton(_ICONS["search"] + "  ابحث")
        self._btn_search.clicked.connect(self._do_search)
        search_lay.addWidget(self._btn_search)
        self._layout.addWidget(search_group)

        # Results
        self._results_list = QListWidget()
        self._results_list.itemDoubleClicked.connect(self._open_result)
        self._layout.addWidget(self._results_list, stretch=1)

        # Workers
        self._worker: Optional[SearchWorker] = None

    def _pick_index_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "اختر مجلداً للفهرسة", QDir.homePath()
        )
        if path:
            self._run_index(path)

    def _run_index(self, directory: str) -> None:
        self._lbl_index_status.setText("جاري الفهرسة...")
        self._btn_index.setEnabled(False)
        self.status_message.emit(f"جاري فهرسة: {directory}")
        # The actual engine is provided by MainWindow via start_indexing()
        # For now, emit a signal or call parent
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "start_indexing"):
                parent.start_indexing(directory)
                return
            parent = parent.parent()

    def on_index_done(self, count: int) -> None:
        self._btn_index.setEnabled(True)
        self._lbl_index_status.setText(f"تم فهرسة {count} ملف")
        self.status_message.emit(f"تم فهرسة {count} ملف بنجاح")

    def on_index_error(self, msg: str) -> None:
        self._btn_index.setEnabled(True)
        self._lbl_index_status.setText(f"خطأ: {msg}")
        QMessageBox.critical(self, "خطأ", f"فشلت الفهرسة:\n{msg}")

    def _do_search(self) -> None:
        query = self._search_input.text().strip()
        if not query:
            return
        self._results_list.clear()
        self._btn_search.setEnabled(False)
        self.status_message.emit(f"جاري البحث عن: {query}")
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "start_search"):
                parent.start_search(query)
                return
            parent = parent.parent()

    def on_search_done(self, results: list) -> None:
        self._btn_search.setEnabled(True)
        for filepath, score in results:
            name = Path(filepath).name
            pct = score * 100
            item = QListWidgetItem(
                f"{name}  <span style='color:#a6adc8;'>({pct:.1f}%)</span>"
            )
            item.setData(Qt.UserRole, filepath)
            self._results_list.addItem(item)
        self.status_message.emit(
            f"تم العثور على {len(results)} نتيجة"
        )

    def on_search_error(self, msg: str) -> None:
        self._btn_search.setEnabled(True)
        QMessageBox.critical(self, "خطأ", f"فشل البحث:\n{msg}")

    def _open_result(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))


# ───────────────────────────────────────────────────────────────────────────
#  3. Assistant Panel
# ───────────────────────────────────────────────────────────────────────────

class AssistantPanel(_BasePanel):
    """المساعد الذكي – AI chat, voice, and RAG."""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self._config = config

        title = QLabel(_ICONS["assistant"] + "  المساعد الذكي")
        title.setObjectName("sectionTitle")
        self._layout.addWidget(title)

        # Tabs: Chat | RAG
        self._tabs = QTabWidget()
        self._layout.addWidget(self._tabs, stretch=1)

        # ---- Chat Tab ----
        chat_widget = QWidget()
        chat_lay = QVBoxLayout(chat_widget)
        chat_lay.setContentsMargins(8, 8, 8, 8)

        self._chat_history = QTextBrowser()
        self._chat_history.setOpenLinks(False)
        self._chat_history.setAlignment(Qt.AlignTop)
        chat_lay.addWidget(self._chat_history, stretch=1)

        input_row = QHBoxLayout()
        self._chat_input = QLineEdit()
        self._chat_input.setPlaceholderText("اكتب رسالتك...")
        self._chat_input.returnPressed.connect(self._send_chat)
        input_row.addWidget(self._chat_input, stretch=1)

        self._btn_voice = QPushButton(_ICONS["voice"])
        self._btn_voice.setFixedSize(36, 36)
        self._btn_voice.setToolTip("إدخال صوتي")
        self._btn_voice.setEnabled(config.voice_enabled)
        self._btn_voice.clicked.connect(self._listen_voice)
        input_row.addWidget(self._btn_voice)

        self._btn_send = QPushButton("إرسال")
        self._btn_send.setObjectName("accentBtn")
        self._btn_send.clicked.connect(self._send_chat)
        input_row.addWidget(self._btn_send)
        chat_lay.addLayout(input_row)

        self._tabs.addTab(chat_widget, "محادثة")

        # ---- RAG Tab ----
        rag_widget = QWidget()
        rag_lay = QVBoxLayout(rag_widget)
        rag_lay.setContentsMargins(8, 8, 8, 8)

        rag_input_row = QHBoxLayout()
        self._rag_input = QLineEdit()
        self._rag_input.setPlaceholderText("اسأل سؤالاً عن ملفاتك...")
        self._rag_input.returnPressed.connect(self._ask_rag)
        rag_input_row.addWidget(self._rag_input, stretch=1)

        self._btn_rag = QPushButton(_ICONS["search"] + "  اسأل")
        self._btn_rag.setObjectName("accentBtn")
        self._btn_rag.clicked.connect(self._ask_rag)
        rag_input_row.addWidget(self._btn_rag)
        rag_lay.addLayout(rag_input_row)

        self._rag_output = QTextBrowser()
        self._rag_output.setAlignment(Qt.AlignTop)
        rag_lay.addWidget(self._rag_output, stretch=1)

        self._tabs.addTab(rag_widget, "أسئلة الملفات")

        # Worker refs
        self._chat_worker: Optional[ChatWorker] = None
        self._rag_worker: Optional[RAGWorker] = None
        self._voice_worker: Optional[VoiceWorker] = None

        # Welcome message
        self._chat_history.append(
            '<div style="direction:rtl; color:#89b4fa;">'
            '<b>مرحباً! أنا مساعد IntelliFile الذكي.</b><br>'
            "يمكنني مساعدتك في تلخيص الملفات، التصنيف، والبحث. "
            "اكتب رسالتك أو استخدم الصوت."
            "</div>"
        )

    # ── Chat ────────────────────────────────────────────────────────────

    def _send_chat(self) -> None:
        text = self._chat_input.text().strip()
        if not text:
            return
        self._chat_input.clear()
        self._append_chat("أنت", text, "#cdd6f4")
        self._btn_send.setEnabled(False)
        self.status_message.emit("المساعد يفكر...")
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "start_chat"):
                parent.start_chat(text)
                return
            parent = parent.parent()

    def on_chat_response(self, reply: str) -> None:
        self._btn_send.setEnabled(True)
        self._append_chat("المساعد", reply, "#89b4fa")
        self.status_message.emit("جاهز")

    def on_chat_error(self, msg: str) -> None:
        self._btn_send.setEnabled(True)
        self._append_chat("خطأ", msg, "#f38ba8")
        self.status_message.emit("خطأ في المساعد")

    # ── Voice ───────────────────────────────────────────────────────────

    def _listen_voice(self) -> None:
        self._btn_voice.setEnabled(False)
        self._btn_voice.setText("...")
        self.status_message.emit("جاري الاستماع...")
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "start_voice"):
                parent.start_voice()
                return
            parent = parent.parent()

    def on_voice_command(self, cmd: dict) -> None:
        self._btn_voice.setEnabled(self._config.voice_enabled)
        self._btn_voice.setText(_ICONS["voice"])
        action = cmd.get("action", "")
        params = cmd.get("params", "")
        display = f"{action}"
        if params:
            display += f": {params}"
        self._append_chat("صوت", display, "#f9e2af")
        # Auto-fill chat input for chat actions
        if action == "chat" and params:
            self._chat_input.setText(params)

    def on_voice_error(self, msg: str) -> None:
        self._btn_voice.setEnabled(self._config.voice_enabled)
        self._btn_voice.setText(_ICONS["voice"])
        self.status_message.emit(f"خطأ صوتي: {msg}")

    # ── RAG ─────────────────────────────────────────────────────────────

    def _ask_rag(self) -> None:
        question = self._rag_input.text().strip()
        if not question:
            return
        self._rag_input.clear()
        self._rag_output.append(
            f'<div style="direction:rtl;">'
            f'<b style="color:#cdd6f4;">أنت:</b> {question}</div>'
        )
        self._btn_rag.setEnabled(False)
        self.status_message.emit("جاري البحث في قاعدة المعرفة...")
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "start_rag"):
                parent.start_rag(question)
                return
            parent = parent.parent()

    def on_rag_response(self, answer: str) -> None:
        self._btn_rag.setEnabled(True)
        self._rag_output.append(
            f'<div style="direction:rtl;">'
            f'<b style="color:#89b4fa;">IntelliFile:</b> {answer}</div>'
        )
        self.status_message.emit("جاهز")

    def on_rag_error(self, msg: str) -> None:
        self._btn_rag.setEnabled(True)
        self._rag_output.append(
            f'<div style="direction:rtl; color:#f38ba8;">خطأ: {msg}</div>'
        )
        self.status_message.emit("خطأ في RAG")

    # ── Helpers ─────────────────────────────────────────────────────────

    def _append_chat(self, sender: str, text: str, color: str) -> None:
        safe_text = text.replace("<", "&lt;").replace(">", "&gt;")
        self._chat_history.append(
            f'<div style="direction:rtl;">'
            f'<b style="color:{color};">{sender}:</b> '
            f"{safe_text}</div>"
        )
        self._chat_history.verticalScrollBar().setValue(
            self._chat_history.verticalScrollBar().maximum()
        )


# ───────────────────────────────────────────────────────────────────────────
#  4. Dashboard Panel
# ───────────────────────────────────────────────────────────────────────────

class DashboardPanel(_BasePanel):
    """لوحة المعلومات – Statistics overview and system health."""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self._config = config

        title = QLabel(_ICONS["dashboard"] + "  لوحة المعلومات")
        title.setObjectName("sectionTitle")
        self._layout.addWidget(title)

        # Stats grid
        self._stats_grid = QGridLayout()
        self._stats_grid.setSpacing(12)
        self._layout.addLayout(self._stats_grid)

        # Add stat cards
        self._stat_cards: dict[str, QLabel] = {}
        card_defs = [
            ("total_files", "إجمالي الملفات", "0"),
            ("classified", "تم تصنيفها", "0"),
            ("categories", "التصنيفات", str(len(config.categories))),
            ("ai_status", "حالة الذكاء الاصطناعي", "غير متصل"),
            ("search_index", "فهرس البحث", "فارغ"),
            ("disk_usage", "حجم البيانات", "0 B"),
        ]
        for i, (key, label, default) in enumerate(card_defs):
            card = self._make_stat_card(key, label, default)
            self._stats_grid.addWidget(card, i // 3, i % 3)
            self._stat_cards[key] = card.findChild(
                QLabel, "statValue"
            )

        # Category breakdown
        self._cat_group = QGroupBox("توزيع التصنيفات")
        self._cat_lay = QVBoxLayout(self._cat_group)
        self._cat_list = QListWidget()
        self._cat_lay.addWidget(self._cat_list)
        self._layout.addWidget(self._cat_group, stretch=1)

        # Refresh button
        self._btn_refresh = QPushButton(_ICONS["refresh"] + "  تحديث")
        self._btn_refresh.clicked.connect(
            lambda: self.status_message.emit("تم تحديث اللوحة")
        )
        self._layout.addWidget(self._btn_refresh, alignment=Qt.AlignLeft)

    def _make_stat_card(self, key: str, label: str, value: str) -> QWidget:
        card = QWidget()
        card.setObjectName("statCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setAlignment(Qt.AlignCenter)

        val_label = QLabel(value)
        val_label.setObjectName("statValue")
        val_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(val_label)

        lbl = QLabel(label)
        lbl.setObjectName("statLabel")
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl)

        return card

    def update_stats(self, stats: dict) -> None:
        """Update the dashboard with classification statistics."""
        total = stats.get("total_files", 0)
        classified = stats.get("classified", 0)
        cat_dist = stats.get("category_distribution", {})

        if "total_files" in self._stat_cards:
            self._stat_cards["total_files"].setText(str(total))
        if "classified" in self._stat_cards:
            self._stat_cards["classified"].setText(str(classified))

        # Category breakdown
        self._cat_list.clear()
        for cat, count in cat_dist.items():
            color = _CATEGORY_COLORS.get(cat, _CATEGORY_COLORS["أخرى"])
            item = QListWidgetItem(
                f'<span style="color:{color};">●</span> '
                f"<b>{cat}</b>: {count}"
            )
            self._cat_list.addItem(item)

    def update_ai_status(self, running: bool) -> None:
        if "ai_status" in self._stat_cards:
            self._stat_cards["ai_status"].setText(
                "متصل ✓" if running else "غير متصل ✗"
            )

    def update_index_status(self, count: int) -> None:
        if "search_index" in self._stat_cards:
            self._stat_cards["search_index"].setText(f"{count} ملف")


# ───────────────────────────────────────────────────────────────────────────
#  5. Settings Panel
# ───────────────────────────────────────────────────────────────────────────

class SettingsPanel(_BasePanel):
    """الإعدادات – Application configuration."""

    settings_changed = Signal()

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self._config = config

        title = QLabel(_ICONS["settings"] + "  الإعدادات")
        title.setObjectName("sectionTitle")
        self._layout.addWidget(title)

        tabs = QTabWidget()
        self._layout.addWidget(tabs, stretch=1)

        # ---- General Tab ----
        general = QWidget()
        g_lay = QFormLayout(general)
        g_lay.setContentsMargins(16, 16, 16, 16)
        g_lay.setSpacing(14)

        self._cb_dark = QCheckBox("الوضع الداكن")
        self._cb_dark.setChecked(config.dark_mode)
        self._cb_dark.toggled.connect(self._on_dark_toggled)
        g_lay.addRow(self._cb_dark)

        self._cb_auto = QCheckBox("تصنيف تلقائي عند الفتح")
        self._cb_auto.setChecked(config.auto_classify)
        self._cb_auto.toggled.connect(
            lambda v: setattr(config, "auto_classify", v)
        )
        g_lay.addRow(self._cb_auto)

        self._cb_dup = QCheckBox("كشف الملفات المكررة")
        self._cb_dup.setChecked(config.duplicate_detection)
        self._cb_dup.toggled.connect(
            lambda v: setattr(config, "duplicate_detection", v)
        )
        g_lay.addRow(self._cb_dup)

        self._cb_protect = QCheckBox("حماية الملفات")
        self._cb_protect.setChecked(config.file_protection)
        self._cb_protect.toggled.connect(
            lambda v: setattr(config, "file_protection", v)
        )
        g_lay.addRow(self._cb_protect)

        self._cb_voice = QCheckBox("تفعيل التحكم الصوتي")
        self._cb_voice.setChecked(config.voice_enabled)
        self._cb_voice.toggled.connect(self._on_voice_toggled)
        g_lay.addRow(self._cb_voice)

        self._combo_lang = QComboBox()
        self._combo_lang.addItems(["العربية", "English"])
        self._combo_lang.setCurrentIndex(
            0 if config.language == "ar" else 1
        )
        g_lay.addRow("اللغة:", self._combo_lang)

        self._edit_db = QLineEdit(config.database_path)
        self._edit_db.setReadOnly(True)
        db_row = QHBoxLayout()
        db_row.addWidget(self._edit_db)
        btn_db = QPushButton("تصفح...")
        btn_db.clicked.connect(self._browse_db_path)
        db_row.addWidget(btn_db)
        g_lay.addRow("مجلد البيانات:", db_row)

        tabs.addTab(general, "عام")

        # ---- AI Tab ----
        ai_widget = QWidget()
        ai_lay = QFormLayout(ai_widget)
        ai_lay.setContentsMargins(16, 16, 16, 16)
        ai_lay.setSpacing(14)

        self._edit_ollama = QLineEdit(config.ollama_url)
        ai_lay.addRow("رابط Ollama:", self._edit_ollama)

        self._combo_model = QComboBox()
        self._combo_model.setEditable(True)
        self._combo_model.setCurrentText(config.ai_model)
        ai_lay.addRow("نموذج AI:", self._combo_model)

        self._btn_test_ai = QPushButton("اختبار الاتصال")
        self._btn_test_ai.setObjectName("accentBtn")
        self._btn_test_ai.clicked.connect(self._test_ai_connection)
        ai_lay.addRow(self._btn_test_ai)

        self._lbl_ai_status = QLabel("")
        self._lbl_ai_status.setWordWrap(True)
        ai_lay.addRow("", self._lbl_ai_status)

        tabs.addTab(ai_widget, "الذكاء الاصطناعي")

        # ---- Categories Tab ----
        cat_widget = QWidget()
        cat_lay = QVBoxLayout(cat_widget)
        cat_lay.setContentsMargins(16, 16, 16, 16)

        self._cat_list = QListWidget()
        for cat in config.categories:
            self._cat_list.addItem(cat)
        cat_lay.addWidget(self._cat_list, stretch=1)

        add_row = QHBoxLayout()
        self._edit_new_cat = QLineEdit()
        self._edit_new_cat.setPlaceholderText("اسم التصنيف الجديد...")
        add_row.addWidget(self._edit_new_cat, stretch=1)
        btn_add = QPushButton("إضافة")
        btn_add.setObjectName("accentBtn")
        btn_add.clicked.connect(self._add_category)
        add_row.addWidget(btn_add)
        cat_lay.addLayout(add_row)

        tabs.addTab(cat_widget, "التصنيفات")

        # Save button
        self._btn_save = QPushButton("حفظ الإعدادات")
        self._btn_save.setObjectName("accentBtn")
        self._btn_save.setFixedHeight(40)
        self._btn_save.clicked.connect(self._save_settings)
        self._layout.addWidget(self._btn_save)

    # ── Slots ───────────────────────────────────────────────────────────

    def _on_dark_toggled(self, checked: bool) -> None:
        self._config.dark_mode = checked
        self.settings_changed.emit()

    def _on_voice_toggled(self, checked: bool) -> None:
        self._config.voice_enabled = checked
        self.settings_changed.emit()

    def _browse_db_path(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "اختر مجلد البيانات", QDir.homePath()
        )
        if path:
            self._edit_db.setText(path)
            self._config.database_path = path

    def _test_ai_connection(self) -> None:
        self._btn_test_ai.setEnabled(False)
        self._lbl_ai_status.setText("جاري الاختبار...")
        url = self._edit_ollama.text().strip()
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "test_ai_connection"):
                parent.test_ai_connection(url)
                return
            parent = parent.parent()

    def on_ai_test_result(self, running: bool, models: list) -> None:
        self._btn_test_ai.setEnabled(True)
        if running:
            self._lbl_ai_status.setText(
                f'<span style="color:#a6e3a1;">✓ متصل – '
                f"{len(models)} نموذج</span>"
            )
            self._combo_model.clear()
            self._combo_model.addItems(models)
            if self._config.ai_model in models:
                self._combo_model.setCurrentText(self._config.ai_model)
        else:
            self._lbl_ai_status.setText(
                '<span style="color:#f38ba8;">✗ غير متصل</span>'
            )

    def _add_category(self) -> None:
        name = self._edit_new_cat.text().strip()
        if not name:
            return
        if name in self._config.categories:
            QMessageBox.warning(self, "تنبيه", "التصنيف موجود مسبقاً")
            return
        self._config.add_custom_category(name)
        self._cat_list.addItem(name)
        self._edit_new_cat.clear()

    def _save_settings(self) -> None:
        self._config.ai_model = self._combo_model.currentText()
        self._config.ollama_url = self._edit_ollama.text().strip()
        lang_idx = self._combo_lang.currentIndex()
        self._config.language = "ar" if lang_idx == 0 else "en"
        try:
            self._config.save()
            self.settings_changed.emit()
            self.status_message.emit("تم حفظ الإعدادات بنجاح")
            QMessageBox.information(self, "نجاح", "تم حفظ الإعدادات")
        except Exception as exc:
            QMessageBox.critical(
                self, "خطأ", f"فشل حفظ الإعدادات:\n{exc}"
            )


# ═══════════════════════════════════════════════════════════════════════════
#  SIDEBAR WIDGET
# ═══════════════════════════════════════════════════════════════════════════

class _SidebarButton(QPushButton):
    """Custom sidebar navigation button."""

    def __init__(self, icon_text: str, label: str, index: int,
                 parent=None):
        super().__init__(parent)
        self._index = index
        self.setText(f"  {icon_text}   {label}")
        self.setCheckable(True)
        self.setFixedHeight(44)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("navButton", True)


class Sidebar(QWidget):
    """Sidebar navigation panel."""

    page_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(4)

        # Logo / title
        logo = QLabel("IntelliFile")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(
            "font-size: 20px; font-weight: bold; padding: 8px 0;"
        )
        layout.addWidget(logo)

        subtitle = QLabel("تصنيف ذكي للملفات")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(subtitle)

        layout.addSpacing(12)

        # Navigation buttons
        self._buttons: list[_SidebarButton] = []
        nav_items = [
            (_ICONS["files"], "مدير الملفات", _PAGE_FILE_MANAGER),
            (_ICONS["search"], "البحث الدلالي", _PAGE_SEMANTIC_SEARCH),
            (_ICONS["assistant"], "المساعد الذكي", _PAGE_ASSISTANT),
            (_ICONS["dashboard"], "لوحة المعلومات", _PAGE_DASHBOARD),
            (_ICONS["settings"], "الإعدادات", _PAGE_SETTINGS),
        ]
        for icon, label, idx in nav_items:
            btn = _SidebarButton(icon, label, idx)
            btn.clicked.connect(lambda checked, i=idx: self._navigate(i))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()

        # Dark mode toggle at bottom
        self._btn_theme = QPushButton(_ICONS["dark"] + "  الوضع الداكن")
        self._btn_theme.setCheckable(True)
        self._btn_theme.setCursor(Qt.PointingHandCursor)
        self._btn_theme.clicked.connect(
            lambda: self.parent().parent().toggle_dark_mode()
            if self.parent() and self.parent().parent() else None
        )
        layout.addWidget(self._btn_theme)

        # Select the first page
        self._buttons[0].setChecked(True)

    def _navigate(self, index: int) -> None:
        for btn in self._buttons:
            btn.setChecked(btn._index == index)
        self.page_changed.emit(index)

    def set_dark_mode(self, dark: bool) -> None:
        self._btn_theme.setChecked(dark)
        self._btn_theme.setText(
            f"{_ICONS['dark'] if dark else _ICONS['light']}  "
            f"{'الوضع الداكن' if dark else 'الوضع الفاتح'}"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    """IntelliFile main application window."""

    def __init__(self, config: Optional[Config] = None, parent=None):
        super().__init__(parent)

        # --- Configuration ---
        self._config = config or (Config() if Config else None)
        if self._config is None:
            raise RuntimeError("Config is not available")

        # --- Core engines (lazy initialisation) ---
        self._classifier: Optional[SmartFileClassifier] = None
        self._file_handler: Optional[FileHandler] = None
        self._ai_engine: Optional[AIEngine] = None
        self._search_engine: Optional[SemanticSearchEngine] = None
        self._voice_ctrl: Optional[VoiceController] = None
        self._rag_engine: Optional[RAGEngine] = None

        self._init_core_engines()

        # --- Window setup ---
        self.setWindowTitle("IntelliFile – تصنيف ذكي للملفات")
        self.setMinimumSize(QSize(1000, 650))
        self.resize(QSize(1200, 780))

        self._apply_rtl()
        self._apply_dark_mode(self._config.dark_mode)

        # --- Build UI ---
        self._build_menu_bar()
        self._build_toolbar()
        self._build_central()
        self._build_status_bar()

        # --- Restore geometry ---
        self._settings = QSettings(_ORG_NAME, _APP_NAME)
        self._restore_state()

        # --- Timers ---
        self._file_count_timer = QTimer(self)
        self._file_count_timer.timeout.connect(self._update_file_count)
        self._file_count_timer.start(3000)

        # --- Connect sidebar signals ---
        self._sidebar.page_changed.connect(self._switch_page)

        # --- Check AI status on startup ---
        QTimer.singleShot(1000, self._check_ai_status)

        logger.info("تم تهيئة النافذة الرئيسية")

    # ══════════════════════════════════════════════════════════════════════
    #  Core Engine Initialisation
    # ══════════════════════════════════════════════════════════════════════

    def _init_core_engines(self) -> None:
        """Initialise core engines, catching import / connection errors."""
        try:
            if SmartFileClassifier is not None:
                self._classifier = SmartFileClassifier(self._config)
        except Exception as exc:
            logger.warning(f"لم يتم تهيئة المصنف: {exc}")

        try:
            if FileHandler is not None:
                self._file_handler = FileHandler(self._config)
        except Exception as exc:
            logger.warning(f"لم يتم تهيئة مدير الملفات: {exc}")

        try:
            if AIEngine is not None:
                self._ai_engine = AIEngine(self._config)
        except Exception as exc:
            logger.warning(f"لم يتم تهيئة محرك AI: {exc}")

        try:
            if SemanticSearchEngine is not None:
                self._search_engine = SemanticSearchEngine()
        except Exception as exc:
            logger.warning(f"لم يتم تهيئة محرك البحث: {exc}")

        try:
            if VoiceController is not None:
                self._voice_ctrl = VoiceController(
                    command_callback=self._handle_voice_command,
                    language=self._config.language,
                )
        except Exception as exc:
            logger.warning(f"لم يتم تهيئة التحكم الصوتي: {exc}")

        try:
            if RAGEngine is not None:
                self._rag_engine = RAGEngine()
        except Exception as exc:
            logger.warning(f"لم يتم تهيئة محرك RAG: {exc}")

    # ══════════════════════════════════════════════════════════════════════
    #  UI Construction
    # ══════════════════════════════════════════════════════════════════════

    def _apply_rtl(self) -> None:
        """Set RTL layout direction for Arabic."""
        if self._config.language == "ar":
            QCoreApplication.setLayoutDirection(Qt.RightToLeft)
            self.setLayoutDirection(Qt.RightToLeft)
        else:
            QCoreApplication.setLayoutDirection(Qt.LeftToRight)
            self.setLayoutDirection(Qt.LeftToRight)

    def _apply_dark_mode(self, dark: bool) -> None:
        """Apply dark or light theme."""
        self.setStyleSheet(_DARK_STYLE if dark else _LIGHT_STYLE)

    # ── Menu Bar ────────────────────────────────────────────────────────

    def _build_menu_bar(self) -> None:
        menubar = self.menuBar()

        # ملف (File)
        menu_file = menubar.addMenu("ملف")
        self._add_action(
            menu_file, "فتح مجلد", _ICONS["open"],
            QKeySequence.Open, self._on_menu_open
        )
        self._add_action(
            menu_file, "تصنيف المجلد الحالي", _ICONS["classify"],
            QKeySequence("Ctrl+B"), self._on_menu_classify
        )
        menu_file.addSeparator()
        self._add_action(
            menu_file, "حفظ الإعدادات", _ICONS["copy"],
            QKeySequence.Save, self._on_menu_save_config
        )
        menu_file.addSeparator()
        self._add_action(
            menu_file, "خروج", _ICONS["quit"],
            QKeySequence.Quit, self.close
        )

        # تحرير (Edit)
        menu_edit = menubar.addMenu("تحرير")
        self._add_action(
            menu_edit, "تراجع", _ICONS["undo"],
            QKeySequence.Undo, self._on_menu_undo
        )
        self._add_action(
            menu_edit, "إعادة", _ICONS["redo"],
            QKeySequence.Redo, self._on_menu_redo
        )
        menu_edit.addSeparator()
        self._add_action(
            menu_edit, "نسخ المسار", _ICONS["copy"],
            QKeySequence.Copy, self._on_menu_copy_path
        )
        self._add_action(
            menu_edit, "إعادة تسمية", _ICONS["rename"],
            QKeySequence("F2"), self._on_menu_rename
        )
        menu_edit.addSeparator()
        self._add_action(
            menu_edit, "حذف", _ICONS["delete"],
            QKeySequence.Delete, self._on_menu_delete
        )

        # أدوات (Tools)
        menu_tools = menubar.addMenu("أدوات")
        self._add_action(
            menu_tools, "فهرسة الملفات", _ICONS["classify"],
            None, self._on_menu_index
        )
        self._add_action(
            menu_tools, "كشف المكررات", _ICONS["search"],
            None, self._on_menu_duplicates
        )
        menu_tools.addSeparator()
        self._add_action(
            menu_tools, "إنشاء مجلدات التصنيف",
            _ICONS["files"], None, self._on_menu_create_folders
        )
        self._add_action(
            menu_tools, "تبديل الوضع الداكن", _ICONS["dark"],
            QKeySequence("Ctrl+D"), self.toggle_dark_mode
        )

        # مساعدة (Help)
        menu_help = menubar.addMenu("مساعدة")
        self._add_action(
            menu_help, "اختبار اتصال AI", _ICONS["assistant"],
            None, self._on_menu_test_ai
        )
        menu_help.addSeparator()
        self._add_action(
            menu_help, "حول IntelliFile", _ICONS["about"],
            QKeySequence("F1"), self._on_menu_about
        )

    @staticmethod
    def _add_action(
        menu: QMenu, text: str, icon_text: str,
        shortcut: Optional[QKeySequence], slot
    ) -> QAction:
        action = QAction(f"{icon_text}  {text}", menu)
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    # ── Toolbar ─────────────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("شريط الأدوات")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(toolbar)

        btn_open = QToolButton()
        btn_open.setText(_ICONS["open"])
        btn_open.setToolTip("فتح مجلد")
        btn_open.clicked.connect(self._on_menu_open)
        toolbar.addWidget(btn_open)

        btn_classify = QToolButton()
        btn_classify.setText(_ICONS["classify"])
        btn_classify.setToolTip("تصنيف")
        btn_classify.clicked.connect(self._on_menu_classify)
        toolbar.addWidget(btn_classify)

        btn_undo = QToolButton()
        btn_undo.setText(_ICONS["undo"])
        btn_undo.setToolTip("تراجع")
        btn_undo.clicked.connect(self._on_menu_undo)
        toolbar.addWidget(btn_undo)

        toolbar.addSeparator()

        btn_search = QToolButton()
        btn_search.setText(_ICONS["search"])
        btn_search.setToolTip("بحث")
        btn_search.clicked.connect(
            lambda: self._sidebar._navigate(_PAGE_SEMANTIC_SEARCH)
        )
        toolbar.addWidget(btn_search)

        btn_assistant = QToolButton()
        btn_assistant.setText(_ICONS["assistant"])
        btn_assistant.setToolTip("المساعد الذكي")
        btn_assistant.clicked.connect(
            lambda: self._sidebar._navigate(_PAGE_ASSISTANT)
        )
        toolbar.addWidget(btn_assistant)

        toolbar.addSeparator()

        btn_theme = QToolButton()
        btn_theme.setText(_ICONS["dark"])
        btn_theme.setToolTip("تبديل السمة")
        btn_theme.clicked.connect(self.toggle_dark_mode)
        toolbar.addWidget(btn_theme)

    # ── Central Widget ──────────────────────────────────────────────────

    def _build_central(self) -> None:
        """Build the central area with sidebar + stacked panels."""
        central_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(central_splitter)

        # Sidebar
        self._sidebar = Sidebar()
        central_splitter.addWidget(self._sidebar)

        # Stacked pages
        self._stack = QStackedWidget()
        central_splitter.addWidget(self._stack)

        # Create panels
        self._panel_files = FileManagerPanel(self._config)
        self._panel_files.status_message.connect(self._set_status)

        self._panel_search = SemanticSearchPanel(self._config)
        self._panel_search.status_message.connect(self._set_status)

        self._panel_assistant = AssistantPanel(self._config)
        self._panel_assistant.status_message.connect(self._set_status)

        self._panel_dashboard = DashboardPanel(self._config)
        self._panel_dashboard.status_message.connect(self._set_status)

        self._panel_settings = SettingsPanel(self._config)
        self._panel_settings.status_message.connect(self._set_status)
        self._panel_settings.settings_changed.connect(
            self._on_settings_changed
        )

        # Connect file manager signals
        self._panel_files.classify_requested.connect(
            self._on_classify_requested
        )

        self._stack.addWidget(self._panel_files)
        self._stack.addWidget(self._panel_search)
        self._stack.addWidget(self._panel_assistant)
        self._stack.addWidget(self._panel_dashboard)
        self._stack.addWidget(self._panel_settings)

        central_splitter.setStretchFactor(0, 0)
        central_splitter.setStretchFactor(1, 1)

    # ── Status Bar ──────────────────────────────────────────────────────

    def _build_status_bar(self) -> None:
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._lbl_file_count = QLabel("الملفات: 0")
        self._status_bar.addPermanentWidget(self._lbl_file_count)

        self._lbl_operation = QLabel("جاهز")
        self._status_bar.addWidget(self._lbl_operation, stretch=1)

        self._lbl_ai_indicator = QLabel("AI: --")
        self._status_bar.addPermanentWidget(self._lbl_ai_indicator)

    # ══════════════════════════════════════════════════════════════════════
    #  Page Switching
    # ══════════════════════════════════════════════════════════════════════

    @Slot(int)
    def _switch_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        page_names = {
            _PAGE_FILE_MANAGER: "مدير الملفات",
            _PAGE_SEMANTIC_SEARCH: "البحث الدلالي",
            _PAGE_ASSISTANT: "المساعد الذكي",
            _PAGE_DASHBOARD: "لوحة المعلومات",
            _PAGE_SETTINGS: "الإعدادات",
        }
        self._set_status(f"الصفحة: {page_names.get(index, '')}")

    # ══════════════════════════════════════════════════════════════════════
    #  Menu Actions
    # ══════════════════════════════════════════════════════════════════════

    def _on_menu_open(self) -> None:
        self._sidebar._navigate(_PAGE_FILE_MANAGER)
        self._panel_files._open_directory()

    def _on_menu_classify(self) -> None:
        self._sidebar._navigate(_PAGE_FILE_MANAGER)
        self._panel_files._classify_directory()

    def _on_menu_save_config(self) -> None:
        try:
            self._config.save()
            self._set_status("تم حفظ الإعدادات")
        except Exception as exc:
            QMessageBox.critical(
                self, "خطأ", f"فشل الحفظ:\n{exc}"
            )

    def _on_menu_undo(self) -> None:
        if self._file_handler:
            result = self._file_handler.undo_last_action()
            if result["success"]:
                self._set_status("تم التراجع عن آخر عملية")
            else:
                QMessageBox.information(
                    self, "تنبيه", result.get("error", "لا توجد عمليات")
                )

    def _on_menu_redo(self) -> None:
        self._set_status("إعادة – غير متاح حالياً")

    def _on_menu_copy_path(self) -> None:
        path = self._panel_files.get_selected_file()
        if path:
            QApplication.clipboard().setText(path)
            self._set_status(f"تم نسخ المسار: {path}")

    def _on_menu_rename(self) -> None:
        path = self._panel_files.get_selected_file()
        if not path:
            QMessageBox.information(self, "تنبيه", "اختر ملفاً أولاً")
            return
        new_name, ok = self._show_rename_dialog(Path(path).name)
        if ok and new_name:
            if self._file_handler:
                result = self._file_handler.rename_file(path, new_name)
                if result["success"]:
                    self._set_status(f"تم إعادة التسمية: {new_name}")
                else:
                    QMessageBox.critical(
                        self, "خطأ", result.get("error", "فشلت إعادة التسمية")
                    )

    def _on_menu_delete(self) -> None:
        path = self._panel_files.get_selected_file()
        if not path:
            QMessageBox.information(self, "تنبيه", "اختر ملفاً أولاً")
            return
        reply = QMessageBox.question(
            self, "تأكيد الحذف",
            f"هل تريد حذف الملف:\n{path}\n\n"
            "سيتم نقله إلى سلة المحذوفات.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes and self._file_handler:
            result = self._file_handler.delete_file(path)
            if result["success"]:
                self._set_status(f"تم حذف: {Path(path).name}")
            else:
                QMessageBox.critical(
                    self, "خطأ", result.get("error", "فشل الحذف")
                )

    def _on_menu_index(self) -> None:
        self._sidebar._navigate(_PAGE_SEMANTIC_SEARCH)
        self._panel_search._pick_index_dir()

    def _on_menu_duplicates(self) -> None:
        QMessageBox.information(
            self, "كشف المكررات",
            "سيتم فحص المجلد الحالي للبحث عن ملفات مكررة...\n"
            "(قيد التطوير)",
        )

    def _on_menu_create_folders(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "اختر المجلد الأساسي", QDir.homePath()
        )
        if path and self._file_handler:
            try:
                created = self._file_handler.create_category_folders(path)
                QMessageBox.information(
                    self, "نجاح",
                    f"تم إنشاء {len(created)} مجلد تصنيف في:\n{path}"
                )
            except Exception as exc:
                QMessageBox.critical(self, "خطأ", str(exc))

    def _on_menu_test_ai(self) -> None:
        self._check_ai_status()

    def _on_menu_about(self) -> None:
        QMessageBox.about(
            self,
            "حول IntelliFile",
            "<h2>IntelliFile v1.0.0</h2>"
            "<p>تطبيق تصنيف ملفات ذكي بالذكاء الاصطناعي</p>"
            "<p>يدعم التصنيف التلقائي، البحث الدلالي، "
            "المساعد الذكي، والتحكم الصوتي.</p>"
            "<p><b>التقنيات:</b> PySide6, Ollama, ChromaDB, "
            "sentence-transformers</p>"
            "<hr>"
            "<p>مرخص بموجب رخصة MIT</p>",
        )

    # ══════════════════════════════════════════════════════════════════════
    #  Classification Pipeline
    # ══════════════════════════════════════════════════════════════════════

    @Slot(str)
    def _on_classify_requested(self, directory: str) -> None:
        """Start background classification when FileManagerPanel requests."""
        if not self._classifier:
            QMessageBox.critical(
                self, "خطأ",
                "المصنف غير متاح. تأكد من تثبيت المكتبات المطلوبة."
            )
            return
        self._panel_files.start_classification(self._classifier)

    # ══════════════════════════════════════════════════════════════════════
    #  Semantic Search Pipeline (called from panel via parent walk)
    # ══════════════════════════════════════════════════════════════════════

    def start_indexing(self, directory: str) -> None:
        if not self._search_engine:
            self._panel_search.on_index_error(
                "محرك البحث غير متاح"
            )
            return
        # Try loading existing index first
        if not self._search_engine._embeddings:
            loaded = self._search_engine.load_index()
            if loaded:
                count = len(self._search_engine._embeddings)
                self._panel_search.on_index_done(count)
                self._panel_dashboard.update_index_status(count)

        worker = SearchWorker(self._search_engine, parent=self)
        worker._mode = "index"
        worker._directory = directory
        worker.index_progress.connect(self._on_index_complete)
        worker.error_occurred.connect(self._panel_search.on_index_error)
        # Keep reference to prevent GC
        self._search_worker = worker
        worker.start()

    @Slot(int)
    def _on_index_complete(self, count: int) -> None:
        self._panel_search.on_index_done(count)
        self._panel_dashboard.update_index_status(count)
        if self._search_engine:
            try:
                self._search_engine.save_index()
            except Exception:
                pass

    def start_search(self, query: str) -> None:
        if not self._search_engine or not self._search_engine._embeddings:
            self._panel_search.on_search_error(
                "الفهرس فارغ – قم بفهرسة مجلد أولاً"
            )
            return
        worker = SearchWorker(self._search_engine, parent=self)
        worker._mode = "search"
        worker._query = query
        worker.search_done.connect(self._panel_search.on_search_done)
        worker.error_occurred.connect(self._panel_search.on_search_error)
        self._search_worker = worker
        worker.start()

    # ══════════════════════════════════════════════════════════════════════
    #  Chat Pipeline
    # ══════════════════════════════════════════════════════════════════════

    def start_chat(self, message: str) -> None:
        if not self._ai_engine:
            self._panel_assistant.on_chat_error(
                "محرك AI غير متاح. تأكد من تشغيل Ollama."
            )
            return
        worker = ChatWorker(self._ai_engine, message, parent=self)
        worker.response_ready.connect(self._panel_assistant.on_chat_response)
        worker.error_occurred.connect(self._panel_assistant.on_chat_error)
        self._chat_worker = worker
        worker.start()

    # ══════════════════════════════════════════════════════════════════════
    #  Voice Pipeline
    # ══════════════════════════════════════════════════════════════════════

    def start_voice(self) -> None:
        if not self._voice_ctrl:
            self._panel_assistant.on_voice_error(
                "التحكم الصوتي غير متاح"
            )
            return
        worker = VoiceWorker(self._voice_ctrl, parent=self)
        worker.command_ready.connect(self._panel_assistant.on_voice_command)
        worker.error_occurred.connect(self._panel_assistant.on_voice_error)
        self._voice_worker = worker
        worker.start()

    def _handle_voice_command(self, cmd: dict) -> None:
        """Callback for voice commands (called from VoiceController)."""
        action = cmd.get("action", "")
        params = cmd.get("params", "")
        logger.info(f"أمر صوتي: {action} {params}")

        if action == "classify":
            self._on_menu_classify()
        elif action == "search" and params:
            self._sidebar._navigate(_PAGE_SEMANTIC_SEARCH)
            self._panel_search._search_input.setText(params)
            self._panel_search._do_search()
        elif action == "open":
            self._on_menu_open()
        elif action == "undo":
            self._on_menu_undo()
        elif action == "chat" and params:
            self._sidebar._navigate(_PAGE_ASSISTANT)
            self._panel_assistant._chat_input.setText(params)
            self._panel_assistant._send_chat()
        elif action == "delete":
            self._on_menu_delete()

    # ══════════════════════════════════════════════════════════════════════
    #  RAG Pipeline
    # ══════════════════════════════════════════════════════════════════════

    def start_rag(self, question: str) -> None:
        if not self._rag_engine:
            self._panel_assistant.on_rag_error("محرك RAG غير متاح")
            return
        worker = RAGWorker(self._rag_engine, question, parent=self)
        worker.result_ready.connect(self._panel_assistant.on_rag_response)
        worker.error_occurred.connect(self._panel_assistant.on_rag_error)
        self._rag_worker = worker
        worker.start()

    # ══════════════════════════════════════════════════════════════════════
    #  AI Connection Check
    # ══════════════════════════════════════════════════════════════════════

    def _check_ai_status(self) -> None:
        if not self._ai_engine:
            self._lbl_ai_indicator.setText("AI: ✗")
            self._panel_dashboard.update_ai_status(False)
            return

        running = self._ai_engine.is_ollama_running()
        if running:
            models = self._ai_engine.list_models()
            self._lbl_ai_indicator.setText(
                f"AI: ✓ ({len(models)})"
            )
            self._panel_dashboard.update_ai_status(True)
            self._panel_settings.on_ai_test_result(True, models)
        else:
            self._lbl_ai_indicator.setText("AI: ✗")
            self._panel_dashboard.update_ai_status(False)
            self._panel_settings.on_ai_test_result(False, [])

    def test_ai_connection(self, url: str) -> None:
        """Test AI connection with a custom URL (called from Settings)."""
        if self._ai_engine:
            old_url = self._config.ollama_url
            self._config.ollama_url = url
            self._ai_engine.config = self._config
            self._check_ai_status()
            if not self._ai_engine.is_ollama_running():
                self._config.ollama_url = old_url
                self._ai_engine.config = self._config
                self._panel_settings.on_ai_test_result(False, [])
        else:
            self._panel_settings.on_ai_test_result(False, [])

    # ══════════════════════════════════════════════════════════════════════
    #  Theme Toggle
    # ══════════════════════════════════════════════════════════════════════

    @Slot()
    def toggle_dark_mode(self) -> None:
        self._config.dark_mode = not self._config.dark_mode
        self._apply_dark_mode(self._config.dark_mode)
        self._sidebar.set_dark_mode(self._config.dark_mode)

    # ══════════════════════════════════════════════════════════════════════
    #  Settings Changed
    # ══════════════════════════════════════════════════════════════════════

    def _on_settings_changed(self) -> None:
        self._apply_rtl()
        self._apply_dark_mode(self._config.dark_mode)
        self._sidebar.set_dark_mode(self._config.dark_mode)
        # Update voice button state in assistant
        self._panel_assistant._btn_voice.setEnabled(
            self._config.voice_enabled
        )

    # ══════════════════════════════════════════════════════════════════════
    #  Status Bar Helpers
    # ══════════════════════════════════════════════════════════════════════

    @Slot(str)
    def _set_status(self, message: str) -> None:
        self._lbl_operation.setText(message)

    def _update_file_count(self) -> None:
        """Periodically update file count in the status bar."""
        try:
            root = self._panel_files._fs_model.rootPath()
            count = sum(1 for _ in Path(root).rglob("*") if _.is_file())
            self._lbl_file_count.setText(f"الملفات: {count}")
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════
    #  Dialogs
    # ══════════════════════════════════════════════════════════════════════

    def _show_rename_dialog(self, current_name: str) -> tuple:
        """Show a rename dialog and return (new_name, accepted)."""
        dialog = QDialog(self)
        dialog.setWindowTitle("إعادة تسمية")
        dialog.setMinimumWidth(350)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("الاسم الجديد:"))
        input_field = QLineEdit(current_name)
        input_field.selectAll()
        layout.addWidget(input_field)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        input_field.setFocus()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return input_field.text().strip(), True
        return "", False

    # ══════════════════════════════════════════════════════════════════════
    #  Window State Persistence
    # ══════════════════════════════════════════════════════════════════════

    def _restore_state(self) -> None:
        geo = self._settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        state = self._settings.value("windowState")
        if state:
            self.restoreState(state)

    def closeEvent(self, event) -> None:  # noqa: N802
        """Save window state and clean up before closing."""
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("windowState", self.saveState())

        # Save config
        try:
            self._config.save()
        except Exception:
            pass

        # Wait for running workers
        for worker_name in (
            "_classify_worker_ref",
            "_search_worker",
            "_chat_worker",
            "_voice_worker",
            "_rag_worker",
        ):
            worker = getattr(self, worker_name, None)
            if worker is not None and worker.isRunning():
                worker.quit()
                worker.wait(2000)

        self._file_count_timer.stop()
        event.accept()
        logger.info("تم إغلاق التطبيق")


# ═══════════════════════════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

def _human_size(size_bytes: int) -> str:
    """Convert bytes to a human-readable size string."""
    if size_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024.0 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    return f"{size:.1f} {units[i]}"


# ═══════════════════════════════════════════════════════════════════════════
#  STANDALONE ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Launch the GUI as a standalone application (for dev / testing)."""
    logging.basicConfig(level=logging.INFO)

    app = QApplication(sys.argv)
    app.setApplicationName(_APP_NAME)
    app.setOrganizationName(_ORG_NAME)

    config = Config() if Config else None
    if config is None:
        # Fallback for layout-only testing
        logger.error("Cannot import Config – running in demo mode")
        sys.exit(1)

    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
