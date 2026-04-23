'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bot,
  Search,
  Grid3X3,
  List,
  FileText,
  ImageIcon,
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
  Zap,
  FolderOpen,
  File,
  Lock,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { CATEGORIES } from './constants';
import { formatFileSize, getFileIcon, getCategoryInfo } from './helpers';
import { UploadDialog } from './UploadDialog';
import { FileActions } from './FileActions';
import type { FileItem, FileCategory, ContextMenuState, UndoAction } from './types';

interface FileManagerProps {
  files: FileItem[];
  setFiles: React.Dispatch<React.SetStateAction<FileItem[]>>;
  viewMode: 'grid' | 'list';
  setViewMode: React.Dispatch<React.SetStateAction<'grid' | 'list'>>;
  selectedCategory: FileCategory | 'الكل';
  setSelectedCategory: React.Dispatch<React.SetStateAction<FileCategory | 'الكل'>>;
  searchQuery: string;
  setSearchQuery: React.Dispatch<React.SetStateAction<string>>;
  selectedFiles: Set<string>;
  setSelectedFiles: React.Dispatch<React.SetStateAction<Set<string>>>;
  classifying: boolean;
  setClassifying: React.Dispatch<React.SetStateAction<boolean>>;
  classifyProgress: number;
  setClassifyProgress: React.Dispatch<React.SetStateAction<number>>;
  undoAction: UndoAction | null;
  setUndoAction: React.Dispatch<React.SetStateAction<UndoAction | null>>;
}

export const FileManager = React.memo(function FileManager({
  files,
  setFiles,
  viewMode,
  setViewMode,
  selectedCategory,
  setSelectedCategory,
  searchQuery,
  setSearchQuery,
  selectedFiles,
  setSelectedFiles,
  classifying,
  setClassifying,
  classifyProgress,
  setClassifyProgress,
  undoAction,
  setUndoAction,
}: FileManagerProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [detailFile, setDetailFile] = useState<FileItem | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [renameDialog, setRenameDialog] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [renameFileId, setRenameFileId] = useState('');
  const [deleteDialog, setDeleteDialog] = useState(false);
  const [deleteFileId, setDeleteFileId] = useState('');
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);

  // Close context menu on click
  useEffect(() => {
    const handler = () => setContextMenu(null);
    window.addEventListener('click', handler);
    return () => window.removeEventListener('click', handler);
  }, []);

  // Auto-dismiss undo toast
  useEffect(() => {
    if (undoAction) {
      const timer = setTimeout(() => setUndoAction(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [undoAction, setUndoAction]);

  // Filtered files
  const filteredFiles = files.filter((f) => {
    const matchCategory = selectedCategory === 'الكل' || f.category === selectedCategory;
    const matchSearch = !searchQuery || f.name.includes(searchQuery);
    return matchCategory && matchSearch;
  });

  // ─── Handlers ──────────────────────────────────────────────────────────

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
  }, [setClassifying, setClassifyProgress, setFiles]);

  const handleSelectAll = useCallback(() => {
    if (selectedFiles.size === filteredFiles.length) {
      setSelectedFiles(new Set());
    } else {
      setSelectedFiles(new Set(filteredFiles.map((f) => f.id)));
    }
  }, [filteredFiles, selectedFiles, setSelectedFiles]);

  const handleToggleSelect = useCallback((id: string) => {
    setSelectedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, [setSelectedFiles]);

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
    [files, setFiles, setSelectedFiles, setUndoAction]
  );

  const handleUndo = useCallback(() => {
    if (undoAction) {
      setFiles(undoAction.files);
      setUndoAction(null);
    }
  }, [undoAction, setFiles, setUndoAction]);

  const handleRename = useCallback(() => {
    if (!renameValue.trim()) return;
    setFiles((prev) =>
      prev.map((f) => (f.id === renameFileId ? { ...f, name: renameValue } : f))
    );
    setRenameDialog(false);
    setRenameValue('');
  }, [renameValue, renameFileId, setFiles]);

  const handleBulkDelete = useCallback(() => {
    setUndoAction({
      files,
      message: `تم حذف ${selectedFiles.size} ملف`,
    });
    setFiles((prev) => prev.filter((f) => !selectedFiles.has(f.id)));
    setSelectedFiles(new Set());
  }, [files, selectedFiles, setFiles, setSelectedFiles, setUndoAction]);

  const handleViewDetail = useCallback((file: FileItem) => {
    setDetailFile(file);
    setDetailOpen(true);
  }, []);

  const handleRenameFile = useCallback((file: FileItem) => {
    setRenameFileId(file.id);
    setRenameValue(file.name);
    setRenameDialog(true);
  }, []);

  const handleDrop = useCallback((newFiles: FileItem[]) => {
    setFiles((prev) => [...newFiles, ...prev]);
  }, [setFiles]);

  // ─── Render ────────────────────────────────────────────────────────────

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="space-y-5"
    >
      {/* Upload Area */}
      <UploadDialog
        isDragging={isDragging}
        onDragStart={() => setIsDragging(true)}
        onDragEnd={() => setIsDragging(false)}
        onDrop={handleDrop}
      />

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
                                handleViewDetail(file);
                              }}
                            >
                              <Eye className="h-4 w-4 ml-2" /> عرض التفاصيل
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-slate-300 focus:bg-slate-700"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRenameFile(file);
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
                            handleViewDetail(file);
                          }}
                        >
                          <Eye className="h-4 w-4 ml-2" /> عرض التفاصيل
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-slate-300 focus:bg-slate-700"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRenameFile(file);
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
      <FileActions
        contextMenu={contextMenu}
        files={files}
        onClose={() => setContextMenu(null)}
        onViewDetail={handleViewDetail}
        onRename={handleRenameFile}
        onDelete={(fileId) => {
          handleDeleteFile(fileId);
          setContextMenu(null);
        }}
      />

      {/* File Detail Sheet */}
      <Sheet open={detailOpen} onOpenChange={setDetailOpen}>
        <SheetContent className="w-80 sm:w-96 bg-slate-900 border-slate-700" dir="rtl">
          <SheetHeader>
            <SheetTitle className="text-slate-200">تفاصيل الملف</SheetTitle>
          </SheetHeader>
          {detailFile && (
            <div className="h-[calc(100vh-100px)] mt-4 overflow-y-auto">
              <div className="space-y-5 pr-4">
                <div className="flex justify-center">
                  <div className="p-6 rounded-2xl bg-slate-800/80 border border-slate-700">
                    {React.cloneElement(getFileIcon(detailFile.extension) as React.ReactElement<any>, {
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
            </div>
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
});
