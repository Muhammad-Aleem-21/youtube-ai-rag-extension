// let currentVideoId = null;
// let aiButton = null;
// let chatWindow = null;
// let transcriptLoadedForVideo = null;
// let chatHistory = [];

// function getVideoId() {
//   const urlParams = new URLSearchParams(window.location.search);
//   return urlParams.get("v");
// }

// /* =========================
//    CREATE AI BUTTON
// ========================= */

// function createAIButton() {
//   if (aiButton) {
//     return;
//   }

//   aiButton = document.createElement("button");

//   aiButton.id = "youtube-ai-button";
//   aiButton.innerHTML = "🤖";
//   aiButton.title = "Ask AI about this video";

//   aiButton.addEventListener("click", () => {
//     toggleChat();
//   });

//   document.body.appendChild(aiButton);
// }

// /* =========================
//    CREATE CHAT WINDOW
// ========================= */

// function createChatWindow() {
//   if (chatWindow) {
//     return;
//   }

//   chatWindow = document.createElement("div");

//   chatWindow.id = "youtube-ai-chat";

//   chatWindow.innerHTML = `
//     <div class="youtube-ai-header">

//       <div class="youtube-ai-title">
//         <span class="youtube-ai-icon">🤖</span>

//         <div>
//           <div class="youtube-ai-name">
//             YouTube AI
//           </div>

//           <div class="youtube-ai-status">
//             ● Ready
//           </div>
//         </div>
//       </div>

//       <button
//         id="youtube-ai-close"
//         class="youtube-ai-close"
//         title="Close"
//       >
//         ×
//       </button>

//     </div>

//     <div class="youtube-ai-video">
//       <div class="youtube-ai-video-label">
//         Current Video
//       </div>

//       <div
//         id="youtube-ai-video-id"
//         class="youtube-ai-video-id"
//       >
//         Detecting...
//       </div>
//     </div>

//     <div
//       id="youtube-ai-messages"
//       class="youtube-ai-messages"
//     >

//       <div id="youtube-ai-heading" class="youtube-ai-heading">
//         ✨ Ask anything about this Topic
//       </div>

//     </div>

//     <div class="youtube-ai-input-area">

//       <textarea
//         id="youtube-ai-input"
//         placeholder="Ask something about this video..."
//         rows="1"
//       ></textarea>

//       <button
//         id="youtube-ai-send"
//         title="Send"
//       >
//         ➤
//       </button>

//     </div>
//   `;

//   document.body.appendChild(chatWindow);

//   setupChatEvents();

//   updateVideoInfo();

//   loadTranscript();
// }

// /* =========================
//    CHAT EVENTS
// ========================= */

// function setupChatEvents() {
//   const closeButton = document.getElementById("youtube-ai-close");

//   const sendButton = document.getElementById("youtube-ai-send");

//   const input = document.getElementById("youtube-ai-input");

//   closeButton.addEventListener("click", () => {
//     closeChat();
//   });

//   sendButton.addEventListener("click", () => {
//     sendMessage();
//   });

//   input.addEventListener("keydown", (event) => {
//     if (event.key === "Enter" && !event.shiftKey) {
//       event.preventDefault();

//       sendMessage();
//     }
//   });
// }

// /* =========================
//    SEND MESSAGE
// ========================= */

// function sendMessage() {
//   const input = document.getElementById("youtube-ai-input");

//   const question = input.value.trim();

//   if (!question) {
//     return;
//   }

//   const videoId = getVideoId();

//   if (!videoId) {
//     addMessage("❌ I couldn't detect the current YouTube video.", "ai");

//     return;
//   }

//   // Display user message

//   addMessage(question, "user");

//   input.value = "";

//   // Save user message

//   chatHistory.push({
//     role: "user",
//     content: question,
//   });

//   // Loading message

//   addMessage("⏳ Thinking...", "ai");

//   chrome.runtime.sendMessage(
//     {
//       type: "CHAT",

