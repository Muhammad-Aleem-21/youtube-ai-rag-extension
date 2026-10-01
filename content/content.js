let currentVideoId = null;
let aiButton = null;
let chatWindow = null;
let transcriptLoadedForVideo = null;
let chatHistory = [];
let currentTranscript = null; // { videoId, segments, languageCode, uploaded }
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

          <div class="youtube-ai-status">
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
   SEND MESSAGE
========================= */

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

  chatHistory.push({ role: "user", content: question });

  addMessage("⏳ Thinking...", "ai");

  requestChat(videoId, question, false);
}

function requestChat(videoId, question, isRetry) {
  chrome.runtime.sendMessage(
    {
      type: "CHAT",
      videoId: videoId,
      question: question,
      history: chatHistory.slice(0, -1),
    },

    async (response) => {
      if (chrome.runtime.lastError) {
        console.error(chrome.runtime.lastError);
        replaceLastAIMessage("❌ Could not connect to the backend.");
        return;
      }

      // Backend lost its cache (e.g. Railway restarted) → re-upload and retry once
      if (response && response.code === "NEEDS_TRANSCRIPT" && !isRetry) {
        try {
          await ensureTranscriptUploaded(videoId, true);
          requestChat(videoId, question, true);
        } catch (error) {
          replaceLastAIMessage(`❌ ${error.message}`);
        }
        return;
      }

      if (!response || !response.success) {
        replaceLastAIMessage(
          `❌ ${response?.error || "Something went wrong."}`,
        );
        return;
      }

      const data = response.data;

      chatHistory.push({ role: "assistant", content: data.answer });

      replaceLastAIMessage(data.answer, data.sources);

      console.log("RAG response:", data);
    },
  );
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
}
////
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

  // Preserve line breaks

  answer.textContent = text;

  lastMessage.appendChild(answer);

    // Sources: transcript timestamps and web links

  if (sources && sources.length > 0) {
    const transcriptSources = sources.filter((s) => s.type !== "web");
    const webSources = sources.filter((s) => s.type === "web");

    // Transcript timestamp buttons (same as before)

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

    // Web links

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

      lastMessage.appendChild(links);
    }
  }

}

/* =========================
   UPDATE VIDEO INFO
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

    // Clear conversation for the previous video
    chatHistory = [];
    currentTranscript = null;
    console.log("YouTube video changed:", currentVideoId);

    updateVideoInfo();

    if (chatWindow) {
      clearChatMessages();
      showWelcomeMessage();
      loadTranscript();
    }
  }
}
createAIButton();
setInterval(checkVideo, 1000);

checkVideo();

////
function loadTranscript() {
  const videoId = getVideoId();

  if (!videoId) {
    return;
  }
  if (transcriptLoadedForVideo === videoId) {
    return;
  }

  transcriptLoadedForVideo = videoId;

  if (!document.getElementById("youtube-ai-messages")) {
    return;
  }

  addMessage("⏳ Loading the transcript for this video...", "ai");

  ensureTranscriptUploaded(videoId)
    .then((t) => {
      addMessage(
        `✅ Transcript loaded successfully (${t.segments.length} segments).`,
        "ai",
      );
    })
    .catch((error) => {
      console.error("Transcript load failed:", error);
      transcriptLoadedForVideo = null;
      addMessage(`❌ ${error.message}`, "ai");
    });
}

/* =========================
   TRANSCRIPT (fetched in the user's browser)
========================= */

async function ensureTranscriptUploaded(videoId, force = false) {
  if (!currentTranscript || currentTranscript.videoId !== videoId) {
    const t = await getTranscriptFromBrowser(videoId);

    currentTranscript = {
      videoId: videoId,
      segments: t.segments,
      languageCode: t.languageCode,
      uploaded: false,
    };
  }

  if (force || !currentTranscript.uploaded) {
    await uploadTranscript(currentTranscript);
    currentTranscript.uploaded = true;
  }

  return currentTranscript;
}

