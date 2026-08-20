import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { text = "Ich habe das Element erkannt. Ich habe drei Änderungen vorbereitet." } = body;

    return NextResponse.json({
      success: true,
      text,
      audioEngine: "Liquid Audio NFM Synthesizer",
      format: "browser_speech_synthesis_ready",
      spokenAt: new Date().toISOString(),
    });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err?.message }, { status: 500 });
  }
}
