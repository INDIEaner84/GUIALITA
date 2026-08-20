/**
 * Agent text backend.
 *
 * Generates the assistant's natural-language reply.
 *
 * In a real LFM2.5 deployment this is an LFM2.5 text chat model (called
 * via llama-server or a cloud proxy). In the sandbox it composes the
 * reply deterministically from the step results.
 *
 * The interface is intentionally stable: the agent loop never depends on
 * a specific model, so any chat model can be dropped in.
 */

import type { Intent } from "./intent";
import type { PlanStep } from "../memory/store";
import { config } from "../config";
import { logger } from "../log";

export interface ComposeArgs {
  userText: string;
  intent: Intent;
  plan: { title: string; steps: PlanStep[] };
  stepResults: Array<{ action: string; result: unknown; ok: boolean }>;
  lastError: string | null;
}

export interface AgentTextBackend {
  compose(args: ComposeArgs): Promise<string>;
}

class StubTextBackend implements AgentTextBackend {
  async compose(args: ComposeArgs): Promise<string> {
    const { intent, stepResults, lastError, userText, plan } = args;
    if (stepResults.length === 0) {
      switch (intent.kind) {
        case "greeting": return "Hello! I am GUIALITA. I can see your desktop, open applications, run terminal commands, and remember our conversations. Try saying: \"look at my desktop\" or \"create a directory called test-agent\".";
        case "help": return "I can: capture & describe the screen, open applications, run terminal commands, manage files, and remember everything in WRACK. Try one of the example commands in the UI.";
        case "stop": return "Stopped. Send a new request to continue.";
        default: return `I understood your request "${userText}" but produced no plan steps.`;
      }
    }
    const lines: string[] = [];
    lines.push(`I worked on: ${plan.title}.`);
    for (const r of stepResults) {
      const out = typeof r.result === "string" ? r.result.trim() : "";
      lines.push(`${r.ok ? "✅" : "❌"} ${r.action}${out ? `: ${out.slice(0, 400)}` : ""}`);
    }
    if (lastError) lines.push(`(one step failed: ${lastError})`);
    lines.push("Anything else?");
    return lines.join("\n");
  }
}

class LocalTextBackend implements AgentTextBackend {
  async compose(args: ComposeArgs): Promise<string> {
    // Real deployment: POST to /v1/chat/completions on a llama-server.
    if (!config.agent.endpoint) {
      logger.warn("agent", "no GUIALITA_AGENT_ENDPOINT; falling back to stub");
      return new StubTextBackend().compose(args);
    }
    const sys = "You are GUIALITA, a multimodal desktop agent. Speak concisely and report what you did.";
    const user = `User: ${args.userText}\nPlan: ${args.plan.title}\nResults:\n` +
      args.stepResults.map((r) => `- ${r.ok ? "OK" : "FAIL"} ${r.action}: ${truncate(String(r.result ?? ""), 200)}`).join("\n") +
      (args.lastError ? `\nLast error: ${args.lastError}` : "");
    const res = await fetch(`${config.agent.endpoint}/v1/chat/completions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        model: config.agent.model,
        messages: [
          { role: "system", content: sys },
          { role: "user", content: user },
        ],
        max_tokens: 256,
        temperature: 0.2,
      }),
    });
    if (!res.ok) throw new Error(`agent text backend ${res.status}`);
    const data = await res.json() as { choices: Array<{ message: { content: string } }> };
    return data.choices[0]?.message?.content ?? "(empty)";
  }
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
}

let _backend: AgentTextBackend | null = null;
export function getAgentTextBackend(): AgentTextBackend {
  if (_backend) return _backend;
  switch (config.agent.provider) {
    case "local-llama-text":
    case "cloud":
      _backend = new LocalTextBackend();
      break;
    default:
      _backend = new StubTextBackend();
  }
  return _backend;
}
