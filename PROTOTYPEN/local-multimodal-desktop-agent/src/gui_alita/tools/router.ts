/**
 * Tool router — typed tool schemas, dispatcher, and execution history.
 *
 * The agent loop calls dispatchTool(name, args). Every tool has:
 *   - name
 *   - description
 *   - typed (zod) arguments
 *   - validation
 *   - execution result
 *   - error result
 *   - logging
 */

import { z } from "zod";
import {
  toolScreenshot,
  toolOpenApplication,
  toolTerminalExecute,
  toolReadFile,
  toolWriteFile,
  toolListDirectory,
  toolMouseMove,
  toolMouseClick,
  toolMouseDoubleClick,
  toolMouseScroll,
  toolKeyboardType,
  toolKeyboardPress,
  type ToolResult,
} from "../desktop/engine";
import { evaluateToolCall } from "../safety";
import { logger } from "../log";
import { appendEvent } from "../memory/store";

export const ToolSchemas = {
  screenshot: z.object({}).describe("Capture the current desktop as a PNG."),
  mouse_move: z.object({ x: z.number().int(), y: z.number().int() }).describe("Move the mouse to (x, y)."),
  mouse_click: z.object({
    x: z.number().int(),
    y: z.number().int(),
    button: z.enum(["left", "right", "middle"]).default("left"),
  }),
  mouse_double_click: z.object({ x: z.number().int(), y: z.number().int() }),
  mouse_scroll: z.object({ amount: z.number().int() }),
  keyboard_type: z.object({ text: z.string().min(1).max(2000) }),
  keyboard_press: z.object({ key: z.string().min(1).max(64) }),
  open_application: z.object({ application: z.string().min(1).max(200) }),
  terminal_execute: z.object({ command: z.string().min(1).max(2000) }),
  read_file: z.object({ path: z.string().min(1) }),
  write_file: z.object({ path: z.string().min(1), content: z.string() }),
  list_directory: z.object({ path: z.string().min(1) }),
} as const;

export type ToolName = keyof typeof ToolSchemas;

export const ToolDescriptions: Record<ToolName, string> = {
  screenshot: "Capture the current desktop as a PNG and return its path.",
  mouse_move: "Move the mouse to integer pixel coordinates (x, y).",
  mouse_click: "Click the mouse at (x, y) with the given button.",
  mouse_double_click: "Double-click the mouse at (x, y).",
  mouse_scroll: "Scroll the mouse wheel by a signed amount.",
  keyboard_type: "Type a string at the current focus.",
  keyboard_press: "Press a single named key (e.g. Return, ctrl+c).",
  open_application: "Open a desktop application by name (e.g. terminal, firefox).",
  terminal_execute: "Run a shell command and return stdout/stderr.",
  read_file: "Read a text file and return its content.",
  write_file: "Write a text file (creates or overwrites).",
  list_directory: "List the entries of a directory.",
};

export function listTools(): Array<{ name: ToolName; description: string; schema: unknown }> {
  return (Object.keys(ToolSchemas) as ToolName[]).map((name) => ({
    name,
    description: ToolDescriptions[name],
    schema: ToolSchemas[name],
  }));
}

export interface DispatchContext {
  sessionId: string;
  taskId?: string | null;
}

export async function dispatchTool(
  name: string,
  rawArgs: unknown,
  ctx: DispatchContext,
): Promise<ToolResult> {
  const t0 = Date.now();
  if (!(name in ToolSchemas)) {
    const r: ToolResult = { ok: false, output: "", error: `unknown tool: ${name}` };
    appendEvent({
      sessionId: ctx.sessionId,
      type: "tool_call",
      actor: "agent",
      tool: name,
      arguments: (rawArgs as Record<string, unknown>) ?? null,
      result: { error: r.error },
      status: "failure",
      taskId: ctx.taskId ?? null,
    });
    return r;
  }
  const schema = ToolSchemas[name as ToolName];
  const parsed = schema.safeParse(rawArgs ?? {});
  if (!parsed.success) {
    const r: ToolResult = { ok: false, output: "", error: parsed.error.message };
    appendEvent({
      sessionId: ctx.sessionId,
      type: "tool_call",
      actor: "agent",
      tool: name,
      arguments: (rawArgs as Record<string, unknown>) ?? null,
      result: { error: r.error },
      status: "failure",
      message: "validation failed",
      taskId: ctx.taskId ?? null,
    });
    return r;
  }
  const args = parsed.data as Record<string, unknown>;
  const verdict = evaluateToolCall(name, args);
  if (!verdict.allowed) {
    const r: ToolResult = { ok: false, output: "", error: verdict.reason ?? "blocked" };
    logger.warn("safety", "tool blocked", { tool: name, reason: verdict.reason });
    appendEvent({
      sessionId: ctx.sessionId,
      type: "safety_block",
      actor: "safety",
      tool: name,
      arguments: args,
      result: { reason: verdict.reason },
      status: "blocked",
      taskId: ctx.taskId ?? null,
    });
    return r;
  }

  let result: ToolResult;
  try {
    result = await runTool(name as ToolName, args);
  } catch (e) {
    result = { ok: false, output: "", error: (e as Error).message };
  }

  const latency = Date.now() - t0;
  logger.info("tools", `${name} ${result.ok ? "ok" : "fail"} (${latency}ms)`, {
    args,
    outputLen: result.output?.length ?? 0,
    stub: result.stub ?? false,
  });
  appendEvent({
    sessionId: ctx.sessionId,
    type: "tool_call",
    actor: "agent",
    tool: name,
    arguments: args,
    result: {
      ok: result.ok,
      output: result.output?.slice(0, 2000),
      error: result.error,
      stub: result.stub,
      latencyMs: latency,
      ...(result.data ?? {}),
    },
    status: result.ok ? "success" : "failure",
    taskId: ctx.taskId ?? null,
  });
  return result;
}

async function runTool(name: ToolName, args: Record<string, unknown>): Promise<ToolResult> {
  switch (name) {
    case "screenshot":        return await toolScreenshot();
    case "mouse_move":        return await toolMouseMove(args.x as number, args.y as number);
    case "mouse_click":       return await toolMouseClick(args.x as number, args.y as number, (args.button as "left" | "right" | "middle") ?? "left");
    case "mouse_double_click":return await toolMouseDoubleClick(args.x as number, args.y as number);
    case "mouse_scroll":      return await toolMouseScroll(args.amount as number);
    case "keyboard_type":     return await toolKeyboardType(args.text as string);
    case "keyboard_press":    return await toolKeyboardPress(args.key as string);
    case "open_application":  return await toolOpenApplication(args.application as string);
    case "terminal_execute":  return await toolTerminalExecute(args.command as string);
    case "read_file":         return await toolReadFile(args.path as string);
    case "write_file":        return await toolWriteFile(args.path as string, args.content as string);
    case "list_directory":    return await toolListDirectory(args.path as string);
  }
}
