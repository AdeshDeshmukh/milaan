// ═══════════════════════════════════════════════════════════════════════════
// Milaan Dashboard — Reactive Client Controller
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

  // Highlight active button
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
      auditBadge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
      auditBadge.style.color = '#34d399';
      auditText.innerText = `Audit Chain Verified (${data.audit_event_count} events)`;
    } else {
      auditBadge.style.borderColor = 'rgba(239, 68, 68, 0.3)';
      auditBadge.style.color = '#f87171';
      auditText.innerText = `Audit Warning: Hash Mismatch`;
    }
  } catch (err) {
    console.error('Failed to load summary:', err);
  }
}

// ── API: 3-Way Matching Explorer ──────────────────────────────────────────
async function fetchMatches(tierFilter = '') {
  const tbody = document.getElementById('matchesTableBody');
  tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-dim);">Loading matching records...</td></tr>';

  try {
    const url = tierFilter ? `/api/matches?tier=${tierFilter}` : '/api/matches';
    const res = await fetch(url);
    const data = await res.json();

    if (!data.matches || data.matches.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-dim);">No matches found for selected criteria.</td></tr>';
      return;
    }

    tbody.innerHTML = data.matches.map(m => {
      const tierBadgeClass = `badge-${m.tier.toLowerCase()}`;
      const reasonBadges = m.reason_codes.map(rc => `<span class="badge" style="background: rgba(255,255,255,0.06); margin-right: 4px;">${rc}</span>`).join('');
      
      return `
        <tr>
          <td><span class="badge ${tierBadgeClass}">${m.tier}</span></td>
          <td><strong style="color: #34d399;">${(m.confidence_score * 100).toFixed(0)}%</strong></td>
          <td>
            <div style="font-weight: 600;">${m.left_record.source}</div>
            <div style="font-size: 0.75rem; color: var(--text-dim);">${m.left_record.external_id} · ${m.left_record.amount}</div>
          </td>
          <td>
            <div style="font-weight: 600;">${m.right_record.source}</div>
            <div style="font-size: 0.75rem; color: var(--text-dim);">${m.right_record.external_id} · ${m.right_record.amount}</div>
          </td>
          <td>${reasonBadges}</td>
          <td><span style="color: ${m.amount_delta === '₹0.00' ? '#34d399' : '#fbbf24'};">${m.amount_delta}</span></td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="color: #f87171;">Error loading matches: ${err.message}</td></tr>`;
  }
}

function filterTier(tier) {
  fetchMatches(tier);
}

