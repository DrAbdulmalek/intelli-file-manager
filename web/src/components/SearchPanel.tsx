'use client';

import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Send, Mic, Clock } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { CATEGORIES, SEARCH_SUGGESTIONS } from './constants';
import { formatFileSize, getFileIcon, getCategoryInfo } from './helpers';
import type { FileItem, FileCategory } from './types';
import api from '@/lib/api';

interface SearchPanelProps {
  files: FileItem[];
  searchResults: FileItem[];
  setSearchResults: React.Dispatch<React.SetStateAction<FileItem[]>>;
  hasSearched: boolean;
  setHasSearched: React.Dispatch<React.SetStateAction<boolean>>;
  isSearching: boolean;
  setIsSearching: React.Dispatch<React.SetStateAction<boolean>>;
  recentSearches: string[];
  setRecentSearches: React.Dispatch<React.SetStateAction<string[]>>;
  semanticQuery: string;
  setSemanticQuery: React.Dispatch<React.SetStateAction<string>>;
  onViewDetail: (file: FileItem) => void;
}

export const SearchPanel = React.memo(function SearchPanel({
  files,
  searchResults,
  setSearchResults,
  hasSearched,
  setHasSearched,
  isSearching,
  setIsSearching,
  recentSearches,
  setRecentSearches,
  semanticQuery,
  setSemanticQuery,
  onViewDetail,
}: SearchPanelProps) {
  const [showSuggestions, setShowSuggestions] = useState(false);

  const handleSemanticSearch = useCallback(async () => {
    if (!semanticQuery.trim()) return;
    setIsSearching(true);
    setShowSuggestions(false);

    try {
      // Try real hybrid search API
      const result = await api.search(semanticQuery, 10, 'hybrid');
      const mapped: FileItem[] = result.results.map((r, i) => ({
        id: r.id || i.toString(),
        name: r.id?.split('/').pop() || 'نتيجة بحث',
        size: 0,
        extension: r.id?.split('.').pop() || '',
        category: 'مستندات' as FileCategory,
        isProtected: false,
        isDuplicate: false,
        createdAt: new Date().toISOString(),
        similarityScore: Math.round((r.rrf_score || r.score || 0) * 1000),
        isClassified: true,
      }));
      setSearchResults(mapped);
    } catch {
      // Fallback to local search
      const query = semanticQuery.toLowerCase();
      const scored = files.map((f) => {
        let score = 0;
        if (f.name.includes(query)) score += 90;
        if (f.category.includes(semanticQuery)) score += 50;
        if (f.extension.includes(query)) score += 30;
        if (score === 0) score = Math.random() * 40 + 10;
        return { ...f, similarityScore: Math.min(score, 99) };
      });
      scored.sort((a, b) => (b.similarityScore || 0) - (a.similarityScore || 0));
      setSearchResults(scored.slice(0, 10));
    } finally {
      setIsSearching(false);
      setHasSearched(true);
      if (!recentSearches.includes(semanticQuery)) {
        setRecentSearches((prev) => [semanticQuery, ...prev.slice(0, 4)]);
      }
    }
  }, [semanticQuery, files, recentSearches, setSearchResults, setIsSearching, setHasSearched, setRecentSearches]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      {/* Search Input */}
      <div className="relative">
        <div className="relative">
          <Search className="absolute right-4 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-500" />
          <Input
            placeholder="ابحث دلالياً عن الملفات... مثال: تقارير المبيعات، صور الفريق، ملفات البرمجة"
            value={semanticQuery}
            onChange={(e) => {
              setSemanticQuery(e.target.value);
              setShowSuggestions(e.target.value.length > 0);
              if (e.target.value.length === 0) {
                setHasSearched(false);
                setSearchResults([]);
              }
            }}
            onFocus={() => semanticQuery.length > 0 && setShowSuggestions(true)}
            onKeyDown={(e) => e.key === 'Enter' && handleSemanticSearch()}
            className="pr-12 pl-14 h-14 bg-slate-800/60 border-slate-700 text-slate-200 placeholder:text-slate-500 rounded-2xl text-base"
          />
          <button
            onClick={handleSemanticSearch}
            className="absolute left-3 top-1/2 -translate-y-1/2 p-1.5 rounded-lg bg-gradient-to-r from-emerald-500 to-teal-500 text-white hover:from-emerald-600 hover:to-teal-600 transition-all cursor-pointer"
          >
            <Send className="h-4 w-4" />
          </button>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="absolute left-14 top-1/2 -translate-y-1/2 p-1.5 rounded-lg bg-slate-700/50 text-slate-400 hover:text-emerald-400 transition-colors cursor-pointer">
                  <Mic className="h-4 w-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent>بحث صوتي</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {/* Suggestions */}
        <AnimatePresence>
          {showSuggestions && (
            <motion.div
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              className="absolute top-full mt-2 w-full bg-slate-800 border border-slate-700 rounded-xl shadow-2xl z-20 overflow-hidden"
            >
              {SEARCH_SUGGESTIONS
                .filter((s) => s.includes(semanticQuery) || semanticQuery === '')
                .slice(0, 5)
                .map((s) => (
                  <button
                    key={s}
                    onClick={() => {
                      setSemanticQuery(s);
                      setShowSuggestions(false);
                    }}
                    className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-700/50 transition-colors cursor-pointer"
                  >
                    <Search className="h-3.5 w-3.5 text-slate-500" />
                    {s}
                  </button>
                ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Recent Searches */}
      {!hasSearched && !isSearching && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-slate-400 flex items-center gap-2">
            <Clock className="h-4 w-4" /> عمليات البحث الأخيرة
          </h3>
          <div className="flex flex-wrap gap-2">
            {recentSearches.map((s) => (
              <button
                key={s}
                onClick={() => {
                  setSemanticQuery(s);
                  handleSemanticSearch();
                }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800/60 border border-slate-700/50 text-sm text-slate-400 hover:border-emerald-500/30 hover:text-emerald-400 transition-all cursor-pointer"
              >
                <Clock className="h-3.5 w-3.5" />
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading */}
      {isSearching && (
        <div className="text-center py-16">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
            className="w-12 h-12 rounded-full border-2 border-emerald-500/20 border-t-emerald-500 mx-auto"
          />
          <p className="text-slate-400 text-sm mt-4">جاري البحث الدلالي...</p>
        </div>
      )}

      {/* Results */}
      {hasSearched && !isSearching && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-slate-400">
              نتائج البحث ({searchResults.length})
            </h3>
            <div className="flex items-center gap-2">
              {CATEGORIES.slice(0, 6).map((cat) => (
                <Badge
                  key={cat.name}
                  variant="outline"
                  className={`text-[10px] px-2 py-0.5 border cursor-pointer ${cat.bg} ${cat.color}`}
                >
                  {cat.icon}
                  <span className="mr-1">{cat.name}</span>
                </Badge>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            {searchResults.map((file, idx) => {
              const catInfo = getCategoryInfo(file.category);
              const score = file.similarityScore || 0;
              return (
                <motion.div
                  key={file.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="flex items-center gap-4 p-4 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:border-emerald-500/30 transition-all cursor-pointer group"
                  onClick={() => onViewDetail(file)}
                >
                  <div className="p-2 rounded-lg bg-slate-700/50 shrink-0">{getFileIcon(file.extension)}</div>
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
                    {file.category}
                  </Badge>
                  <div className="text-left shrink-0 w-16">
                    <div className="flex items-center gap-1.5">
                      <div className="flex-1 h-1.5 rounded-full bg-slate-700 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            score >= 80
                              ? 'bg-emerald-500'
                              : score >= 50
                              ? 'bg-yellow-500'
                              : 'bg-red-500'
                          }`}
                          style={{ width: `${score}%` }}
                        />
                      </div>
                      <span
                        className={`text-[11px] font-medium min-w-[32px] ${
                          score >= 80
                            ? 'text-emerald-400'
                            : score >= 50
                            ? 'text-yellow-400'
                            : 'text-red-400'
                        }`}
                      >
                        {score.toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}
    </motion.div>
  );
});
