# Web Demo Role Differentiation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the role-differentiated web demo defined in `docs/superpowers/specs/2026-03-28-web-demo-role-differentiation-design.md`, covering UI updates, backend fallback signalling, and smoke testing.

**Architecture:** Keep the single-page demo structure. Extend `script.js` with role metadata, UI rendering helpers, and fallback detection while inserting a role context section in `cea-diagnosis.html`. On the backend, add explicit fallback logging/comment markers in `OutputAdapter`. Introduce a minimal Playwright smoke test to assert DOM variants.

**Tech Stack:** HTML, vanilla JavaScript, inline CSS, FastAPI (Python), pytest, Playwright (Node.js)

---

### File Map

| Path | Responsibility |
|------|----------------|
| `cea-diagnosis.html` | HTML structure & inline styles for the demo UI |
| `script.js` | Frontend logic controlling role switches, rendering, WebSocket handling |
| `backend/agents/output_adapter.py` | Generates role-specific output and handles fallbacks |
| `backend/diagnosis_knowledge.py` | Contains output templates (ensure marker comments where needed) |
| `tests/e2e/role-variants.spec.ts` | New Playwright smoke test validating DOM differences |
| `playwright.config.ts` | Playwright configuration (new) |
| `package.json` / `package-lock.json` | Node dependencies for Playwright (new, minimal) |

---

### Task 1: Inject Role Context Banner in HTML & Styles

**Files:**
- Modify: `cea-diagnosis.html`

- [ ] **Step 1: Add role-context container under role selector**

Insert the snippet directly below the existing role toggle button group:

```html
      <div id="roleContext" class="role-context owner" data-role="owner">
        <div class="role-chip">👤 车主视角</div>
        <div class="role-summary">重点关注是否能自助快速恢复上电。</div>
        <div class="role-example">示例输入："踩刹车按启动按钮，车辆无法上电"</div>
      </div>
```

- [ ] **Step 2: Extend inline styles for role-context variants**

Add the styles near existing CSS definitions:

```css
  .role-context{margin-top:12px;padding:12px;border-radius:10px;background:var(--panel-bg);border:1px solid var(--panel-border);box-shadow:var(--panel-shadow);transition:background .2s ease, border .2s ease}
  .role-context .role-chip{display:inline-flex;align-items:center;font-weight:600;font-size:12px;padding:4px 10px;border-radius:999px;background:rgba(59,130,246,.12);color:#1d4ed8;margin-bottom:6px}
  .role-context.owner{background:rgba(59,130,246,.08);border-color:rgba(59,130,246,.25)}
  .role-context.technician{background:rgba(34,197,94,.08);border-color:rgba(34,197,94,.25)}
  .role-context.technician .role-chip{background:rgba(34,197,94,.12);color:#047857}
  .role-context.customer_service{background:rgba(168,85,247,.08);border-color:rgba(168,85,247,.25)}
  .role-context.customer_service .role-chip{background:rgba(168,85,247,.12);color:#6b21a8}
  .role-context .role-summary{font-size:12px;color:var(--tx2)}
  .role-context .role-example{margin-top:4px;font-size:11px;color:var(--tx3)}
```

- [ ] **Step 3: Manual smoke check**

Run a local HTTP server and open the page:

```bash
python -m http.server 8000
```

Navigate to `http://localhost:8000/cea-diagnosis.html` and confirm the new banner appears below the role buttons with owner styling.

- [ ] **Step 4: Commit**

```bash
git add cea-diagnosis.html
git commit -m "feat: add role context banner to web demo"
```

---

### Task 2: Embed Role Metadata & Dynamic Banner Updates in script.js

**Files:**
- Modify: `script.js`

- [ ] **Step 1: Define role metadata constant**

Place near the top (after existing constants):

```javascript
const ROLE_METADATA={
  owner:{
    chip:"👤 车主视角",
    summary:"重点关注是否能自助快速恢复上电。",
    example:"踩刹车按启动按钮，车辆无法上电",
    className:"owner"
  },
  technician:{
    chip:"👩‍🔧 技师视角",
    summary:"排查信号与规则链路，定位根因并记录工单。",
    example:"踩刹车按启动键仍然 0:Off，KeyValidSt=INVALID",
    className:"technician"
  },
  customer_service:{
    chip:"🎧 客服视角",
    summary:"指导车主复现并判断是否需要升级工单。",
    example:"客户反馈提示钥匙未找到，如何指导？",
    className:"customer_service"
  }
};
```

