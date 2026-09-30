window.addEventListener("message", (event) => {
  if (event.source !== window || event.data?.type !== "smart-query-session") return;
  if (event.data.token) chrome.storage.local.set({ access_token: event.data.token });
  else chrome.storage.local.remove("access_token");
});