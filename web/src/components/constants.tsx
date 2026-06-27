import React from 'react';
import {
  FolderOpen,
  Bot,
  Search,
  BarChart3,
  Settings,
  FileText,
  Image as ImageIcon,
  Video,
  Music,
  Archive,
  Code,
  Monitor,
  Type,
  FileQuestion,
} from 'lucide-react';
import type { FileCategory, FileItem, TabId, CategoryDisplay, SidebarItem, ChatMessage, RecentActivity } from './types';

// ─── Categories ──────────────────────────────────────────────────────────────

export const CATEGORIES: CategoryDisplay[] = [
  { name: 'مستندات', color: 'text-blue-400', bg: 'bg-blue-500/20 border-blue-500/30', icon: <FileText className="h-4 w-4" /> },
  { name: 'صور', color: 'text-pink-400', bg: 'bg-pink-500/20 border-pink-500/30', icon: <ImageIcon className="h-4 w-4" /> },
  { name: 'فيديو', color: 'text-purple-400', bg: 'bg-purple-500/20 border-purple-500/30', icon: <Video className="h-4 w-4" /> },
  { name: 'صوت', color: 'text-orange-400', bg: 'bg-orange-500/20 border-orange-500/30', icon: <Music className="h-4 w-4" /> },
  { name: 'أرشيفات', color: 'text-yellow-400', bg: 'bg-yellow-500/20 border-yellow-500/30', icon: <Archive className="h-4 w-4" /> },
  { name: 'برمجة', color: 'text-emerald-400', bg: 'bg-emerald-500/20 border-emerald-500/30', icon: <Code className="h-4 w-4" /> },
  { name: 'أنظمة', color: 'text-cyan-400', bg: 'bg-cyan-500/20 border-cyan-500/30', icon: <Monitor className="h-4 w-4" /> },
  { name: 'خطوط', color: 'text-rose-400', bg: 'bg-rose-500/20 border-rose-500/30', icon: <Type className="h-4 w-4" /> },
  { name: 'أخرى', color: 'text-gray-400', bg: 'bg-gray-500/20 border-gray-500/30', icon: <FileQuestion className="h-4 w-4" /> },
];

// ─── Sidebar Items ───────────────────────────────────────────────────────────

export const SIDEBAR_ITEMS: SidebarItem[] = [
  { id: 'files', label: 'مدير الملفات', icon: <FolderOpen className="h-5 w-5" /> },
  { id: 'copilot', label: 'المساعد الذكي', icon: <Bot className="h-5 w-5" /> },
  { id: 'search', label: 'البحث الدلالي', icon: <Search className="h-5 w-5" /> },
  { id: 'dashboard', label: 'لوحة المعلومات', icon: <BarChart3 className="h-5 w-5" /> },
  { id: 'settings', label: 'الإعدادات', icon: <Settings className="h-5 w-5" /> },
];

// ─── Tab Titles ──────────────────────────────────────────────────────────────

export const TAB_TITLES: Record<TabId, string> = {
  files: 'مدير الملفات',
  copilot: 'المساعد الذكي',
  search: 'البحث الدلالي',
  dashboard: 'لوحة المعلومات',
  settings: 'الإعدادات',
};

// ─── Tab Descriptions ────────────────────────────────────────────────────────

export const TAB_DESCRIPTIONS: Record<TabId, string> = {
  files: 'إدارة وتنظيم ملفاتك بذكاء باستخدام التصنيف التلقائي',
  copilot: 'تحدث مع المساعد الذكي لإدارة ملفاتك بسهولة',
  search: 'ابحث عن الملفات باستخدام البحث الدلالي المتقدم',
  dashboard: 'عرض إحصائيات شاملة حول ملفاتك وتصنيفاتها',
  settings: 'تخصيص إعدادات التطبيق حسب احتياجاتك',
};

// ─── Chart Colors ────────────────────────────────────────────────────────────

