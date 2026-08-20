"use client";

import React, { useState, useEffect, useRef } from "react";
import confetti from "canvas-confetti";
import { AgentHeader } from "@/components/agent/AgentHeader";
import { SpeechControl } from "@/components/agent/SpeechControl";
import { VisionOverlay, TargetElementData } from "@/components/agent/VisionOverlay";
import { ProposalsDeck, ProposalData } from "@/components/agent/ProposalsDeck";
import { VerificationPanel, VerificationData } from "@/components/agent/VerificationPanel";
import { DesktopControlPanel } from "@/components/agent/DesktopControlPanel";
import { SessionTimeline, LogItem } from "@/components/agent/SessionTimeline";
import { LiveAppContainer, AppStateConfig } from "@/components/live/LiveAppContainer";
import { Sparkles, FileText, CheckCircle2, ChevronDown, ChevronUp, Eye, Mic, Code2, RefreshCw } from "lucide-react";

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<"browser" | "desktop" | "logs">("browser");
  const [isTtsEnabled, setIsTtsEnabled] = useState(true);
  const [agentStatus, setAgentStatus] = useState<"idle" | "analyzing" | "proposed" | "applying" | "verified" | "error">("idle");
  const [showAnalysisDoc, setShowAnalysisDoc] = useState(false);

  // App live editable configuration
  const [appConfig, setAppConfig] = useState<AppStateConfig>({
    headerVariant: "modern",
    headerTitle: "MUSCAL Multimodal UI Builder — Liquid NFM Dashboard",
    heroVariant: "modern",
    heroHeading: "Transformiere Web-UIs mit natürlicher Sprache und Vision",
    heroSubheading: "Sprich mit deinem UI, zeige auf Elemente und lass das Liquid NFM/LFM Modell Änderungen in Echtzeit umsetzen.",
    heroCtaText: "Agent Starten",
    cardVariant: "modern",
    cardColumns: 3,
    actionVariant: "modern",
  });

  // Multimodal state
  const [selectedSelector, setSelectedSelector] = useState<string | null>('[data-component="LiveHero"]');
  const [targetElement, setTargetElement] = useState<TargetElementData | null>({
    id: "target_init",
    selector: '[data-component="LiveHero"]',
    componentName: "LiveHero",
    filePath: "src/components/live/LiveHero.tsx",
    boundingBox: { x: 320, y: 180, width: 840, height: 280 },
    accessibilityLabel: "Hero Section Component",
    detectedReason: "Liquid NFM combined cursor focus with DOM selector '[data-component=\"LiveHero\"]'. Ready for instructions.",
  });

  const [proposals, setProposals] = useState<ProposalData[]>([]);
  const [activeAppliedId, setActiveAppliedId] = useState<string | null>(null);
  const [verification, setVerification] = useState<VerificationData | null>(null);
  const [sessionLogs, setSessionLogs] = useState<LogItem[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);

  // Text to speech synthesizer helper
  const speakText = (text: string) => {
    if (!isTtsEnabled || typeof window === "undefined") return;
    try {
      window.speechSynthesis?.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "de-DE";
      utterance.rate = 1.0;
      window.speechSynthesis?.speak(utterance);
    } catch (e) {
      console.error("Speech synthesis error", e);
    }
  };

  // Log append helper
  const addLog = (message: string, speaker: "user" | "liquid_agent" | "system", type: string) => {
    const newItem: LogItem = {
      id: `log_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      type,
      speaker,
      message,
      timestamp: new Date().toISOString(),
    };
    setSessionLogs((prev) => [newItem, ...prev]);
  };

  // Initial load
  useEffect(() => {
    addLog("Multimodale Agentenumgebung (Liquid NFM Engine v2.4) initialisiert.", "system", "reload");
  }, []);

  // Handle direct click selection on live UI
  const handleSelectElementFromLive = (elData: { selector: string; componentName: string; label: string; rect: DOMRect }) => {
    setSelectedSelector(elData.selector);
    const newTarget: TargetElementData = {
      id: `target_${Date.now()}`,
      selector: elData.selector,
      componentName: elData.componentName,
      filePath: `src/components/live/${elData.componentName}.tsx`,
      boundingBox: {
        x: elData.rect.x,
        y: elData.rect.y,
        width: elData.rect.width,
        height: elData.rect.height,
      },
      accessibilityLabel: elData.label,
      detectedReason: `Mausklick erfasst. Liquid Vision NFM hat DOM Element '${elData.componentName}' hervorgehoben.`,
    };
    setTargetElement(newTarget);
    addLog(`Element '${elData.componentName}' im Browser ausgewählt.`, "user", "vision");
  };

  // Process user command (spoken or typed)
  const handleProcessCommand = async (userInstruction: string) => {
    setIsProcessing(true);
    setAgentStatus("analyzing");
    addLog(`" ${userInstruction} "`, "user", "speech");

    try {
      // Step 1: Speech intent parsing
      const parseRes = await fetch("/api/speech/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: userInstruction }),
      });
      const parseData = await parseRes.json();
      const intent = parseData?.parsed?.intent;

      // Handle direct proposal selection e.g. "Nimm B"
      if (intent === "select_proposal" && parseData.parsed.selectedOption) {
        const optionKey = parseData.parsed.selectedOption;
        const matchingProp = proposals.find((p) => p.optionKey === optionKey);
        if (matchingProp) {
          await handleApplyProposal(matchingProp.id);
          setIsProcessing(false);
          return;
        }
      }

      // Step 2: Vision & DOM Identification
      const visionRes = await fetch("/api/vision/identify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userInstruction,
          selectedSelector,
        }),
      });
      const visionData = await visionRes.json();

      if (visionData.success && visionData.target) {
        setTargetElement(visionData.target);
        setSelectedSelector(visionData.target.selector);
        addLog(
          `Ziel-Komponente '${visionData.target.componentName}' (${visionData.target.filePath}) von Liquid Vision erkannt.`,
          "liquid_agent",
          "vision"
        );
      }

      // Step 3: Generate Proposals
      const proposalRes = await fetch("/api/proposals/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          targetId: visionData?.target?.id || targetElement?.id,
          userInstruction,
        }),
      });
      const proposalData = await proposalRes.json();

      if (proposalData.success && proposalData.proposals) {
        setProposals(proposalData.proposals);
        setAgentStatus("proposed");
        addLog(`Drei Änderungsvorschläge (A, B, C) für die UI erzeugt.`, "liquid_agent", "proposal");

        speakText(
          `Ich habe das Element ${visionData?.target?.componentName || "im UI"} erkannt. Ich habe drei Änderungsvorschläge vorbereitet.`
        );
      }
    } catch (err: any) {
      console.error(err);
      setAgentStatus("error");
      addLog(`Fehler beim Analysieren: ${err?.message}`, "system", "error");
    } finally {
      setIsProcessing(false);
    }
  };

  // Step 5 & 6: Apply chosen proposal & reload
  const handleApplyProposal = async (proposalId: string) => {
    setAgentStatus("applying");
    setIsProcessing(true);

    try {
      const applyRes = await fetch("/api/proposals/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ proposalId }),
      });
      const applyData = await applyRes.json();

      if (applyData.success) {
        const applied = applyData.appliedProposal;
        setActiveAppliedId(proposalId);

        // Update live app preview config based on preset
        if (targetElement?.componentName === "LiveHero" || applied.affectedComponent === "LiveHero") {
          setAppConfig((prev) => ({
            ...prev,
            heroVariant: applied.stylePreset as any,
            heroHeading:
              applied.stylePreset === "compact"
                ? "MUSCAL Developer Engine (Kompakt)"
                : applied.stylePreset === "minimal"
                ? "Fokussierte UI Oberfläche (Minimal)"
                : "NFM Multimodal UI Intelligence Platform",
          }));
        } else if (targetElement?.componentName === "LiveHeader" || applied.affectedComponent === "LiveHeader") {
          setAppConfig((prev) => ({
            ...prev,
            headerVariant: applied.stylePreset as any,
          }));
        } else if (targetElement?.componentName === "LiveCardGrid" || applied.affectedComponent === "LiveCardGrid") {
          setAppConfig((prev) => ({
            ...prev,
            cardVariant: applied.stylePreset as any,
            cardColumns: applied.stylePreset === "compact" ? 2 : 3,
          }));
        }

        // Trigger confetti celebration
        try {
          confetti({ particleCount: 70, spread: 60, origin: { y: 0.6 } });
        } catch (e) {}

        addLog(`Vorschlag Option ${applied.optionKey} (${applied.title}) angewendet.`, "liquid_agent", "code");

        // Step 7: Verify
        const verifyRes = await fetch("/api/verify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            proposalId,
            affectedComponent: applied.affectedComponent,
          }),
        });
        const verifyData = await verifyRes.json();

        if (verifyData.success) {
          setVerification(verifyData.verification);
          setAgentStatus("verified");
          addLog(`Visuelle Selbstüberprüfung erfolgreich.`, "liquid_agent", "verify");
          speakText(`Option ${applied.optionKey} wurde angewendet und die Oberfläche wurde neu geladen.`);
        }
      }
    } catch (err: any) {
      console.error(err);
      setAgentStatus("error");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleResetSession = () => {
    setProposals([]);
    setVerification(null);
    setActiveAppliedId(null);
    setAgentStatus("idle");
    addLog("Sitzung zurückgesetzt.", "system", "reload");
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500 selection:text-white flex flex-col">
      {/* Agent Top HUD Header */}
      <AgentHeader
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        isTtsEnabled={isTtsEnabled}
        setIsTtsEnabled={setIsTtsEnabled}
        agentStatus={agentStatus}
        onResetSession={handleResetSession}
      />

      {/* Main Workspace Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 space-y-6">
        {/* Toggle Analysis Document Section (Bestandsaufnahme) */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-lg">
          <button
            onClick={() => setShowAnalysisDoc(!showAnalysisDoc)}
            className="w-full flex items-center justify-between text-left text-xs font-bold text-indigo-300 uppercase tracking-wider"
          >
            <span className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-400" />
              Arbeitsauftrag & Bestandsaufnahme (Phase 1 + Phase 2 Architektur-Analyse)
            </span>
            <span className="flex items-center gap-1 text-slate-400">
              {showAnalysisDoc ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </span>
          </button>

          {showAnalysisDoc && (
            <div className="mt-4 space-y-3 text-xs text-slate-300 border-t border-slate-800 pt-4 font-mono leading-relaxed">
              <div>
                <strong className="text-indigo-300 font-bold block">1. CURRENT STATE:</strong>
                Lokal laufende Next.js 16 (App Router) + PostgreSQL / Drizzle ORM Anwendung mit Tailwind CSS v4, Web Speech API integration, Liquid NFM multimodal vision inspector engine und React 19 editable components.
              </div>
              <div>
                <strong className="text-indigo-300 font-bold block">2. MISSING COMPONENTS:</strong>
                Keine externen Paywalled APIs erforderlich; vollständiges lokales Liquid NFM Mock / Heuristik Modell mit Vision Transformer DOM Matching, Synthesizer TTS und Hot Reloading verbaut.
              </div>
              <div>
                <strong className="text-indigo-300 font-bold block">3. REUSE OPPORTUNITIES:</strong>
                Wiederverwendung von Drizzle ORM Schema, Web Speech Recognition/Synthesis APIs, Tailwind utility classes und Server Components API proxy routes.
              </div>
              <div>
                <strong className="text-indigo-300 font-bold block">4. MINIMAL ARCHITECTURE:</strong>
                Single Fullstack Next.js Repository mit In-Memory / PostgreSQL Session State, `/api/vision/identify`, `/api/proposals/generate`, `/api/proposals/apply`, `/api/verify` endpoints und Live Target UI Canvas.
              </div>
              <div>
                <strong className="text-indigo-300 font-bold block">5. IMPLEMENTATION PLAN:</strong>
                Phase 1 (Browser UI MVP) -&gt; Phase 2 (Vision & Bounding Box) -&gt; Phase 3 (Code Proposals A/B/C) -&gt; Phase 4 (Reload & Verify) -&gt; Phase 5 (Speech STT) -&gt; Phase 6 (Audio TTS) -&gt; Phase 7 (Desktop Controls Module).
              </div>
              <div>
                <strong className="text-indigo-300 font-bold block">6. RISKS:</strong>
                Browser Speech-Recognition benötigt Mikrofon-Freigabe; automatisierte Falbacks für manuelle Eingabe & Schnellklick-Chips wurden integriert.
              </div>
              <div>
                <strong className="text-indigo-300 font-bold block">7. NEXT IMPLEMENTATION STEP:</strong>
                Live UX-Loop durchführen: 👁 SEHEN -&gt; 🎤 SAGEN -&gt; 🎯 MARKIEREN -&gt; 💡 VORSCHLÄGE -&gt; 👆 AUSWÄHLEN -&gt; 🔄 RELOAD.
              </div>
            </div>
          )}
        </div>

        {/* Tab 1: Browser Multimodal Builder (Phase 1 - Phase 6) */}
        {activeTab === "browser" && (
          <div className="space-y-6">
            {/* Top Interactive Live App View */}
            <div className="space-y-2">
              <div className="flex items-center justify-between px-1">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-300">
                  <Eye className="w-4 h-4 text-indigo-400" />
                  Live Anwendung (Interactive App Canvas)
                </div>
                <span className="text-[11px] text-slate-500 font-mono">
                  Tipp: Klicke ein Element zum Ziel-Markieren an
                </span>
              </div>

              <LiveAppContainer
                config={appConfig}
                onSelectElement={handleSelectElementFromLive}
                selectedSelector={selectedSelector}
              />
            </div>

            {/* Multimodal Agent HUD & Controls */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left Column: Voice Commands & Vision Inspector */}
              <div className="space-y-6">
                <SpeechControl
                  onProcessCommand={handleProcessCommand}
                  isProcessing={isProcessing}
                  isTtsEnabled={isTtsEnabled}
                  speakText={speakText}
                />

                <VisionOverlay
                  target={targetElement}
                  onSelectComponent={(sel) => {
                    setSelectedSelector(sel);
                    const compName = sel.includes("Header")
                      ? "LiveHeader"
                      : sel.includes("Card")
                      ? "LiveCardGrid"
                      : sel.includes("Action")
                      ? "LiveActionSection"
                      : "LiveHero";

                    setTargetElement({
                      id: `target_${Date.now()}`,
                      selector: sel,
                      componentName: compName,
                      filePath: `src/components/live/${compName}.tsx`,
                      boundingBox: { x: 200, y: 150, width: 800, height: 200 },
                      accessibilityLabel: `${compName} Selected`,
                      detectedReason: `Manuell ausgewählt via Inspector: ${compName}`,
                    });
                  }}
                  selectedSelector={selectedSelector}
                />
              </div>

              {/* Right Column: AI Proposals, Verification & Log */}
              <div className="space-y-6">
                <ProposalsDeck
                  proposals={proposals}
                  onApplyProposal={handleApplyProposal}
                  isApplying={isProcessing}
                  activeAppliedId={activeAppliedId}
                />

                <VerificationPanel verification={verification} />

                <SessionTimeline logs={sessionLogs} />
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Desktop Control Module (Phase 7) */}
        {activeTab === "desktop" && <DesktopControlPanel />}

        {/* Tab 3: Detailed Session Logs */}
        {activeTab === "logs" && (
          <div className="space-y-4">
            <SessionTimeline logs={sessionLogs} />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 py-4 px-6 text-center text-xs text-slate-500">
        MUSCAL Multimodal UI Builder — Powered by Liquid NFM/LFM Architecture & PostgreSQL + Drizzle ORM
      </footer>
    </div>
  );
}
