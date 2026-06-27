'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles, HardDrive } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { SIDEBAR_ITEMS } from './constants';
import { formatFileSize } from './helpers';
import type { TabId } from './types';

interface SidebarProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  totalSize: number;
}

export const Sidebar = React.memo(function Sidebar({ activeTab, onTabChange, totalSize }: SidebarProps) {
  return (
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
            onClick={() => onTabChange(item.id)}
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
});
