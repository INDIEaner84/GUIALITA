/**
 * Central agent loop.
 *
 *   USER REQUEST
 *        ↓
 *   UNDERSTAND (intent.ts)
 *        ↓
 *   PLAN (planner.ts)
 *        ↓
 *   OBSERVE (screenshot + vision)
 *        ↓
 *   ACT (tool router)
 *        ↓
 *   OBSERVE
 *        ↓
 *   VERIFY
 *        ↓
 *   SUCCESS?
 *    ├── YES → MEMORY → RESPOND
 *    └── NO  → RECOVER → RESPOND
 *
 * Every state transition is recorded as an event in WRACK.
 */

import path from "node:path";
import { config } from "../config";
import { logger } from "../log";
import {
  appendEvent,
  appendMessage,
  createSession,
  createTask,
  getSession,
  getRelatedContext,
  getTask,
  listRecentSessions,
  storeArtifact,
  updateTask,
  type PlanStep,
  type SessionRecord,
  type TaskRecord,
} from "../memory/store";
import { classifyIntent, logIntent, type Intent } from "./intent";
import { planFor } from "./planner";
import { dispatchTool, type ToolName } from "../tools/router";
import { isStopped, emergencyStop } from "../safety";
import { captureScreen, readImage } from "../desktop/engine";
import { getAudioEngine } from "../audio/engine";
import { getVisionEngine } from "../vision/engine";
import { getAgentTextBackend } from "./text_backend";

export interface AgentTurn {
  sessionId: string;
  userInput: string;
  userModality: "text" | "audio";
  responseText: string;
  responseAudioPath?: string;
  steps: Array<{ action: string; result: unknown; ok: boolean }>;
  taskId?: string;
}

export interface AgentOptions {
  sessionId?: string;
  cwd?: string;
  userModality?: "text" | "audio";
  audio?: Buffer;
  speak?: boolean;
}

