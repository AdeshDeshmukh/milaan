// ═══════════════════════════════════════════════════════════════════════════
// Milaan Dashboard — Reactive Client Controller (Cream / Enterprise Theme)
// ═══════════════════════════════════════════════════════════════════════════

let currentRunId = null;
let activeTab = 'matches';

document.addEventListener('DOMContentLoaded', () => {
  refreshData();
});

async function refreshData() {
  await fetchSummary();
  if (activeTab === 'matches') fetchMatches();
  else if (activeTab === 'exceptions') fetchExceptions();
  else if (activeTab === 'approvals') fetchProposals();
  else if (activeTab === 'audit') fetchAuditTrail();
}

function switchTab(tabId) {
  activeTab = tabId;
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('section[id^="tab-"]').forEach(sec => sec.style.display = 'none');

  const targetTab = document.getElementById(`tab-${tabId}`);
  if (targetTab) targetTab.style.display = 'flex';

  const buttons = document.querySelectorAll('.tab-btn');
  if (tabId === 'matches') buttons[0].classList.add('active');
  else if (tabId === 'exceptions') buttons[1].classList.add('active');
  else if (tabId === 'approvals') buttons[2].classList.add('active');
  else if (tabId === 'audit') buttons[3].classList.add('active');
  else if (tabId === 'qa') buttons[4].classList.add('active');

  if (tabId === 'matches') fetchMatches();
  else if (tabId === 'exceptions') fetchExceptions();
  else if (tabId === 'approvals') fetchProposals();
  else if (tabId === 'audit') fetchAuditTrail();
}

// ── API: Summary & KPIs ───────────────────────────────────────────────────
async function fetchSummary() {
  try {
    const res = await fetch('/api/summary');
    const data = await res.json();
    currentRunId = data.run_id;

    document.getElementById('kpiMatchRate').innerText = `${data.overall_match_rate_pct}%`;
    document.getElementById('kpiMatchedSubtext').innerText = `${data.matched_records} / ${data.total_records} records matched`;
    document.getElementById('kpiFalseMatchRate').innerText = `${data.false_match_rate_pct.toFixed(2)}%`;
    document.getElementById('kpiExceptions').innerText = data.total_exceptions;
    document.getElementById('kpiResidueSubtext').innerText = `${data.unclassified_residue_count} residue sent to AI`;
    document.getElementById('kpiPendingApprovals').innerText = data.pending_proposals_count;

    const auditBadge = document.getElementById('auditBadge');
    const auditText = document.getElementById('auditBadgeText');
    if (data.audit_verified) {
      auditBadge.style.borderColor = 'var(--success-border)';
      auditBadge.style.color = 'var(--success-text)';
      auditBadge.style.background = 'var(--success-bg)';
      auditText.innerText = `Audit Chain Verified (${data.audit_event_count} events)`;
    } else {
      auditBadge.style.borderColor = 'var(--danger-border)';
      auditBadge.style.color = 'var(--danger-text)';
      auditBadge.style.background = 'var(--danger-bg)';
      auditText.innerText = `Audit Warning: Hash Mismatch`;
    }
  } catch (err) {
    console.error('Failed to load summary:', err);
  }
}

