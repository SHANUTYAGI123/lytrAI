import { useState } from 'react';
import type { FC } from 'react';
import { Bot, RefreshCw, Copy, Check, ShieldAlert, Cpu } from 'lucide-react';
import type { HealthResponse } from '../types';

interface NavbarProps {
  sessionId: string;
  onNewSession: () => void;
  health: HealthResponse | null;
  healthLoading: boolean;
  systemPromptOpen: boolean;
  onToggleSystemPrompt: () => void;
  simulationOpen: boolean;
  onToggleSimulation: () => void;
  activeSimulation: string;
}

export const Navbar: FC<NavbarProps> = ({
  sessionId,
  onNewSession,
  health,
  healthLoading,
  systemPromptOpen,
  onToggleSystemPrompt,
  simulationOpen,
  onToggleSimulation,
  activeSimulation,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopySession = () => {
    navigator.clipboard.writeText(sessionId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <header className="sticky top-0 z-30 w-full border-b border-slate-800 bg-slate-900/90 backdrop-blur-md">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between gap-4">
        {/* Brand / Logo */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 p-0.5 shadow-lg shadow-indigo-500/20">
            <div className="h-full w-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <Bot className="h-5 w-5 text-indigo-400" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg tracking-tight text-white">Lyftr AI</span>
              <span className="text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                Gateway
              </span>
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">
              Key Failover &amp; Response Caching
            </p>
          </div>
        </div>

        {/* Center / Session Info */}
        <div className="flex items-center gap-2 bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-300">
          <span className="text-slate-500">Session:</span>
          <span className="font-mono text-indigo-300 max-w-[120px] sm:max-w-[160px] truncate">
            {sessionId}
          </span>
          <button
            onClick={handleCopySession}
            title="Copy Session ID"
            className="p-1 hover:text-white transition-colors cursor-pointer"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
          </button>
        </div>

        {/* Right actions */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Health Badge */}
          <div
            className={`hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
              healthLoading
                ? 'bg-slate-800 text-slate-400 border-slate-700'
                : health?.status === 'ok'
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                healthLoading
                  ? 'bg-slate-500 animate-pulse'
                  : health?.status === 'ok'
                  ? 'bg-emerald-400'
                  : 'bg-rose-400'
              }`}
            />
            <span>
              {healthLoading
                ? 'Checking...'
                : health?.status === 'ok'
                ? `Pool: ${health.keys_configured} keys | Cache: ON`
                : 'Offline'}
            </span>
          </div>

          {/* System Prompt Toggle */}
          <button
            onClick={onToggleSystemPrompt}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1.5 cursor-pointer ${
              systemPromptOpen
                ? 'bg-indigo-600 text-white border-indigo-500'
                : 'bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-800'
            }`}
          >
            <Cpu className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">System Prompt</span>
          </button>

          {/* Failover Simulation Toggle */}
          <button
            onClick={onToggleSimulation}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1.5 cursor-pointer ${
              activeSimulation
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 animate-pulse'
                : simulationOpen
                ? 'bg-slate-700 text-white border-slate-600'
                : 'bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-800'
            }`}
          >
            <ShieldAlert className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Failover Test</span>
          </button>

          {/* New Chat Button */}
          <button
            onClick={onNewSession}
            title="Start New Chat Session"
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white transition-all shadow-sm shadow-indigo-600/30 flex items-center gap-1.5 cursor-pointer"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>New Chat</span>
          </button>
        </div>
      </div>
    </header>
  );
};