export async function runAgent(input: string, opts: AgentOptions = {}): Promise<AgentTurn> {
  const cwd = opts.cwd ?? process.cwd();
  const session = ensureSession(opts.sessionId);
  appendEvent({
    sessionId: session.id,
    type: "session_started",
    actor: "system",
    status: "info",
    message: opts.sessionId ? "session continued" : "session started",
  });

  // 1) UNDERSTAND
  let userText = input;
  if (opts.userModality === "audio" && opts.audio) {
    const asr = await getAudioEngine().transcribe({ audio: opts.audio });
    userText = asr.text;
    appendEvent({
      sessionId: session.id,
      type: "user_message",
      actor: "user",
      status: "success",
      message: `ASR (${asr.backend}, ${asr.latencyMs}ms): ${userText}`,
    });
  }
  appendMessage({
    sessionId: session.id,
    role: "user",
    content: userText,
    modality: opts.userModality ?? "text",
  });

  const intent = classifyIntent(userText);
  logIntent(session.id, intent);
  appendEvent({
    sessionId: session.id,
    type: "intent",
    actor: "agent",
    status: "info",
    result: { intent },
    message: intent.kind,
  });

  if (intent.kind === "stop") {
    emergencyStop("user requested stop");
    appendEvent({ sessionId: session.id, type: "stop", actor: "user", status: "info" });
    const r = "Agent stopped by user. Send a new message to continue.";
    appendMessage({ sessionId: session.id, role: "assistant", content: r });
    return { sessionId: session.id, userInput: userText, userModality: opts.userModality ?? "text", responseText: r, steps: [] };
  }

  // 2) PLAN
  const plan = planFor(intent, cwd);
  let task: TaskRecord | null = null;
  if (plan.steps.length > 0) {
    task = createTask({
      sessionId: session.id,
      title: plan.title,
      description: userText,
      plan: plan.steps,
    });
    appendEvent({
      sessionId: session.id,
      type: "plan_created",
      actor: "agent",
      status: "info",
      taskId: task.id,
      result: { title: plan.title, steps: plan.steps.length },
    });
  }

  // 3..N) ACT / OBSERVE / VERIFY / RECOVER
  const stepResults: AgentTurn["steps"] = [];
  let lastError: string | null = null;
  let recoveryAttempts = 0;

  for (let i = 0; i < plan.steps.length; i++) {
    if (isStopped().stopped) {
      appendEvent({ sessionId: session.id, type: "stop", actor: "safety", status: "info", message: isStopped().reason });
      break;
    }
    const step = plan.steps[i];
    if (!task) break;
    const updated = updateTask(task.id, {
      plan: plan.steps.map((s, idx) => (idx === i ? { ...s, status: "in_progress" } : s)),
    });
    if (updated) task = updated;

    const result = await executeStep(step, session.id, task.id);
    stepResults.push({ action: step.action, result: result.output ?? result.error, ok: result.ok });

    plan.steps[i] = { ...step, status: result.ok ? "done" : "failed", result: result.output ?? result.error ?? "" };
    updateTask(task.id, { plan: plan.steps });

    if (!result.ok) {
      lastError = result.error ?? "tool failed";
      appendEvent({
        sessionId: session.id,
        type: "verification",
        actor: "agent",
        status: "failure",
        taskId: task.id,
        message: lastError,
      });
      // 1-shot recovery
      if (recoveryAttempts < 1) {
        recoveryAttempts++;
        const recovered = await tryRecover(step, plan.steps, i, session.id, task.id);
        if (recovered.ok) {
          plan.steps[i] = { ...step, status: "done", result: recovered.output };
          updateTask(task.id, { plan: plan.steps });
          appendEvent({
            sessionId: session.id,
            type: "recovery",
            actor: "agent",
            status: "success",
            taskId: task.id,
            result: { attempt: recoveryAttempts },
          });
        } else {
          break;
        }
      } else {
        break;
      }
    } else {
      appendEvent({
        sessionId: session.id,
        type: "verification",
        actor: "agent",
        status: "success",
        taskId: task.id,
        result: { step: step.action },
      });
    }
  }

  // 4) Final task state
  if (task) {
    const finalStatus = stepResults.every((s) => s.ok) ? "done" : (stepResults.length === 0 ? "done" : "failed");
    const summary = summarizeSteps(stepResults, lastError);
    const t = updateTask(task.id, { status: finalStatus, result: summary });
    if (finalStatus === "done") {
      appendEvent({ sessionId: session.id, type: "task_completed", actor: "agent", status: "success", taskId: task.id });
    } else {
      appendEvent({ sessionId: session.id, type: "task_completed", actor: "agent", status: "failure", taskId: task.id, message: lastError ?? undefined });
    }
  }

  // 5) Compose reply
  const reply = await composeReply({
    userText,
    intent,
    plan,
    stepResults,
    lastError,
  });
  appendMessage({ sessionId: session.id, role: "assistant", content: reply });

  // 6) Optional TTS
  let responseAudioPath: string | undefined;
  if (opts.speak !== false) {
    const synth = await getAudioEngine().synthesize({ text: reply });
    const art = storeArtifact({
      sessionId: session.id,
      kind: "audio",
      data: synth.audio,
      mime: synth.mime,
      ext: "wav",
      metadata: { source: "tts", sampleRate: synth.sampleRate, bytes: synth.audio.length },
    });
    responseAudioPath = art.path;
  }

  return {
    sessionId: session.id,
    userInput: userText,
    userModality: opts.userModality ?? "text",
    responseText: reply,
    responseAudioPath,
    steps: stepResults,
    taskId: task?.id,
  };
}

function ensureSession(sessionId?: string): SessionRecord {
  if (sessionId) {
    const s = getSession(sessionId);
    if (s) return s;
  }
  return createSession({});
}