// ── API: 3-Way Matching Explorer ──────────────────────────────────────────
async function fetchMatches(tierFilter = '') {
  const tbody = document.getElementById('matchesTableBody');
  tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 2rem;">Loading matching records...</td></tr>';

  try {
    const url = tierFilter ? `/api/matches?tier=${tierFilter}` : '/api/matches';
    const res = await fetch(url);
    const data = await res.json();

    if (!data.matches || data.matches.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 2rem;">No matches found for selected criteria.</td></tr>';
      return;
    }

    tbody.innerHTML = data.matches.map(m => {
      const tierBadgeClass = `badge-${m.tier.toLowerCase()}`;
      const reasonBadges = m.reason_codes.map(rc => `<span class="badge" style="background: var(--bg-subtle); color: var(--text-muted); border: 1px solid var(--border-card); margin-right: 4px;">${rc}</span>`).join('');
      
      return `
        <tr>
          <td><span class="badge ${tierBadgeClass}">${m.tier}</span></td>
          <td><strong style="color: var(--success); font-weight: 700;">${(m.confidence_score * 100).toFixed(0)}%</strong></td>
          <td>
            <div style="font-weight: 600; color: var(--text-main);">${m.left_record.source}</div>
            <div style="font-size: 0.76rem; color: var(--text-dim); font-family: monospace;">${m.left_record.external_id} · <span style="color: var(--text-main); font-weight: 600;">${m.left_record.amount}</span></div>
          </td>
          <td>
            <div style="font-weight: 600; color: var(--text-main);">${m.right_record.source}</div>
            <div style="font-size: 0.76rem; color: var(--text-dim); font-family: monospace;">${m.right_record.external_id} · <span style="color: var(--text-main); font-weight: 600;">${m.right_record.amount}</span></div>
          </td>
          <td>${reasonBadges}</td>
          <td><span style="font-weight: 700; color: ${m.amount_delta === '₹0.00' ? 'var(--success)' : 'var(--warning)'};">${m.amount_delta}</span></td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="color: var(--danger);">Error loading matches: ${err.message}</td></tr>`;
  }
}

function filterTier(tier) {
  fetchMatches(tier);
}

// ── API: Exceptions & Grounded Explanations ────────────────────────────────
async function fetchExceptions() {
  const tbody = document.getElementById('exceptionsTableBody');
  tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-dim); padding: 2rem;">Loading exceptions...</td></tr>';

  try {
    const res = await fetch('/api/exceptions');
    const data = await res.json();

    if (!data.exceptions || data.exceptions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-dim); padding: 2rem;">No exceptions logged for this run.</td></tr>';
      return;
    }

    tbody.innerHTML = data.exceptions.map((exc) => {
      const guardBadge = exc.citation_valid
        ? '<span class="badge" style="background: var(--success-bg); color: var(--success-text); border: 1px solid var(--success-border);">🛡️ Citation Guard Valid</span>'
        : '<span class="badge" style="background: var(--danger-bg); color: var(--danger-text); border: 1px solid var(--danger-border);">⚠️ Hallucination Flagged</span>';

      return `
        <tr>
          <td><strong style="color: var(--accent-warm); font-weight: 700;">${exc.category}</strong></td>
          <td><span class="badge" style="background: var(--bg-subtle); border: 1px solid var(--border-card); color: var(--text-muted);">${exc.source}</span></td>
          <td><code style="font-size: 0.8rem; background: var(--bg-subtle); padding: 2px 6px; border-radius: 4px;">${exc.external_id}</code></td>
          <td><strong style="color: var(--text-main);">${exc.amount}</strong></td>
          <td><span style="color: var(--indigo); font-weight: 600;">${exc.recommended_action}</span></td>
          <td>${guardBadge}</td>
          <td>
            <button class="btn btn-secondary" style="padding: 0.25rem 0.6rem; font-size: 0.75rem;" onclick='openExplanationModal(${JSON.stringify(exc)})'>
              Inspect Root Cause
            </button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="color: var(--danger);">Error loading exceptions: ${err.message}</td></tr>`;
  }
}

function openExplanationModal(exc) {
  const modal = document.getElementById('explanationModal');
  const title = document.getElementById('modalTitle');
  const body = document.getElementById('modalBody');

  title.innerText = `Exception Analysis: ${exc.category}`;
  const expl = exc.grounded_explanation || {};

  body.innerHTML = `
    <div style="background: var(--bg-subtle); padding: 0.95rem; border-radius: 8px; border: 1px solid var(--border-card);">
      <div style="font-size: 0.72rem; color: var(--text-dim); text-transform: uppercase; font-weight: 700; letter-spacing: 0.4px;">Transaction Context</div>
      <div style="font-weight: 700; margin-top: 4px; color: var(--text-main);">Record ID: <code style="background: #ffffff; padding: 2px 6px; border-radius: 4px; border: 1px solid var(--border-card);">${exc.external_id}</code> (${exc.amount})</div>
      <div style="color: var(--text-muted); font-size: 0.84rem; margin-top: 4px;">${exc.description}</div>
    </div>

    <div style="background: var(--accent-warm-bg); padding: 0.95rem; border-radius: 8px; border: 1px solid var(--accent-warm-border);">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="font-size: 0.72rem; color: var(--accent-warm); text-transform: uppercase; font-weight: 700; letter-spacing: 0.4px;">Grounded Controller Analysis</span>
        <span class="badge" style="background: var(--success-bg); color: var(--success-text); border: 1px solid var(--success-border);">Citation Verified</span>
      </div>
      <p style="margin-top: 0.45rem; font-size: 0.88rem; color: var(--text-main); font-weight: 500;">${expl.summary || 'Standard exception pattern identified.'}</p>
      <div style="margin-top: 0.45rem; font-size: 0.8rem; color: var(--text-dim);">${expl.root_cause_analysis || ''}</div>
    </div>

    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid var(--border-light);">
      <span style="font-size: 0.82rem; color: var(--text-muted); font-weight: 600;">Recommended Next Action:</span>
      <span class="badge badge-t0" style="font-size: 0.8rem; padding: 0.25rem 0.6rem;">${exc.recommended_action}</span>
    </div>
  `;

  modal.classList.add('open');
}

function closeModal() {
  document.getElementById('explanationModal').classList.remove('open');
}

// ── API: Human Approval Queue ─────────────────────────────────────────────
async function fetchProposals() {
  const tbody = document.getElementById('proposalsTableBody');
  tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 2rem;">Loading approval queue...</td></tr>';

  try {
    const res = await fetch('/api/proposals');
    const data = await res.json();

    if (!data.proposals || data.proposals.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 2rem;">No pending action proposals.</td></tr>';
      return;
    }

    tbody.innerHTML = data.proposals.map(p => {
      const isPending = p.status.toLowerCase() === 'pending';
      const statusBadge = `<span class="badge badge-${p.status.toLowerCase()}">${p.status}</span>`;

      const actionButtons = isPending ? `
        <div style="display: flex; gap: 0.35rem;">
          <button class="btn btn-primary" style="padding: 0.3rem 0.65rem; font-size: 0.76rem;" onclick="reviewProposal('${p.proposal_id}', 'approve')">Approve & Post</button>
          <button class="btn btn-secondary" style="padding: 0.3rem 0.65rem; font-size: 0.76rem; color: var(--danger);" onclick="reviewProposal('${p.proposal_id}', 'reject')">Reject</button>
        </div>
      ` : '<span style="color: var(--text-dim); font-size: 0.76rem; font-weight: 500;">Action Finalized</span>';

      return `
        <tr>
          <td><code style="font-size: 0.8rem; background: var(--bg-subtle); padding: 2px 6px; border-radius: 4px;">${p.proposal_id}</code></td>
          <td><span class="badge" style="background: var(--indigo-bg); color: var(--indigo); border: 1px solid var(--indigo-border);">${p.action_type}</span></td>
          <td>${statusBadge}</td>
          <td>
            <div style="font-weight: 500;">${p.summary}</div>
            ${p.adjust_amount && p.adjust_amount !== '₹0.00' ? `<div style="font-size: 0.75rem; color: var(--accent-warm); font-weight: 600; margin-top: 2px;">Adjustment Amount: ${p.adjust_amount}</div>` : ''}
          </td>
          <td><span style="color: var(--text-dim); font-size: 0.8rem;">${p.reviewed_by || 'Awaiting Review'}</span></td>
          <td>${actionButtons}</td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="color: var(--danger);">Error loading proposals: ${err.message}</td></tr>`;
  }
}

async function reviewProposal(proposalId, action) {
  try {
    const res = await fetch(`/api/proposals/${proposalId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: action, reviewer: 'controller@merchant.com' })
    });
    if (res.ok) {
      await fetchSummary();
      await fetchProposals();
    }
  } catch (err) {
    alert(`Error reviewing proposal: ${err.message}`);
  }
}

async function bulkApprove() {
  try {
    const res = await fetch('/api/proposals/bulk-approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'approve', reviewer: 'controller@merchant.com' })
    });
    const data = await res.json();
    alert(data.message);
    await refreshData();
  } catch (err) {
    alert(`Error in bulk approval: ${err.message}`);
  }
}

// ── API: Cryptographic Audit Trail ────────────────────────────────────────
async function fetchAuditTrail() {
  const tbody = document.getElementById('auditTableBody');
  tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 2rem;">Loading audit events...</td></tr>';

  try {
    const res = await fetch('/api/audit?limit=25');
    const data = await res.json();

    if (!data.events || data.events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 2rem;">No audit events recorded yet.</td></tr>';
      return;
    }

    tbody.innerHTML = data.events.reverse().map(ev => {
      const dateStr = new Date(ev.timestamp * 1000).toLocaleString();
      const currHash = ev.event_hash ? ev.event_hash.substring(0, 14) + '...' : 'genesis';
      const prevHash = ev.prev_hash ? ev.prev_hash.substring(0, 14) + '...' : '00000000000000...';

      return `
        <tr>
          <td><span style="font-size: 0.8rem; color: var(--text-dim);">${dateStr}</span></td>
          <td><span class="badge" style="background: var(--bg-subtle); border: 1px solid var(--border-card); color: var(--text-muted);">${ev.event_type}</span></td>
          <td><code style="font-size: 0.8rem;">${ev.run_id || '--'}</code></td>
          <td><code style="color: var(--success); font-weight: 600; font-size: 0.8rem;">${currHash}</code></td>
          <td><code style="color: var(--text-dim); font-size: 0.8rem;">${prevHash}</code></td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="color: var(--danger);">Error loading audit trail: ${err.message}</td></tr>`;
  }
}

async function verifyAuditChain() {
  try {
    const res = await fetch('/api/audit');
    const data = await res.json();
    alert(data.verified ? `✅ Integrity Verified: ${data.message}` : `❌ Tampering Detected: ${data.message}`);
  } catch (err) {
    alert(`Audit verification failed: ${err.message}`);
  }
}

// ── API: AI Controller Q&A ────────────────────────────────────────────────
async function sendChatQuery() {
  const input = document.getElementById('chatInput');
  const query = input.value.trim();
  if (!query) return;

  const chatHistory = document.getElementById('chatHistory');
  
  // Add User message
  const userDiv = document.createElement('div');
  userDiv.className = 'chat-msg msg-user';
  userDiv.innerText = query;
  chatHistory.appendChild(userDiv);
  input.value = '';
  chatHistory.scrollTop = chatHistory.scrollHeight;

  // Assistant typing placeholder
  const botDiv = document.createElement('div');
  botDiv.className = 'chat-msg msg-assistant';
  botDiv.innerText = 'Analyzing verified reconciliation records...';
  chatHistory.appendChild(botDiv);

  try {
    const res = await fetch('/api/qa', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query, run_id: currentRunId })
    });
    const data = await res.json();
    botDiv.innerText = data.answer;
  } catch (err) {
    botDiv.innerText = `Error generating response: ${err.message}`;
  }

  chatHistory.scrollTop = chatHistory.scrollHeight;
}

function sendQuickPrompt(promptText) {
  document.getElementById('chatInput').value = promptText;
  sendChatQuery();
}

async function triggerReconRun() {
  try {
    const btn = document.getElementById('btnRunRecon');
    btn.disabled = true;
    btn.innerText = 'Reconciling...';

    const res = await fetch('/api/reconcile/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ records: 500, seed: Math.floor(Math.random() * 1000) })
    });
    const data = await res.json();
    alert(`✨ ${data.message}! (Run ID: ${data.run_id})`);
    await refreshData();
  } catch (err) {
    alert(`Reconciliation trigger failed: ${err.message}`);
  } finally {
    const btn = document.getElementById('btnRunRecon');
    btn.disabled = false;
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg> Run Reconciliation`;
  }
}