//       videoId: videoId,

//       question: question,

//       history: chatHistory.slice(0, -1),
//     },

//     (response) => {
//       if (chrome.runtime.lastError) {
//         console.error(chrome.runtime.lastError);

//         replaceLastAIMessage("❌ Could not connect to the backend.");

//         return;
//       }

//       if (!response || !response.success) {
//         replaceLastAIMessage(
//           `❌ ${response?.error || "Something went wrong."}`,
//         );

//         return;
//       }

//       const data = response.data;

//       // Save AI response

//       chatHistory.push({
//         role: "assistant",
//         content: data.answer,
//       });

//       // Replace loading message

//       replaceLastAIMessage(data.answer, data.sources);

//       console.log("RAG response:", data);
//     },
//   );
// }

// /* =========================
//    ADD MESSAGE
// ========================= */

// function addMessage(text, type) {
//   const messages = document.getElementById("youtube-ai-messages");

//   const message = document.createElement("div");

//   message.className =
//     type === "user"
//       ? "youtube-ai-message user-message"
//       : "youtube-ai-message ai-message";

//   message.textContent = text;

//   messages.appendChild(message);

//   messages.scrollTop = messages.scrollHeight;
// }
// ////
// function replaceLastAIMessage(text, sources = []) {
//   const messages = document.getElementById("youtube-ai-messages");

//   if (!messages) {
//     return;
//   }

//   const aiMessages = messages.querySelectorAll(
//     ".youtube-ai-message.ai-message",
//   );

//   if (aiMessages.length === 0) {
//     addMessage(text, "ai");

//     return;
//   }

//   const lastMessage = aiMessages[aiMessages.length - 1];

//   lastMessage.innerHTML = "";

//   const answer = document.createElement("div");

//   answer.className = "youtube-ai-answer";

//   // Preserve line breaks

//   answer.textContent = text;

//   lastMessage.appendChild(answer);

//     // Sources: transcript timestamps and web links

//   if (sources && sources.length > 0) {
//     const transcriptSources = sources.filter((s) => s.type !== "web");
//     const webSources = sources.filter((s) => s.type === "web");

//     // Transcript timestamp buttons (same as before)

//     if (transcriptSources.length > 0) {
//       const timestamps = document.createElement("div");

//       timestamps.className = "youtube-ai-timestamps";

//       transcriptSources.forEach((source) => {
//         const button = document.createElement("button");

//         const totalSeconds = Math.floor(source.start);

//         const minutes = Math.floor(totalSeconds / 60);

//         const seconds = totalSeconds % 60;

//         const formatted = `${minutes}:${String(seconds).padStart(2, "0")}`;

//         button.textContent = `▶ ${formatted}`;

//         button.title = "Jump to this part of the video";

//         button.addEventListener("click", () => {
//           jumpToTimestamp(source.start);
//         });

//         timestamps.appendChild(button);
//       });

//       lastMessage.appendChild(timestamps);
//     }

//     // Web links

//     if (webSources.length > 0) {
//       const links = document.createElement("div");

//       links.className = "youtube-ai-web-sources";

//       const label = document.createElement("div");

//       label.className = "youtube-ai-web-label";

//       label.textContent = "🌐 Sources";

//       links.appendChild(label);

//       webSources.forEach((source) => {
//         const link = document.createElement("a");

//         link.href = source.url;

//         link.target = "_blank";

//         link.rel = "noopener noreferrer";

//         link.textContent = source.title || source.url;

//         link.title = source.url;

//         links.appendChild(link);
//       });

//       lastMessage.appendChild(links);
//     }
//   }

// }

// /* =========================
//    UPDATE VIDEO INFO
// ========================= */

// function updateVideoInfo() {
//   const videoId = getVideoId();

//   const videoIdElement = document.getElementById("youtube-ai-video-id");

//   if (!videoIdElement) {
//     return;
//   }

//   if (videoId) {
//     videoIdElement.textContent = videoId;
//   } else {
//     videoIdElement.textContent = "No video detected";
//   }
// }

