export type ResolutionSource = 'LIVE_INFERENCE' | 'LLM_CACHE';

export interface MessageMetadata {
  resolution_source: ResolutionSource;
  model: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  key_id?: string | null;
  fallback_attempts?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'error';
  content: string;
  metadata?: MessageMetadata;
  createdAt: Date;
  isError?: boolean;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  metadata: MessageMetadata;
}

export interface HealthResponse {
  status: string;
  keys_configured: number;
  cache_enabled: boolean;
}

export interface SessionHistoryItem {
  role: 'user' | 'assistant';
  content: string;
  metadata?: {
    resolution_source: ResolutionSource;
    input_tokens: number;
    output_tokens: number;
  };
}

export interface SessionHistoryResponse {
  session_id: string;
  messages: SessionHistoryItem[];
}
