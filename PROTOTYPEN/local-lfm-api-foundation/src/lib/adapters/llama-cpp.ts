import { ChatRequest, ChatResponse, DiagnosticInfo, ModelAdapter } from "./types";

export class LlamaCppAdapter implements ModelAdapter {
  id = "llama-cpp" as const;
  name = "llama.cpp / Local OpenAI API";
  defaultEndpoint = process.env.LLAMA_CPP_ENDPOINT || "http://127.0.0.1:8080";

  async checkHealth(customEndpoint?: string): Promise<DiagnosticInfo> {
    const endpoint = customEndpoint || this.defaultEndpoint;
    const startTime = Date.now();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);

      const res = await fetch(`${endpoint}/v1/models`, {
        signal: controller.signal,
        headers: { Accept: "application/json" },
      }).catch(async () => {
        return await fetch(`${endpoint}/health`, { signal: controller.signal });
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
          reason: `llama.cpp returned HTTP ${res.status}`,
          recommendedAction: `Check llama.cpp or OpenAI compatible server at ${endpoint}`,
        };
      }

      const data = await res.json().catch(() => ({}));
      const models = data.data ? data.data.map((m: { id: string }) => m.id) : ["lfm-1.0-gguf"];

      return {
        status: "ONLINE",
        adapterType: this.id,
        targetEndpoint: endpoint,
        detectedModel: models[0] || "lfm-1.0-gguf",
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
        reason: `llama.cpp unreachable: ${errorMsg}`,
        recommendedAction: `Start llama.cpp server: './llama-server -m path/to/lfm-model.gguf --port 8080'`,
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
        model: request.model || "lfm-1.0-gguf",
        messages: [{ role: "user", content: request.message }],
        temperature: 0.7,
      };

      const res = await fetch(`${endpoint}/v1/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);
      const latency_ms = Date.now() - startTime;

      if (!res.ok) {
        throw new Error(`llama.cpp HTTP ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();
      const responseText = data.choices?.[0]?.message?.content || "";

      return {
        response: responseText,
        model: data.model || request.model || "llama.cpp-model",
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
        response: `[LLAMA.CPP ERROR]: ${errorMsg}`,
        model: request.model || "llama.cpp-model",
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
          recommendedAction: `Start llama.cpp server on port 8080`,
        },
      };
    }
  }
}
