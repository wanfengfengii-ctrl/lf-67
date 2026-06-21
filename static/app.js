const API = '/api';
let lastResult = null;
let lastReq = null;
let lastMultiResult = null;
let selectedSchemeId = null;

function getFormData() {
    const v = id => document.getElementById(id).value;
    const humidity = v('humidity');
    const maxLayers = v('max_layers');
    return {
        cabin: {
            length: parseFloat(v('cabin_length')),
            width: parseFloat(v('cabin_width')),
            height: parseFloat(v('cabin_height'))
        },
        bag: {
            length: parseFloat(v('bag_length')),
            width: parseFloat(v('bag_width')),
            height: parseFloat(v('bag_height')),
            weight: parseFloat(v('bag_weight'))
        },
        layers: parseInt(v('layers')),
        grain_type: v('grain_type'),
        humidity: humidity === '' ? null : parseFloat(humidity),
        voyage_days: parseInt(v('voyage_days')),
        loading_order: v('loading_order'),
        sea_state: v('sea_state'),
        max_loss_rate: parseFloat(v('max_loss_rate')),
        max_layers: maxLayers === '' ? null : parseInt(maxLayers),
        priority_target: v('priority_target')
    };
}

function getBatchFormData() {
    const v = id => document.getElementById(id).value;
    const maxLayers = v('max_layers');
    const humidities = v('batch_humidities')
        .split(/[,，\s]+/)
        .map(s => parseFloat(s.trim()))
        .filter(n => !isNaN(n) && n >= 0 && n <= 100);
    const seaStates = [];
    document.querySelectorAll('#batch_sea_states input[type="checkbox"]:checked').forEach(cb => {
        seaStates.push(cb.value);
    });
    return {
        cabin: {
            length: parseFloat(v('cabin_length')),
            width: parseFloat(v('cabin_width')),
            height: parseFloat(v('cabin_height'))
        },
        bag: {
            length: parseFloat(v('bag_length')),
            width: parseFloat(v('bag_width')),
            height: parseFloat(v('bag_height')),
            weight: parseFloat(v('bag_weight'))
        },
        grain_type: v('grain_type'),
        voyage_days: parseInt(v('voyage_days')),
        loading_order: v('loading_order'),
        humidity_values: humidities,
        sea_state_values: seaStates,
        layers: parseInt(v('layers')),
        max_loss_rate: parseFloat(v('max_loss_rate')),
        max_layers: maxLayers === '' ? null : parseInt(maxLayers),
        priority_target: v('priority_target')
    };
}

const GRAIN_LABELS = {
    rice: '稻米', wheat: '小麦', millet: '粟米', sorghum: '高粱', soybean: '大豆'
};
const ORDER_LABELS = {
    bottom_heavy: '底层加重', top_heavy: '顶层加重', even: '均匀分布', pyramid: '金字塔式'
};
const SEA_STATE_LABELS = {
    calm: '平静', slight: '轻微摇晃', moderate: '中等摇晃', rough: '剧烈摇晃', very_rough: '极端摇晃'
};
const PRIORITY_LABELS = {
    min_loss: '最小损耗优先', max_capacity: '最大容量优先',
    min_pressure: '最低承压优先', balance: '综合平衡'
};

async function apiCall(endpoint, body) {
    const res = await fetch(API + endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '请求失败' }));
        throw new Error(err.detail || '模拟计算出错');
    }
    return res.json();
}

function setButtonLoading(loading, text) {
    const btn = document.getElementById('btn_simulate');
    btn.disabled = loading;
    btn.textContent = loading ? text : '▶ 当前方案模拟';
}

async function runSimulation() {
    setButtonLoading(true, '计算中...');
    try {
        const req = getFormData();
        const result = await apiCall('/simulate', req);
        lastResult = result;
        lastReq = req;
        renderResult(req, result);
    } catch (e) {
        alert('模拟失败: ' + e.message);
    } finally {
        setButtonLoading(false);
    }
}

async function runComparison() {
    setButtonLoading(true, '对比中...');
    try {
        const req = getFormData();
        const result = await apiCall('/compare', req);
        lastReq = req;
        renderComparison(req, result);
    } catch (e) {
        alert('对比失败: ' + e.message);
    } finally {
        setButtonLoading(false);
    }
}

async function runMultiSchemes() {
    setButtonLoading(true, '生成方案中...');
    try {
        const req = getFormData();
        const result = await apiCall('/multi-schemes', req);
        lastMultiResult = result;
        lastReq = req;
        selectedSchemeId = result.best_scheme_id;
        renderMultiSchemes(req, result);
    } catch (e) {
        alert('生成方案失败: ' + e.message);
    } finally {
        setButtonLoading(false);
    }
}

