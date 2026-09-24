import { useEffect, useState } from "react";
import Login from "./Login";
import { request, API } from "./api";

const menus = {
  Admin: ["Dashboard", "Users", "Escalated To HOD", "Escalated To Me", "Reassigned", "Analytics"],
  HOD: ["Dashboard", "Analytics"],
  Department: ["Dashboard", "Escalations", "Reassigned"],
  Instructor: ["Dashboard", "Escalations", "Reassigned"],
};

const badge = (s) => `badge ${s.toLowerCase().replaceAll(" ", "-")}`;

function Cards({ stats, role }) {
  const isDeptRole = role === "Department" || role === "Instructor";
  const labels = isDeptRole
    ? ["Total Queries", "Pending", "Resolved Today", "Escalated", "Reassigned"]
    : ["Total Queries", "Pending", "Resolved Today", "Escalated"];
  const values = isDeptRole
    ? [stats.total, stats.pending, stats.resolved_today, stats.escalated, stats.reassigned]
    : [stats.total, stats.pending, stats.resolved_today, stats.escalated];
  return (
    <div className="cards">
      {labels.map((label, i) => (
        <article className="metric" key={label}>
          <span>{label}</span>
          <strong className={["blue", "orange", "green", "red", "purple"][i]}>
            {String(values[i] || 0).padStart(2, "0")}
          </strong>
        </article>
      ))}
    </div>
  );
}

