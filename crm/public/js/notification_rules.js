(() => {
  'use strict';
  const boot = window.expCRMRuleBoot;
  const byId = id => document.getElementById(id);
  let state, currentId = crypto.randomUUID().replaceAll('-', ''), pending = null;
  let selected = new Set(), labels = new Map(), searchGeneration = 0;
  const error = byId('error'), status = byId('status');
  const channels = ['crm-push', 'one-message', 'one-push', 'email'];
  const mutationId = () => crypto.randomUUID().replaceAll('-', '');

  function showError(message) { error.textContent = message; error.hidden = false; error.focus(); }
  async function rpc(method, values = {}, post = false) {
    const route = '/api/method/crm.notification_rules.api.' + method;
    const payload = {...values, expected_viewer: boot.viewer};
    const response = await fetch(post ? route : route + '?' + new URLSearchParams(payload), {
      method: post ? 'POST' : 'GET', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': boot.csrf},
      ...(post ? {body: JSON.stringify(payload)} : {})
    });
    let data;
    try { data = await response.json(); } catch { throw new Error('Не удалось получить ответ. Повторите запрос.'); }
    if (!response.ok) {
      if (data.exc_type === 'TimestampMismatchError') throw new Error('Настройки изменились в другом окне. Введённое сохранено в форме; обновите настройки перед новым сохранением.');
      throw new Error('Не удалось выполнить действие. Проверьте доступ и выбранные значения.');
    }
    return data.message;
  }
  function choice(id, text, checked, onChange) {
    const label = document.createElement('label'); label.className = 'check';
    const input = document.createElement('input'); input.type = 'checkbox'; input.value = id; input.checked = checked;
    input.addEventListener('change', () => onChange(input.checked));
    label.append(input, document.createTextNode(text)); return label;
  }
  function renderLeads(rows) {
    rows.forEach(row => labels.set(row.id, row.label));
    const ids = [...new Set([...selected, ...rows.map(row => row.id)])];
    byId('leads').replaceChildren(...ids.map(id => choice(id, labels.get(id) || id, selected.has(id), checked => {
      checked ? selected.add(id) : selected.delete(id); count(); pending = null;
    })));
    count();
  }
  function count() { byId('selected-count').textContent = 'Выбрано лидов: ' + selected.size; }
  function renderState() {
    const names = { crm_push: 'CRM push', one_message: 'сообщение One', one_push: 'push One', email: 'почта' };
    const active = Object.entries(names).map(([key, name]) => `${name}: ${state.masters[key] ? 'включён' : 'выключен'}`);
    byId('masters').textContent = 'Общие настройки каналов — ' + active.join('; ') + '. Правило не включает выключенный канал автоматически.'
      + (state.push_service_available ? '' : ' Служба push сейчас выключена.');
    const rows = state.configuration.rules.map(rule => {
      const row = document.createElement('div'); row.className = 'saved-rule';
      const label = document.createElement('span'); label.textContent = `${rule.name} · ${rule.enabled ? 'включено' : 'выключено'}`;
      row.append(label);
      if (rule.object === 'CRM Lead' && rule.event === 'lead_status_changed' && rule.scope === 'selected'
          && ['statuses', 'owners', 'sources', 'pipelines'].every(key => !rule[key].length)) {
        const edit = document.createElement('button'); edit.type = 'button'; edit.className = 'secondary'; edit.textContent = 'Изменить';
        edit.addEventListener('click', () => editRule(rule)); row.append(edit);
      }
      return row;
    });
    byId('saved').replaceChildren(...rows);
    if (!rows.length) byId('saved').textContent = 'Правил пока нет.';
  }
  function editRule(rule) {
    if (rule.unavailable_selection_count) { showError('Часть выбранных лидов недоступна. Проверьте доступ перед изменением правила.'); return; }
    currentId = rule.id; selected = new Set(rule.record_ids); pending = null;
    byId('rule-name').value = rule.name; byId('enabled').checked = rule.enabled;
    byId('include-self').checked = rule.include_self;
    channels.forEach(id => byId(id).checked = rule.channels[id.replaceAll('-', '_')]);
    byId('one-push').disabled = !byId('one-message').checked;
    byId('statuses').querySelectorAll('input').forEach(input => input.checked = rule.to_statuses.includes(input.value));
    search(); byId('rule-name').focus();
  }
  async function search() {
    const generation = ++searchGeneration;
    try {
      const rows = await rpc('search_records', {doctype: 'CRM Lead', query: byId('lead-search').value});
      if (generation === searchGeneration) renderLeads(rows);
    } catch (e) { showError(e.message); }
  }
  byId('one-message').addEventListener('change', () => {
    byId('one-push').disabled = !byId('one-message').checked;
    if (byId('one-push').disabled) byId('one-push').checked = false;
  });
  let timer;
  byId('lead-search').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(search, 180); });
  byId('rule-form').addEventListener('input', () => { pending = null; });
  byId('rule-form').addEventListener('submit', async event => {
    event.preventDefault(); error.hidden = true;
    const statuses = [...byId('statuses').querySelectorAll('input:checked')].map(input => input.value);
    if (!selected.size || !statuses.length) { showError('Выберите хотя бы один лид и один статус.'); return; }
    if (!byId('crm-push').checked && !byId('one-message').checked && !byId('email').checked) { showError('Выберите способ доставки.'); return; }
    const values = {id: currentId, name: byId('rule-name').value, enabled: byId('enabled').checked,
      object: 'CRM Lead', event: 'lead_status_changed', scope: 'selected', record_ids: [...selected],
      to_statuses: statuses, include_self: byId('include-self').checked,
      channels: Object.fromEntries(channels.map(id => [id.replaceAll('-', '_'), byId(id).checked]))};
    pending ||= {values, expected_revision: state.revision, mutation_id: mutationId()};
    byId('save').disabled = true; status.textContent = 'Сохранение…';
    try {
      state = await rpc('save_rule', pending, true); pending = null; renderState(); status.textContent = 'Правило сохранено.';
    } catch (e) { status.textContent = ''; showError(e.message); }
    finally { byId('save').disabled = false; }
  });
  byId('reload').addEventListener('click', async () => {
    try { state = await rpc('get_settings'); pending = null; renderState(); error.hidden = true; status.textContent = 'Настройки обновлены. Введённые условия остались в форме.'; }
    catch (e) { showError(e.message); }
  });
  byId('new-rule').addEventListener('click', () => {
    currentId = mutationId(); pending = null; selected = new Set(); byId('rule-form').reset(); search();
    byId('one-push').disabled = true; status.textContent = ''; byId('rule-name').focus();
  });
  (async () => {
    byId('save').disabled = true;
    try {
      const results = await Promise.all([rpc('get_settings'), rpc('options')]); state = results[0];
      byId('statuses').replaceChildren(...results[1].statuses['CRM Lead'].map(name => choice(name, name, false, () => { pending = null; })));
      renderState(); await search(); byId('save').disabled = false;
    } catch (e) { showError(e.message); }
  })();
})();
