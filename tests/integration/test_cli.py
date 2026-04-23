"""اختبارات تكامل واجهة سطر الأوامر CLI

يغطي هذا الملف الاختبارات التالية:
  - أمر التصنيف (classify)
  - أمر الإحصائيات (stats)
  - عرض المساعدة عند عدم تحديد أمر
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from io import StringIO

import pytest

from src.core.agent_cli import AgentCLI
from src.core.config import Config


class TestCLIClassifyCommand:
    """اختبار أمر classify في واجهة سطر الأوامر"""

    def test_cli_classify_command_single_file(self, sample_files):
        """يتحقق من تصنيف ملف واحد عبر أمر CLI

        يختبر:
          - نجاح الأمر (success=True)
          - وجود نتيجة واحدة
          - صحة التصنيف في النتيجة
        """
        cli = AgentCLI()
        result = cli.execute_command("classify", [sample_files["pdf_file"]])

        assert result["success"] is True
        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["category"] == "مستندات"

    def test_cli_classify_command_directory(self, tmp_dir):
        """يتحقق من تصنيف مجلد كامل عبر أمر CLI

        يختبر:
          - نجاح الأمر (success=True)
          - وجود إحصائيات في النتيجة
          - أن الإحصائيات تحتوي تصنيفات
        """
        cli = AgentCLI()
        result = cli.execute_command("classify", [str(tmp_dir)])

        assert result["success"] is True
        assert "results" in result
        assert "stats" in result
        assert len(result["results"]) > 0
        assert len(result["stats"]) > 0

    def test_cli_classify_command_nonexistent_path(self):
        """يتحقق من أن تصنيف مسار غير موجود يُرجع خطأ"""
        cli = AgentCLI()
        result = cli.execute_command("classify", ["/nonexistent/path"])

        assert result["success"] is False
        assert "error" in result

    def test_cli_classify_command_with_output_flag(self, sample_files, tmp_path):
        """يتحقق من أن أمر التصنيف يعمل مع خيار --output"""
        cli = AgentCLI()
        result = cli.execute_command(
            "classify",
            [sample_files["pdf_file"], "--output", str(tmp_path)]
        )

        assert result["success"] is True


class TestCLIStatsCommand:
    """اختبار أمر stats في واجهة سطر الأوامر"""

    def test_cli_stats_command(self, tmp_dir):
        """يتحقق من أن أمر الإحصائيات يعمل ويعرض ملخصاً

        يختبر:
          - نجاح الأمر (success=True)
          - وجود ملخص في النتيجة
          - أن الملخص يحتوي معلومات مفيدة
        """
        cli = AgentCLI()

        # محاكاة FileAgent لأنه يُستدعى في _cmd_stats
        with patch("src.core.file_agent.FileAgent") as MockAgent:
            mock_instance = MagicMock()
            mock_instance.daily_summary.return_value = (
                "📅 ملخص يومي\n📊 عدد الملفات: 10\n💾 الحجم الكلي: 1024 بايت"
            )
            MockAgent.return_value = mock_instance

            result = cli.execute_command("stats", [str(tmp_dir)])

            assert result["success"] is True
            assert "summary" in result
            mock_instance.daily_summary.assert_called_once_with(str(tmp_dir))

    def test_cli_stats_command_default_path(self):
        """يتحقق من أن أمر الإحصائيات يعمل مع المسار الافتراضي (.)"""
        cli = AgentCLI()

        with patch("src.core.file_agent.FileAgent") as MockAgent:
            mock_instance = MagicMock()
            mock_instance.daily_summary.return_value = "ملخص"
            MockAgent.return_value = mock_instance

            result = cli.execute_command("stats", [])

            assert result["success"] is True

    def test_cli_stats_command_nonexistent_path(self):
        """يتحقق من أن أمر الإحصائيات مع مسار غير موجود لا ينهار"""
        cli = AgentCLI()

        with patch("src.core.file_agent.FileAgent") as MockAgent:
            mock_instance = MagicMock()
            mock_instance.daily_summary.return_value = "ملخص فارغ"
            MockAgent.return_value = mock_instance

            result = cli.execute_command("stats", ["/nonexistent"])

            assert result["success"] is True


class TestCLINoCommand:
    """اختبار عرض المساعدة عند عدم تحديد أمر"""

    def test_cli_no_command_shows_help(self, capsys):
        """يتحقق من أن الأمر غير المعروف يُرجع خطأ ويطبع المساعدة

        عند استدعاء CLI بأمر غير معروف يجب أن تُطبع صفحة المساعدة
        ويُرجع خطأ.
        """
        cli = AgentCLI()

        with pytest.raises(SystemExit):
            result = cli.execute_command("unknown_command", [])

    def test_cli_print_help_output(self, capsys):
        """يتحقق من أن صفحة المساعدة تحتوي نصوص مفيدة"""
        cli = AgentCLI()

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            cli.parser.print_help()
            help_text = mock_stdout.getvalue()

        assert "intellifile" in help_text.lower() or "IntelliFile" in help_text
        assert "classify" in help_text or "تصنيف" in help_text

    def test_cli_version(self):
        """يتحقق من خيار --version"""
        cli = AgentCLI()

        with pytest.raises(SystemExit) as exc_info:
            cli.parse_args(["--version"])
        assert exc_info.value.code == 0

    def test_cli_organize_dry_run(self, tmp_dir):
        """يتحقق من أن أمر organize مع --dry-run لا يُنفذ أي نقل"""
        cli = AgentCLI()

        with patch("src.core.classifier.SmartFileClassifier") as MockClassifier:
            with patch("src.core.file_handler.FileHandler") as MockHandler:
                mock_classifier = MagicMock()
                mock_classifier.batch_classify.return_value = [
                    {"name": "test.pdf", "category": "مستندات", "path": "test.pdf"}
                ]
                MockClassifier.return_value = mock_classifier

                mock_handler = MagicMock()
                mock_handler.create_category_folders.return_value = []
                MockHandler.return_value = mock_handler

                result = cli.execute_command(
                    "organize", [str(tmp_dir), "--dry-run"]
                )

                assert result["success"] is True
                assert result.get("dry_run") is True
                # يجب ألا تُستدعى move_file
                mock_handler.move_file.assert_not_called()


class TestCLIParseArgs:
    """اختبار تحليل معاملات الأوامر"""

    def test_parse_classify_args(self):
        """يتحقق من تحليل معاملات أمر التصنيف"""
        cli = AgentCLI()
        parsed = cli.parse_args(["classify", "/path/to/dir", "--auto", "-o", "/out"])

        assert parsed.command == "classify"
        assert parsed.path == "/path/to/dir"
        assert parsed.auto is True
        assert parsed.output == "/out"
        assert parsed.model == "gemma3"  # افتراضي

    def test_parse_search_args(self):
        """يتحقق من تحليل معاملات أمر البحث"""
        cli = AgentCLI()
        parsed = cli.parse_args(["search", "تقارير", "/path"])

        assert parsed.command == "search"
        assert parsed.query == "تقارير"
        assert parsed.path == "/path"

    def test_parse_voice_args(self):
        """يتحقق من تحليل معاملات أمر الصوت"""
        cli = AgentCLI()
        parsed = cli.parse_args(["voice", "--timeout", "5"])

        assert parsed.command == "voice"
        assert parsed.timeout == 5
