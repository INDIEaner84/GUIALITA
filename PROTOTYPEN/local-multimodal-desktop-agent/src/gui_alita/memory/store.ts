/**
 * WRACK — Working Retrieval And Context Knowledge.
 *
 * A persistent memory layer for GUIALITA. Every important entity
 * (Session, Message, Task, Event, Observation, ToolCall, ToolResult, Artifact)
 * is stored here.
 *
 * Storage: SQLite (better-sqlite3).
 * Artifacts: filesystem (config.memory.artifactDir).
 *
 * The schema is graph-compatible: foreign keys form a navigable graph
 * (Session → Message, Session → Task, Session → Event, Task → Observation,
 * Event → ToolCall → ToolResult, anything → Artifact). A later graph layer
 * can read the same tables.
 *
 * Worker API: a typed service is exposed so future Agent Workers can
 * query/insert without knowing the SQLite layer.
 */

import path from "node:path";
import fs from "node:fs";
import crypto from "node:crypto";
import Database from "better-sqlite3";
import { config, ensureDirs } from "../config";
import { logger } from "../log";

export type ID = string;
export type ISODate = string;

export interface SessionRecord {
  id: ID;
  title: string | null;
  createdAt: ISODate;
  updatedAt: ISODate;
  metadata: Record<string, unknown>;
  parentSessionId: ID | null;
}

export interface MessageRecord {
  id: ID;
  sessionId: ID;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  modality: "text" | "audio" | "image" | "screen";
  createdAt: ISODate;
  metadata: Record<string, unknown>;
}

export type TaskStatus = "open" | "in_progress" | "done" | "failed" | "cancelled";

export interface TaskRecord {
  id: ID;
  sessionId: ID;
  title: string;
  description: string;
  status: TaskStatus;
  plan: PlanStep[];
  createdAt: ISODate;
  updatedAt: ISODate;
  result: string | null;
}

export interface PlanStep {
  index: number;
  action: string;
  arguments: Record<string, unknown>;
  reason: string;
  status: "pending" | "in_progress" | "done" | "failed" | "skipped";
  result?: string;
}

export type EventType =
  | "session_started"
  | "session_continued"
  | "user_message"
  | "assistant_message"
  | "intent"
  | "plan_created"
  | "tool_call"
  | "tool_result"
  | "observation"
  | "verification"
  | "recovery"
  | "error"
  | "task_created"
  | "task_completed"
  | "memory_write"
  | "memory_retrieval"
  | "stop"
  | "safety_block";

export interface EventRecord {
  id: ID;
  sessionId: ID;
  type: EventType;
  actor: "user" | "agent" | "system" | "safety";
  tool: string | null;
  arguments: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  status: "success" | "failure" | "blocked" | "info";
  message: string | null;
  createdAt: ISODate;
  taskId: ID | null;
}

export interface ArtifactRecord {
  id: ID;
  sessionId: ID;
  kind: "screenshot" | "audio" | "document" | "log" | "agent_output";
  path: string;
  mime: string;
  bytes: number;
  sha256: string;
  createdAt: ISODate;
  metadata: Record<string, unknown>;
}

const SCHEMA = `
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  title TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{}',
  parent_session_id TEXT REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  modality TEXT NOT NULL DEFAULT 'text',
  created_at TEXT NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL,
  plan TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  result TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id, created_at);

CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  type TEXT NOT NULL,
  actor TEXT NOT NULL,
  tool TEXT,
  arguments TEXT,
  result TEXT,
  status TEXT NOT NULL,
  message TEXT,
  task_id TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type, created_at);

CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  kind TEXT NOT NULL,
  path TEXT NOT NULL,
  mime TEXT NOT NULL,
  bytes INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_artifacts_session ON artifacts(session_id, created_at);
`;

let _db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (_db) return _db;
  ensureDirs();
  const dbPath = config.memory.database;
  _db = new Database(dbPath);
  _db.pragma("journal_mode = WAL");
  _db.pragma("foreign_keys = ON");
  _db.exec(SCHEMA);
  logger.info("wrack", "memory store opened", { path: dbPath });
  return _db;
}

export function newId(): ID {
  return crypto.randomBytes(12).toString("hex");
}

