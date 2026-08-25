import { useState } from "react";
import { submitReview } from "../api/endpoints";
import type { ComplianceCheck } from "../types";

interface Props {
  inspectionId: string;
  check: ComplianceCheck;
  onReviewed: () => void;
}

const DECISIONS = ["CONFIRM", "REJECT", "OVERRIDE", "REQUEST_MORE_EVIDENCE"] as const;

export function ReviewPanel({ inspectionId, check, onReviewed }: Props) {
  const [decision, setDecision] = useState<(typeof DECISIONS)[number]>("CONFIRM");
  const [finalStatus, setFinalStatus] = useState(check.status);
  const [comment, setComment] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [expanded, setExpanded] = useState(false);

  async function handleSubmit() {
    setSubmitting(true);
    try {
      await submitReview(inspectionId, check.id, decision, finalStatus, comment, reason);
      setExpanded(false);
      setComment("");
      setReason("");
      onReviewed();
    } finally {
      setSubmitting(false);
    }
  }

  if (!expanded) {
    return (
      <button className="secondary" style={{ marginTop: 8, fontSize: 12 }} onClick={() => setExpanded(true)}>
        {check.review_decisions.length > 0 ? "Add another review decision" : "Review this finding"}
      </button>
    );
  }

  return (
    <div style={{ marginTop: 10, borderTop: "1px solid var(--color-border)", paddingTop: 10 }}>
      <div className="form-row">
        <label>Decision</label>
        <select value={decision} onChange={(e) => setDecision(e.target.value as typeof decision)}>
          {DECISIONS.map((d) => (
            <option key={d} value={d}>{d.replaceAll("_", " ")}</option>
          ))}
        </select>
      </div>
      <div className="form-row">
        <label>Final status</label>
        <select value={finalStatus} onChange={(e) => setFinalStatus(e.target.value as typeof finalStatus)}>
          <option value="PASS">PASS</option>
          <option value="POTENTIAL_NON_COMPLIANCE">POTENTIAL_NON_COMPLIANCE</option>
          <option value="NEEDS_MANUAL_REVIEW">NEEDS_MANUAL_REVIEW</option>
          <option value="NOT_APPLICABLE">NOT_APPLICABLE</option>
          <option value="UNABLE_TO_VERIFY">UNABLE_TO_VERIFY</option>
        </select>
      </div>
      <div className="form-row">
        <label>Comment</label>
        <textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} />
      </div>
      <div className="form-row">
        <label>Reason (optional)</label>
        <input type="text" value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>
      <button onClick={handleSubmit} disabled={submitting}>
        {submitting ? "Submitting…" : "Submit review decision"}
      </button>
      <button className="secondary" style={{ marginLeft: 8 }} onClick={() => setExpanded(false)}>
        Cancel
      </button>
    </div>
  );
}
