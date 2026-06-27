import React from 'react';
import {
  FileText,
  Image as ImageIcon,
  Video,
  Music,
  Archive,
  Code,
  Monitor,
  Type,
  File,
} from 'lucide-react';
import { CATEGORIES } from './constants';
import type { FileCategory } from './types';

// ─── Format File Size ────────────────────────────────────────────────────────

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 بايت';
  const units = ['بايت', 'كيلوبايت', 'ميغابايت', 'غيغابايت'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

// ─── Get File Icon ───────────────────────────────────────────────────────────

export function getFileIcon(ext: string): React.ReactNode {
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

// ─── Get Category Info ───────────────────────────────────────────────────────

export function getCategoryInfo(name: FileCategory) {
  return CATEGORIES.find((c) => c.name === name) || CATEGORIES[8];
}

// ─── Compute Stats ───────────────────────────────────────────────────────────

export function computeStats(files: { size: number; isClassified?: boolean; isDuplicate: boolean }[]) {
  const totalFiles = files.length;
  const classifiedFiles = files.filter((f) => f.isClassified).length;
  const duplicateFiles = files.filter((f) => f.isDuplicate).length;
  const totalSize = files.reduce((acc, f) => acc + f.size, 0);
  return { totalFiles, classifiedFiles, duplicateFiles, totalSize };
}

// ─── Compute Category Distribution ──────────────────────────────────────────

export function computeCategoryDistribution(files: { category: FileCategory }[]) {
  return CATEGORIES.map((cat) => ({
    name: cat.name,
    value: files.filter((f) => f.category === cat.name).length,
  })).filter((d) => d.value > 0);
}

// ─── Compute File Type Distribution ─────────────────────────────────────────

export function computeFileTypeData(files: { extension: string }[]) {
  const dist = files.reduce<Record<string, number>>((acc, f) => {
    acc[f.extension] = (acc[f.extension] || 0) + 1;
    return acc;
  }, {});
  return Object.entries(dist)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);
}