// /* =========================
//    OPEN / CLOSE CHAT
// ========================= */

// function toggleChat() {
//   if (!chatWindow) {
//     createChatWindow();
//   }

//   if (chatWindow.style.display === "none" || chatWindow.style.display === "") {
//     chatWindow.style.display = "flex";

//     updateVideoInfo();
//   } else {
//     closeChat();
//   }
// }

// function closeChat() {
//   if (chatWindow) {
//     chatWindow.style.display = "none";
//   }
// }

// /* =========================
//    CHECK VIDEO CHANGES
// ========================= */

// function checkVideo() {
//   const videoId = getVideoId();

//   if (!videoId) {
//     return;
//   }

//   if (videoId !== currentVideoId) {
//     currentVideoId = videoId;

//     transcriptLoadedForVideo = null;

//     // Clear conversation for the previous video
//     chatHistory = [];

//     console.log("YouTube video changed:", currentVideoId);

//     updateVideoInfo();

//     if (chatWindow) {
//       clearChatMessages();
//       showWelcomeMessage();
//       loadTranscript();
//     }
//   }
// }
// createAIButton();
// setInterval(checkVideo, 1000);

// checkVideo();

// ////
// function loadTranscript() {
//   const videoId = getVideoId();

//   if (!videoId) {
//     return;
//   }
//   if (transcriptLoadedForVideo === videoId) {
//     return;
//   }

//   transcriptLoadedForVideo = videoId;

//   const messages = document.getElementById("youtube-ai-messages");

//   if (!messages) {
//     return;
//   }

//   addMessage("⏳ Loading the transcript for this video...", "ai");

//   chrome.runtime.sendMessage(
//     {
//       type: "GET_TRANSCRIPT",
//       videoId: videoId,
//     },
//     (response) => {
//       if (chrome.runtime.lastError) {
//         addMessage(
//           "❌ Could not connect to the backend. Make sure the Python server is running.",
//           "ai",
//         );

//         return;
//       }

//       if (!response || !response.success) {
//         addMessage(
//           `❌ ${response?.error || "Could not retrieve the transcript."}`,
//           "ai",
//         );

//         return;
//       }

//       const transcriptData = response.data;

//       console.log("Transcript received:", transcriptData);

//       addMessage(
//         `✅ Transcript loaded successfully (${transcriptData.count} segments).`,
//         "ai",
//       );

//       console.log("Full transcript:", transcriptData.transcript);
//     },
//   );
// }

// /////
// function clearChatMessages() {
//   const messages = document.getElementById("youtube-ai-messages");

//   if (!messages) {
//     return;
//   }

//   messages.innerHTML = "";
// }

// function showWelcomeMessage() {
//   addMessage(
//     "👋 Hi! I'm your YouTube AI assistant.\n\nAsk me anything about the video you're watching.",
//     "ai",
//   );
// }

// /////
// function jumpToTimestamp(seconds) {
//   const video = document.querySelector("video");

//   if (!video) {
//     console.error("YouTube video element not found.");

//     return;
//   }

//   video.currentTime = seconds;

//   video.play();
// }


let currentVideoId = null;
let aiButton = null;
let chatWindow = null;
let transcriptLoadedForVideo = null; // video ID whose transcript is confirmed on the backend
let transcriptInFlight = null; // { videoId, promise }
let chatHistory = [];

const BRIDGE_REQUEST = "YT_AI_TRANSCRIPT_REQUEST";
const BRIDGE_RESPONSE = "YT_AI_TRANSCRIPT_RESPONSE";
const BRIDGE_TIMEOUT_MS = 30000;

function getVideoId() {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get("v");
}

/* =========================
   CREATE AI BUTTON
========================= */

function createAIButton() {
  if (aiButton) {
    return;
  }

  aiButton = document.createElement("button");

  aiButton.id = "youtube-ai-button";
  aiButton.innerHTML = "🤖";
  aiButton.title = "Ask AI about this video";

  aiButton.addEventListener("click", () => {
    toggleChat();
  });

  document.body.appendChild(aiButton);
}

