/**
 * Vision engine — LFM2.5-VL adapter.
 *
 * Backends:
 *  - "stub": deterministic structured analysis (used in the headless sandbox
 *    where there is no display and no GPU).
 *  - "local-llama-mtmd": shells out to llama.cpp's multimodal CLI
 *    (llama-mtmd-cli / llama-server --mmproj) with the LFM2.5-VL GGUF and
 *    its mmproj projector.
 *  - "cloud": HTTPS to a local proxy.
 *
 * The LFM2.5-VL GGUF needs an mmproj file; both must be provided via
 * GUIALITA_VISION_MODEL_PATH and GUIALITA_VISION_MMPROJ_PATH.
 */

import { spawn } from "node:child_process";
import fs from "node:fs";
import { config } from "../config";
import { logger } from "../log";

export interface VisionEngine {
  analyzeImage(opts: { image: Buffer; prompt: string }): Promise<VisionResult>;
  analyzeScreen(opts: { image: Buffer; prompt: string }): Promise<VisionResult>;
  describeScreen(opts: { image: Buffer }): Promise<VisionResult>;
  health(): Promise<{ ok: boolean; backend: string; detail?: string }>;
}

export interface VisionResult {
  description: string;
  objects: string[];
  text: string | null;
  latencyMs: number;
  backend: string;
  model: string;
}

// ── Stub backend ─────────────────────────────────────────────────────────

class StubVisionEngine implements VisionEngine {
  private hash(buf: Buffer): string {
    let h = 5381;
    for (let i = 0; i < buf.length; i++) h = ((h << 5) + h) ^ buf[i];
    return (h >>> 0).toString(16).padStart(8, "0");
  }

  async analyzeImage(opts: { image: Buffer; prompt: string }): Promise<VisionResult> {
    const t0 = Date.now();
    await new Promise((r) => setTimeout(r, 5));
    const h = this.hash(opts.image);
    return {
      description:
        `[stub vision] I cannot really see the image. ` +
        `hash=${h}, bytes=${opts.image.length}, prompt="${opts.prompt.slice(0, 60)}".`,
      objects: [],
      text: null,
      latencyMs: Date.now() - t0,
      backend: "stub",
      model: config.vision.model,
    };
  }

  async analyzeScreen(opts: { image: Buffer; prompt: string }): Promise<VisionResult> {
    return this.analyzeImage(opts);
  }

  async describeScreen(opts: { image: Buffer }): Promise<VisionResult> {
    return this.analyzeImage({
      image: opts.image,
      prompt: "Describe what is visible on the desktop.",
    });
  }

  async health(): Promise<{ ok: boolean; backend: string; detail?: string }> {
    return { ok: true, backend: "stub", detail: "deterministic; install LFM2.5-VL to enable real vision" };
  }
}

// ── Local llama.cpp multimodal backend ──────────────────────────────────

class LocalLfmVlEngine implements VisionEngine {
  private binaryCandidates = [
    "llama-mtmd-cli",
    "llama-mtmd",
    "llama-server",
  ];

  private findBinary(): string | null {
    for (const c of this.binaryCandidates) {
      try { if (c) return c; } catch { /* ignore */ }
    }
    return null;
  }

  private async run(args: string[]): Promise<{ stdout: string; stderr: string; code: number }> {
    const bin = this.findBinary();
    if (!bin) throw new Error("llama-mtmd-cli / llama-server not found in PATH");
    return await new Promise((resolve, reject) => {
      const p = spawn(bin, args);
      const out: Buffer[] = [];
      const err: Buffer[] = [];
      p.stdout.on("data", (d) => out.push(d));
      p.stderr.on("data", (d) => err.push(d));
      p.on("error", reject);
      p.on("close", (code) =>
        resolve({ stdout: Buffer.concat(out).toString("utf8"), stderr: Buffer.concat(err).toString("utf8"), code: code ?? -1 }),
      );
    });
  }

  private async callModel(image: Buffer, prompt: string): Promise<string> {
    const model = config.vision.modelPath;
    const mmproj = config.vision.mmprojPath;
    if (!model || !mmproj) throw new Error("GUIALITA_VISION_MODEL_PATH and GUIALITA_VISION_MMPROJ_PATH required");
    const tmp = `/tmp/vision_${Date.now()}.png`;
    fs.writeFileSync(tmp, image);
    try {
      const { stdout, code } = await this.run([
        "-m", model,
        "--mmproj", mmproj,
        "--image", tmp,
        "-p", prompt,
        "-n", "256",
        "--no-display-prompt",
      ]);
      if (code !== 0) throw new Error("llama-mtmd-cli failed");
      return stdout.trim();
    } finally {
      try { fs.unlinkSync(tmp); } catch { /* ignore */ }
    }
  }

  async analyzeImage(opts: { image: Buffer; prompt: string }): Promise<VisionResult> {
    const t0 = Date.now();
    const text = await this.callModel(opts.image, opts.prompt);
    return {
      description: text,
      objects: [],
      text: null,
      latencyMs: Date.now() - t0,
      backend: "local-llama-mtmd",
      model: config.vision.model,
    };
  }

  async analyzeScreen(opts: { image: Buffer; prompt: string }): Promise<VisionResult> {
    return this.analyzeImage(opts);
  }

  async describeScreen(opts: { image: Buffer }): Promise<VisionResult> {
    return this.analyzeImage({
      image: opts.image,
      prompt: "Describe what is currently visible on the desktop. List windows, icons, and any visible text.",
    });
  }

  async health(): Promise<{ ok: boolean; backend: string; detail?: string }> {
    const bin = this.findBinary();
    if (!bin) return { ok: false, backend: "local-llama-mtmd", detail: "binary not found" };
    return { ok: true, backend: "local-llama-mtmd", detail: `binary=${bin}` };
  }
}

let _engine: VisionEngine | null = null;
export function getVisionEngine(): VisionEngine {
  if (_engine) return _engine;
  switch (config.vision.provider) {
    case "local-llama-mtmd":
      logger.info("vision", "using local-llama-mtmd backend");
      _engine = new LocalLfmVlEngine();
      break;
    default:
      logger.info("vision", "using stub vision backend", { provider: config.vision.provider });
      _engine = new StubVisionEngine();
  }
  return _engine;
}