- [ ] **Step 2: Implement `renderRoleContext()` helper**

Add function before existing helpers:

```javascript
function renderRoleContext(r){
  const meta=ROLE_METADATA[r]||ROLE_METADATA.owner;
  const container=document.getElementById('roleContext');
  if(!container)return;
  container.className=`role-context ${meta.className}`;
  container.dataset.role=r;
  container.innerHTML=`<div class="role-chip">${meta.chip}</div><div class="role-summary">${meta.summary}</div><div class="role-example">示例输入："${meta.example}"</div>`;
  const symptomInput=document.getElementById('symptomInput');
  if(symptomInput && !symptomInput.value){
    symptomInput.placeholder=meta.example;
  }
}
```

- [ ] **Step 3: Invoke helper on role change & page load**

Extend `setRole` and `window.addEventListener('load', ...)`:

```javascript
function setRole(r){
  role=r;
  document.querySelectorAll('.rbtn').forEach(b=>b.classList.remove('active'));
  document.getElementById({owner:'btn-owner',technician:'btn-tech',customer_service:'btn-cs'}[r]).classList.add('active');
  renderRoleContext(r);
  loadScenario(scenarioKey,true);
}

window.addEventListener('load',()=>{
  loadScenario('ble_auth');
  renderRoleContext(role);
  connectWebSocket();
  // existing drawWires calls remain
});
```

Update `loadScenario` signature to accept `preserveInput` flag and only overwrite the textbox when appropriate:

```javascript
function loadScenario(k,preserveInput=false){
  scenarioKey=k;
  const sc=SCENARIOS[k];
  const symptomEl=document.getElementById('symptomInput');
  if(!preserveInput && symptomEl){
    symptomEl.value=sc.symptom[role]||sc.symptom.owner;
  }
  // existing signal population stays
}
```

- [ ] **Step 4: Run lint/manual check**

Reload the browser page and switch roles to confirm the banner updates and the default symptom text changes per role.

- [ ] **Step 5: Commit**

```bash
git add script.js
git commit -m "feat: add role metadata and dynamic context banner"
```

---

### Task 3: Expand Scenario Metadata & Signal Presentation

**Files:**
- Modify: `script.js`

- [ ] **Step 1: Update `SCENARIOS` structure with per-role symptom**

For each scenario entry, wrap the `symptom` string into an object keyed by role. Example:

```javascript
const SCENARIOS={
  ble_auth:{
    symptom:{
      owner:'踩刹车按启动按钮，车辆无法上电，屏幕弹出"钥匙未找到"',
      technician:'踩刹车按启动仍 St1:Off，KeyValidSt=INVALID，BLE_ErrorCode=0x05',
      customer_service:'客户反馈提示钥匙未找到，指导步骤是什么？'
    },
    // existing signals...
  },
  // repeat for other scenarios
};
```

- [ ] **Step 2: Add tooltip text for scenario buttons**

Extend `loadScenario` to set `title` attribute on each scenario button using role-specific hints:

```javascript
function refreshScenarioTooltips(){
  Object.entries(SCENARIOS).forEach(([key,sc])=>{
    const btn=document.querySelector(`[data-scenario="${key}"]`);
    if(btn && sc.tooltips){
      btn.title=sc.tooltips[role]||sc.tooltips.owner||'';
    }
  });
}
```

Call `refreshScenarioTooltips()` inside `setRole` after `renderRoleContext` and at the end of `loadScenario`.

Ensure each scenario definition has a `tooltips` object matching roles.

- [ ] **Step 3: Adjust signal grid for technician role**

When iterating through `sc.signals`, branch by role:

```javascript
for(const [id,[cls,val]] of Object.entries(sc.signals)){
  const el=document.getElementById(id);
  if(!el)continue;
  const displayVal=role==='technician'?`${val}`:val.split(' ')[0];
  el.className='sig-val '+cls;
  el.textContent=displayVal;
}
```

- [ ] **Step 4: Smoke test manually**

Reload UI, select technician role, hover scenario shortcuts, confirm tooltips change, signals show full values.

- [ ] **Step 5: Commit**

```bash
git add script.js
git commit -m "feat: enrich scenarios with role metadata and tooltips"
```

---

### Task 4: Role-Specific Output Wrapper & Fallback Banner

