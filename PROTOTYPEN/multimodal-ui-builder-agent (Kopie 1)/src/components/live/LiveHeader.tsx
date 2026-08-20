"use client";

import React from "react";
import { Sparkles, Shield, Bell, User, Search, Settings } from "lucide-react";

export interface LiveHeaderProps {
  variant?: "modern" | "compact" | "minimal";
  title?: string;
  showSearch?: boolean;
  onSelectElement?: (elData: { selector: string; componentName: string; label: string; rect: DOMRect }) => void;
  selectedSelector?: string | null;
}

export function LiveHeader({
  variant = "modern",
  title = "MUSCAL Workspace & Analytics Dashboard",
  showSearch = true,
  onSelectElement,
  selectedSelector,
}: LiveHeaderProps) {
  const isSelected = selectedSelector === '[data-component="LiveHeader"]';

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    e.stopPropagation();
    if (onSelectElement) {
      const rect = e.currentTarget.getBoundingClientRect();
      onSelectElement({
        selector: '[data-component="LiveHeader"]',
        componentName: "LiveHeader",
        label: "Header / Navigation Toolbar Component",
        rect,
      });
    }
  };

  return (
    <div
      data-component="LiveHeader"
      onClick={handleClick}
      className={`relative cursor-pointer transition-all duration-300 rounded-2xl border ${
        isSelected
          ? "ring-4 ring-indigo-500 ring-offset-2 border-indigo-500 shadow-xl"
          : "hover:border-indigo-300 border-slate-200"
      } ${
        variant === "compact"
          ? "p-3 bg-slate-900 text-white"
          : variant === "minimal"
          ? "p-4 bg-white text-slate-800 shadow-sm"
          : "p-5 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white shadow-lg"
      }`}
    >
      {isSelected && (
        <span className="absolute -top-3 left-4 bg-indigo-600 text-white text-xs px-2.5 py-0.5 rounded-full font-mono font-medium tracking-wide shadow-md flex items-center gap-1 z-20">
          <Sparkles className="w-3 h-3" /> AI Target: LiveHeader.tsx
        </span>
      )}

      <div className="flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center font-bold text-white shadow-md">
            M
          </div>
          <div>
            <h2 className="text-lg font-bold tracking-tight flex items-center gap-2">
              {title}
              <span className="text-xs font-normal px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                v2.4
              </span>
            </h2>
            <p className="text-xs opacity-70">Multimodal Liquid NFM Engine Active</p>
          </div>
        </div>

        {showSearch && (
          <div className="relative w-full md:w-72">
            <Search className="absolute left-3 top-2.5 h-4 w-4 opacity-50" />
            <input
              type="text"
              placeholder="Suchbegriff eingeben..."
              className="w-full pl-9 pr-4 py-1.5 text-sm rounded-lg bg-white/10 border border-white/20 text-current placeholder-current/50 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              readOnly
            />
          </div>
        )}

        <div className="flex items-center gap-2">
          <button className="p-2 rounded-lg hover:bg-white/10 transition text-sm flex items-center gap-1 opacity-80 hover:opacity-100">
            <Bell className="w-4 h-4" />
            <span className="hidden sm:inline text-xs">Benachrichtigungen</span>
          </button>
          <button className="p-2 rounded-lg hover:bg-white/10 transition text-sm flex items-center gap-1 opacity-80 hover:opacity-100">
            <Settings className="w-4 h-4" />
            <span className="hidden sm:inline text-xs">Optionen</span>
          </button>
          <div className="h-8 w-8 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-semibold border-2 border-white/30">
            JD
          </div>
        </div>
      </div>
    </div>
  );
}
