'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Upload } from 'lucide-react';
import type { FileItem, FileCategory } from './types';

interface UploadDialogProps {
  isDragging: boolean;
  onDragStart: () => void;
  onDragEnd: () => void;
  onDrop: (files: FileItem[]) => void;
}

export const UploadDialog = React.memo(function UploadDialog({
  isDragging,
  onDragStart,
  onDragEnd,
  onDrop,
}: UploadDialogProps) {
  return (
    <motion.div
      whileHover={{ scale: 1.005 }}
      className={`relative border-2 border-dashed rounded-2xl p-8 text-center transition-all duration-300 cursor-pointer ${
        isDragging
          ? 'border-emerald-400 bg-emerald-500/10 shadow-lg shadow-emerald-500/10'
          : 'border-slate-600 bg-slate-800/30 hover:border-emerald-500/50 hover:bg-slate-800/50'
      }`}
      onDragOver={(e) => {
        e.preventDefault();
        onDragStart();
      }}
      onDragLeave={onDragEnd}
      onDrop={(e) => {
        e.preventDefault();
        onDragEnd();
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
        onDrop(newFiles);
      }}
    >
      <Upload className={`h-10 w-10 mx-auto mb-3 transition-colors ${isDragging ? 'text-emerald-400' : 'text-slate-500'}`} />
      <p className="text-sm text-slate-300 font-medium">اسحب الملفات وأفلتها هنا</p>
      <p className="text-xs text-slate-500 mt-1">أو انقر لاختيار الملفات • يدعم جميع أنواع الملفات</p>
    </motion.div>
  );
});