// ── API: Exceptions & Grounded Explanations ────────────────────────────────
async function fetchExceptions() {
  const tbody = document.getElementById('exceptionsTableBody');
  tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-dim);">Loading exceptions...</td></tr>';

  try {
    const res = await fetch('/api/exceptions');
    const data = await res.json();

    if (!data.exceptions || data.exceptions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-dim);">No exceptions logged for this run.</td></tr>';
      return;
    }

    tbody.innerHTML = data.exceptions.map((exc, index) => {
      const guardBadge = exc.citation_valid
        ? '<span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399;">🛡️ Citation Guard Valid</span>'
        : '<span class="badge" style="background: rgba(239, 68, 68, 0.15); color: #f87171;">⚠️ Hallucination Flagged</span>';

      return `
        <tr>
          <td><strong style="color: #f59e0b;">${exc.category}</strong></td>
          <td><span class="badge" style="background: rgba(255,255,255,0.06);">${exc.source}</span></td>
          <td><code>${exc.external_id}</code></td>
          <td><strong style="color: #34d399;">${exc.amount}</strong></td>
          <td><span style="color: #818cf8; font-weight: 600;">${exc.recommended_action}</span></td>
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
    tbody.innerHTML = `<tr><td colspan="7" style="color: #f87171;">Error loading exceptions: ${err.message}</td></tr>`;
  }
}

function openExplanationModal(exc) {
  const modal = document.getElementById('explanationModal');
  const title = document.getElementById('modalTitle');
  const body = document.getElementById('modalBody');

  title.innerText = `Exception Analysis: ${exc.category}`;
  const expl = exc.grounded_explanation || {};

  body.innerHTML = `
    <div style="background: rgba(15,23,42,0.8); padding: 0.85rem; border-radius: 8px; border: 1px solid var(--border-card);">
      <div style="font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase;">Transaction Context</div>
      <div style="font-weight: 600; margin-top: 4px;">Record ID: <code>${exc.external_id}</code> (${exc.amount})</div>
      <div style="color: var(--text-muted); font-size: 0.85rem;">${exc.description}</div>
    </div>

    <div style="background: rgba(99,102,241,0.08); padding: 0.85rem; border-radius: 8px; border: 1px solid rgba(99,102,241,0.25);">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="font-size: 0.75rem; color: #a5b4fc; text-transform: uppercase; font-weight: 600;">Grounded AI Controller Analysis</span>
        <span class="badge" style="background: rgba(16,185,129,0.2); color: #34d399;">Citation Verified</span>
      </div>
      <p style="margin-top: 0.5rem; font-size: 0.9rem; color: var(--text-main);">${expl.summary || 'Standard exception pattern identified.'}</p>
      <div style="margin-top: 0.5rem; font-size: 0.8rem; color: var(--text-dim);">${expl.root_cause_analysis || ''}</div>
    </div>

    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
      <span style="font-size: 0.85rem; color: var(--text-muted);">Recommended Next Action:</span>
      <span class="badge badge-t0" style="font-size: 0.85rem;">${exc.recommended_action}</span>
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
  tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-dim);">Loading approval queue...</td></tr>';

  try {
    const res = await fetch('/api/proposals');
    const data = await res.json();

    if (!data.proposals || data.proposals.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-dim);">No pending action proposals.</td></tr>';
      return;
    }

    tbody.innerHTML = data.proposals.map(p => {
      const isPending = p.status.toLowerCase() === 'pending';
      const statusBadge = `<span class="badge badge-${p.status.toLowerCase()}">${p.status}</span>`;

      const actionButtons = isPending ? `
        <div style="display: flex; gap: 0.3rem;">
          <button class="btn btn-success" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;" onclick="reviewProposal('${p.proposal_id}', 'approve')">Approve & Post</button>
          <button class="btn btn-danger" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;" onclick="reviewProposal('${p.proposal_id}', 'reject')">Reject</button>
        </div>
      ` : '<span style="color: var(--text-dim); font-size: 0.75rem;">Action Finalized</span>';

      return `
        <tr>
          <td><code>${p.proposal_id}</code></td>
          <td><span class="badge" style="background: rgba(99,102,241,0.15); color: #818cf8;">${p.action_type}</span></td>
          <td>${statusBadge}</td>
          <td>
            <div>${p.summary}</div>
            ${p.adjust_amount && p.adjust_amount !== '₹0.00' ? `<div style="font-size: 0.75rem; color: #fbbf24;">Adjustment: ${p.adjust_amount}</div>` : ''}
          </td>
          <td><span style="color: var(--text-dim); font-size: 0.8rem;">${p.reviewed_by || 'Awaiting Review'}</span></td>
          <td>${actionButtons}</td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="color: #f87171;">Error loading proposals: ${err.message}</td></tr>`;
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
  tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-dim);">Loading audit events...</td></tr>';

  try {
    const res = await fetch('/api/audit?limit=25');
    const data = await res.json();

    if (!data.events || data.events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-dim);">No audit events recorded yet.</td></tr>';
      return;
    }

    tbody.innerHTML = data.events.reverse().map(ev => {
      const dateStr = new Date(ev.timestamp * 1000).toLocaleString();
      const currHash = ev.event_hash ? ev.event_hash.substring(0, 14) + '...' : 'genesis';
      const prevHash = ev.prev_hash ? ev.prev_hash.substring(0, 14) + '...' : '00000000000000...';

      return `
        <tr>
          <td><span style="font-size: 0.8rem; color: var(--text-muted);">${dateStr}</span></td>
          <td><span class="badge" style="background: rgba(255,255,255,0.06);">${ev.event_type}</span></td>
          <td><code>${ev.run_id || '--'}</code></td>
          <td><code style="color: #34d399;">${currHash}</code></td>
          <td><code style="color: var(--text-dim);">${prevHash}</code></td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="color: #f87171;">Error loading audit trail: ${err.message}</td></tr>`;
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
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg> Run 3-Way Recon`;
  }
}
