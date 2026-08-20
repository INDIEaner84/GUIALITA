import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { proposals, codeModifications, agentLogs, sessions } from "@/db/schema";
import { eq } from "drizzle-orm";
import { randomUUID } from "crypto";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { proposalId, sessionId = "session_default" } = body;

    if (!proposalId) {
      return NextResponse.json({ success: false, error: "proposalId is required" }, { status: 400 });
    }

    const found = await db.select().from(proposals).where(eq(proposals.id, proposalId)).limit(1);

    if (found.length === 0) {
      return NextResponse.json({ success: false, error: "Proposal not found" }, { status: 404 });
    }

    const proposal = found[0];

    // Mark as applied
    await db.update(proposals).set({ isApplied: true }).where(eq(proposals.id, proposalId));

    const modId = `mod_${Date.now()}_${randomUUID().substring(0, 6)}`;
    await db.insert(codeModifications).values({
      id: modId,
      proposalId,
      filePath: proposal.affectedFile,
      previousCode: `// Original component state in ${proposal.affectedFile}`,
      newCode: proposal.proposedCode,
      status: "success",
      appliedAt: new Date(),
    });

    await db.insert(agentLogs).values({
      id: `log_${Date.now()}_${randomUUID().substring(0, 6)}`,
      sessionId,
      type: "code",
      speaker: "liquid_agent",
      message: `Vorschlag Option ${proposal.optionKey} (${proposal.title}) erfolgreich auf ${proposal.affectedFile} angewendet.`,
      metadata: { proposalId, file: proposal.affectedFile, stylePreset: proposal.stylePreset },
      timestamp: new Date(),
    });

    return NextResponse.json({
      success: true,
      appliedProposal: {
        ...proposal,
        isApplied: true,
      },
      modificationId: modId,
      reloadRequired: true,
      timestamp: new Date().toISOString(),
    });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err?.message }, { status: 500 });
  }
}
