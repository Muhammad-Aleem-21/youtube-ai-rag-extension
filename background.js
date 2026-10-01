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

async function postJson(path, body) {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const text = await response.text();

  let data;
  try {
    data = JSON.parse(text);
  } catch (error) {
    throw new Error(
      "Backend returned an invalid response. Please check the backend logs."
    );
  }

  return { response, data };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "UPLOAD_TRANSCRIPT") {
    postJson("/transcript", {
      video_id: message.videoId,
      language_code: message.languageCode,
      segments: message.segments,
    })
      .then(({ response, data }) => {
        if (!response.ok) {
          throw new Error(data.detail || "Failed to upload transcript.");
        }
        sendResponse({ success: true, data });
      })
      .catch((error) => {
        console.error("Transcript upload failed:", error);
        sendResponse({ success: false, error: error.message });
      });

    return true;
  }

  if (message.type === "CHAT") {
    postJson("/chat", {
      video_id: message.videoId,
      question: message.question,
      history: message.history || [],
    })
      .then(({ response, data }) => {
        if (response.status === 409 && data.detail === "TRANSCRIPT_NEEDED") {
          sendResponse({ success: false, code: "NEEDS_TRANSCRIPT" });
          return;
        }

        if (!response.ok) {
          throw new Error(data.detail || "Failed to get AI response.");
        }

        sendResponse({ success: true, data });
      })
      .catch((error) => {
        console.error("Chat request failed:", error);
        sendResponse({ success: false, error: error.message });
      });

    return true;
  }
});