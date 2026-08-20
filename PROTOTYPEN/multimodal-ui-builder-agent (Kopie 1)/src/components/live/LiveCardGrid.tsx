"use client";

import React from "react";
import { Sparkles, Eye, Mic, Code2, RefreshCw, Cpu, CheckCircle } from "lucide-react";

export interface LiveCardGridProps {
  variant?: "modern" | "compact" | "minimal";
  columns?: 2 | 3 | 4;
  onSelectElement?: (elData: { selector: string; componentName: string; label: string; rect: DOMRect }) => void;
  selectedSelector?: string | null;
}

export function LiveCardGrid({
  variant = "modern",
  columns = 3,
  onSelectElement,
  selectedSelector,
}: LiveCardGridProps) {
  const isSelected = selectedSelector === '[data-component="LiveCardGrid"]';

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    e.stopPropagation();
    if (onSelectElement) {
      const rect = e.currentTarget.getBoundingClientRect();
      onSelectElement({
        selector: '[data-component="LiveCardGrid"]',
        componentName: "LiveCardGrid",
        label: "Feature Cards Grid Component",
        rect,
      });
    }
  };

  const cards = [
    {
      icon: Eye,
      title: "1. Multimodale Vision",
      desc: "Erkennt Screenshots, DOM Bounding Boxes und Accessibility-Trees zur prazisen Element-Zuordnung.",
      badge: "Vision AI",
      color: "from-blue-500 to-indigo-600",
    },
    {
      icon: Mic,
      title: "2. Liquid Audio Channel",
      desc: "Nimmt Sprachbefehle entgegen ('Mach diesen Bereich uebersichtlicher') und gibt Feedback via TTS.",
      badge: "Speech STT/TTS",
      color: "from-purple-500 to-pink-600",
    },
    {
      icon: Code2,
      title: "3. Smart Code Patching",
      desc: "Erzeugt 3 konkrete Änderungsvorschlaege (A, B, C) mit Risikobewertung und modifiziert direkt den Code.",
      badge: "NFM Code Engine",
      color: "from-emerald-500 to-teal-600",
    },
  ];

  return (
    <div
      data-component="LiveCardGrid"
      onClick={handleClick}
      className={`relative cursor-pointer transition-all duration-300 rounded-2xl border ${
        isSelected
          ? "ring-4 ring-indigo-500 ring-offset-2 border-indigo-500 shadow-2xl"
          : "hover:border-indigo-300 border-slate-200"
      } ${
        variant === "compact"
          ? "p-4 bg-slate-900"
          : variant === "minimal"
          ? "p-6 bg-white shadow-sm"
          : "p-6 bg-slate-900 text-white shadow-lg"
      }`}
    >
      {isSelected && (
        <span className="absolute -top-3 left-4 bg-indigo-600 text-white text-xs px-2.5 py-0.5 rounded-full font-mono font-medium tracking-wide shadow-md flex items-center gap-1 z-20">
          <Sparkles className="w-3 h-3" /> AI Target: LiveCardGrid.tsx
        </span>
      )}

      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-indigo-400" /> Kernel Module & Fähigkeiten
          </h3>
          <p className="text-xs text-slate-400">Integrierte Liquid NFM/LFM Agent Bausteine</p>
        </div>
        <span className="text-xs px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
          {columns} Spalten Modus
        </span>
      </div>

      <div className={`grid grid-cols-1 md:grid-cols-${columns} gap-4`}>
        {cards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div
              key={idx}
              className="group p-4 rounded-xl bg-slate-800/80 border border-slate-700/80 hover:border-indigo-500/50 transition duration-200"
            >
              <div className="flex items-center justify-between mb-3">
                <div
                  className={`w-9 h-9 rounded-lg bg-gradient-to-tr ${card.color} flex items-center justify-center text-white shadow-md`}
                >
                  <Icon className="w-5 h-5" />
                </div>
                <span className="text-[10px] uppercase tracking-wider font-semibold text-indigo-300 bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-800/50">
                  {card.badge}
                </span>
              </div>
              <h4 className="text-sm font-semibold text-white group-hover:text-indigo-300 transition">
                {card.title}
              </h4>
              <p className="mt-1 text-xs text-slate-400 leading-relaxed">{card.desc}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