export function nowIso(): ISODate {
  return new Date().toISOString();
}

function jsonOrEmpty(v: unknown): string {
  if (v === null || v === undefined) return "{}";
  return JSON.stringify(v);
}

function parseJson<T>(s: string | null, fallback: T): T {
  if (!s) return fallback;
  try {
    return JSON.parse(s) as T;
  } catch {
    return fallback;
  }
}

// ── Sessions ─────────────────────────────────────────────────────────────

export function createSession(opts: {
  title?: string;
  parentSessionId?: ID | null;
  metadata?: Record<string, unknown>;
} = {}): SessionRecord {
  const db = getDb();
  const id = newId();
  const ts = nowIso();
  db.prepare(
    `INSERT INTO sessions (id, title, created_at, updated_at, metadata, parent_session_id)
     VALUES (?, ?, ?, ?, ?, ?)`,
  ).run(
    id,
    opts.title ?? null,
    ts,
    ts,
    jsonOrEmpty(opts.metadata ?? {}),
    opts.parentSessionId ?? null,
  );
  return {
    id,
    title: opts.title ?? null,
    createdAt: ts,
    updatedAt: ts,
    metadata: opts.metadata ?? {},
    parentSessionId: opts.parentSessionId ?? null,
  };
}

export function getSession(id: ID): SessionRecord | null {
  const row = getDb()
    .prepare(`SELECT * FROM sessions WHERE id = ?`)
    .get(id) as Record<string, unknown> | undefined;
  if (!row) return null;
  return rowToSession(row);
}

export function listRecentSessions(limit = 20): SessionRecord[] {
  const rows = getDb()
    .prepare(`SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?`)
    .all(limit) as Record<string, unknown>[];
  return rows.map(rowToSession);
}

export function touchSession(id: ID): void {
  getDb()
    .prepare(`UPDATE sessions SET updated_at = ? WHERE id = ?`)
    .run(nowIso(), id);
}

function rowToSession(r: Record<string, unknown>): SessionRecord {
  return {
    id: r.id as string,
    title: (r.title as string | null) ?? null,
    createdAt: r.created_at as string,
    updatedAt: r.updated_at as string,
    metadata: parseJson<Record<string, unknown>>((r.metadata as string) ?? null, {}),
    parentSessionId: (r.parent_session_id as string | null) ?? null,
  };
}

// ── Messages ─────────────────────────────────────────────────────────────

