import { GET as healthGet } from "@/app/api/health/route";

export const dynamic = "force-dynamic";

export async function GET() {
  return healthGet();
}
