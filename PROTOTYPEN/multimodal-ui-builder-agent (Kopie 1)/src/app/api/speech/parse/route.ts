import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { transcript, currentStatus } = body;

    const text = (transcript || "").toLowerCase().trim();

    let intent = "unknown";
    let targetComponent = null;
    let selectedOption = null;

    if (text.includes("nimm a") || text.includes("vorschlag a") || text.includes("option a") || text === "a") {
      intent = "select_proposal";
      selectedOption = "A";
    } else if (text.includes("nimm b") || text.includes("vorschlag b") || text.includes("option b") || text === "b") {
      intent = "select_proposal";
      selectedOption = "B";
    } else if (text.includes("nimm c") || text.includes("vorschlag c") || text.includes("option c") || text === "c") {
      intent = "select_proposal";
      selectedOption = "C";
    } else if (
      text.includes("gefallt mir nicht") ||
      text.includes("gefällt mir nicht") ||
      text.includes("andern") ||
      text.includes("ändern") ||
      text.includes("überarbeiten") ||
      text.includes("übersichtlicher") ||
      text.includes("schrift") ||
      text.includes("button") ||
      text.includes("navigation") ||
      text.includes("header") ||
      text.includes("hero") ||
      text.includes("modern") ||
      text.includes("kompakt")
    ) {
      intent = "modify_ui";
      
      if (text.includes("header") || text.includes("oben") || text.includes("titel")) {
        targetComponent = "LiveHeader";
      } else if (text.includes("hero") || text.includes("bereich") || text.includes("banner") || text.includes("text")) {
        targetComponent = "LiveHero";
      } else if (text.includes("karte") || text.includes("cards") || text.includes("raster") || text.includes("spalte")) {
        targetComponent = "LiveCardGrid";
      } else if (text.includes("terminal") || text.includes("diagnose") || text.includes("unten")) {
        targetComponent = "LiveActionSection";
      }
    } else if (text.includes("desktop") || text.includes("öffne") || text.includes("klicke")) {
      intent = "desktop_action";
    }

    return NextResponse.json({
      success: true,
      parsed: {
        rawTranscript: transcript,
        intent,
        targetComponent,
        selectedOption,
        timestamp: new Date().toISOString(),
      },
    });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err?.message }, { status: 500 });
  }
}
