import { useEffect, useState, type FormEvent } from "react";
import { createUser, listUsers } from "../api/endpoints";
import type { User } from "../types";

export function UserManagementPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("INSPECTOR");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function refresh() {
    listUsers().then(setUsers).catch((e) => setError(e.message));
  }

  useEffect(refresh, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createUser(email, password, fullName, role);
      setEmail("");
      setPassword("");
      setFullName("");
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h1>User Management</h1>
      <p className="page-subtitle">Admin-only: manage ReguLens accounts and roles.</p>

      <div className="card" style={{ padding: 0, marginBottom: 24 }}>
        <table>
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.full_name}</td>
                <td>{u.email}</td>
                <td>{u.role}</td>
                <td>{u.is_active ? "Active" : "Inactive"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Create user</h2>
      <div className="card" style={{ maxWidth: 480 }}>
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <label>Full name</label>
            <input type="text" required value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div className="form-row">
            <label>Email</label>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="form-row">
            <label>Password</label>
            <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <div className="form-row">
            <label>Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="ADMIN">Admin</option>
              <option value="INSPECTOR">Inspector</option>
              <option value="REVIEWER">Reviewer</option>
            </select>
          </div>
          <button type="submit" disabled={submitting}>{submitting ? "Creating…" : "Create user"}</button>
          {error && <p className="error-text">{error}</p>}
        </form>
      </div>
    </div>
  );
}
