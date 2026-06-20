// Anam integration (server side).
//
// The browser must never see ANAM_API_KEY. Instead, this module exchanges
// the API key for a short-lived session token that the browser SDK uses to
// open the WebRTC avatar stream.
//
// API reference:
//   POST https://api.anam.ai/v1/auth/session-token
//   Headers: Content-Type: application/json, Authorization: Bearer <API_KEY>
//   Response: { "sessionToken": "..." }
//
// Two ways to identify the character (this app prefers the first):
//   1. Stateful persona session:  { personaConfig: { personaId } }
//      Anam Lab exposes a Persona ID for both custom and stock characters.
//   2. Ephemeral runtime config:  { personaConfig: { name, avatarId, voiceId, llmId } }
//      Legacy fallback, only used when ANAM_PERSONA_ID is not set.
//
// If Anam changes this endpoint or body shape, this file is the only place
// to update.

const SESSION_TOKEN_ENDPOINT = "https://api.anam.ai/v1/auth/session-token";

// "Bring your own brain" LLM id for the ephemeral fallback: the avatar does
// no thinking of its own and only lip-syncs text we send from the browser.
const CUSTOM_BRAIN_LLM_ID = "CUSTOMER_CLIENT_V1";

export async function createSessionToken({ apiKey, personaId, avatarId, voiceId }) {
  let personaConfig;

  if (personaId) {
    console.log(
      `[anam] Using stateful persona mode (personaId ${personaId.slice(0, 6)}...).`
    );
    personaConfig = { personaId };
  } else if (avatarId) {
    console.log(
      `[anam] Using legacy avatarId fallback mode (avatarId ${avatarId.slice(0, 6)}...).`
    );
    personaConfig = {
      name: "Supplier Setup Process Assistant",
      avatarId,
      llmId: CUSTOM_BRAIN_LLM_ID,
    };
    if (voiceId) {
      personaConfig.voiceId = voiceId;
    }
  } else {
    throw new Error("No ANAM_PERSONA_ID (or fallback ANAM_AVATAR_ID) configured.");
  }

  const response = await fetch(SESSION_TOKEN_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({ personaConfig }),
  });

  if (!response.ok) {
    const body = await response.text();
    console.error(`[anam] Session token request failed: HTTP ${response.status}`);
    console.error(`[anam] Response body: ${body}`);
    throw new Error(`Anam session token request failed (${response.status})`);
  }

  const data = await response.json();
  console.log("[anam] Session token obtained.");
  return data.sessionToken;
}
