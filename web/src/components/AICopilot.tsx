'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Bot, Send, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { QUICK_COMMANDS, AI_RESPONSES } from './constants';
import type { ChatMessage } from './types';
import api from '@/lib/api';

interface AICopilotProps {
  chatMessages: ChatMessage[];
  setChatMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  chatInput: string;
  setChatInput: React.Dispatch<React.SetStateAction<string>>;
  isTyping: boolean;
  setIsTyping: React.Dispatch<React.SetStateAction<boolean>>;
}

export const AICopilot = React.memo(function AICopilot({
  chatMessages,
  setChatMessages,
  chatInput,
  setChatInput,
  isTyping,
  setIsTyping,
}: AICopilotProps) {
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, isTyping]);

  const handleSendMessage = useCallback(
    async (text?: string) => {
      const msg = text || chatInput.trim();
      if (!msg) return;

      const userMsg: ChatMessage = {
        id: Date.now().toString(),
        role: 'user',
        content: msg,
        timestamp: new Date().toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' }),
      };
      setChatMessages((prev) => [...prev, userMsg]);
      setChatInput('');
      setIsTyping(true);

      try {
        // Try real API first
        const result = await api.copilotChat(msg);
        const assistantMsg: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: result.response,
          timestamp: new Date().toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' }),
        };
        setChatMessages((prev) => [...prev, assistantMsg]);
      } catch (error) {
        // Fallback to simulated response when backend unavailable
        const matchedKey = Object.keys(AI_RESPONSES).find((k) => msg.includes(k));
        const aiResponse = matchedKey
          ? AI_RESPONSES[matchedKey]
          : `🤖 فهمت طلبك: "${msg}"\n\n⚠️ الخادم غير متاح حالياً. يتم استخدام الردود المحلية.\n\nيمكنك تشغيل خادم API: python -m uvicorn src.api.server:app --port 8421`;
        const assistantMsg: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: aiResponse,
          timestamp: new Date().toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' }),
        };
        setChatMessages((prev) => [...prev, assistantMsg]);
      } finally {
        setIsTyping(false);
      }
    },
    [chatInput, setChatMessages, setChatInput, setIsTyping]
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="flex flex-col h-[calc(100vh-180px)]"
    >
      {/* Quick Commands */}
      <div className="flex flex-wrap gap-2 mb-4">
        {QUICK_COMMANDS.map((cmd) => (
          <motion.button
            key={cmd}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => handleSendMessage(cmd)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800/60 border border-slate-700/50 text-sm text-slate-300 hover:border-emerald-500/30 hover:text-emerald-400 transition-all cursor-pointer"
          >
            <Zap className="h-3.5 w-3.5" />
            {cmd}
          </motion.button>
        ))}
      </div>

      {/* Chat Messages */}
      <ScrollArea className="flex-1 rounded-xl bg-slate-800/30 border border-slate-700/30 p-4">
        <div className="space-y-4">
          {chatMessages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${msg.role === 'user' ? 'justify-start' : 'justify-end'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-emerald-500/15 border border-emerald-500/20 text-emerald-50 rounded-br-sm'
                    : 'bg-slate-700/50 border border-slate-700 text-slate-200 rounded-bl-sm'
                }`}
              >
                {msg.role === 'assistant' && (
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-5 h-5 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center">
                      <Bot className="h-3 w-3 text-white" />
                    </div>
                    <span className="text-[10px] text-slate-400">المساعد الذكي</span>
                  </div>
                )}
                <div className="text-sm whitespace-pre-line leading-relaxed">{msg.content}</div>
                <p className="text-[10px] text-slate-500 mt-2">{msg.timestamp}</p>
              </div>
            </motion.div>
          ))}

          {/* Typing Animation */}
          {isTyping && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-end"
            >
              <div className="bg-slate-700/50 border border-slate-700 rounded-2xl rounded-bl-sm px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center">
                    <Bot className="h-3 w-3 text-white" />
                  </div>
                  <div className="flex gap-1">
                    {[0, 1, 2].map((i) => (
                      <motion.div
                        key={i}
                        animate={{ y: [0, -5, 0] }}
                        transition={{ repeat: Infinity, duration: 0.6, delay: i * 0.15 }}
                        className="w-2 h-2 rounded-full bg-emerald-400"
                      />
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          )}
          <div ref={chatEndRef} />
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="mt-4 flex gap-2">
        <Input
          placeholder="اكتب أمراً أو سؤالاً..."
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
          className="flex-1 bg-slate-800/60 border-slate-700 text-slate-200 placeholder:text-slate-500 h-12 rounded-xl"
        />
        <Button
          onClick={() => handleSendMessage()}
          className="h-12 w-12 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white p-0"
        >
          <Send className="h-5 w-5" />
        </Button>
      </div>
    </motion.div>
  );
});
