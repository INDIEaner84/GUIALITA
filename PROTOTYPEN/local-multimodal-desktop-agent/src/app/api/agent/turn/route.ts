/**
 * POST /api/agent/turn
 *
 *   { sessionId?, text, modality?: "text"|"audio", audioBase64?, speak?: boolean }
 *
 *   → { sessionId, userText, responseText, responseAudioUrl?, steps[], taskId? }
 */

import { NextRequest, NextResponse } from "next/server";
import { runAgent } from "@/gui_alita/agent/loop";
import { clearStop, isStopped } from "@/gui_alita/safety";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as {
      sessionId?: string;
      text?: string;
      modality?: "text" | "audio";
      audioBase64?: string;
      speak?: boolean;
    };

    if (body.text === "resume") {
      clearStop();
    }
    if (isStopped().stopped && body.text !== "resume") {
      return NextResponse.json({ error: "agent stopped; send {text:'resume'} to continue" }, { status: 423 });
    }

    const modality = body.modality ?? "text";
    const audio = modality === "audio" && body.audioBase64
      ? Buffer.from(body.audioBase64, "base64")
      : undefined;
    const text = body.text ?? (modality === "audio" ? "" : "");

    const result = await runAgent(text, {
      sessionId: body.sessionId,
      userModality: modality,
      audio,
      speak: body.speak,
    });
    return NextResponse.json({
      ok: true,
      sessionId: result.sessionId,
      userText: result.userInput,
      responseText: result.responseText,
      responseAudioUrl: result.responseAudioPath ? `/api/agent/audio?path=${encodeURIComponent(result.responseAudioPath)}` : undefined,
      steps: result.steps,
      taskId: result.taskId,
    });
  } catch (e) {
    return NextResponse.json({ ok: false, error: (e as Error).message }, { status: 500 });
  }
}
