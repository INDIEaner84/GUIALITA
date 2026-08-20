/**
 * POST /api/agent/stop  — emergency stop (and resume).
 */

import { NextRequest, NextResponse } from "next/server";
import { emergencyStop, clearStop, isStopped } from "@/gui_alita/safety";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as { action?: "stop" | "resume"; reason?: string };
    if (body.action === "resume") {
      clearStop();
      return NextResponse.json({ ok: true, stopped: false });
    }
    emergencyStop(body.reason ?? "user pressed STOP AGENT");
    return NextResponse.json({ ok: true, stopped: true, state: isStopped() });
  } catch (e) {
    return NextResponse.json({ ok: false, error: (e as Error).message }, { status: 500 });
  }
}

export async function GET() {
  return NextResponse.json({ ok: true, state: isStopped() });
}