/* =========================
   CREATE CHAT WINDOW
========================= */

function createChatWindow() {
  if (chatWindow) {
    return;
  }

  chatWindow = document.createElement("div");

  chatWindow.id = "youtube-ai-chat";

  chatWindow.innerHTML = `
    <div class="youtube-ai-header">

      <div class="youtube-ai-title">
        <span class="youtube-ai-icon">🤖</span>

        <div>
          <div class="youtube-ai-name">
            YouTube AI
          </div>

          <div id="youtube-ai-status" class="youtube-ai-status">
            ● Ready
          </div>
        </div>
      </div>

      <button
        id="youtube-ai-close"
        class="youtube-ai-close"
        title="Close"
      >
        ×
      </button>

    </div>

    <div class="youtube-ai-video">
      <div class="youtube-ai-video-label">
        Current Video
      </div>

      <div
        id="youtube-ai-video-id"
        class="youtube-ai-video-id"
      >
        Detecting...
      </div>
    </div>

    <div
      id="youtube-ai-messages"
      class="youtube-ai-messages"
    >

      <div id="youtube-ai-heading" class="youtube-ai-heading">
        ✨ Ask anything about this Topic
      </div>

    </div>

    <div class="youtube-ai-input-area">

      <textarea
        id="youtube-ai-input"
        placeholder="Ask something about this video..."
        rows="1"
      ></textarea>

      <button
        id="youtube-ai-send"
        title="Send"
      >
        ➤
      </button>

    </div>
  `;

  document.body.appendChild(chatWindow);

  setupChatEvents();

  updateVideoInfo();

  loadTranscript();
}

/* =========================
   CHAT EVENTS
========================= */

function setupChatEvents() {
  const closeButton = document.getElementById("youtube-ai-close");

  const sendButton = document.getElementById("youtube-ai-send");

  const input = document.getElementById("youtube-ai-input");

  closeButton.addEventListener("click", () => {
    closeChat();
  });

  sendButton.addEventListener("click", () => {
    sendMessage();
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();

      sendMessage();
    }
  });
}

/* =========================
   BACKGROUND MESSAGING
========================= */

function sendToBackground(message) {
  return new Promise((resolve) => {
    const failure = {
      success: false,
      error: "Could not connect to the extension. Try reloading the page.",
      code: "EXTENSION_ERROR",
    };

    try {
      chrome.runtime.sendMessage(message, (response) => {
        if (chrome.runtime.lastError) {
          console.error(
            "[YT-AI] runtime error:",
            chrome.runtime.lastError.message,
          );

          resolve(failure);

          return;
        }

        resolve(response || failure);
      });
    } catch (error) {
      // e.g. "Extension context invalidated" after the extension was reloaded
      console.error("[YT-AI] sendMessage threw:", error);

      resolve(failure);
    }
  });
}

/* =========================
   TRANSCRIPT ACQUISITION (via page bridge)
========================= */

function requestTranscriptFromPage(videoId) {
  return new Promise((resolve, reject) => {
    const requestId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;

    const timer = setTimeout(() => {
      window.removeEventListener("message", onMessage);

      reject({
        code: "BRIDGE_TIMEOUT",
        message: "Timed out waiting for the YouTube page.",
      });
    }, BRIDGE_TIMEOUT_MS);

    function onMessage(event) {
      if (event.source !== window) {
        return;
      }

      const data = event.data;

      if (!data || data.type !== BRIDGE_RESPONSE || data.requestId !== requestId) {
        return;
      }

      clearTimeout(timer);

      window.removeEventListener("message", onMessage);

      if (data.ok) {
        resolve(data);
      } else {
        reject(data.error || { code: "TRANSCRIPT_FAILED" });
      }
    }

    window.addEventListener("message", onMessage);

    window.postMessage(
      { type: BRIDGE_REQUEST, requestId: requestId, videoId: videoId },
      window.location.origin,
    );
  });
}

