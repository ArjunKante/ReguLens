import { Fragment, useEffect, useState } from "react";
import { listRules } from "../api/endpoints";
import type { RuleOut } from "../types";

export function RuleManagementPage() {
  const [rules, setRules] = useState<RuleOut[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listRules().then(setRules).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error-text">{error}</p>;

  return (
    <div>
      <h1>Rule Management</h1>
      <p className="page-subtitle">
        Every rule is traced to its statutory source. Editing a rule (admin only, via the API)
        creates a new version — past inspections keep referencing the version that was active when
        they ran; see docs/legal-rules.md for full source citations.
      </p>

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr><th>Rule</th><th>Reference</th><th>Type</th><th>Severity</th><th>Version</th><th>Status</th></tr>
          </thead>
          <tbody>
            {rules.map((rule) => (
              <Fragment key={rule.id}>
                <tr style={{ cursor: "pointer" }} onClick={() => setExpanded(expanded === rule.id ? null : rule.id)}>
                  <td><strong>{rule.rule_key}</strong><br />{rule.current_version?.title}</td>
                  <td>{rule.current_version?.rule_reference}</td>
                  <td>{rule.current_version?.validation_type}</td>
                  <td>{rule.current_version?.severity}</td>
                  <td>v{rule.current_version?.version_number}</td>
                  <td>{rule.active ? "Active" : "Inactive"}</td>
                </tr>
                {expanded === rule.id && rule.current_version && (
                  <tr>
                    <td colSpan={6} style={{ background: "#fafbfc" }}>
                      <p><strong>Requirement:</strong> {rule.current_version.requirement}</p>
                      <p><strong>Applicability:</strong> {rule.current_version.applicability}</p>
                      {rule.current_version.exceptions && (
                        <p><strong>Exceptions:</strong> {rule.current_version.exceptions}</p>
                      )}
                      <p>
                        <strong>Source:</strong> {rule.current_version.source_document} (
                        {rule.current_version.source_locator})
                      </p>
                      {rule.current_version.notes && <p><strong>Notes:</strong> {rule.current_version.notes}</p>}
                      {rule.current_version.applicable_categories.length > 0 && (
                        <p><strong>Applies only to:</strong> {rule.current_version.applicable_categories.join(", ")}</p>
                      )}
                      {rule.current_version.excluded_categories.length > 0 && (
                        <p><strong>Excluded categories:</strong> {rule.current_version.excluded_categories.join(", ")}</p>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
