'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Clock, BarChart3, Activity, TrendingUp, HardDrive } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
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
import { CATEGORIES, PIE_COLORS } from './constants';
import { formatFileSize, computeCategoryDistribution, computeFileTypeData } from './helpers';
import { StatsCards } from './StatsCards';
import type { FileItem, RecentActivity } from './types';

interface DashboardProps {
  files: FileItem[];
  recentActivity: RecentActivity[];
  totalSize: number;
  totalFiles: number;
  classifiedFiles: number;
  duplicateFiles: number;
}

export const Dashboard = React.memo(function Dashboard({
  files,
  recentActivity,
  totalSize,
  totalFiles,
  classifiedFiles,
  duplicateFiles,
}: DashboardProps) {
  const categoryDistribution = computeCategoryDistribution(files);
  const fileTypeData = computeFileTypeData(files);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      {/* Stats Cards */}
      <StatsCards
        stats={{ totalFiles, classifiedFiles, duplicateFiles, totalSize }}
      />

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
});
