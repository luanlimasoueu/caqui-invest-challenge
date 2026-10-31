const state = {
  customerId: 'C-0001',
  overview: null,
  activeView: 'app-view',
  lastAnswers: {},
};

const $ = (selector, parent = document) => parent.querySelector(selector);
const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function formatMoney(value) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(value || 0));
}

function formatShortDate(value) {
  if (!value) return 'a confirmar';
  const [year, month, day] = value.slice(0, 10).split('-');
  return `${day}/${month}/${year}`;
}

async function api(url, options = {}) {
  const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Não foi possível concluir a ação.');
  return data;
}

function showToast(message, tone = '') {
  const toast = $('#toast');
  toast.textContent = message;
  toast.className = `toast show ${tone}`;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => { toast.className = 'toast'; }, 4200);
}

function switchView(viewId, prefill = '') {
  state.activeView = viewId;
  $$('.view').forEach(view => view.classList.toggle('active', view.id === viewId));
  $$('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.view === viewId));
  const titles = {
    'app-view': 'Aplicativo do cliente',
    'whatsapp-view': 'WhatsApp simulado',
    'chatbot-view': 'Chatbot com rastreabilidade',
    'human-view': 'Painel humano',
  };
  $('#breadcrumb-title').textContent = titles[viewId] || 'Atendimento';
  if (prefill && viewId === 'whatsapp-view') $('#whatsapp-input').value = prefill;
  if (prefill && viewId === 'chatbot-view') $('#chatbot-input').value = prefill;
  if (viewId === 'human-view') loadQueue();
}

function renderAccount(customer) {
  $('#account-card').innerHTML = `
    <div class="section-label">Conta autenticada</div>
    <div class="account-name">${escapeHtml(customer.persona || customer.first_name)}</div>
    <div class="account-meta">${escapeHtml(customer.city)} · CPF ${escapeHtml(customer.cpf_masked)}</div>
    <div class="account-balance-label">Saldo em conta</div>
    <div class="account-balance">${escapeHtml(customer.balance_label)}</div>
    <div class="account-footer"><span>ID ${escapeHtml(customer.id)}</span><span>Dados sintéticos</span></div>
  `;
  $('#chatbot-first-name').textContent = customer.first_name;
}

function timelineMarkup(operation) {
  const refused = operation.status === 'recusada';
  const steps = refused
    ? [['done', 'Pedido', operation.requested_label.split(' às ')[0]], ['done', 'Análise', 'concluída'], ['current', 'Recusada', 'ver motivo']]
    : [['done', 'Pedido recebido', operation.requested_label.split(' às ')[0]], ['done', 'Em análise', operation.status === 'liquidada' ? 'concluída' : 'agora'], ['current', 'Liquidação', operation.expected_label], ['future', 'Na conta', operation.status === 'liquidada' ? 'concluída' : 'próximo passo']];
  return `<div class="timeline">${steps.map(([klass, label, sub]) => `<div class="timeline-step ${klass}"><span class="timeline-point"></span><strong>${escapeHtml(label)}</strong><span>${escapeHtml(sub)}</span></div>`).join('')}</div>`;
}

function renderFeatured(operation) {
  if (!operation) {
    $('#featured-operation-content').innerHTML = '<div class="loading-block">Nenhuma operação encontrada para este cliente.</div>';
    return;
  }
  const statusText = operation.status === 'em_processamento' ? 'Em processamento' : operation.status_label;
  $('#featured-operation-content').innerHTML = `
    <div class="featured-content">
      <div>
        <div class="operation-kicker"><span class="operation-dot"></span>${escapeHtml(statusText)} · ${escapeHtml(operation.id)}</div>
        <div class="featured-amount">${escapeHtml(operation.amount_label)}</div>
        <div class="featured-meta">${escapeHtml(operation.type_label)} · ${escapeHtml(operation.product_label)} · pedido em ${escapeHtml(operation.requested_label)}</div>
      </div>
      <div class="featured-date"><div class="date-label">Liquidação prevista</div><div class="date-value">${escapeHtml(operation.expected_label)}</div><div class="date-note">${escapeHtml(operation.expected_source)}</div></div>
    </div>
    ${timelineMarkup(operation)}
  `;
}

function renderOperations(operations) {
  const list = $('#operations-list');
  if (!operations.length) {
    list.innerHTML = '<div class="loading-block">Nenhuma operação encontrada para este cliente.</div>';
    return;
  }
  list.innerHTML = operations.map(operation => `
    <div class="operation-row">
      <div class="operation-name"><span class="operation-mini-icon">${operation.type === 'resgate' ? '↓' : '↗'}</span><div><strong>${escapeHtml(operation.type_label)}</strong><span>${escapeHtml(operation.id)} · ${escapeHtml(operation.product_label)}</span></div></div>
      <div class="operation-amount">${escapeHtml(operation.amount_label)}</div>
      <div class="operation-date">${escapeHtml(formatShortDate(operation.requested_at))}</div>
      <span class="status-label ${escapeHtml(operation.status)}">${escapeHtml(operation.status_label)}</span>
    </div>
  `).join('');
}

async function loadOverview() {
  try {
    const data = await api(`/api/overview?customer_id=${encodeURIComponent(state.customerId)}`);
    state.overview = data;
    state.customerId = data.customer.id;
    renderAccount(data.customer);
    renderFeatured(data.featured_operation);
    renderOperations(data.operations);
    $('#customer-select').value = data.customer.id;
  } catch (error) {
    showToast(error.message, 'danger');
  }
}

async function loadCustomers() {
  const data = await api('/api/customers');
  $('#customer-select').innerHTML = data.customers.map(customer => `<option value="${escapeHtml(customer.id)}">${escapeHtml(customer.name)} · ${escapeHtml(customer.id)}</option>`).join('');
  $('#customer-select').value = state.customerId;
}

function appendWhatsappMessage(text, direction = 'incoming', meta = '') {
  const list = $('#whatsapp-messages');
  const node = document.createElement('div');
  node.className = `message ${direction}`;
  node.innerHTML = `${escapeHtml(text)}<span class="message-time">10:00 ${direction === 'outgoing' ? '✓✓' : ''}</span>`;
  list.appendChild(node);
  if (meta) {
    const source = document.createElement('div');
    source.className = 'message incoming';
    source.innerHTML = `<strong style="font-size:10px;color:#0b6b64;">${escapeHtml(meta)}</strong><span class="message-time">10:00</span>`;
    list.appendChild(source);
  }
  list.scrollTop = list.scrollHeight;
}

function appendChatMessage(text, direction = 'bot') {
  const list = $('#chatbot-messages');
  const node = document.createElement('div');
  node.className = `chat-message ${direction}`;
  node.innerHTML = `<div class="bot-mark">${direction === 'bot' ? '✦' : '•••'}</div><div><p>${escapeHtml(text)}</p><span class="chat-time">10:00</span></div>`;
  list.appendChild(node);
  list.scrollTop = list.scrollHeight;
}

function renderAnswerDetails(result) {
  const card = $('#last-answer-card');
  const isDanger = result.risk.scam;
  const badge = isDanger ? 'segurança prioritária' : result.handoff ? 'entrega humana' : 'respondido com regra';
  card.innerHTML = `
    <div class="section-label">Última resposta</div>
    <div class="answer-result">
      <div class="decision-row"><strong style="font-size:12px;color:#123d3a;">${escapeHtml(result.intent.replaceAll('_', ' '))}</strong><span class="decision-badge">${escapeHtml(badge)}</span></div>
      ${result.protocol ? `<div style="font:10px 'DM Mono',monospace;color:#71807d;margin-top:7px;">PROTOCOLO ${escapeHtml(result.protocol)}</div>` : ''}
      <div style="margin-top:15px;">${result.sources.map(source => `<span class="source-chip"><strong>${escapeHtml(source.label)}</strong>${escapeHtml(source.detail)}</span>`).join('')}</div>
      ${result.handoff ? `<button class="human-cta" data-view-target="human-view">Abrir contexto no painel humano →</button>` : ''}
    </div>
  `;
  card.querySelectorAll('[data-view-target]').forEach(button => button.addEventListener('click', () => switchView(button.dataset.viewTarget)));
}

async function resolve(channel, message) {
  const text = String(message || '').trim();
  if (!text) return;
  if (channel === 'whatsapp') appendWhatsappMessage(text, 'outgoing');
  if (channel === 'chatbot') appendChatMessage(text, 'user');
  try {
    const result = await api('/api/resolve', { method: 'POST', body: JSON.stringify({ customer_id: state.customerId, message: text, channel }) });
    if (channel === 'whatsapp') appendWhatsappMessage(result.reply, 'incoming', result.sources[0]?.label || 'Resposta com fonte');
    if (channel === 'chatbot') {
      appendChatMessage(result.reply, 'bot');
      renderAnswerDetails(result);
    }
    if (result.risk.scam) showToast('Fluxo interrompido: caso enviado para segurança.', 'danger');
    else if (result.handoff) showToast(`Caso encaminhado com o protocolo ${result.protocol}.`);
  } catch (error) {
    showToast(error.message, 'danger');
  }
}

async function loadQueue() {
  try {
    const data = await api('/api/queue');
    $('#queue-list').innerHTML = data.items.map(item => `
      <div class="queue-row">
        <span class="priority-bar ${escapeHtml(item.priority)}"></span>
        <div class="queue-main"><strong>${escapeHtml(item.customer)}</strong><span>${escapeHtml(item.protocol)} · ${escapeHtml(item.source)}</span></div>
        <div class="queue-subject">${escapeHtml(item.subject)}<br><em>${escapeHtml(item.preview)}</em></div>
        <div><span class="priority-label ${escapeHtml(item.priority)}">${escapeHtml(item.priority)}</span><div class="queue-age">${escapeHtml(item.age)}</div></div>
        <button class="open-case" data-customer="${escapeHtml(item.customer_id)}">Abrir caso →</button>
      </div>
    `).join('');
    $$('.open-case', $('#queue-list')).forEach(button => button.addEventListener('click', () => {
      state.customerId = button.dataset.customer;
      $('#customer-select').value = state.customerId;
      loadOverview();
      switchView('app-view');
      showToast('Contexto do cliente carregado no aplicativo.');
    }));
  } catch (error) {
    showToast(error.message, 'danger');
  }
}

function bindEvents() {
  $$('.nav-item').forEach(button => button.addEventListener('click', () => switchView(button.dataset.view)));
  $$('.action-card, [data-view-target]').forEach(button => {
    if (button.classList.contains('nav-item')) return;
    button.addEventListener('click', () => switchView(button.dataset.viewTarget, button.dataset.prefill || ''));
  });
  $('#customer-select').addEventListener('change', event => { state.customerId = event.target.value; loadOverview(); });
  $('#refresh-data').addEventListener('click', () => { loadOverview(); showToast('Dados atualizados a partir do pacote sintético.'); });
  $('#whatsapp-form').addEventListener('submit', event => { event.preventDefault(); const input = $('#whatsapp-input'); const text = input.value; input.value = ''; resolve('whatsapp', text); });
  $('#chatbot-form').addEventListener('submit', event => { event.preventDefault(); const input = $('#chatbot-input'); const text = input.value; input.value = ''; resolve('chatbot', text); });
  $$('#whatsapp-quick-replies button').forEach(button => button.addEventListener('click', () => { $('#whatsapp-input').value = button.dataset.message; $('#whatsapp-input').focus(); }));
  $$('.chat-suggestions button').forEach(button => button.addEventListener('click', () => { $('#chatbot-input').value = button.dataset.message; $('#chatbot-input').focus(); }));
  $$('.scenario-card button').forEach(button => button.addEventListener('click', () => { $('#whatsapp-input').value = button.dataset.message; $('#whatsapp-input').focus(); }));
}

async function init() {
  bindEvents();
  try {
    await loadCustomers();
    await loadOverview();
    await loadQueue();
  } catch (error) {
    showToast('Inicie o servidor local para carregar os dados.', 'danger');
  }
}

init();
