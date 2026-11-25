/* VORNEQ V7-03: SSE stream parser for chat streaming (pure, DOM-free).
 * Feeds raw Uint8Array chunks; decodes UTF-8 incrementally (TextDecoder with
 * {stream: true}, so multibyte characters split across chunks stay intact),
 * reassembles SSE frames split at any byte, and returns only well-formed
 * events of known types with strictly increasing sequence numbers. Replayed
 * or out-of-order events and invalid JSON are dropped. No eval, no HTML.
 */
(function (global) {
  "use strict";
  const TYPES = new Set(["response.created", "response.started", "response.delta", "response.section",
    "response.citation", "response.usage", "response.completed", "response.incomplete",
    "response.cancelled", "response.failed", "heartbeat"]);
  const MAX_FRAME_CHARS = 65536;
  const MAX_BUFFER_CHARS = 262144;

  function create() {
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let lastSequence = 0;
    function parseFrame(frame) {
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("data:")) data += line.slice(5).trimStart();
      }
      if (!data || data.length > MAX_FRAME_CHARS) return null;
      try {
        const event = JSON.parse(data);
        if (!event || typeof event !== "object" || !TYPES.has(event.type) ||
            !Number.isInteger(event.sequence_number) || !event.payload || typeof event.payload !== "object") return null;
        return event;
      } catch (_error) { return null; }
    }
    function drain() {
      const events = [];
      let cut;
      while ((cut = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        const event = parseFrame(frame);
        if (!event || event.sequence_number <= lastSequence) continue;   // replayed / out of order
        lastSequence = event.sequence_number;
        events.push(event);
      }
      return events;
    }
    return {
      feed(chunk) {
        buffer += decoder.decode(chunk, { stream: true });
        if (buffer.length > MAX_BUFFER_CHARS) throw new Error("oversized stream buffer");
        return drain();
      },
      end() {
        buffer += decoder.decode();
        return drain();
      },
      get lastSequence() { return lastSequence; },
    };
  }
  global.VQStreamParser = Object.freeze({ create, TYPES });
})(typeof window !== "undefined" ? window : globalThis);