**Files:**
- Modify: `script.js`
- Modify: `cea-diagnosis.html`

- [ ] **Step 1: Add container markup for role report and fallback hint**

Within the output section of `cea-diagnosis.html`, wrap the existing `outputBox` and add a placeholder for extra panels:

```html
        <div id="roleOutputShell">
          <div id="outputHeader"></div>
          <div id="outputBox"></div>
          <div id="roleCompanion"></div>
          <div id="fallbackHint" class="fallback-hint" hidden>⚠️ 当前角色缺少专属模板，已呈现车主版本。</div>
        </div>
```

Add styles near CSS section:

```css
  #roleOutputShell{margin-top:12px;border:1px solid rgba(15,23,42,.12);border-radius:12px;overflow:hidden;background:rgba(15,23,42,.03)}
  #outputHeader{padding:10px 14px;background:rgba(15,23,42,.06);font-size:12px;font-weight:600;color:var(--tx2)}
  #roleCompanion{padding:12px;border-top:1px solid rgba(15,23,42,.08);display:none}
  .fallback-hint{padding:10px 14px;font-size:11px;color:#92400e;background:rgba(251,191,36,.25);border-top:1px solid rgba(217,119,6,.4)}
```

- [ ] **Step 2: Enhance `updateOutputMessage` in `script.js`**

Replace the body with:

```javascript
function updateOutputMessage(msg){
  const shell=document.getElementById('roleOutputShell');
  const header=document.getElementById('outputHeader');
  const companion=document.getElementById('roleCompanion');
  const fallback=document.getElementById('fallbackHint');
  const ob=document.getElementById('outputBox');
  if(!shell||!header||!companion||!fallback||!ob)return;

  const meta=ROLE_METADATA[role]||ROLE_METADATA.owner;
  header.textContent=`${meta.chip} · 输出报告`;

  const text=(msg.output&&msg.output.text)||msg.html||'';
  ob.innerHTML=text||'<div style="font-size:10px;color:var(--tx3);text-align:center;padding:10px 0">无输出</div>';
  ob.classList.add('vis');

  const fallbackRole=(msg.output&&msg.output.fallback_role)||detectFallbackRole(text);
  fallback.hidden=!fallbackRole;
  if(fallbackRole){
    fallback.textContent=`⚠️ 当前角色缺少专属模板，已呈现 ${fallbackRole} 版本。`;
  }

  companion.style.display='block';
  companion.innerHTML=renderRoleCompanion(meta);

  const hint=msg.escalation||(msg.output&&msg.output.escalation);
  const esc=document.getElementById('escalationHint');
  if(esc){
    if(hint){
      esc.textContent='⚠️ '+hint;
      esc.style.display='block';
      esc.classList.add('vis');
    }else{
      esc.style.display='none';
      esc.classList.remove('vis');
    }
  }
}

function detectFallbackRole(html){
  const match=String(html).match(/<!--\s*ROLE_FALLBACK:([a-z_]+)\s*-->/i);
  return match?match[1]:null;
}

function renderRoleCompanion(meta){
  if(meta.className==='owner'){
    return `<div class="companion-block"><h4>自助排查步骤</h4><ol><li>重新开关蓝牙并靠近车辆</li><li>确认 App 权限已开启</li><li>必要时使用 NFC 备用钥匙</li></ol><p class="companion-cta">☎️ 客服热线：400-XXX-XXXX</p></div>`;
  }
  if(meta.className==='technician'){
    return `<div class="companion-block"><h4>技师快速检查</h4><ul><li>读取 KeyValidSt / Flag_BLE 原始值</li><li>记录 BLE_ErrorCode 并同步工单</li><li>检查 R-KEY001/R-BLE001 规则触发情况</li></ul></div>`;
  }
  return `<div class="companion-block"><h4>客服话术建议</h4><p>"您好，请帮我确认手机蓝牙是否开启并靠近车辆。若仍提示钥匙未找到，我这边可以升级给技术同事进一步协助。"</p></div>`;
}
```

Add companion styles inside HTML `<style>` block:

```css
  .companion-block h4{margin:0 0 6px 0;font-size:12px;color:var(--tx2)}
  .companion-block ol,.companion-block ul{margin:0;padding-left:18px;font-size:11px;color:var(--tx2)}
  .companion-cta{margin-top:8px;font-size:11px;color:#b91c1c;font-weight:600}
```

- [ ] **Step 3: Manual verification**

