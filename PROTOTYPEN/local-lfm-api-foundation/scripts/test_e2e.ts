import { modelManager } from "../src/lib/adapters/manager";

async function runE2ETest() {
  console.log("==================================================");
  console.log("   PHASE 0 — LOCAL LFM E2E FUNCTIONAL TEST   ");
  console.log("==================================================\n");

  console.log("1. Probing Local Model Runtimes...");
  const probes = await modelManager.probeAll();
  
  for (const [adapterKey, probe] of Object.entries(probes)) {
    const icon = probe.reachable ? "🟢" : "🔴";
    console.log(`   ${icon} Adapter [${adapterKey}]: status=${probe.status}, endpoint=${probe.targetEndpoint}, model=${probe.detectedModel || "none"}, latency=${probe.latencyMs}ms`);
  }

  console.log("\n2. Testing Primary LFM Adapter Direct Health...");
  const lfmAdapter = modelManager.getAdapter("lfm");
  const lfmHealth = await lfmAdapter.checkHealth();
  console.log(`   LFM Target: ${lfmHealth.targetEndpoint}`);
  console.log(`   LFM Reachable: ${lfmHealth.reachable}`);
  console.log(`   LFM Model Name: ${lfmHealth.detectedModel}`);
  console.log(`   LFM Latency: ${lfmHealth.latencyMs}ms`);

  if (!lfmHealth.reachable) {
    console.log(`\n⚠️ Warning: Native LFM engine on port 8000 is offline.`);
    console.log(`   Reason: ${lfmHealth.reason}`);
    console.log(`   Recommended Action: ${lfmHealth.recommendedAction}`);
  }

  console.log("\n3. Executing E2E Chat Message Test...");
  const prompt = "Hallo LFM, antworte mit:\nLFM CONNECTION TEST OK";
  console.log(`   User Prompt: "${prompt}"`);

  const startTime = Date.now();
  const chatResp = await modelManager.chat({ message: prompt });
  const duration = Date.now() - startTime;

  console.log("\n--- CHAT RESPONSE RECEIVED ---");
  console.log(`MODEL           : ${chatResp.model}`);
  console.log(`ADAPTER         : ${chatResp.adapterType}`);
  console.log(`ENDPOINT        : ${chatResp.targetEndpoint}`);
  console.log(`LATENCY         : ${chatResp.latency_ms}ms (Total roundtrip: ${duration}ms)`);
  console.log(`STATUS          : ${chatResp.status}`);
  console.log(`IS MOCK FALLBACK: ${chatResp.isMockFallback || false}`);
  console.log(`RESPONSE TEXT   :\n${chatResp.response}`);
  console.log("------------------------------\n");

  const passed = chatResp.status === "SUCCESS" && chatResp.response.includes("LFM CONNECTION TEST OK");

  if (passed) {
    console.log("✅ E2E TEST PASSED! Browser -> API -> Local LFM communication verified.");
  } else {
    console.error("❌ E2E TEST FAILED! Did not receive expected response.");
    process.exit(1);
  }
}

runE2ETest().catch((err) => {
  console.error("Fatal error during E2E test:", err);
  process.exit(1);
});
