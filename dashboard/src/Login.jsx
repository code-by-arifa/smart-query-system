import { useEffect } from "react";

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "368173087140-jq3rnv8nkbmtl4841961e3m7b0dde4s6.apps.googleusercontent.com";
import { API } from "./api";

export default function Login({ onLogin }) {
  useEffect(() => {
    /* global google */
    google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: handleCredential,
    });
    google.accounts.id.renderButton(document.getElementById("google-btn"), {
      theme: "outline",
      size: "large",
    });
  }, []);

  async function handleCredential(response) {
    const res = await fetch(`${API}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: response.credential }),
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      alert(errBody.detail || "You're not a registered staff member.");
      return;
    }
  
    const data = await res.json();
    localStorage.setItem("access_token", data.access_token);
    window.postMessage({ type: "smart-query-session", token: data.access_token }, window.location.origin);
    onLogin(data.user);
  }

  return (
    <div className="login-screen">
      <section className="login-brand"><div className="mail-icon">✉</div><h1>Smart Query<br/>Routing & Email<br/>Automation System</h1><p>Intelligent. Automated. Efficient.</p></section>
      <section className="login-card"><h2>Welcome Back!</h2><p>Sign in to access your dashboard</p><div id="google-btn"></div><small>◉ Secure authentication using Google OAuth2</small></section>
    </div>
  );
}
