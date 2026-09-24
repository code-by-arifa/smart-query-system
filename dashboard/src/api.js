export const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function request(path, options = {}) {
  const token = localStorage.getItem("access_token");
  const response = await fetch(`${API}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || "Request failed");
  return response.status === 204 ? null : response.json();
}
