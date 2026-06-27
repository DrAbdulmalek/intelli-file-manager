'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Eye,
  Edit3,
  Move,
  Copy,
  Download,
  Trash2,
} from 'lucide-react';
import { Separator } from '@/components/ui/separator';
import type { ContextMenuState, FileItem } from './types';

interface FileActionsProps {
  contextMenu: ContextMenuState | null;
  files: FileItem[];
  onClose: () => void;
  onViewDetail: (file: FileItem) => void;
  onRename: (file: FileItem) => void;
  onDelete: (fileId: string) => void;
}

interface MenuItem {
  icon: React.ReactNode;
  label: string;
  action: () => void;
  danger?: boolean;
}

interface SeparatorItem {
  separator: true;
}

export const FileActions = React.memo(function FileActions({
  contextMenu,
  files,
  onClose,
  onViewDetail,
  onRename,
  onDelete,
}: FileActionsProps) {
  if (!contextMenu) return null;

  const fileId = contextMenu.fileId;

  const menuItems: (MenuItem | SeparatorItem)[] = [
    { icon: <Eye className="h-4 w-4" />, label: 'عرض التفاصيل', action: () => {
      const f = files.find((fi) => fi.id === fileId);
      if (f) onViewDetail(f);
    }},
    { icon: <Edit3 className="h-4 w-4" />, label: 'إعادة تسمية', action: () => {
      const f = files.find((fi) => fi.id === fileId);
      if (f) onRename(f);
    }},
    { icon: <Move className="h-4 w-4" />, label: 'نقل إلى...', action: () => {} },
    { icon: <Copy className="h-4 w-4" />, label: 'نسخ', action: () => {} },
    { icon: <Download className="h-4 w-4" />, label: 'تنزيل', action: () => {} },
    { separator: true },
    { icon: <Trash2 className="h-4 w-4 text-red-400" />, label: 'حذف', action: () => onDelete(fileId), danger: true },
  ];

  return (
    <AnimatePresence>
      {contextMenu && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className="fixed z-50 bg-slate-800 border border-slate-700 rounded-xl shadow-2xl py-1 min-w-[180px]"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          {menuItems.map((item, i) =>
            'separator' in item ? (
              <Separator key={i} className="bg-slate-700 my-1" />
            ) : (
              <button
                key={i}
                onClick={() => {
                  (item as MenuItem).action();
                  onClose();
                }}
                className={`w-full flex items-center gap-2 px-4 py-2 text-sm transition-colors ${
                  (item as MenuItem).danger
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
  );
});
