let currentVideoId = null;
let aiButton = null;
let chatWindow = null;
let transcriptLoadedForVideo = null;
let chatHistory = [];

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

  // Display user message

  addMessage(question, "user");

  input.value = "";

  // Save user message

  chatHistory.push({
    role: "user",
    content: question,
  });

  // Loading message

  addMessage("⏳ Thinking...", "ai");

  chrome.runtime.sendMessage(
    {
      type: "CHAT",

      videoId: videoId,

      question: question,

      history: chatHistory.slice(0, -1),
    },

    (response) => {
      if (chrome.runtime.lastError) {
        console.error(chrome.runtime.lastError);

        replaceLastAIMessage("❌ Could not connect to the backend.");

        return;
      }

      if (!response || !response.success) {
        replaceLastAIMessage(
          `❌ ${response?.error || "Something went wrong."}`,
        );

        return;
      }

      const data = response.data;

      // Save AI response

      chatHistory.push({
        role: "assistant",
        content: data.answer,
      });

      // Replace loading message

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

  const messages = document.getElementById("youtube-ai-messages");

  if (!messages) {
    return;
  }

  addMessage("⏳ Loading the transcript for this video...", "ai");

  chrome.runtime.sendMessage(
    {
      type: "GET_TRANSCRIPT",
      videoId: videoId,
    },
    (response) => {
      if (chrome.runtime.lastError) {
        addMessage(
          "❌ Could not connect to the backend. Make sure the Python server is running.",
          "ai",
        );

        return;
      }

      if (!response || !response.success) {
        addMessage(
          `❌ ${response?.error || "Could not retrieve the transcript."}`,
          "ai",
        );

        return;
      }

      const transcriptData = response.data;

      console.log("Transcript received:", transcriptData);

      addMessage(
        `✅ Transcript loaded successfully (${transcriptData.count} segments).`,
        "ai",
      );

      console.log("Full transcript:", transcriptData.transcript);
    },
  );
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