Run the demo, execute a diagnosis for each role, and confirm header text, companion panel, and fallback banner when forcing fallback (temporarily comment out technician template in backend to test).

- [ ] **Step 4: Commit**

```bash
git add script.js cea-diagnosis.html
git commit -m "feat: render role-specific output wrapper with fallback hint"
```

---

### Task 5: Role Tags in Reasoning & Message Bus

**Files:**
- Modify: `script.js`

- [ ] **Step 1: Update `addChain` to append role tag**

Inside `addChain`, adjust the title composition:

```javascript
const roleTag=`<span class="role-tag">${ROLE_METADATA[role].chip}</span>`;
el.innerHTML=`<div class="cs-line"><div class="cs-dot">${i+1}</div><div class="cs-conn"></div></div><div class="cs-body"><div class="cs-title">[S${i+1}] ${step.title} ${roleTag} ${tag}</div><div class="cs-content">${step.body}${dh}</div></div>`;
```

Add CSS:

```css
  .role-tag{display:inline-flex;align-items:center;font-size:10px;padding:2px 6px;border-radius:999px;background:rgba(59,130,246,.18);color:#1d4ed8;margin-left:4px}
```

- [ ] **Step 2: Show role in message bus entries when target is output agent**

Modify `pushMsg` to inject the role chip:

```javascript
const roleChip=to==='Output'?`<span class="bus-role">${ROLE_METADATA[role].chip}</span>`:'';
el.innerHTML=`<div class="bus-head"><span class="bus-from ${AGENT_CLS[from]||''}">${AGENT_NAMES[from]||from}</span><span class="bus-arrow">→</span><span class="bus-to">${AGENT_NAMES[to]||to}</span>${roleChip}</div><div class="bus-content">${content}</div>`;
```

Add style:

```css
  .bus-role{margin-left:6px;font-size:10px;color:#1d4ed8;background:rgba(37,99,235,.12);padding:2px 6px;border-radius:999px}
```

- [ ] **Step 3: Update CSS for technician/customer service chips**

Ensure `.role-tag` and `.bus-role` change color based on role by toggling class on root container (set in `renderRoleContext`):

```javascript
document.body.dataset.role=role;
```

Add CSS selectors:

```css
  body[data-role="technician"] .role-tag,body[data-role="technician"] .bus-role{background:rgba(34,197,94,.18);color:#047857}
  body[data-role="customer_service"] .role-tag,body[data-role="customer_service"] .bus-role{background:rgba(168,85,247,.18);color:#6b21a8}
```

- [ ] **Step 4: Manual verification**

Reload UI, run diagnosis, inspect reasoning chain & message bus for role chips.

- [ ] **Step 5: Commit**

```bash
git add script.js cea-diagnosis.html
git commit -m "feat: tag reasoning and bus entries with current role"
```

---

### Task 6: Backend Fallback Marker & Logging

**Files:**
- Modify: `backend/agents/output_adapter.py`
- Modify: `backend/diagnosis_knowledge.py`
- Modify: `tests/test_diagnosis_knowledge.py` (add assertion)

- [ ] **Step 1: Emit fallback marker comment and return structured payload**

In `_get_output`, append marker when fallback is used:

```python
        if scenario in OUTPUT_TEMPLATES and "owner" in OUTPUT_TEMPLATES[scenario]:
            owner_html = OUTPUT_TEMPLATES[scenario]["owner"]
            return f"<!-- ROLE_FALLBACK:owner -->\n{owner_html}"
```

- [ ] **Step 2: Log fallback role inside `process`**

After computing `output_html`, detect fallback:

```python
        fallback_role = None
        if "<!-- ROLE_FALLBACK:" in output_html:
            fallback_role = output_html.split("ROLE_FALLBACK:", 1)[1].split("-->", 1)[0].strip()
            logger.info(
                "OutputAdapter fallback to role template", scenario=scenario, role=role, fallback_role=fallback_role
            )
```

Include `fallback_role` in the message payload:

```python
        await self.send({
            "type": "output",
            "html": output_html,
            "escalation": escalation,
            "fallback_role": fallback_role
        })
```

- [ ] **Step 3: Ensure templates carry explicit comments**

For scenarios missing technician/customer_service entries, add explicit HTML comments noting pending work (e.g., inside `diagnosis_knowledge.OUTPUT_TEMPLATES` so fallback detection is accurate). Example for `key_timeout` fallback:

```python
        "customer_service": "<!-- ROLE_TEMPLATE:customer_service -->\n<div class=...>...",
```

- [ ] **Step 4: Add unit test for fallback marker**

In `tests/test_diagnosis_knowledge.py`, add:

```python
def test_output_adapter_fallback_marker(monkeypatch):
    from backend.agents.output_adapter import OutputAdapterAgent
    from backend.models import DiagnosisContext, Role

    agent = OutputAdapterAgent()
    ctx = DiagnosisContext(symptom="unknown", role=Role.CUSTOMER_SERVICE, signals={}, dtc_codes=[])

    async def run():
        result = await agent.process(ctx)
        assert "ROLE_FALLBACK" in result.output_html

    asyncio.run(run())
```

- [ ] **Step 5: Run tests**

```bash
cd backend
python -m pytest tests/test_diagnosis_knowledge.py -k fallback -vv
```

- [ ] **Step 6: Commit**

```bash
git add backend/agents/output_adapter.py backend/diagnosis_knowledge.py backend/tests/test_diagnosis_knowledge.py
git commit -m "feat: log role fallback and expose marker to frontend"
```

---

### Task 7: Introduce Playwright Smoke Test Suite

**Files:**
- Create: `package.json`, `package-lock.json`
- Create: `playwright.config.ts`
- Create: `tests/e2e/role-variants.spec.ts`

- [ ] **Step 1: Initialize Node project with Playwright**

```bash
npm init -y
npm install --save-dev @playwright/test
```

- [ ] **Step 2: Add Playwright config**

Create `playwright.config.ts`:

```ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: 'tests/e2e',
  use: {
    baseURL: 'http://localhost:8000',
    headless: true
  }
});
```

- [ ] **Step 3: Write smoke test**

Create `tests/e2e/role-variants.spec.ts`:

```ts
import { test, expect } from '@playwright/test';

test.beforeAll(async () => {
  // assumes python -m http.server 8000 is running
});

test('role variants render distinct DOM markers', async ({ page }) => {
  await page.goto('/cea-diagnosis.html');

  const getRoleVariant = async () => page.locator('#roleContext').getAttribute('data-role');

  await expect(await getRoleVariant()).toBe('owner');

  await page.click('#btn-tech');
  await expect(await getRoleVariant()).toBe('technician');

  await page.click('#btn-cs');
  await expect(await getRoleVariant()).toBe('customer_service');

  await page.click('#goBtn');
  await page.waitForSelector('#roleOutputShell .companion-block');
  const header = await page.locator('#outputHeader').innerText();
  expect(header).toContain('客服视角');
});
```

- [ ] **Step 4: Document script in package.json**

Add to `package.json` scripts:

```json
  "scripts": {
    "test:e2e": "playwright test"
  }
```

- [ ] **Step 5: Run Playwright test**

```bash
python -m http.server 8000 &
SERVER_PID=$!
npx playwright test tests/e2e/role-variants.spec.ts --headed
kill $SERVER_PID
```

- [ ] **Step 6: Commit**

```bash
git add package.json package-lock.json playwright.config.ts tests/e2e/role-variants.spec.ts
git commit -m "test: add role variant smoke test with Playwright"
```

---

### Task 8: Update Documentation

**Files:**
- Modify: `docs/TECHNICAL_DESIGN.md`

- [ ] **Step 1: Add subsection summarizing role differentiation**

Append under “WebSocket Communication” or relevant UX section:

```markdown
### Role-Adaptive Frontend Behaviour

- Role selection now renders a context banner and adjusts scenario presets.
- Output panel surfaces role chips, support panels, and fallback warnings when backend templates are missing.
- Message bus and reasoning chain visually tag entries with the active role for clarity during demos.
```

- [ ] **Step 2: Commit**

```bash
git add docs/TECHNICAL_DESIGN.md
git commit -m "docs: record role-differentiated demo behaviour"
```

---

## Self-Review

- **Spec coverage:** Plan addresses role context, result differentiation, pipeline tagging, scenario/signal adjustments, backend fallback markers, Playwright smoke tests, and documentation updates requested in the spec.
- **Placeholder scan:** No TODO/TBD placeholders; each step contains concrete instructions, code snippets, and commands.
- **Type consistency:** Role keys (`owner`, `technician`, `customer_service`) remain consistent across constants, DOM attributes, and tests.
