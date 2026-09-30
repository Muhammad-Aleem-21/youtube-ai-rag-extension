// const API_URL = "https://youtube-ai-rag-extension-production.up.railway.app";
// chrome.runtime.onMessage.addListener(
//   (message, sender, sendResponse) => {

//     if (message.type === "GET_TRANSCRIPT") {

//       const videoId = message.videoId;

//       fetch(
//         `${API_URL}/transcript/${videoId}`
//       )
//         .then(async (response) => {

//           const data = await response.json();

//           if (!response.ok) {
//             throw new Error(
//               data.detail || "Failed to retrieve transcript."
//             );
//           }

//           sendResponse({
//             success: true,
//             data: data
//           });

//         })
//         .catch((error) => {

//           console.error(
//             "Transcript request failed:",
//             error
//           );

//           sendResponse({
//             success: false,
//             error: error.message
//           });

//         });

//       return true;
//     }


//     if (message.type === "CHAT") {

//       const videoId = message.videoId;
//       const question = message.question;

//       fetch(
//         `${API_URL}/chat`,
//         {
//           method: "POST",

//           headers: {
//             "Content-Type": "application/json"
//           },

//           body: JSON.stringify({
//             video_id: videoId,
//             question: question,
//             history: message.history || []
//           })
//         }
//       )
//         .then(async (response) => {

//           const text = await response.text();

//           let data;

//           try {
//             data = JSON.parse(text);
//           } catch (error) {
//             throw new Error(
//               "Backend returned an invalid response. Please check the backend terminal."
//             );
//           }

//           if (!response.ok) {
//             throw new Error(
//               data.detail || "Failed to get AI response."
//             );
//           }

//           sendResponse({
//             success: true,
//             data: data
//           });

//         })
        
//         .catch((error) => {

//           console.error(
//             "Chat request failed:",
//             error
//           );

//           sendResponse({
//             success: false,
//             error: error.message
//           });

//         });

//       return true;
//     }
//   }
// );


const API_URL = "https://youtube-ai-rag-extension-production.up.railway.app";

const TIMEOUTS = {
  status: 15000,
  upload: 90000, // first upload may wait for embedding model warm-up
  chat: 120000,
};

class ApiError extends Error {
  constructor(message, code, status) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

/* =========================
   CLIENT ID (per install)
========================= */

let clientIdPromise = null;

function getClientId() {
  if (!clientIdPromise) {
    clientIdPromise = (async () => {
      const stored = await chrome.storage.local.get("clientId");

      if (stored.clientId) {
        return stored.clientId;
      }

      const clientId = crypto.randomUUID();
      await chrome.storage.local.set({ clientId });
      return clientId;
    })();
  }

  return clientIdPromise;
}

/* =========================
   API HELPER
========================= */

function describeError(data, status) {
  const detail = data && data.detail;

  if (typeof detail === "string") {
    return { message: detail, code: undefined };
  }

  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    return {
      message: detail.message || `Request failed (${status}).`,
      code: detail.code,
    };
  }

  if (Array.isArray(detail)) {
    return {
      message: "The server rejected the request data.",
      code: "VALIDATION_ERROR",
    };
  }

  return { message: `Request failed (${status}).`, code: undefined };
}

async function apiRequest(path, { method = "GET", body, timeoutMs }) {
  const clientId = await getClientId();

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_URL}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        "X-Client-Id": clientId,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });

    const text = await response.text();

    let data = null;

    try {
      data = JSON.parse(text);
    } catch (error) {
      data = null;
    }

    if (!response.ok) {
      const { message, code } = describeError(data, response.status);
      throw new ApiError(message, code, response.status);
    }

    if (data === null) {
      throw new ApiError(
        "Backend returned an invalid response. Please check the backend logs.",
        "BAD_RESPONSE",
        response.status,
      );
    }

    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (error.name === "AbortError") {
      throw new ApiError("The request to the backend timed out.", "TIMEOUT");
    }

    throw new ApiError("Could not connect to the backend.", "NETWORK");
  } finally {
    clearTimeout(timer);
  }
}

/* =========================
   MESSAGE HANDLERS
========================= */

const HANDLERS = {
  // Is the transcript for this video already cached on the server?
  TRANSCRIPT_STATUS: (message) =>
    apiRequest(
      `/transcript/${encodeURIComponent(message.videoId)}/status`,
      { timeoutMs: TIMEOUTS.status },
    ),

  // Send the browser-acquired transcript to the server (once per video).
  UPLOAD_TRANSCRIPT: (message) => {
    const payload = message.payload;

    console.log(
      `Uploading transcript for ${payload.video_id}: ` +
        `${payload.transcript.length} segments, ` +
        `language=${payload.language_code || "unknown"}, ` +
        `generated=${payload.is_generated}`,
    );

    return apiRequest("/transcript", {
      method: "POST",
      body: payload,
      timeoutMs: TIMEOUTS.upload,
    });
  },

  CHAT: (message) =>
    apiRequest("/chat", {
      method: "POST",
      body: {
        video_id: message.videoId,
        question: message.question,
        history: message.history || [],
      },
      timeoutMs: TIMEOUTS.chat,
    }),
};

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const handler = message && HANDLERS[message.type];

  if (!handler) {
    return false;
  }

  handler(message)
    .then((data) => {
      sendResponse({ success: true, data: data });
    })
    .catch((error) => {
      console.error(`${message.type} failed:`, error);

      sendResponse({
        success: false,
        error: error.message || "Something went wrong.",
        code: error.code,
      });
    });

  return true;
});