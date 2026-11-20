import type { FC } from 'react';
import { Bot, User, Zap, Sparkles, Clock, ArrowDownRight, ArrowUpRight, ShieldCheck, AlertCircle } from 'lucide-react';
import type { ChatMessage } from '../types';

interface MessageItemProps {
  message: ChatMessage;
}

export const MessageItem: FC<MessageItemProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const isError = message.role === 'error' || message.isError;

  if (isError) {
    return (
      <div className="flex items-start gap-3 my-4">
        <div className="h-8 w-8 rounded-lg bg-rose-500/20 border border-rose-500/30 flex items-center justify-center shrink-0">
          <AlertCircle className="h-4 w-4 text-rose-400" />
        </div>
        <div className="flex-1 bg-rose-950/40 border border-rose-500/30 rounded-2xl p-4 text-sm text-rose-200 shadow-sm">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-rose-300">Request Error</span>
          </div>
          <div className="font-mono text-xs text-rose-300/90 whitespace-pre-wrap">
            {message.content}
          </div>
        </div>
      </div>
    );
  }

  if (isUser) {
    return (
      <div className="flex items-start justify-end gap-3 my-4">
        <div className="max-w-[85%] sm:max-w-[75%] bg-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm shadow-md shadow-indigo-600/10">
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        </div>
        <div className="h-8 w-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
          <User className="h-4 w-4 text-slate-300" />
        </div>
      </div>
    );
  }

  // Assistant Message Container
  const meta = message.metadata;
  const isCached = meta?.resolution_source === 'LLM_CACHE';

  return (
    <div className="flex items-start gap-3 my-4" data-testid="assistant-message">
      <div className="h-8 w-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0 mt-0.5">
        <Bot className="h-4 w-4 text-indigo-400" />
      </div>

      <div className="flex-1 min-w-0 bg-slate-900/90 border border-slate-800 rounded-2xl rounded-tl-sm p-4 shadow-sm text-sm">
        {/* Reply Body */}
        <div className="text-slate-100 whitespace-pre-wrap leading-relaxed mb-3">
          {message.content}
        </div>

        {/* Metadata Footer */}
        {meta && (
          <div className="pt-3 border-t border-slate-800/80 flex flex-wrap items-center gap-2 sm:gap-3 text-xs">
            {/* Resolution Source */}
            <div
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full font-medium border ${
                isCached
                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                  : 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30'
              }`}
            >
              {isCached ? (
                <Zap className="h-3 w-3 text-emerald-400" />
              ) : (
                <Sparkles className="h-3 w-3 text-cyan-400" />
              )}
              <span data-testid="meta-source" className="font-mono uppercase font-semibold">
                {meta.resolution_source}
              </span>
            </div>

            {/* Model Used */}
            <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-slate-950/80 border border-slate-800 text-slate-300">
              <span className="text-slate-500">model:</span>
              <span data-testid="meta-model" className="font-mono text-indigo-300">
                {meta.model}
              </span>
            </div>

            {/* Latency */}
            <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-slate-950/80 border border-slate-800 text-slate-300">
              <Clock className="h-3 w-3 text-slate-400" />
              <span data-testid="meta-latency" className="font-mono font-medium text-amber-300">
                {meta.latency_ms} ms
              </span>
            </div>

            {/* Tokens */}
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-slate-950/80 border border-slate-800 text-slate-300">
              <div className="flex items-center gap-1" title="Input Tokens">
                <ArrowDownRight className="h-3 w-3 text-sky-400" />
                <span className="text-slate-500">in:</span>
                <span data-testid="meta-input-tokens" className="font-mono font-medium text-sky-300">
                  {meta.input_tokens}
                </span>
              </div>
              <span className="text-slate-700">|</span>
              <div className="flex items-center gap-1" title="Output Tokens">
                <ArrowUpRight className="h-3 w-3 text-violet-400" />
                <span className="text-slate-500">out:</span>
                <span data-testid="meta-output-tokens" className="font-mono font-medium text-violet-300">
                  {meta.output_tokens}
                </span>
              </div>
            </div>

            {/* Key ID (if present and not null) */}
            {meta.key_id && (
              <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-300">
                <ShieldCheck className="h-3 w-3 text-indigo-400" />
                <span className="font-mono text-[11px]">{meta.key_id}</span>
              </div>
            )}

            {/* Fallback indicator */}
            {meta.fallback_attempts !== undefined && meta.fallback_attempts > 0 && (
              <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300">
                <span className="font-mono text-[11px]">
                  {meta.fallback_attempts} fallback {meta.fallback_attempts === 1 ? 'attempt' : 'attempts'}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