async function runBatchCompare() {
    setButtonLoading(true, '批量计算中...');
    try {
        const req = getBatchFormData();
        if (req.humidity_values.length === 0) {
            alert('请至少填写一个有效的湿度值');
            return;
        }
        if (req.sea_state_values.length === 0) {
            alert('请至少勾选一个海况');
            return;
        }
        const result = await apiCall('/batch-compare', req);
        lastReq = req;
        renderBatchCompare(req, result);
    } catch (e) {
        alert('批量对比失败: ' + e.message);
    } finally {
        setButtonLoading(false);
    }
}

function renderWarnings(r) {
    if (!r.warnings || r.warnings.length === 0) return '';
    const hasDanger = r.is_high_risk;
    return `<div class="warnings-box ${hasDanger ? 'danger-box' : ''}">
        <h4>${hasDanger ? '⚠ 严重警告 / 高风险方案' : '⚠ 提示信息'}</h4>
        <ul>${r.warnings.map(w => `<li>${w}</li>`).join('')}</ul>
    </div>`;
}

function renderMitigationAdvice(advice) {
    const sections = [
        { key: 'pressure_advice', cls: 'pressure', title: '🔧 承压控制建议', icon: '📐' },
        { key: 'moisture_advice', cls: 'moisture', title: '💧 防潮防霉建议', icon: '💧' },
        { key: 'loss_advice', cls: 'loss', title: '📉 降损建议', icon: '📉' },
        { key: 'stability_advice', cls: 'stability', title: '⚓ 稳性与安全建议', icon: '⚓' },
        { key: 'general_advice', cls: 'general', title: '📋 通用建议', icon: '📋' }
    ];
    let html = '';
    sections.forEach(s => {
        const items = advice[s.key] || [];
        if (items.length === 0) return;
        html += `<div class="advice-card ${s.cls}">
            <h4>${s.title}</h4>
            <ul>${items.map(i => `<li>${i}</li>`).join('')}</ul>
        </div>`;
    });
    if (!html) return '';
    return `<div class="viz-panel">
        <h3>🛡 风险处置建议</h3>
        <div class="advice-grid">${html}</div>
    </div>`;
}

function renderResultCards(r) {
    const fsColor = r.feasibility_score >= 75 ? 'var(--success)' : r.feasibility_score >= 50 ? 'var(--warn)' : 'var(--danger)';
    return `<div class="result-cards">
        <div class="result-card pressure">
            <div class="label">底层承压</div>
            <div class="value">${r.bottom_pressure_kpa.toFixed(2)} <span style="font-size:14px;color:var(--text2)">kPa</span></div>
            <div class="sub">平均 ${r.avg_pressure_kpa.toFixed(2)} kPa</div>
        </div>
        <div class="result-card moisture">
            <div class="label">受潮风险</div>
            <div class="value">${r.moisture_risk_level}</div>
            <div class="sub">风险指数 ${r.moisture_risk_score.toFixed(3)}</div>
        </div>
        <div class="result-card loss">
            <div class="label">预计损耗率 ${!r.is_formal_assessment ? '<span class="badge badge-warn" style="margin-left:6px;font-size:10px;">非正式</span>' : ''}</div>
            <div class="value" style="color:${!r.is_formal_assessment ? 'var(--text2)' : r.estimated_loss_rate > 10 ? 'var(--danger)' : r.estimated_loss_rate > 5 ? 'var(--warn)' : 'var(--text)'}; opacity:${r.is_formal_assessment ? 1 : 0.6}">${r.estimated_loss_rate.toFixed(2)}%</div>
            <div class="sub">压缩率 ${r.max_compression_ratio.toFixed(3)}${!r.is_formal_assessment ? ' · 湿度缺失仅供参考' : ''}</div>
        </div>
        <div class="result-card feasibility">
            <div class="label">可执行性评分</div>
            <div class="value" style="color:${fsColor}">${r.feasibility_score.toFixed(0)}<span style="font-size:14px;color:var(--text2)">分</span></div>
            <div class="sub">${r.can_execute ? '<span class="badge badge-success">可执行</span>' : '<span class="badge badge-danger">不可执行</span>'} · ${r.is_high_risk ? '<span class="badge badge-danger">高风险</span>' : '<span class="badge badge-success">风险可控</span>'}</div>
        </div>
    </div>`;
}

