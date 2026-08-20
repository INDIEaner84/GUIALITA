"use client";

import React from "react";
import { Sparkles, Mic, Eye, Code, Monitor, RefreshCw, Volume2, VolumeX, ShieldCheck, Activity } from "lucide-react";

export interface AgentHeaderProps {
  activeTab: "browser" | "desktop" | "logs";
  setActiveTab: (tab: "browser" | "desktop" | "logs") => void;
  isTtsEnabled: boolean;
  setIsTtsEnabled: (enabled: boolean) => void;
  agentStatus: "idle" | "analyzing" | "proposed" | "applying" | "verified" | "error";
  onResetSession: () => void;
}

export function AgentHeader({
  activeTab,
  setActiveTab,
  isTtsEnabled,
  setIsTtsEnabled,
  agentStatus,
  onResetSession,
}: AgentHeaderProps) {
  const getStatusBadge = () => {
    switch (agentStatus) {
      case "analyzing":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-500/20 text-amber-300 border border-amber-500/30 animate-pulse">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Vision & DOM Analyse...
          </span>
        );
      case "proposed":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" /> 3 Vorschläge Bereit
          </span>
        );
      case "applying":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-purple-500/20 text-purple-300 border border-purple-500/30 animate-pulse">
            <Code className="w-3.5 h-3.5 animate-spin" /> Code Patching & HMR...
          </span>
        );
      case "verified":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> Visuell Verifiziert
          </span>
        );
      case "error":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-red-500/20 text-red-300 border border-red-500/30">
            Fehler aufgetreten
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
            <Activity className="w-3.5 h-3.5 text-emerald-400" /> Bereit für Interaktion
          </span>
        );
    }
  };

  return (
    <header className="bg-slate-900 border-b border-slate-800 px-4 py-3 sticky top-0 z-40 shadow-lg">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Logo & Model Branding */}
        <div className="flex items-center gap-3 w-full md:w-auto justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-emerald-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-sm md:text-base font-bold text-white flex items-center gap-2">
                MUSCAL Multimodal UI Builder
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                  Liquid NFM/LFM
                </span>
              </h1>
              <p className="text-xs text-slate-400">Local Browser Agent & Code Synthesizer</p>
            </div>
          </div>

          <div className="md:hidden">{getStatusBadge()}</div>
        </div>

        {/* Center Mode Navigation Tabs */}
        <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab("browser")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${
              activeTab === "browser"
                ? "bg-indigo-600 text-white shadow"
                : "text-slate-400 hover:text-white hover:bg-slate-900"
            }`}
          >
            <Eye className="w-3.5 h-3.5" /> Browser UI Builder
          </button>
          <button
            onClick={() => setActiveTab("desktop")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${
              activeTab === "desktop"
                ? "bg-indigo-600 text-white shadow"
                : "text-slate-400 hover:text-white hover:bg-slate-900"
            }`}
          >
            <Monitor className="w-3.5 h-3.5" /> Desktop Control
          </button>
          <button
            onClick={() => setActiveTab("logs")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${
              activeTab === "logs"
                ? "bg-indigo-600 text-white shadow"
                : "text-slate-400 hover:text-white hover:bg-slate-900"
            }`}
          >
            <Activity className="w-3.5 h-3.5" /> Session Log
          </button>
        </div>

        {/* Right Controls: Audio TTS & Status */}
        <div className="hidden md:flex items-center gap-3">
          {getStatusBadge()}

          <button
            onClick={() => setIsTtsEnabled(!isTtsEnabled)}
            className={`p-2 rounded-lg border transition text-xs flex items-center gap-1.5 ${
              isTtsEnabled
                ? "bg-indigo-950 border-indigo-700 text-indigo-300"
                : "bg-slate-800 border-slate-700 text-slate-400 hover:text-white"
            }`}
            title={isTtsEnabled ? "Text-to-Speech aktiv" : "Text-to-Speech stummgeschaltet"}
          >
            {isTtsEnabled ? <Volume2 className="w-4 h-4 text-indigo-400" /> : <VolumeX className="w-4 h-4" />}
            <span className="hidden lg:inline">{isTtsEnabled ? "Audio An" : "Audio Aus"}</span>
          </button>

          <button
            onClick={onResetSession}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 transition text-xs flex items-center gap-1"
            title="Sitzung zurücksetzen"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">Reset</span>
          </button>
        </div>
      </div>
    </header>
  );
}
