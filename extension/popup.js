const API = "https://smart-query-system.onrender.com/*";

function loadQueries() { 
chrome.storage.local.get(["access_token"], ({ access_token }) => fetch(`${API}/api/queries?status=Pending`, {
  headers: access_token ? { Authorization: `Bearer ${access_token}` } : {},
})
  .then((res) => res.json())
  .then((data) => {
    const list = document.getElementById("query-list");
    document.getElementById("query-count").textContent = `You have ${data.length} pending query(s)`;
    list.replaceChildren();
    if (data.length === 0) {
      const empty = document.createElement("p");
      empty.textContent = "No pending queries.";
      list.append(empty);
      return;
    }
    data.forEach((q) => {
      const item = document.createElement("div");
      item.className = "query-item";

      const subject = document.createElement("b");
      subject.textContent = q.subject;
      const email = document.createElement("span");
      email.className = "email";
      email.textContent = q.student_email;
      const status = document.createElement("span");
      status.className = `badge ${q.status === "In Progress" ? "in-progress" : ""}`;
      status.textContent = q.status;

      item.append(subject, email, status);
      list.append(item);
    });
  })
  .catch((err) => {
    document.getElementById("query-list").innerHTML = "Error loading queries.";
    document.getElementById("query-count").textContent = "Sign in to the dashboard to see protected queries.";
    console.error(err);
  }));
}
loadQueries();
document.getElementById("refresh").addEventListener("click", loadQueries);

document.getElementById("open-dashboard").addEventListener("click", () => {
  chrome.tabs.create({ url: "https://smart-query-dashboard.onrender.com,chrome-extension://jnoefnjnodfbjmkbilebmifojgodocml" });
});
