// Receives the dashboard's short-lived session token and stores it for the popup.
window.addEventListener("message", (event) => {
  if (event.source !== window || event.data?.type !== "smart-query-session") return;
  chrome.storage.local.set({ access_token: event.data.token });
});
