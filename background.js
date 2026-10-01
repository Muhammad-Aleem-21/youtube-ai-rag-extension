const API_URL = "https://youtube-ai-rag-extension-production.up.railway.app";
chrome.runtime.onMessage.addListener(
  (message, sender, sendResponse) => {

    if (message.type === "GET_TRANSCRIPT") {

      const videoId = message.videoId;

      fetch(
        `${API_URL}/transcript/${videoId}`
      )
        .then(async (response) => {

          const data = await response.json();

          if (!response.ok) {
            throw new Error(
              data.detail || "Failed to retrieve transcript."
            );
          }

          sendResponse({
            success: true,
            data: data
          });

        })
        .catch((error) => {

          console.error(
            "Transcript request failed:",
            error
          );

          sendResponse({
            success: false,
            error: error.message
          });

        });

      return true;
    }


    if (message.type === "CHAT") {

      const videoId = message.videoId;
      const question = message.question;

      fetch(
        `${API_URL}/chat`,
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json"
          },

          body: JSON.stringify({
            video_id: videoId,
            question: question,
            history: message.history || []
          })
        }
      )
        .then(async (response) => {

          const text = await response.text();

          let data;

          try {
            data = JSON.parse(text);
          } catch (error) {
            throw new Error(
              "Backend returned an invalid response. Please check the backend terminal."
            );
          }

          if (!response.ok) {
            throw new Error(
              data.detail || "Failed to get AI response."
            );
          }

          sendResponse({
            success: true,
            data: data
          });

        })
        
        .catch((error) => {

          console.error(
            "Chat request failed:",
            error
          );

          sendResponse({
            success: false,
            error: error.message
          });

        });

      return true;
    }
  }
);

