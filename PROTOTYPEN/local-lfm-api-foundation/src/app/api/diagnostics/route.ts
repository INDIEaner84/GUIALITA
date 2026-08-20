import { NextResponse } from "next/server";
import { modelManager } from "@/lib/adapters/manager";

export const dynamic = "force-dynamic";

export async function GET() {
  const allProbes = await modelManager.probeAll();

  const summary = {
    timestamp: new Date().toISOString(),
    overallStatus: Object.values(allProbes).some((p) => p.reachable) ? "HEALTHY" : "DEGRADED",
    runtimes: allProbes,
    troubleshooting: [
      {
        runtime: "Local LFM (Native Engine)",
        port: 8000,
        cmd: "python3 scripts/lfm_runtime_server.py --port 8000",
        description: "Runs native local LFM HTTP runtime server",
      },
      {
        runtime: "Ollama",
        port: 11434,
        cmd: "ollama serve",
        description: "Runs Ollama model service",
      },
      {
        runtime: "llama.cpp",
        port: 8080,
        cmd: "./llama-server -m path/to/model.gguf --port 8080",
        description: "Runs llama.cpp OpenAI-compatible server",
      },
    ],
  };

  return NextResponse.json(summary);
}