function sanitizeTranscript(raw) {
  if (!Array.isArray(raw)) {
    return [];
  }

  const out = [];

  for (const segment of raw) {
    if (!segment || typeof segment.text !== "string") {
      continue;
    }

    const text = segment.text.replace(/\s+/g, " ").trim();
    const start = Number(segment.start);
    const duration = Number(segment.duration);

    if (!text || !Number.isFinite(start) || start < 0) {
      continue;
    }

    out.push({
      text: text,
      start: start,
      duration: Number.isFinite(duration) && duration >= 0 ? duration : 0,
    });
  }

  return out;
}

function friendlyTranscriptError(code) {
  switch (code) {
    case "CAPTIONS_DISABLED":
      return "Captions are disabled for this video.";

    case "NO_USABLE_TRANSCRIPT":
      return "No usable transcript is available for this video.";

    default:
      return "Could not retrieve captions for this video.";
  }
}

async function runTranscriptPipeline(videoId, force) {
  // 1. Already on the server? Then don't extract or send anything.
  if (!force) {
    const status = await sendToBackground({
      type: "TRANSCRIPT_STATUS",
      videoId: videoId,
    });

    if (status.success && status.data && status.data.ready) {
      console.log("[YT-AI] Transcript already cached on server:", videoId);

      return { ok: true, count: status.data.count };
    }
  }

  // 2. Get it from the YouTube page (user's browser).
  let page;

  try {
    page = await requestTranscriptFromPage(videoId);
  } catch (error) {
    console.warn("[YT-AI] Transcript acquisition failed:", error);

    return {
      ok: false,
      code: error && error.code,
      error: friendlyTranscriptError(error && error.code),
    };
  }

  const transcript = sanitizeTranscript(page.transcript);

  if (!transcript.length) {
    return {
      ok: false,
      code: "NO_USABLE_TRANSCRIPT",
      error: friendlyTranscriptError("NO_USABLE_TRANSCRIPT"),
    };
  }

  if (getVideoId() !== videoId) {
    return { ok: false, stale: true, error: "The video changed." };
  }

  // 3. Send it to Railway once.
  const upload = await sendToBackground({
    type: "UPLOAD_TRANSCRIPT",
    payload: {
      video_id: videoId,
      transcript: transcript,
      language: page.language || null,
      language_code: page.language_code || null,
      is_generated:
        typeof page.is_generated === "boolean" ? page.is_generated : null,
    },
  });

  if (!upload.success) {
    return {
      ok: false,
      code: upload.code,
      error: upload.error || "Could not send the transcript to the server.",
    };
  }

  return {
    ok: true,
    count: (upload.data && upload.data.count) || transcript.length,
  };
}

function ensureTranscript(videoId, force = false) {
  if (!force && transcriptLoadedForVideo === videoId) {
    return Promise.resolve({ ok: true });
  }

  if (!force && transcriptInFlight && transcriptInFlight.videoId === videoId) {
    return transcriptInFlight.promise;
  }

  const promise = runTranscriptPipeline(videoId, force)
    .then((result) => {
      if (result.ok && getVideoId() === videoId) {
        transcriptLoadedForVideo = videoId;
      }

      return result;
    })
    .finally(() => {
      if (transcriptInFlight && transcriptInFlight.promise === promise) {
        transcriptInFlight = null;
      }
    });

  transcriptInFlight = { videoId: videoId, promise: promise };

  return promise;
}

/* =========================
   SEND MESSAGE
========================= */

