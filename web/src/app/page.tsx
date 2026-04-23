'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FolderOpen,
  Bot,
  Search,
  BarChart3,
  Settings,
  Upload,
  Grid3X3,
  List,
  FileText,
  Image as ImageIcon,
  Video,
  Music,
  Archive,
  Code,
  Monitor,
  Type,
  FileQuestion,
  Shield,
  MoreVertical,
  Trash2,
  Copy,
  Edit3,
  Move,
  Download,
  Eye,
  Send,
  Mic,
  X,
  Check,
  ChevronDown,
  ChevronLeft,
  RefreshCw,
  Star,
  Clock,
  HardDrive,
  FolderPlus,
  File,
  Lock,
  AlertTriangle,
  Sparkles,
  MessageSquare,
  Zap,
  Globe,
  Moon,
  Sun,
  Plus,
  Minus,
  Hash,
  TrendingUp,
  Activity,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Progress } from '@/components/ui/progress';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts';

// ─── Types ───────────────────────────────────────────────────────────────────

type FileCategory =
  | 'مستندات'
  | 'صور'
  | 'فيديو'
  | 'صوت'
  | 'أرشيفات'
  | 'برمجة'
  | 'أنظمة'
  | 'خطوط'
  | 'أخرى';

interface FileItem {
  id: string;
  name: string;
  size: number;
  extension: string;
  category: FileCategory;
  isProtected: boolean;
  isDuplicate: boolean;
  hasPassword?: boolean;
  createdAt: string;
  selected?: boolean;
  isClassified?: boolean;
  similarityScore?: number;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface RecentActivity {
  id: string;
  action: string;
  fileName: string;
  time: string;
  type: 'classify' | 'upload' | 'delete' | 'protect' | 'move';
}

type TabId = 'files' | 'copilot' | 'search' | 'dashboard' | 'settings';

// ─── Constants ───────────────────────────────────────────────────────────────

const CATEGORIES: { name: FileCategory; color: string; bg: string; icon: React.ReactNode }[] = [
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

const SIDEBAR_ITEMS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'files', label: 'مدير الملفات', icon: <FolderOpen className="h-5 w-5" /> },
  { id: 'copilot', label: 'المساعد الذكي', icon: <Bot className="h-5 w-5" /> },
  { id: 'search', label: 'البحث الدلالي', icon: <Search className="h-5 w-5" /> },
  { id: 'dashboard', label: 'لوحة المعلومات', icon: <BarChart3 className="h-5 w-5" /> },
  { id: 'settings', label: 'الإعدادات', icon: <Settings className="h-5 w-5" /> },
];

const PIE_COLORS = ['#10b981', '#f472b6', '#a78bfa', '#fb923c', '#facc15', '#34d399', '#22d3ee', '#fb7185', '#9ca3af'];

const QUICK_COMMANDS = [
  'صنّف جميع الملفات',
  'ابحث عن الملفات المكررة',
  'أنشئ هيكل مجلدات جديد',
  'لخّص محتويات الملفات',
];

const AI_RESPONSES: Record<string, string> = {
  'صنّف جميع الملفات': '🤖 تم بدء عملية التصنيف التلقائي...\n\n✅ تم تصنيف 24 ملف بنجاح:\n\n📄 المستندات: 6 ملفات (تقارير، عروض تقديمية، فواتير)\n🖼️ الصور: 4 ملفات (صور فريق العمل، لقطات شاشة)\n📦 الأرشيفات: 3 ملفات (مشاريع، نسخ احتياطية)\n💻 البرمجة: 5 ملفات (مصادر، أكواد، مكتبات)\n🎵 الصوت: 2 ملف (بودكاست، مؤثرات)\n🎬 الفيديو: 2 ملف (تسجيلات، تعليمات)\n🔤 الخطوط: 1 ملف\n⚙️ الأنظمة: 1 ملف\n\n📊 دقة التصنيف: 94.7%',
  'ابحث عن الملفات المكررة': '🔍 جاري البحث عن الملفات المكررة...\n\nتم العثور على 3 مجموعات من الملفات المكررة:\n\n1️⃣ تقرير_المبيعات_2024.pdf\n   └── تقرير_المبيعات_v2.pdf (98.5% تطابق)\n   └── sales_report_final.pdf (97.2% تطابق)\n\n2️⃣ صورة_فريق_العمل.jpg\n   └── team_photo_copy.jpg (99.1% تطابق)\n\n3️⃣ قاعدة_البيانات.sql\n   └── database_backup.sql (95.8% تطابق)\n\n💾 يمكن توفير 12.4 MB بحذف المكررات',
  'أنشئ هيكل مجلدات جديد': '📁 تم إنشاء هيكل المجلدات المقترح:\n\n📂 IntelliFile/\n├── 📂 مستندات/\n│   ├── 📂 تقارير/\n│   ├── 📂 عروض تقديمية/\n│   ├── 📂 فواتير/\n│   └── 📂 عقود/\n├── 📂 الوسائط/\n│   ├── 📂 صور/\n│   ├── 📂 فيديو/\n│   └── 📂 صوت/\n├── 📂 البرمجة/\n│   ├── 📂 مصادر/\n│   ├── 📂 مشاريع/\n│   └── 📂 مكتبات/\n├── 📂 أرشيفات/\n└── 📂 أنظمة/\n\n✨ هل تريد تطبيق هذا الهيكل؟',
  'لخّص محتويات الملفات': '📋 ملخص محتويات الملفات:\n\n📄 تقرير_المبيعات_2024.pdf\n   → تقرير سنوي شامل يتضمن إحصائيات المبيعات للربع الأول\n\n📊 بيانات_الميزانية.xlsx\n   → جدول بيانات مالي يتضمن الميزانية والمصروفات\n\n🎨 تصميم_الواجهة.fig\n   → ملف تصميم واجهة المستخدم للتطبيق الجديد\n\n📝 ملاحظات_الاجتماع.md\n   → ملاحظات اجتماع فريق التطوير - 15 مارس 2024\n\n💻 app_main.py\n   → التطبيق الرئيسي - واجهة برمجة بلغة بايثون\n\n📦 تم تلخيص 24 ملف بنجاح ✅',
};

// ─── Sample Data ─────────────────────────────────────────────────────────────

