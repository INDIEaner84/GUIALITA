import { NextResponse } from "next/server";
import { modelManager } from "@/lib/adapters/manager";
import { db } from "@/db";
import { sql } from "drizzle-orm";

export const dynamic = "force-dynamic";

export async function GET() {
  const startTime = Date.now();
  
  // Check Database status
  let dbStatus = "ONLINE";
  try {
    await db.execute(sql`select 1`);
  } catch {
    dbStatus = "OFFLINE";
  }

  // Detect and probe local model runtimes
  const { activeAdapter, diagnostics } = await modelManager.autoDetectActive();
  const apiLatency = Date.now() - startTime;

  return NextResponse.json({
    api: {
      status: "ONLINE",
      latency_ms: apiLatency,
      database: dbStatus,
      timestamp: new Date().toISOString(),
    },
    model: {
      adapter: activeAdapter.id,
      adapterName: activeAdapter.name,
      status: diagnostics.status,
      reachable: diagnostics.reachable,
      modelLoaded: diagnostics.modelLoaded,
      modelName: diagnostics.detectedModel || "Unknown",
      targetEndpoint: diagnostics.targetEndpoint,
      latency_ms: diagnostics.latencyMs,
      availableModels: diagnostics.availableModels || [],
    },
    diagnostics: {
      reason: diagnostics.reason || null,
      recommendedAction: diagnostics.recommendedAction || null,
      details: diagnostics.rawDetails || null,
    },
  });
}