async function askBackend(videoId, question, history) {
  const ready = await ensureTranscript(videoId);

  if (!ready.ok) {
    return { success: false, error: ready.error };
  }

  let response = await sendToBackground({
    type: "CHAT",
    videoId: videoId,
    question: question,
    history: history,
  });

  // Server restarted / cache evicted → resend the transcript once and retry.
  if (!response.success && response.code === "TRANSCRIPT_NOT_LOADED") {
    console.warn("[YT-AI] Server lost the transcript; re-uploading.");

    transcriptLoadedForVideo = null;

    const reload = await ensureTranscript(videoId, true);

    if (!reload.ok) {
      return { success: false, error: reload.error };
    }

    response = await sendToBackground({
      type: "CHAT",
      videoId: videoId,
      question: question,
      history: history,
    });
  }

  return response;
}

function sendMessage() {
  const input = document.getElementById("youtube-ai-input");

  const question = input.value.trim();

  if (!question) {
    return;
  }

  const videoId = getVideoId();

  if (!videoId) {
    addMessage("❌ I couldn't detect the current YouTube video.", "ai");

    return;
  }

  addMessage(question, "user");

  input.value = "";

  chatHistory.push({
    role: "user",
    content: question,
  });

  addMessage("⏳ Thinking...", "ai");

  const history = chatHistory.slice(0, -1);

  askBackend(videoId, question, history).then((response) => {
    // The user navigated to another video while we were waiting.
    if (getVideoId() !== videoId) {
      return;
    }

    if (!response || !response.success) {
      replaceLastAIMessage(
        `❌ ${response?.error || "Something went wrong."}`,
      );

      return;
    }

    const data = response.data;

    chatHistory.push({
      role: "assistant",
      content: data.answer,
    });

    replaceLastAIMessage(data.answer, data.sources);

    console.log("RAG response:", data);
  });
}

/* =========================
   ADD MESSAGE
========================= */

function addMessage(text, type) {
  const messages = document.getElementById("youtube-ai-messages");

  const message = document.createElement("div");

  message.className =
    type === "user"
      ? "youtube-ai-message user-message"
      : "youtube-ai-message ai-message";

  message.textContent = text;

  messages.appendChild(message);

  messages.scrollTop = messages.scrollHeight;

  return message;
}

function setMessageText(messageElement, text) {
  if (messageElement) {
    messageElement.textContent = text;
  }
}

function replaceLastAIMessage(text, sources = []) {
  const messages = document.getElementById("youtube-ai-messages");

  if (!messages) {
    return;
  }

  const aiMessages = messages.querySelectorAll(
    ".youtube-ai-message.ai-message",
  );

  if (aiMessages.length === 0) {
    addMessage(text, "ai");

    return;
  }

  const lastMessage = aiMessages[aiMessages.length - 1];

  lastMessage.innerHTML = "";

  const answer = document.createElement("div");

  answer.className = "youtube-ai-answer";

  answer.textContent = text;

  lastMessage.appendChild(answer);

  if (sources && sources.length > 0) {
    const transcriptSources = sources.filter((s) => s.type !== "web");
    const webSources = sources.filter((s) => s.type === "web");

    if (transcriptSources.length > 0) {
      const timestamps = document.createElement("div");

      timestamps.className = "youtube-ai-timestamps";

      transcriptSources.forEach((source) => {
        const button = document.createElement("button");

        const totalSeconds = Math.floor(source.start);

        const minutes = Math.floor(totalSeconds / 60);

        const seconds = totalSeconds % 60;

        const formatted = `${minutes}:${String(seconds).padStart(2, "0")}`;

        button.textContent = `▶ ${formatted}`;

        button.title = "Jump to this part of the video";

        button.addEventListener("click", () => {
          jumpToTimestamp(source.start);
        });

        timestamps.appendChild(button);
      });

      lastMessage.appendChild(timestamps);
    }

    if (webSources.length > 0) {
      const links = document.createElement("div");

      links.className = "youtube-ai-web-sources";

      const label = document.createElement("div");

      label.className = "youtube-ai-web-label";

      label.textContent = "🌐 Sources";

      links.appendChild(label);

      webSources.forEach((source) => {
        const link = document.createElement("a");

        link.href = source.url;

        link.target = "_blank";

        link.rel = "noopener noreferrer";

        link.textContent = source.title || source.url;

        link.title = source.url;

        links.appendChild(link);
      });

      // (the original code built this block but never attached it)
      lastMessage.appendChild(links);
    }
  }
}

