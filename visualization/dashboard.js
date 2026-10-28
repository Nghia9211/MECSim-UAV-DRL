/* Local-only explorer for recorded simulation output. No network dependency. */
(() => {
  'use strict';
  const DATA = JSON.parse(document.getElementById('experiment-data').textContent);
  const $ = id => document.getElementById(id);
  // Keep detailed analysis available without crowding the replay workspace.
  const main = $('uav-lab');
  const advanced = document.createElement('details');
  advanced.className = 'advanced'; advanced.id = 'advanced';
  advanced.innerHTML = '<summary>Nâng cao · cấu hình, checkpoint và phân tích</summary>';
  main.insertBefore(advanced, main.querySelector('footer'));
  const datasetControl = $('dataset').closest('label');
  datasetControl.classList.add('dataset-control');
  for (const id of ['theme', 'build-date']) { const node = $(id); node.hidden = true; advanced.append(node); }
  main.querySelector('.top-meta').replaceWith(datasetControl);
  for (const selector of ['.filters', '.scope', '.stats', '.charts-grid', '.validation-panel', '.provenance']) advanced.append(main.querySelector(selector));
  main.querySelector('.intro').hidden = true;
  const compact = document.createElement('section'); compact.className = 'panel compact-results';
  compact.innerHTML = '<h2>So sánh trung bình nhiều case</h2><p>Bản đồ phía trên phát lại một case đang chọn. Best checkpoint được chọn bằng validation.</p><div class="table-scroll"><table><thead id="compact-head"></thead><tbody id="compact-body"></tbody></table></div>';
  main.insertBefore(compact, advanced);
  advanced.append(main.querySelector('.table-panel'));
  // The default view is only the replay; secondary controls stay collapsed.
  const caseOptions = document.createElement('details');
  caseOptions.className = 'case-options';
  caseOptions.innerHTML = '<summary>Chọn lần chạy</summary>';
  const trajectory = main.querySelector('.trajectory-panel');
  caseOptions.append(main.querySelector('.case-controls'));
  trajectory.querySelector('.panel-head').replaceWith(caseOptions);
  const results = document.createElement('details');
  results.className = 'results-disclosure';
  results.innerHTML = '<summary>Xem bảng so sánh kết quả</summary>';
  main.insertBefore(results, compact); results.append(compact);
  advanced.append(main.querySelector('.flight-info'));
  advanced.append(main.querySelector('.map-footer'));
  $('play').textContent = 'Phát';
  $('rewind').textContent = 'Làm lại';
  document.documentElement.dataset.theme = 'light';
  const POLICIES = ['DQN', 'ROUND_ROBIN', 'OLDEST_DATA', 'RANDOM'];
  const LABELS = {DQN: 'DQN', ROUND_ROBIN: 'Round Robin', OLDEST_DATA: 'Oldest Data', RANDOM: 'Random'};
  const COLORS = {DQN: 'var(--blue)', ROUND_ROBIN: 'var(--orange)', OLDEST_DATA: 'var(--green)', RANDOM: 'var(--purple)'};
  const PROFILE = {REFERENCE: 'REFERENCE · mặc định', REWARD_AFTER: 'REWARD_AFTER · tuổi sau step', LOCAL_COMPLETION: 'LOCAL_COMPLETION · xử lý xong', MOBILE: 'Mobile · ALL_UAV + EDF'};
  const METRICS = {
    slots: {name: 'Lifetime (slot)', unit: 'slot', direction: 1},
    seconds: {name: 'Thời gian mô phỏng (s)', unit: 's', direction: 1},
    energy: {name: 'Năng lượng UAV (kJ)', unit: 'kJ', direction: -1},
    dvr: {name: 'DVR ảnh (%)', unit: '%', direction: -1},
    delivery: {name: 'Ảnh chuyển kết quả đúng hạn', unit: 'ảnh', direction: 1},
    offloaded: {name: 'Ảnh được offload', unit: 'ảnh', direction: 0}
  };
  const state = {dataset: DATA.datasets[0].id, profile: DATA.datasets[0].defaultProfile, checkpoint: 'best', metric: 'slots', seed: 0,
    task: 2000000, focus: 'DQN', visible: new Set(POLICIES), time: 0, maxTime: 1, playing: false, animation: null};
  const fmt = (n, d = 2) => Number.isFinite(n) ? new Intl.NumberFormat('vi-VN', {maximumFractionDigits: d, minimumFractionDigits: d}).format(n) : '—';
  const mean = a => a.length ? a.reduce((s, x) => s + x, 0) / a.length : NaN;
  const esc = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const ds = () => DATA.datasets.find(d => d.id === state.dataset);
  const metric = () => ({...METRICS[state.metric], ...(state.metric === 'energy' && ds().kind === 'mobile' ? {name: 'Tổng năng lượng hệ thống (kJ)'} : {})});
  const value = r => state.metric === 'energy' ? r.energy / 1000 : state.metric === 'dvr' ? r.dvr * 100 : r[state.metric];
  const selected = (checkpoint = state.checkpoint) => ds().rows.filter(r => r.profile === state.profile && (r.policy !== 'DQN' || r.checkpoint === checkpoint));
  const options = (id, values, selectedValue, labels = {}) => { $(id).innerHTML = values.map(v => `<option value="${esc(v)}" ${String(v) === String(selectedValue) ? 'selected' : ''}>${esc(labels[v] || v)}</option>`).join(''); };
  const svg = (w, h, title, content) => `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(title)}"><title>${esc(title)}</title>${content}</svg>`;
  const text = (x, y, s, cls = 'axis', extra = '') => `<text x="${x}" y="${y}" class="${cls}" ${extra}>${esc(s)}</text>`;
  function scaleMax(values) {
    const v = Math.max(1, ...values.filter(Number.isFinite)) * 1.13;
    const step = Math.pow(10, Math.floor(Math.log10(v)));
    return Math.ceil(v / step * 2) / 2 * step;
  }
  function aggregates() {
    return POLICIES.map(policy => {
      const rows = selected().filter(r => r.policy === policy);
      const groups = new Map();
      for (const r of rows) { const key = ds().kind === 'mobile' ? r.task : r.seed; if (!groups.has(key)) groups.set(key, []); groups.get(key).push(value(r)); }
      const points = [...groups].map(([seed, vals]) => ({seed, value: mean(vals)}));
      return {policy, rows, points, average: mean(rows.map(value))};
    });
  }
  function metricNote() {
    if (state.metric === 'energy') return ds().kind === 'paper'
      ? 'Chỉ năng lượng UAV, không phải tổng hệ thống. Episode có lifetime khác nhau: tiêu thụ ít hơn khi dừng sớm không tự có nghĩa tốt hơn.'
      : 'Tổng năng lượng gồm ground và UAV. Đọc cùng DVR/delivery; episode mobile cố định 600 giây, chưa đo lifetime.';
    if (state.metric === 'offloaded') return 'Số ảnh offloaded là mức sử dụng UAV, không phải objective cần tối đa hóa riêng.';
    return ds().kind === 'paper' ? 'Các chấm là mean của từng learning/layout seed nếu có; baseline dùng chung chỉ tính một lần/case. Không phải confidence interval.' : 'Chấm thể hiện từng task-seed episode; chỉ một learning seed, chưa chứng minh hội tụ hoặc superiority.';
  }
  function renderStats(groups) {
    const q = groups[0], direction = metric().direction;
    const others = groups.slice(1).filter(g => Number.isFinite(g.average));
    const comparator = direction === 0 ? others.find(g => g.policy === 'OLDEST_DATA') : others.reduce((a, b) => direction * b.average > direction * a.average ? b : a);
    $('stat-label').textContent = `DQN · ${metric().name}`;
    $('stat-dqn').textContent = `${fmt(q.average)} ${metric().unit}`;
    $('stat-dqn-detail').textContent = `${q.rows.length} episode · ${state.checkpoint === 'best' ? 'best theo validation' : 'final checkpoint'}`;
    $('baseline-label').textContent = direction === 0 ? 'Heuristic đối chiếu' : `Heuristic có mean ${direction === 1 ? 'cao' : 'thấp'} nhất`;
    $('stat-baseline').textContent = `${fmt(comparator.average)} ${metric().unit}`;
    $('stat-baseline-detail').textContent = `${LABELS[comparator.policy]} · ${comparator.rows.length} episode`;
    const delta = q.average - comparator.average;
    $('stat-delta').textContent = `${delta >= 0 ? '+' : ''}${fmt(delta)} ${state.metric === 'dvr' ? 'điểm %' : metric().unit}`;
    $('stat-delta-detail').textContent = `Chênh lệch mô tả, chưa kiểm định thống kê`;
    $('stat-cases').textContent = `${new Set(q.rows.map(r => r.seed)).size} seed × ${new Set(q.rows.map(r => r.task)).size} case`;
    $('stat-unit').textContent = ds().unit;
  }
  function renderBars(groups) {
    const w = 590, h = 250, left = 110, width = 393, top = 20, maximum = scaleMax(groups.flatMap(g => [g.average, ...g.points.map(p => p.value)]));
    let marks = '';
    for (let i = 0; i <= 4; i++) { const x = left + i / 4 * width; marks += `<path d="M${x},12V220" class="grid-line"/>${text(x, 243, fmt(maximum * i / 4, maximum > 100 ? 0 : 1), 'axis', 'text-anchor="middle"')}`; }
    groups.forEach((g, i) => {
      const y = top + i * 49, len = g.average / maximum * width;
      marks += text(left - 12, y + 20, LABELS[g.policy], 'chart-label', 'text-anchor="end"');
      marks += `<rect x="${left}" y="${y + 2}" width="${len}" height="28" rx="5" fill="${COLORS[g.policy]}" opacity="${g.policy === 'DQN' ? .9 : .65}" data-tip="${esc(`${LABELS[g.policy]}: ${fmt(g.average)} ${metric().unit}; ${g.rows.length} episode`)}"/>`;
      for (const [j, p] of g.points.entries()) marks += `<circle class="point" cx="${left + p.value / maximum * width}" cy="${y + 16 + ((j % 3) - 1) * 6}" r="3.5" fill="${COLORS[g.policy]}" data-tip="${esc(`${LABELS[g.policy]}, ${ds().kind === 'mobile' ? 'task seed' : 'seed'} ${p.seed}: ${fmt(p.value)} ${metric().unit}`)}"/>`;
      marks += text(left + len + 9, y + 21, fmt(g.average), 'chart-label');
    });
    $('bars').innerHTML = svg(w, h, 'Trung bình theo thuật toán, đơn vị ' + metric().unit, marks);
    $('comparison-unit').textContent = `${metric().name} · ${state.metric === 'offloaded' ? 'chỉ số mô tả' : metric().direction > 0 ? 'cao hơn' : 'thấp hơn'} — xem phạm vi bên dưới`;
    $('chart-note').textContent = metricNote();
  }
  function renderStability() {
    if (ds().kind === 'mobile') {
      $('stability-title').textContent = 'Kết quả từng task seed';
      $('stability-unit').textContent = `${metric().name} · 10 case được ghép cặp`;
      $('stability-note').textContent = 'DQN pilot chỉ train 2.000 bước; các đường không biểu diễn nhiều learning seed.';
      const rows = selected(), tasks = [...new Set(rows.map(r => r.task))].sort((a, b) => a - b);
      const max = scaleMax(rows.map(value)), W = 590, H = 250, L = 52, T = 16, pw = 500, ph = 192;
      let s = '';
      for (let i = 0; i <= 4; i++) { const y = T + ph - i / 4 * ph; s += `<path d="M${L},${y}H${L + pw}" class="grid-line"/>${text(L - 9, y + 4, fmt(i / 4 * max, 0), 'axis', 'text-anchor="end"')}`; }
      POLICIES.forEach(policy => {
        const points = tasks.map((task, j) => { const r = rows.find(r => r.policy === policy && r.task === task); return [L + j / Math.max(1, tasks.length - 1) * pw, T + ph - value(r) / max * ph, r]; });
        s += `<polyline points="${points.map(p => p.slice(0, 2).join(',')).join(' ')}" class="plot-line" stroke="${COLORS[policy]}"/>`;
        points.forEach(p => { s += `<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="${COLORS[policy]}" data-tip="${esc(`${LABELS[policy]}, task ${p[2].task}: ${fmt(value(p[2]))} ${metric().unit}`)}"/>`; });
      });
      tasks.forEach((task, i) => { if (i % 2 === 0 || i === tasks.length - 1) s += text(L + i / Math.max(1, tasks.length - 1) * pw, 237, `…${String(task).slice(-3)}`, 'axis', 'text-anchor="middle"'); });
      $('stability').innerHTML = svg(W, H, 'So sánh các thuật toán trên từng task seed', s); return;
    }
    $('stability-title').textContent = 'Best và final theo learning seed';
    $('stability-unit').textContent = metric().name + ' · chỉ DQN';
    $('stability-note').textContent = 'Best được chọn bằng validation. Final là checkpoint cuối đúng 1m. Cùng test case, không phải mẫu độc lập bổ sung.';
    const seeds = [...new Set(ds().rows.filter(r => r.profile === state.profile && r.policy === 'DQN').map(r => r.seed))].sort();
    const values = seeds.map(seed => ['best', 'final'].map(cp => mean(ds().rows.filter(r => r.profile === state.profile && r.policy === 'DQN' && r.seed === seed && r.checkpoint === cp).map(value))));
    const max = scaleMax(values.flat()), W = 590, H = 250, L = 55, T = 28, ph = 177, pw = 490;
    let s = `<rect x="360" y="3" width="9" height="9" fill="var(--blue)"/>${text(375, 12, 'Best', 'axis')}<rect x="430" y="3" width="9" height="9" fill="var(--muted)"/>${text(445, 12, 'Final', 'axis')}`;
    for (let i = 0; i <= 4; i++) { const y = T + ph - i / 4 * ph; s += `<path d="M${L},${y}H${L + pw}" class="grid-line"/>${text(L - 9, y + 4, fmt(i / 4 * max, 0), 'axis', 'text-anchor="end"')}`; }
    seeds.forEach((seed, i) => {
      const center = L + (i + .5) / seeds.length * pw;
      values[i].forEach((v, j) => { if (!Number.isFinite(v)) return; const x = center - 40 + j * 44, height = v / max * ph; s += `<rect x="${x}" y="${T + ph - height}" width="36" height="${height}" rx="4" fill="${j === 0 ? 'var(--blue)' : 'var(--muted)'}" opacity="${j === 0 ? .9 : .5}" data-tip="Seed ${seed} · ${j === 0 ? 'Best' : 'Final'}: ${fmt(v)} ${metric().unit}"/>${text(x + 18, T + ph - height - 7, fmt(v), 'chart-label', 'text-anchor="middle"')}`; });
      s += text(center, 237, `Seed ${seed}`, 'axis', 'text-anchor="middle"');
    });
    $('stability').innerHTML = svg(W, H, 'DQN best và final theo từng learning seed', s);
  }
  function renderTable(groups) {
    const primary = ds().kind === 'paper' ? 'Lifetime (slot) ↑' : 'DVR ảnh (%) ↓';
    $('compact-head').innerHTML = `<tr><th>Thuật toán</th><th>${primary}</th><th>Năng lượng ${ds().kind === 'paper' ? 'UAV' : 'hệ thống'} (kJ)</th></tr>`;
    $('compact-body').innerHTML = groups.map(g => `<tr><td><span class="swatch" style="--series:${COLORS[g.policy]}"></span>${LABELS[g.policy]}</td><td>${fmt(mean(g.rows.map(r => ds().kind === 'paper' ? r.slots : r.dvr * 100)))}</td><td>${fmt(mean(g.rows.map(r => r.energy / 1000)))}</td></tr>`).join('');
    $('table-head').innerHTML = `<tr><th>Thuật toán</th><th>Mean (${esc(metric().unit)})</th><th>Min episode</th><th>Max episode</th><th>Episode</th><th>Learning/layout nhóm</th></tr>`;
    $('table-body').innerHTML = groups.map(g => `<tr><td><span class="swatch" style="--series:${COLORS[g.policy]}"></span>${LABELS[g.policy]}</td><td>${fmt(g.average)}</td><td>${fmt(Math.min(...g.rows.map(value)))}</td><td>${fmt(Math.max(...g.rows.map(value)))}</td><td>${g.rows.length}</td><td>${g.points.length}${ds().kind === 'mobile' ? ' task case' : g.points[0]?.seed === -1 ? ' bộ dùng chung' : ' seed'}</td></tr>`).join('');
  }
  function renderValidation() {
    const curves = ds().curves.filter(c => c.profile === state.profile), mobile = ds().kind === 'mobile';
    $('validation-unit').textContent = mobile ? 'DVR validation của mobile pilot; checkpoint chọn theo reward, không theo DVR này.' : 'Mean lifetime trên 5 validation case. Không dùng test để chọn checkpoint.';
    if (!curves.length) { $('validation').innerHTML = '<div class="empty">Không có validation curve trong bộ kết quả này.</div>'; return; }
    const W = 1200, H = 245, L = 65, T = 26, ph = 175, pw = 1065;
    const maxX = Math.max(...curves.flatMap(c => c.points.map(p => p[0]))), maxY = scaleMax(curves.flatMap(c => c.points.map(p => p[1] * (mobile ? 100 : 1))));
    const colors = ['var(--blue)', 'var(--orange)', 'var(--green)']; let s = '';
    for (let i = 0; i <= 4; i++) { const y = T + ph - i / 4 * ph, x = L + i / 4 * pw; s += `<path d="M${L},${y}H${L + pw}" class="grid-line"/>${text(L - 12, y + 4, fmt(maxY * i / 4, 0), 'axis', 'text-anchor="end"')}${text(x, 231, `${fmt(maxX * i / 4 / 1000, 0)}k`, 'axis', 'text-anchor="middle"')}`; }
    curves.forEach((c, i) => {
      const coords = c.points.map(p => [L + p[0] / maxX * pw, T + ph - p[1] * (mobile ? 100 : 1) / maxY * ph]);
      s += `<polyline points="${coords.map(p => p.join(',')).join(' ')}" class="plot-line" stroke="${colors[i % 3]}" opacity=".8"/>`;
      c.points.forEach((p, j) => { s += `<circle cx="${coords[j][0]}" cy="${coords[j][1]}" r="2.7" fill="${colors[i % 3]}" data-tip="Seed ${c.seed} · ${fmt(p[0], 0)} bước · ${fmt(p[1] * (mobile ? 100 : 1))} ${mobile ? '%' : 'slot'}"/>`; });
      s += `<circle cx="${L + 130 * i}" cy="8" r="4" fill="${colors[i % 3]}"/>${text(L + 10 + 130 * i, 12, 'Seed ' + c.seed, 'axis')}`;
    });
    $('validation').innerHTML = svg(W, H, 'Validation DQN theo số bước training', s);
  }
  let caseRows = [];
  function setCase() {
    pause();
    const available = selected().filter(r => r.traceId && r.task === state.task && (r.seed === state.seed || r.seed === -1));
    caseRows = POLICIES.map(p => available.find(r => r.policy === p)).filter(Boolean);
    state.maxTime = Math.max(1, ...caseRows.map(r => r.seconds)); state.time = state.maxTime;
    $('time').max = state.maxTime; $('time').value = state.time;
    renderMap();
  }
  function pointAt(trace, time) {
    if (trace.kind === 'paper') {
      let i = trace.points.findIndex(p => time < p[1] - 1e-7); if (i < 0) i = trace.points.length - 1;
      const p = trace.points[i], before = i ? trace.points[i - 1] : null;
      const sx = before ? before[2] : 0, sy = before ? before[3] : 0, initial = before ? before[4] : 1600000;
      const d = Math.hypot(p[2] - sx, p[3] - sy), flight = d / trace.speed, dt = Math.max(0, Math.min(time, p[1]) - p[0]);
      const f = flight ? Math.min(1, dt / flight) : 1;
      const battery = time >= p[1] ? p[4] : Math.max(p[4], initial - 150 * Math.min(dt, flight) - 80 * Math.max(0, dt - flight));
      return {x: sx + (p[2] - sx) * f, y: sy + (p[3] - sy) * f, battery, moving: dt < flight - 1e-7,
        age: time >= p[1] ? p[5] : before ? before[5] : 0, action: p[6], slot: i + 1, totalSlots: trace.points.length};
    }
    const ps = trace.points; let i = 0; while (i + 1 < ps.length && ps[i + 1][0] <= time) i++;
    const a = ps[i], b = ps[Math.min(i + 1, ps.length - 1)], f = b[0] > a[0] ? Math.min(1, Math.max(0, (time - a[0]) / (b[0] - a[0]))) : 0;
    return {x: a[1] + (b[1] - a[1]) * f, y: a[2] + (b[2] - a[2]) * f, battery: a[3] + (b[3] - a[3]) * f, moving: a[4], action: a[5]};
  }
  function wholePath(trace) {
    return trace.kind === 'paper' ? [[0, 0], ...trace.points.map(p => [p[2], p[3]])] : trace.points.map(p => [p[1], p[2]]);
  }
  function elapsedPath(trace, time, now) {
    const pts = trace.kind === 'paper' ? [[0, 0], ...trace.points.filter(p => p[1] <= time).map(p => [p[2], p[3]])]
      : trace.points.filter(p => p[0] <= time).map(p => [p[1], p[2]]);
    return [...pts, [now.x, now.y]];
  }
  function renderMap() {
    if (!caseRows.length) { $('map').innerHTML = '<div class="empty">Không có trace cho case này. Chọn task seed đã được lưu trace.</div>'; $('flight-details').innerHTML = ''; return; }
    const focused = caseRows.find(r => r.policy === state.focus) || caseRows[0], trace = ds().traces[focused.traceId], nodes = ds().layouts[trace.layout];
    const W = 740, H = 472, L = 60, T = 24, size = 400, area = trace.area;
    const x = v => L + v / area * size, y = v => T + size - v / area * size;
    let s = `<rect x="${L}" y="${T}" width="${size}" height="${size}" fill="var(--soft)" rx="3"/>`;
    for (let i = 0; i <= 4; i++) { const v = i / 4 * area; s += `<path d="M${x(v)},${T}V${T + size}M${L},${y(v)}H${L + size}" class="grid-line"/>${text(x(v), T + size + 23, fmt(v, 0), 'axis', 'text-anchor="middle"')}${text(L - 12, y(v) + 4, fmt(v, 0), 'axis', 'text-anchor="end"')}`; }
    s += text(L + size / 2, 469, 'x (m)', 'axis', 'text-anchor="middle"') + text(17, 18, 'y (m)', 'axis');
    for (const row of caseRows) {
      if (!state.visible.has(row.policy)) continue;
      const tr = ds().traces[row.traceId], t = Math.min(state.time, row.seconds), p = pointAt(tr, t), focus = row.policy === state.focus;
      const full = wholePath(tr).map(p => `${x(p[0])},${y(p[1])}`).join(' ');
      const current = elapsedPath(tr, t, p).map(p => `${x(p[0])},${y(p[1])}`).join(' ');
      s += `<polyline points="${full}" fill="none" stroke="${COLORS[row.policy]}" stroke-width="1.2" opacity=".12"/>`;
      s += `<polyline points="${current}" fill="none" stroke="${COLORS[row.policy]}" stroke-width="${focus ? 2.8 : 1.6}" opacity="${focus ? .95 : .5}"/>`;
      if (focus && $('coverage').checked && !p.moving && state.time < row.seconds) s += `<circle cx="${x(p.x)}" cy="${y(p.y)}" r="${Math.sqrt(tr.range ** 2 - tr.altitude ** 2) / area * size}" fill="${COLORS[row.policy]}" opacity=".09"/>`;
    }
    for (const n of nodes) {
      const title = `Thiết bị ${n.id} · (${fmt(n.x, 1)}, ${fmt(n.y, 1)}) m · ${n.connected ? 'có' : 'mất'} kết nối · ${n.powered ? 'có nguồn ngoài' : 'dùng pin'} · ${n.hardware} / ${n.task}`;
      s += n.connected ? `<circle cx="${x(n.x)}" cy="${y(n.y)}" r="6" fill="var(--surface)" stroke="var(--muted)" stroke-width="1.5" data-tip="${esc(title)}"/>` : `<rect x="${x(n.x) - 5.5}" y="${y(n.y) - 5.5}" width="11" height="11" rx="1" fill="var(--surface)" stroke="var(--muted)" stroke-width="1.5" data-tip="${esc(title)}"/>`;
      s += text(x(n.x) + 9, y(n.y) - 7, `${n.id}${n.powered ? ' P' : ''}`, 'axis');
    }
    for (const row of caseRows) {
      if (!state.visible.has(row.policy)) continue;
      const p = pointAt(ds().traces[row.traceId], Math.min(state.time, row.seconds)), focused = row.policy === state.focus;
      s += `<circle cx="${x(p.x)}" cy="${y(p.y)}" r="${focused ? 8 : 5}" fill="${COLORS[row.policy]}" stroke="var(--surface)" stroke-width="2" data-tip="${esc(`${LABELS[row.policy]} · (${fmt(p.x, 1)}, ${fmt(p.y, 1)}) m · pin ${fmt(p.battery / 1000)} kJ${state.time >= row.seconds ? ' · đã kết thúc' : ''}`)}"/>`;
    }
    s += text(505, 45, 'Cùng task seed ' + state.task, 'chart-label') + text(505, 69, `Layout ${focused.layout} · H = ${trace.altitude} m`, 'axis');
    caseRows.forEach((r, i) => { s += `<circle cx="510" cy="${105 + i * 44}" r="4" fill="${COLORS[r.policy]}"/>${text(522, 109 + i * 44, LABELS[r.policy], 'chart-label')}${text(522, 126 + i * 44, state.time >= r.seconds ? `Kết thúc · ${fmt(r.seconds, 0)} s` : `${fmt(state.time, 0)} / ${fmt(r.seconds, 0)} s`, 'axis')}`; });
    $('map').innerHTML = svg(W, H, `Đường bay UAV trên vùng ${area} × ${area} mét`, s);
    const p = pointAt(trace, Math.min(state.time, focused.seconds)), ended = state.time >= focused.seconds;
    $('flight-policy').textContent = LABELS[focused.policy];
    $('flight-status').textContent = ended ? 'Đã kết thúc' : p.moving ? 'Đang bay' : 'Đang hover';
    const details = [['Vị trí (x, y)', `${fmt(p.x, 1)}, ${fmt(p.y, 1)} m`], ['Pin UAV còn', `${fmt(p.battery / 1000)} kJ`], ['Thiết bị đích', `#${p.action}`]];
    if (trace.kind === 'paper') details.push(['Slot đang xem', `${p.slot} / ${p.totalSlots}`], ['Tuổi dữ liệu lớn nhất', `${p.age} slot`]);
    details.push(['Kết thúc do', ended ? focused.reason : 'Chưa kết thúc']);
    $('flight-details').innerHTML = details.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('');
    $('map-caption').textContent = `${area} × ${area} m · UAV H=${trace.altitude} m · v=${trace.speed} m/s · bán kính chiếu ≈${fmt(Math.sqrt(trace.range ** 2 - trace.altitude ** 2), 1)} m`;
    $('trace-note').textContent = trace.kind === 'paper' ? 'Bay thẳng ở 5 m/s rồi hover; vị trí, pin và age tại mốc slot lấy từ trace. Không nội suy age giữa slot.' : 'Vị trí và pin nội suy giữa các event đã lưu. Mobile pilot chỉ lưu trace của task đầu.';
    $('time-label').textContent = `${fmt(state.time, 0)} / ${fmt(state.maxTime, 0)} s`;
    $('time').value = state.time;
  }
  function renderProvenance() {
    $('provenance').innerHTML = `<div><strong>${esc(ds().audit)}</strong><br>Nguồn: <code>${esc(ds().source)}</code><br>${esc(ds().note)}<br>Energy paper = năng lượng UAV; energy mobile = tổng ground + UAV. Không gộp hai môi trường.<br>Điểm best/final dùng cùng case; không tính thành mẫu độc lập bổ sung. SD hoặc chấm không phải kiểm định thống kê.<br>Xuất bảng CSV chỉ tạo file kết quả hiển thị; không sửa raw outputs hoặc model.</div>`;
  }
  function renderAll() {
    const groups = aggregates(); renderStats(groups); renderBars(groups); renderStability(); renderTable(groups); renderValidation(); renderProvenance();
    $('scope-note').textContent = ds().note;
    $('run-stamp').textContent = ds().budget;
    const seeds = [...new Set(selected().filter(r => r.policy === 'DQN' && r.traceId).map(r => r.seed))].sort((a, b) => a - b);
    if (!seeds.includes(state.seed)) state.seed = seeds[0]; options('seed', seeds, state.seed);
    $('seed-label').firstChild.textContent = ds().id === 'reference' ? 'Learning / layout seed' : 'Learning seed';
    const tasks = [...new Set(selected().filter(r => r.policy === 'DQN' && r.seed === state.seed && r.traceId).map(r => r.task))].sort((a, b) => a - b);
    if (!tasks.includes(state.task)) state.task = tasks[0]; options('task', tasks, state.task);
    setCase();
    document.documentElement.dataset.ready = 'true';
  }
  function selectDataset(id) {
    state.dataset = id; state.profile = ds().defaultProfile; state.checkpoint = 'best'; state.metric = ds().metrics[0];
    options('profile', ds().profiles, state.profile, PROFILE); options('metric', ds().metrics, state.metric, Object.fromEntries(ds().metrics.map(k => [k, metricName(k)])));
    $('checkpoint').value = 'best'; $('checkpoint').disabled = ds().kind === 'mobile';
    $('checkpoint').options[1].textContent = ds().kind === 'mobile' ? 'Không có final test trace' : 'Final đúng 1 triệu bước';
    renderAll();
  }
  function metricName(k) { return k === 'energy' && ds().kind === 'mobile' ? 'Tổng năng lượng hệ thống (kJ)' : METRICS[k].name; }
  function pause() { state.playing = false; if (state.animation) cancelAnimationFrame(state.animation); state.animation = null; $('play').textContent = 'Phát đường bay'; }
  function play() {
    if (state.playing) { pause(); return; }
    if (state.time >= state.maxTime) state.time = 0;
    state.playing = true; $('play').textContent = 'Tạm dừng'; let previous = performance.now();
    const frame = now => { if (!state.playing) return; state.time = Math.min(state.maxTime, state.time + (now - previous) / 1000 * state.maxTime / 40 * Number($('speed').value)); previous = now; renderMap(); if (state.time >= state.maxTime) pause(); else state.animation = requestAnimationFrame(frame); };
    state.animation = requestAnimationFrame(frame);
  }
  function exportCsv() {
    const groups = aggregates(), rows = [['dataset', 'profile', 'checkpoint_DQN', 'policy', 'metric', 'mean', 'episode_count'], ...groups.map(g => [ds().id, state.profile, state.checkpoint, g.policy, metric().name, g.average, g.rows.length])];
    const csv = '\ufeff' + rows.map(row => row.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], {type: 'text/csv;charset=utf-8'})), link = document.createElement('a');
    link.href = url; link.download = `uav-${ds().id}-${state.profile}-${state.checkpoint}-${state.metric}.csv`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  options('dataset', DATA.datasets.map(d => d.id), state.dataset, Object.fromEntries(DATA.datasets.map(d => [d.id, d.title])));
  options('focus', POLICIES, state.focus, LABELS);
  $('build-date').textContent = '· ' + DATA.built.slice(0, 10);
  $('policy-toggles').innerHTML = POLICIES.map(p => `<button data-policy="${p}" aria-pressed="true"><span class="swatch" style="--series:${COLORS[p]}"></span>${LABELS[p]}</button>`).join('');
  $('dataset').addEventListener('change', () => selectDataset($('dataset').value));
  $('profile').addEventListener('change', () => { state.profile = $('profile').value; renderAll(); });
  $('checkpoint').addEventListener('change', () => { state.checkpoint = $('checkpoint').value; renderAll(); });
  $('metric').addEventListener('change', () => { state.metric = $('metric').value; renderAll(); });
  $('seed').addEventListener('change', () => { state.seed = Number($('seed').value); renderAll(); });
  $('task').addEventListener('change', () => { state.task = Number($('task').value); setCase(); });
  $('focus').addEventListener('change', () => { state.focus = $('focus').value; renderMap(); });
  $('coverage').addEventListener('change', renderMap);
  $('time').addEventListener('input', () => { pause(); state.time = Number($('time').value); renderMap(); });
  $('play').addEventListener('click', play);
  $('rewind').addEventListener('click', () => { pause(); state.time = 0; renderMap(); });
  $('export').addEventListener('click', exportCsv);
  $('theme').addEventListener('click', () => { const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = next; try { localStorage.setItem('uav-lab-theme', next); } catch {} });
  $('policy-toggles').addEventListener('click', e => { const b = e.target.closest('button[data-policy]'); if (!b) return; const p = b.dataset.policy; if (state.visible.has(p)) { if (state.visible.size > 1) state.visible.delete(p); } else state.visible.add(p); b.setAttribute('aria-pressed', String(state.visible.has(p))); renderMap(); });
  document.addEventListener('pointerover', e => { const target = e.target.closest('[data-tip]'); if (!target) return; $('tooltip').textContent = target.dataset.tip; $('tooltip').hidden = false; });
  document.addEventListener('pointermove', e => { const t = $('tooltip'); t.style.left = Math.min(e.clientX + 14, window.innerWidth - t.offsetWidth - 12) + 'px'; t.style.top = Math.min(e.clientY + 14, window.innerHeight - t.offsetHeight - 12) + 'px'; });
  document.addEventListener('pointerout', e => { if (e.target.closest('[data-tip]')) $('tooltip').hidden = true; });
  document.documentElement.dataset.theme = 'light';
  selectDataset(state.dataset);
  window.UAVDashboard = {data: DATA, state, selectDataset, aggregates, pointAt, pause, renderAll, renderMap,
    set: patch => { Object.assign(state, patch); options('profile', ds().profiles, state.profile, PROFILE); $('checkpoint').value = state.checkpoint; $('metric').value = state.metric; renderAll(); }};
})();
