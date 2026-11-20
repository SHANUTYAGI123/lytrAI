import React from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface SimulationToolbarProps {
  activeSimulation: string;
  onSelectSimulation: (val: string) => void;
  onClose: () => void;
}

export const SimulationToolbar: React.FC<SimulationToolbarProps> = ({
  activeSimulation,
  onSelectSimulation,
  onClose,
}) => {
  const presets = [
    { label: 'Normal (None)', value: '' },
    { label: 'Key 1 Rate Limit (429)', value: 'key_1=429' },
    { label: 'Key 1 Server Error (500)', value: 'key_1=500' },
    { label: 'All Keys Fail (*=429)', value: '*=429' },
  ];

  return (
    <div className="bg-amber-950/40 border-b border-amber-500/30 px-4 py-3 text-xs text-amber-200">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
          <span className="font-semibold text-amber-300">Failover Test Hook</span>
          <span className="text-amber-400/80 hidden md:inline">
            Injects <code className="bg-amber-900/50 px-1 py-0.5 rounded text-amber-200">X-Simulate-Failure</code> header into requests
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {presets.map((p) => {
            const isSelected = activeSimulation === p.value;
            return (
              <button
                key={p.label}
                type="button"
                onClick={() => onSelectSimulation(p.value)}
                className={`px-2.5 py-1 rounded-md font-mono text-[11px] transition-all border ${
                  isSelected
                    ? 'bg-amber-500 text-slate-950 font-bold border-amber-400 shadow-sm shadow-amber-500/40'
                    : 'bg-slate-900/80 text-amber-200/90 border-amber-500/30 hover:bg-slate-900 hover:border-amber-400'
                }`}
              >
                {p.label}
              </button>
            );
          })}

          <div className="flex items-center gap-1.5 ml-1">
            <input
              type="text"
              placeholder="e.g. key_1=429,key_2=500"
              value={activeSimulation}
              onChange={(e) => onSelectSimulation(e.target.value)}
              className="bg-slate-900/90 border border-amber-500/40 rounded px-2 py-0.5 text-xs text-amber-200 font-mono w-44 focus:outline-none focus:ring-1 focus:ring-amber-400"
            />
            <button
              onClick={onClose}
              className="p-1 hover:text-white transition-colors"
              title="Close toolbar"
            >
              <X className="h-4 w-4 text-amber-400" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
