import { useState, useEffect, useRef } from 'react';
import { Navbar } from './components/Navbar';
import { SimulationToolbar } from './components/SimulationToolbar';
import { MessageItem } from './components/MessageItem';
import { ChatInput } from './components/ChatInput';
import type { ChatMessage, HealthResponse } from './types';
import { fetchHealth, postChatMessage } from './api';
import { Bot, Sparkles, Zap, ShieldAlert, Cpu } from 'lucide-react';

// Generates a unique session id on each page load, e.g. s-7f3a
const generateSessionId = (): string => {
  const rand = Math.random().toString(36).substring(2, 8);
  return `s-${rand}`;
};

export function App() {
  // A new session starts on each page load
  const [sessionId, setSessionId] = useState<string>(() => generateSessionId());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [systemPrompt, setSystemPrompt] = useState<string>('');
  const [activeSimulation, setActiveSimulation] = useState<string>('');
  const [simulationOpen, setSimulationOpen] = useState<boolean>(false);
  const [systemPromptOpen, setSystemPromptOpen] = useState<boolean>(false);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Check health on mount
  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        const h = await fetchHealth();
        if (mounted) {
          setHealth(h);
          setHealthLoading(false);
        }
      } catch {
        if (mounted) {
          setHealth(null);
          setHealthLoading(false);
        }
      }
    };
    check();
    const timer = setInterval(check, 15000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const handleNewSession = () => {
    const newId = generateSessionId();
    setSessionId(newId);
    setMessages([]);
  };

  const handleSendMessage = async (userText: string) => {
    const userMsg: ChatMessage = {
      id: `usr-${Date.now()}`,
      role: 'user',
      content: userText,
      createdAt: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const response = await postChatMessage(
        sessionId,
        userText,
        systemPrompt || undefined,
        activeSimulation || undefined
      );

      const assistantMsg: ChatMessage = {
        id: `asst-${Date.now()}`,
        role: 'assistant',
        content: response.reply,
        metadata: response.metadata,
        createdAt: new Date(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      // Readable error message in chat, never a blank screen
      const errorContent = err.message || 'An unexpected error occurred.';
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: 'error',
        content: errorContent,
        createdAt: new Date(),
        isError: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 font-sans">
      <Navbar
        sessionId={sessionId}
        onNewSession={handleNewSession}
        health={health}
        healthLoading={healthLoading}
        systemPromptOpen={systemPromptOpen}
        onToggleSystemPrompt={() => setSystemPromptOpen((prev) => !prev)}
        simulationOpen={simulationOpen}
        onToggleSimulation={() => setSimulationOpen((prev) => !prev)}
        activeSimulation={activeSimulation}
      />

      {/* Failover Test Hook Toolbar */}
      {simulationOpen && (
        <SimulationToolbar
          activeSimulation={activeSimulation}
          onSelectSimulation={setActiveSimulation}
          onClose={() => setSimulationOpen(false)}
        />
      )}

      {/* System Prompt Drawer / Input */}
      {systemPromptOpen && (
        <div className="bg-slate-900 border-b border-slate-800 px-4 py-3">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-center gap-2 mb-2 text-xs font-semibold text-indigo-400">
              <Cpu className="h-4 w-4" />
              <span>Session System Prompt (Optional)</span>
            </div>
            <textarea
              data-testid="system-prompt-input"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="e.g. You are a senior software architect with deep expertise in distributed systems..."
              rows={2}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-sans"
            />
          </div>
        </div>
      )}

      {/* Active simulation warning banner */}
      {activeSimulation && !simulationOpen && (
        <div className="bg-amber-950/60 border-b border-amber-500/30 px-4 py-2 text-xs text-amber-300 flex items-center justify-between">
          <div className="max-w-4xl mx-auto flex items-center gap-2 w-full">
            <ShieldAlert className="h-4 w-4 text-amber-400 shrink-0" />
            <span>
              Simulation active: <code className="font-mono bg-amber-900/60 px-1 py-0.5 rounded">{activeSimulation}</code>
            </span>
            <button
              onClick={() => setActiveSimulation('')}
              className="ml-auto underline hover:text-white cursor-pointer"
            >
              Reset to Normal
            </button>
          </div>
        </div>
      )}

      {/* Main Chat Area */}
      <main className="flex-1 max-w-4xl w-full mx-auto p-4 flex flex-col justify-between">
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8 mt-12 sm:mt-20">
              <div className="h-16 w-16 rounded-2xl bg-gradient-to-tr from-indigo-500 to-cyan-400 p-0.5 shadow-xl shadow-indigo-500/20 mb-6">
                <div className="h-full w-full bg-slate-950 rounded-[14px] flex items-center justify-center">
                  <Bot className="h-8 w-8 text-indigo-400" />
                </div>
              </div>

              <h2 className="text-2xl font-bold tracking-tight text-white mb-2">
                Lyftr AI Chatbot
              </h2>
              <p className="text-sm text-slate-400 max-w-md mb-8 leading-relaxed">
                Featuring multi-key automated failover and LiteLLM response caching.
                Every request tracks latency, exact token usage, and resolution source.
              </p>

              {/* Quick Prompt Suggestions */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full text-left">
                <button
                  onClick={() => handleSendMessage('What is the capital of France?')}
                  className="p-3 rounded-xl bg-slate-900/80 hover:bg-slate-900 border border-slate-800 hover:border-indigo-500/40 text-xs transition-all text-slate-300 group cursor-pointer"
                >
                  <div className="flex items-center gap-2 font-medium text-slate-200 mb-1 group-hover:text-indigo-400">
                    <Sparkles className="h-3.5 w-3.5" />
                    <span>Test Caching (1st message)</span>
                  </div>
                  <span className="text-slate-500">
                    Send "What is the capital of France?" to see LIVE_INFERENCE, then send again for LLM_CACHE!
                  </span>
                </button>

                <button
                  onClick={() => {
                    setActiveSimulation('key_1=429');
                    setSimulationOpen(true);
                    handleSendMessage('Explain how automatic key failover works.');
                  }}
                  className="p-3 rounded-xl bg-slate-900/80 hover:bg-slate-900 border border-slate-800 hover:border-amber-500/40 text-xs transition-all text-slate-300 group cursor-pointer"
                >
                  <div className="flex items-center gap-2 font-medium text-slate-200 mb-1 group-hover:text-amber-400">
                    <Zap className="h-3.5 w-3.5" />
                    <span>Test Failover (key_1=429)</span>
                  </div>
                  <span className="text-slate-500">
                    Simulates 429 on key_1 and verifies seamless fallback to key_2!
                  </span>
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4 pb-4">
              {messages.map((msg) => (
                <MessageItem key={msg.id} message={msg} />
              ))}

              {isLoading && (
                <div className="flex items-start gap-3 my-4">
                  <div className="h-8 w-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
                    <Bot className="h-4 w-4 text-indigo-400 animate-pulse" />
                  </div>
                  <div className="bg-slate-900/90 border border-slate-800 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-2">
                    <div className="h-2 w-2 bg-indigo-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                    <div className="h-2 w-2 bg-indigo-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                    <div className="h-2 w-2 bg-indigo-400 rounded-full animate-bounce" />
                    <span className="text-xs text-slate-400 ml-2">Generating response...</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Bottom Input Area */}
        <div className="sticky bottom-0 pt-2 pb-4 bg-gradient-to-t from-slate-950 via-slate-950 to-transparent">
          <ChatInput onSendMessage={handleSendMessage} disabled={isLoading} />
        </div>
      </main>
    </div>
  );
}

export default App;