function renderResult(req, r) {
    const main = document.getElementById('main_content');
    let html = '';

    html += `<h2 style="font-size:16px;margin-bottom:16px;display:flex;align-items:center;gap:10px;">
        📊 当前方案评估结果
        <span class="priority-tag">优先目标：${PRIORITY_LABELS[req.priority_target] || req.priority_target}</span>
    </h2>`;

    html += renderWarnings(r);
    html += renderResultCards(r);

    html += `<div class="viz-section">
        <div class="viz-panel no-margin">
            <h3>📐 舱内堆码剖面图</h3>
            <div class="canvas-wrap"><canvas id="crossSection" width="480" height="320"></canvas></div>
        </div>
        <div class="viz-panel no-margin">
            <h3>📊 各层承压分布</h3>
            <div class="canvas-wrap"><canvas id="pressureChart" width="480" height="320"></canvas></div>
        </div>
    </div>`;

    html += `<div class="viz-panel">
        <h3>📋 各层详情（共${req.layers}层 · ${r.total_bags}包 · 容量${r.capacity_used_pct.toFixed(1)}%）</h3>
        <table class="layer-detail-table">
            <tr><th>层号</th><th>粮包数</th><th>承压 (kPa)</th><th>压力分布</th><th>受潮风险</th></tr>
            ${r.layer_details.map(l => {
                const maxP = Math.max(...r.layer_details.map(x => x.pressure_kpa), 0.01);
                const pct = (l.pressure_kpa / maxP * 100).toFixed(0);
                const color = l.pressure_kpa > 5 ? 'var(--danger)' : l.pressure_kpa > 2 ? 'var(--warn)' : 'var(--accent)';
                const mColor = l.moisture_risk > 0.6 ? 'var(--danger)' : l.moisture_risk > 0.3 ? 'var(--warn)' : 'var(--success)';
                return `<tr>
                    <td>${l.layer}</td>
                    <td>${l.bags_count}</td>
                    <td>${l.pressure_kpa.toFixed(3)}</td>
                    <td><div class="pressure-bar"><div class="pressure-bar-fill" style="width:${pct}%;background:${color}"></div></div></td>
                    <td style="color:${mColor}">${(l.moisture_risk * 100).toFixed(1)}%</td>
                </tr>`;
            }).join('')}
        </table>
    </div>`;

    html += renderMitigationAdvice(r.mitigation_advice || {});

    main.innerHTML = html;

    requestAnimationFrame(() => {
        drawCrossSection(req, r);
        drawPressureChart(r);
    });
}

function renderComparison(req, comp) {
    const main = document.getElementById('main_content');
    const best = comp.best_order;

    const formalBadge = !comp.is_formal_assessment ? '<span class="badge badge-warn" style="margin-left:8px;font-size:11px;">非正式评估</span>' : '';
    let html = `<h2 style="font-size:16px;margin-bottom:16px;">⚖ 装载方式对比 ${formalBadge} <span style="font-size:12px;color:var(--text2);font-weight:400;">（最优方案: ${ORDER_LABELS[best]}，损耗率 ${comp.best_loss_rate.toFixed(2)}%）</span></h2>`;

    html += `<div class="viz-panel">
        <h3>📋 方案对比表</h3>
        <table class="comparison-table">
            <tr>
                <th>装载方式</th>
                <th>底层承压</th>
                <th>受潮风险</th>
                <th>损耗率</th>
                <th>可行性</th>
                <th>风险等级</th>
                <th>状态</th>
            </tr>
            ${comp.items.map(item => {
                const r = item.result;
                const isBest = item.loading_order === best;
                const riskBadge = r.is_high_risk
                    ? '<span class="badge badge-danger">高风险</span>'
                    : r.estimated_loss_rate > 5
                        ? '<span class="badge badge-warn">中风险</span>'
                        : '<span class="badge badge-success">低风险</span>';
                const execBadge = r.can_execute
                    ? '<span class="badge badge-success">可执行</span>'
                    : '<span class="badge badge-danger">不可执行</span>';
                const fsColor = r.feasibility_score >= 75 ? 'var(--success)' : r.feasibility_score >= 50 ? 'var(--warn)' : 'var(--danger)';
                return `<tr class="${isBest ? 'best' : ''}">
                    <td>${ORDER_LABELS[item.loading_order]} ${isBest ? '⭐' : ''}</td>
                    <td>${r.bottom_pressure_kpa.toFixed(2)} kPa</td>
                    <td>${r.moisture_risk_level} (${r.moisture_risk_score.toFixed(2)})</td>
                    <td style="font-weight:600;color:${r.estimated_loss_rate > 10 ? 'var(--danger)' : 'var(--text)'}">${r.estimated_loss_rate.toFixed(2)}%</td>
                    <td style="color:${fsColor};font-weight:600;">${r.feasibility_score.toFixed(0)}分</td>
                    <td>${riskBadge}</td>
                    <td>${execBadge}</td>
                </tr>`;
            }).join('')}
        </table>
    </div>`;

    html += `<div class="viz-section">
        <div class="viz-panel no-margin">
            <h3>📊 损耗率对比</h3>
            <div class="canvas-wrap"><canvas id="compChart" width="480" height="300"></canvas></div>
        </div>
        <div class="viz-panel no-margin">
            <h3>📊 底层承压对比</h3>
            <div class="canvas-wrap"><canvas id="compPressure" width="480" height="300"></canvas></div>
        </div>
    </div>`;

    html += `<div class="viz-section">
        <div class="viz-panel no-margin">
            <h3>📊 可行性评分对比</h3>
            <div class="canvas-wrap"><canvas id="compFeasibility" width="480" height="300"></canvas></div>
        </div>
        <div class="viz-panel no-margin">
            <h3>📊 受潮风险对比</h3>
            <div class="canvas-wrap"><canvas id="compMoisture" width="480" height="300"></canvas></div>
        </div>
    </div>`;

    main.innerHTML = html;
    requestAnimationFrame(() => {
        drawComparisonCharts(comp);
    });
}

