import { LFMModelAdapter } from "./lfm";
import { OllamaAdapter } from "./ollama";
import { LlamaCppAdapter } from "./llama-cpp";
import { LFMSimulatorAdapter } from "./simulator";
import { AdapterType, ChatRequest, ChatResponse, DiagnosticInfo, ModelAdapter } from "./types";

export class ModelManager {
  private adapters: Map<AdapterType, ModelAdapter> = new Map();

  constructor() {
    this.adapters.set("lfm", new LFMModelAdapter());
    this.adapters.set("ollama", new OllamaAdapter());
    this.adapters.set("llama-cpp", new LlamaCppAdapter());
    this.adapters.set("lfm-simulator", new LFMSimulatorAdapter());
  }

  getAdapter(type: AdapterType): ModelAdapter {
    const adapter = this.adapters.get(type);
    if (!adapter) {
      return this.adapters.get("lfm-simulator")!;
    }
    return adapter;
  }

  async probeAll(): Promise<Record<AdapterType, DiagnosticInfo>> {
    const results: Partial<Record<AdapterType, DiagnosticInfo>> = {};

    const probePromises = Array.from(this.adapters.entries()).map(async ([key, adapter]) => {
      try {
        const diag = await adapter.checkHealth();
        results[key] = diag;
      } catch (err) {
        results[key] = {
          status: "OFFLINE",
          adapterType: key,
          targetEndpoint: adapter.defaultEndpoint,
          detectedModel: null,
          latencyMs: null,
          reachable: false,
          modelLoaded: false,
          reason: err instanceof Error ? err.message : String(err),
          recommendedAction: `Start ${adapter.name} on ${adapter.defaultEndpoint}`,
        };
      }
    });

    await Promise.all(probePromises);
    return results as Record<AdapterType, DiagnosticInfo>;
  }

  async autoDetectActive(): Promise<{ activeAdapter: ModelAdapter; diagnostics: DiagnosticInfo }> {
    // 1. Check LFM first
    const lfmAdapter = this.adapters.get("lfm")!;
    const lfmHealth = await lfmAdapter.checkHealth();
    if (lfmHealth.reachable && lfmHealth.status === "ONLINE") {
      return { activeAdapter: lfmAdapter, diagnostics: lfmHealth };
    }

    // 2. Check Ollama
    const ollamaAdapter = this.adapters.get("ollama")!;
    const ollamaHealth = await ollamaAdapter.checkHealth();
    if (ollamaHealth.reachable && ollamaHealth.status === "ONLINE") {
      return { activeAdapter: ollamaAdapter, diagnostics: ollamaHealth };
    }

    // 3. Check llama.cpp / OpenAI
    const llamaAdapter = this.adapters.get("llama-cpp")!;
    const llamaHealth = await llamaAdapter.checkHealth();
    if (llamaHealth.reachable && llamaHealth.status === "ONLINE") {
      return { activeAdapter: llamaAdapter, diagnostics: llamaHealth };
    }

    // 4. Fallback to Simulator so user has functional core even when external binary isn't launched yet
    const simAdapter = this.adapters.get("lfm-simulator")!;
    const simHealth = await simAdapter.checkHealth();
    
    // Attach details about why primary native LFM was offline
    simHealth.reason = lfmHealth.reason || "Native LFM server on port 8000 is offline.";
    simHealth.recommendedAction = "To switch to native LFM runtime, launch: python3 scripts/lfm_runtime_server.py --port 8000";

    return { activeAdapter: simAdapter, diagnostics: simHealth };
  }

  async chat(request: ChatRequest, requestedAdapter?: AdapterType): Promise<ChatResponse> {
    if (requestedAdapter && requestedAdapter !== "lfm-simulator") {
      const adapter = this.getAdapter(requestedAdapter);
      const health = await adapter.checkHealth();
      
      // If requested adapter is offline, attempt chat but catch error or return clear diagnostic
      if (!health.reachable) {
        // Run chat attempt (which returns error response with diagnostic object)
        const resp = await adapter.chat(request);
        resp.diagnostics = health;
        return resp;
      }
      return await adapter.chat(request);
    }

    // Auto routing
    const { activeAdapter, diagnostics } = await this.autoDetectActive();
    const resp = await activeAdapter.chat(request);
    resp.diagnostics = diagnostics;
    return resp;
  }
}

export const modelManager = new ModelManager();
