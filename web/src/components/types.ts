import React from 'react';

// ─── File Types ──────────────────────────────────────────────────────────────

export type FileCategory =
  | 'مستندات'
  | 'صور'
  | 'فيديو'
  | 'صوت'
  | 'أرشيفات'
  | 'برمجة'
  | 'أنظمة'
  | 'خطوط'
  | 'أخرى';

export interface FileItem {
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

// ─── Chat ────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

// ─── Activity ────────────────────────────────────────────────────────────────

export interface RecentActivity {
  id: string;
  action: string;
  fileName: string;
  time: string;
  type: 'classify' | 'upload' | 'delete' | 'protect' | 'move';
}

// ─── Navigation ──────────────────────────────────────────────────────────────

export type TabId = 'files' | 'copilot' | 'search' | 'dashboard' | 'settings';

// ─── Category Display ────────────────────────────────────────────────────────

export interface CategoryDisplay {
  name: FileCategory;
  color: string;
  bg: string;
  icon: React.ReactNode;
}

// ─── Sidebar ─────────────────────────────────────────────────────────────────

export interface SidebarItem {
  id: TabId;
  label: string;
  icon: React.ReactNode;
}

// ─── Context Menu ────────────────────────────────────────────────────────────

export interface ContextMenuState {
  x: number;
  y: number;
  fileId: string;
}

// ─── Undo Action ─────────────────────────────────────────────────────────────

export interface UndoAction {
  files: FileItem[];
  message: string;
}

// ─── Stats ───────────────────────────────────────────────────────────────────

export interface StatsData {
  totalFiles: number;
  classifiedFiles: number;
  duplicateFiles: number;
  totalSize: number;
}
