"""المساعد القابل للتوسع ذاتياً - إنشاء أدوات جديدة"""
import logging
import traceback
from typing import Dict, List, Optional, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class SelfExtendingAssistant:
    """مساعد يمكنه إنشاء أدوات جديدة في وقت التشغيل"""

    def __init__(self, ai_engine=None):
        self.ai_engine = ai_engine
        self._tools: Dict[str, Dict] = {}
        self._setup_built_in_tools()

    def _setup_built_in_tools(self):
        """إعداد الأدوات المدمجة"""
        self._tools = {
            "file_info": {
                "description": "عرض معلومات الملف",
                "function": self._tool_file_info,
                "params": ["filepath"],
            },
            "list_files": {
                "description": "سرد الملفات في مجلد",
                "function": self._tool_list_files,
                "params": ["directory"],
            },
            "get_stats": {
                "description": "إحصائيات المجلد",
                "function": self._tool_get_stats,
                "params": ["directory"],
            },
            "search_files": {
                "description": "البحث في الملفات",
                "function": self._tool_search_files,
                "params": ["directory", "pattern"],
            },
        }

    def create_tool(self, name: str, description: str,
                     function_code: str) -> bool:
        """إنشاء أداة جديدة ديناميكياً"""
        try:
            # إنشاء دالة من الكود
            namespace = {}
            exec(function_code, namespace)
            func = namespace.get(name)
            if not callable(func):
                return False

            self._tools[name] = {
                "description": description,
                "function": func,
                "dynamic": True,
            }
            logger.info(f"تم إنشاء أداة جديدة: {name}")
            return True
        except Exception as e:
            logger.error(f"خطأ في إنشاء الأداة {name}: {e}")
            return False

    def execute_tool(self, name: str, params: Dict = None) -> str:
        """تنفيذ أداة"""
        tool = self._tools.get(name)
        if not tool:
            return f"الأداة '{name}' غير موجودة"

        func = tool["function"]
        try:
            if params:
                result = func(**params)
            else:
                result = func()
            return str(result) if result is not None else "تم التنفيذ بنجاح"
        except Exception as e:
            logger.error(f"خطأ في تنفيذ {name}: {e}")
            return f"خطأ: {e}"

    def remove_tool(self, name: str) -> bool:
        """حذف أداة"""
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def list_tools(self) -> List[Dict]:
        """قائمة جميع الأدوات"""
        return [
            {"name": name, "description": info["description"], "dynamic": info.get("dynamic", False)}
            for name, info in self._tools.items()
        ]

    async def generate_tool_from_instruction(self, instruction: str) -> Optional[Dict]:
        """استخدام AI لتوليد أداة من وصف"""
        if not self.ai_engine:
            return None

        prompt = (
            f"أنت مساعد IntelliFile. أنش أداة Python بناءً على الوصف التالي.\n"
            f"أجب بصيغة Python فقط بدون أي شرح:\n\n"
            f"الوصف: {instruction}\n\n"
            f"القالب:\n"
            f"def tool_name(**kwargs):\n"
            f"    # الكود هنا\n"
            f"    return result\n"
        )

        try:
            response = self.ai_engine.chat(prompt)
            code = response.strip()
            # استخراج اسم الدالة
            import re
            match = re.search(r"def\s+(\w+)\s*\(", code)
            if match:
                name = match.group(1)
                self.create_tool(name, instruction, code)
                return {"name": name, "description": instruction, "code": code}
        except Exception:
            pass

        return None

    # === الأدوات المدمجة ===
    @staticmethod
    def _tool_file_info(filepath: str) -> str:
        path = Path(filepath)
        if not path.exists():
            return f"الملف غير موجود: {filepath}"
        stat = path.stat()
        return f"📄 {path.name}\n   المسار: {path}\n   الحجم: {stat.st_size} بايت\n   التعديل: {stat.st_mtime}"

    @staticmethod
    def _tool_list_files(directory: str) -> str:
        path = Path(directory)
        if not path.is_dir():
            return f"المجلد غير موجود: {directory}"
        files = [f.name for f in path.iterdir() if f.is_file() and not f.name.startswith(".")]
        return "\n".join(f"  📄 {f}" for f in files[:50]) or "المجلد فارغ"

    @staticmethod
    def _tool_get_stats(directory: str) -> str:
        path = Path(directory)
        if not path.is_dir():
            return f"المجلد غير موجود: {directory}"
        files = [f for f in path.rglob("*") if f.is_file() and not f.name.startswith(".")]
        from collections import Counter
        exts = Counter(f.suffix.lower() for f in files)
        lines = [f"📊 إحصائيات {path.name}:", f"  الملفات: {len(files)}"]
        for ext, count in exts.most_common(10):
            lines.append(f"  {ext}: {count}")
        return "\n".join(lines)

    @staticmethod
    def _tool_search_files(directory: str, pattern: str) -> str:
        from pathlib import Path
        matches = []
        path = Path(directory)
        if path.is_dir():
            for f in path.rglob(f"*{pattern}*"):
                matches.append(str(f))
        if not matches:
            return "لم يتم العثور على نتائج."
        return "\n".join(matches[:20])
