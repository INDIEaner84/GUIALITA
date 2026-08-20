"use client";

import { useEffect, useState, useRef } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Cpu,
  RefreshCw,
  Send,
  Server,
  Terminal,
  Play,
  Zap,
  Radio,
  XCircle,
  HelpCircle,
  Database,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

type StatusType = "INITIALIZING" | "ONLINE" | "WORKING" | "SUCCESS" | "ERROR" | "OFFLINE";

interface SystemHealth {
  api: {
    status: string;
    latency_ms: number;
    database: string;
    timestamp: string;
  };
  model: {
    adapter: string;
    adapterName: string;
    status: StatusType;
    reachable: boolean;
    modelLoaded: boolean;
    modelName: string;
    targetEndpoint: string;
    latency_ms: number | null;
    availableModels: string[];
  };
  diagnostics: {
    reason: string | null;
    recommendedAction: string | null;
    details: Record<string, unknown> | null;
  };
}

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  model?: string;
  adapter?: string;
  latency_ms?: number;
  timestamp: string;
  status: StatusType;
  targetEndpoint?: string;
  requestText?: string;
}

export default function Home() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loadingHealth, setLoadingHealth] = useState<boolean>(true);
  const [selectedAdapter, setSelectedAdapter] = useState<string>("auto");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState<string>("");
  const [isSending, setIsSending] = useState<boolean>(false);
  const [chatStatus, setChatStatus] = useState<StatusType>("INITIALIZING");
  const [lastLatency, setLastLatency] = useState<number | null>(null);
  const [showDiagnostics, setShowDiagnostics] = useState<boolean>(true);
  const [showArchitecture, setShowArchitecture] = useState<boolean>(false);
  const [e2eTestResult, setE2eTestResult] = useState<{
    running: boolean;
    passed?: boolean;
    message?: string;
    isRealLFM?: boolean;
  }>({ running: false });

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch system health on mount and periodically
  const checkHealth = async () => {
    setLoadingHealth(true);
    try {
      const res = await fetch("/api/health");
      const data: SystemHealth = await res.json();
      setHealth(data);
      if (data.model.status) {
        setChatStatus(data.model.status);
      } else {
        setChatStatus(data.model.reachable ? "ONLINE" : "OFFLINE");
      }
      if (data.model.latency_ms !== null) {
        setLastLatency(data.model.latency_ms);
      }
    } catch {
      setHealth({
        api: { status: "OFFLINE", latency_ms: 0, database: "OFFLINE", timestamp: new Date().toISOString() },
        model: {
          adapter: "lfm",
          adapterName: "Local LFM",
          status: "OFFLINE",
          reachable: false,
          modelLoaded: false,
          modelName: "Unknown",
          targetEndpoint: "http://127.0.0.1:8000",
          latency_ms: null,
          availableModels: [],
        },
        diagnostics: {
          reason: "Failed to connect to Local Assistant API",
          recommendedAction: "Ensure Next.js server is running",
          details: null,
        },
      });
      setChatStatus("OFFLINE");
    } finally {
      setLoadingHealth(false);
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  // Send Chat message
  const handleSendMessage = async (customMessage?: string) => {
    const textToSend = customMessage || inputMessage;
    if (!textToSend.trim() || isSending) return;

    const userMsgId = `user_${Date.now()}`;
    const assistantMsgId = `asst_${Date.now()}`;
    const timestamp = new Date().toLocaleTimeString();

    // Append User message
    const userMsg: ChatMessage = {
      id: userMsgId,
      sender: "user",
      text: textToSend,
      timestamp,
      status: "WORKING",
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!customMessage) setInputMessage("");
    setIsSending(true);
    setChatStatus("WORKING");

    const startTime = Date.now();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: textToSend,
          adapter: selectedAdapter === "auto" ? undefined : selectedAdapter,
        }),
      });

      const data = await res.json();
      const latency = data.latency_ms || Date.now() - startTime;
      setLastLatency(latency);

      const assistantMsg: ChatMessage = {
        id: assistantMsgId,
        sender: "assistant",
        text: data.response,
        model: data.model,
        adapter: data.adapter,
        latency_ms: latency,
        timestamp: new Date(data.timestamp || Date.now()).toLocaleTimeString(),
        status: data.status as StatusType,
        targetEndpoint: data.targetEndpoint,
        requestText: textToSend,
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setChatStatus(data.status === "SUCCESS" ? "SUCCESS" : "ERROR");
    } catch (err: unknown) {
      const latency = Date.now() - startTime;
      const errorMsg = err instanceof Error ? err.message : String(err);

      const assistantMsg: ChatMessage = {
        id: assistantMsgId,
        sender: "assistant",
        text: `[CONNECTION ERROR]: ${errorMsg}`,
        model: health?.model.modelName || "LFM",
        adapter: selectedAdapter,
        latency_ms: latency,
        timestamp: new Date().toLocaleTimeString(),
        status: "ERROR",
        targetEndpoint: health?.model.targetEndpoint || "http://127.0.0.1:8000",
        requestText: textToSend,
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setChatStatus("ERROR");
    } finally {
      setIsSending(false);
      checkHealth();
    }
  };

  // Run Connection Test (Requirement 7)
  const runConnectionTest = async () => {
    setE2eTestResult({ running: true });
    setChatStatus("WORKING");
    try {
      const res = await fetch("/api/test", { method: "POST" });
      const data = await res.json();
      
      setE2eTestResult({
        running: false,
        passed: data.passed,
        message: data.summary,
        isRealLFM: data.isRealLFMResponse,
      });

      if (data.passed) {
        setChatStatus("SUCCESS");
      } else {
        setChatStatus("ERROR");
      }

      const timestamp = new Date().toLocaleTimeString();
      setMessages((prev) => [
        ...prev,
        {
          id: `test_user_${Date.now()}`,
          sender: "user",
          text: data.request.message,
          timestamp,
          status: "SUCCESS",
        },
        {
          id: `test_asst_${Date.now()}`,
          sender: "assistant",
          text: data.response.text,
          model: data.response.model,
          adapter: data.response.adapter,
          latency_ms: data.response.latency_ms,
          timestamp,
          status: data.response.status,
          targetEndpoint: data.response.targetEndpoint,
          requestText: data.request.message,
        },
      ]);
    } catch (err) {
      setE2eTestResult({
        running: false,
        passed: false,
        message: `Test Failed: ${err instanceof Error ? err.message : String(err)}`,
      });
      setChatStatus("ERROR");
    } font: {
      checkHealth();
    }
  };

  const getStatusBadge = (status: StatusType | string) => {
    switch (status) {
      case "ONLINE":
      case "SUCCESS":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            ONLINE
          </span>
        );
      case "WORKING":
      case "INITIALIZING":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
            <RefreshCw className="w-3 h-3 animate-spin text-amber-400" />
            {status}
          </span>
        );
      case "OFFLINE":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30">
            <span className="w-2 h-2 rounded-full bg-rose-400" />
            OFFLINE
          </span>
        );
      case "ERROR":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-red-500/15 text-red-400 border border-red-500/30">
            <XCircle className="w-3 h-3 text-red-400" />
            ERROR
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-slate-500/15 text-slate-400 border border-slate-500/30">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col selection:bg-cyan-500 selection:text-slate-950">
      {/* Header Bar */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-cyan-500/20 to-blue-600/20 rounded-lg border border-cyan-500/30 text-cyan-400">
              <Cpu className="w-6 h-6" />
            </div>
            <div>
              <h1 className="font-bold text-lg tracking-tight text-white flex items-center gap-2">
                LOCAL AI ASSISTANT
                <span className="text-xs font-normal px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800">
                  PHASE 0 — FOUNDATION
                </span>
              </h1>
              <p className="text-xs text-slate-400">
                Local LFM Browser Communication Core
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={runConnectionTest}
              disabled={e2eTestResult.running || isSending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-semibold text-xs transition-all shadow-lg shadow-cyan-950/50 disabled:opacity-50"
            >
              {e2eTestResult.running ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Play className="w-3.5 h-3.5" />
              )}
              LFM CONNECTION TEST
            </button>

            <button
              onClick={checkHealth}
              disabled={loadingHealth}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
              title="Refresh Health & Probes"
            >
              <RefreshCw className={`w-4 h-4 ${loadingHealth ? "animate-spin text-cyan-400" : ""}`} />
            </button>
          </div>
        </div>
      </header>

      {/* Main Grid Layout */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Model & API Status Cards */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          {/* Status Matrix Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2.5 mb-3">
              <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                <Activity className="w-4 h-4 text-cyan-400" />
                SYSTEM STATUS
              </h2>
              <span className="text-[10px] uppercase tracking-wider text-slate-500 font-mono">
                LIVE METRICS
              </span>
            </div>

            <div className="space-y-3 font-mono text-xs">
              {/* MODEL STATUS */}
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-950/60 border border-slate-800/80">
                <span className="text-slate-400 flex items-center gap-1.5 font-medium">
                  <Radio className="w-3.5 h-3.5 text-slate-400" />
                  MODEL:
                </span>
                <span className="font-bold text-slate-200">
                  {health?.model.adapterName || "LFM"}
                </span>
              </div>

              {/* MODEL RUNTIME STATUS */}
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-950/60 border border-slate-800/80">
                <span className="text-slate-400 font-medium">STATUS:</span>
                {getStatusBadge(health?.model.status || chatStatus)}
              </div>

              {/* MODEL NAME */}
              <div className="flex flex-col gap-1 p-2 rounded-lg bg-slate-950/60 border border-slate-800/80">
                <span className="text-slate-400 font-medium text-[11px]">DETECTED MODEL:</span>
                <span className="font-semibold text-cyan-300 truncate font-mono text-xs">
                  {health?.model.modelName || "Searching..."}
                </span>
              </div>

              {/* API STATUS */}
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-950/60 border border-slate-800/80">
                <span className="text-slate-400 flex items-center gap-1.5 font-medium">
                  <Server className="w-3.5 h-3.5 text-slate-400" />
                  API:
                </span>
                {getStatusBadge(health?.api.status || "OFFLINE")}
              </div>

              {/* LATENCY */}
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-950/60 border border-slate-800/80">
                <span className="text-slate-400 flex items-center gap-1.5 font-medium">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  LATENCY:
                </span>
                <span className="font-bold text-amber-400">
                  {lastLatency !== null ? `${lastLatency} ms` : health?.model.latency_ms !== null && health?.model.latency_ms !== undefined ? `${health.model.latency_ms} ms` : "-- ms"}
                </span>
              </div>

              {/* TARGET ENDPOINT */}
              <div className="flex flex-col gap-1 p-2 rounded-lg bg-slate-950/60 border border-slate-800/80">
                <span className="text-slate-400 font-medium text-[11px]">TARGET ENDPOINT:</span>
                <span className="font-mono text-[11px] text-slate-300 truncate">
                  {health?.model.targetEndpoint || "http://127.0.0.1:8000"}
                </span>
              </div>

              {/* DATABASE STATUS */}
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-950/60 border border-slate-800/80">
                <span className="text-slate-400 flex items-center gap-1.5 font-medium">
                  <Database className="w-3.5 h-3.5 text-slate-400" />
                  POSTGRES LOGS:
                </span>
                <span className={`text-xs font-semibold ${health?.api.database === "ONLINE" ? "text-emerald-400" : "text-rose-400"}`}>
                  {health?.api.database || "UNKNOWN"}
                </span>
              </div>
            </div>
          </div>

          {/* Model Backend Selector & Probe Control */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl">
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-cyan-400" />
              BACKEND ADAPTER ROUTING
            </h3>
            <select
              value={selectedAdapter}
              onChange={(e) => setSelectedAdapter(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:outline-none focus:border-cyan-500 font-mono"
            >
              <option value="auto">⚡ Auto-Detect (Native LFM Primary)</option>
              <option value="lfm">🟢 Local LFM Native Engine (port 8000)</option>
              <option value="ollama">🦙 Ollama API (port 11434)</option>
              <option value="llama-cpp">🦙 llama.cpp / OpenAI API (port 8080)</option>
              <option value="lfm-simulator">⚡ Standalone LFM Emulator</option>
            </select>
          </div>

          {/* E2E Test Result Banner */}
          {e2eTestResult.message && (
            <div className={`p-3.5 rounded-xl border text-xs font-mono shadow-xl transition-all ${
              e2eTestResult.passed
                ? "bg-emerald-950/40 border-emerald-500/40 text-emerald-200"
                : "bg-rose-950/40 border-rose-500/40 text-rose-200"
            }`}>
              <div className="flex items-center gap-2 font-bold mb-1">
                {e2eTestResult.passed ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                )}
                {e2eTestResult.passed ? "E2E TEST SUCCESS" : "E2E TEST FAILED"}
              </div>
              <p>{e2eTestResult.message}</p>
              {e2eTestResult.isRealLFM && (
                <div className="mt-2 text-[11px] font-semibold text-cyan-300 bg-cyan-950/60 p-1.5 rounded border border-cyan-800">
                  🎯 Confirmed: Real Native LFM Model response received!
                </div>
              )}
            </div>
          )}

          {/* Technical Diagnostics Drawer */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
            <button
              onClick={() => setShowDiagnostics(!showDiagnostics)}
              className="w-full px-4 py-3 flex items-center justify-between text-xs font-semibold text-slate-300 bg-slate-900 hover:bg-slate-800/80 transition border-b border-slate-800"
            >
              <span className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-cyan-400" />
                TECHNICAL DIAGNOSTICS
              </span>
              {showDiagnostics ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            {showDiagnostics && (
              <div className="p-4 font-mono text-[11px] space-y-3 bg-slate-950/80">
                <div>
                  <span className="text-slate-500 block font-semibold mb-0.5">MODEL STATUS:</span>
                  <span className={`font-bold ${health?.model.reachable ? "text-emerald-400" : "text-rose-400"}`}>
                    {health?.model.status || "OFFLINE"}
                  </span>
                </div>

                <div>
                  <span className="text-slate-500 block font-semibold mb-0.5">REASON:</span>
                  <p className="text-slate-300 bg-slate-900 p-2 rounded border border-slate-800">
                    {health?.diagnostics.reason || (health?.model.reachable ? "No active issues. Connection operational." : "Target server refused connection.")}
                  </p>
                </div>

                <div>
                  <span className="text-slate-500 block font-semibold mb-0.5">TARGET:</span>
                  <code className="text-cyan-300">{health?.model.targetEndpoint || "http://127.0.0.1:8000"}</code>
                </div>

                <div>
                  <span className="text-slate-500 block font-semibold mb-0.5">RECOMMENDED ACTION:</span>
                  <p className="text-amber-300 bg-amber-950/30 p-2 rounded border border-amber-900/40">
                    {health?.diagnostics.recommendedAction || "To run local LFM model server: python3 scripts/lfm_runtime_server.py --port 8000"}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Future Architecture Roadmap Toggle */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
            <button
              onClick={() => setShowArchitecture(!showArchitecture)}
              className="w-full px-4 py-3 flex items-center justify-between text-xs font-semibold text-slate-300 bg-slate-900 hover:bg-slate-800/80 transition"
            >
              <span className="flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-cyan-400" />
                SYSTEM ARCHITECTURE PIPELINE
              </span>
              {showArchitecture ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            {showArchitecture && (
              <div className="p-4 text-xs font-mono space-y-2 bg-slate-950/80 border-t border-slate-800 text-slate-400">
                <div className="p-2 rounded bg-cyan-950/40 border border-cyan-800 text-cyan-300 font-bold">
                  ● PHASE 0 (CURRENT): BROWSER ↔ LOCAL API ↔ LFM MODEL
                </div>
                <div className="pl-4 border-l-2 border-slate-800 space-y-1 text-[11px]">
                  <div>↓ Voice &amp; LFM Audio Pipeline</div>
                  <div>↓ Knowledge Objects &amp; Graph</div>
                  <div>↓ Worker Agents &amp; Planner</div>
                  <div>↓ Coding Agent &amp; Vision</div>
                  <div>↓ Desktop Control &amp; WebRTC</div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Chat Interface & Message Turns */}
        <div className="lg:col-span-8 flex flex-col bg-slate-900 border border-slate-800 rounded-xl shadow-xl overflow-hidden h-[680px]">
          {/* Chat Header */}
          <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
              <h2 className="font-semibold text-sm text-slate-200">
                LFM CONVERSATION STREAM
              </h2>
            </div>
            <div className="text-xs text-slate-400 font-mono">
              MESSAGES: {messages.length}
            </div>
          </div>

          {/* Messages Container */}
          <div className="flex-1 p-4 overflow-y-auto space-y-4 font-sans bg-slate-950/50">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500 space-y-3">
                <Cpu className="w-12 h-12 text-slate-700 animate-pulse" />
                <div>
                  <p className="font-semibold text-slate-300 text-sm">
                    No active messages yet.
                  </p>
                  <p className="text-xs max-w-md mt-1">
                    Send a message or click &quot;LFM CONNECTION TEST&quot; above to verify local communication with the LFM model.
                  </p>
                </div>
                <button
                  onClick={() => handleSendMessage("Hallo LFM, antworte mit:\nLFM CONNECTION TEST OK")}
                  className="mt-2 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-400 border border-slate-700 text-xs font-mono transition"
                >
                  Send Test Message: &quot;Hallo LFM, antworte mit: LFM CONNECTION TEST OK&quot;
                </button>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${
                    msg.sender === "user" ? "items-end" : "items-start"
                  }`}
                >
                  <div
                    className={`max-w-[88%] rounded-xl p-4 shadow-lg ${
                      msg.sender === "user"
                        ? "bg-gradient-to-r from-cyan-600 to-blue-600 text-white rounded-br-none"
                        : "bg-slate-900 border border-slate-800 text-slate-100 rounded-bl-none"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3 mb-1.5 text-[11px] opacity-80 font-mono">
                      <span className="font-bold uppercase tracking-wider">
                        {msg.sender === "user" ? "User" : "Assistant (LFM)"}
                      </span>
                      <span>{msg.timestamp}</span>
                    </div>

                    <p className="text-sm whitespace-pre-wrap leading-relaxed">
                      {msg.text}
                    </p>

                    {/* Message Turn Metadata Display */}
                    {msg.sender === "assistant" && (
                      <div className="mt-3 pt-2.5 border-t border-slate-800 font-mono text-[11px] text-slate-400 grid grid-cols-2 gap-x-4 gap-y-1 bg-slate-950/40 p-2 rounded border border-slate-800/60">
                        <div>
                          <span className="text-slate-500">MODEL:</span>{" "}
                          <span className="text-cyan-300 font-semibold">
                            {msg.model || "lfm-1.0-3b-instruct"}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500">LATENCY:</span>{" "}
                          <span className="text-amber-300 font-semibold">
                            {msg.latency_ms} ms
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500">STATUS:</span>{" "}
                          <span
                            className={`font-semibold ${
                              msg.status === "SUCCESS"
                                ? "text-emerald-400"
                                : "text-rose-400"
                            }`}
                          >
                            {msg.status}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500">ENDPOINT:</span>{" "}
                          <span className="text-slate-300 truncate inline-block max-w-[120px]">
                            {msg.targetEndpoint || "localhost:8000"}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            {isSending && (
              <div className="flex items-center gap-2 text-xs text-amber-400 font-mono bg-amber-950/20 p-3 rounded-lg border border-amber-900/40 w-fit">
                <RefreshCw className="w-4 h-4 animate-spin text-amber-400" />
                Communicating with local LFM model...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Form Footer */}
          <div className="p-4 border-t border-slate-800 bg-slate-900">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder="Nachricht eingeben... (z.B. Hallo)"
                disabled={isSending}
                className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
              />
              <button
                type="submit"
                disabled={!inputMessage.trim() || isSending}
                className="px-5 py-3 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 disabled:text-slate-600 font-semibold text-slate-950 text-sm transition flex items-center gap-2 shadow-lg shadow-cyan-950/50"
              >
                <Send className="w-4 h-4" />
                SEND
              </button>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}
