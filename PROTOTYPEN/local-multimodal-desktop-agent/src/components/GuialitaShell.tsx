"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { config as publicConfig } from "@/gui_alita/config_public";

type Role = "user" | "assistant" | "system" | "tool";
type Modality = "text" | "audio" | "image" | "screen";

interface Message {
  id?: string;
  role: Role;
  content: string;
  modality?: Modality;
  createdAt?: string;
}

interface Step {
  action: string;
  result: string;
  ok: boolean;
}

interface TurnResponse {
  ok: boolean;
  sessionId: string;
  userText: string;
  responseText: string;
  responseAudioUrl?: string;
  steps: Step[];
  taskId?: string;
}

interface SessionSummary {
  id: string;
  title: string | null;
  createdAt: string;
}

export default function GuialitaShell() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hello, I am GUIALITA. I can hear you, see your desktop, run terminal commands, and remember our conversations.",
      modality: "text",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<"IDLE" | "THINKING" | "ACTING" | "SPEAKING">("IDLE");
  const [audioOn, setAudioOn] = useState<boolean>(true);
  const [recording, setRecording] = useState<boolean>(false);
  const [stopped, setStopped] = useState<boolean>(false);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [lastSteps, setLastSteps] = useState<Step[]>([]);
  const [screenshotUrl, setScreenshotUrl] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // load session list
  useEffect(() => {
    void (async () => {
      try {
        const r = await fetch("/api/agent/memory?action=sessions");
        const j = await r.json();
        if (j.ok) setSessions(j.sessions);
      } catch { /* ignore */ }
    })();
  }, [sessionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 9_999_999, behavior: "smooth" });
  }, [messages]);

  const send = useCallback(async (textOverride?: string) => {
    const text = (textOverride ?? input).trim();
    if (!text || busy) return;
    setBusy(true);
    setStatus("THINKING");
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text, modality: "text" }]);

    try {
      const r = await fetch("/api/agent/turn", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text, sessionId, speak: audioOn }),
      });
      const j: TurnResponse = await r.json();
      if (!j.ok) {
        setMessages((m) => [...m, { role: "assistant", content: "(error) " + (j as unknown as { error: string }).error }]);
      } else {
        setSessionId(j.sessionId);
        setLastSteps(j.steps);
        setMessages((m) => [...m, { role: "assistant", content: j.responseText, modality: "text" }]);
        if (audioOn && j.responseAudioUrl) {
          setStatus("SPEAKING");
          if (audioRef.current) {
            audioRef.current.src = j.responseAudioUrl;
            try { await audioRef.current.play(); } catch { /* user gesture */ }
          }
        }
        // refresh the latest screenshot if one was taken
        if (j.steps.some((s) => s.action === "screenshot")) {
          try {
            const cap = await fetch("/api/desktop/screenshot", { method: "POST" });
            const cj = await cap.json() as { ok: boolean; imagePath?: string };
            if (cj.ok && cj.imagePath) {
              setScreenshotUrl(`/api/desktop/screenshot?ts=${Date.now()}&path=${encodeURIComponent(cj.imagePath)}`);
            }
          } catch { /* ignore */ }
        }
      }
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: "(network error) " + (e as Error).message }]);
    } finally {
      setBusy(false);
      setStatus("IDLE");
    }
  }, [audioOn, busy, input, sessionId]);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const buf = await blob.arrayBuffer();
        const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
        setStatus("THINKING");
        setBusy(true);
        setMessages((m) => [...m, { role: "user", content: "(voice input)", modality: "audio" }]);
        try {
          const r = await fetch("/api/agent/turn", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ sessionId, modality: "audio", audioBase64: b64, speak: audioOn }),
          });
          const j: TurnResponse = await r.json();
          if (j.ok) {
            setSessionId(j.sessionId);
            setLastSteps(j.steps);
            setMessages((m) => [...m, { role: "assistant", content: j.responseText, modality: "text" }]);
            if (audioOn && j.responseAudioUrl && audioRef.current) {
              setStatus("SPEAKING");
              audioRef.current.src = j.responseAudioUrl;
              try { await audioRef.current.play(); } catch { /* ignore */ }
            }
          } else {
            setMessages((m) => [...m, { role: "assistant", content: "(error) ASR pipeline failed" }]);
          }
        } catch {
          setMessages((m) => [...m, { role: "assistant", content: "(network error)" }]);
        } finally {
          setBusy(false);
          setStatus("IDLE");
        }
      };
      rec.start();
      mediaRecorderRef.current = rec;
      setRecording(true);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "Microphone access denied or unavailable. Try the text input instead." }]);
    }
  }, [audioOn, sessionId]);

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }, []);

  const stopAgent = useCallback(async () => {
    await fetch("/api/agent/stop", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ action: "stop" }) });
    setStopped(true);
  }, []);
  const resumeAgent = useCallback(async () => {
    await fetch("/api/agent/stop", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ action: "resume" }) });
    setStopped(false);
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <audio ref={audioRef} hidden />

      <header className="border-b border-slate-800 bg-slate-900/70 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">GUIALITA <span className="text-slate-500 font-normal">— local multimodal desktop agent</span></h1>
          <p className="text-xs text-slate-400 mt-1">voice · vision · desktop control · WRACK memory</p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className={`px-2 py-1 rounded ${status === "IDLE" ? "bg-emerald-900/60 text-emerald-300" : "bg-amber-900/60 text-amber-200"}`}>{status}</span>
          {stopped && <span className="px-2 py-1 rounded bg-red-900/60 text-red-200">STOPPED</span>}
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4 p-4 h-[calc(100vh-72px)]">
        <section className="flex flex-col bg-slate-900/40 border border-slate-800 rounded-2xl overflow-hidden">
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-2xl px-4 py-2 whitespace-pre-wrap text-sm leading-relaxed ${
                  m.role === "user" ? "bg-sky-700/60 text-white" :
                  m.role === "assistant" ? "bg-slate-800 text-slate-100" :
                  "bg-amber-900/40 text-amber-100"
                }`}>
                  <div className="text-[10px] uppercase tracking-wide opacity-60 mb-1">
                    {m.role === "user" ? "You" : m.role === "assistant" ? "GUIALITA" : m.role}
                    {m.modality && m.modality !== "text" ? ` · ${m.modality}` : ""}
                  </div>
                  {m.content}
                </div>
              </div>
            ))}
            {lastSteps.length > 0 && (
              <div className="mt-2 border-t border-slate-800 pt-2 text-xs text-slate-400">
                <div className="font-semibold mb-1">Last plan steps</div>
                {lastSteps.map((s, i) => (
                  <div key={i} className="font-mono">{s.ok ? "✅" : "❌"} {s.action} — {String(s.result ?? "").slice(0, 160)}</div>
                ))}
              </div>
            )}
          </div>
          <div className="border-t border-slate-800 p-3 flex items-center gap-2">
            <button
              onClick={() => (recording ? stopRecording() : startRecording())}
              disabled={busy}
              className={`px-3 py-2 rounded-xl text-sm font-medium border ${recording ? "bg-red-700/80 border-red-500" : "bg-slate-800 border-slate-700 hover:bg-slate-700"}`}
              title="Press to speak"
            >
              {recording ? "■ Stop" : "🎤 Speak"}
            </button>
            <button
              onClick={async () => {
                setStatus("ACTING");
                const r = await fetch("/api/desktop/screenshot", { method: "POST" });
                const j = await r.json() as { ok: boolean; imagePath?: string };
                if (j.ok && j.imagePath) {
                  setScreenshotUrl(`/api/desktop/screenshot?path=${encodeURIComponent(j.imagePath)}&ts=${Date.now()}`);
                }
                setStatus("IDLE");
              }}
              className="px-3 py-2 rounded-xl text-sm bg-slate-800 border border-slate-700 hover:bg-slate-700"
              title="Capture screen now"
            >
              📷 Screen
            </button>
            {stopped
              ? <button onClick={resumeAgent} className="px-3 py-2 rounded-xl text-sm bg-emerald-800 border border-emerald-700 hover:bg-emerald-700">▶ Resume</button>
              : <button onClick={stopAgent} className="px-3 py-2 rounded-xl text-sm bg-red-800 border border-red-700 hover:bg-red-700">⏹ STOP AGENT</button>}
            <label className="ml-auto text-xs flex items-center gap-1 text-slate-400">
              <input type="checkbox" checked={audioOn} onChange={(e) => setAudioOn(e.target.checked)} /> voice reply
            </label>
            <input
              className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm outline-none focus:border-sky-500"
              placeholder="Say or type something…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") void send(); }}
              disabled={busy}
            />
            <button
              onClick={() => void send()}
              disabled={busy || !input.trim()}
              className="px-4 py-2 rounded-xl text-sm bg-sky-600 hover:bg-sky-500 disabled:bg-slate-700 disabled:text-slate-500 font-medium"
            >
              Send
            </button>
          </div>
        </section>

        <aside className="flex flex-col gap-3 overflow-hidden">
          <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-3">
            <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">Desktop</div>
            {screenshotUrl
              ? <img alt="screenshot" src={screenshotUrl} className="w-full rounded border border-slate-800" />
              : <div className="aspect-video w-full rounded border border-dashed border-slate-700 grid place-items-center text-slate-500 text-xs">no screenshot yet — press 📷</div>}
          </div>
          <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-3 flex-1 overflow-y-auto">
            <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">Recent sessions (WRACK)</div>
            {sessions.length === 0 && <div className="text-slate-500 text-xs">no sessions yet</div>}
            <ul className="space-y-1 text-xs">
              {sessions.map((s) => (
                <li key={s.id} className={`p-2 rounded border ${sessionId === s.id ? "border-sky-600 bg-sky-900/30" : "border-slate-800 bg-slate-900/40"}`}>
                  <div className="font-mono text-[10px] text-slate-500">{s.id.slice(0, 8)} · {new Date(s.createdAt).toLocaleString()}</div>
                  <div className="text-slate-200">{s.title ?? "(untitled)"}</div>
                  <button
                    className="text-[10px] text-sky-400 hover:underline mt-1"
                    onClick={async () => {
                      const r = await fetch(`/api/agent/memory?action=session&sessionId=${s.id}`);
                      const j = await r.json() as { ok: boolean; session?: { id: string }; messages?: Message[] };
                      if (j.ok && j.session) {
                        setSessionId(j.session.id);
                        setMessages(j.messages ?? []);
                      }
                    }}
                  >open</button>
                </li>
              ))}
            </ul>
          </div>
          <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-3 text-[11px] text-slate-400 space-y-1">
            <div className="uppercase tracking-wider text-slate-500 mb-1">Config</div>
            <div>audio: <span className="text-slate-200">{publicConfig.audio.provider}</span></div>
            <div>vision: <span className="text-slate-200">{publicConfig.vision.provider}</span></div>
            <div>agent: <span className="text-slate-200">{publicConfig.agent.provider}</span></div>
            <div>memory: <span className="text-slate-200">{publicConfig.memory.provider}</span></div>
            <div>desktop control: <span className="text-slate-200">{publicConfig.desktop.controlEnabled ? "on" : "off"}</span></div>
            <div>model: <span className="text-slate-200">{publicConfig.vision.model}</span></div>
          </div>
        </aside>
      </div>
    </main>
  );
}
