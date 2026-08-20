"use client";

import React from "react";
import { ShieldCheck, CheckCircle2, RefreshCw, Eye, Sparkles } from "lucide-react";

export interface VerificationData {
  status: string;
  expected: string;
  actual: string;
  passed: boolean;
  confidenceScore: number;
  timestamp: string;
}

export interface VerificationPanelProps {
  verification: VerificationData | null;
  onReVerify?: () => void;
}

export function VerificationPanel({ verification, onReVerify }: VerificationPanelProps) {
  if (!verification) return null;

  return (
    <div className="bg-slate-900 border border-emerald-900/60 rounded-2xl p-4 shadow-xl space-y-3">
      <div className="flex items-center justify-between border-b border-emerald-900/40 pb-2">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-400">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-300 flex items-center gap-2">
              Automatische Selbstüberprüfung & Reload
              <span className="text-[10px] bg-emerald-950 text-emerald-400 px-2 py-0.5 rounded border border-emerald-800">
                VERIFIED ({(verification.confidenceScore * 100).toFixed(0)}%)
              </span>
            </h3>
            <p className="text-[11px] text-slate-400">Vision verification after code patch & browser sync.</p>
          </div>
        </div>

        {onReVerify && (
          <button
            onClick={onReVerify}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs flex items-center gap-1 border border-slate-700"
          >
            <RefreshCw className="w-3 h-3" />
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
        <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 space-y-1">
          <div className="text-[10px] text-slate-500 uppercase font-bold">EXPECTED VISUAL STATE</div>
          <div className="text-slate-200 text-xs font-sans">{verification.expected}</div>
        </div>

        <div className="bg-slate-950 p-3 rounded-xl border border-emerald-900/50 space-y-1">
          <div className="text-[10px] text-emerald-400 uppercase font-bold flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> ACTUAL VISUAL MATCH
          </div>
          <div className="text-emerald-200 text-xs font-sans">{verification.actual}</div>
        </div>
      </div>
    </div>
  );
}
