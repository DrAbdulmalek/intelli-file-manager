'use client';

import React, { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Bot,
  Zap,
  Moon,
  Sun,
  Plus,
  X,
  Lock,
  Edit3,
  Archive,
  FolderPlus,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface SettingsPanelProps {
  autoClassify: boolean;
  setAutoClassify: React.Dispatch<React.SetStateAction<boolean>>;
  fileProtection: boolean;
  setFileProtection: React.Dispatch<React.SetStateAction<boolean>>;
  duplicateDetection: boolean;
  setDuplicateDetection: React.Dispatch<React.SetStateAction<boolean>>;
  multimodalProcessing: boolean;
  setMultimodalProcessing: React.Dispatch<React.SetStateAction<boolean>>;
  aiModel: string;
  setAiModel: React.Dispatch<React.SetStateAction<string>>;
  language: string;
  setLanguage: React.Dispatch<React.SetStateAction<string>>;
  darkMode: boolean;
  setDarkMode: React.Dispatch<React.SetStateAction<boolean>>;
  customCategories: string[];
  setCustomCategories: React.Dispatch<React.SetStateAction<string[]>>;
  newCategory: string;
  setNewCategory: React.Dispatch<React.SetStateAction<string>>;
  archivePasswords: { name: string; password: string }[];
}

export const SettingsPanel = React.memo(function SettingsPanel({
  autoClassify,
  setAutoClassify,
  fileProtection,
  setFileProtection,
  duplicateDetection,
  setDuplicateDetection,
  multimodalProcessing,
  setMultimodalProcessing,
  aiModel,
  setAiModel,
  language,
  setLanguage,
  darkMode,
  setDarkMode,
  customCategories,
  setCustomCategories,
  newCategory,
  setNewCategory,
  archivePasswords,
}: SettingsPanelProps) {
  const handleAddCategory = useCallback(() => {
    if (newCategory.trim() && !customCategories.includes(newCategory.trim())) {
      setCustomCategories((prev) => [...prev, newCategory.trim()]);
      setNewCategory('');
    }
  }, [newCategory, customCategories, setCustomCategories, setNewCategory]);

  const featureToggles = [
    { label: 'التصنيف التلقائي', desc: 'تصنيف الملفات تلقائياً باستخدام الذكاء الاصطناعي', value: autoClassify, setter: setAutoClassify },
    { label: 'حماية ملفات التطبيقات', desc: 'حماية الملفات المهمة من الحذف العرضي', value: fileProtection, setter: setFileProtection },
    { label: 'الكشف عن المكررات', desc: 'التحقق التلقائي من وجود ملفات مكررة', value: duplicateDetection, setter: setDuplicateDetection },
    { label: 'المعالجة متعددة الوسائط', desc: 'تحليل محتوى الصور والفيديو والصوت', value: multimodalProcessing, setter: setMultimodalProcessing },
  ];

  return (
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
          {featureToggles.map((item) => (
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
});
