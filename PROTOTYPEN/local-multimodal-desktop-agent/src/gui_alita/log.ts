/**
 * Structured logger.
 *
 * Writes JSON lines to logs/gui_alita.log and a short human-readable line to
 * stdout. Every important action (startup, model load, inference, tool call,
 * tool result, error, memory write, memory retrieval, agent state transition)
 * goes through this logger.
 */

import fs from "node:fs";
import path from "node:path";
import { config, ensureDirs } from "./config";

let stream: fs.WriteStream | null = null;

function getStream(): fs.WriteStream {
  if (stream) return stream;
  ensureDirs();
  const logFile = path.join(config.paths.logsDir, "gui_alita.log");
  stream = fs.createWriteStream(logFile, { flags: "a" });
  return stream;
}

export type LogLevel = "debug" | "info" | "warn" | "error";

export interface LogEntry {
  ts: string;
  level: LogLevel;
  component: string;
  message: string;
  sessionId?: string;
  [k: string]: unknown;
}

export function log(entry: Partial<LogEntry> & Pick<LogEntry, "level" | "component" | "message">): void {
  const full: LogEntry = { ts: new Date().toISOString(), ...entry } as LogEntry;
  try {
    getStream().write(JSON.stringify(full) + "\n");
  } catch {
    // never let logging crash the agent
  }
  const line =
    `[${full.ts}] ${full.level.toUpperCase()} ` +
    `${full.component}${full.sessionId ? " " + full.sessionId : ""}: ${full.message}`;
  if (full.level === "error") console.error(line);
  else if (full.level === "warn") console.warn(line);
  else console.log(line);
}

export const logger = {
  debug: (component: string, message: string, extra?: Record<string, unknown>) =>
    log({ level: "debug", component, message, ...extra }),
  info: (component: string, message: string, extra?: Record<string, unknown>) =>
    log({ level: "info", component, message, ...extra }),
  warn: (component: string, message: string, extra?: Record<string, unknown>) =>
    log({ level: "warn", component, message, ...extra }),
  error: (component: string, message: string, extra?: Record<string, unknown>) =>
    log({ level: "error", component, message, ...extra }),
};
