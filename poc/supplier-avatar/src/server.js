// Express server for the DT602 Supplier Setup Process Assistant PoC.
//
// Responsibilities:
//   1. Serve the static frontend from /public.
//   2. Tell the frontend whether the app is in "live" or "mock" mode.
//   3. Broker credentials: exchange server-side API keys for short-lived
//      browser credentials (ElevenLabs signed URL, Anam session token) so
//      that no API key ever reaches the browser.
import express from "express";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { config } from "./config.js";
import { getSignedUrl } from "./elevenlabs.js";
import { createSessionToken } from "./anam.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.join(__dirname, "..", "public");

const app = express();
app.use(express.json());
app.use(express.static(publicDir));

// Simple request logging for debugging / evidence.
app.use((req, res, next) => {
  console.log(`[server] ${req.method} ${req.url}`);
  next();
});

// Frontend asks this first to decide how to behave. Never includes secrets.
app.get("/api/config", (req, res) => {
  res.json({
    mode: config.mode,
    missing: config.missing,
  });
});

// Live mode only: short-lived URL the browser uses to talk to the agent.
app.get("/api/elevenlabs/signed-url", async (req, res) => {
  if (config.mode !== "live") {
    return res.status(503).json({ error: "App is in mock mode (credentials missing)." });
  }
  try {
    const signedUrl = await getSignedUrl(config.elevenLabs);
    res.json({ signedUrl });
  } catch (error) {
    console.error("[server] ElevenLabs signed URL error:", error.message);
    res.status(502).json({ error: error.message });
  }
});

// Live mode only: short-lived token the browser uses to stream the avatar.
app.post("/api/anam/session-token", async (req, res) => {
  if (config.mode !== "live") {
    return res.status(503).json({ error: "App is in mock mode (credentials missing)." });
  }
  try {
    const sessionToken = await createSessionToken(config.anam);
    res.json({ sessionToken });
  } catch (error) {
    console.error("[server] Anam session token error:", error.message);
    res.status(502).json({ error: error.message });
  }
});

app.listen(config.port, "127.0.0.1", () => {
  console.log("==================================================");
  console.log("  Supplier Setup Process Assistant (DT602 PoC)");
  console.log(`  Running at http://127.0.0.1:${config.port}`);
  console.log(`  Mode: ${config.mode.toUpperCase()}`);
  if (config.mode === "mock") {
    console.log(`  Missing credentials: ${config.missing.join(", ")}`);
    console.log("  Add them to .env and restart to enable live mode.");
  }
  console.log("==================================================");
});
