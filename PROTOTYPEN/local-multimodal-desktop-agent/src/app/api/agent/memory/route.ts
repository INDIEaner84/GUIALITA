/**
 * Memory inspection endpoints (for the UI and for Agent Workers).
 *
 *   GET /api/agent/memory?sessionId=<id>             → session detail
 *   GET /api/agent/memory?action=sessions            → recent sessions
 *   GET /api/agent/memory?action=search&q=...         → message search
 *   GET /api/agent/memory?action=events&sessionId=... → events
 *   GET /api/agent/memory?action=context&q=...       → related context
 *   GET /api/agent/memory?action=tools               → tool catalog
 */

import { NextRequest, NextResponse } from "next/server";
import {
  getSession,
  getMessages,
  getEvents,
  listRecentSessions,
  searchMessages,
  getRelatedContext,
} from "@/gui_alita/memory/store";
import { listTools } from "@/gui_alita/tools/router";
import { config } from "@/gui_alita/config";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const action = sp.get("action") ?? "session";
  const sessionId = sp.get("sessionId");
  try {
    if (action === "sessions") {
      return NextResponse.json({ ok: true, sessions: listRecentSessions(50) });
    }
    if (action === "search") {
      return NextResponse.json({ ok: true, messages: searchMessages(sp.get("q") ?? "", 50) });
    }
    if (action === "events") {
      if (!sessionId) return NextResponse.json({ ok: false, error: "sessionId required" }, { status: 400 });
      return NextResponse.json({ ok: true, events: getEvents(sessionId, 500) });
    }
    if (action === "context") {
      return NextResponse.json({ ok: true, context: getRelatedContext(sp.get("q") ?? "", 25) });
    }
    if (action === "tools") {
      return NextResponse.json({ ok: true, tools: listTools() });
    }
    if (action === "config") {
      return NextResponse.json({ ok: true, config });
    }
    if (action === "session") {
      if (!sessionId) return NextResponse.json({ ok: false, error: "sessionId required" }, { status: 400 });
      const session = getSession(sessionId);
      if (!session) return NextResponse.json({ ok: false, error: "not found" }, { status: 404 });
      return NextResponse.json({ ok: true, session, messages: getMessages(sessionId) });
    }
    return NextResponse.json({ ok: false, error: "unknown action" }, { status: 400 });
  } catch (e) {
    return NextResponse.json({ ok: false, error: (e as Error).message }, { status: 500 });
  }
}