function NewQueryForm({ onCreated }) {
  const [form, setForm] = useState({ student_email: "", subject: "", query_text: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await request("/api/query", { method: "POST", body: JSON.stringify(form) });
      setForm({ student_email: "", subject: "", query_text: "" });
      onCreated();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel">
      <h2>Submit New Query (simulates an incoming student email)</h2>
      <form onSubmit={submit} className="button-row">
        <input
          placeholder="Student email"
          type="email"
          value={form.student_email}
          onChange={(e) => setForm({ ...form, student_email: e.target.value })}
          required
        />
        <input
          placeholder="Subject"
          value={form.subject}
          onChange={(e) => setForm({ ...form, subject: e.target.value })}
          required
        />
        <input
          placeholder="Query text"
          value={form.query_text}
          onChange={(e) => setForm({ ...form, query_text: e.target.value })}
          required
        />
        <button className="primary" type="submit" disabled={busy}>
          Submit Query
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </section>
  );
}

function QueryTable({ queries, deptNames, open, escalate, viewerRole }) {
  return (
    <section className="panel">
      <h2>Recent Queries</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Subject</th>
              <th>Student Email</th>
              <th>Category</th>
              <th>Department</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {queries.slice(0, 10).map((q) => (
              <tr key={q.query_id}>
                <td>{q.subject}</td>
                <td>{q.student_email}</td>
                <td>{q.category || "Not classified"}</td>
                <td>
                {q.dept_id
                  ? (viewerRole === "Admin" || viewerRole === "HOD"
                    ? (deptNames[q.dept_id] || "Routed")
                    : "Routed")
                  : "Not routed"}
                </td>
                <td>
                  <span className={badge(q.status)}>{q.status === "Escalated" && viewerRole === "HOD" ? "Action Required" : viewerRole === "Admin" && q.status === "Reassigned by HOD"? `Reassigned to ${deptNames[q.dept_id] || "Unknown"}`: q.status}</span>
                </td>
                <td className="actions">
                  {q.status !== "Resolved" && <button onClick={() => open(q)}>✎</button>}
                  {q.status !== "Resolved" && q.status !== "Reassigned by HOD" && viewerRole !== "HOD" && <button onClick={() => escalate(q)}>⚑</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Detail({ query, back, reload, user, departments, deptNames }) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [escalateTarget, setEscalateTarget] = useState("HOD");
  const [reassigning, setReassigning] = useState(false);
  const [reassignTarget, setReassignTarget] = useState("");
  const [reassignComment, setReassignComment] = useState("");
  const [reassignBusy, setReassignBusy] = useState(false);
  const [rerouting, setRerouting] = useState(false);
  const [rerouteTarget, setRerouteTarget] = useState("");
  const [rerouteBusy, setRerouteBusy] = useState(false);

  const rerouteQuery = async () => {
  setRerouteBusy(true);
  setActionError("");
  try {
    await request(`/api/queries/${query.query_id}/assign-department`, {
      method: "PATCH",
      body: JSON.stringify({ dept_id: rerouteTarget }),
    });
    reload();
    back();
  } catch (e) {
    setActionError(e.message);
  } finally {
    setRerouteBusy(false);
  }
};
  const generate = async () => {
  setBusy(true);
  setActionError("");
  setActionMessage("");
  try {
    const result = await request(`/api/reply/generate?query_id=${query.query_id}`, { method: "POST" });
    setDraft(result.draft);
  } catch (e) {
    setActionError(e.message);
  } finally {
    setBusy(false);
  }
};

  const escalateThis = async () => {
  try {
    await request(`/api/queries/${query.query_id}/escalate?escalated_to_role=${escalateTarget}`, { method: "POST" });
    reload();
    back();
  } catch (e) {
    setActionError(e.message);
  }
};
const deptByName = Object.fromEntries(departments.map((d) => [d.dept_name, d.dept_id]));
const REASSIGN_OPTIONS = [
  ...departments
    .filter((d) => d.dept_name !== "Admin")
    .map((d) => ({ label: d.dept_name === "Academic" ? "Instructor" : d.dept_name, value: d.dept_id })),
  { label: "Admin", value: "ADMIN" },
];

const forwardQuery = async () => {
  setReassignBusy(true);
  setActionError("");
  try {
    await request(`/api/queries/${query.query_id}/reassign`, {
      method: "POST",
      body: JSON.stringify({ target: reassignTarget, comment: reassignComment }),
      });
      reload();
      back();
    } catch (e) {
    setActionError(e.message);
    } finally {
    setReassignBusy(false);
  }
};
  const approveAndSend = async () => {
    setBusy(true);
    setActionError("");
    try {
      await request("/api/reply/send", {
        method: "POST",
        body: JSON.stringify({ query_id: query.query_id, body: draft }),
      });
      reload();
      back();
    } catch (e) {
      setActionError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="detail">
      <button className="back" onClick={back}>← Back to Dashboard</button>
      <div className="detail-grid">
        <section className="panel">
          <h2>Query Information</h2>
          <dl>
            <dt>Student Name</dt>
            <dd>{query.student_name || "Not provided"}</dd>
            <dt>Student Email</dt>
            <dd>{query.student_email}</dd>
            <dt>Subject</dt>
            <dd>{query.subject}</dd>
            <dt>Category</dt>
            <dd>{query.category || "Not classified"}</dd>
            <dt>Department</dt>
            <dd>{query.dept_id ? (deptNames[query.dept_id] || "Routed") : "Not routed"}</dd>
            
            <dt>Status</dt>
            <dd><span className={badge(query.status)}>{query.status === "Escalated" && user.role === "HOD"? "Action Required": user.role === "Admin" && query.status === "Reassigned by HOD"? `Reassigned to ${deptNames[query.dept_id] || "Unknown"}`: query.status}</span></dd>
          </dl>
          {actionMessage && <p className="success-message">{actionMessage}</p>}
          {actionError && <p className="error">{actionError}</p>}
        </section>

        <section className="panel message">
          <h2>Student Message</h2>
          <p>{query.query_text}</p>
        </section>
        {query.hod_comment && (
          <section className="panel message">
            <h2>Note from HOD</h2>
            <p>{query.hod_comment}</p>
          </section>
        )}
        <section className="panel">
            <h2>AI Reply (Editable)</h2>
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Generate an editable reply draft…"
            />
            <div className="button-row">
              <button className="primary" disabled={busy} onClick={generate}>Generate AI Reply</button>
              <button className="success" disabled={!draft || busy} onClick={approveAndSend}>Approve & Send</button>
              {user.role === "HOD" && (
                <button className="primary" onClick={() => setReassigning(true)}>Reassign</button>
              )}
              {user.role === "Admin" && (
                <button className="primary" onClick={() => setRerouting(true)}>Reroute</button>
              )}
              {(user.role === "Department" || user.role === "Instructor") && (
                <select value={escalateTarget} onChange={(e) => setEscalateTarget(e.target.value)}>
                  <option value="HOD">Escalate to HOD</option>
                  <option value="Admin">Escalate to Admin</option>
                </select>
              )}
              {user.role !== "HOD" && query.status !== "Reassigned by HOD" && (
                <button className="danger" disabled={busy} onClick={escalateThis}>Escalate</button>
              )}
            </div>

            {reassigning && (
              <div className="panel" style={{ marginTop: 12 }}>
                <h2>Reassign Query</h2>
                <select value={reassignTarget} onChange={(e) => setReassignTarget(e.target.value)}>
                  <option value="">Choose department…</option>
                    {REASSIGN_OPTIONS.map((opt) => (
                    <option key={opt.label} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
                {reassignTarget && (
                  <textarea
                    placeholder="Add a comment for the receiving department…"
                    value={reassignComment}
                    onChange={(e) => setReassignComment(e.target.value)}
                    style={{ marginTop: 10, width: "100%" }}
                  />
                )}
                {reassignTarget && reassignComment.trim() && (
                  <button className="success" disabled={reassignBusy} onClick={forwardQuery} style={{ marginTop: 10 }}>
                    Forward
                  </button>
                )}
              </div>
            )}

            {rerouting && (
              <div className="panel" style={{ marginTop: 12 }}>
              <h2>Reroute to Correct Department</h2>
              <select value={rerouteTarget} onChange={(e) => setRerouteTarget(e.target.value)}>
                <option value="">Choose department…</option>
                {departments
                  .filter((d) => d.dept_name !== "Admin")
                  .map((d) => (
                    <option key={d.dept_id} value={d.dept_id}>
                      {d.dept_name === "Academic" ? "Instructor" : d.dept_name}
                    </option>
                  ))}
                </select>
                {rerouteTarget && (
                  <button className="success" disabled={rerouteBusy} onClick={rerouteQuery} style={{ marginTop: 10 }}>
                    Confirm Reroute
                  </button>
                )}
              </div>
            )}
          </section>
      </div>
    </main>
  );
}
function DropdownButton({ children, onClick, danger }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: hover ? "#F3F4F6" : "transparent",
        border: "none",
        textAlign: "left",
        padding: "9px 12px",
        borderRadius: 6,
        fontSize: 14,
        fontWeight: 500,
        color: danger ? "#B0362B" : "#1E293B",
        cursor: "pointer",
      }}
    >
      {children}
    </button>
  );
}

function Users({ departments, deptNameById }) {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ name: "", email: "", role: "Instructor", dept_id: "" });
  const [formError, setFormError] = useState("");
  const [openMenuId, setOpenMenuId] = useState(null);
  const [notice, setNotice] = useState("");

  const fixedDepartmentName = {
    Admin: "Admin",
    HOD: "HOD",
    Instructor: "Academic",
  }[form.role];
  const fixedDepartment = fixedDepartmentName
    ? departments.find((department) => department.dept_name === fixedDepartmentName)
    : null;
  const departmentOptions = departments.filter((department) =>
    ["Finance", "Exam", "Registrar", "IT Support"].includes(department.dept_name)
  );
  const selectedDepartmentId = fixedDepartment ? fixedDepartment.dept_id : form.dept_id;

  const loadUsers = () => request("/api/users").then((data) => setUsers(data.filter((u) => u.role !== "Admin"))).catch(() => {});
  useEffect(() => { loadUsers(); }, []);

  useEffect(() => {
    if (!openMenuId) return;
    const closeMenu = () => setOpenMenuId(null);
    document.addEventListener("click", closeMenu);
    return () => document.removeEventListener("click", closeMenu);
  }, [openMenuId]);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 4000);
    return () => clearTimeout(timer);
  }, [notice]);

  const addUser = async (e) => {
    e.preventDefault();
    setFormError("");
    if (!selectedDepartmentId) {
      setFormError("The required department has not loaded. Please try again.");
      return;
    }
    try {
      await request("/api/users", {
        method: "POST",
        body: JSON.stringify({ ...form, dept_id: selectedDepartmentId }),
      });
      setForm({ name: "", email: "", role: "Instructor", dept_id: "" });
      loadUsers();
    } catch (err) {
      setFormError(err.message);
    }
  };

  const activateUser = async (id) => {
    setOpenMenuId(null);
    try {
      await request(`/api/users/${id}/activate`, { method: "POST" });
      setNotice("User has been activated.");
      loadUsers();
    } catch (e) {
      setFormError(e.message);
    }
  };

  const deactivateUser = async (id) => {
    setOpenMenuId(null);
    try {
      await request(`/api/users/${id}/deactivate`, { method: "POST" });
      setNotice("User has been deactivated.");
      loadUsers();
    } catch (e) {
      setFormError(e.message);
    }
  };

  const deleteUser = async (id) => {
    setOpenMenuId(null);
    if (!window.confirm("This will permanently delete this user's account. Continue?")) return;
    try {
      await request(`/api/users/${id}`, { method: "DELETE" });
      setNotice("User has been deleted.");
      loadUsers();
    } catch (e) {
      setFormError(e.message);
    }
  };

  return (
    <section className="panel">
      <div className="section-heading"><h2>User Management</h2></div>
      <form onSubmit={addUser} className="button-row" style={{ marginBottom: 16 }}>
        <input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        <input placeholder="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
        <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value, dept_id: "" })}>
          <option>Instructor</option>
          <option>Department</option>
          <option>HOD</option>
          <option>Admin</option>
        </select>
        <select
          value={selectedDepartmentId}
          disabled={Boolean(fixedDepartmentName)}
          onChange={(e) => setForm({ ...form, dept_id: e.target.value })}
          required
        >
          {fixedDepartmentName ? (
            <option value={fixedDepartment?.dept_id || ""}>
              {fixedDepartmentName}
            </option>
          ) : (
            <>
              <option value="">Choose department…</option>
              {departmentOptions.map((department) => (
                <option key={department.dept_id} value={department.dept_id}>
                  {department.dept_name}
                </option>
              ))}
            </>
          )}
        </select>
        <button className="primary" type="submit">＋ Add User</button>
      </form>
      {formError && <p className="error">{formError}</p>}
      {notice && <p className="success-message">{notice}</p>}

      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>Name</th><th>Email</th><th>Role</th><th>Department</th><th>Status</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const isActive = u.is_active !== false;
              return (
                <tr key={u.user_id} style={!isActive ? { opacity: 0.5 } : {}}>
                  <td>{u.name}</td>
                  <td>{u.email}</td>
                  <td>{u.role}</td>
                  <td>{deptNameById[u.dept_id] || "—"}</td>
                  <td>{isActive ? "Active" : "Inactive"}</td>
                  <td style={{ position: "relative", textAlign: "center" }}>
                    <button
                      onClick={(e) => { e.stopPropagation(); setOpenMenuId(openMenuId === u.user_id ? null : u.user_id); }}
                      style={{
                        background: "none",
                        border: "none",
                        fontSize: 20,
                        cursor: "pointer",
                        color: "#4B5563",
                        padding: "4px 10px",
                        borderRadius: 6,
                      }}
                    >
                      ⋮
                    </button>

                    {openMenuId === u.user_id && (
                      <div
                        style={{
                          position: "absolute",
                          top: "calc(100% + 4px)",
                          right: 8,
                          background: "#fff",
                          border: "1px solid #E5E7EB",
                          borderRadius: 10,
                          boxShadow: "0 10px 30px rgba(0,0,0,0.18)",
                          minWidth: 140,
                          padding: 6,
                          display: "flex",
                          flexDirection: "column",
                          zIndex: 100,
                        }}
                      >
                        {isActive ? (
                          <DropdownButton onClick={() => deactivateUser(u.user_id)}>Deactivate</DropdownButton>
                        ) : (
                          <DropdownButton onClick={() => activateUser(u.user_id)}>Activate</DropdownButton>
                        )}
                          <DropdownButton danger onClick={() => deleteUser(u.user_id)}>Delete</DropdownButton>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const CHART_COLORS = ["#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed", "#0891b2"];

function DonutChart({ data }) {
  const entries = Object.entries(data);
  const total = entries.reduce((sum, [, v]) => sum + v, 0) || 1;

  let cumulative = 0;
  const segments = entries.map(([, value], i) => {
    const start = (cumulative / total) * 360;
    cumulative += value;
    const end = (cumulative / total) * 360;
    return `${CHART_COLORS[i % CHART_COLORS.length]} ${start}deg ${end}deg`;
  });

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
      <div
        style={{
          width: 160,
          height: 160,
          borderRadius: "50%",
          background: `conic-gradient(${segments.join(", ")})`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: 100,
            height: 100,
            background: "#fff",
            borderRadius: "50%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 22,
            fontWeight: 700,
            color: "#1e293b",
          }}
        >
          {total}
        </div>
      </div>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {entries.map(([label, value], i) => (
          <li key={label} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, fontSize: 14 }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                display: "inline-block",
                background: CHART_COLORS[i % CHART_COLORS.length],
              }}
            />
            {label} — {value}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Analytics() {
  const [data, setData] = useState(null);
  const [workload, setWorkload] = useState(null);

  useEffect(() => {
    request("/api/analytics").then(setData).catch(() => {});
    request("/api/analytics/departments").then(setWorkload).catch(() => {});
  }, []);

  if (!data) return <p>Loading analytics...</p>;

  return (
    <div className="analytics-grid">
      <section className="panel">
        <h2>Queries by Category</h2>
        <DonutChart data={data.by_category} />
      </section>

      <section className="panel">
        <h2>Queries by Status</h2>
        <div className="bars">
          {Object.entries(data.by_status).map(([name, count]) => {
            const max = Math.max(...Object.values(data.by_status), 1);
            return (
              <div key={name}>
                <span>{name}</span>
                <i style={{ width: `${Math.max(10, (count / max) * 100)}%` }} />
                {count}
              </div>
            );
          })}
        </div>
      </section>

      {workload && (
        <section className="panel">
          <h2>Department Workload</h2>
          <div className="bars">
            {Object.entries(workload).map(([name, count]) => {
              const max = Math.max(...Object.values(workload), 1);
              return (
                <div key={name}>
                  <span>{name}</span>
                  <i style={{ width: `${Math.max(10, (count / max) * 100)}%` }} />
                  {count}
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
export default function App() {
  const [user, setUser] = useState(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const [stats, setStats] = useState({});
  const [queries, setQueries] = useState([]);
  const [active, setActive] = useState("Dashboard");
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const [bulkMessage, setBulkMessage] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);
  const [departments, setDepartments] = useState([]);

  useEffect(() => {
  if (!user) return;
  request("/api/departments").then(setDepartments).catch(() => {});
}, [user]);
  const deptNameById = Object.fromEntries(departments.map((d) => [d.dept_id, d.dept_name]));

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) { setCheckingSession(false); return; }
    request("/api/auth/profile")
      .then((u) => { setUser(u); setActive("Dashboard"); })
      .catch(() => localStorage.removeItem("access_token"))
      .finally(() => setCheckingSession(false));
  }, []);
  useEffect(() => {
  if (!bulkMessage) return;
  const timer = setTimeout(() => setBulkMessage(""), 5000);
  return () => clearTimeout(timer);
}, [bulkMessage]);

const load = async (section = active) => {
  try {
    const s = await request("/api/dashboard/stats");
    setStats(s);
    if (section === "Escalated To HOD") {
      setQueries(await request("/api/escalations?target=HOD"));
    } else if (section === "Escalated To Me") {
      setQueries(await request("/api/escalations?target=Admin"));
    } else if (section === "Escalations") {
      setQueries(await request("/api/escalations"));
    } else if (section === "Reassigned") {
      setQueries(await request("/api/reassigned"));
    } else {
      const all = await request("/api/queries");
      setQueries(user.role === "HOD" || user.role === "Admin" ? all : all.filter((q) => q.status !== "Escalated" && q.status !== "Reassigned by HOD"));
    }
  } catch (e) {
    setError(e.message);
  }
};

const downloadReport = async () => {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API}/api/reports/daily`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) { setError("Failed to generate report."); return; }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "daily_report.pdf";
  a.click();
  window.URL.revokeObjectURL(url);
};

useEffect(() => { if (user) load(active); }, [user, active]);

  if (checkingSession) return <p style={{ padding: 24 }}>Loading session...</p>;
  if (!user) return <Login onLogin={setUser} />;
  if (selected) return <Detail query={selected} back={() => setSelected(null)} reload={() => load(active)} user={user} departments={departments} deptNames={deptNameById} />;

  const menu = menus[user.role] || menus.Instructor;

  return (
    <div className="app-shell">
      <aside>
        <div className="brand">▣ <span>Smart Query Router</span></div>
        {menu.map((item) => (
          <button key={item} className={active === item ? "nav active" : "nav"} onClick={() => setActive(item)}>
            {item}
          </button>
        ))}
        <button
          className="nav logout"
          onClick={() => {
            localStorage.removeItem("access_token");
            setUser(null);
            setBulkMessage("");
            setError("");
            setQueries([]);
            setActive("Dashboard");
          }}
        >
          Logout
        </button>
      </aside>

      <main className="content">
        <header>
          <div><h1>{active}</h1></div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
  <span
    style={{
      width: 34,
      height: 34,
      borderRadius: "50%",
      background: "#2F6FED",
      color: "#fff",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
    }}
  >
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="8" r="4" fill="currentColor" />
      <path d="M4 20c0-4.4 3.6-8 8-8s8 3.6 8 8" fill="currentColor" />
    </svg>
  </span>
  <div style={{ display: "flex", flexDirection: "column" }}>
    <span style={{ fontSize: 15, fontWeight: 700, color: "#14213D" }}>{user.name}</span>
    <span style={{ fontSize: 13, color: "#7C8698" }}>{user.role}</span>
  </div>
</div>
        </header>

        {error && <p className="error">{error}</p>}

        {active === "Users" ? (
          <Users departments={departments} deptNameById={deptNameById} />
        ) : active === "Analytics" ? (
          <Analytics />
        ) : (
          <>
            <Cards stats={stats} role={user.role} />
            {active === "Dashboard" && (
              <>
                {(user.role === "HOD" || user.role === "Admin") && (
                  <button className="primary" onClick={downloadReport} style={{ marginBottom: 12 }}>
                    Download Daily Report (PDF)
                  </button>
                )}
                {user.role === "Admin" && <NewQueryForm onCreated={load} />}
              </>
            )}
            <QueryTable
              queries={queries}
              deptNames={deptNameById}
              open={setSelected}
              viewerRole={user.role}
              escalate={(q) =>
                request(`/api/queries/${q.query_id}/escalate`, { method: "POST" })
                  .then(() => load(active))
                  .catch((e) => setError(e.message))
                }
              />
          </>
        )}
      </main>
    </div>
  );
}
