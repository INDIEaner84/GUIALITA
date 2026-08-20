"use client";

import React from "react";
import { Sparkles, Terminal, Activity, CheckCircle, ShieldAlert, Cpu } from "lucide-react";

export interface LiveActionSectionProps {
  variant?: "modern" | "compact" | "minimal";
  onSelectElement?: (elData: { selector: string; componentName: string; label: string; rect: DOMRect }) => void;
  selectedSelector?: string | null;
}

export function LiveActionSection({
  variant = "modern",
  onSelectElement,
  selectedSelector,
}: LiveActionSectionProps) {
  const isSelected = selectedSelector === '[data-component="LiveActionSection"]';

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    e.stopPropagation();
    if (onSelectElement) {
      const rect = e.currentTarget.getBoundingClientRect();
      onSelectElement({
        selector: '[data-component="LiveActionSection"]',
        componentName: "LiveActionSection",
        label: "Live System Diagnostics & Status Console Component",
        rect,
      });
    }
  };

  return (
    <div
      data-component="LiveActionSection"
      onClick={handleClick}
      className={`relative cursor-pointer transition-all duration-300 rounded-2xl border ${
        isSelected
          ? "ring-4 ring-indigo-500 ring-offset-2 border-indigo-500 shadow-2xl"
          : "hover:border-indigo-300 border-slate-200"
      } ${
        variant === "compact"
          ? "p-4 bg-slate-900 text-white"
          : variant === "minimal"
          ? "p-5 bg-white text-slate-900 border-slate-300 shadow-sm"
          : "p-6 bg-slate-950 text-emerald-400 border-slate-800 font-mono shadow-xl"
      }`}
    >
      {isSelected && (
        <span className="absolute -top-3 left-4 bg-indigo-600 text-white text-xs px-2.5 py-0.5 rounded-full font-mono font-medium tracking-wide shadow-md flex items-center gap-1 z-20">
          <Sparkles className="w-3 h-3" /> AI Target: LiveActionSection.tsx
        </span>
      )}

      <div className="flex items-center justify-between border-b border-emerald-900/50 pb-3 mb-3">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-bold text-emerald-300 uppercase tracking-widest">
            Liquid Terminal Diagnostics
          </span>
        </div>
        <span className="inline-flex items-center gap-1.5 text-[11px] text-emerald-400 bg-emerald-950/80 px-2.5 py-0.5 rounded-full border border-emerald-800/60">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> SYSTEM HEALTH 100%
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
        <div className="bg-emerald-950/30 p-3 rounded-lg border border-emerald-900/40">
          <div className="text-emerald-500 text-[10px] uppercase font-bold">NFM Model Latency</div>
          <div className="text-lg font-bold text-white mt-1">14.2 ms</div>
          <div className="text-[10px] text-emerald-400/70 mt-0.5">Real-time local neural inference</div>
        </div>
        <div className="bg-emerald-950/30 p-3 rounded-lg border border-emerald-900/40">
          <div className="text-emerald-500 text-[10px] uppercase font-bold">Vision Precision</div>
          <div className="text-lg font-bold text-white mt-1">99.4 %</div>
          <div className="text-[10px] text-emerald-400/70 mt-0.5">DOM + Bounding box matching</div>
        </div>
        <div className="bg-emerald-950/30 p-3 rounded-lg border border-emerald-900/40">
          <div className="text-emerald-500 text-[10px] uppercase font-bold">HMR Hot Reload</div>
          <div className="text-lg font-bold text-white mt-1">Ready</div>
          <div className="text-[10px] text-emerald-400/70 mt-0.5">Instant UI re-sync pipeline</div>
        </div>
      </div>
    </div>
  );
}
