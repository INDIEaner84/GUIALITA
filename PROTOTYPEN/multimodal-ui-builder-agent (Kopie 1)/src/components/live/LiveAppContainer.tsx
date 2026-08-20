"use client";

import React from "react";
import { LiveHeader, LiveHeaderProps } from "./LiveHeader";
import { LiveHero, LiveHeroProps } from "./LiveHero";
import { LiveCardGrid, LiveCardGridProps } from "./LiveCardGrid";
import { LiveActionSection, LiveActionSectionProps } from "./LiveActionSection";

export interface AppStateConfig {
  headerVariant: "modern" | "compact" | "minimal";
  headerTitle: string;
  heroVariant: "modern" | "compact" | "minimal";
  heroHeading: string;
  heroSubheading: string;
  heroCtaText: string;
  cardVariant: "modern" | "compact" | "minimal";
  cardColumns: 2 | 3 | 4;
  actionVariant: "modern" | "compact" | "minimal";
}

export interface LiveAppContainerProps {
  config?: Partial<AppStateConfig>;
  onSelectElement?: (elData: { selector: string; componentName: string; label: string; rect: DOMRect }) => void;
  selectedSelector?: string | null;
}

export function LiveAppContainer({
  config = {},
  onSelectElement,
  selectedSelector,
}: LiveAppContainerProps) {
  const headerVariant = config.headerVariant || "modern";
  const headerTitle = config.headerTitle || "MUSCAL Multimodal UI Builder — Liquid NFM Dashboard";
  const heroVariant = config.heroVariant || "modern";
  const heroHeading = config.heroHeading || "Transformiere Web-UIs mit natürlicher Sprache und Vision";
  const heroSubheading = config.heroSubheading || "Sprich mit deinem UI, zeige auf Elemente und lass das Liquid NFM/LFM Modell Änderungen in Echtzeit umsetzen.";
  const heroCtaText = config.heroCtaText || "Agent Starten";
  const cardVariant = config.cardVariant || "modern";
  const cardColumns = config.cardColumns || 3;
  const actionVariant = config.actionVariant || "modern";

  return (
    <div className="w-full min-h-[700px] bg-slate-950 text-slate-100 p-4 sm:p-6 rounded-3xl border border-slate-800 shadow-2xl space-y-6 select-none relative overflow-hidden">
      {/* Background ambient liquid glow */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-600/10 blur-[120px] rounded-full pointer-events-none"></div>
      <div className="absolute bottom-0 left-0 w-96 h-96 bg-purple-600/10 blur-[120px] rounded-full pointer-events-none"></div>

      <LiveHeader
        variant={headerVariant}
        title={headerTitle}
        onSelectElement={onSelectElement}
        selectedSelector={selectedSelector}
      />

      <LiveHero
        variant={heroVariant}
        heading={heroHeading}
        subheading={heroSubheading}
        ctaText={heroCtaText}
        onSelectElement={onSelectElement}
        selectedSelector={selectedSelector}
      />

      <LiveCardGrid
        variant={cardVariant}
        columns={cardColumns}
        onSelectElement={onSelectElement}
        selectedSelector={selectedSelector}
      />

      <LiveActionSection
        variant={actionVariant}
        onSelectElement={onSelectElement}
        selectedSelector={selectedSelector}
      />
    </div>
  );
}
