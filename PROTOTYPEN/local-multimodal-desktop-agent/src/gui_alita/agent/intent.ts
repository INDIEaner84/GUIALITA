/**
 * Intent understanding.
 *
 * In a full LFM2.5 deployment the intent model is LFM2.5-Audio or a text
 * LFM2.5 chat model. In the stub backend the intent is classified by
 * deterministic pattern matching, which is enough to drive the acceptance
 * tests and the UI.
 */

import { logger } from "../log";

export type Intent =
  | { kind: "greeting" }
  | { kind: "describe_screen" }
  | { kind: "open_application"; application: string }
  | { kind: "terminal_command"; command: string }
  | { kind: "create_directory"; path: string }
  | { kind: "create_file"; path: string; content: string }
  | { kind: "read_file"; path: string }
  | { kind: "list_directory"; path: string }
  | { kind: "search_memory"; query: string }
  | { kind: "continue_previous" }
  | { kind: "build_memory_system" }
  | { kind: "implement_feature"; description: string }
  | { kind: "stop" }
  | { kind: "help" }
  | { kind: "unknown"; text: string };

const OPEN_TRIGGERS: Array<{ app: RegExp; name: string }> = [
  { app: /\b(terminal|shell|console)\b/i, name: "terminal" },
  { app: /\b(firefox|chrome|browser)\b/i, name: "firefox" },
  { app: /\b(file\s*manager|files|nautilus|explorer)\b/i, name: "nautilus" },
  { app: /\b(code|vscode|vs\s*code|editor)\b/i, name: "code" },
];

export function classifyIntent(text: string): Intent {
  const t = text.trim();
  const lower = t.toLowerCase();

  if (/^(hi|hello|hey|good\s+(morning|afternoon|evening))\b/.test(lower)) return { kind: "greeting" };
  if (/stop|halt|cancel\s+(the\s+)?agent|emergency\s+stop/.test(lower)) return { kind: "stop" };
  if (/^(help|what\s+can\s+you\s+do|\?)/.test(lower)) return { kind: "help" };
  if (/continue\s+(where|from)/i.test(lower) || /yesterday|last\s+session/.test(lower)) {
    return { kind: "continue_previous" };
  }
  if (/what\s+(is|do\s+you\s+see|is\s+visible|is\s+on)\b.*(screen|desktop)/i.test(lower)) {
    return { kind: "describe_screen" };
  }
  if (/(look\s+at|see|describe|what).*(screen|desktop)/i.test(lower)) {
    return { kind: "describe_screen" };
  }
  for (const { app, name } of OPEN_TRIGGERS) {
    if (app.test(lower) && /open|launch|start/.test(lower)) {
      return { kind: "open_application", application: name };
    }
  }
  // "create a directory called foo" / "make a folder called bar"
  let m = t.match(/(?:create|make|add)\s+(?:a\s+)?(?:directory|folder)\s+(?:called|named)?\s*([^\s.]+)/i);
  if (m) return { kind: "create_directory", path: m[1] };
  // "create a file called foo.txt with content bar"  (simple)
  m = t.match(/(?:create|write)\s+(?:a\s+)?file\s+(?:called|named)?\s*(\S+)\s+(?:with|containing)\s+(.+)$/i);
  if (m) return { kind: "create_file", path: m[1], content: m[2] };
  // "read <file>" / "show <file>"
  m = t.match(/(?:read|show|cat|open)\s+(?:the\s+)?(?:file\s+)?(\/[^\s]+|\.\/[^\s]+|[\w./-]+\.[a-z0-9]{1,6})/i);
  if (m) return { kind: "read_file", path: m[1] };
  // "list <dir>" / "ls <dir>"
  m = t.match(/^(?:list|ls)\s+(\/[^\s]+|\.\/[^\s]+|~?\/[\w./-]*)/i);
  if (m) return { kind: "list_directory", path: m[1] };
  // search memory
  m = t.match(/(?:search|find|recall)\s+(?:memory|conversations?|history)\s+(?:for|about|of)?\s*(.+)$/i);
  if (m) return { kind: "search_memory", query: m[1] };
  // build the memory system / WRACK
  if (/build\s+(?:the\s+)?(?:wrack|memory|work\s*memory)/i.test(lower) ||
      /work\s*memory.*(?:can|so).*(?:stored?|persist|retriev)/i.test(lower)) {
    return { kind: "build_memory_system" };
  }
  // implement a feature
  if (/^(?:implement|build|add|create)\s+(?:a\s+|the\s+)?(.+)$/i.test(t) &&
      /memory|worker|tool|feature/i.test(t)) {
    const m2 = t.match(/^(?:implement|build|add|create)\s+(?:a\s+|the\s+)?(.+)$/i);
    if (m2) return { kind: "implement_feature", description: m2[1] };
  }
  // terminal "run <cmd>" / "execute <cmd>" / leading "$"
  m = t.match(/^(?:run|execute|shell)\s+(.+)$/i);
  if (m) return { kind: "terminal_command", command: m[1] };

  return { kind: "unknown", text: t };
}

export function intentToText(intent: Intent): string {
  switch (intent.kind) {
    case "greeting": return "GREETING";
    case "describe_screen": return "DESCRIBE_SCREEN";
    case "open_application": return `OPEN_APPLICATION(${intent.application})`;
    case "terminal_command": return `TERMINAL_COMMAND(${intent.command})`;
    case "create_directory": return `CREATE_DIRECTORY(${intent.path})`;
    case "create_file": return `CREATE_FILE(${intent.path})`;
    case "read_file": return `READ_FILE(${intent.path})`;
    case "list_directory": return `LIST_DIRECTORY(${intent.path})`;
    case "search_memory": return `SEARCH_MEMORY(${intent.query})`;
    case "continue_previous": return "CONTINUE_PREVIOUS";
    case "build_memory_system": return "BUILD_MEMORY_SYSTEM";
    case "implement_feature": return `IMPLEMENT_FEATURE(${intent.description})`;
    case "stop": return "STOP";
    case "help": return "HELP";
    case "unknown": return `UNKNOWN(${intent.text})`;
  }
}

export function logIntent(sessionId: string, intent: Intent): void {
  logger.info("intent", intentToText(intent), { sessionId });
}
