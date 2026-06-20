// Central configuration. Loads .env and decides whether the app runs in
// "live" mode (all credentials present) or "mock" mode (anything missing).
import dotenv from "dotenv";

dotenv.config();

const REQUIRED_KEYS = [
  "ELEVENLABS_API_KEY",
  "ELEVENLABS_AGENT_ID",
  "ANAM_API_KEY",
];

const missing = REQUIRED_KEYS.filter((key) => !process.env[key]);

// Anam needs a Persona ID (what Anam Lab exposes for custom and stock
// characters). ANAM_AVATAR_ID is accepted only as a legacy fallback.
if (!process.env.ANAM_PERSONA_ID && !process.env.ANAM_AVATAR_ID) {
  missing.push("ANAM_PERSONA_ID");
}

export const config = {
  port: Number(process.env.PORT) || 5180,

  // "live" only when every required credential is set.
  mode: missing.length === 0 ? "live" : "mock",
  missing,

  elevenLabs: {
    apiKey: process.env.ELEVENLABS_API_KEY || "",
    agentId: process.env.ELEVENLABS_AGENT_ID || "",
  },

  anam: {
    apiKey: process.env.ANAM_API_KEY || "",
    personaId: process.env.ANAM_PERSONA_ID || "",
    avatarId: process.env.ANAM_AVATAR_ID || "", // legacy fallback only
    voiceId: process.env.ANAM_VOICE_ID || "", // optional, fallback mode only
  },
};
