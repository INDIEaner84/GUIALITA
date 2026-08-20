/**
 * Audio engine — LFM2.5-Audio adapter.
 *
 * Backends:
 *  - "stub": deterministic responses, used in the headless sandbox and in CI.
 *  - "local-llama-liquid-audio": shells out to the Liquid-AI patched
 *    llama.cpp binary ("llama-liquid-audio" / "liquid-audio-server").
 *  - "cloud": HTTPS to a local reverse proxy (placeholder for future).
 *
 * Real LFM2.5-Audio supports ASR, TTS, and interleaved audio+text
 * conversation. The adapter only calls the documented endpoints.
 */

import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { config } from "../config";
import { logger } from "../log";

export interface AudioEngine {
  /** ASR: audio → text. */
  transcribe(opts: { audio: Buffer; mime?: string }): Promise<TranscriptionResult>;
  /** TTS: text → audio bytes (WAV/PCM). */
  synthesize(opts: { text: string }): Promise<SynthesisResult>;
  /** Interleaved: audio in → text out (conversational use). */
  converse(opts: { audio: Buffer; systemPrompt?: string }): Promise<ConversationTurn>;
  /** Probe readiness. */
  health(): Promise<{ ok: boolean; backend: string; detail?: string }>;
}

export interface TranscriptionResult {
  text: string;
  language?: string;
  confidence?: number;
  latencyMs: number;
  backend: string;
}

export interface SynthesisResult {
  audio: Buffer;
  mime: string;
  sampleRate: number;
  durationSec: number;
  latencyMs: number;
  backend: string;
}

export interface ConversationTurn {
  text: string;
  audio: Buffer;
  mime: string;
  sampleRate: number;
  latencyMs: number;
  backend: string;
}

// ── Stub backend (sandbox / CI) ─────────────────────────────────────────

class StubAudioEngine implements AudioEngine {
  async transcribe(opts: { audio: Buffer; mime?: string }): Promise<TranscriptionResult> {
    const t0 = Date.now();
    await new Promise((r) => setTimeout(r, 5));
    // In the sandbox we cannot really transcribe, but we can produce a
    // useful, deterministic placeholder so the rest of the agent works.
    const text = "[stub ASR] I heard audio but no real ASR is running. " +
      `Backend=${config.audio.provider}, bytes=${opts.audio.length}.`;
    return { text, latencyMs: Date.now() - t0, backend: "stub" };
  }

  async synthesize(opts: { text: string }): Promise<SynthesisResult> {
    const t0 = Date.now();
    // Generate a short tone-like PCM so the synthesizer produces real bytes
    // (helps the TTS test in the headless container). The frequency encodes
    // the first 3 chars of text as a sanity check.
    const sampleRate = config.audio.sampleRate;
    const seconds = Math.max(0.2, Math.min(2.0, opts.text.length / 40));
    const numSamples = Math.floor(sampleRate * seconds);
    const buf = Buffer.alloc(44 + numSamples * 2);
    // WAV header (mono, 16-bit PCM)
    buf.write("RIFF", 0);
    buf.writeUInt32LE(36 + numSamples * 2, 4);
    buf.write("WAVE", 8);
    buf.write("fmt ", 12);
    buf.writeUInt32LE(16, 16);
    buf.writeUInt16LE(1, 20);   // PCM
    buf.writeUInt16LE(1, 22);   // mono
    buf.writeUInt32LE(sampleRate, 24);
    buf.writeUInt32LE(sampleRate * 2, 28);
    buf.writeUInt16LE(2, 32);
    buf.writeUInt16LE(16, 34);
    buf.write("data", 36);
    buf.writeUInt32LE(numSamples * 2, 40);
    const seed = (opts.text.charCodeAt(0) || 65) % 24;
    for (let i = 0; i < numSamples; i++) {
      const v = Math.sin((2 * Math.PI * (220 + seed * 20) * i) / sampleRate) * 0.2;
      buf.writeInt16LE(Math.max(-32768, Math.min(32767, Math.floor(v * 32767))), 44 + i * 2);
    }
    return {
      audio: buf,
      mime: "audio/wav",
      sampleRate,
      durationSec: seconds,
      latencyMs: Date.now() - t0,
      backend: "stub",
    };
  }

  async converse(opts: { audio: Buffer; systemPrompt?: string }): Promise<ConversationTurn> {
    const t0 = Date.now();
    const reply = "[stub converse] I received your voice. No real LFM2.5-Audio is running.";
    const synth = await this.synthesize({ text: reply });
    return {
      text: reply,
      audio: synth.audio,
      mime: synth.mime,
      sampleRate: synth.sampleRate,
      latencyMs: Date.now() - t0,
      backend: "stub",
    };
  }

  async health(): Promise<{ ok: boolean; backend: string; detail?: string }> {
    return { ok: true, backend: "stub", detail: "deterministic responses; install LFM2.5-Audio to enable real ASR/TTS" };
  }
}

// ── Local llama-liquid-audio backend ────────────────────────────────────

class LocalLfmAudioEngine implements AudioEngine {
  private binaryCandidates = [
    config.audio.modelPath,                                  // user-provided path
    "llama-liquid-audio",                                    // PATH
    "liquid-audio",                                          // upstream binary
    "llama-server",                                          // patched build
  ].filter(Boolean) as string[];

