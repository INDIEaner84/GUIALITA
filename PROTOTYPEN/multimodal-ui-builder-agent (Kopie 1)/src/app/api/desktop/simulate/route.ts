import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { desktopActions, agentLogs } from "@/db/schema";
import { randomUUID } from "crypto";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { actionType = "mouse_click", coordinates = { x: 450, y: 300 }, targetApp = "Chromium", sessionId = "session_default", description } = body;

    const actionId = `desk_${Date.now()}_${randomUUID().substring(0, 5)}`;
    const actionDesc = description || `Desktop Action '${actionType}' executed on ${targetApp} at (${coordinates.x}, ${coordinates.y}).`;

    await db.insert(desktopActions).values({
      id: actionId,
      sessionId,
      actionType,
      targetCoordinates: coordinates,
      description: actionDesc,
      status: "completed",
      createdAt: new Date(),
    });

    await db.insert(agentLogs).values({
      id: `log_${Date.now()}_${randomUUID().substring(0, 6)}`,
      sessionId,
      type: "desktop",
      speaker: "liquid_agent",
      message: actionDesc,
      metadata: { actionType, coordinates, targetApp },
      timestamp: new Date(),
    });

    return NextResponse.json({
      success: true,
      action: {
        id: actionId,
        actionType,
        targetApp,
        coordinates,
        description: actionDesc,
        status: "completed",
        timestamp: new Date().toISOString(),
      },
    });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err?.message }, { status: 500 });
  }
}