export const PIE_COLORS = ['#10b981', '#f472b6', '#a78bfa', '#fb923c', '#facc15', '#34d399', '#22d3ee', '#fb7185', '#9ca3af'];

// ─── Quick Commands ──────────────────────────────────────────────────────────

export const QUICK_COMMANDS = [
  'صنّف جميع الملفات',
  'ابحث عن الملفات المكررة',
  'أنشئ هيكل مجلدات جديد',
  'لخّص محتويات الملفات',
];

// ─── AI Responses ────────────────────────────────────────────────────────────

export const AI_RESPONSES: Record<string, string> = {
  'صنّف جميع الملفات': '🤖 تم بدء عملية التصنيف التلقائي...\n\n✅ تم تصنيف 24 ملف بنجاح:\n\n📄 المستندات: 6 ملفات (تقارير، عروض تقديمية، فواتير)\n🖼️ الصور: 4 ملفات (صور فريق العمل، لقطات شاشة)\n📦 الأرشيفات: 3 ملفات (مشاريع، نسخ احتياطية)\n💻 البرمجة: 5 ملفات (مصادر، أكواد، مكتبات)\n🎵 الصوت: 2 ملف (بودكاست، مؤثرات)\n🎬 الفيديو: 2 ملف (تسجيلات، تعليمات)\n🔤 الخطوط: 1 ملف\n⚙️ الأنظمة: 1 ملف\n\n📊 دقة التصنيف: 94.7%',
  'ابحث عن الملفات المكررة': '🔍 جاري البحث عن الملفات المكررة...\n\nتم العثور على 3 مجموعات من الملفات المكررة:\n\n1️⃣ تقرير_المبيعات_2024.pdf\n   └── تقرير_المبيعات_v2.pdf (98.5% تطابق)\n   └── sales_report_final.pdf (97.2% تطابق)\n\n2️⃣ صورة_فريق_العمل.jpg\n   └── team_photo_copy.jpg (99.1% تطابق)\n\n3️⃣ قاعدة_البيانات.sql\n   └── database_backup.sql (95.8% تطابق)\n\n💾 يمكن توفير 12.4 MB بحذف المكررات',
  'أنشئ هيكل مجلدات جديد': '📁 تم إنشاء هيكل المجلدات المقترح:\n\n📂 IntelliFile/\n├── 📂 مستندات/\n│   ├── 📂 تقارير/\n│   ├── 📂 عروض تقديمية/\n│   ├── 📂 فواتير/\n│   └── 📂 عقود/\n├── 📂 الوسائط/\n│   ├── 📂 صور/\n│   ├── 📂 فيديو/\n│   └── 📂 صوت/\n├── 📂 البرمجة/\n│   ├── 📂 مصادر/\n│   ├── 📂 مشاريع/\n│   └── 📂 مكتبات/\n├── 📂 أرشيفات/\n└── 📂 أنظمة/\n\n✨ هل تريد تطبيق هذا الهيكل؟',
  'لخّص محتويات الملفات': '📋 ملخص محتويات الملفات:\n\n📄 تقرير_المبيعات_2024.pdf\n   → تقرير سنوي شامل يتضمن إحصائيات المبيعات للربع الأول\n\n📊 بيانات_الميزانية.xlsx\n   → جدول بيانات مالي يتضمن الميزانية والمصروفات\n\n🎨 تصميم_الواجهة.fig\n   → ملف تصميم واجهة المستخدم للتطبيق الجديد\n\n📝 ملاحظات_الاجتماع.md\n   → ملاحظات اجتماع فريق التطوير - 15 مارس 2024\n\n💻 app_main.py\n   → التطبيق الرئيسي - واجهة برمجة بلغة بايثون\n\n📦 تم تلخيص 24 ملف بنجاح ✅',
};

// ─── Sample Files ────────────────────────────────────────────────────────────