export function appendMessage(opts: {
  sessionId: ID;
  role: MessageRecord["role"];
  content: string;
  modality?: MessageRecord["modality"];
  metadata?: Record<string, unknown>;
}): MessageRecord {
  const db = getDb();
  const id = newId();
  const ts = nowIso();
  db.prepare(
    `INSERT INTO messages (id, session_id, role, content, modality, created_at, metadata)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
  ).run(
    id,
    opts.sessionId,
    opts.role,
    opts.content,
    opts.modality ?? "text",
    ts,
    jsonOrEmpty(opts.metadata ?? {}),
  );
  touchSession(opts.sessionId);
  return {
    id,
    sessionId: opts.sessionId,
    role: opts.role,
    content: opts.content,
    modality: opts.modality ?? "text",
    createdAt: ts,
    metadata: opts.metadata ?? {},
  };
}

export function getMessages(sessionId: ID, limit = 200): MessageRecord[] {
  const rows = getDb()
    .prepare(
      `SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC LIMIT ?`,
    )
    .all(sessionId, limit) as Record<string, unknown>[];
  return rows.map((r) => ({
    id: r.id as string,
    sessionId: r.session_id as string,
    role: r.role as MessageRecord["role"],
    content: r.content as string,
    modality: (r.modality as MessageRecord["modality"]) ?? "text",
    createdAt: r.created_at as string,
    metadata: parseJson<Record<string, unknown>>((r.metadata as string) ?? null, {}),
  }));
}

export function searchMessages(query: string, limit = 25): MessageRecord[] {
  // Naive LIKE search; can be replaced with FTS5 or a vector index later.
  const rows = getDb()
    .prepare(
      `SELECT * FROM messages WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?`,
    )
    .all(`%${query}%`, limit) as Record<string, unknown>[];
  return rows.map((r) => ({
    id: r.id as string,
    sessionId: r.session_id as string,
    role: r.role as MessageRecord["role"],
    content: r.content as string,
    modality: (r.modality as MessageRecord["modality"]) ?? "text",
    createdAt: r.created_at as string,
    metadata: parseJson<Record<string, unknown>>((r.metadata as string) ?? null, {}),
  }));
}

// ── Tasks ────────────────────────────────────────────────────────────────

export function createTask(opts: {
  sessionId: ID;
  title: string;
  description: string;
  plan?: PlanStep[];
}): TaskRecord {
  const db = getDb();
  const id = newId();
  const ts = nowIso();
  db.prepare(
    `INSERT INTO tasks (id, session_id, title, description, status, plan, created_at, updated_at, result)
     VALUES (?, ?, ?, ?, 'open', ?, ?, ?, NULL)`,
  ).run(
    id,
    opts.sessionId,
    opts.title,
    opts.description,
    JSON.stringify(opts.plan ?? []),
    ts,
    ts,
  );
  return {
    id,
    sessionId: opts.sessionId,
    title: opts.title,
    description: opts.description,
    status: "open",
    plan: opts.plan ?? [],
    createdAt: ts,
    updatedAt: ts,
    result: null,
  };
}

export function updateTask(
  id: ID,
  patch: Partial<Pick<TaskRecord, "status" | "plan" | "result">>,
): TaskRecord | null {
  const db = getDb();
  const current = db.prepare(`SELECT * FROM tasks WHERE id = ?`).get(id) as
    | Record<string, unknown>
    | undefined;
  if (!current) return null;
  const next = {
    status: patch.status ?? (current.status as TaskStatus),
    plan: patch.plan ?? parseJson<PlanStep[]>((current.plan as string) ?? "[]", []),
    result: patch.result ?? (current.result as string | null),
    updated_at: nowIso(),
  };
  db.prepare(
    `UPDATE tasks SET status = ?, plan = ?, result = ?, updated_at = ? WHERE id = ?`,
  ).run(next.status, JSON.stringify(next.plan), next.result, next.updated_at, id);
  const updated = db.prepare(`SELECT * FROM tasks WHERE id = ?`).get(id) as
    | Record<string, unknown>
    | undefined;
  return updated ? rowToTask(updated) : null;
}

export function getTask(id: ID): TaskRecord | null {
  const row = getDb().prepare(`SELECT * FROM tasks WHERE id = ?`).get(id) as
    | Record<string, unknown>
    | undefined;
  return row ? rowToTask(row) : null;
}

export function listTasksForSession(sessionId: ID): TaskRecord[] {
  const rows = getDb()
    .prepare(`SELECT * FROM tasks WHERE session_id = ? ORDER BY created_at DESC`)
    .all(sessionId) as Record<string, unknown>[];
  return rows.map(rowToTask);
}

function rowToTask(r: Record<string, unknown>): TaskRecord {
  return {
    id: r.id as string,
    sessionId: r.session_id as string,
    title: r.title as string,
    description: r.description as string,
    status: r.status as TaskStatus,
    plan: parseJson<PlanStep[]>((r.plan as string) ?? "[]", []),
    createdAt: r.created_at as string,
    updatedAt: r.updated_at as string,
    result: (r.result as string | null) ?? null,
  };
}

// ── Events ───────────────────────────────────────────────────────────────

export function appendEvent(opts: {
  sessionId: ID;
  type: EventType;
  actor: EventRecord["actor"];
  tool?: string | null;
  arguments?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
  status?: EventRecord["status"];
  message?: string | null;
  taskId?: ID | null;
}): EventRecord {
  const db = getDb();
  const id = newId();
  const ts = nowIso();
  db.prepare(
    `INSERT INTO events (id, session_id, type, actor, tool, arguments, result, status, message, task_id, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(
    id,
    opts.sessionId,
    opts.type,
    opts.actor,
    opts.tool ?? null,
    opts.arguments ? JSON.stringify(opts.arguments) : null,
    opts.result ? JSON.stringify(opts.result) : null,
    opts.status ?? "info",
    opts.message ?? null,
    opts.taskId ?? null,
    ts,
  );
  return {
    id,
    sessionId: opts.sessionId,
    type: opts.type,
    actor: opts.actor,
    tool: opts.tool ?? null,
    arguments: opts.arguments ?? null,
    result: opts.result ?? null,
    status: opts.status ?? "info",
    message: opts.message ?? null,
    createdAt: ts,
    taskId: opts.taskId ?? null,
  };
}

export function getEvents(sessionId: ID, limit = 500): EventRecord[] {
  const rows = getDb()
    .prepare(`SELECT * FROM events WHERE session_id = ? ORDER BY created_at ASC LIMIT ?`)
    .all(sessionId, limit) as Record<string, unknown>[];
  return rows.map(rowToEvent);
}

function rowToEvent(r: Record<string, unknown>): EventRecord {
  return {
    id: r.id as string,
    sessionId: r.session_id as string,
    type: r.type as EventType,
    actor: r.actor as EventRecord["actor"],
    tool: (r.tool as string | null) ?? null,
    arguments: parseJson<Record<string, unknown> | null>((r.arguments as string | null) ?? null, null),
    result: parseJson<Record<string, unknown> | null>((r.result as string | null) ?? null, null),
    status: r.status as EventRecord["status"],
    message: (r.message as string | null) ?? null,
    createdAt: r.created_at as string,
    taskId: (r.task_id as string | null) ?? null,
  };
}

// ── Artifacts ────────────────────────────────────────────────────────────

export interface StoreArtifactOpts {
  sessionId: ID;
  kind: ArtifactRecord["kind"];
  data: Buffer | string;
  mime: string;
  ext: string;
  metadata?: Record<string, unknown>;
}

export function storeArtifact(opts: StoreArtifactOpts): ArtifactRecord {
  ensureDirs();
  const id = newId();
  const ts = nowIso();
  const sub = path.join(config.memory.artifactDir, opts.kind + "s");
  if (!fs.existsSync(sub)) fs.mkdirSync(sub, { recursive: true });
  const filename = `${opts.sessionId.slice(0, 8)}_${id}.${opts.ext}`;
  const full = path.join(sub, filename);
  const buf = typeof opts.data === "string" ? Buffer.from(opts.data, "utf8") : opts.data;
  fs.writeFileSync(full, buf);
  const sha = crypto.createHash("sha256").update(buf).digest("hex");
  getDb()
    .prepare(
      `INSERT INTO artifacts (id, session_id, kind, path, mime, bytes, sha256, created_at, metadata)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    )
    .run(
      id,
      opts.sessionId,
      opts.kind,
      full,
      opts.mime,
      buf.length,
      sha,
      ts,
      jsonOrEmpty(opts.metadata ?? {}),
    );
  return {
    id,
    sessionId: opts.sessionId,
    kind: opts.kind,
    path: full,
    mime: opts.mime,
    bytes: buf.length,
    sha256: sha,
    createdAt: ts,
    metadata: opts.metadata ?? {},
  };
}

export function getArtifact(id: ID): ArtifactRecord | null {
  const row = getDb().prepare(`SELECT * FROM artifacts WHERE id = ?`).get(id) as
    | Record<string, unknown>
    | undefined;
  if (!row) return null;
  return {
    id: row.id as string,
    sessionId: row.session_id as string,
    kind: row.kind as ArtifactRecord["kind"],
    path: row.path as string,
    mime: row.mime as string,
    bytes: row.bytes as number,
    sha256: row.sha256 as string,
    createdAt: row.created_at as string,
    metadata: parseJson<Record<string, unknown>>((row.metadata as string) ?? null, {}),
  };
}

// ── Retrieval helpers for Agent Workers ──────────────────────────────────

export function getRelatedContext(query: string, limit = 10): {
  sessions: SessionRecord[];
  messages: MessageRecord[];
  events: EventRecord[];
} {
  const messages = searchMessages(query, limit);
  const sessionIds = new Set(messages.map((m) => m.sessionId));
  const sessions: SessionRecord[] = [];
  for (const sid of sessionIds) {
    const s = getSession(sid);
    if (s) sessions.push(s);
  }
  // grab a few events from those sessions
  const events: EventRecord[] = [];
  for (const sid of sessionIds) {
    events.push(...getEvents(sid, 50));
  }
  return { sessions, messages, events };
}
