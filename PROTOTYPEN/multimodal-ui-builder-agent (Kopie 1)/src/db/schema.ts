import { pgTable, text, timestamp, boolean, jsonb } from "drizzle-orm/pg-core";

export const sessions = pgTable("sessions", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  currentUrl: text("current_url").notNull().default("/"),
  activeTargetId: text("active_target_id"),
  activeProposalId: text("active_proposal_id"),
  status: text("status").notNull().default("idle"), // 'idle' | 'analyzing' | 'proposed' | 'applying' | 'verified' | 'error'
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

export const targetElements = pgTable("target_elements", {
  id: text("id").primaryKey(),
  sessionId: text("session_id").notNull(),
  selector: text("selector").notNull(),
  componentName: text("component_name").notNull(),
  filePath: text("file_path").notNull(),
  boundingBox: jsonb("bounding_box").notNull(), // { x: number, y: number, width: number, height: number }
  accessibilityLabel: text("accessibility_label"),
  currentCodeSnippet: text("current_code_snippet"),
  detectedReason: text("detected_reason"),
  screenshotUrl: text("screenshot_url"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const proposals = pgTable("proposals", {
  id: text("id").primaryKey(),
  targetId: text("target_id").notNull(),
  optionKey: text("option_key").notNull(), // 'A' | 'B' | 'C'
  title: text("title").notNull(),
  description: text("description").notNull(),
  stylePreset: text("style_preset").notNull(),
  affectedComponent: text("affected_component").notNull(),
  affectedFile: text("affected_file").notNull(),
  expectedVisualChange: text("expected_visual_change").notNull(),
  technicalChange: text("technical_change").notNull(),
  risk: text("risk").notNull().default("low"), // 'low' | 'medium' | 'high'
  proposedCode: text("proposed_code").notNull(),
  diffSummary: text("diff_summary").notNull(),
  isApplied: boolean("is_applied").default(false).notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const codeModifications = pgTable("code_modifications", {
  id: text("id").primaryKey(),
  proposalId: text("proposal_id").notNull(),
  filePath: text("file_path").notNull(),
  previousCode: text("previous_code").notNull(),
  newCode: text("new_code").notNull(),
  status: text("status").notNull().default("success"),
  appliedAt: timestamp("applied_at").defaultNow().notNull(),
});

export const agentLogs = pgTable("agent_logs", {
  id: text("id").primaryKey(),
  sessionId: text("session_id").notNull(),
  type: text("type").notNull(), // 'speech' | 'vision' | 'proposal' | 'code' | 'reload' | 'verify' | 'desktop'
  speaker: text("speaker").notNull(), // 'user' | 'liquid_agent' | 'system'
  message: text("message").notNull(),
  metadata: jsonb("metadata"),
  timestamp: timestamp("timestamp").defaultNow().notNull(),
});

export const desktopActions = pgTable("desktop_actions", {
  id: text("id").primaryKey(),
  sessionId: text("session_id").notNull(),
  actionType: text("action_type").notNull(), // 'mouse_click' | 'key_press' | 'launch_app' | 'screenshot' | 'switch_window'
  targetCoordinates: jsonb("target_coordinates"),
  description: text("description").notNull(),
  status: text("status").notNull().default("completed"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});