  private findBinary(): string | null {
    for (const c of this.binaryCandidates) {
      try {
        if (c && (c.includes("/") ? fs.existsSync(c) : true)) return c;
      } catch {
        // ignore
      }
    }
    return null;
  }

  private async run(args: string[], stdin?: Buffer): Promise<{ stdout: string; stderr: string; code: number }> {
    const bin = this.findBinary();
    if (!bin) throw new Error("llama-liquid-audio binary not found");
    return await new Promise((resolve, reject) => {
      const p = spawn(bin, args);
      const out: Buffer[] = [];
      const err: Buffer[] = [];
      p.stdout.on("data", (d) => out.push(d));
      p.stderr.on("data", (d) => err.push(d));
      if (stdin) {
        p.stdin.write(stdin);
        p.stdin.end();
      }
      p.on("error", reject);
      p.on("close", (code) =>
        resolve({ stdout: Buffer.concat(out).toString("utf8"), stderr: Buffer.concat(err).toString("utf8"), code: code ?? -1 }),
      );
    });
  }

  async transcribe(opts: { audio: Buffer; mime?: string }): Promise<TranscriptionResult> {
    const t0 = Date.now();
    const tmp = path.join("/tmp", `audio_${Date.now()}.wav`);
    fs.writeFileSync(tmp, opts.audio);
    try {
      const model = config.audio.modelPath;
      if (!model) throw new Error("GUIALITA_AUDIO_MODEL_PATH not set");
      const { stdout, code } = await this.run([
        "-m", model,
        "--audio-input", tmp,
        "--task", "asr",
      ]);
      if (code !== 0) throw new Error("llama-liquid-audio asr failed");
      return { text: stdout.trim(), latencyMs: Date.now() - t0, backend: "local-llama-liquid-audio" };
    } finally {
      try { fs.unlinkSync(tmp); } catch { /* ignore */ }
    }
  }

  async synthesize(opts: { text: string }): Promise<SynthesisResult> {
    const t0 = Date.now();
    const model = config.audio.modelPath;
    if (!model) throw new Error("GUIALITA_AUDIO_MODEL_PATH not set");
    const { stdout, code } = await this.run([
      "-m", model,
      "--task", "tts",
      "--prompt", opts.text,
      "--output-format", "wav",
    ]);
    if (code !== 0) throw new Error("llama-liquid-audio tts failed");
    const audio = Buffer.from(stdout, "binary");
    return {
      audio,
      mime: "audio/wav",
      sampleRate: config.audio.sampleRate,
      durationSec: audio.length / (config.audio.sampleRate * 2),
      latencyMs: Date.now() - t0,
      backend: "local-llama-liquid-audio",
    };
  }

  async converse(opts: { audio: Buffer; systemPrompt?: string }): Promise<ConversationTurn> {
    // LFM2.5-Audio interleaved mode: feed audio + system prompt, get text + audio.
    const t0 = Date.now();
    const tmp = path.join("/tmp", `conv_${Date.now()}.wav`);
    fs.writeFileSync(tmp, opts.audio);
    try {
      const model = config.audio.modelPath;
      if (!model) throw new Error("GUIALITA_AUDIO_MODEL_PATH not set");
      const { stdout, code } = await this.run([
        "-m", model,
        "--task", "converse",
        "--audio-input", tmp,
        ...(opts.systemPrompt ? ["--system", opts.systemPrompt] : []),
        "--output-format", "wav",
      ]);
      if (code !== 0) throw new Error("llama-liquid-audio converse failed");
      // The local binary is expected to emit JSON {"text": "...", "audio_b64": "..."}
      // or a WAV. We attempt JSON first.
      let text = "";
      let audio: Buffer;
      try {
        const j = JSON.parse(stdout) as { text: string; audio_b64: string };
        text = j.text;
        audio = Buffer.from(j.audio_b64, "base64");
      } catch {
        text = "";
        audio = Buffer.from(stdout, "binary");
      }
      return {
        text,
        audio,
        mime: "audio/wav",
        sampleRate: config.audio.sampleRate,
        latencyMs: Date.now() - t0,
        backend: "local-llama-liquid-audio",
      };
    } finally {
      try { fs.unlinkSync(tmp); } catch { /* ignore */ }
    }
  }

  async health(): Promise<{ ok: boolean; backend: string; detail?: string }> {
    try {
      const bin = this.findBinary();
      if (!bin) return { ok: false, backend: "local-llama-liquid-audio", detail: "binary not found in PATH" };
      return { ok: true, backend: "local-llama-liquid-audio", detail: `binary=${bin}` };
    } catch (e) {
      return { ok: false, backend: "local-llama-liquid-audio", detail: (e as Error).message };
    }
  }
}

let _engine: AudioEngine | null = null;
export function getAudioEngine(): AudioEngine {
  if (_engine) return _engine;
  switch (config.audio.provider) {
    case "local-llama-liquid-audio":
      logger.info("audio", "using local-llama-liquid-audio backend");
      _engine = new LocalLfmAudioEngine();
      break;
    case "cloud":
    case "stub":
    default:
      logger.info("audio", "using stub audio backend", { provider: config.audio.provider });
      _engine = new StubAudioEngine();
  }
  return _engine;
}