/* =========================
   UPDATE VIDEO INFO / STATUS
========================= */

function updateVideoInfo() {
  const videoId = getVideoId();

  const videoIdElement = document.getElementById("youtube-ai-video-id");

  if (!videoIdElement) {
    return;
  }

  if (videoId) {
    videoIdElement.textContent = videoId;
  } else {
    videoIdElement.textContent = "No video detected";
  }
}

function setStatus(text) {
  const status = document.getElementById("youtube-ai-status");

  if (status) {
    status.textContent = `● ${text}`;
  }
}

/* =========================
   OPEN / CLOSE CHAT
========================= */

function toggleChat() {
  if (!chatWindow) {
    createChatWindow();
  }

  if (chatWindow.style.display === "none" || chatWindow.style.display === "") {
    chatWindow.style.display = "flex";

    updateVideoInfo();

    // No-op if already loaded/loading; retries after an earlier failure
    // and covers a video change while the window was hidden.
    loadTranscript();
  } else {
    closeChat();
  }
}

function closeChat() {
  if (chatWindow) {
    chatWindow.style.display = "none";
  }
}

/* =========================
   CHECK VIDEO CHANGES
========================= */

function checkVideo() {
  const videoId = getVideoId();

  if (!videoId) {
    return;
  }

  if (videoId !== currentVideoId) {
    currentVideoId = videoId;

    transcriptLoadedForVideo = null;

    transcriptInFlight = null;

    chatHistory = [];

    console.log("YouTube video changed:", currentVideoId);

    updateVideoInfo();

    if (chatWindow) {
      clearChatMessages();
      showWelcomeMessage();

      // Only fetch right away if the window is visible;
      // otherwise toggleChat() loads it when the user opens the window.
      if (chatWindow.style.display === "flex") {
        loadTranscript();
      } else {
        setStatus("Ready");
      }
    }
  }
}

createAIButton();

setInterval(checkVideo, 1000);

// YouTube fires this after each SPA navigation (faster than the poll).
window.addEventListener("yt-navigate-finish", checkVideo);

checkVideo();

/* =========================
   LOAD TRANSCRIPT
========================= */

async function loadTranscript() {
  const videoId = getVideoId();

  if (!videoId) {
    return;
  }

  if (!document.getElementById("youtube-ai-messages")) {
    return;
  }

  if (transcriptLoadedForVideo === videoId) {
    return;
  }

  if (transcriptInFlight && transcriptInFlight.videoId === videoId) {
    return;
  }

  setStatus("Loading transcript...");

  const notice = addMessage(
    "⏳ Loading the transcript for this video...",
    "ai",
  );

  const result = await ensureTranscript(videoId);

  // The user navigated away while we were loading.
  if (getVideoId() !== videoId) {
    return;
  }

  if (result.ok) {
    setMessageText(
      notice,
      result.count
        ? `✅ Transcript loaded successfully (${result.count} segments).`
        : "✅ Transcript loaded successfully.",
    );

    setStatus("Ready");
  } else {
    setMessageText(notice, `❌ ${result.error}`);

    setStatus("Transcript unavailable");
  }
}

/* =========================
   HELPERS
========================= */

function clearChatMessages() {
  const messages = document.getElementById("youtube-ai-messages");

  if (!messages) {
    return;
  }

  messages.innerHTML = "";
}

function showWelcomeMessage() {
  addMessage(
    "👋 Hi! I'm your YouTube AI assistant.\n\nAsk me anything about the video you're watching.",
    "ai",
  );
}

function jumpToTimestamp(seconds) {
  const video = document.querySelector("video");

  if (!video) {
    console.error("YouTube video element not found.");
    return;
  }

  video.currentTime = seconds;

  video.play();
}