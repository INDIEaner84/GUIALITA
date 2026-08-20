import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { proposals, agentLogs, targetElements } from "@/db/schema";
import { eq } from "drizzle-orm";
import { randomUUID } from "crypto";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { targetId, userInstruction = "Bereich übersichtlicher machen", sessionId = "session_default" } = body;

    let componentName = "LiveHero";
    let filePath = "src/components/live/LiveHero.tsx";

    if (targetId) {
      const found = await db.select().from(targetElements).where(eq(targetElements.id, targetId)).limit(1);
      if (found.length > 0) {
        componentName = found[0].componentName;
        filePath = found[0].filePath;
      }
    }

    const generatedProposals = [
      {
        id: `prop_${Date.now()}_A_${randomUUID().substring(0, 5)}`,
        targetId: targetId || "target_default",
        optionKey: "A",
        title: "Modern & Dynamic Grid Layout",
        description: "Erhöht die visuelle Hierarchie mit ausdrucksstarken Gradienten, subtilen Glow-Effekten und hervorgehobenen Metriken.",
        stylePreset: "modern",
        affectedComponent: componentName,
        affectedFile: filePath,
        expectedVisualChange: "Mehr Tiefe, schimmernder Indigo-Hintergrund und vergrößerte Call-to-Action Buttons.",
        technicalChange: "Aktualisiert Tailwind Container-Klassen zu 'bg-gradient-to-br from-indigo-900 via-purple-900' und fügt Glow-Backdrop hinzu.",
        risk: "low",
        proposedCode: `<LiveHero variant="modern" heading="NFM Multimodal UI Intelligence Platform" subheading="Echtzeit-Analyse & Code-Generierung" ctaText="Jetzt Erkunden" />`,
        diffSummary: "+ bg-gradient-to-br from-indigo-900\n+ shadow-2xl hover:shadow-indigo-500/30\n+ flex-wrap font-extrabold",
        isApplied: false,
        createdAt: new Date(),
      },
      {
        id: `prop_${Date.now()}_B_${randomUUID().substring(0, 5)}`,
        targetId: targetId || "target_default",
        optionKey: "B",
        title: "Kompakte & Informationsdichte Ansicht",
        description: "Reduziert Margins und Padding um 40%, nutzt dunklen Kontrast und maximiert den nutzbaren Platz für Entwickler.",
        stylePreset: "compact",
        affectedComponent: componentName,
        affectedFile: filePath,
        expectedVisualChange: "Schlankeres Profil, reduzierte Schriftgrößen und dunkler Slate-900 Hintergrund.",
        technicalChange: "Setzt variant='compact', reduziert Padding auf 'p-4 md:p-6' und strafft Abstände.",
        risk: "low",
        proposedCode: `<LiveHero variant="compact" heading="MUSCAL Developer Engine" subheading="Kompakter High-Density Modus" ctaText="Start" />`,
        diffSummary: "- p-10 bg-gradient-to-br\n+ p-5 bg-slate-900 text-white\n- text-3xl -> text-xl font-bold",
        isApplied: false,
        createdAt: new Date(),
      },
      {
        id: `prop_${Date.now()}_C_${randomUUID().substring(0, 5)}`,
        targetId: targetId || "target_default",
        optionKey: "C",
        title: "Minimalistische & Clean-Design Variante",
        description: "Entfernt überflüssige Gradienten für ein klares, elegantes Layout auf hellem/neutralem Hintergrund.",
        stylePreset: "minimal",
        affectedComponent: componentName,
        affectedFile: filePath,
        expectedVisualChange: "Heller neutraler Hintergrund mit dunkler Typografie und dezenten borders.",
        technicalChange: "Setzt variant='minimal', wechselt zu 'bg-slate-50 text-slate-900 border-slate-300'.",
        risk: "low",
        proposedCode: `<LiveHero variant="minimal" heading="Fokussierte UI Oberfläche" subheading="Klare Trennung ohne Ablenkung" ctaText="Ausführen" />`,
        diffSummary: "- bg-slate-900 shadow-xl\n+ bg-white text-slate-900 shadow-sm\n+ border border-slate-200",
        isApplied: false,
        createdAt: new Date(),
      },
    ];

    for (const prop of generatedProposals) {
      await db.insert(proposals).values(prop);
    }

    await db.insert(agentLogs).values({
      id: `log_${Date.now()}_${randomUUID().substring(0, 6)}`,
      sessionId,
      type: "proposal",
      speaker: "liquid_agent",
      message: `3 Änderungsvorschläge (A: Modern, B: Kompakt, C: Minimalist) für '${componentName}' erzeugt.`,
      metadata: { targetId, count: 3 },
      timestamp: new Date(),
    });

    return NextResponse.json({
      success: true,
      proposals: generatedProposals,
    });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err?.message }, { status: 500 });
  }
}
