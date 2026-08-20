import { NextResponse } from "next/server";
import { modelManager } from "@/lib/adapters/manager";

export const dynamic = "force-dynamic";

export async function POST() {
  const testMessage = "Hallo LFM, antworte mit:\nLFM CONNECTION TEST OK";
  const startTime = Date.now();

  const chatResult = await modelManager.chat({ message: testMessage });
  const latency_ms = Date.now() - startTime;

  const passed =
    chatResult.status === "SUCCESS" &&
    chatResult.response.includes("LFM CONNECTION TEST OK");

  const isRealLFM = !chatResult.isMockFallback && chatResult.adapterType === "lfm";

  return NextResponse.json({
    testName: "Phase 0 E2E LFM Connection Test",
    passed,
    isRealLFMResponse: isRealLFM,
    request: {
      message: testMessage,
    },
    response: {
      text: chatResult.response,
      model: chatResult.model,
      adapter: chatResult.adapterType,
      targetEndpoint: chatResult.targetEndpoint,
      latency_ms: chatResult.latency_ms,
      status: chatResult.status,
      timestamp: chatResult.timestamp,
    },
    diagnostics: chatResult.diagnostics || null,
    totalDurationMs: latency_ms,
    summary: passed
      ? isRealLFM
        ? "PASS: Native Local LFM Model responded correctly to connection test!"
        : "PASS: LFM Adapter responded (Simulator Mode active)."
      : "FAIL: Model failed to respond with expected LFM CONNECTION TEST OK string.",
  });
}