export const SAMPLE_FILES: FileItem[] = [
  { id: '1', name: 'تقرير_المبيعات_2024.pdf', size: 2456789, extension: '.pdf', category: 'مستندات', isProtected: false, isDuplicate: false, createdAt: '2024-03-15', isClassified: true },
  { id: '2', name: 'صورة_فريق_العمل.jpg', size: 3456789, extension: '.jpg', category: 'صور', isProtected: false, isDuplicate: false, createdAt: '2024-03-14', isClassified: true },
  { id: '3', name: 'مشروع_تطوير_الويب.zip', size: 45678901, extension: '.zip', category: 'أرشيفات', isProtected: true, isDuplicate: false, createdAt: '2024-03-13', hasPassword: true, isClassified: true },
  { id: '4', name: 'عرض_تقديمي_المنتج.pptx', size: 8934567, extension: '.pptx', category: 'مستندات', isProtected: false, isDuplicate: false, createdAt: '2024-03-12', isClassified: true },
  { id: '5', name: 'تسجيل_الاجتماع.mp4', size: 156789012, extension: '.mp4', category: 'فيديو', isProtected: false, isDuplicate: false, createdAt: '2024-03-11', isClassified: true },
  { id: '6', name: 'قاعدة_البيانات.sql', size: 1234567, extension: '.sql', category: 'برمجة', isProtected: false, isDuplicate: false, createdAt: '2024-03-10', isClassified: true },
  { id: '7', name: 'بودكاست_التقنية.mp3', size: 34567890, extension: '.mp3', category: 'صوت', isProtected: false, isDuplicate: false, createdAt: '2024-03-09', isClassified: true },
  { id: '8', name: 'تصميم_الواجهة.fig', size: 23456789, extension: '.fig', category: 'أنظمة', isProtected: true, isDuplicate: false, createdAt: '2024-03-08', isClassified: true },
  { id: '9', name: 'خط_كوفي_عربي.ttf', size: 890123, extension: '.ttf', category: 'خطوط', isProtected: false, isDuplicate: false, createdAt: '2024-03-07', isClassified: true },
  { id: '10', name: 'ملاحظات_الاجتماع.md', size: 45678, extension: '.md', category: 'مستندات', isProtected: false, isDuplicate: false, createdAt: '2024-03-06', isClassified: true },
  { id: '11', name: 'لقطة_شاشة_التطبيق.png', size: 2345678, extension: '.png', category: 'صور', isProtected: false, isDuplicate: false, createdAt: '2024-03-05', isClassified: true },
  { id: '12', name: 'مكتبة_المشروع.js', size: 567890, extension: '.js', category: 'برمجة', isProtected: false, isDuplicate: false, createdAt: '2024-03-04', isClassified: true },
  { id: '13', name: 'فيديو_تعليمي.mov', size: 234567890, extension: '.mov', category: 'فيديو', isProtected: false, isDuplicate: true, createdAt: '2024-03-03', isClassified: true },
  { id: '14', name: 'نسخة_احتياطية.tar.gz', size: 67890123, extension: '.tar.gz', category: 'أرشيفات', isProtected: true, hasPassword: true, isDuplicate: false, createdAt: '2024-03-02', isClassified: true },
  { id: '15', name: 'مؤثرات_صوتية.wav', size: 45678901, extension: '.wav', category: 'صوت', isProtected: false, isDuplicate: false, createdAt: '2024-03-01', isClassified: true },
  { id: '16', name: 'app_main.py', size: 34567, extension: '.py', category: 'برمجة', isProtected: false, isDuplicate: false, createdAt: '2024-02-28', isClassified: true },
  { id: '17', name: 'بيانات_الميزانية.xlsx', size: 6789012, extension: '.xlsx', category: 'مستندات', isProtected: false, isDuplicate: false, createdAt: '2024-02-27', isClassified: true },
  { id: '18', name: 'صورة_الشعار.svg', size: 123456, extension: '.svg', category: 'صور', isProtected: true, isDuplicate: false, createdAt: '2024-02-26', isClassified: true },
  { id: '19', name: 'ملف_الإعدادات.ini', size: 2345, extension: '.ini', category: 'أنظمة', isProtected: false, isDuplicate: false, createdAt: '2024-02-25', isClassified: true },
  { id: '20', name: 'خط_نافباري.otf', size: 567890, extension: '.otf', category: 'خطوط', isProtected: false, isDuplicate: false, createdAt: '2024-02-24', isClassified: true },
  { id: '21', name: 'مشروع_المتجر.zip', size: 34567890, extension: '.zip', category: 'أرشيفات', isProtected: false, isDuplicate: true, createdAt: '2024-02-23', isClassified: false },
  { id: '22', name: 'سيرة_ذاتية.docx', size: 234567, extension: '.docx', category: 'مستندات', isProtected: true, isDuplicate: false, createdAt: '2024-02-22', isClassified: true },
  { id: '23', name: 'config.yaml', size: 8901, extension: '.yaml', category: 'برمجة', isProtected: false, isDuplicate: false, createdAt: '2024-02-21', isClassified: false },
  { id: '24', name: 'خلفية_سطح_المكتب.jpg', size: 5678901, extension: '.jpg', category: 'صور', isProtected: false, isDuplicate: false, createdAt: '2024-02-20', isClassified: true },
  { id: '25', name: 'تقرير_المبيعات_v2.pdf', size: 2490000, extension: '.pdf', category: 'مستندات', isProtected: false, isDuplicate: true, createdAt: '2024-03-15', isClassified: true },
];

