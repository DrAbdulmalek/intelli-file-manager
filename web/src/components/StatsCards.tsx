'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { File, Check, Copy, HardDrive } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { StatsData } from './types';
import { formatFileSize } from './helpers';

interface StatsCardsProps {
  stats: StatsData;
}

export const StatsCards = React.memo(function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      label: 'إجمالي الملفات',
      value: stats.totalFiles,
      icon: <File className="h-5 w-5" />,
      color: 'text-emerald-400',
      bg: 'bg-emerald-500/10',
      border: 'border-emerald-500/20',
    },
    {
      label: 'الملفات المصنفة',
      value: stats.classifiedFiles,
      icon: <Check className="h-5 w-5" />,
      color: 'text-teal-400',
      bg: 'bg-teal-500/10',
      border: 'border-teal-500/20',
      sub: stats.totalFiles > 0 ? `${Math.round((stats.classifiedFiles / stats.totalFiles) * 100)}%` : undefined,
    },
    {
      label: 'الملفات المكررة',
      value: stats.duplicateFiles,
      icon: <Copy className="h-5 w-5" />,
      color: 'text-amber-400',
      bg: 'bg-amber-500/10',
      border: 'border-amber-500/20',
    },
    {
      label: 'المساحة المستخدمة',
      value: formatFileSize(stats.totalSize),
      icon: <HardDrive className="h-5 w-5" />,
      color: 'text-purple-400',
      bg: 'bg-purple-500/10',
      border: 'border-purple-500/20',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((stat, idx) => (
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
                {stat.sub && (
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
  );
});
