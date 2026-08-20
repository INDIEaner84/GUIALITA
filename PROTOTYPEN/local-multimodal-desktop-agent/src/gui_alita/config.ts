/**
 * Central configuration for GUIALITA.
 *
 * Mirrors the YAML spec in the brief. The single source of truth is this
 * module; environment variables override file values so that a deployment
 * can swap models or storage without code changes.
 */

import path from "node:path";
import fs from "node:fs";

export type AudioBackend = "stub" | "local-llama-liquid-audio" | "cloud";
export type VisionBackend = "stub" | "local-llama-mtmd" | "cloud";
export type MemoryBackend = "sqlite" | "postgres";
export type AgentBackend = "stub" | "local-llama-text" | "cloud";

export interface GuiAlitaConfig {
  audio: {
    provider: AudioBackend;
    model: string;
    /** Path to a local LFM2.5-Audio GGUF or to a llama-liquid-audio binary. */
    modelPath?: string;
    /** llama-server / llama-liquid-audio endpoint, if HTTP. */
    endpoint?: string;
    sampleRate: number;
  };
  vision: {
    provider: VisionBackend;
    model: string;
    modelPath?: string;
    /** mmproj file for VL GGUF backends. */
    mmprojPath?: string;
    endpoint?: string;
  };
  agent: {
    provider: AgentBackend;
    model: string;
    endpoint?: string;
    /** Maximum Observe→Plan→Act→Verify cycles per user request. */
    maxSteps: number;
  };
  memory: {
    provider: MemoryBackend;
    /** SQLite file path; resolved against dataDir if relative. */
    database: string;
    /** Root directory for the artifact store (screenshots, audio, ...). */
    artifactDir: string;
  };
  desktop: {
    screenshotEnabled: boolean;
    controlEnabled: boolean;
  };
  safety: {
    requireConfirmationForDestructiveActions: boolean;
    /** Max length of a terminal command in characters. */
    maxCommandLength: number;
    /** Default timeout for any tool call (ms). */
    defaultToolTimeoutMs: number;
  };
  paths: {
    /** Project root. */
    root: string;
    /** Data directory (db + artifacts). */
    dataDir: string;
    /** Logs directory. */
    logsDir: string;
  };
}

function envStr(name: string, fallback?: string): string | undefined {
  const v = process.env[name];
  if (v === undefined || v === "") return fallback;
  return v;
}

function envBool(name: string, fallback: boolean): boolean {
  const v = process.env[name];
  if (v === undefined) return fallback;
  return v === "1" || v.toLowerCase() === "true";
}

function envInt(name: string, fallback: number): number {
  const v = process.env[name];
  if (v === undefined) return fallback;
  const n = Number.parseInt(v, 10);
  return Number.isFinite(n) ? n : fallback;
}

const ROOT = process.cwd();
const DATA_DIR = envStr("GUIALITA_DATA_DIR", path.join(ROOT, "data")) ?? path.join(ROOT, "data");
const LOGS_DIR = path.join(DATA_DIR, "logs");

export const config: GuiAlitaConfig = {
  audio: {
    provider: (envStr("GUIALITA_AUDIO_PROVIDER", "stub") as AudioBackend),
    model: envStr("GUIALITA_AUDIO_MODEL", "LiquidAI/LFM2.5-Audio-1.5B") ?? "LiquidAI/LFM2.5-Audio-1.5B",
    modelPath: envStr("GUIALITA_AUDIO_MODEL_PATH"),
    endpoint: envStr("GUIALITA_AUDIO_ENDPOINT"),
    sampleRate: envInt("GUIALITA_AUDIO_SAMPLE_RATE", 16000),
  },
  vision: {
    provider: (envStr("GUIALITA_VISION_PROVIDER", "stub") as VisionBackend),
    model: envStr("GUIALITA_VISION_MODEL", "LiquidAI/LFM2.5-VL-3B") ?? "LiquidAI/LFM2.5-VL-3B",
    modelPath: envStr("GUIALITA_VISION_MODEL_PATH"),
    mmprojPath: envStr("GUIALITA_VISION_MMPROJ_PATH"),
    endpoint: envStr("GUIALITA_VISION_ENDPOINT"),
  },
  agent: {
    provider: (envStr("GUIALITA_AGENT_PROVIDER", "stub") as AgentBackend),
    model: envStr("GUIALITA_AGENT_MODEL", "LiquidAI/LFM2.5-1.2B") ?? "LiquidAI/LFM2.5-1.2B",
    endpoint: envStr("GUIALITA_AGENT_ENDPOINT"),
    maxSteps: envInt("GUIALITA_AGENT_MAX_STEPS", 8),
  },
  memory: {
    provider: "sqlite",
    database: envStr("GUIALITA_MEMORY_DB", path.join(DATA_DIR, "wrack.sqlite")) ?? path.join(DATA_DIR, "wrack.sqlite"),
    artifactDir: envStr("GUIALITA_ARTIFACT_DIR", path.join(DATA_DIR, "artifacts")) ?? path.join(DATA_DIR, "artifacts"),
  },
  desktop: {
    screenshotEnabled: envBool("GUIALITA_SCREENSHOT_ENABLED", true),
    controlEnabled: envBool("GUIALITA_CONTROL_ENABLED", false),
  },
  safety: {
    requireConfirmationForDestructiveActions: envBool(
      "GUIALITA_REQUIRE_CONFIRMATION",
      true,
    ),
    maxCommandLength: envInt("GUIALITA_MAX_COMMAND_LENGTH", 1024),
    defaultToolTimeoutMs: envInt("GUIALITA_TOOL_TIMEOUT_MS", 15_000),
  },
  paths: {
    root: ROOT,
    dataDir: DATA_DIR,
    logsDir: LOGS_DIR,
  },
};

let _initialized = false;
export function ensureDirs(): void {
  if (_initialized) return;
  for (const dir of [
    config.paths.dataDir,
    config.paths.logsDir,
    config.memory.artifactDir,
    path.join(config.memory.artifactDir, "screenshots"),
    path.join(config.memory.artifactDir, "audio"),
    path.join(config.memory.artifactDir, "documents"),
    path.join(config.memory.artifactDir, "agent_outputs"),
  ]) {
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  }
  _initialized = true;
}

export const configYamlExample = `# GUIALITA configuration
audio:
  provider: stub            # stub | local-llama-liquid-audio | cloud
  model: LiquidAI/LFM2.5-Audio-1.5B
  modelPath: /path/to/LFM2.5-Audio-1.5B-Q4.gguf
  endpoint: http://127.0.0.1:8080
  sampleRate: 16000

vision:
  provider: stub            # stub | local-llama-mtmd | cloud
  model: LiquidAI/LFM2.5-VL-3B
  modelPath: /path/to/LFM2.5-VL-3B-Q4.gguf
  mmprojPath: /path/to/LFM2.5-VL-3B-mmproj.gguf
  endpoint: http://127.0.0.1:8081

agent:
  provider: stub            # stub | local-llama-text | cloud
  model: LiquidAI/LFM2.5-1.2B
  endpoint: http://127.0.0.1:8082
  maxSteps: 8

memory:
  provider: sqlite
  database: ./data/wrack.sqlite
  artifactDir: ./data/artifacts

desktop:
  screenshotEnabled: true
  controlEnabled: false   # turn on when xdotool is installed

safety:
  requireConfirmationForDestructiveActions: true
  maxCommandLength: 1024
  defaultToolTimeoutMs: 15000
`;
