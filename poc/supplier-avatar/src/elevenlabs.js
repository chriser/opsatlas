// ElevenLabs integration (server side).
//
// The browser must never see ELEVENLABS_API_KEY. Instead, this module
// exchanges the API key for a short-lived "signed URL" (valid ~15 minutes)
// that the browser SDK uses to open the conversation with the agent.
//
// API reference:
//   GET https://api.elevenlabs.io/v1/convai/conversation/get-signed-url?agent_id=...
//   Header: xi-api-key
//   Response: { "signed_url": "wss://..." }
//
// If ElevenLabs changes this endpoint, this file is the only place to update.

const SIGNED_URL_ENDPOINT =
  "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url";

export async function getSignedUrl({ apiKey, agentId }) {
  const url = `${SIGNED_URL_ENDPOINT}?agent_id=${encodeURIComponent(agentId)}`;
  console.log(`[elevenlabs] Requesting signed URL for agent ${agentId.slice(0, 6)}...`);

  const response = await fetch(url, {
    method: "GET",
    headers: { "xi-api-key": apiKey },
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(
      `ElevenLabs signed URL request failed (${response.status}): ${body}`
    );
  }

  const data = await response.json();
  console.log("[elevenlabs] Signed URL obtained.");
  return data.signed_url;
}
