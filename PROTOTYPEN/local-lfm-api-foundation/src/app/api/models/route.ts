import { NextResponse } from "next/server";
import { modelManager } from "@/lib/adapters/manager";

export const dynamic = "force-dynamic";

export async function GET() {
  const allProbes = await modelManager.probeAll();

  const modelsList = [];
  for (const [adapterKey, probe] of Object.entries(allProbes)) {
    if (probe.reachable && probe.availableModels) {
      for (const mName of probe.availableModels) {
        modelsList.push({
          id: mName,
          adapter: adapterKey,
          targetEndpoint: probe.targetEndpoint,
          status: probe.status,
        });
      }
    }
  }

  // Always list standard LFM models if empty
  if (modelsList.length === 0) {
    modelsList.push(
      { id: "lfm-1.0-3b-instruct", adapter: "lfm", targetEndpoint: "http://127.0.0.1:8000", status: "OFFLINE" },
      { id: "lfm-lite", adapter: "lfm", targetEndpoint: "http://127.0.0.1:8000", status: "OFFLINE" }
    );
  }

  return NextResponse.json({ models: modelsList, total: modelsList.length });
}
