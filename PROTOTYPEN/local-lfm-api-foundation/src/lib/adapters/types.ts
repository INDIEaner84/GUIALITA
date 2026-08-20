export type SystemStatus =
  | "INITIALIZING"
  | "ONLINE"
  | "WORKING"
  | "SUCCESS"
  | "ERROR"
  | "OFFLINE";

export type AdapterType = "lfm" | "ollama" | "llama-cpp" | "openai-local" | "lfm-simulator";

export interface DiagnosticInfo {
  status: SystemStatus;
  adapterType: AdapterType;
  targetEndpoint: string;
  detectedModel: string | null;
  latencyMs: number | null;
  reachable: boolean;
  modelLoaded: boolean;
  reason?: string;
  recommendedAction?: string;
  availableModels?: string[];
  rawDetails?: Record<string, unknown>;
}

export interface ChatRequest {
  message: string;
  model?: string;
  systemPrompt?: string;
}

export interface ChatResponse {
  response: string;
  model: string;
  adapterType: AdapterType;
  latency_ms: number;
  status: SystemStatus;
  timestamp: string;
  targetEndpoint: string;
  isMockFallback?: boolean;
  diagnostics?: DiagnosticInfo;
}

export interface ModelAdapter {
  id: AdapterType;
  name: string;
  defaultEndpoint: string;
  
  checkHealth(endpoint?: string): Promise<DiagnosticInfo>;
  chat(request: ChatRequest, endpoint?: string): Promise<ChatResponse>;
  listModels(endpoint?: string): Promise<string[]>;
}