const SAMPLE_FILES: FileItem[] = [
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

// ─── Helper Functions ────────────────────────────────────────────────────────

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 بايت';
  const units = ['بايت', 'كيلوبايت', 'ميغابايت', 'غيغابايت'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

function getFileIcon(ext: string): React.ReactNode {
  const e = ext.toLowerCase();
  if (['.pdf'].includes(e)) return <FileText className="h-8 w-8 text-red-400" />;
  if (['.doc', '.docx'].includes(e)) return <FileText className="h-8 w-8 text-blue-400" />;
  if (['.pptx', '.ppt'].includes(e)) return <FileText className="h-8 w-8 text-orange-400" />;
  if (['.xlsx', '.xls'].includes(e)) return <FileText className="h-8 w-8 text-emerald-400" />;
  if (['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp'].includes(e)) return <ImageIcon className="h-8 w-8 text-pink-400" />;
  if (['.mp4', '.mov', '.avi', '.mkv'].includes(e)) return <Video className="h-8 w-8 text-purple-400" />;
  if (['.mp3', '.wav', '.ogg', '.flac'].includes(e)) return <Music className="h-8 w-8 text-yellow-400" />;
  if (['.zip', '.rar', '.7z', '.tar.gz'].includes(e)) return <Archive className="h-8 w-8 text-amber-400" />;
  if (['.js', '.ts', '.py', '.sql', '.html', '.css', '.yaml', '.json'].includes(e)) return <Code className="h-8 w-8 text-emerald-400" />;
  if (['.exe', '.msi', '.dmg', '.app', '.ini'].includes(e)) return <Monitor className="h-8 w-8 text-cyan-400" />;
  if (['.ttf', '.otf', '.woff', '.woff2'].includes(e)) return <Type className="h-8 w-8 text-rose-400" />;
  return <File className="h-8 w-8 text-gray-400" />;
}

function getCategoryInfo(name: FileCategory) {
  return CATEGORIES.find((c) => c.name === name) || CATEGORIES[8];
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function IntelliFile() {
  // State
  const [activeTab, setActiveTab] = useState<TabId>('files');
  const [files, setFiles] = useState<FileItem[]>(SAMPLE_FILES);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedCategory, setSelectedCategory] = useState<FileCategory | 'الكل'>('الكل');
  const [searchQuery, setSearchQuery] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [detailFile, setDetailFile] = useState<FileItem | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [classifying, setClassifying] = useState(false);
  const [classifyProgress, setClassifyProgress] = useState(0);
  const [renameDialog, setRenameDialog] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [renameFileId, setRenameFileId] = useState('');
  const [deleteDialog, setDeleteDialog] = useState(false);
  const [deleteFileId, setDeleteFileId] = useState('');
  const [undoAction, setUndoAction] = useState<{ files: FileItem[]; message: string } | null>(null);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; fileId: string } | null>(null);

  // AI Copilot State
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: '0',
      role: 'assistant',
      content: 'مرحباً! أنا المساعد الذكي لـ IntelliFile 🤖\n\nيمكنني مساعدتك في:\n• تصنيف الملفات تلقائياً\n• البحث عن الملفات المكررة\n• إنشاء هيكل مجلدات\n• تلخيص محتويات الملفات\n\nكيف يمكنني مساعدتك اليوم؟',
      timestamp: new Date().toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [chatInput, setChatInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Semantic Search State
  const [semanticQuery, setSemanticQuery] = useState('');
  const [searchResults, setSearchResults] = useState<FileItem[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [recentSearches, setRecentSearches] = useState<string[]>([
    'تقارير المبيعات',
    'صور الفريق',
    'ملفات البرمجة',
  ]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Settings State
  const [autoClassify, setAutoClassify] = useState(true);
  const [fileProtection, setFileProtection] = useState(true);
  const [duplicateDetection, setDuplicateDetection] = useState(true);
  const [multimodalProcessing, setMultimodalProcessing] = useState(false);
  const [aiModel, setAiModel] = useState('intellifile-v3');
  const [language, setLanguage] = useState('ar');
  const [darkMode, setDarkMode] = useState(true);
  const [customCategories, setCustomCategories] = useState<string[]>([]);
  const [newCategory, setNewCategory] = useState('');
  const [archivePasswords, setArchivePasswords] = useState<{ name: string; password: string }[]>([
    { name: 'مشروع_تطوير_الويب.zip', password: '••••••••' },
    { name: 'نسخة_احتياطية.tar.gz', password: '••••••••' },
  ]);

  // Recent Activity
  const [recentActivity] = useState<RecentActivity[]>([
    { id: '1', action: 'تم تصنيف الملف', fileName: 'تقرير_المبيعات_2024.pdf', time: 'منذ 5 دقائق', type: 'classify' },
    { id: '2', action: 'تم رفع ملف جديد', fileName: 'صورة_فريق_العمل.jpg', time: 'منذ 15 دقيقة', type: 'upload' },
    { id: '3', action: 'تم حماية الملف', fileName: 'مشروع_تطوير_الويب.zip', time: 'منذ ساعة', type: 'protect' },
    { id: '4', action: 'تم نقل الملف', fileName: 'config.yaml', time: 'منذ ساعتين', type: 'move' },
    { id: '5', action: 'تم حذف ملف مكرر', fileName: 'فيديو_تعليمي.mov', time: 'منذ 3 ساعات', type: 'delete' },
    { id: '6', action: 'تم تصنيف 5 ملفات', fileName: 'دفعة تصنيف', time: 'منذ 5 ساعات', type: 'classify' },
  ]);

  // Sidebar collapse on mobile
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, isTyping]);

  useEffect(() => {
    const handler = () => setContextMenu(null);
    window.addEventListener('click', handler);
    return () => window.removeEventListener('click', handler);
  }, []);

  useEffect(() => {
    if (undoAction) {
      const timer = setTimeout(() => setUndoAction(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [undoAction]);

  // Filtered files
  const filteredFiles = files.filter((f) => {
    const matchCategory = selectedCategory === 'الكل' || f.category === selectedCategory;
    const matchSearch = !searchQuery || f.name.includes(searchQuery);
    return matchCategory && matchSearch;
  });

  // Stats
  const totalFiles = files.length;
  const classifiedFiles = files.filter((f) => f.isClassified).length;
  const duplicateFiles = files.filter((f) => f.isDuplicate).length;
  const totalSize = files.reduce((acc, f) => acc + f.size, 0);

  // Category distribution
  const categoryDistribution = CATEGORIES.map((cat) => ({
    name: cat.name,
    value: files.filter((f) => f.category === cat.name).length,
  })).filter((d) => d.value > 0);

  // File type distribution
  const fileTypeDistribution = files.reduce<Record<string, number>>((acc, f) => {
    acc[f.extension] = (acc[f.extension] || 0) + 1;
    return acc;
  }, {});
  const fileTypeData = Object.entries(fileTypeDistribution)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);

  // ─── Handlers ──────────────────────────────────────────────────────────

  const handleSendMessage = useCallback(
    (text?: string) => {
      const msg = text || chatInput.trim();
      if (!msg) return;

      const userMsg: ChatMessage = {
        id: Date.now().toString(),
        role: 'user',
        content: msg,
        timestamp: new Date().toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' }),
      };
      setChatMessages((prev) => [...prev, userMsg]);
      setChatInput('');
      setIsTyping(true);

      setTimeout(() => {
        setIsTyping(false);
        const matchedKey = Object.keys(AI_RESPONSES).find((k) => msg.includes(k));
        const aiResponse = matchedKey
          ? AI_RESPONSES[matchedKey]
          : `🤖 فهمت طلبك: "${msg}"\n\nجاري معالجة الأمر...\n\n✅ تم التنفيذ بنجاح!\n\nيمكنني مساعدتك بأي أمر آخر. ماذا تريد أن أفعل؟`;
        const assistantMsg: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: aiResponse,
          timestamp: new Date().toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' }),
        };
        setChatMessages((prev) => [...prev, assistantMsg]);
      }, 2000 + Math.random() * 1500);
    },
    [chatInput]
  );

  const handleSemanticSearch = useCallback(() => {
    if (!semanticQuery.trim()) return;
    setIsSearching(true);
    setShowSuggestions(false);

    setTimeout(() => {
      const query = semanticQuery.toLowerCase();
      const scored = files.map((f) => {
        let score = 0;
        if (f.name.includes(query)) score += 90;
        if (f.category.includes(semanticQuery)) score += 50;
        if (f.extension.includes(query)) score += 30;
        if (score === 0) score = Math.random() * 40 + 10;
        return { ...f, similarityScore: Math.min(score, 99) };
      });
      scored.sort((a, b) => (b.similarityScore || 0) - (a.similarityScore || 0));
      setSearchResults(scored.slice(0, 10));
      setIsSearching(false);
      setHasSearched(true);
      if (!recentSearches.includes(semanticQuery)) {
        setRecentSearches((prev) => [semanticQuery, ...prev.slice(0, 4)]);
      }
    }, 1200);
  }, [semanticQuery, files, recentSearches]);

  const handleClassifyAll = useCallback(() => {
    setClassifying(true);
    setClassifyProgress(0);
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 15 + 5;
      if (progress >= 100) {
        progress = 100;
        clearInterval(interval);
        setFiles((prev) => prev.map((f) => ({ ...f, isClassified: true })));
        setTimeout(() => setClassifying(false), 500);
      }
      setClassifyProgress(Math.min(progress, 100));
    }, 300);
  }, []);

  const handleSelectAll = useCallback(() => {
    if (selectedFiles.size === filteredFiles.length) {
      setSelectedFiles(new Set());
    } else {
      setSelectedFiles(new Set(filteredFiles.map((f) => f.id)));
    }
  }, [filteredFiles, selectedFiles]);

  const handleToggleSelect = useCallback((id: string) => {
    setSelectedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleDeleteFile = useCallback(
    (id: string) => {
      const file = files.find((f) => f.id === id);
      if (!file) return;
      setUndoAction({
        files,
        message: `تم حذف "${file.name}"`,
      });
      setFiles((prev) => prev.filter((f) => f.id !== id));
      setSelectedFiles((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    },
    [files]
  );

  const handleUndo = useCallback(() => {
    if (undoAction) {
      setFiles(undoAction.files);
      setUndoAction(null);
    }
  }, [undoAction]);

  const handleRename = useCallback(() => {
    if (!renameValue.trim()) return;
    setFiles((prev) =>
      prev.map((f) => (f.id === renameFileId ? { ...f, name: renameValue } : f))
    );
    setRenameDialog(false);
    setRenameValue('');
  }, [renameValue, renameFileId]);

  const handleAddCategory = useCallback(() => {
    if (newCategory.trim() && !customCategories.includes(newCategory.trim())) {
      setCustomCategories((prev) => [...prev, newCategory.trim()]);
      setNewCategory('');
    }
  }, [newCategory, customCategories]);

  const handleBulkDelete = useCallback(() => {
    setUndoAction({
      files,
      message: `تم حذف ${selectedFiles.size} ملف`,
    });
    setFiles((prev) => prev.filter((f) => !selectedFiles.has(f.id)));
    setSelectedFiles(new Set());
  }, [files, selectedFiles]);

  // ─── Render Sidebar ────────────────────────────────────────────────────

  const renderSidebar = () => (
    <aside className="fixed top-0 right-0 z-40 h-screen w-64 bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 border-l border-slate-700/50 flex flex-col transition-transform duration-300 lg:translate-x-0">
      {/* Logo */}
      <div className="p-5 border-b border-slate-700/50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">IntelliFile</h1>
            <p className="text-[10px] text-slate-400">إدارة الملفات الذكية</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        {SIDEBAR_ITEMS.map((item) => (
          <motion.button
            key={item.id}
            whileHover={{ x: -4 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => {
              setActiveTab(item.id);
              setSidebarOpen(false);
            }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 cursor-pointer ${
              activeTab === item.id
                ? 'bg-emerald-500/15 text-emerald-400 shadow-lg shadow-emerald-500/5 border border-emerald-500/20'
                : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
            }`}
          >
            <span className={activeTab === item.id ? 'text-emerald-400' : ''}>{item.icon}</span>
            <span>{item.label}</span>
            {activeTab === item.id && (
              <motion.div
                layoutId="activeTab"
                className="mr-auto w-1.5 h-1.5 rounded-full bg-emerald-400"
              />
            )}
          </motion.button>
        ))}
      </nav>

      {/* Storage Info */}
      <div className="p-4 border-t border-slate-700/50">
        <div className="rounded-xl bg-slate-800/80 p-3">
          <div className="flex items-center gap-2 mb-2">
            <HardDrive className="h-4 w-4 text-emerald-400" />
            <span className="text-xs text-slate-300">التخزين المستخدم</span>
          </div>
          <Progress value={(totalSize / (1024 * 1024 * 1024)) * 100} className="h-2 bg-slate-700" />
          <p className="text-[10px] text-slate-400 mt-1.5">
            {formatFileSize(totalSize)} من 1 غيغابايت
          </p>
        </div>
      </div>
    </aside>
  );

  // ─── Render File Manager ───────────────────────────────────────────────

  const renderFileManager = () => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="space-y-5"
    >
      {/* Upload Area */}
      <motion.div
        whileHover={{ scale: 1.005 }}
        className={`relative border-2 border-dashed rounded-2xl p-8 text-center transition-all duration-300 cursor-pointer ${
          isDragging
            ? 'border-emerald-400 bg-emerald-500/10 shadow-lg shadow-emerald-500/10'
            : 'border-slate-600 bg-slate-800/30 hover:border-emerald-500/50 hover:bg-slate-800/50'
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          const newFiles: FileItem[] = Array.from(e.dataTransfer.files).map((f, i) => ({
            id: Date.now().toString() + i,
            name: f.name,
            size: f.size,
            extension: '.' + f.name.split('.').pop(),
            category: 'أخرى' as FileCategory,
            isProtected: false,
            isDuplicate: false,
            createdAt: new Date().toISOString().split('T')[0],
            isClassified: false,
          }));
          setFiles((prev) => [...newFiles, ...prev]);
        }}
      >
        <Upload className={`h-10 w-10 mx-auto mb-3 transition-colors ${isDragging ? 'text-emerald-400' : 'text-slate-500'}`} />
        <p className="text-sm text-slate-300 font-medium">اسحب الملفات وأفلتها هنا</p>
        <p className="text-xs text-slate-500 mt-1">أو انقر لاختيار الملفات • يدعم جميع أنواع الملفات</p>
      </motion.div>

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          {/* Category Filter */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <Badge
              variant="outline"
              className={`cursor-pointer transition-all px-3 py-1.5 text-xs ${
                selectedCategory === 'الكل'
                  ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                  : 'text-slate-400 border-slate-600 hover:border-emerald-500/30'
              }`}
              onClick={() => setSelectedCategory('الكل')}
            >
              الكل ({files.length})
            </Badge>
            {CATEGORIES.map((cat) => {
              const count = files.filter((f) => f.category === cat.name).length;
              if (count === 0) return null;
              return (
                <Badge
                  key={cat.name}
                  variant="outline"
                  className={`cursor-pointer transition-all px-3 py-1.5 text-xs border ${cat.bg} ${
                    selectedCategory === cat.name
                      ? `${cat.color} ring-1 ring-current/30`
                      : 'text-slate-400 border-slate-600 hover:border-slate-500'
                  }`}
                  onClick={() => setSelectedCategory(cat.name)}
                >
                  {cat.name} ({count})
                </Badge>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Bulk Actions */}
          {selectedFiles.size > 0 && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-1.5"
            >
              <span className="text-xs text-emerald-400 font-medium">{selectedFiles.size} ملف محدد</span>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0 text-emerald-400 hover:text-emerald-300"
                      onClick={handleClassifyAll}
                    >
                      <Zap className="h-3.5 w-3.5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>تصنيف</TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0 text-red-400 hover:text-red-300"
                      onClick={handleBulkDelete}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>حذف</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </motion.div>
          )}

          {/* Search */}
          <div className="relative">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
            <Input
              placeholder="بحث في الملفات..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pr-9 pl-3 h-9 w-44 bg-slate-800/50 border-slate-700 text-sm text-slate-200 placeholder:text-slate-500"
            />
          </div>

          {/* View Toggle */}
          <div className="flex items-center bg-slate-800/50 rounded-lg border border-slate-700 p-0.5">
            <Button
              variant={viewMode === 'grid' ? 'default' : 'ghost'}
              size="sm"
              className={`h-8 w-8 p-0 ${viewMode === 'grid' ? 'bg-emerald-500/20 text-emerald-400' : 'text-slate-400'}`}
              onClick={() => setViewMode('grid')}
            >
              <Grid3X3 className="h-4 w-4" />
            </Button>
            <Button
              variant={viewMode === 'list' ? 'default' : 'ghost'}
              size="sm"
              className={`h-8 w-8 p-0 ${viewMode === 'list' ? 'bg-emerald-500/20 text-emerald-400' : 'text-slate-400'}`}
              onClick={() => setViewMode('list')}
            >
              <List className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Select All & Classify Progress */}
      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={selectedFiles.size === filteredFiles.length && filteredFiles.length > 0}
            onChange={handleSelectAll}
            className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500/30 accent-emerald-500"
          />
          <span className="text-xs text-slate-400">تحديد الكل</span>
        </label>
        {classifying && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-3 flex-1 mx-6">
            <Progress value={classifyProgress} className="h-2 bg-slate-700 flex-1" />
            <span className="text-xs text-emerald-400 min-w-[80px]">{Math.round(classifyProgress)}%</span>
          </motion.div>
        )}
        {!classifying && (
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-xs text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/10 gap-1.5"
            onClick={handleClassifyAll}
          >
            <Zap className="h-3.5 w-3.5" />
            تصنيف تلقائي
          </Button>
        )}
      </div>

      {/* File Grid / List */}
      <div className={viewMode === 'grid' ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3' : 'space-y-2'}>
        <AnimatePresence mode="popLayout">
          {filteredFiles.map((file) => {
            const catInfo = getCategoryInfo(file.category);
            return (
              <motion.div
                key={file.id}
                layout
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.2 }}
                onContextMenu={(e) => {
                  e.preventDefault();
                  setContextMenu({ x: e.clientX, y: e.clientY, fileId: file.id });
                }}
              >
                {viewMode === 'grid' ? (
                  <Card
                    className={`group bg-slate-800/60 border-slate-700/50 hover:border-emerald-500/30 hover:shadow-lg hover:shadow-emerald-500/5 transition-all duration-300 cursor-pointer overflow-hidden ${
                      selectedFiles.has(file.id) ? 'ring-2 ring-emerald-500 border-emerald-500/50' : ''
                    }`}
                    onClick={() => handleToggleSelect(file.id)}
                    onDoubleClick={() => {
                      setDetailFile(file);
                      setDetailOpen(true);
                    }}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between mb-3">
                        <div className="relative">
                          <div className="p-2 rounded-lg bg-slate-700/50">{getFileIcon(file.extension)}</div>
                          {file.isProtected && (
                            <div className="absolute -top-1 -left-1 w-4 h-4 rounded-full bg-amber-500 flex items-center justify-center">
                              <Shield className="h-2.5 w-2.5 text-white" />
                            </div>
                          )}
                          {file.isDuplicate && (
                            <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 flex items-center justify-center">
                              <Copy className="h-2.5 w-2.5 text-white" />
                            </div>
                          )}
                        </div>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0 text-slate-500 hover:text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="start" className="bg-slate-800 border-slate-700">
                            <DropdownMenuItem
                              className="text-slate-300 focus:bg-slate-700"
                              onClick={(e) => {
                                e.stopPropagation();
                                setDetailFile(file);
                                setDetailOpen(true);
                              }}
                            >
                              <Eye className="h-4 w-4 ml-2" /> عرض التفاصيل
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-slate-300 focus:bg-slate-700"
                              onClick={(e) => {
                                e.stopPropagation();
                                setRenameFileId(file.id);
                                setRenameValue(file.name);
                                setRenameDialog(true);
                              }}
                            >
                              <Edit3 className="h-4 w-4 ml-2" /> إعادة تسمية
                            </DropdownMenuItem>
                            <DropdownMenuItem className="text-slate-300 focus:bg-slate-700">
                              <Move className="h-4 w-4 ml-2" /> نقل
                            </DropdownMenuItem>
                            <DropdownMenuItem className="text-slate-300 focus:bg-slate-700">
                              <Download className="h-4 w-4 ml-2" /> تنزيل
                            </DropdownMenuItem>
                            <DropdownMenuSeparator className="bg-slate-700" />
                            <DropdownMenuItem
                              className="text-red-400 focus:bg-red-500/10 focus:text-red-400"
                              onClick={(e) => {
                                e.stopPropagation();
                                setDeleteFileId(file.id);
                                setDeleteDialog(true);
                              }}
                            >
                              <Trash2 className="h-4 w-4 ml-2" /> حذف
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                      <div className="space-y-2">
                        <p className="text-sm font-medium text-slate-200 truncate" title={file.name}>
                          {file.name}
                        </p>
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] text-slate-500">{formatFileSize(file.size)}</span>
                          <Badge
                            variant="outline"
                            className={`text-[10px] px-1.5 py-0 border ${catInfo.bg} ${catInfo.color}`}
                          >
                            {catInfo.icon}
                            <span className="mr-1">{file.category}</span>
                          </Badge>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] text-slate-600">{file.createdAt}</span>
                          {!file.isClassified && (
                            <span className="text-[10px] text-amber-400">بانتظار التصنيف</span>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <div
                    className={`group flex items-center gap-4 p-3 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:border-emerald-500/30 hover:shadow-lg hover:shadow-emerald-500/5 transition-all duration-300 cursor-pointer ${
                      selectedFiles.has(file.id) ? 'ring-2 ring-emerald-500 border-emerald-500/50' : ''
                    }`}
                    onClick={() => handleToggleSelect(file.id)}
                    onDoubleClick={() => {
                      setDetailFile(file);
                      setDetailOpen(true);
                    }}
                  >
                    <div className="relative shrink-0">
                      <div className="p-1.5 rounded-lg bg-slate-700/50">{getFileIcon(file.extension)}</div>
                      {file.isProtected && (
                        <div className="absolute -top-1 -left-1 w-3.5 h-3.5 rounded-full bg-amber-500 flex items-center justify-center">
                          <Shield className="h-2 w-2 text-white" />
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-200 truncate">{file.name}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[11px] text-slate-500">{formatFileSize(file.size)}</span>
                        <span className="text-[11px] text-slate-600">•</span>
                        <span className="text-[11px] text-slate-500">{file.createdAt}</span>
                      </div>
                    </div>
                    <Badge
                      variant="outline"
                      className={`text-[10px] px-2 py-0.5 border shrink-0 ${catInfo.bg} ${catInfo.color}`}
                    >
                      {catInfo.icon}
                      <span className="mr-1">{file.category}</span>
                    </Badge>
                    {file.isDuplicate && (
                      <Badge variant="outline" className="text-[10px] px-2 py-0.5 border-red-500/30 bg-red-500/10 text-red-400 shrink-0">
                        مكرر
                      </Badge>
                    )}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0 text-slate-500 hover:text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start" className="bg-slate-800 border-slate-700">
                        <DropdownMenuItem
                          className="text-slate-300 focus:bg-slate-700"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDetailFile(file);
                            setDetailOpen(true);
                          }}
                        >
                          <Eye className="h-4 w-4 ml-2" /> عرض التفاصيل
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-slate-300 focus:bg-slate-700"
                          onClick={(e) => {
                            e.stopPropagation();
                            setRenameFileId(file.id);
                            setRenameValue(file.name);
                            setRenameDialog(true);
                          }}
                        >
                          <Edit3 className="h-4 w-4 ml-2" /> إعادة تسمية
                        </DropdownMenuItem>
                        <DropdownMenuSeparator className="bg-slate-700" />
                        <DropdownMenuItem
                          className="text-red-400 focus:bg-red-500/10 focus:text-red-400"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteFile(file.id);
                          }}
                        >
                          <Trash2 className="h-4 w-4 ml-2" /> حذف
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                )}
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {filteredFiles.length === 0 && (
        <div className="text-center py-16">
          <FolderOpen className="h-16 w-16 text-slate-600 mx-auto mb-4" />
          <p className="text-slate-400 text-sm">لا توجد ملفات في هذا التصنيف</p>
        </div>
      )}

      {/* Context Menu */}
      <AnimatePresence>
        {contextMenu && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="fixed z-50 bg-slate-800 border border-slate-700 rounded-xl shadow-2xl py-1 min-w-[180px]"
            style={{ left: contextMenu.x, top: contextMenu.y }}
          >
            {[
              { icon: <Eye className="h-4 w-4" />, label: 'عرض التفاصيل', action: () => {
                const f = files.find((fi) => fi.id === contextMenu.fileId);
                if (f) { setDetailFile(f); setDetailOpen(true); }
              }},
              { icon: <Edit3 className="h-4 w-4" />, label: 'إعادة تسمية', action: () => {
                const f = files.find((fi) => fi.id === contextMenu.fileId);
                if (f) { setRenameFileId(f.id); setRenameValue(f.name); setRenameDialog(true); }
              }},
              { icon: <Move className="h-4 w-4" />, label: 'نقل إلى...', action: () => {} },
              { icon: <Copy className="h-4 w-4" />, label: 'نسخ', action: () => {} },
              { icon: <Download className="h-4 w-4" />, label: 'تنزيل', action: () => {} },
              { separator: true },
              { icon: <Trash2 className="h-4 w-4 text-red-400" />, label: 'حذف', action: () => handleDeleteFile(contextMenu.fileId), danger: true },
            ].map((item, i) =>
              'separator' in item ? (
                <Separator key={i} className="bg-slate-700 my-1" />
              ) : (
                <button
                  key={i}
                  onClick={() => {
                    (item as { action: () => void }).action();
                    setContextMenu(null);
                  }}
                  className={`w-full flex items-center gap-2 px-4 py-2 text-sm transition-colors ${
                    'danger' in item && item.danger
                      ? 'text-red-400 hover:bg-red-500/10'
                      : 'text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </button>
              )
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* File Detail Sheet */}
      <Sheet open={detailOpen} onOpenChange={setDetailOpen} dir="rtl">
        <SheetContent className="w-80 sm:w-96 bg-slate-900 border-slate-700">
          <SheetHeader>
            <SheetTitle className="text-slate-200">تفاصيل الملف</SheetTitle>
          </SheetHeader>
          {detailFile && (
            <ScrollArea className="h-[calc(100vh-100px)] mt-4">
              <div className="space-y-5 pr-4">
                <div className="flex justify-center">
                  <div className="p-6 rounded-2xl bg-slate-800/80 border border-slate-700">
                    {React.cloneElement(getFileIcon(detailFile.extension) as React.ReactElement, {
                      className: 'h-16 w-16',
                    })}
                  </div>
                </div>
                <div className="text-center">
                  <h3 className="text-lg font-bold text-slate-200 break-all">{detailFile.name}</h3>
                  <p className="text-xs text-slate-500 mt-1">{detailFile.extension} • {formatFileSize(detailFile.size)}</p>
                </div>
                <Separator className="bg-slate-700" />
                <div className="space-y-3">
                  {[
                    { label: 'الحجم', value: formatFileSize(detailFile.size) },
                    { label: 'النوع', value: detailFile.extension },
                    { label: 'التصنيف', value: detailFile.category },
                    { label: 'تاريخ الإنشاء', value: detailFile.createdAt },
                    { label: 'الحالة', value: detailFile.isClassified ? 'مصنّف ✓' : 'بانتظار التصنيف' },
                  ].map((row) => (
                    <div key={row.label} className="flex justify-between items-center">
                      <span className="text-sm text-slate-400">{row.label}</span>
                      <span className="text-sm font-medium text-slate-200">{row.value}</span>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2">
                  {detailFile.isProtected && (
                    <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30 gap-1">
                      <Shield className="h-3 w-3" /> محمي
                    </Badge>
                  )}
                  {detailFile.isDuplicate && (
                    <Badge className="bg-red-500/20 text-red-400 border-red-500/30 gap-1">
                      <Copy className="h-3 w-3" /> مكرر
                    </Badge>
                  )}
                  {detailFile.hasPassword && (
                    <Badge className="bg-purple-500/20 text-purple-400 border-purple-500/30 gap-1">
                      <Lock className="h-3 w-3" /> مؤرشف بكلمة مرور
                    </Badge>
                  )}
                </div>
                <Separator className="bg-slate-700" />
                <div className="flex gap-2">
                  <Button className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white gap-2">
                    <Download className="h-4 w-4" /> تنزيل
                  </Button>
                  <Button
                    variant="outline"
                    className="border-slate-700 text-slate-300 hover:bg-slate-800 gap-2"
                    onClick={() => {
                      setRenameFileId(detailFile.id);
                      setRenameValue(detailFile.name);
                      setRenameDialog(true);
                    }}
                  >
                    <Edit3 className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    className="border-red-500/20 text-red-400 hover:bg-red-500/10"
                    onClick={() => {
                      handleDeleteFile(detailFile.id);
                      setDetailOpen(false);
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </ScrollArea>
          )}
        </SheetContent>
      </Sheet>

      {/* Rename Dialog */}
      <Dialog open={renameDialog} onOpenChange={setRenameDialog}>
        <DialogContent className="bg-slate-900 border-slate-700" dir="rtl">
          <DialogHeader>
            <DialogTitle className="text-slate-200">إعادة تسمية الملف</DialogTitle>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            className="bg-slate-800 border-slate-700 text-slate-200 mt-4"
            onKeyDown={(e) => e.key === 'Enter' && handleRename()}
          />
          <DialogFooter className="gap-2 mt-4">
            <Button variant="outline" className="border-slate-700 text-slate-300" onClick={() => setRenameDialog(false)}>
              إلغاء
            </Button>
            <Button className="bg-emerald-500 hover:bg-emerald-600 text-white" onClick={handleRename}>
              حفظ
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={deleteDialog} onOpenChange={setDeleteDialog}>
        <DialogContent className="bg-slate-900 border-slate-700" dir="rtl">
          <DialogHeader>
            <DialogTitle className="text-slate-200">تأكيد الحذف</DialogTitle>
          </DialogHeader>
          <p className="text-slate-400 text-sm mt-2">هل أنت متأكد من حذف هذا الملف؟ لا يمكن التراجع عن هذا الإجراء.</p>
          <DialogFooter className="gap-2 mt-4">
            <Button variant="outline" className="border-slate-700 text-slate-300" onClick={() => setDeleteDialog(false)}>
              إلغاء
            </Button>
            <Button className="bg-red-500 hover:bg-red-600 text-white" onClick={() => { handleDeleteFile(deleteFileId); setDeleteDialog(false); }}>
              حذف
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Undo Toast */}
      <AnimatePresence>
        {undoAction && (
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 50 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 shadow-2xl flex items-center gap-3"
          >
            <span className="text-sm text-slate-300">{undoAction.message}</span>
            <Button
              variant="link"
              className="text-emerald-400 p-0 h-auto text-sm"
              onClick={handleUndo}
            >
              تراجع
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );

  // ─── Render AI Copilot ─────────────────────────────────────────────────

  const renderCopilot = () => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="flex flex-col h-[calc(100vh-180px)]"
    >
      {/* Quick Commands */}
      <div className="flex flex-wrap gap-2 mb-4">
        {QUICK_COMMANDS.map((cmd) => (
          <motion.button
            key={cmd}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => handleSendMessage(cmd)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800/60 border border-slate-700/50 text-sm text-slate-300 hover:border-emerald-500/30 hover:text-emerald-400 transition-all cursor-pointer"
          >
            <Zap className="h-3.5 w-3.5" />
            {cmd}
          </motion.button>
        ))}
      </div>

      {/* Chat Messages */}
      <ScrollArea className="flex-1 rounded-xl bg-slate-800/30 border border-slate-700/30 p-4">
        <div className="space-y-4">
          {chatMessages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${msg.role === 'user' ? 'justify-start' : 'justify-end'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-emerald-500/15 border border-emerald-500/20 text-emerald-50 rounded-br-sm'
                    : 'bg-slate-700/50 border border-slate-700 text-slate-200 rounded-bl-sm'
                }`}
              >
                {msg.role === 'assistant' && (
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-5 h-5 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center">
                      <Bot className="h-3 w-3 text-white" />
                    </div>
                    <span className="text-[10px] text-slate-400">المساعد الذكي</span>
                  </div>
                )}
                <div className="text-sm whitespace-pre-line leading-relaxed">{msg.content}</div>
                <p className="text-[10px] text-slate-500 mt-2">{msg.timestamp}</p>
              </div>
            </motion.div>
          ))}

          {/* Typing Animation */}
          {isTyping && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-end"
            >
              <div className="bg-slate-700/50 border border-slate-700 rounded-2xl rounded-bl-sm px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center">
                    <Bot className="h-3 w-3 text-white" />
                  </div>
                  <div className="flex gap-1">
                    {[0, 1, 2].map((i) => (
                      <motion.div
                        key={i}
                        animate={{ y: [0, -5, 0] }}
                        transition={{ repeat: Infinity, duration: 0.6, delay: i * 0.15 }}
                        className="w-2 h-2 rounded-full bg-emerald-400"
                      />
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          )}
          <div ref={chatEndRef} />
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="mt-4 flex gap-2">
        <Input
          placeholder="اكتب أمراً أو سؤالاً..."
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
          className="flex-1 bg-slate-800/60 border-slate-700 text-slate-200 placeholder:text-slate-500 h-12 rounded-xl"
        />
        <Button
          onClick={() => handleSendMessage()}
          className="h-12 w-12 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white p-0"
        >
          <Send className="h-5 w-5" />
        </Button>
      </div>
    </motion.div>
  );

  // ─── Render Semantic Search ────────────────────────────────────────────

  const renderSearch = () => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      {/* Search Input */}
      <div className="relative">
        <div className="relative">
          <Search className="absolute right-4 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-500" />
          <Input
            placeholder="ابحث دلالياً عن الملفات... مثال: تقارير المبيعات، صور الفريق، ملفات البرمجة"
            value={semanticQuery}
            onChange={(e) => {
              setSemanticQuery(e.target.value);
              setShowSuggestions(e.target.value.length > 0);
              if (e.target.value.length === 0) {
                setHasSearched(false);
                setSearchResults([]);
              }
            }}
            onFocus={() => semanticQuery.length > 0 && setShowSuggestions(true)}
            onKeyDown={(e) => e.key === 'Enter' && handleSemanticSearch()}
            className="pr-12 pl-14 h-14 bg-slate-800/60 border-slate-700 text-slate-200 placeholder:text-slate-500 rounded-2xl text-base"
          />
          <button
            onClick={handleSemanticSearch}
            className="absolute left-3 top-1/2 -translate-y-1/2 p-1.5 rounded-lg bg-gradient-to-r from-emerald-500 to-teal-500 text-white hover:from-emerald-600 hover:to-teal-600 transition-all cursor-pointer"
          >
            <Send className="h-4 w-4" />
          </button>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="absolute left-14 top-1/2 -translate-y-1/2 p-1.5 rounded-lg bg-slate-700/50 text-slate-400 hover:text-emerald-400 transition-colors cursor-pointer">
                  <Mic className="h-4 w-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent>بحث صوتي</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {/* Suggestions */}
        <AnimatePresence>
          {showSuggestions && (
            <motion.div
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              className="absolute top-full mt-2 w-full bg-slate-800 border border-slate-700 rounded-xl shadow-2xl z-20 overflow-hidden"
            >
              {['تقارير المبيعات', 'صور الفريق', 'ملفات البرمجة', 'أرشيفات محمية', 'ملفات الصوت']
                .filter((s) => s.includes(semanticQuery) || semanticQuery === '')
                .slice(0, 5)
                .map((s) => (
                  <button
                    key={s}
                    onClick={() => {
                      setSemanticQuery(s);
                      setShowSuggestions(false);
                    }}
                    className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-700/50 transition-colors cursor-pointer"
                  >
                    <Search className="h-3.5 w-3.5 text-slate-500" />
                    {s}
                  </button>
                ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Recent Searches */}
      {!hasSearched && !isSearching && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-slate-400 flex items-center gap-2">
            <Clock className="h-4 w-4" /> عمليات البحث الأخيرة
          </h3>
          <div className="flex flex-wrap gap-2">
            {recentSearches.map((s) => (
              <button
                key={s}
                onClick={() => {
                  setSemanticQuery(s);
                  handleSemanticSearch();
                }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800/60 border border-slate-700/50 text-sm text-slate-400 hover:border-emerald-500/30 hover:text-emerald-400 transition-all cursor-pointer"
              >
                <Clock className="h-3.5 w-3.5" />
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading */}
      {isSearching && (
        <div className="text-center py-16">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
            className="w-12 h-12 rounded-full border-2 border-emerald-500/20 border-t-emerald-500 mx-auto"
          />
          <p className="text-slate-400 text-sm mt-4">جاري البحث الدلالي...</p>
        </div>
      )}

      {/* Results */}
      {hasSearched && !isSearching && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-slate-400">
              نتائج البحث ({searchResults.length})
            </h3>
            <div className="flex items-center gap-2">
              {CATEGORIES.slice(0, 6).map((cat) => (
                <Badge
                  key={cat.name}
                  variant="outline"
                  className={`text-[10px] px-2 py-0.5 border cursor-pointer ${cat.bg} ${cat.color}`}
                >
                  {cat.icon}
                  <span className="mr-1">{cat.name}</span>
                </Badge>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            {searchResults.map((file, idx) => {
              const catInfo = getCategoryInfo(file.category);
              const score = file.similarityScore || 0;
              return (
                <motion.div
                  key={file.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="flex items-center gap-4 p-4 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:border-emerald-500/30 transition-all cursor-pointer group"
                  onClick={() => {
                    setDetailFile(file);
                    setDetailOpen(true);
                  }}
                >
                  <div className="p-2 rounded-lg bg-slate-700/50 shrink-0">{getFileIcon(file.extension)}</div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-200 truncate">{file.name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[11px] text-slate-500">{formatFileSize(file.size)}</span>
                      <span className="text-[11px] text-slate-600">•</span>
                      <span className="text-[11px] text-slate-500">{file.createdAt}</span>
                    </div>
                  </div>
                  <Badge
                    variant="outline"
                    className={`text-[10px] px-2 py-0.5 border shrink-0 ${catInfo.bg} ${catInfo.color}`}
                  >
                    {file.category}
                  </Badge>
                  <div className="text-left shrink-0 w-16">
                    <div className="flex items-center gap-1.5">
                      <div className="flex-1 h-1.5 rounded-full bg-slate-700 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            score >= 80
                              ? 'bg-emerald-500'
                              : score >= 50
                              ? 'bg-yellow-500'
                              : 'bg-red-500'
                          }`}
                          style={{ width: `${score}%` }}
                        />
                      </div>
                      <span
                        className={`text-[11px] font-medium min-w-[32px] ${
                          score >= 80
                            ? 'text-emerald-400'
                            : score >= 50
                            ? 'text-yellow-400'
                            : 'text-red-400'
                        }`}
                      >
                        {score.toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}
    </motion.div>
  );

  // ─── Render Dashboard ──────────────────────────────────────────────────

  const renderDashboard = () => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: 'إجمالي الملفات',
            value: totalFiles,
            icon: <File className="h-5 w-5" />,
            color: 'text-emerald-400',
            bg: 'bg-emerald-500/10',
            border: 'border-emerald-500/20',
          },
          {
            label: 'الملفات المصنفة',
            value: classifiedFiles,
            icon: <Check className="h-5 w-5" />,
            color: 'text-teal-400',
            bg: 'bg-teal-500/10',
            border: 'border-teal-500/20',
            sub: `${Math.round((classifiedFiles / totalFiles) * 100)}%`,
          },
          {
            label: 'الملفات المكررة',
            value: duplicateFiles,
            icon: <Copy className="h-5 w-5" />,
            color: 'text-amber-400',
            bg: 'bg-amber-500/10',
            border: 'border-amber-500/20',
          },
          {
            label: 'المساحة المستخدمة',
            value: formatFileSize(totalSize),
            icon: <HardDrive className="h-5 w-5" />,
            color: 'text-purple-400',
            bg: 'bg-purple-500/10',
            border: 'border-purple-500/20',
          },
        ].map((stat, idx) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.1 }}
          >
            <Card className={`bg-slate-800/60 border ${stat.border}`}>
              <CardContent className="p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className={`p-2 rounded-lg ${stat.bg} ${stat.color}`}>{stat.icon}</div>
                  {'sub' in stat && stat.sub && (
                    <Badge className="bg-slate-700/50 text-slate-400 text-[10px] border-0">{stat.sub}</Badge>
                  )}
                </div>
                <p className="text-2xl font-bold text-slate-200">{stat.value}</p>
                <p className="text-xs text-slate-500 mt-1">{stat.label}</p>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Category Pie Chart */}
        <Card className="bg-slate-800/60 border-slate-700/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-300 flex items-center gap-2">
              <Activity className="h-4 w-4 text-emerald-400" /> توزيع الملفات حسب التصنيف
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={categoryDistribution}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {categoryDistribution.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '12px',
                      color: '#e2e8f0',
                      fontSize: '12px',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-wrap gap-3 mt-2 justify-center">
              {categoryDistribution.map((d, i) => (
                <div key={d.name} className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }} />
                  <span className="text-[11px] text-slate-400">{d.name} ({d.value})</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* File Type Bar Chart */}
        <Card className="bg-slate-800/60 border-slate-700/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-300 flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-emerald-400" /> توزيع أنواع الملفات
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[320px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={fileTypeData} layout="vertical" margin={{ right: 20, left: 10, top: 5, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
                  <XAxis type="number" stroke="#64748b" fontSize={11} />
                  <YAxis type="category" dataKey="name" stroke="#64748b" fontSize={11} width={60} />
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '12px',
                      color: '#e2e8f0',
                      fontSize: '12px',
                    }}
                  />
                  <Bar dataKey="count" fill="#10b981" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Recent Activity */}
        <Card className="bg-slate-800/60 border-slate-700/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-300 flex items-center gap-2">
              <Clock className="h-4 w-4 text-emerald-400" /> النشاط الأخير
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {recentActivity.map((activity) => (
                <div key={activity.id} className="flex items-start gap-3">
                  <div
                    className={`mt-1 w-2 h-2 rounded-full shrink-0 ${
                      activity.type === 'classify'
                        ? 'bg-emerald-400'
                        : activity.type === 'upload'
                        ? 'bg-teal-400'
                        : activity.type === 'delete'
                        ? 'bg-red-400'
                        : activity.type === 'protect'
                        ? 'bg-amber-400'
                        : 'bg-purple-400'
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-slate-300">{activity.action}</p>
                    <p className="text-[11px] text-slate-500 truncate">{activity.fileName}</p>
                  </div>
                  <span className="text-[10px] text-slate-600 shrink-0">{activity.time}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Top Categories */}
        <Card className="bg-slate-800/60 border-slate-700/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-300 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-400" /> أعلى التصنيفات
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {categoryDistribution
                .sort((a, b) => b.value - a.value)
                .map((cat, idx) => {
                  const pct = Math.round((cat.value / totalFiles) * 100);
                  const color = PIE_COLORS[CATEGORIES.findIndex((c) => c.name === cat.name) % PIE_COLORS.length];
                  return (
                    <div key={cat.name} className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-slate-300">{cat.name}</span>
                          <span className="text-[10px] text-slate-500">{cat.value} ملف</span>
                        </div>
                        <span className="text-xs font-bold text-slate-400">{pct}%</span>
                      </div>
                      <div className="h-2 rounded-full bg-slate-700 overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ duration: 1, delay: idx * 0.1 }}
                          className="h-full rounded-full"
                          style={{ backgroundColor: color }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>

            {/* Storage Usage */}
            <Separator className="bg-slate-700 my-4" />
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <HardDrive className="h-4 w-4 text-slate-500" />
                <span className="text-xs text-slate-400">استخدام التخزين</span>
              </div>
              <div className="h-3 rounded-full bg-slate-700 overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min((totalSize / (1024 * 1024 * 1024)) * 100, 100)}%` }}
                  transition={{ duration: 1.5 }}
                  className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400"
                />
              </div>
              <p className="text-[11px] text-slate-500">
                {formatFileSize(totalSize)} من 1 غيغابايت ({((totalSize / (1024 * 1024 * 1024)) * 100).toFixed(1)}%)
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </motion.div>
  );

  // ─── Render Settings ───────────────────────────────────────────────────

  const renderSettings = () => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="max-w-2xl space-y-6"
    >
      {/* Feature Toggles */}
      <Card className="bg-slate-800/60 border-slate-700/50">
        <CardHeader>
          <CardTitle className="text-sm text-slate-300 flex items-center gap-2">
            <Zap className="h-4 w-4 text-emerald-400" /> الميزات الذكية
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {[
            { label: 'التصنيف التلقائي', desc: 'تصنيف الملفات تلقائياً باستخدام الذكاء الاصطناعي', value: autoClassify, setter: setAutoClassify },
            { label: 'حماية ملفات التطبيقات', desc: 'حماية الملفات المهمة من الحذف العرضي', value: fileProtection, setter: setFileProtection },
            { label: 'الكشف عن المكررات', desc: 'التحقق التلقائي من وجود ملفات مكررة', value: duplicateDetection, setter: setDuplicateDetection },
            { label: 'المعالجة متعددة الوسائط', desc: 'تحليل محتوى الصور والفيديو والصوت', value: multimodalProcessing, setter: setMultimodalProcessing },
          ].map((item) => (
            <div key={item.label} className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-200">{item.label}</p>
                <p className="text-xs text-slate-500 mt-0.5">{item.desc}</p>
              </div>
              <Switch checked={item.value} onCheckedChange={item.setter} className="data-[state=checked]:bg-emerald-500" />
            </div>
          ))}
        </CardContent>
      </Card>

      {/* AI Model & Language */}
      <Card className="bg-slate-800/60 border-slate-700/50">
        <CardHeader>
          <CardTitle className="text-sm text-slate-300 flex items-center gap-2">
            <Bot className="h-4 w-4 text-emerald-400" /> نموذج الذكاء الاصطناعي
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm text-slate-400">النموذج</label>
            <Select value={aiModel} onValueChange={setAiModel}>
              <SelectTrigger className="bg-slate-700/50 border-slate-600 text-slate-200">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-700">
                <SelectItem value="intellifile-v3" className="text-slate-200">IntelliFile v3 (الأحدث)</SelectItem>
                <SelectItem value="intellifile-v2" className="text-slate-200">IntelliFile v2 (مستقر)</SelectItem>
                <SelectItem value="intellifile-lite" className="text-slate-200">IntelliFile Lite (سريع)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-400">اللغة</label>
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger className="bg-slate-700/50 border-slate-600 text-slate-200">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-700">
                <SelectItem value="ar" className="text-slate-200">العربية</SelectItem>
                <SelectItem value="en" className="text-slate-200">English</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-200">الوضع الداكن</p>
              <p className="text-xs text-slate-500 mt-0.5">تفعيل المظهر الداكن للتطبيق</p>
            </div>
            <div className="flex items-center gap-2 bg-slate-700/50 p-1 rounded-lg">
              <Button
                size="sm"
                variant={darkMode ? 'default' : 'ghost'}
                className={`h-8 px-3 text-xs gap-1.5 ${darkMode ? 'bg-emerald-500 text-white' : 'text-slate-400'}`}
                onClick={() => setDarkMode(true)}
              >
                <Moon className="h-3.5 w-3.5" /> داكن
              </Button>
              <Button
                size="sm"
                variant={!darkMode ? 'default' : 'ghost'}
                className={`h-8 px-3 text-xs gap-1.5 ${!darkMode ? 'bg-emerald-500 text-white' : 'text-slate-400'}`}
                onClick={() => setDarkMode(false)}
              >
                <Sun className="h-3.5 w-3.5" /> فاتح
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Custom Categories */}
      <Card className="bg-slate-800/60 border-slate-700/50">
        <CardHeader>
          <CardTitle className="text-sm text-slate-300 flex items-center gap-2">
            <FolderPlus className="h-4 w-4 text-emerald-400" /> التصنيفات المخصصة
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="أضف تصنيفاً جديداً..."
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddCategory()}
              className="flex-1 bg-slate-700/50 border-slate-600 text-slate-200 placeholder:text-slate-500"
            />
            <Button
              onClick={handleAddCategory}
              className="bg-emerald-500 hover:bg-emerald-600 text-white gap-1.5"
            >
              <Plus className="h-4 w-4" /> إضافة
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            {customCategories.map((cat) => (
              <Badge
                key={cat}
                variant="outline"
                className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 px-3 py-1.5 gap-1.5"
              >
                {cat}
                <button
                  onClick={() => setCustomCategories((prev) => prev.filter((c) => c !== cat))}
                  className="hover:text-red-400 transition-colors cursor-pointer"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
            {customCategories.length === 0 && (
              <p className="text-xs text-slate-600">لم تتم إضافة تصنيفات مخصصة بعد</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Archive Passwords */}
      <Card className="bg-slate-800/60 border-slate-700/50">
        <CardHeader>
          <CardTitle className="text-sm text-slate-300 flex items-center gap-2">
            <Lock className="h-4 w-4 text-emerald-400" /> كلمات مرور الأرشيفات
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {archivePasswords.map((item, idx) => (
            <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-slate-700/30 border border-slate-700/50">
              <div className="flex items-center gap-3">
                <Archive className="h-4 w-4 text-amber-400" />
                <div>
                  <p className="text-sm text-slate-200">{item.name}</p>
                  <p className="text-[11px] text-slate-500">{item.password}</p>
                </div>
              </div>
              <Button variant="ghost" size="sm" className="h-8 text-slate-400 hover:text-slate-300">
                <Edit3 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
          <Button variant="outline" className="w-full border-slate-700 text-slate-400 hover:text-emerald-400 gap-2 mt-2">
            <Plus className="h-4 w-4" /> إضافة كلمة مرور
          </Button>
        </CardContent>
      </Card>
    </motion.div>
  );

  // ─── Tab Title Map ─────────────────────────────────────────────────────

  const tabTitles: Record<TabId, string> = {
    files: 'مدير الملفات',
    copilot: 'المساعد الذكي',
    search: 'البحث الدلالي',
    dashboard: 'لوحة المعلومات',
    settings: 'الإعدادات',
  };

  // ─── Main Render ───────────────────────────────────────────────────────

  return (
    <TooltipProvider delayDuration={200}>
      <div dir="rtl" className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-200">
        {/* Mobile Header */}
        <div className="lg:hidden fixed top-0 left-0 right-0 z-30 h-14 bg-slate-900/95 backdrop-blur border-b border-slate-800 flex items-center px-4 gap-3">
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0 text-slate-400"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </Button>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center">
              <Sparkles className="h-3.5 w-3.5 text-white" />
            </div>
            <span className="text-sm font-bold text-white">IntelliFile</span>
          </div>
        </div>

        {/* Mobile Sidebar Overlay */}
        <AnimatePresence>
          {sidebarOpen && (
            <>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-30 bg-black/50 lg:hidden"
                onClick={() => setSidebarOpen(false)}
              />
              <motion.div
                initial={{ x: 260 }}
                animate={{ x: 0 }}
                exit={{ x: 260 }}
                transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                className="fixed top-0 right-0 z-40 h-screen lg:hidden"
              >
                {renderSidebar()}
              </motion.div>
            </>
          )}
        </AnimatePresence>

        {/* Desktop Sidebar */}
        <div className="hidden lg:block">{renderSidebar()}</div>

        {/* Main Content */}
        <main className="lg:mr-64 min-h-screen pt-14 lg:pt-0">
          <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
            {/* Page Header */}
            <div className="mb-6">
              <motion.h2
                key={activeTab}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                className="text-2xl font-bold text-white flex items-center gap-3"
              >
                <span className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400">
                  {SIDEBAR_ITEMS.find((i) => i.id === activeTab)?.icon}
                </span>
                {tabTitles[activeTab]}
              </motion.h2>
              <p className="text-sm text-slate-500 mt-2">
                {activeTab === 'files' && 'إدارة وتنظيم ملفاتك بذكاء باستخدام التصنيف التلقائي'}
                {activeTab === 'copilot' && 'تحدث مع المساعد الذكي لإدارة ملفاتك بسهولة'}
                {activeTab === 'search' && 'ابحث عن الملفات باستخدام البحث الدلالي المتقدم'}
                {activeTab === 'dashboard' && 'عرض إحصائيات شاملة حول ملفاتك وتصنيفاتها'}
                {activeTab === 'settings' && 'تخصيص إعدادات التطبيق حسب احتياجاتك'}
              </p>
            </div>

            {/* Render Active Tab Content */}
            {activeTab === 'files' && renderFileManager()}
            {activeTab === 'copilot' && renderCopilot()}
            {activeTab === 'search' && renderSearch()}
            {activeTab === 'dashboard' && renderDashboard()}
            {activeTab === 'settings' && renderSettings()}
          </div>
        </main>
      </div>
    </TooltipProvider>
  );
}
