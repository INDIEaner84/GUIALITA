import { ChatRequest, ChatResponse, DiagnosticInfo, ModelAdapter } from "./types";

export class OllamaAdapter implements ModelAdapter {
  id = "ollama" as const;
  name = "Ollama Local API";
  defaultEndpoint = process.env.OLLAMA_ENDPOINT || "http://127.0.0.1:11434";

  async checkHealth(customEndpoint?: string): Promise<DiagnosticInfo> {
    const endpoint = customEndpoint || this.defaultEndpoint;
    const startTime = Date.now();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);

      const res = await fetch(`${endpoint}/api/tags`, {
        signal: controller.signal,
        headers: { Accept: "application/json" },
      });

      clearTimeout(timeoutId);
      const latencyMs = Date.now() - startTime;

      if (!res.ok) {
        return {
          status: "ERROR",
          adapterType: this.id,
          targetEndpoint: endpoint,
          detectedModel: null,
          latencyMs,
          reachable: true,
          modelLoaded: false,
          reason: `Ollama returned HTTP ${res.status}`,
          recommendedAction: `Check Ollama service status at ${endpoint}`,
        };
      }

      const data = await res.json();
      const models = data.models ? data.models.map((m: { name: string }) => m.name) : [];
      const primaryModel = models[0] || "lfm-3b";

      return {
        status: "ONLINE",
        adapterType: this.id,
        targetEndpoint: endpoint,
        detectedModel: primaryModel,
        latencyMs,
        reachable: true,
        modelLoaded: models.length > 0,
        availableModels: models,
        rawDetails: data,
      };
    } catch (err: unknown) {
      const latencyMs = Date.now() - startTime;
      const errorMsg = err instanceof Error ? err.message : String(err);

      return {
        status: "OFFLINE",
        adapterType: this.id,
        targetEndpoint: endpoint,
        detectedModel: null,
        latencyMs,
        reachable: false,
        modelLoaded: false,
        reason: `Ollama unreachable: ${errorMsg}`,
        recommendedAction: `Start Ollama service using 'ollama serve'`,
      };
    }
  }

  async listModels(customEndpoint?: string): Promise<string[]> {
    const health = await this.checkHealth(customEndpoint);
    return health.availableModels || [];
  }

  async chat(request: ChatRequest, customEndpoint?: string): Promise<ChatResponse> {
    const endpoint = customEndpoint || this.defaultEndpoint;
    const startTime = Date.now();
    const timestamp = new Date().toISOString();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 15000);

      const payload = {
        model: request.model || "lfm-3b",
        prompt: request.message,
        stream: false,
      };

      const res = await fetch(`${endpoint}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);
      const latency_ms = Date.now() - startTime;

      if (!res.ok) {
        throw new Error(`Ollama HTTP ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();

      return {
        response: data.response || "",
        model: data.model || request.model || "ollama-model",
        adapterType: this.id,
        latency_ms,
        status: "SUCCESS",
        timestamp,
        targetEndpoint: endpoint,
      };
    } catch (err: unknown) {
      const latency_ms = Date.now() - startTime;
      const errorMsg = err instanceof Error ? err.message : String(err);

      return {
        response: `[OLLAMA ERROR]: ${errorMsg}`,
        model: request.model || "ollama-model",
        adapterType: this.id,
        latency_ms,
        status: "ERROR",
        timestamp,
        targetEndpoint: endpoint,
        diagnostics: {
          status: "ERROR",
          adapterType: this.id,
          targetEndpoint: endpoint,
          detectedModel: null,
          latencyMs: latency_ms,
          reachable: false,
          modelLoaded: false,
          reason: errorMsg,
          recommendedAction: `Start Ollama runtime: 'ollama serve'`,
        },
      };
    }
  }
}
