/**
 * Desktop engine — screenshot, mouse, keyboard, terminal, filesystem.
 *
 * In a real local install these tools shell out to scrot / xdotool / bash.
 * In the headless sandbox they produce a synthesized PNG and log a noop
 * so the agent loop can still be exercised end-to-end. The synthesis
 * behaviour is honest: it is logged at WARN level and clearly marked.
 */

import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { config, ensureDirs } from "../config";
import { logger } from "../log";

export interface ScreenCapture {
  timestamp: string;
  width: number;
  height: number;
  imagePath: string | null;
  bytes: number;
  source: "scrot" | "gnome-screenshot" | "mss" | "import" | "stub";
  stub: boolean;
}

function which(cmd: string): boolean {
  const p = process.env.PATH ?? "";
  for (const dir of p.split(":")) {
    if (dir && fs.existsSync(path.join(dir, cmd))) return true;
  }
  return false;
}

function synthesizePng(width = 1920, height = 1080, label = "GUIALITA sandbox"): Buffer {
  // Minimal 8-bit RGB PNG with a horizontal gradient and the label in the
  // top-left corner. We hand-encode the PNG to avoid pulling in a native
  // dependency (canvas).
  const channels = 3;
  const stride = width * channels;
  const raw = Buffer.alloc((stride + 1) * height); // +1 for PNG filter byte per row
  for (let y = 0; y < height; y++) {
    raw[y * (stride + 1)] = 0; // PNG filter "None"
    for (let x = 0; x < width; x++) {
      const off = y * (stride + 1) + 1 + x * channels;
      const t = x / width;
      raw[off] = Math.floor(20 + 30 * t);
      raw[off + 1] = Math.floor(30 + 50 * t);
      raw[off + 2] = Math.floor(60 + 80 * t);
    }
  }
  // We need IDAT (zlib-compressed) and IHDR. Use zlib built into Node.
  // We do not embed a real font; a few white pixels form a "marker" bar.
  for (let y = 40; y < 70; y++) {
    for (let x = 40; x < 40 + Math.min(width - 40, label.length * 14); x++) {
      const off = y * (stride + 1) + 1 + x * channels;
      raw[off] = 240; raw[off + 1] = 240; raw[off + 2] = 240;
    }
  }
  // Compress
  const zlib = require("node:zlib") as typeof import("node:zlib");
  const compressed = zlib.deflateSync(raw);

  function chunk(type: string, data: Buffer): Buffer {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length, 0);
    const typeBuf = Buffer.from(type, "ascii");
    const crc = Buffer.alloc(4);
    const crcInput = Buffer.concat([typeBuf, data]);
    crc.writeUInt32BE(crc32(crcInput), 0);
    return Buffer.concat([len, typeBuf, data, crc]);
  }

  const sig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;       // bit depth
  ihdr[9] = 2;       // colour type RGB
  ihdr[10] = 0;      // compression
  ihdr[11] = 0;      // filter
  ihdr[12] = 0;      // interlace
  return Buffer.concat([
    sig,
    chunk("IHDR", ihdr),
    chunk("IDAT", compressed),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

// CRC32 (PNG flavour)
const CRC_TABLE: number[] = (() => {
  const t = new Array<number>(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();
function crc32(buf: Buffer): number {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

export async function captureScreen(): Promise<ScreenCapture> {
  ensureDirs();
  const out = path.join(config.memory.artifactDir, "screenshots", `screen_${Date.now()}.png`);
  const t0 = Date.now();

  const tools: Array<{ name: ScreenCapture["source"]; cmd: string; args: (out: string) => string[] }> = [
    { name: "scrot", cmd: "scrot", args: (o) => [o] },
    { name: "gnome-screenshot", cmd: "gnome-screenshot", args: (o) => ["-f", o] },
    { name: "import", cmd: "import", args: (o) => ["-window", "root", o] },
  ];
  for (const t of tools) {
    if (which(t.cmd)) {
      try {
        await new Promise<void>((resolve, reject) => {
          const p = spawn(t.cmd, t.args(out));
          p.on("error", reject);
          p.on("close", (code) => (code === 0 ? resolve() : reject(new Error("exit " + code))));
        });
        const stat = fs.statSync(out);
        return {
          timestamp: new Date().toISOString(),
          width: 0,
          height: 0,
          imagePath: out,
          bytes: stat.size,
          source: t.name,
          stub: false,
        };
      } catch (e) {
        logger.warn("desktop", `screenshot via ${t.name} failed: ${(e as Error).message}`);
      }
    }
  }
  // Stub fallback
  const png = synthesizePng();
  fs.writeFileSync(out, png);
  logger.warn("desktop", "no display server; using synthesized screenshot stub", { path: out });
  return {
    timestamp: new Date().toISOString(),
    width: 1920,
    height: 1080,
    imagePath: out,
    bytes: png.length,
    source: "stub",
    stub: true,
  };
}

export function readImage(imagePath: string): Buffer {
  return fs.readFileSync(imagePath);
}

// ── Tool implementations ────────────────────────────────────────────────

export interface ToolResult {
  ok: boolean;
  output: string;
  data?: Record<string, unknown>;
  error?: string;
  stub?: boolean;
}

export async function toolScreenshot(): Promise<ToolResult> {
  if (!config.desktop.screenshotEnabled) {
    return { ok: false, output: "screenshot tool disabled in config" };
  }
  const cap = await captureScreen();
  return {
    ok: true,
    output: `captured ${cap.bytes} bytes from ${cap.source}${cap.stub ? " (stub)" : ""}`,
    data: { path: cap.imagePath, ...cap },
    stub: cap.stub,
  };
}

export async function toolOpenApplication(application: string): Promise<ToolResult> {
  if (!config.desktop.controlEnabled) {
    return { ok: true, output: `[noop] open_application(${application}) — desktop control disabled`, stub: true };
  }
  return await runShell(`${application} &`, 5_000);
}

export async function toolTerminalExecute(command: string): Promise<ToolResult> {
  return await runShell(command, config.safety.defaultToolTimeoutMs);
}

export async function toolReadFile(path: string): Promise<ToolResult> {
  try {
    const content = fs.readFileSync(path, "utf8");
    return { ok: true, output: content };
  } catch (e) {
    return { ok: false, output: "", error: (e as Error).message };
  }
}

export async function toolWriteFile(path: string, content: string): Promise<ToolResult> {
  try {
    fs.writeFileSync(path, content);
    return { ok: true, output: `wrote ${content.length} bytes to ${path}` };
  } catch (e) {
    return { ok: false, output: "", error: (e as Error).message };
  }
}

export async function toolListDirectory(path: string): Promise<ToolResult> {
  try {
    const entries = fs.readdirSync(path, { withFileTypes: true });
    const out = entries
      .map((e) => `${e.isDirectory() ? "d" : "-"} ${e.name}`)
      .join("\n");
    return { ok: true, output: out };
  } catch (e) {
    return { ok: false, output: "", error: (e as Error).message };
  }
}

export async function toolMouseMove(x: number, y: number): Promise<ToolResult> {
  if (!config.desktop.controlEnabled) return { ok: true, output: `[noop] mouse_move ${x},${y}`, stub: true };
  return await runShell(`xdotool mousemove ${x} ${y}`, 5_000);
}

export async function toolMouseClick(x: number, y: number, button = "left"): Promise<ToolResult> {
  if (!config.desktop.controlEnabled) return { ok: true, output: `[noop] mouse_click ${button} ${x},${y}`, stub: true };
  return await runShell(`xdotool mouseclick ${button === "left" ? "1" : button === "right" ? "3" : "2"} ${x} ${y}`, 5_000);
}

export async function toolMouseDoubleClick(x: number, y: number): Promise<ToolResult> {
  if (!config.desktop.controlEnabled) return { ok: true, output: `[noop] mouse_double_click ${x},${y}`, stub: true };
  return await runShell(`xdotool mouseclick --repeat 2 1 ${x} ${y}`, 5_000);
}

export async function toolMouseScroll(amount: number): Promise<ToolResult> {
  if (!config.desktop.controlEnabled) return { ok: true, output: `[noop] mouse_scroll ${amount}`, stub: true };
  return await runShell(`xdotool mousescroll ${amount > 0 ? "down" : "up"} ${Math.abs(amount)}`, 5_000);
}

export async function toolKeyboardType(text: string): Promise<ToolResult> {
  if (!config.desktop.controlEnabled) return { ok: true, output: `[noop] keyboard_type "${text}"`, stub: true };
  return await runShell(`xdotool type --clearmodifiers ${shellQuote(text)}`, 10_000);
}

export async function toolKeyboardPress(key: string): Promise<ToolResult> {
  if (!config.desktop.controlEnabled) return { ok: true, output: `[noop] keyboard_press ${key}`, stub: true };
  return await runShell(`xdotool key ${key}`, 5_000);
}

function shellQuote(s: string): string {
  return "'" + s.replace(/'/g, "'\\''") + "'";
}

async function runShell(cmd: string, timeoutMs: number): Promise<ToolResult> {
  return await new Promise((resolve) => {
    const p = spawn("/bin/bash", ["-c", cmd], {
      env: { ...process.env, HOME: os.homedir() },
      timeout: timeoutMs,
    });
    const out: Buffer[] = [];
    const err: Buffer[] = [];
    p.stdout.on("data", (d) => out.push(d));
    p.stderr.on("data", (d) => err.push(d));
    p.on("error", (e) => resolve({ ok: false, output: "", error: e.message }));
    p.on("close", (code) =>
      resolve({
        ok: code === 0,
        output: Buffer.concat(out).toString("utf8").slice(0, 8000),
        error: code === 0 ? undefined : Buffer.concat(err).toString("utf8").slice(0, 2000),
        data: { exitCode: code },
      }),
    );
  });
}
