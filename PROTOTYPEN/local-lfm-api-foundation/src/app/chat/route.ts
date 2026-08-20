import { POST as chatPost } from "@/app/api/chat/route";

export const dynamic = "force-dynamic";

export async function POST(req: any) {
  return chatPost(req);
}
