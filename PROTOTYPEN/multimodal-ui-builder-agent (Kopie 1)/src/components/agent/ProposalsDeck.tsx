"use client";

import React from "react";
import { Sparkles, CheckCircle2, AlertTriangle, ArrowRight, Code2, Layers, Check } from "lucide-react";

export interface ProposalData {
  id: string;
  optionKey: string; // 'A' | 'B' | 'C'
  title: string;
  description: string;
  stylePreset: string;
  affectedComponent: string;
  affectedFile: string;
  expectedVisualChange: string;
  technicalChange: string;
  risk: string;
  proposedCode: string;
  diffSummary: string;
  isApplied?: boolean;
}

export interface ProposalsDeckProps {
  proposals: ProposalData[];
  onApplyProposal: (proposalId: string) => void;
  isApplying: boolean;
  activeAppliedId: string | null;
}

export function ProposalsDeck({
  proposals,
  onApplyProposal,
  isApplying,
  activeAppliedId,
}: ProposalsDeckProps) {
  if (!proposals || proposals.length === 0) return null;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-2xl space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              Liquid AI Änderungsvorschläge
              <span className="text-xs font-normal normal-case text-indigo-300 bg-indigo-950 px-2 py-0.5 rounded border border-indigo-800">
                3 Alternativen generiert
              </span>
            </h3>
            <p className="text-xs text-slate-400">
              Wähle einen Vorschlag per Klick oder sag z.B. <strong className="text-indigo-300 font-mono">"Nimm B"</strong>
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {proposals.map((prop) => {
          const isApplied = prop.isApplied || activeAppliedId === prop.id;

          return (
            <div
              key={prop.id || prop.optionKey}
              className={`relative rounded-2xl p-4 border transition-all duration-300 flex flex-col justify-between ${
                isApplied
                  ? "bg-gradient-to-b from-indigo-950 to-slate-900 border-indigo-500 ring-2 ring-indigo-500/50 shadow-xl"
                  : "bg-slate-950/90 border-slate-800 hover:border-slate-700"
              }`}
            >
              {isApplied && (
                <div className="absolute -top-3 right-4 bg-emerald-600 text-white text-[10px] font-bold px-2.5 py-0.5 rounded-full shadow flex items-center gap-1">
                  <Check className="w-3 h-3" /> AKTIV ANGEWENDET
                </div>
              )}

              <div className="space-y-3">
                {/* Header Badge */}
                <div className="flex items-center justify-between">
                  <span className="h-7 w-7 rounded-lg bg-indigo-600 font-bold text-white text-xs flex items-center justify-center shadow">
                    {prop.optionKey}
                  </span>
                  <span
                    className={`text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded border ${
                      prop.risk === "low"
                        ? "bg-emerald-950/80 text-emerald-300 border-emerald-800/80"
                        : "bg-amber-950/80 text-amber-300 border-amber-800/80"
                    }`}
                  >
                    Risiko: {prop.risk.toUpperCase()}
                  </span>
                </div>

                <div>
                  <h4 className="text-sm font-bold text-slate-100">{prop.title}</h4>
                  <p className="mt-1 text-xs text-slate-400 leading-relaxed">{prop.description}</p>
                </div>

                {/* Details */}
                <div className="space-y-1.5 text-[11px] bg-slate-900/80 p-2.5 rounded-xl border border-slate-800/80">
                  <div className="text-slate-300">
                    <strong className="text-slate-400 font-medium">Visuell:</strong> {prop.expectedVisualChange}
                  </div>
                  <div className="text-slate-400 font-mono text-[10px]">
                    <strong>Datei:</strong> {prop.affectedFile}
                  </div>
                </div>

                {/* Code Diff Preview */}
                <div className="bg-slate-950 p-2 rounded-lg font-mono text-[10px] text-emerald-400/90 border border-slate-800 whitespace-pre-wrap">
                  {prop.diffSummary}
                </div>
              </div>

              {/* Action Button */}
              <div className="pt-4 mt-2">
                <button
                  onClick={() => onApplyProposal(prop.id)}
                  disabled={isApplying || isApplied}
                  className={`w-full py-2.5 px-3 rounded-xl font-bold text-xs transition flex items-center justify-center gap-2 shadow-lg ${
                    isApplied
                      ? "bg-emerald-600/20 text-emerald-300 border border-emerald-500/30 cursor-default"
                      : "bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white"
                  }`}
                >
                  {isApplied ? (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Angewendet
                    </>
                  ) : (
                    <>
                      <span>Option {prop.optionKey} Auswählen</span> <ArrowRight className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