function uploadTranscript(t) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(
      {
        type: "UPLOAD_TRANSCRIPT",
        videoId: t.videoId,
        languageCode: t.languageCode,
        segments: t.segments,
      },
      (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error("Could not connect to the backend."));
          return;
        }
        if (!response || !response.success) {
          reject(new Error(response?.error || "Failed to upload transcript."));
          return;
        }
        resolve(response.data);
      },
    );
  });
}

async function fetchCaptionTracks(videoId) {
  // Method 1: YouTube's internal player API (Android client)
  try {
    const res = await fetch(
      "https://www.youtube.com/youtubei/v1/player?prettyPrint=false",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          context: {
            client: {
              clientName: "ANDROID",
              clientVersion: "20.10.38",
              androidSdkVersion: 30,
              hl: "en",
            },
          },
          videoId: videoId,
        }),
      },
    );

    const data = await res.json();
    const tracks =
      data?.captions?.playerCaptionsTracklistRenderer?.captionTracks;

    if (tracks && tracks.length) {
      return tracks;
    }
  } catch (error) {
    console.warn("InnerTube caption lookup failed:", error);
  }

  // Method 2: read the player data embedded in the watch page
  try {
    const res = await fetch(`https://www.youtube.com/watch?v=${videoId}`);
    const html = await res.text();

    const match = html.match(
      /ytInitialPlayerResponse\s*=\s*({.+?})\s*;\s*(?:var\s|<\/script>)/,
    );

    if (match) {
      const data = JSON.parse(match[1]);
      const tracks =
        data?.captions?.playerCaptionsTracklistRenderer?.captionTracks;

      if (tracks && tracks.length) {
        return tracks;
      }
    }
  } catch (error) {
    console.warn("Watch page caption lookup failed:", error);
  }

  return [];
}

async function fetchTrackSegments(track, translateTo) {
  const url = new URL(track.baseUrl);

  url.searchParams.set("fmt", "json3");

  if (translateTo) {
    url.searchParams.set("tlang", translateTo);
  }

  const res = await fetch(url.toString());
  const text = await res.text();

  if (!text) {
    throw new Error("YouTube returned an empty caption response.");
  }

  const data = JSON.parse(text);

  return (data.events || [])
    .filter((e) => e.segs)
    .map((e) => ({
      text: e.segs
        .map((s) => s.utf8)
        .join("")
        .replace(/\n/g, " ")
        .trim(),
      start: (e.tStartMs || 0) / 1000,
      duration: (e.dDurationMs || 0) / 1000,
    }))
    .filter((s) => s.text);
}

async function getTranscriptFromBrowser(videoId) {
  const tracks = await fetchCaptionTracks(videoId);

  if (!tracks.length) {
    throw new Error("No captions are available for this video.");
  }

  const isEnglish = (t) => (t.languageCode || "").startsWith("en");

  // 1. English captions (prefer manual over auto-generated)
  const english =
    tracks.find((t) => isEnglish(t) && t.kind !== "asr") ||
    tracks.find(isEnglish);

  if (english) {
    const segments = await fetchTrackSegments(english);
    if (segments.length) {
      return { segments, languageCode: "en" };
    }
  }

  // 2. Other language: try YouTube's own translation to English
  const source = tracks[0];

  if (source.isTranslatable) {
    try {
      const segments = await fetchTrackSegments(source, "en");
      if (segments.length) {
        return { segments, languageCode: "en" };
      }
    } catch (error) {
      console.warn("YouTube translation failed, falling back to Groq:", error);
    }
  }

  // 3. Send the original language; the backend translates it with Groq
  const segments = await fetchTrackSegments(source);

  if (!segments.length) {
    throw new Error("The transcript was empty.");
  }

  return { segments, languageCode: source.languageCode || "unknown" };
}

/////
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

/////
function jumpToTimestamp(seconds) {
  const video = document.querySelector("video");

  if (!video) {
    console.error("YouTube video element not found.");

    return;
  }

  video.currentTime = seconds;

  video.play();
}


// #####################
//let currentVideoId = null;
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


