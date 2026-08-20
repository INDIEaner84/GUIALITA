/**
 * Public-safe view of the agent config (safe to import in client components).
 * Values are computed at build time and embedded as constants so that no
 * server-only module is pulled into the client bundle.
 */

export interface PublicConfig {
  audio: { provider: string; model: string; sampleRate: number };
  vision: { provider: string; model: string };
  agent: { provider: string; model: string; maxSteps: number };
  memory: { provider: string };
  desktop: { screenshotEnabled: boolean; controlEnabled: boolean };
  model: string;
}

const provider = (typeof process !== "undefined" && process.env.GUIALITA_AUDIO_PROVIDER) || "stub";
const visionProvider = (typeof process !== "undefined" && process.env.GUIALITA_VISION_PROVIDER) || "stub";
const agentProvider = (typeof process !== "undefined" && process.env.GUIALITA_AGENT_PROVIDER) || "stub";
const audioModel = (typeof process !== "undefined" && process.env.GUIALITA_AUDIO_MODEL) || "LiquidAI/LFM2.5-Audio-1.5B";
const visionModel = (typeof process !== "undefined" && process.env.GUIALITA_VISION_MODEL) || "LiquidAI/LFM2.5-VL-3B";
const agentModel = (typeof process !== "undefined" && process.env.GUIALITA_AGENT_MODEL) || "LiquidAI/LFM2.5-1.2B";

export const config: PublicConfig = {
  audio: { provider, model: audioModel, sampleRate: 16000 },
  vision: { provider: visionProvider, model: visionModel },
  agent: { provider: agentProvider, model: agentModel, maxSteps: 8 },
  memory: { provider: "sqlite" },
  desktop: { screenshotEnabled: true, controlEnabled: false },
  model: visionModel,
};
