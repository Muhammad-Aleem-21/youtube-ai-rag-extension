/*
 * page-bridge.js
 *
 * Runs in the page's MAIN world (manifest: "world": "MAIN"), so it can see
 * YouTube's own JS objects (ytcfg, the player). Content scripts run in an
 * isolated world and cannot. All requests go to youtube.com from the user's
 * own browser/IP/cookies. Railway is never involved.
 *
 * Talks to content.js via window.postMessage.
 *
 * YOUTUBE-INTERNALS: everything that depends on YouTube's undocumented
 * structure lives in acquireTranscriptFromYouTube() and the helpers above it.
 * If YouTube changes something, this is the only file to update.
 */
(() => {
  "use strict";

  if (window.__ytAiBridgeInstalled) {
    return;
  }
  window.__ytAiBridgeInstalled = true;

  const REQUEST_TYPE = "YT_AI_TRANSCRIPT_REQUEST";
  const RESPONSE_TYPE = "YT_AI_TRANSCRIPT_RESPONSE";
  const TAG = "[YT-AI page-bridge]";

  const log = (...args) => console.log(TAG, ...args);
  const warn = (...args) => console.warn(TAG, ...args);

  class TranscriptError extends Error {
    constructor(code, message) {
      super(message);
      this.code = code;
    }
  }

  /* =========================
     GENERIC HELPERS
  ========================= */

  function findKey(root, key) {
    const stack = [root];

    while (stack.length) {
      const node = stack.pop();

      if (!node || typeof node !== "object") {
        continue;
      }

      if (!Array.isArray(node) && Object.prototype.hasOwnProperty.call(node, key)) {
        return node[key];
      }

      for (const value of Object.values(node)) {
        if (value && typeof value === "object") {
          stack.push(value);
        }
      }
    }

    return undefined;
  }

  function extractJsonAfter(text, markers) {
    for (const marker of markers) {
      const markerIndex = text.indexOf(marker);

      if (markerIndex === -1) {
        continue;
      }

      const start = text.indexOf("{", markerIndex + marker.length);

      if (start === -1) {
        continue;
      }

      let depth = 0;
      let inString = false;
      let escaped = false;

      for (let i = start; i < text.length; i++) {
        const c = text[i];

        if (inString) {
          if (escaped) {
            escaped = false;
          } else if (c === "\\") {
            escaped = true;
          } else if (c === '"') {
            inString = false;
          }
          continue;
        }

        if (c === '"') {
          inString = true;
        } else if (c === "{") {
          depth++;
        } else if (c === "}") {
          depth--;

          if (depth === 0) {
            try {
              return JSON.parse(text.slice(start, i + 1));
            } catch (error) {
              break;
            }
          }
        }
      }
    }

    return null;
  }

  function decodeEntities(value) {
    const textarea = document.createElement("textarea");
    textarea.innerHTML = value;
    return textarea.value;
  }

  function cleanText(value) {
    return decodeEntities(value || "").replace(/\s+/g, " ").trim();
  }

  /* =========================
     WATCH PAGE DATA
  ========================= */

  let watchHtmlCache = { videoId: null, promise: null };

  function fetchWatchHtml(videoId) {
    if (watchHtmlCache.videoId === videoId && watchHtmlCache.promise) {
      return watchHtmlCache.promise;
    }

    const promise = fetch(`/watch?v=${encodeURIComponent(videoId)}`, {
      credentials: "include",
    }).then((response) => {
      if (!response.ok) {
        throw new TranscriptError(
          "TRANSCRIPT_FAILED",
          `Watch page request failed: HTTP ${response.status}`,
        );
      }
      return response.text();
    });

    watchHtmlCache = { videoId, promise };

    promise.catch(() => {
      if (watchHtmlCache.promise === promise) {
        watchHtmlCache = { videoId: null, promise: null };
      }
    });

    return promise;
  }

  async function getPlayerResponse(videoId) {
    // 1. The live player object (fresh after SPA navigation)
    try {
      const player = document.querySelector("#movie_player");
      const response =
        player && typeof player.getPlayerResponse === "function"
          ? player.getPlayerResponse()
          : null;

      if (response && response.videoDetails && response.videoDetails.videoId === videoId) {
        return response;
      }
    } catch (error) {
      warn("movie_player.getPlayerResponse failed:", error);
    }

    // 2. Hard page load global
    const initial = window.ytInitialPlayerResponse;

    if (initial && initial.videoDetails && initial.videoDetails.videoId === videoId) {
      return initial;
    }

    // 3. Fetch the watch page (same-origin, user's own session)
    const html = await fetchWatchHtml(videoId);

    const parsed = extractJsonAfter(html, [
      "ytInitialPlayerResponse = ",
      'window["ytInitialPlayerResponse"] = ',
    ]);

    if (!parsed) {
      throw new TranscriptError(
        "TRANSCRIPT_FAILED",
        "Could not find player data in the watch page.",
      );
    }

    return parsed;
  }

  /* =========================
     STRATEGY A: caption track (timedtext)
  ========================= */

  function orderTracks(tracks) {
    const isEnglish = (t) => (t.languageCode || "").toLowerCase().startsWith("en");
    const isManual = (t) => t.kind !== "asr";

    const buckets = [
      tracks.filter((t) => isEnglish(t) && isManual(t)),
      tracks.filter((t) => isEnglish(t) && !isManual(t)),
      tracks.filter((t) => !isEnglish(t) && isManual(t)),
      tracks.filter((t) => !isEnglish(t) && !isManual(t)),
    ];

    return buckets.flat();
  }

  function trackLabel(track) {
    if (!track) {
      return null;
    }

    const name = track.name;

    if (name && name.simpleText) {
      return name.simpleText;
    }

    if (name && Array.isArray(name.runs)) {
      return name.runs.map((r) => r.text).join("");
    }

    return track.languageCode || null;
  }

  // When captions are switched on, the player itself requests a timedtext URL
  // that includes a PO token. If we can see it, reuse its token parameters.
  function getPotParams(videoId) {
    try {
      const entries = performance
        .getEntriesByType("resource")
        .filter(
          (e) =>
            e.name.includes("/api/timedtext") &&
            e.name.includes(`v=${videoId}`) &&
            e.name.includes("pot="),
        );

      if (!entries.length) {
        return null;
      }

      const url = new URL(entries[entries.length - 1].name);
      const params = {};

      for (const key of ["pot", "potc", "c"]) {
        if (url.searchParams.has(key)) {
          params[key] = url.searchParams.get(key);
        }
      }

      return params.pot ? params : null;
    } catch (error) {
      return null;
    }
  }

  function parseJson3(data) {
    const out = [];

    for (const event of data.events || []) {
      if (!event.segs) {
        continue;
      }

      const text = cleanText(event.segs.map((s) => s.utf8 || "").join(""));

      if (!text) {
        continue;
      }

      out.push({
        text: text,
        start: (event.tStartMs || 0) / 1000,
        duration: (event.dDurationMs || 0) / 1000,
      });
    }

    return out;
  }

  function parseXml(body) {
    const doc = new DOMParser().parseFromString(body, "text/xml");

    if (doc.querySelector("parsererror")) {
      return [];
    }

    const out = [];

    // Format 1: <text start="1.2" dur="3.4">
    doc.querySelectorAll("text").forEach((node) => {
      const text = cleanText(node.textContent);

      if (!text) {
        return;
      }

      out.push({
        text: text,
        start: parseFloat(node.getAttribute("start")) || 0,
        duration: parseFloat(node.getAttribute("dur")) || 0,
      });
    });

    if (out.length) {
      return out;
    }

    // Format 3: <p t="1200" d="3400"> (milliseconds)
    doc.querySelectorAll("p").forEach((node) => {
      const text = cleanText(node.textContent);

      if (!text) {
        return;
      }

      out.push({
        text: text,
        start: (parseFloat(node.getAttribute("t")) || 0) / 1000,
        duration: (parseFloat(node.getAttribute("d")) || 0) / 1000,
      });
    });

    return out;
  }

  async function fetchTrackSegments(track, videoId) {
    const url = new URL(track.baseUrl, location.origin);

    url.searchParams.set("fmt", "json3");

    const pot = getPotParams(videoId);

    if (pot) {
      for (const [key, value] of Object.entries(pot)) {
        url.searchParams.set(key, value);
      }
    }

    const response = await fetch(url.toString(), { credentials: "include" });

    if (!response.ok) {
      throw new Error(`timedtext HTTP ${response.status}`);
    }

    const body = await response.text();

    if (!body.trim()) {
      throw new Error("timedtext returned an empty body");
    }

    if (body.trimStart().startsWith("{")) {
      return parseJson3(JSON.parse(body));
    }

    return parseXml(body);
  }

  /* =========================
     STRATEGY B: innertube get_transcript
     (the endpoint behind YouTube's "Show transcript" panel)
  ========================= */

  async function fetchViaInnertube(videoId) {
    const html = await fetchWatchHtml(videoId);

    const initialData = extractJsonAfter(html, [
      "ytInitialData = ",
      'window["ytInitialData"] = ',
    ]);

    const endpoint = initialData && findKey(initialData, "getTranscriptEndpoint");
    const params = endpoint && endpoint.params;

    if (!params) {
      throw new Error("No transcript panel found for this video");
    }

    const cfg = window.ytcfg;

    const context =
      (cfg && typeof cfg.get === "function" && cfg.get("INNERTUBE_CONTEXT")) || {
        client: {
          clientName: "WEB",
          clientVersion:
            (cfg && typeof cfg.get === "function" && cfg.get("INNERTUBE_CLIENT_VERSION")) ||
            "2.20250101.00.00",
          hl: "en",
        },
      };

    const apiKey = cfg && typeof cfg.get === "function" ? cfg.get("INNERTUBE_API_KEY") : null;

    const endpointUrl =
      "/youtubei/v1/get_transcript?prettyPrint=false" +
      (apiKey ? `&key=${encodeURIComponent(apiKey)}` : "");

    const response = await fetch(endpointUrl, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context: context, params: params }),
    });

    if (!response.ok) {
      throw new Error(`get_transcript HTTP ${response.status}`);
    }

    const json = await response.json();
    const initialSegments = findKey(json, "initialSegments");

    if (!Array.isArray(initialSegments)) {
      throw new Error("get_transcript returned no segments");
    }

    const out = [];

    for (const item of initialSegments) {
      const renderer = item && item.transcriptSegmentRenderer;

      if (!renderer) {
        continue;
      }

      const snippet = renderer.snippet || {};

      const rawText = Array.isArray(snippet.runs)
        ? snippet.runs.map((r) => r.text).join("")
        : snippet.simpleText || "";

      const text = cleanText(rawText);

      if (!text) {
        continue;
      }

      const startMs = Number(renderer.startMs);
      const endMs = Number(renderer.endMs);

      out.push({
        text: text,
        start: Number.isFinite(startMs) ? startMs / 1000 : 0,
        duration:
          Number.isFinite(startMs) && Number.isFinite(endMs) && endMs >= startMs
            ? (endMs - startMs) / 1000
            : 0,
      });
    }

    return out;
  }

  /* =========================
     MAIN ENTRY: acquireTranscriptFromYouTube
  ========================= */

  async function acquireTranscriptFromYouTube(videoId) {
    const playerResponse = await getPlayerResponse(videoId);

    const renderer =
      playerResponse &&
      playerResponse.captions &&
      playerResponse.captions.playerCaptionsTracklistRenderer;

    const tracks = (renderer && renderer.captionTracks) || [];
    const candidates = orderTracks(tracks).filter((t) => t.baseUrl);

    log(
      `Video ${videoId}: ${tracks.length} caption track(s):`,
      tracks.map((t) => `${t.languageCode}${t.kind === "asr" ? " (auto)" : ""}`),
    );

    // Strategy A
    for (const track of candidates.slice(0, 3)) {
      try {
        const segments = await fetchTrackSegments(track, videoId);

        if (segments.length) {
          log(`Strategy A (timedtext) succeeded: ${segments.length} segments`);

          return {
            transcript: segments,
            language: trackLabel(track),
            language_code: track.languageCode || null,
            is_generated: track.kind === "asr",
          };
        }
      } catch (error) {
        warn(`Strategy A failed for track ${track.languageCode}:`, error.message);
      }
    }

    // Strategy B
    try {
      const segments = await fetchViaInnertube(videoId);

      if (segments.length) {
        log(`Strategy B (get_transcript) succeeded: ${segments.length} segments`);

        // get_transcript returns the video's default transcript language;
        // label it with the best matching track when we know one.
        const hint = candidates[0] || tracks[0] || null;

        return {
          transcript: segments,
          language: trackLabel(hint),
          language_code: hint ? hint.languageCode || null : null,
          is_generated: hint ? hint.kind === "asr" : null,
        };
      }
    } catch (error) {
      warn("Strategy B failed:", error.message);
    }

    if (!tracks.length) {
      throw new TranscriptError("CAPTIONS_DISABLED", "No caption tracks exist for this video.");
    }

    throw new TranscriptError(
      "NO_USABLE_TRANSCRIPT",
      "Caption tracks exist but no strategy returned usable text.",
    );
  }

  /* =========================
     MESSAGE BRIDGE
  ========================= */

  function respond(payload) {
    window.postMessage({ type: RESPONSE_TYPE, ...payload }, window.location.origin);
  }

  window.addEventListener("message", async (event) => {
    if (event.source !== window) {
      return;
    }

    const data = event.data;

    if (!data || data.type !== REQUEST_TYPE) {
      return;
    }

    const { requestId, videoId } = data;

    if (typeof videoId !== "string" || !/^[A-Za-z0-9_-]{11}$/.test(videoId)) {
      respond({
        requestId,
        ok: false,
        error: { code: "TRANSCRIPT_FAILED", message: "Invalid video ID." },
      });
      return;
    }

    try {
      const result = await acquireTranscriptFromYouTube(videoId);

      respond({
        requestId,
        ok: true,
        videoId,
        transcript: result.transcript,
        language: result.language,
        language_code: result.language_code,
        is_generated: result.is_generated,
      });
    } catch (error) {
      console.error(TAG, "Transcript acquisition failed:", error);

      respond({
        requestId,
        ok: false,
        error: {
          code: error.code || "TRANSCRIPT_FAILED",
          message: error.message || "Transcript acquisition failed.",
        },
      });
    }
  });

  log("ready");
})();