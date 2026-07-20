/**
 * IntelliFile API Client — communicates with FastAPI backend
 * 
 * All API calls go to http://localhost:8421/api/
 * Fallback to mock data when backend is unavailable
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8421/api';

// ─── Types ─────────────────────────────────────────────────────────────────

export interface ClassifyResult {
  name: string;
  path: string;
  extension: string;
  category: string;
  confidence: number;
  content_type: string;
  size: number;
}

export interface SearchResult {
  id: string;
  text: string;
  score: number;
  engine: string;
  bm25_rank?: number;
  semantic_rank?: number;
  rrf_score?: number;
}

export interface TagData {
  name: string;
  category: string;
  confidence: number;
  source: string;
}

export interface FileTagsData {
  filepath: string;
  tags: TagData[];
  lastUpdated: string;
}

export interface CopilotResponse {
  response: string;
  sources: { id: string; text: string; rrf_score: number; engine: string }[];
  conversation_id: string;
  message_count: number;
}

export interface NerEntity {
  text: string;
  type: string;
  confidence: number;
  source: string;
}

export interface NerResult {
  entities: NerEntity[];
  patient_name: string;
  patient_id: string;
  diagnosis: string[];
  medications: string[];
  procedures: string[];
  summary: Record<string, number>;
}

export interface HealthStatus {
  status: string;
  version: string;
  engines: Record<string, boolean>;
}

export interface ProcessResult {
  path: string;
  type: string;
  name: string;
  extracted_text?: string;
  ocr_engine?: string;
  ocr_success?: boolean;
  ai_description?: string;
  medical_entities?: Record<string, number>;
  diagnosis?: string[];
  medications?: string[];
  transcript?: string;
}

// ─── API Client ────────────────────────────────────────────────────────────

class IntelliFileAPI {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
        ...options,
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || `API error: ${response.status}`);
      }
      return response.json();
    } catch (error) {
      if (error instanceof TypeError && error.message.includes('fetch')) {
        console.warn('Backend unavailable, using fallback:', path);
        throw new Error('BACKEND_UNAVAILABLE');
      }
      throw error;
    }
  }

  // ─── Health ───────────────────────────────────────────────────────────

  async health(): Promise<HealthStatus> {
    return this.request<HealthStatus>('/health');
  }

  // ─── Classify ─────────────────────────────────────────────────────────

  async classify(path: string, recursive = true): Promise<{ results: ClassifyResult[]; total: number }> {
    return this.request('/classify', {
      method: 'POST',
      body: JSON.stringify({ path, recursive }),
    });
  }

  // ─── Search ───────────────────────────────────────────────────────────

  async search(query: string, topK = 10, engine: 'hybrid' | 'bm25' | 'semantic' = 'hybrid'): Promise<{
    query: string;
    results: SearchResult[];
    engine: string;
    total: number;
  }> {
    return this.request('/search', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK, engine }),
    });
  }

  async indexDirectory(directory: string, extensions = ''): Promise<{ indexed: number }> {
    return this.request(`/search/index?directory=${encodeURIComponent(directory)}&extensions=${extensions}`, {
      method: 'POST',
    });
  }

  // ─── Tags ─────────────────────────────────────────────────────────────

  async autoTag(filepath: string): Promise<FileTagsData> {
    return this.request(`/tags/auto?filepath=${encodeURIComponent(filepath)}`, {
      method: 'POST',
    });
  }

  async addTag(filepath: string, tag: string, category = 'manual'): Promise<FileTagsData> {
    return this.request('/tags/add', {
      method: 'POST',
      body: JSON.stringify({ filepath, tag, category }),
    });
  }

  async removeTag(filepath: string, tag: string): Promise<{ removed: boolean }> {
    return this.request(`/tags/remove?filepath=${encodeURIComponent(filepath)}&tag=${encodeURIComponent(tag)}`, {
      method: 'DELETE',
    });
  }

  async searchTags(directory: string, tag: string): Promise<{ tag: string; files: string[]; count: number }> {
    return this.request(`/tags/search?directory=${encodeURIComponent(directory)}&tag=${encodeURIComponent(tag)}`);
  }

  async getAllTags(directory: string): Promise<Record<string, number>> {
    return this.request(`/tags/all?directory=${encodeURIComponent(directory)}`);
  }

  // ─── File Copilot ─────────────────────────────────────────────────────

  async copilotChat(message: string, conversationId?: string): Promise<CopilotResponse> {
    return this.request('/copilot/chat', {
      method: 'POST',
      body: JSON.stringify({ message, conversation_id: conversationId }),
    });
  }

  async copilotIndex(filepaths: string[]): Promise<{ indexed: number }> {
    return this.request('/copilot/index', {
      method: 'POST',
      body: JSON.stringify(filepaths),
    });
  }

  async copilotSummarize(filepath: string): Promise<{ summary: string }> {
    return this.request(`/copilot/summarize?filepath=${encodeURIComponent(filepath)}`, {
      method: 'POST',
    });
  }

  async listConversations(): Promise<{ id: string; title: string; messages: number; files: number }[]> {
    return this.request('/copilot/conversations');
  }

  // ─── Medical NER ──────────────────────────────────────────────────────

  async extractEntities(text: string, useLlm = false): Promise<NerResult> {
    return this.request('/ner/extract', {
      method: 'POST',
      body: JSON.stringify({ text, use_llm: useLlm }),
    });
  }

  // ─── Multimodal Processing ────────────────────────────────────────────

  async processImage(filepath: string, fixScan = true): Promise<ProcessResult> {
    return this.request(`/process/image?filepath=${encodeURIComponent(filepath)}&fix_scan=${fixScan}`, {
      method: 'POST',
    });
  }

  async processAudio(filepath: string): Promise<ProcessResult> {
    return this.request(`/process/audio?filepath=${encodeURIComponent(filepath)}`, {
      method: 'POST',
    });
  }

  async processVideo(filepath: string): Promise<ProcessResult> {
    return this.request(`/process/video?filepath=${encodeURIComponent(filepath)}`, {
      method: 'POST',
    });
  }

  async processDocument(filepath: string): Promise<ProcessResult> {
    return this.request(`/process/document?filepath=${encodeURIComponent(filepath)}`, {
      method: 'POST',
    });
  }

  async uploadAndProcess(file: File): Promise<ProcessResult> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${this.baseUrl}/process/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) throw new Error(`Upload error: ${response.status}`);
    return response.json();
  }

  // ─── Organize ─────────────────────────────────────────────────────────

  async organize(sourceDir: string, targetDir = '', dryRun = true, moveFiles = false): Promise<{
    organized: Record<string, string[]>;
    dry_run: boolean;
    total_files: number;
    errors: string[];
  }> {
    return this.request('/organize', {
      method: 'POST',
      body: JSON.stringify({ source_dir: sourceDir, target_dir: targetDir, dry_run: dryRun, move_files: moveFiles }),
    });
  }

  // ─── Stats ────────────────────────────────────────────────────────────

  async stats(): Promise<{ categories: string[]; version: string }> {
    return this.request('/stats');
  }

  // ─── WebSocket ────────────────────────────────────────────────────────

  createCopilotWebSocket(): WebSocket | null {
    try {
      const wsUrl = this.baseUrl.replace(/^http/, 'ws').replace(/\/api$/, '/api/copilot/ws');
      return new WebSocket(wsUrl);
    } catch {
      return null;
    }
  }
}

// Singleton instance
export const api = new IntelliFileAPI();

export default api;