// ─── Search Suggestions ─────────────────────────────────────────────────────

export const SEARCH_SUGGESTIONS = [
  'تقارير المبيعات',
  'صور الفريق',
  'ملفات البرمجة',
  'أرشيفات محمية',
  'ملفات الصوت',
];

// ─── Initial Data ─────────────────────────────────────────────────────────────

export const INITIAL_CHAT_MESSAGES: ChatMessage[] = [
  {
    id: '0',
    role: 'assistant',
    content: 'مرحباً! أنا المساعد الذكي لـ IntelliFile 🤖\n\nيمكنني مساعدتك في:\n• تصنيف الملفات تلقائياً\n• البحث عن الملفات المكررة\n• إنشاء هيكل مجلدات\n• تلخيص محتويات الملفات\n\nكيف يمكنني مساعدتك اليوم؟',
    timestamp: new Date().toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' }),
  },
];

export const INITIAL_RECENT_SEARCHES = ['تقارير المبيعات', 'صور الفريق', 'ملفات البرمجة'];

export const INITIAL_RECENT_ACTIVITY: RecentActivity[] = [
  { id: '1', action: 'تم تصنيف الملف', fileName: 'تقرير_المبيعات_2024.pdf', time: 'منذ 5 دقائق', type: 'classify' },
  { id: '2', action: 'تم رفع ملف جديد', fileName: 'صورة_فريق_العمل.jpg', time: 'منذ 15 دقيقة', type: 'upload' },
  { id: '3', action: 'تم حماية الملف', fileName: 'مشروع_تطوير_الويب.zip', time: 'منذ ساعة', type: 'protect' },
  { id: '4', action: 'تم نقل الملف', fileName: 'config.yaml', time: 'منذ ساعتين', type: 'move' },
  { id: '5', action: 'تم حذف ملف مكرر', fileName: 'فيديو_تعليمي.mov', time: 'منذ 3 ساعات', type: 'delete' },
  { id: '6', action: 'تم تصنيف 5 ملفات', fileName: 'دفعة تصنيف', time: 'منذ 5 ساعات', type: 'classify' },
];

export const ARCHIVE_PASSWORDS = [
  { name: 'مشروع_تطوير_الويب.zip', password: '••••••••' },
  { name: 'نسخة_احتياطية.tar.gz', password: '••••••••' },
];
