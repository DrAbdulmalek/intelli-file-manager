'use client';

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { TooltipProvider } from '@/components/ui/tooltip';
import { SAMPLE_FILES, SIDEBAR_ITEMS, TAB_TITLES, TAB_DESCRIPTIONS, INITIAL_CHAT_MESSAGES, INITIAL_RECENT_SEARCHES, INITIAL_RECENT_ACTIVITY, ARCHIVE_PASSWORDS } from '@/components/constants';
import { computeStats } from '@/components/helpers';
import { Sidebar } from '@/components/Sidebar';
import { FileManager } from '@/components/FileManager';
import { AICopilot } from '@/components/AICopilot';
import { SearchPanel } from '@/components/SearchPanel';
import { Dashboard } from '@/components/Dashboard';
import { SettingsPanel } from '@/components/SettingsPanel';
import type { TabId, FileItem, FileCategory, ChatMessage, RecentActivity, UndoAction } from '@/components/types';

export default function IntelliFile() {
  const [files, setFiles] = useState<FileItem[]>(SAMPLE_FILES);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedCategory, setSelectedCategory] = useState<FileCategory | 'الكل'>('الكل');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [classifying, setClassifying] = useState(false);
  const [classifyProgress, setClassifyProgress] = useState(0);
  const [undoAction, setUndoAction] = useState<UndoAction | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(INITIAL_CHAT_MESSAGES);
  const [chatInput, setChatInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [semanticQuery, setSemanticQuery] = useState('');
  const [searchResults, setSearchResults] = useState<FileItem[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [recentSearches, setRecentSearches] = useState<string[]>(INITIAL_RECENT_SEARCHES);
  const [detailFile, setDetailFile] = useState<FileItem | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [autoClassify, setAutoClassify] = useState(true);
  const [fileProtection, setFileProtection] = useState(true);
  const [duplicateDetection, setDuplicateDetection] = useState(true);
  const [multimodalProcessing, setMultimodalProcessing] = useState(false);
  const [aiModel, setAiModel] = useState('intellifile-v3');
  const [language, setLanguage] = useState('ar');
  const [darkMode, setDarkMode] = useState(true);
  const [customCategories, setCustomCategories] = useState<string[]>([]);
  const [newCategory, setNewCategory] = useState('');
  const [recentActivity] = useState<RecentActivity[]>(INITIAL_RECENT_ACTIVITY);
  const [activeTab, setActiveTab] = useState<TabId>('files');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const stats = useMemo(() => computeStats(files), [files]);

  return (
    <TooltipProvider delayDuration={200}>
      <div dir="rtl" className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-200">
        {/* Mobile Header */}
        <div className="lg:hidden fixed top-0 left-0 right-0 z-30 h-14 bg-slate-900/95 backdrop-blur border-b border-slate-800 flex items-center px-4 gap-3">
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0 text-slate-400" onClick={() => setSidebarOpen(!sidebarOpen)}>
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" /></svg>
          </Button>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center"><Sparkles className="h-3.5 w-3.5 text-white" /></div>
            <span className="text-sm font-bold text-white">IntelliFile</span>
          </div>
        </div>

        {/* Mobile Sidebar Overlay */}
        <AnimatePresence>
          {sidebarOpen && (
            <>
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-30 bg-black/50 lg:hidden" onClick={() => setSidebarOpen(false)} />
              <motion.div initial={{ x: 260 }} animate={{ x: 0 }} exit={{ x: 260 }} transition={{ type: 'spring', damping: 25, stiffness: 300 }} className="fixed top-0 right-0 z-40 h-screen lg:hidden">
                <Sidebar activeTab={activeTab} onTabChange={(tab) => { setActiveTab(tab); setSidebarOpen(false); }} totalSize={stats.totalSize} />
              </motion.div>
            </>
          )}
        </AnimatePresence>

        {/* Desktop Sidebar */}
        <div className="hidden lg:block"><Sidebar activeTab={activeTab} onTabChange={setActiveTab} totalSize={stats.totalSize} /></div>

        {/* Main Content */}
        <main className="lg:mr-64 min-h-screen pt-14 lg:pt-0">
          <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
            <div className="mb-6">
              <motion.h2 key={activeTab} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} className="text-2xl font-bold text-white flex items-center gap-3">
                <span className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400">{SIDEBAR_ITEMS.find((i) => i.id === activeTab)?.icon}</span>
                {TAB_TITLES[activeTab]}
              </motion.h2>
              <p className="text-sm text-slate-500 mt-2">{TAB_DESCRIPTIONS[activeTab]}</p>
            </div>
            {activeTab === 'files' && <FileManager files={files} setFiles={setFiles} viewMode={viewMode} setViewMode={setViewMode} selectedCategory={selectedCategory} setSelectedCategory={setSelectedCategory} searchQuery={searchQuery} setSearchQuery={setSearchQuery} selectedFiles={selectedFiles} setSelectedFiles={setSelectedFiles} classifying={classifying} setClassifying={setClassifying} classifyProgress={classifyProgress} setClassifyProgress={setClassifyProgress} undoAction={undoAction} setUndoAction={setUndoAction} />}
            {activeTab === 'copilot' && <AICopilot chatMessages={chatMessages} setChatMessages={setChatMessages} chatInput={chatInput} setChatInput={setChatInput} isTyping={isTyping} setIsTyping={setIsTyping} />}
            {activeTab === 'search' && <SearchPanel files={files} searchResults={searchResults} setSearchResults={setSearchResults} hasSearched={hasSearched} setHasSearched={setHasSearched} isSearching={isSearching} setIsSearching={setIsSearching} recentSearches={recentSearches} setRecentSearches={setRecentSearches} semanticQuery={semanticQuery} setSemanticQuery={setSemanticQuery} onViewDetail={(f) => { setDetailFile(f); setDetailOpen(true); }} />}
            {activeTab === 'dashboard' && <Dashboard files={files} recentActivity={recentActivity} totalSize={stats.totalSize} totalFiles={stats.totalFiles} classifiedFiles={stats.classifiedFiles} duplicateFiles={stats.duplicateFiles} />}
            {activeTab === 'settings' && <SettingsPanel autoClassify={autoClassify} setAutoClassify={setAutoClassify} fileProtection={fileProtection} setFileProtection={setFileProtection} duplicateDetection={duplicateDetection} setDuplicateDetection={setDuplicateDetection} multimodalProcessing={multimodalProcessing} setMultimodalProcessing={setMultimodalProcessing} aiModel={aiModel} setAiModel={setAiModel} language={language} setLanguage={setLanguage} darkMode={darkMode} setDarkMode={setDarkMode} customCategories={customCategories} setCustomCategories={setCustomCategories} newCategory={newCategory} setNewCategory={setNewCategory} archivePasswords={ARCHIVE_PASSWORDS} />}
          </div>
        </main>
      </div>
    </TooltipProvider>
  );
}