let multiFilter = 'all';

function renderMultiSchemes(req, ms) {
    const main = document.getElementById('main_content');
    const priorityTag = `<span class="priority-tag">优先目标：${PRIORITY_LABELS[ms.priority_target] || ms.priority_target}</span>`;

    if (selectedSchemeId) {
        const scheme = ms.schemes.find(s => s.scheme_id === selectedSchemeId);
        if (scheme) {
            renderMultiSchemeDetail(req, ms, scheme);
            return;
        }
    }

    let html = `<h2 style="font-size:16px;margin-bottom:16px;">
        🎯 智能装载方案推荐 ${priorityTag}
        ${!ms.is_formal_assessment ? '<span class="badge badge-warn" style="margin-left:8px;font-size:11px;">非正式评估(缺湿度)</span>' : ''}
    </h2>`;

    html += `<div class="scheme-stats">
        <div class="scheme-stat recommended"><div class="num">${ms.recommended_count}</div><div class="label">✅ 推荐方案</div></div>
        <div class="scheme-stat alternative"><div class="num">${ms.alternative_count}</div><div class="label">🔵 备选方案</div></div>
        <div class="scheme-stat highrisk"><div class="num">${ms.high_risk_count}</div><div class="label">🔴 高风险(不推荐)</div></div>
        <div class="scheme-stat informal"><div class="num">${ms.informal_count}</div><div class="label">🟡 非正式</div></div>
    </div>`;

    html += `<div class="scheme-tabs">
        <div class="scheme-tab ${multiFilter==='all'?'active':''}" onclick="setMultiFilter('all')">全部方案 (${ms.schemes.length})</div>
        <div class="scheme-tab ${multiFilter==='recommended'?'active':''}" onclick="setMultiFilter('recommended')">✅ 推荐 (${ms.recommended_count})</div>
        <div class="scheme-tab ${multiFilter==='alternative'?'active':''}" onclick="setMultiFilter('alternative')">🔵 备选 (${ms.alternative_count})</div>
        <div class="scheme-tab ${multiFilter==='high_risk'?'active':''}" onclick="setMultiFilter('high_risk')">🔴 高风险 (${ms.high_risk_count})</div>
    </div>`;

    const statusMap = { recommended: 'recommended', alternative: 'alternative', high_risk: 'highrisk', informal: 'informal' };
    const filteredSchemes = multiFilter === 'all' ? ms.schemes : ms.schemes.filter(s => s.status === multiFilter);

    html += `<div class="scheme-cards">`;
    filteredSchemes.forEach(s => {
        const r = s.result;
        const statusClass = statusMap[s.status] || 'alternative';
        const isBest = s.scheme_id === ms.best_scheme_id;
        const fsColor = r.feasibility_score >= 75 ? 'var(--success)' : r.feasibility_score >= 50 ? 'var(--warn)' : 'var(--danger)';
        html += `<div class="scheme-card ${statusClass} ${isBest?'best':''}" onclick="selectScheme('${s.scheme_id}')">
            <div class="scheme-card-header">
                <div class="scheme-card-title">${s.rank}. ${s.scheme_name} ${isBest?'⭐':''}</div>
                <div class="scheme-card-rank">${s.rank}</div>
            </div>
            <div class="scheme-card-meta">
                <span>装载: <b>${ORDER_LABELS[s.loading_order]}</b></span>
                <span>层数: <b>${s.layers}层</b></span>
                <span>总包数: <b>${s.total_bags}包</b></span>
                <span>容量: <b>${r.capacity_used_pct.toFixed(1)}%</b></span>
            </div>
            <div class="scheme-card-scores">
                <div class="score-item loss"><div class="s-value">${r.estimated_loss_rate.toFixed(2)}%</div><div class="s-label">损耗率</div></div>
                <div class="score-item press"><div class="s-value">${r.bottom_pressure_kpa.toFixed(2)}</div><div class="s-label">承压(kPa)</div></div>
                <div class="score-item feas"><div class="s-value" style="color:${fsColor}">${r.feasibility_score.toFixed(0)}</div><div class="s-label">可行性分</div></div>
            </div>
        </div>`;
    });
    html += `</div>`;

    main.innerHTML = html;
}

function setMultiFilter(f) {
    multiFilter = f;
    if (lastMultiResult && lastReq) renderMultiSchemes(lastReq, lastMultiResult);
}

