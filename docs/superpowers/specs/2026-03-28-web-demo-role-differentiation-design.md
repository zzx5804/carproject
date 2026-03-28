# Web Demo Role-Differentiation Design

- **Date:** 2026-03-28
- **Author:** Hephaestus (autonomous agent)
- **Status:** Draft for review
- **Scope:** `cea-diagnosis.html`, `script.js`, backend output adapter templates (`backend/agents/output_adapter.py`, `backend/diagnosis_knowledge.py`)

---

## 1. Background & Objectives

Recent feedback surfaced that the web demo (WebSocket UI) does not surface role-based differences after running a diagnosis. Although the backend already emits role-specific HTML templates for certain scenarios, the UI largely renders them with identical framing. This creates three gaps:

1. **User perception:** Switching between roles (owner / technician / customer_service) changes almost nothing in the interface, so testers cannot validate adaptive messaging.
2. **Information prioritisation:** Rules, hypotheses, and confidence modules show identical structure despite each role needing different entry points or calls to action.
3. **Scenario coverage visibility:** Some scenarios lack templates for all roles; the demo silently falls back to owner text, masking missing content.

**Goal:** Ensure the demo clearly reflects role differentiation throughout the interaction while keeping backend behaviour stable (no new API contract). Solution must be achievable quickly (plan A) but leave an upgrade path to richer data contracts (plan B).

---

## 2. Current-State Findings

- The UI consists of a single HTML file (`cea-diagnosis.html`) with inline CSS and a supporting script (`script.js`). WebSocket messages include the selected `role`, but the UI only uses it when sending the `start` payload.
- Back-end output templates exist per scenario/role (`diagnosis_knowledge.OUTPUT_TEMPLATES`), yet not all scenarios define every role. The OutputAdapter falls back to the owner template silently when a role-specific template is missing.
- Message bus, reasoning chain, signal panels, and other elements do not adjust wording or emphasis by role.
- Scenario quick-select buttons are static; they always reflect owner-centric descriptions.

---

## 3. Requirements Summary (Plan A – UI Focused)

### 3.1 Role Context Surface

- Introduce a persistent **Role Context banner** under the role toggle showing:
  - Short descriptor of the selected role’s primary goal.
  - One sample symptom phrasing suited to that role.
  - Visual badge and colour accent unique per role (e.g., owner = blue, technician = green, customer service = purple).
- Refresh banner content whenever role changes and set the text area placeholder to the new sample.

### 3.2 Results Pane Differentiation

- Wrap the existing HTML returned by OutputAdapter in a `role-report` container that adds:
  - Role icon + label chip (e.g., “👩‍🔧 Technician View”).
  - Role-specific complementary components:
    - **Owner:** “自助排查” checklist (collapsible), hotline CTA.
    - **Technician:** “关键信号读值” quick links (pull from signals in UI), placeholder for OBD steps.
    - **Customer Service:** “通话话术” block quoting suggested language, highlight escalation criteria.
- Display a warning chip if the adapter reports that a role-specific template is missing (`payload.fallbackRole` to be injected by frontend when template HTML contains fallback marker).

### 3.3 Pipeline Visualisation Adjustments

- In reasoning steps (`addChain`) append `Role: <role>` tag for steps emitted after output generation.
- In rule/hypothesis lists highlight entries most relevant to the current role (owner = readability, technician = IDs/confidence, customer service = simplified text).
- Message bus entries referencing OutputAdapter should include the role name in the header chip.

### 3.4 Scenario & Signal Aids

- Update `SCENARIOS` map to hold role-specific example symptom text and guidance bullets.
- When switching role, update the quick scenario buttons’ tooltips to reflect how that role should interpret the scenario.
- Signals grid: for technician role, show raw code values; for owner/customer service, show plain-language labels.

### 3.5 Fallback Handling

- Detect missing templates by scanning returned HTML for a comment marker (e.g., `<!-- ROLE_FALLBACK: owner -->` appended by OutputAdapter when fallback occurs). Display a yellow banner prompting content authors to add the missing template.
- Log fallback event inside OutputAdapter so CLI/QA can spot the gap (`logger.info("Role template fallback", role=role, scenario=scenario)`).

### 3.6 Testing & Instrumentation

- Add lightweight Playwright smoke script (in follow-up implementation) verifying three role selections lead to distinct DOM variations (`data-role-variant` attributes).
- Enable console debug toggle in UI to print role-specific payloads for manual verification.

---

## 4. Upgrade Path (Plan B – Structured Output)

While out of scope for the immediate fix, document how to evolve:

1. Extend OutputAdapter to return JSON payload: `{ summary, actions[], talk_track[], metrics, escalation }`.
2. Update frontend to render dedicated components per role using the structured fields.
3. Ensure CLI/REST clients consume the same structure to maintain parity.

Documenting this path ensures the current UI-only work does not preclude future structured upgrades.

---

## 5. Implementation Checklist

| Area | Tasks |
|------|-------|
| Frontend | Role context banner, `role-report` wrapper, role-specific companion panels, scenario button metadata, message bus & reasoning tags |
| Backend | Optional: add fallback marker comment in templates; log fallback events |
| QA | Manual walkthrough for each role; confirm fallback banner appears when templates missing |
| Docs | Update README/AGENTS if role differentiation instructions needed |

---

## 6. Risks & Mitigations

- **Template absence:** Some scenarios still missing role HTML → fallback banner + log ensures visibility.
- **UI complexity creep:** Inline CSS may become unwieldy → scope to minimal CSS additions; note in future refactor plan.
- **WebSocket payload coupling:** Relies on existing message shapes; verify no backend change required aside from optional markers.

---

## 7. Acceptance Criteria

1. Selecting different roles alters contextual guidance before running diagnostics.
2. After pipeline completes, the output card displays role-specific framing and supporting panels.
3. Message bus / reasoning chain reflect the selected role in pertinent entries.
4. Missing role templates are explicitly flagged in UI and logs.
5. QA checklist (manual or automated) confirms DOM differences for each role.

---

## 8. Open Questions

- Do we need localisation adjustments per role (e.g., customer-service script tone)?
- Should the CLI mimic the same role banners for parity? (Out of current scope.)
- Any telemetry hooks desired to measure role usage frequency?

Pending answers do not block the initial implementation.

---

## 9. Timeline & Ownership

- **Implementation Window:** Target within current sprint (same week).
- **Owner:** Frontend adjustments by web demo maintainer; backend fallback logging by platform engineer.
- **Reviewers:** Product owner for UX acceptance, QA to validate role flows.
