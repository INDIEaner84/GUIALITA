"use client";

import React from "react";
import { Sparkles, Eye, Target, FileCode, CheckCircle2, AlertCircle } from "lucide-react";

export interface TargetElementData {
  id: string;
  selector: string;
  componentName: string;
  filePath: string;
  boundingBox: { x: number; y: number; width: number; height: number };
  accessibilityLabel: string;
  detectedReason?: string;
  codeSnippet?: string;
}

export interface VisionOverlayProps {
  target: TargetElementData | null;
  onSelectComponent: (selector: string) => void;
  selectedSelector: string | null;
}

export function VisionOverlay({ target, onSelectComponent, selectedSelector }: VisionOverlayProps) {
  const componentsList = [
    { selector: '[data-component="LiveHeader"]', name: "LiveHeader.tsx", label: "Header Toolbar" },
    { selector: '[data-component="LiveHero"]', name: "LiveHero.tsx", label: "Hero Call-to-Action" },
    { selector: '[data-component="LiveCardGrid"]', name: "LiveCardGrid.tsx", label: "Feature Cards Grid" },
    { selector: '[data-component="LiveActionSection"]', name: "LiveActionSection.tsx", label: "Diagnostics Console" },
  ];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400">
            <Eye className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Vision & DOM Element Inspector
            </h3>
            <p className="text-[11px] text-slate-400">
              Klicke ein Element im Vorschau-Bereich an oder wähle es unten aus.
            </p>
          </div>
        </div>

        {target && (
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-emerald-950 text-emerald-300 border border-emerald-800 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Vision Linked
          </span>
        )}
      </div>

      {/* Target Selector Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {componentsList.map((comp) => {
          const isSelected = selectedSelector === comp.selector;
          return (
            <button
              key={comp.selector}
              onClick={() => onSelectComponent(comp.selector)}
              className={`p-2.5 rounded-xl text-left border transition flex flex-col justify-between ${
                isSelected
                  ? "bg-indigo-950 border-indigo-500 text-white shadow-lg ring-2 ring-indigo-500/50"
                  : "bg-slate-950/80 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700"
              }`}
            >
              <span className="text-[10px] font-mono opacity-60 flex items-center gap-1">
                <FileCode className="w-3 h-3" /> {comp.name}
              </span>
              <span className="text-xs font-bold truncate mt-1">{comp.label}</span>
            </button>
          );
        })}
      </div>

      {/* Detailed Target Card */}
      {target ? (
        <div className="bg-slate-950 border border-indigo-900/50 rounded-xl p-3 text-xs space-y-2 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/5 blur-2xl rounded-full pointer-events-none"></div>

          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center gap-2 text-indigo-300 font-bold">
              <Target className="w-4 h-4 text-indigo-400 animate-pulse" />
              <span>Identifiziertes Ziel: {target.componentName}</span>
            </div>
            <span className="font-mono text-[10px] text-slate-500">{target.filePath}</span>
          </div>

          <p className="text-slate-300 text-[11px] leading-relaxed">{target.detectedReason}</p>

          <div className="flex flex-wrap gap-2 text-[10px] font-mono text-slate-400 bg-slate-900/80 p-2 rounded-lg border border-slate-800">
            <span>Selector: <strong className="text-indigo-300">{target.selector}</strong></span>
            <span>•</span>
            <span>
              Rect: X={Math.round(target.boundingBox.x)}, Y={Math.round(target.boundingBox.y)}, W={Math.round(target.boundingBox.width)}, H={Math.round(target.boundingBox.height)}
            </span>
          </div>
        </div>
      ) : (
        <div className="p-3 bg-slate-950/50 rounded-xl border border-dashed border-slate-800 text-slate-500 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-slate-600 shrink-0" />
          <span>Noch kein Element gewählt. Sag z.B. "Der Bereich hier gefällt mir nicht" oder klicke auf das UI.</span>
        </div>
      )}
    </div>
  );
}
