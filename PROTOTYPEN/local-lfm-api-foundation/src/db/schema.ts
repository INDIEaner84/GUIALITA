import { pgTable, text, timestamp, integer, varchar, jsonb } from "drizzle-orm/pg-core";

export const chatLogs = pgTable("chat_logs", {
  id: varchar("id", { length: 64 }).primaryKey(),
  userMessage: text("user_message").notNull(),
  assistantResponse: text("assistant_response").notNull(),
  modelName: varchar("model_name", { length: 255 }).notNull(),
  adapterType: varchar("adapter_type", { length: 64 }).notNull(),
  latencyMs: integer("latency_ms").notNull(),
  status: varchar("status", { length: 32 }).notNull(), // INITIALIZING | ONLINE | WORKING | SUCCESS | ERROR | OFFLINE
  targetEndpoint: varchar("target_endpoint", { length: 255 }),
  errorMessage: text("error_message"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const diagnosticEvents = pgTable("diagnostic_events", {
  id: varchar("id", { length: 64 }).primaryKey(),
  eventType: varchar("event_type", { length: 64 }).notNull(), // PROBE | HEALTH_CHECK | ERROR | MODEL_CHANGE
  targetUrl: varchar("target_url", { length: 255 }).notNull(),
  status: varchar("status", { length: 32 }).notNull(),
  details: jsonb("details"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});