function selectScheme(id) {
    selectedSchemeId = id;
    if (lastMultiResult && lastReq) renderMultiSchemes(lastReq, lastMultiResult);
}

function renderMultiSchemeDetail(req, ms, scheme) {
    const main = document.getElementById('main_content');
    const r = scheme.result;
    const fakeReq = { ...req, layers: scheme.layers, loading_order: scheme.loading_order };

    const statusBadgeMap = {
        recommended: '<span class="badge badge-success">推荐方案</span>',
        alternative: '<span class="badge badge-info">备选方案</span>',
        high_risk: '<span class="badge badge-danger">高风险(不推荐)</span>',
        informal: '<span class="badge badge-warn">非正式评估</span>'
    };

    let html = `<div class="scheme-detail-wrap">`;
    html += `<button class="back-btn" onclick="backToSchemeList()">← 返回方案列表</button>`;
    html += `<h2 style="font-size:16px;margin-bottom:16px;">
        📋 方案详情：${scheme.scheme_name}
        ${statusBadgeMap[scheme.status] || ''}
        ${scheme.scheme_id === ms.best_scheme_id ? ' ⭐ 最优' : ''}
        <span class="priority-tag">综合得分 ${scheme.score.toFixed(1)}</span>
    </h2>`;

    html += renderWarnings(r);
    html += renderResultCards(r);

    html += `<div class="viz-section">
        <div class="viz-panel no-margin">
            <h3>📐 舱内堆码剖面图（${scheme.layers}层 · ${ORDER_LABELS[scheme.loading_order]}）</h3>
            <div class="canvas-wrap"><canvas id="crossSection" width="480" height="320"></canvas></div>
        </div>
        <div class="viz-panel no-margin">
            <h3>📊 各层承压分布</h3>
            <div class="canvas-wrap"><canvas id="pressureChart" width="480" height="320"></canvas></div>
        </div>
    </div>`;

    html += `<div class="viz-panel">
        <h3>📋 各层详情</h3>
        <table class="layer-detail-table">
            <tr><th>层号</th><th>粮包数</th><th>承压 (kPa)</th><th>压力分布</th><th>受潮风险</th></tr>
            ${r.layer_details.map(l => {
                const maxP = Math.max(...r.layer_details.map(x => x.pressure_kpa), 0.01);
                const pct = (l.pressure_kpa / maxP * 100).toFixed(0);
                const color = l.pressure_kpa > 5 ? 'var(--danger)' : l.pressure_kpa > 2 ? 'var(--warn)' : 'var(--accent)';
                const mColor = l.moisture_risk > 0.6 ? 'var(--danger)' : l.moisture_risk > 0.3 ? 'var(--warn)' : 'var(--success)';
                return `<tr>
                    <td>${l.layer}</td>
                    <td>${l.bags_count}</td>
                    <td>${l.pressure_kpa.toFixed(3)}</td>
                    <td><div class="pressure-bar"><div class="pressure-bar-fill" style="width:${pct}%;background:${color}"></div></div></td>
                    <td style="color:${mColor}">${(l.moisture_risk * 100).toFixed(1)}%</td>
                </tr>`;
            }).join('')}
        </table>
    </div>`;

    html += renderMitigationAdvice(r.mitigation_advice || {});
    html += `</div>`;

    main.innerHTML = html;

    requestAnimationFrame(() => {
        drawCrossSection(fakeReq, r);
        drawPressureChart(r);
    });
}

function backToSchemeList() {
    selectedSchemeId = null;
    if (lastMultiResult && lastReq) renderMultiSchemes(lastReq, lastMultiResult);
}

