"use client";

import React from "react";
import { Activity, Mic, Eye, Sparkles, Code, ShieldCheck, Terminal, User, Bot } from "lucide-react";

export interface LogItem {
  id: string;
  type: string; // 'speech' | 'vision' | 'proposal' | 'code' | 'reload' | 'verify' | 'desktop'
  speaker: string; // 'user' | 'liquid_agent' | 'system'
  message: string;
  timestamp: string;
  metadata?: any;
}

export interface SessionTimelineProps {
  logs: LogItem[];
  onRefreshLogs?: () => void;
}

export function SessionTimeline({ logs, onRefreshLogs }: SessionTimelineProps) {
  const getIcon = (type: string) => {
    switch (type) {
      case "speech":
        return <Mic className="w-3.5 h-3.5 text-indigo-400" />;
      case "vision":
        return <Eye className="w-3.5 h-3.5 text-blue-400" />;
      case "proposal":
        return <Sparkles className="w-3.5 h-3.5 text-purple-400" />;
      case "code":
        return <Code className="w-3.5 h-3.5 text-amber-400" />;
      case "verify":
        return <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />;
      default:
        return <Activity className="w-3.5 h-3.5 text-slate-400" />;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-2xl space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Multimodaler Session-Verlauf & Memory
            </h3>
            <p className="text-xs text-slate-400">Protokoll aller Interaktionen, Erkennungen & Code-Änderungen</p>
          </div>
        </div>

        {onRefreshLogs && (
          <button
            onClick={onRefreshLogs}
            className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition"
          >
            Aktualisieren
          </button>
        )}
      </div>

      <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
        {logs.length === 0 ? (
          <div className="text-center py-8 text-xs text-slate-500">Noch keine Aktionen in dieser Sitzung.</div>
        ) : (
          logs.map((item) => (
            <div
              key={item.id}
              className={`p-3 rounded-xl border text-xs space-y-1 transition ${
                item.speaker === "user"
                  ? "bg-slate-950 border-indigo-900/60 ml-4"
                  : item.type === "verify"
                  ? "bg-emerald-950/40 border-emerald-900/60"
                  : "bg-slate-950 border-slate-800"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-bold">
                  {getIcon(item.type)}
                  <span className={item.speaker === "user" ? "text-indigo-300" : "text-slate-200"}>
                    {item.speaker === "user" ? "Benutzer (Sprache/Klick)" : "Liquid NFM Agent"}
                  </span>
                </div>
                <span className="text-[10px] text-slate-500 font-mono">
                  {new Date(item.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <p className="text-slate-300 pl-5 leading-relaxed">{item.message}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
