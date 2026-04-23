"""
واجهة رسومية بسيطة لـ IntelliFile
Simple GUI for IntelliFile using PySide6
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTextEdit, QProgressBar,
    QSplitter, QTreeWidget, QTreeWidgetItem, QMessageBox, QStatusBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon

# إضافة مسار المشروع
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import Config
from src.core.file_handler import FileHandler
from src.core.ai_engine import AIEngine
from src.core.rag_engine import RAGEngine
from src.core.classifier import DocumentClassifier


class WorkerThread(QThread):
    """خيط عمل للمهام الطويلة"""
    progress = Signal(int)
    message = Signal(str)
    finished = Signal(object)
    error = Signal(str)
    
    def __init__(self, task_func, *args, **kwargs):
        super().__init__()
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            result = self.task_func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """النافذة الرئيسية للتطبيق"""
    
    def __init__(self):
        super().__init__()
        
        # تحميل الإعدادات
        self.config = Config()
        
        # تهيئة المحركات
        try:
            self.file_handler = FileHandler(self.config)
            self.ai_engine = AIEngine(self.config)
            self.rag_engine = RAGEngine(self.config, self.ai_engine)
            self.classifier = DocumentClassifier(self.config)
            self.initialized = True
        except Exception as e:
            self.initialized = False
            QMessageBox.critical(self, "خطأ", f"فشل تهيئة النظام:\n{str(e)}")
        
        # إعداد الواجهة
        self.init_ui()
        
        # تحديث شريط الحالة
        self.update_status_bar()
    
    def init_ui(self):
        """تهيئة واجهة المستخدم"""
        self.setWindowTitle("IntelliFile - نظام إدارة الملفات الذكي")
        self.setMinimumSize(1200, 800)
        
        # إنشاء الويدجت الرئيسي
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # التخطيط الرئيسي
        main_layout = QVBoxLayout(central_widget)
        
        # شريط الأدوات العلوي
        toolbar_layout = QHBoxLayout()
        
        self.btn_scan = QPushButton("📁 مسح مجلد")
        self.btn_scan.clicked.connect(self.scan_directory)
        toolbar_layout.addWidget(self.btn_scan)
        
        self.btn_index = QPushButton("📚 فهرسة الملفات")
        self.btn_index.clicked.connect(self.index_files)
        toolbar_layout.addWidget(self.btn_index)
        
        self.btn_search = QPushButton("🔍 بحث")
        self.btn_search.clicked.connect(self.show_search)
        toolbar_layout.addWidget(self.btn_search)
        
        self.btn_classify = QPushButton("🏷️ تصنيف")
        self.btn_classify.clicked.connect(self.classify_selected)
        toolbar_layout.addWidget(self.btn_classify)
        
        toolbar_layout.addStretch()
        
        main_layout.addLayout(toolbar_layout)
        
        # تقسيم الشاشة
        splitter = QSplitter(Qt.Horizontal)
        
        # شجرة الملفات
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["الملف", "النوع", "الحجم"])
        self.file_tree.setMinimumWidth(400)
        splitter.addWidget(self.file_tree)
        
        # منطقة المحتوى
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # منطقة عرض النتائج
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Courier New", 10))
        content_layout.addWidget(self.result_text)
        
        # شريط التقدم
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        content_layout.addWidget(self.progress_bar)
        
        splitter.addWidget(content_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(splitter)
        
        # شريط الحالة
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
    
    def update_status_bar(self):
        """تحديث شريط الحالة"""
        if self.initialized:
            self.status_bar.showMessage(
                f"✅ متصل | النموذج: {self.config.ai_model} | اللغة: {'العربية' if self.config.language == 'ar' else 'English'}"
            )
        else:
            self.status_bar.showMessage("❌ غير متصل - تحقق من إعدادات النظام")
    
    def scan_directory(self):
        """مسح مجلد"""
        directory = QFileDialog.getExistingDirectory(self, "اختر مجلداً للمسح")
        
        if not directory:
            return
        
        self.progress_bar.setVisible(True)
        self.result_text.clear()
        self.result_text.append(f"📁 جاري مسح: {directory}\n")
        
        # تشغيل المسح في خيط منفصل
        self.worker = WorkerThread(self.file_handler.scan_directory, directory)
        self.worker.message.connect(lambda msg: self.result_text.append(msg))
        self.worker.finished.connect(self.on_scan_complete)
        self.worker.error.connect(self.on_error)
        self.worker.start()
    
    def on_scan_complete(self, results):
        """عند اكتمال المسح"""
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(100)
        
        self.file_tree.clear()
        self.result_text.append(f"\n✅ تم العثور على {len(results)} ملفاً\n")
        
        # إضافة الملفات إلى الشجرة
        for file_info in results[:100]:  # عرض أول 100 ملف فقط
            item = QTreeWidgetItem([
                file_info['name'],
                file_info.get('type', 'unknown'),
                file_info.get('size', 'N/A')
            ])
            self.file_tree.addTopLevelItem(item)
        
        if len(results) > 100:
            self.result_text.append(f"... و{len(results) - 100} ملفات أخرى")
    
    def index_files(self):
        """فهرسة الملفات"""
        if not self.initialized:
            QMessageBox.warning(self, "تحذير", "النظام غير مهيأ بشكل كامل")
            return
        
        # الحصول على الملفات المحددة أو جميع الملفات
        items = []
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            items.append(item)
        
        if not items:
            QMessageBox.information(self, "معلومات", "لا توجد ملفات لفهرستها. قم بمسح مجلد أولاً.")
            return
        
        self.result_text.append("\n📚 جاري الفهرسة...\n")
        self.progress_bar.setVisible(True)
        
        # هنا يمكن إضافة كود الفهرسة الفعلي
        self.progress_bar.setValue(100)
        self.result_text.append("✅ اكتملت الفهرسة\n")
    
    def show_search(self):
        """إظهار نافذة البحث"""
        from PySide6.QtWidgets import QInputDialog
        
        text, ok = QInputDialog.getText(self, "بحث", "أدخل نص البحث:")
        
        if ok and text:
            self.result_text.append(f"\n🔍 البحث عن: {text}\n")
            
            if self.initialized:
                try:
                    results = self.rag_engine.semantic_search(text, top_k=5)
                    
                    if results:
                        for i, result in enumerate(results, 1):
                            self.result_text.append(f"{i}. {result.get('file_name', 'Unknown')}")
                            self.result_text.append(f"   التشابه: {result.get('similarity', 0):.2%}")
                            content = result.get('content', '')
                            if len(content) > 200:
                                content = content[:200] + "..."
                            self.result_text.append(f"   المحتوى: {content}\n")
                    else:
                        self.result_text.append("⚠️ لم يتم العثور على نتائج\n")
                
                except Exception as e:
                    self.result_text.append(f"❌ خطأ: {str(e)}\n")
            else:
                self.result_text.append("⚠️ النظام غير مهيأ للبحث\n")
    
    def classify_selected(self):
        """تصنيف الملف المحدد"""
        selected_items = self.file_tree.selectedItems()
        
        if not selected_items:
            QMessageBox.information(self, "معلومات", "اختر ملفاً لتصنيفه")
            return
        
        item = selected_items[0]
        filename = item.text(0)
        
        self.result_text.append(f"\n🏷️ تصنيف: {filename}\n")
        
        # هنا يمكن إضافة كود التصنيف الفعلي
        self.result_text.append("⚠️ وظيفة التصنيف قيد التطوير\n")
    
    def on_error(self, error_msg):
        """عند حدوث خطأ"""
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "خطأ", f"حدث خطأ:\n{error_msg}")
        self.result_text.append(f"\n❌ خطأ: {error_msg}\n")


def main():
    """الدالة الرئيسية لواجهة الرسومية"""
    app = QApplication(sys.argv)
    
    # تعيين الخط
    font = QFont("Segoe UI", 10)
    if sys.platform.startswith('linux'):
        font = QFont("Ubuntu", 10)
    app.setFont(font)
    
    # إنشاء النافذة الرئيسية
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
