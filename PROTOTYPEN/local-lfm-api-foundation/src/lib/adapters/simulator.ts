import { ChatRequest, ChatResponse, DiagnosticInfo, ModelAdapter } from "./types";

export class LFMSimulatorAdapter implements ModelAdapter {
  id = "lfm-simulator" as const;
  name = "Embedded LFM Emulator (Standalone)";
  defaultEndpoint = "embedded://lfm-core";

  async checkHealth(): Promise<DiagnosticInfo> {
    return {
      status: "ONLINE",
      adapterType: this.id,
      targetEndpoint: this.defaultEndpoint,
      detectedModel: "lfm-1.0-3b-instruct (Embedded Engine)",
      latencyMs: 4,
      reachable: true,
      modelLoaded: true,
      availableModels: ["lfm-1.0-3b-instruct", "lfm-lite", "lfm-7b-instruct"],
      recommendedAction: "Embedded LFM emulator active. To connect to native LFM server, start python3 scripts/lfm_runtime_server.py --port 8000.",
    };
  }

  async listModels(): Promise<string[]> {
    return ["lfm-1.0-3b-instruct", "lfm-lite", "lfm-7b-instruct"];
  }

  async chat(request: ChatRequest): Promise<ChatResponse> {
    const startTime = Date.now();
    const timestamp = new Date().toISOString();

    // Check test message
    const normalized = request.message.trim().toLowerCase();
    let responseText = "";

    if (normalized.includes("hallo lfm, antworte mit: lfm connection test ok") || normalized.includes("lfm connection test ok")) {
      responseText = "LFM CONNECTION TEST OK";
    } else if (normalized === "hallo" || normalized === "hello") {
      responseText = "Hallo! Ich bin dein lokales Liquid Foundation Model (LFM). Wie kann ich dir heute helfen?";
    } else {
      responseText = `[LFM Response]: Ich habe deine Nachricht erhalten ("${request.message}"). Als lokales Liquid Foundation Model verarbeite ich Anfragen direkt auf dieser Maschine. Phase 0 Browser-Kommunikation ist aktiv.`;
    }

    // Simulate minor processing latency
    await new Promise((resolve) => setTimeout(resolve, 35));
    const latency_ms = Date.now() - startTime;

    return {
      response: responseText,
      model: request.model || "lfm-1.0-3b-instruct",
      adapterType: this.id,
      latency_ms,
      status: "SUCCESS",
      timestamp,
      targetEndpoint: this.defaultEndpoint,
      isMockFallback: true,
    };
  }
}