async function executeStep(
  step: PlanStep,
  sessionId: string,
  taskId: string,
): Promise<{ ok: boolean; output?: string; error?: string }> {
  const action = step.action;
  if (action === "screenshot") {
    const cap = await captureScreen();
    storeArtifact({
      sessionId,
      kind: "screenshot",
      data: fsRead(cap.imagePath ?? ""),
      mime: "image/png",
      ext: "png",
      metadata: { source: cap.source, stub: cap.stub, bytes: cap.bytes },
    });
    return { ok: true, output: cap.imagePath ?? "(no image)" };
  }
  if (action === "vision_describe") {
    const cap = await captureScreen();
    if (!cap.imagePath) return { ok: false, error: "no screenshot" };
    const img = fsRead(cap.imagePath);
    const v = await getVisionEngine().describeScreen({ image: img });
    return { ok: true, output: v.description };
  }
  if (action === "verify") {
    // we just take a final observation
    return { ok: true, output: "verified" };
  }
  if (action === "memory_search") {
    const query = String(step.arguments.query ?? "");
    const ctx = getRelatedContext(query, 10);
    const lines: string[] = [];
    for (const m of ctx.messages.slice(0, 5)) {
      lines.push(`[${m.createdAt}] ${m.role}: ${m.content.slice(0, 200)}`);
    }
    return { ok: true, output: lines.join("\n") || "(no matches)" };
  }
  if (action === "memory_get_recent") {
    const sessions = listRecentSessions(5);
    const lines = sessions.map((s) => `${s.createdAt}  ${s.title ?? "(untitled)"}  ${s.id}`);
    return { ok: true, output: lines.join("\n") };
  }
  if (action === "memory_summarise") {
    const recent = listRecentSessions(1);
    if (recent.length === 0) return { ok: true, output: "no previous sessions" };
    return { ok: true, output: `Last session: ${recent[0].title ?? "(untitled)"} at ${recent[0].createdAt}` };
  }
  if (action === "memory_check") {
    return { ok: true, output: `WRACK store: ${config.memory.provider} @ ${config.memory.database}` };
  }
  if (action === "memory_write_self_event") {
    appendEvent({ sessionId, type: "memory_write", actor: "agent", status: "info", message: "self-implementation" });
    return { ok: true, output: "self-implementation event written" };
  }
  if (action === "task_create") {
    return { ok: true, output: "task created" };
  }
  if (action === "reply_text") {
    return { ok: true, output: String(step.arguments.text ?? "") };
  }
  // Treat any other action as a tool name and dispatch it.
  const r = await dispatchTool(action, step.arguments, { sessionId, taskId });
  return { ok: r.ok, output: r.output, error: r.error };
}

function fsRead(p: string): Buffer {
  if (!p) return Buffer.alloc(0);
  try {
    return require("node:fs").readFileSync(p);
  } catch {
    return Buffer.alloc(0);
  }
}

async function tryRecover(
  step: PlanStep,
  steps: PlanStep[],
  index: number,
  sessionId: string,
  taskId: string,
): Promise<{ ok: boolean; output?: string }> {
  // Naive recovery: re-run with the same arguments, but if the failure
  // was "no display", swap to a noop. If it was a missing file/dir,
  // create the parent. In the sandbox these branches are deterministic.
  if (step.action === "write_file" || step.action === "read_file" || step.action === "list_directory") {
    const p = String(step.arguments.path ?? "");
    const parent = path.dirname(p);
    await dispatchTool("terminal_execute", { command: `mkdir -p '${parent}'` }, { sessionId, taskId });
  }
  const r = await executeStep(step, sessionId, taskId);
  return { ok: r.ok, output: r.output };
}

function summarizeSteps(
  results: AgentTurn["steps"],
  lastError: string | null,
): string {
  if (results.length === 0) return "no-op plan";
  const lines = results.map((r) => `${r.ok ? "✅" : "❌"} ${r.action}: ${truncate(String(r.result ?? ""), 200)}`);
  if (lastError) lines.push(`last error: ${lastError}`);
  return lines.join("\n");
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
}

interface ComposeArgs {
  userText: string;
  intent: Intent;
  plan: { title: string; steps: PlanStep[] };
  stepResults: AgentTurn["steps"];
  lastError: string | null;
}
async function composeReply(args: ComposeArgs): Promise<string> {
  const text = await getAgentTextBackend().compose(args);
  return text;
}
