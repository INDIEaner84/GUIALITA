import { ChatRequest, ChatResponse, DiagnosticInfo, ModelAdapter } from "./types";

export class LFMModelAdapter implements ModelAdapter {
  id = "lfm" as const;
  name = "Local LFM (Liquid Foundation Model)";
  defaultEndpoint = process.env.LFM_ENDPOINT || "http://127.0.0.1:8000";

  async checkHealth(customEndpoint?: string): Promise<DiagnosticInfo> {
    const endpoint = customEndpoint || this.defaultEndpoint;
    const startTime = Date.now();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);

      // Try checking health / info endpoint
      const res = await fetch(`${endpoint}/health`, {
        signal: controller.signal,
        headers: { Accept: "application/json" },
      }).catch(async () => {
        // Fallback check v1/models if /health doesn't respond
        return await fetch(`${endpoint}/v1/models`, {
          signal: controller.signal,
          headers: { Accept: "application/json" },
        });
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
          reason: `LFM HTTP server returned status ${res.status} ${res.statusText}`,
          recommendedAction: `Check LFM server configuration and ensure a model is loaded at ${endpoint}.`,
        };
      }

      const data = await res.json().catch(() => ({}));
      const modelName = data.model || data.active_model || data.data?.[0]?.id || "lfm-1.0-3b-instruct";
      const availableModels = data.models || (data.data ? data.data.map((m: { id: string }) => m.id) : [modelName]);

      return {
        status: "ONLINE",
        adapterType: this.id,
        targetEndpoint: endpoint,
        detectedModel: modelName,
        latencyMs,
        reachable: true,
        modelLoaded: true,
        availableModels,
        rawDetails: data,
      };
    } catch (err: unknown) {
      const latencyMs = Date.now() - startTime;
      const errorMessage = err instanceof Error ? err.message : String(err);
      const isRefused = errorMessage.includes("ECONNREFUSED") || errorMessage.includes("fetch failed") || errorMessage.includes("aborted");

      return {
        status: "OFFLINE",
        adapterType: this.id,
        targetEndpoint: endpoint,
        detectedModel: null,
        latencyMs,
        reachable: false,
        modelLoaded: false,
        reason: isRefused
          ? `Connection refused at ${endpoint}`
          : `LFM runtime unreachable: ${errorMessage}`,
        recommendedAction: `Start the local LFM runtime service on ${endpoint}. Command: python3 scripts/lfm_runtime_server.py --port 8000`,
      };
    }
  }

  async listModels(customEndpoint?: string): Promise<string[]> {
    const health = await this.checkHealth(customEndpoint);
    return health.availableModels || ["lfm-1.0-3b-instruct", "lfm-lite", "lfm-7b-instruct"];
  }

  async chat(request: ChatRequest, customEndpoint?: string): Promise<ChatResponse> {
    const endpoint = customEndpoint || this.defaultEndpoint;
    const startTime = Date.now();
    const timestamp = new Date().toISOString();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 15000);

      // Try LFM specific format or OpenAI format
      const payload = {
        model: request.model || "lfm-1.0-3b-instruct",
        messages: [
          ...(request.systemPrompt ? [{ role: "system", content: request.systemPrompt }] : []),
          { role: "user", content: request.message },
        ],
        prompt: request.message, // for legacy endpoints
        temperature: 0.7,
      };

      const res = await fetch(`${endpoint}/v1/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      }).catch(async () => {
        // Direct /chat alternative
        return await fetch(`${endpoint}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: request.message, model: request.model }),
          signal: controller.signal,
        });
      });

      clearTimeout(timeoutId);
      const latency_ms = Date.now() - startTime;

      if (!res.ok) {
        throw new Error(`LFM endpoint returned HTTP ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();
      let responseText = "";

      if (data.choices?.[0]?.message?.content) {
        responseText = data.choices[0].message.content;
      } else if (data.response) {
        responseText = data.response;
      } else if (data.text) {
        responseText = data.text;
      } else {
        responseText = JSON.stringify(data);
      }

      return {
        response: responseText,
        model: data.model || request.model || "lfm-1.0-3b-instruct",
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
        response: `[LFM ERROR]: ${errorMsg}`,
        model: request.model || "lfm-1.0-3b-instruct",
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
          recommendedAction: `Verify LFM runtime at ${endpoint}. Ensure service is running with 'python3 scripts/lfm_runtime_server.py --port 8000'`,
        },
      };
    }
  }
}
