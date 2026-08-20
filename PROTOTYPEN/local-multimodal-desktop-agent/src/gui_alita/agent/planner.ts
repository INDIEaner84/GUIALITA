/**
 * Planner.
 *
 * Given an intent, build a typed plan (sequence of tool calls). Each step
 * has an action, arguments, and a reason. The agent loop executes one
 * step at a time, observes, and verifies.
 *
 * Plans are deterministic. A future version can ask an LFM2.5 chat model
 * to generate the plan; the typed PlanStep structure remains the same.
 */

import type { Intent } from "./intent";
import type { PlanStep } from "../memory/store";

let stepCounter = 0;
function nextIndex(): number { return stepCounter++; }

export function planFor(intent: Intent, cwd: string): { title: string; steps: PlanStep[] } {
  stepCounter = 0;
  const push = (action: string, args: Record<string, unknown>, reason: string): PlanStep => ({
    index: nextIndex(),
    action,
    arguments: args,
    reason,
    status: "pending",
  });

  switch (intent.kind) {
    case "greeting":
      return { title: "Reply to greeting", steps: [] };
    case "help":
      return { title: "Describe capabilities", steps: [] };
    case "stop":
      return { title: "Stop the agent", steps: [] };
    case "describe_screen":
      return {
        title: "Describe the current desktop",
        steps: [
          push("screenshot", {}, "Capture the desktop so the vision model can analyse it."),
          push("vision_describe", {}, "Run LFM2.5-VL on the captured screenshot."),
        ],
      };
    case "open_application":
      return {
        title: `Open application: ${intent.application}`,
        steps: [
          push("open_application", { application: intent.application }, `Launch ${intent.application}.`),
          push("screenshot", {}, "Verify the application window appeared."),
          push("verify", { expectation: `window for ${intent.application} visible` }, "Confirm the application is on screen."),
        ],
      };
    case "create_directory": {
      const p = resolvePath(intent.path, cwd);
      return {
        title: `Create directory: ${p}`,
        steps: [
          push("terminal_execute", { command: `mkdir -p ${shq(p)}` }, `Create the directory ${p}.`),
          push("verify", { expectation: `directory exists: ${p}` }, "Verify the directory was created."),
        ],
      };
    }
    case "create_file": {
      const p = resolvePath(intent.path, cwd);
      return {
        title: `Create file: ${p}`,
        steps: [
          push("write_file", { path: p, content: intent.content }, `Write ${p}.`),
          push("read_file", { path: p }, "Read back the file to verify."),
        ],
      };
    }
    case "read_file":
      return {
        title: `Read file: ${intent.path}`,
        steps: [push("read_file", { path: resolvePath(intent.path, cwd) }, "Read the requested file.")],
      };
    case "list_directory":
      return {
        title: `List directory: ${intent.path}`,
        steps: [push("list_directory", { path: resolvePath(intent.path, cwd) }, "List the requested directory.")],
      };
    case "search_memory":
      return {
        title: `Search memory: ${intent.query}`,
        steps: [push("memory_search", { query: intent.query }, "Search the WRACK store.")],
      };
    case "continue_previous":
      return {
        title: "Continue previous session",
        steps: [
          push("memory_get_recent", { limit: 5 }, "Fetch the most recent sessions."),
          push("memory_summarise", {}, "Summarise the last session."),
        ],
      };
    case "build_memory_system":
      return {
        title: "Build the WRACK memory system",
        steps: [
          push("memory_check", {}, "Check that the WRACK store is reachable."),
          push("read_file", { path: "src/gui_alita/memory/store.ts" }, "Inspect existing memory code."),
          push("memory_write_self_event", { note: "self-implementation" }, "Record the self-implementation event."),
        ],
      };
    case "implement_feature":
      return {
        title: `Implement feature: ${intent.description}`,
        steps: [
          push("list_directory", { path: "src/gui_alita" }, "Inspect the current source tree."),
          push("task_create", { title: intent.description }, "Create a task for the implementation."),
        ],
      };
    case "terminal_command":
      return {
        title: `Run: ${intent.command}`,
        steps: [push("terminal_execute", { command: intent.command }, "Run the requested command.")],
      };
    case "unknown":
    default:
      return {
        title: "Unknown intent",
        steps: [
          push("reply_text", { text: `I am not sure what to do with: "${intent.text}". Try "help".` },
            "Ask the user for clarification."),
        ],
      };
  }
}

function resolvePath(p: string, cwd: string): string {
  if (p.startsWith("/") || p.startsWith("~")) return p;
  if (p.startsWith("./") || p.startsWith("../")) return p;
  return `${cwd.replace(/\/$/, "")}/${p}`;
}

function shq(s: string): string { return "'" + s.replace(/'/g, "'\\''") + "'"; }
