/**
 * POST /api/desktop/screenshot    — capture a fresh screenshot
 * GET  /api/desktop/screenshot?path=... — stream an existing artifact
 */

import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import { captureScreen } from "@/gui_alita/desktop/engine";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST() {
  try {
    const cap = await captureScreen();
    return NextResponse.json({ ok: true, ...cap });
  } catch (e) {
    return NextResponse.json({ ok: false, error: (e as Error).message }, { status: 500 });
  }
}

export async function GET(req: NextRequest) {
  const p = req.nextUrl.searchParams.get("path");
  if (!p) return NextResponse.json({ error: "path required" }, { status: 400 });
  const root = path.join(process.cwd(), "data", "artifacts");
  const abs = path.resolve(p);
  if (!abs.startsWith(root)) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  if (!fs.existsSync(abs)) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  const buf = fs.readFileSync(abs);
  return new NextResponse(buf, {
    status: 200,
    headers: { "content-type": "image/png", "content-length": String(buf.length) },
  });
}
