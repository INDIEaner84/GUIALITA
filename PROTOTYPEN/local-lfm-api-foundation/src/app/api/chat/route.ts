import { NextRequest, NextResponse } from "next/server";
import { modelManager } from "@/lib/adapters/manager";
import { AdapterType } from "@/lib/adapters/types";
import { db } from "@/db";
import { chatLogs } from "@/db/schema";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}));
    const message = body.message;

    if (!message || typeof message !== "string" || !message.trim()) {
      return NextResponse.json(
        {
          error: "Missing or invalid 'message' field in request body",
          status: "ERROR",
        },
        { status: 400 }
      );
    }

    const adapterType = body.adapter as AdapterType | undefined;
    const requestedModel = body.model as string | undefined;

    const chatResult = await modelManager.chat(
      {
        message: message.trim(),
        model: requestedModel,
      },
      adapterType
    );

    // Persist to database
    try {
      const id = `chat_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
      await db.insert(chatLogs).values({
        id,
        userMessage: message.trim(),
        assistantResponse: chatResult.response,
        modelName: chatResult.model,
        adapterType: chatResult.adapterType,
        latencyMs: chatResult.latency_ms,
        status: chatResult.status,
        targetEndpoint: chatResult.targetEndpoint,
        errorMessage: chatResult.status === "ERROR" ? chatResult.response : null,
      });
    } catch (dbErr) {
      console.error("Failed to insert chat log into database:", dbErr);
    }

    return NextResponse.json({
      response: chatResult.response,
      model: chatResult.model,
      adapter: chatResult.adapterType,
      latency_ms: chatResult.latency_ms,
      status: chatResult.status,
      timestamp: chatResult.timestamp,
      targetEndpoint: chatResult.targetEndpoint,
      request: {
        message: message.trim(),
      },
      diagnostics: chatResult.diagnostics || null,
      isMockFallback: chatResult.isMockFallback || false,
    });
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      {
        response: `[API SYSTEM ERROR]: ${errorMsg}`,
        model: "Unknown",
        latency_ms: 0,
        status: "ERROR",
        timestamp: new Date().toISOString(),
        diagnostics: {
          status: "ERROR",
          reason: errorMsg,
          recommendedAction: "Verify local server processes and API routing.",
        },
      },
      { status: 500 }
    );
  }
}
