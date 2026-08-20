"use client";

import React from "react";
import { Sparkles, ArrowRight, Play, Zap, CheckCircle2 } from "lucide-react";

export interface LiveHeroProps {
  variant?: "modern" | "compact" | "minimal";
  heading?: string;
  subheading?: string;
  ctaText?: string;
  onSelectElement?: (elData: { selector: string; componentName: string; label: string; rect: DOMRect }) => void;
  selectedSelector?: string | null;
}

export function LiveHero({
  variant = "modern",
  heading = "Transformiere Web-UIs mit natürlicher Sprache und Vision",
  subheading = "Sprich mit deinem UI, zeige auf Elemente und lass das Liquid NFM/LFM Modell Änderungen in Echtzeit umsetzen.",
  ctaText = "Agent Starten",
  onSelectElement,
  selectedSelector,
}: LiveHeroProps) {
  const isSelected = selectedSelector === '[data-component="LiveHero"]';

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    e.stopPropagation();
    if (onSelectElement) {
      const rect = e.currentTarget.getBoundingClientRect();
      onSelectElement({
        selector: '[data-component="LiveHero"]',
        componentName: "LiveHero",
        label: "Hero Section / Call to Action Component",
        rect,
      });
    }
  };

  return (
    <div
      data-component="LiveHero"
      onClick={handleClick}
      className={`relative cursor-pointer transition-all duration-300 rounded-2xl border ${
        isSelected
          ? "ring-4 ring-indigo-500 ring-offset-2 border-indigo-500 shadow-2xl"
          : "hover:border-indigo-300 border-slate-200"
      } ${
        variant === "compact"
          ? "p-6 bg-slate-900 text-white"
          : variant === "minimal"
          ? "p-8 bg-slate-50 text-slate-900 border-slate-300"
          : "p-10 bg-gradient-to-br from-indigo-900 via-purple-900 to-slate-900 text-white shadow-xl"
      }`}
    >
      {isSelected && (
        <span className="absolute -top-3 left-4 bg-indigo-600 text-white text-xs px-2.5 py-0.5 rounded-full font-mono font-medium tracking-wide shadow-md flex items-center gap-1 z-20">
          <Sparkles className="w-3 h-3" /> AI Target: LiveHero.tsx
        </span>
      )}

      <div className="max-w-3xl space-y-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
          <Zap className="w-3.5 h-3.5 text-yellow-400" /> Liquid Neural Field Model Online
        </div>

        <h1
          className={`${
            variant === "compact" ? "text-2xl" : variant === "minimal" ? "text-3xl" : "text-3xl md:text-4xl"
          } font-extrabold tracking-tight leading-tight`}
        >
          {heading}
        </h1>

        <p className={`text-sm md:text-base ${variant === "minimal" ? "text-slate-600" : "text-indigo-100/80"}`}>
          {subheading}
        </p>

        <div className="pt-2 flex flex-wrap gap-3 items-center">
          <button className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 font-semibold text-white shadow-lg hover:shadow-indigo-500/30 transition flex items-center gap-2 text-sm">
            {ctaText} <ArrowRight className="w-4 h-4" />
          </button>
          <button className="px-4 py-2.5 rounded-xl border border-white/20 hover:bg-white/10 transition text-sm flex items-center gap-2">
            <Play className="w-4 h-4 text-indigo-400" /> Demo Video ansehen
          </button>
        </div>

        <div className="pt-4 flex items-center gap-6 text-xs opacity-70">
          <span className="flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Speech-to-Text
          </span>
          <span className="flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Vision Overlay
          </span>
          <span className="flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Auto-Verification
          </span>
        </div>
      </div>
    </div>
  );
}
