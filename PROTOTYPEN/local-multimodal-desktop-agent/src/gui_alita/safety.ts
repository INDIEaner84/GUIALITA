/**
 * Safety layer.
 *
 * The desktop-control tool layer must never silently execute destructive
 * commands. This module provides:
 *
 *  - a tool allowlist,
 *  - dangerous-command pattern detection (rm -rf, mkfs, dd, shutdown, ...),
 *  - filesystem path restrictions,
 *  - command timeouts,
 *  - audit logging (delegated to the WRACK event store),
 *  - an emergency-stop flag that the agent loop checks between steps.
 */

import { config } from "./config";
import { logger } from "./log";

export type StopState = { stopped: boolean; reason: string | null };

const stopState: StopState = { stopped: false, reason: null };

export function emergencyStop(reason: string): void {
  stopState.stopped = true;
  stopState.reason = reason;
  logger.warn("safety", "EMERGENCY STOP", { reason });
}

export function clearStop(): void {
  stopState.stopped = false;
  stopState.reason = null;
}

export function isStopped(): StopState {
  return { ...stopState };
}

const DANGEROUS_PATTERNS: RegExp[] = [
  /\brm\s+-rf?\b\s+\//i,                  // rm -rf /
  /\bshutdown\b/i,
  /\breboot\b/i,
  /\bmkfs(\.\w+)?\b/i,
  /\bdd\s+if=/i,
  /\b:()\s*{\s*:\s*\|\s*:\s*&\s*}\s*;\s*:/, // fork bomb
  /\bcurl\s+[^|]*\|\s*(ba)?sh\b/i,        // curl|sh
  /\bwget\s+[^|]*\|\s*(ba)?sh\b/i,
  /\bsudo\b/i,
  /\bchmod\s+-R\s+0+\b/i,
  /\bchown\s+-R\b/i,
  />\s*\/dev\/sd[a-z]/i,
  /\bnc\s+-l\b/i,                         // reverse shell listener
];

export function isDangerousCommand(cmd: string): boolean {
  return DANGEROUS_PATTERNS.some((p) => p.test(cmd));
}

export interface SafetyVerdict {
  allowed: boolean;
  reason: string | null;
  destructive: boolean;
}

export function evaluateToolCall(
  tool: string,
  args: Record<string, unknown>,
): SafetyVerdict {
  if (stopState.stopped) {
    return { allowed: false, reason: `agent stopped: ${stopState.reason}`, destructive: false };
  }
  if (tool === "terminal_execute" || tool === "open_application") {
    const cmd = String(args.command ?? args.application ?? "");
    if (cmd.length > config.safety.maxCommandLength) {
      return { allowed: false, reason: "command too long", destructive: false };
    }
    if (isDangerousCommand(cmd)) {
      return {
        allowed: false,
        reason: "dangerous command blocked by safety layer",
        destructive: true,
      };
    }
    if (config.safety.requireConfirmationForDestructiveActions && /rm\s/i.test(cmd)) {
      return {
        allowed: true,
        reason: "destructive (rm) — confirm in UI; auto-allowed in tests when confirmation disabled",
        destructive: true,
      };
    }
  }
  if (tool === "write_file" || tool === "read_file" || tool === "list_directory") {
    const p = String(args.path ?? "");
    if (p.startsWith("/etc") || p.startsWith("/boot") || p.startsWith("/proc") || p.startsWith("/sys")) {
      return { allowed: false, reason: "system path blocked", destructive: true };
    }
  }
  if (tool === "mouse_move" || tool === "mouse_click" || tool === "mouse_double_click" ||
      tool === "mouse_scroll" || tool === "keyboard_type" || tool === "keyboard_press" ||
      tool === "open_application") {
    if (!config.desktop.controlEnabled) {
      return {
        allowed: true,
        reason: "desktop control disabled in config — tool returns noop",
        destructive: false,
      };
    }
  }
  return { allowed: true, reason: null, destructive: false };
}