function renderBatchCompare(req, bc) {
    const main = document.getElementById('main_content');
    const bestCell = bc.best_cell;

    let html = `<h2 style="font-size:16px;margin-bottom:16px;">
        📊 湿度 × 海况 批量对比矩阵
        <span class="priority-tag">${bc.humidity_values.length}湿度 × ${bc.sea_state_values.length}海况</span>
        ${!bc.is_any_formal ? '<span class="badge badge-warn" style="margin-left:8px;font-size:11px;">含非正式</span>' : ''}
    </h2>`;

    if (bestCell) {
        html += `<div class="warnings-box" style="background:rgba(102,187,106,0.08);border-color:rgba(102,187,106,0.3);">
            <h4 style="color:var(--success)">★ 最优组合</h4>
            <ul>
                <li style="color:var(--success)">湿度 <b>${bestCell.humidity}%</b> + 海况 <b>${SEA_STATE_LABELS[bestCell.sea_state] || bestCell.sea_state}</b>，损耗率仅 <b>${bestCell.loss_rate.toFixed(2)}%</b></li>
            </ul>
        </div>`;
    }

    html += `<div class="viz-panel">
        <h3>📋 损耗率矩阵（点击单元格查看详情）</h3>
        <div class="batch-matrix">
            <table class="matrix-table">
                <thead>
                    <tr>
                        <th class="corner"></th>
                        ${bc.sea_state_values.map(ss => `<th>${SEA_STATE_LABELS[ss] || ss}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>`;

    bc.humidity_values.forEach((h, rowIdx) => {
        html += `<tr><th>湿度 ${h}%</th>`;
        bc.sea_state_values.forEach((ss, colIdx) => {
            const cell = bc.cells[rowIdx][colIdx];
            const isBest = bestCell && bestCell.row === rowIdx && bestCell.col === colIdx;
            if (cell.error) {
                html += `<td><div class="matrix-cell risk-high"><div class="error-msg">${cell.error.substring(0, 20)}</div></div></td>`;
            } else {
                const r = cell.result;
                const riskClass = r.is_high_risk ? 'risk-high' : r.estimated_loss_rate > 5 ? 'risk-medium' : 'risk-low';
                const lossColor = r.estimated_loss_rate > 10 ? 'var(--danger)' : r.estimated_loss_rate > 5 ? 'var(--warn)' : 'var(--success)';
                const mBadge = r.moisture_risk_score > 0.6
                    ? '<span class="moisture-tag" style="background:rgba(239,83,80,0.2);color:var(--danger)">高湿</span>'
                    : r.moisture_risk_score > 0.3
                        ? '<span class="moisture-tag" style="background:rgba(255,183,77,0.2);color:var(--warn)">中湿</span>'
                        : '<span class="moisture-tag" style="background:rgba(102,187,106,0.2);color:var(--success)">低湿</span>';
                const hrBadge = r.is_high_risk ? '<br><span class="badge badge-danger" style="margin-top:4px;">高风险</span>' : '';
                html += `<td>
                    <div class="matrix-cell ${riskClass} ${isBest ? 'best' : ''}" onclick="viewBatchCell(${rowIdx}, ${colIdx})">
                        <div class="loss-val" style="color:${lossColor}">${r.estimated_loss_rate.toFixed(2)}%</div>
                        <div class="press-val">承压 ${r.bottom_pressure_kpa.toFixed(1)}kPa</div>
                        ${mBadge}
                        ${hrBadge}
                    </div>
                </td>`;
            }
        });
        html += `</tr>`;
    });

    html += `</tbody></table>
        </div>
        <div class="matrix-legend">
            <div class="legend-item"><div class="legend-box" style="background:rgba(102,187,106,0.05);"></div>低风险</div>
            <div class="legend-item"><div class="legend-box" style="background:rgba(255,183,77,0.06);"></div>中风险</div>
            <div class="legend-item"><div class="legend-box" style="background:rgba(239,83,80,0.08);"></div>高风险</div>
            <div class="legend-item"><div class="legend-box" style="box-shadow:inset 0 0 0 2px var(--success);"></div>最优组合</div>
        </div>
    </div>`;

    const allValid = [];
    bc.cells.forEach(row => row.forEach(cell => {
        if (cell.result && !cell.result.is_high_risk) allValid.push(cell);
    }));
    if (allValid.length > 1) {
        const labels = allValid.map(c => `${c.humidity}%/${SEA_STATE_LABELS[c.sea_state].substring(0,2)}`);
        html += `<div class="viz-section">
            <div class="viz-panel no-margin">
                <h3>📊 非高风险组合损耗率对比</h3>
                <div class="canvas-wrap"><canvas id="batchLossChart" width="600" height="300"></canvas></div>
            </div>
            <div class="viz-panel no-margin">
                <h3>📊 非高风险组合承压对比</h3>
                <div class="canvas-wrap"><canvas id="batchPressChart" width="600" height="300"></canvas></div>
            </div>
        </div>`;
        main.innerHTML = html;
        requestAnimationFrame(() => {
            const lossData = allValid.map(c => c.result.estimated_loss_rate);
            const pressData = allValid.map(c => c.result.bottom_pressure_kpa);
            drawBarCompare(document.getElementById('batchLossChart'), labels, lossData, '%', '损耗率');
            drawBarCompare(document.getElementById('batchPressChart'), labels, pressData, 'kPa', '底层承压');
        });
    } else {
        main.innerHTML = html;
    }

    window._lastBatchResult = bc;
    window._lastBatchReq = req;
}

function viewBatchCell(row, col) {
    const bc = window._lastBatchResult;
    const req = window._lastBatchReq;
    if (!bc) return;
    const cell = bc.cells[row][col];
    if (cell.error) {
        alert('该组合无法计算: ' + cell.error);
        return;
    }
    const r = cell.result;
    const simReq = {
        cabin: req.cabin, bag: req.bag,
        layers: req.layers || 6,
        grain_type: req.grain_type,
        humidity: cell.humidity,
        voyage_days: req.voyage_days,
        loading_order: req.loading_order,
        sea_state: cell.sea_state,
        max_loss_rate: req.max_loss_rate,
        max_layers: req.max_layers,
        priority_target: req.priority_target
    };
    lastResult = r;
    lastReq = simReq;
    renderResult(simReq, r);
}

function drawCrossSection(req, r) {
    const canvas = document.getElementById('crossSection');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const cabinL = req.cabin.length;
    const cabinH = req.cabin.height;
    const bagL = req.bag.length;
    const bagH = req.bag.height;
    const layers = r.layer_details.length;

    const margin = 40;
    const drawW = W - margin * 2;
    const drawH = H - margin * 2;
    const scale = Math.min(drawW / cabinL, drawH / cabinH);
    const cW = cabinL * scale;
    const cH = cabinH * scale;
    const oX = margin + (drawW - cW) / 2;
    const oY = margin + (drawH - cH) / 2;

    ctx.strokeStyle = '#4fc3f7';
    ctx.lineWidth = 2;
    ctx.strokeRect(oX, oY, cW, cH);
    ctx.fillStyle = 'rgba(79,195,247,0.06)';
    ctx.fillRect(oX, oY, cW, cH);

    ctx.font = '10px sans-serif';
    ctx.fillStyle = '#8899aa';
    ctx.textAlign = 'center';
    ctx.fillText(`${cabinL}m`, oX + cW / 2, oY - 8);
    ctx.save();
    ctx.translate(oX - 12, oY + cH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(`${cabinH}m`, 0, 0);
    ctx.restore();

    const bagsPerRow = Math.floor(cabinL / bagL);
    const bW = bagL * scale;
    const bH = bagH * scale;

    const maxPressure = Math.max(...r.layer_details.map(l => l.pressure_kpa), 0.01);

    for (let i = 0; i < layers; i++) {
        const info = r.layer_details[i];
        const pressureRatio = info.pressure_kpa / maxPressure;
        const y = oY + cH - (i + 1) * bH;
        const bagsInRow = Math.min(bagsPerRow, info.bags_count);

        for (let j = 0; j < bagsInRow; j++) {
            const x = oX + j * bW;
            const red = Math.round(79 + 160 * pressureRatio);
            const green = Math.round(195 - 120 * pressureRatio);
            const blue = Math.round(247 - 180 * pressureRatio);
            ctx.fillStyle = `rgba(${red},${green},${blue},0.7)`;
            ctx.fillRect(x + 1, y + 1, bW - 2, bH - 2);
            ctx.strokeStyle = `rgba(${red},${green},${blue},0.9)`;
            ctx.lineWidth = 0.5;
            ctx.strokeRect(x + 1, y + 1, bW - 2, bH - 2);
        }

        ctx.font = '10px sans-serif';
        ctx.fillStyle = '#e0e8f0';
        ctx.textAlign = 'right';
        ctx.fillText(`L${info.layer}`, oX - 4, y + bH / 2 + 4);
    }

    ctx.fillStyle = '#4fc3f7';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('舱内堆码剖面（侧视图）', W / 2, H - 6);

    const legendX = W - margin - 80;
    const legendY = margin + 10;
    ctx.font = '9px sans-serif';
    ctx.fillStyle = '#8899aa';
    ctx.textAlign = 'left';
    ctx.fillText('承压', legendX, legendY);
    const grad = ctx.createLinearGradient(legendX, legendY + 4, legendX + 70, legendY + 4);
    grad.addColorStop(0, 'rgba(79,195,247,0.7)');
    grad.addColorStop(1, 'rgba(239,83,80,0.7)');
    ctx.fillStyle = grad;
    ctx.fillRect(legendX, legendY + 8, 70, 8);
    ctx.fillStyle = '#8899aa';
    ctx.fillText('低', legendX, legendY + 28);
    ctx.fillText('高', legendX + 58, legendY + 28);
}

function drawPressureChart(r) {
    const canvas = document.getElementById('pressureChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const data = r.layer_details;
    const margin = { top: 20, right: 20, bottom: 40, left: 55 };
    const cW = W - margin.left - margin.right;
    const cH = H - margin.top - margin.bottom;

    const maxP = Math.max(...data.map(d => d.pressure_kpa), 0.01);
    const barW = cW / data.length * 0.7;
    const gap = cW / data.length;

    ctx.strokeStyle = '#2a4560';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 5; i++) {
        const y = margin.top + cH - (i / 5) * cH;
        ctx.beginPath();
        ctx.moveTo(margin.left, y);
        ctx.lineTo(W - margin.right, y);
        ctx.stroke();
        ctx.fillStyle = '#8899aa';
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText((maxP * i / 5).toFixed(1), margin.left - 6, y + 3);
    }

    data.forEach((d, i) => {
        const x = margin.left + i * gap + (gap - barW) / 2;
        const h = (d.pressure_kpa / maxP) * cH;
        const y = margin.top + cH - h;
        const ratio = d.pressure_kpa / maxP;
        const red = Math.round(79 + 160 * ratio);
        const green = Math.round(195 - 120 * ratio);
        const blue = Math.round(247 - 180 * ratio);
        const grad = ctx.createLinearGradient(x, y, x, y + h);
        grad.addColorStop(0, `rgba(${red},${green},${blue},0.9)`);
        grad.addColorStop(1, `rgba(${red},${green},${blue},0.5)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.roundRect(x, y, barW, h, [3, 3, 0, 0]);
        ctx.fill();
        ctx.fillStyle = '#e0e8f0';
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(d.pressure_kpa.toFixed(2), x + barW / 2, y - 4);
        ctx.fillText(`L${d.layer}`, x + barW / 2, margin.top + cH + 16);
    });

    ctx.fillStyle = '#8899aa';
    ctx.font = '9px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('承压 (kPa)', margin.left - 4, margin.top - 6);
}

function drawComparisonCharts(comp) {
    const canvas1 = document.getElementById('compChart');
    const canvas2 = document.getElementById('compPressure');
    const canvas3 = document.getElementById('compFeasibility');
    const canvas4 = document.getElementById('compMoisture');

    const items = comp.items;
    const labels = items.map(i => ORDER_LABELS[i.loading_order]);
    const lossData = items.map(i => i.result.estimated_loss_rate);
    const pressData = items.map(i => i.result.bottom_pressure_kpa);
    const feasData = items.map(i => i.result.feasibility_score);
    const moistData = items.map(i => +(i.result.moisture_risk_score * 100).toFixed(1));

    if (canvas1) drawBarCompare(canvas1, labels, lossData, '%', '损耗率');
    if (canvas2) drawBarCompare(canvas2, labels, pressData, 'kPa', '底层承压');
    if (canvas3) drawBarCompare(canvas3, labels, feasData, '分', '可行性');
    if (canvas4) drawBarCompare(canvas4, labels, moistData, '%', '受潮指数');
}

function drawBarCompare(canvas, labels, values, unit, title) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const margin = { top: 20, right: 20, bottom: 60, left: 55 };
    const cW = W - margin.left - margin.right;
    const cH = H - margin.top - margin.bottom;

    const maxV = Math.max(...values, 0.01);
    const barW = cW / labels.length * 0.6;
    const gap = cW / labels.length;

    const colors = ['#4fc3f7', '#ffb74d', '#66bb6a', '#ef5350', '#ab47bc', '#26c6da'];

    ctx.strokeStyle = '#2a4560';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 5; i++) {
        const y = margin.top + cH - (i / 5) * cH;
        ctx.beginPath();
        ctx.moveTo(margin.left, y);
        ctx.lineTo(W - margin.right, y);
        ctx.stroke();
        ctx.fillStyle = '#8899aa';
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText((maxV * i / 5).toFixed(1), margin.left - 6, y + 3);
    }

    labels.forEach((label, i) => {
        const x = margin.left + i * gap + (gap - barW) / 2;
        const h = (values[i] / maxV) * cH;
        const y = margin.top + cH - h;
        const grad = ctx.createLinearGradient(x, y, x, y + h);
        grad.addColorStop(0, colors[i % colors.length]);
        grad.addColorStop(1, colors[i % colors.length] + '80');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.roundRect(x, y, barW, h, [3, 3, 0, 0]);
        ctx.fill();
        ctx.fillStyle = '#e0e8f0';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(values[i].toFixed(2) + unit, x + barW / 2, y - 4);
        ctx.fillStyle = '#8899aa';
        ctx.font = '10px sans-serif';
        ctx.save();
        ctx.translate(x + barW / 2, margin.top + cH + 12);
        ctx.rotate(-Math.PI / 6);
        ctx.fillText(label, 0, 0);
        ctx.restore();
    });

    ctx.fillStyle = '#8899aa';
    ctx.font = '9px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(title + ' (' + unit + ')', margin.left - 4, margin.top - 6);
}

let autoSimulateTimer = null;
let lastAutoReq = null;

function scheduleAutoSimulate() {
    if (autoSimulateTimer) clearTimeout(autoSimulateTimer);
    autoSimulateTimer = setTimeout(() => {
        try {
            const req = getFormData();
            const reqStr = JSON.stringify(req);
            if (lastResult && reqStr !== lastAutoReq) {
                lastAutoReq = reqStr;
                apiCall('/simulate', req).then(result => {
                    lastResult = result;
                    lastReq = req;
                    renderResult(req, result);
                }).catch(() => {});
            }
        } catch (e) {}
    }, 600);
}

document.addEventListener('DOMContentLoaded', () => {
    const inputs = document.querySelectorAll('.panel input, .panel select');
    inputs.forEach(input => {
        input.addEventListener('input', scheduleAutoSimulate);
        input.addEventListener('change', scheduleAutoSimulate);
    });
});
