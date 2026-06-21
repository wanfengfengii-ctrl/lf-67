const API = '/api';
let lastResult = null;
let lastReq = null;
let lastMultiResult = null;
let selectedSchemeId = null;
let currentView = 'empty';
let isComputing = false;
let currentModule = 'sim';
let monitorEvents = [];

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

const BUTTON_TEXTS = {
    btn_simulate: '▶ 当前方案模拟',
    btn_multi: '🎯 智能生成多方案',
    btn_compare: '⚖ 对比装载方式',
    btn_batch: '📊 湿度×海况矩阵对比'
};

function setAllButtonsDisabled(disabled) {
    isComputing = disabled;
    ['btn_simulate', 'btn_multi', 'btn_compare', 'btn_batch'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.disabled = disabled;
    });
}

function setActiveButtonLoading(activeId, loadingText) {
    setAllButtonsDisabled(true);
    const btn = document.getElementById(activeId);
    if (btn) btn.textContent = loadingText;
}

function resetAllButtons() {
    setAllButtonsDisabled(false);
    Object.entries(BUTTON_TEXTS).forEach(([id, text]) => {
        const btn = document.getElementById(id);
        if (btn) btn.textContent = text;
    });
}

async function runSimulation() {
    if (isComputing) return;
    setActiveButtonLoading('btn_simulate', '计算中...');
    try {
        const req = getFormData();
        const result = await apiCall('/simulate', req);
        lastResult = result;
        lastReq = req;
        currentView = 'single';
        renderResult(req, result);
    } catch (e) {
        alert('模拟失败: ' + e.message);
    } finally {
        resetAllButtons();
    }
}

async function runComparison() {
    if (isComputing) return;
    setActiveButtonLoading('btn_compare', '对比中...');
    try {
        const req = getFormData();
        const result = await apiCall('/compare', req);
        lastReq = req;
        currentView = 'compare';
        renderComparison(req, result);
    } catch (e) {
        alert('对比失败: ' + e.message);
    } finally {
        resetAllButtons();
    }
}

async function runMultiSchemes() {
    if (isComputing) return;
    setActiveButtonLoading('btn_multi', '生成方案中...');
    try {
        const req = getFormData();
        const result = await apiCall('/multi-schemes', req);
        lastMultiResult = result;
        lastReq = req;
        selectedSchemeId = result.best_scheme_id;
        currentView = 'multi';
        renderMultiSchemes(req, result);
    } catch (e) {
        alert('生成方案失败: ' + e.message);
    } finally {
        resetAllButtons();
    }
}

async function runBatchCompare() {
    if (isComputing) return;
    setActiveButtonLoading('btn_batch', '批量计算中...');
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
        currentView = 'batch';
        renderBatchCompare(req, result);
    } catch (e) {
        alert('批量对比失败: ' + e.message);
    } finally {
        resetAllButtons();
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
    currentView = 'single';
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
        if (isComputing) return;
        if (currentView !== 'single') return;
        try {
            const req = getFormData();
            const reqStr = JSON.stringify(req);
            if (lastResult && reqStr !== lastAutoReq) {
                lastAutoReq = reqStr;
                apiCall('/simulate', req).then(result => {
                    lastResult = result;
                    lastReq = req;
                    if (currentView === 'single') {
                        renderResult(req, result);
                    }
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

    const today = new Date().toISOString().split('T')[0];
    const dateInput = document.getElementById('mon_record_date');
    if (dateInput) dateInput.value = today;
});

const WARNING_LEVEL_LABELS = {
    normal: '正常', low: '低风险预警', medium: '中风险预警',
    high: '高风险预警', critical: '极高风险预警'
};
const DISPOSAL_STATUS_LABELS = {
    pending: '待确认', confirmed: '已确认', processing: '处置中',
    completed: '已处置', closed: '已闭环'
};
const BAG_STATUS_LABELS = {
    normal: '正常', compressed: '压损变形', damp: '受潮',
    moldy: '发霉', damaged: '破损'
};
const ROCKING_LABELS = {
    calm: '平静', slight: '轻微', moderate: '中等', rough: '剧烈', very_rough: '极端'
};
const EVENT_LABELS = {
    humidity_spike: '湿度突升', temp_spike: '温度异常', pressure_worsen: '压损恶化',
    moisture_spread: '受潮扩散', bag_damage: '粮包破损', hull_shake: '船体剧烈摇晃',
    water_leak: '渗水漏水', other: '其他异常'
};

function switchModule(mod) {
    currentModule = mod;
    document.getElementById('nav_sim').classList.toggle('active', mod === 'sim');
    document.getElementById('nav_monitor').classList.toggle('active', mod === 'monitor');
    document.getElementById('panel_sim').style.display = mod === 'sim' ? '' : 'none';
    document.getElementById('panel_monitor').style.display = mod === 'monitor' ? '' : 'none';
    if (mod === 'monitor') {
        currentView = 'monitor_empty';
        const main = document.getElementById('main_content');
        main.innerHTML = `<div class="empty-state">
            <div class="icon">📡</div>
            <p>运输过程监测与预警处置模块</p>
            <div class="empty-hints">
                <div class="hint-card"><span class="hint-icon">📝</span><div><b>每日记录</b><p>按航行日期记录舱内环境与粮包状态</p></div></div>
                <div class="hint-card"><span class="hint-icon">⚠</span><div><b>预警处置</b><p>自动识别风险并给出预警等级与处置建议</p></div></div>
                <div class="hint-card"><span class="hint-icon">📊</span><div><b>趋势分析</b><p>查看风险趋势图与处置前后对比</p></div></div>
                <div class="hint-card"><span class="hint-icon">🚨</span><div><b>异常上报</b><p>紧急异常事件快速上报与闭环</p></div></div>
            </div>
        </div>`;
    } else {
        currentView = 'empty';
        const main = document.getElementById('main_content');
        main.innerHTML = `<div class="empty-state">
            <div class="icon">🚢</div>
            <p>配置左侧参数后选择操作模式开始</p>
            <div class="empty-hints">
                <div class="hint-card"><span class="hint-icon">▶</span><div><b>当前方案模拟</b><p>针对输入参数的单次详细评估</p></div></div>
                <div class="hint-card"><span class="hint-icon">🎯</span><div><b>智能生成多方案</b><p>自动组合层数×装载方式，按优先级推荐</p></div></div>
                <div class="hint-card"><span class="hint-icon">📊</span><div><b>湿度×海况矩阵</b><p>批量对比不同环境条件下的风险</p></div></div>
                <div class="hint-card"><span class="hint-icon">📡</span><div><b>运输过程监测</b><p>记录每日舱内环境与粮包状态，自动预警</p></div></div>
            </div>
        </div>`;
    }
}

function addMonitorEvent() {
    const type = document.getElementById('mon_event_type').value;
    const desc = document.getElementById('mon_event_desc').value;
    monitorEvents.push({ event_type: type, description: desc });
    document.getElementById('mon_event_desc').value = '';
    renderEventList();
}

function removeMonitorEvent(idx) {
    monitorEvents.splice(idx, 1);
    renderEventList();
}

function renderEventList() {
    const container = document.getElementById('mon_event_list');
    if (!container) return;
    if (monitorEvents.length === 0) {
        container.innerHTML = '<div style="font-size:12px;color:var(--text2);padding:4px 0;">暂无异常事件</div>';
        return;
    }
    container.innerHTML = monitorEvents.map((e, i) =>
        `<div class="event-tag">${EVENT_LABELS[e.event_type] || e.event_type}${e.description ? ' - ' + e.description : ''}<span class="event-remove" onclick="removeMonitorEvent(${i})">✕</span></div>`
    ).join('');
}

async function submitDailyRecord() {
    if (isComputing) return;
    const voyageId = document.getElementById('mon_voyage_id').value.trim();
    const recordDate = document.getElementById('mon_record_date').value;
    const humidity = parseFloat(document.getElementById('mon_humidity').value);
    const temperature = parseFloat(document.getElementById('mon_temperature').value);
    const rocking = document.getElementById('mon_rocking').value;
    const bagStatus = document.getElementById('mon_bag_status').value;
    const bagNote = document.getElementById('mon_bag_note').value;
    const note = document.getElementById('mon_note').value;

    if (!voyageId) { alert('请输入航次编号'); return; }
    if (!recordDate) { alert('请选择记录日期'); return; }

    const body = {
        voyage_id: voyageId,
        record_date: recordDate,
        cabin_humidity: humidity,
        cabin_temperature: temperature,
        rocking_level: rocking,
        bag_check_status: bagStatus,
        bag_check_note: bagNote,
        abnormal_events: monitorEvents.map(e => ({ event_type: e.event_type, description: e.description })),
        note: note
    };

    isComputing = true;
    try {
        const result = await apiCall('/monitor/daily-record', body);
        monitorEvents = [];
        renderEventList();
        renderMonitorRecordDetail(result);
    } catch (e) {
        alert('提交失败: ' + e.message);
    } finally {
        isComputing = false;
    }
}

function renderMonitorRecordDetail(rec) {
    const main = document.getElementById('main_content');
    const wLevel = WARNING_LEVEL_LABELS[rec.warning_level] || rec.warning_level;
    const wColor = { normal: 'var(--success)', low: 'var(--accent)', medium: 'var(--warn)', high: 'var(--danger)', critical: 'var(--danger)' }[rec.warning_level] || 'var(--text)';
    const bagLabel = BAG_STATUS_LABELS[rec.bag_check_status] || rec.bag_check_status;
    const rockLabel = ROCKING_LABELS[rec.rocking_level] || rec.rocking_level;

    let html = `<h2 style="font-size:16px;margin-bottom:16px;">📡 每日监测记录 — ${rec.record_date}</h2>`;

    html += `<div class="monitor-record-cards">
        <div class="result-card moisture">
            <div class="label">舱内湿度</div>
            <div class="value">${rec.cabin_humidity.toFixed(1)}<span style="font-size:14px;color:var(--text2)">%</span></div>
        </div>
        <div class="result-card pressure">
            <div class="label">舱内温度</div>
            <div class="value">${rec.cabin_temperature.toFixed(1)}<span style="font-size:14px;color:var(--text2)">°C</span></div>
        </div>
        <div class="result-card feasibility">
            <div class="label">风险指数</div>
            <div class="value" style="color:${wColor}">${rec.risk_score.toFixed(3)}</div>
            <div class="sub">${wLevel}</div>
        </div>
        <div class="result-card ${rec.warning_level === 'normal' ? '' : 'loss'}">
            <div class="label">运输状态</div>
            <div class="value" style="color:${rec.transport_status === '正常' ? 'var(--success)' : 'var(--danger)'}">${rec.transport_status}</div>
            <div class="sub">处置状态: ${DISPOSAL_STATUS_LABELS[rec.disposal_status] || rec.disposal_status}</div>
        </div>
    </div>`;

    html += `<div class="monitor-detail-grid">
        <div class="viz-panel"><h3>📋 记录详情</h3>
            <table class="layer-detail-table">
                <tr><th>项目</th><th>数值</th></tr>
                <tr><td>航次编号</td><td>${rec.voyage_id}</td></tr>
                <tr><td>记录日期</td><td>${rec.record_date}</td></tr>
                <tr><td>舱内湿度</td><td>${rec.cabin_humidity.toFixed(1)}%</td></tr>
                <tr><td>舱内温度</td><td>${rec.cabin_temperature.toFixed(1)}°C</td></tr>
                <tr><td>船体摇晃</td><td>${rockLabel}</td></tr>
                <tr><td>抽检粮包状态</td><td>${bagLabel}${rec.bag_check_note ? ' — ' + rec.bag_check_note : ''}</td></tr>
                <tr><td>风险指数</td><td style="color:${wColor};font-weight:700;">${rec.risk_score.toFixed(4)}</td></tr>
                <tr><td>预警等级</td><td style="color:${wColor};font-weight:700;">${wLevel}</td></tr>
                <tr><td>运输状态</td><td style="color:${rec.transport_status === '正常' ? 'var(--success)' : 'var(--danger)'}">${rec.transport_status}</td></tr>
                ${rec.note ? `<tr><td>备注</td><td>${rec.note}</td></tr>` : ''}
            </table>
        </div>
        <div class="viz-panel"><h3>⚠ 产生预警（${rec.warnings.length}条）</h3>`;

    if (rec.warnings.length === 0) {
        html += '<div style="color:var(--success);padding:10px;font-size:13px;">✅ 当日无预警</div>';
    } else {
        html += '<div class="warning-list">';
        rec.warnings.forEach(w => {
            const wl = WARNING_LEVEL_LABELS[w.warning_level] || w.warning_level;
            const wc = { normal: 'var(--success)', low: 'var(--accent)', medium: 'var(--warn)', high: 'var(--danger)', critical: 'var(--danger)' }[w.warning_level] || 'var(--text)';
            html += `<div class="warning-item level-${w.warning_level}">
                <div class="warning-header">
                    <span class="warning-level-badge" style="background:${wc}20;color:${wc}">${wl}</span>
                    <span class="warning-type">${EVENT_LABELS[w.warning_type] || w.warning_type}</span>
                </div>
                <div class="warning-msg">${w.warning_message}</div>
                <div class="warning-actions">
                    <span class="warning-disposal">处置: ${DISPOSAL_STATUS_LABELS[w.disposal_status] || w.disposal_status}</span>
                    ${w.disposal_status === 'pending' ? `<button class="btn-micro" onclick="confirmWarning('${w.warning_id}')">确认</button>` : ''}
                </div>
            </div>`;
        });
        html += '</div>';
    }
    html += `</div></div>`;

    if (rec.disposal_status !== 'completed' && rec.disposal_status !== 'closed') {
        html += `<div class="viz-panel">
            <h3>🔧 处置操作</h3>
            <div class="disposal-form">
                <div class="form-row-2">
                    <div class="form-group">
                        <label>处置状态</label>
                        <select id="disp_status_${rec.record_id}">
                            <option value="confirmed">已确认</option>
                            <option value="processing">处置中</option>
                            <option value="completed">已处置</option>
                            <option value="closed">已闭环</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>运输状态</label>
                        <select id="disp_transport_${rec.record_id}">
                            <option value="异常待处置" ${rec.transport_status !== '正常' ? 'selected' : ''}>异常待处置</option>
                            <option value="运输正常">运输正常</option>
                        </select>
                    </div>
                </div>
                <div class="form-group">
                    <label>处置措施</label>
                    <input type="text" id="disp_action_${rec.record_id}" placeholder="记录采取的处置措施">
                </div>
                <button class="btn-primary" onclick="submitDisposal('${rec.record_id}')">提交处置结果</button>
            </div>
        </div>`;
    }

    main.innerHTML = html;
}

async function confirmWarning(warningId) {
    try {
        await apiCall(`/monitor/warning/${warningId}/confirm`, { confirmed: true });
        alert('预警已确认');
    } catch (e) {
        alert('确认失败: ' + e.message);
    }
}

async function submitDisposal(recordId) {
    const status = document.getElementById(`disp_status_${recordId}`).value;
    const transport = document.getElementById(`disp_transport_${recordId}`).value;
    const action = document.getElementById(`disp_action_${recordId}`).value;

    try {
        const result = await apiCall(`/monitor/record/${recordId}/disposal`, {
            disposal_status: status,
            disposal_action: action,
            transport_status: transport
        });
        renderMonitorRecordDetail(result);
    } catch (e) {
        alert('处置提交失败: ' + e.message);
    }
}

async function queryVoyageRecords() {
    const voyageId = document.getElementById('mon_query_voyage').value.trim();
    if (!voyageId) { alert('请输入航次编号'); return; }

    try {
        const res = await fetch(`${API}/monitor/voyage/${encodeURIComponent(voyageId)}/records`);
        if (!res.ok) throw new Error('查询失败');
        const records = await res.json();
        renderVoyageRecordsList(voyageId, records);
    } catch (e) {
        alert('查询失败: ' + e.message);
    }
}

function renderVoyageRecordsList(voyageId, records) {
    const main = document.getElementById('main_content');

    let html = `<h2 style="font-size:16px;margin-bottom:16px;">📋 航次 ${voyageId} 每日监测记录（${records.length}天）</h2>`;

    if (records.length === 0) {
        html += '<div class="viz-panel"><p style="color:var(--text2);padding:20px;">暂无记录，请先提交每日监测数据</p></div>';
        main.innerHTML = html;
        return;
    }

    html += `<div class="viz-panel">
        <h3>📋 每日记录汇总</h3>
        <table class="monitor-table">
            <thead>
                <tr>
                    <th>日期</th><th>湿度(%)</th><th>温度(°C)</th><th>摇晃</th>
                    <th>粮包状态</th><th>风险指数</th><th>预警等级</th>
                    <th>运输状态</th><th>处置</th><th>操作</th>
                </tr>
            </thead>
            <tbody>`;

    records.forEach(r => {
        const wColor = { normal: 'var(--success)', low: 'var(--accent)', medium: 'var(--warn)', high: 'var(--danger)', critical: 'var(--danger)' }[r.warning_level] || 'var(--text)';
        const tColor = r.transport_status === '正常' ? 'var(--success)' : 'var(--danger)';
        html += `<tr>
            <td>${r.record_date}</td>
            <td>${r.cabin_humidity.toFixed(1)}</td>
            <td>${r.cabin_temperature.toFixed(1)}</td>
            <td>${ROCKING_LABELS[r.rocking_level] || r.rocking_level}</td>
            <td>${BAG_STATUS_LABELS[r.bag_check_status] || r.bag_check_status}</td>
            <td style="color:${wColor};font-weight:700;">${r.risk_score.toFixed(3)}</td>
            <td style="color:${wColor};">${WARNING_LEVEL_LABELS[r.warning_level] || r.warning_level}</td>
            <td style="color:${tColor};font-weight:600;">${r.transport_status}</td>
            <td>${DISPOSAL_STATUS_LABELS[r.disposal_status] || r.disposal_status}</td>
            <td><button class="btn-micro" onclick="viewRecordDetail('${r.record_id}')">详情</button></td>
        </tr>`;
    });

    html += '</tbody></table></div>';
    main.innerHTML = html;
}

async function viewRecordDetail(recordId) {
    try {
        const res = await fetch(`${API}/monitor/record/${encodeURIComponent(recordId)}`);
        if (!res.ok) throw new Error('获取失败');
        const rec = await res.json();
        renderMonitorRecordDetail(rec);
    } catch (e) {
        alert('获取详情失败: ' + e.message);
    }
}

async function queryVoyageWarnings() {
    const voyageId = document.getElementById('mon_query_voyage').value.trim();
    if (!voyageId) { alert('请输入航次编号'); return; }

    try {
        const res = await fetch(`${API}/monitor/voyage/${encodeURIComponent(voyageId)}/warnings`);
        if (!res.ok) throw new Error('查询失败');
        const warnings = await res.json();
        renderWarningsHistory(voyageId, warnings);
    } catch (e) {
        alert('查询失败: ' + e.message);
    }
}

function renderWarningsHistory(voyageId, warnings) {
    const main = document.getElementById('main_content');
    let html = `<h2 style="font-size:16px;margin-bottom:16px;">⚠ 航次 ${voyageId} 预警历史（${warnings.length}条）</h2>`;

    if (warnings.length === 0) {
        html += '<div class="viz-panel"><p style="color:var(--success);padding:20px;">✅ 该航次无预警记录</p></div>';
        main.innerHTML = html;
        return;
    }

    const pendingCount = warnings.filter(w => w.disposal_status === 'pending').length;
    const unresolvedCount = warnings.filter(w => !['completed', 'closed'].includes(w.disposal_status)).length;
    const closedCount = warnings.filter(w => ['completed', 'closed'].includes(w.disposal_status)).length;
    const highRiskCount = warnings.filter(w => ['high', 'critical'].includes(w.warning_level)).length;

    html += `<div class="scheme-stats">
        <div class="scheme-stat highrisk"><div class="num">${highRiskCount}</div><div class="label">🔴 高风险</div></div>
        <div class="scheme-stat alternative"><div class="num">${pendingCount}</div><div class="label">🔵 待确认</div></div>
        <div class="scheme-stat recommended"><div class="num">${closedCount}</div><div class="label">✅ 已闭环</div></div>
        <div class="scheme-stat informal"><div class="num">${unresolvedCount}</div><div class="label">🟡 未闭环</div></div>
    </div>`;

    html += '<div class="viz-panel"><div class="warning-list">';
    warnings.forEach(w => {
        const wl = WARNING_LEVEL_LABELS[w.warning_level] || w.warning_level;
        const wc = { normal: 'var(--success)', low: 'var(--accent)', medium: 'var(--warn)', high: 'var(--danger)', critical: 'var(--danger)' }[w.warning_level] || 'var(--text)';
        html += `<div class="warning-item level-${w.warning_level}">
            <div class="warning-header">
                <span class="warning-level-badge" style="background:${wc}20;color:${wc}">${wl}</span>
                <span class="warning-type">${EVENT_LABELS[w.warning_type] || w.warning_type}</span>
                <span class="warning-date">${w.record_date}</span>
            </div>
            <div class="warning-msg">${w.warning_message}</div>
            <div class="warning-actions">
                <span class="warning-disposal">处置: ${DISPOSAL_STATUS_LABELS[w.disposal_status] || w.disposal_status}</span>
                ${w.disposal_time ? `<span class="warning-time">处置时间: ${w.disposal_time.substring(0, 16)}</span>` : ''}
                ${w.disposal_action ? `<span class="warning-action-text">措施: ${w.disposal_action}</span>` : ''}
                ${w.disposal_status === 'pending' ? `<button class="btn-micro" onclick="confirmWarning('${w.warning_id}');queryVoyageWarnings();">确认</button>` : ''}
            </div>
        </div>`;
    });
    html += '</div></div>';

    main.innerHTML = html;
}

async function queryVoyageSummary() {
    const voyageId = document.getElementById('mon_query_voyage').value.trim();
    if (!voyageId) { alert('请输入航次编号'); return; }

    try {
        const res = await fetch(`${API}/monitor/voyage/${encodeURIComponent(voyageId)}/summary`);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: '查询失败' }));
            throw new Error(err.detail || '查询失败');
        }
        const summary = await res.json();
        renderVoyageSummary(voyageId, summary);
    } catch (e) {
        alert('查询失败: ' + e.message);
    }
}

function renderVoyageSummary(voyageId, summary) {
    const main = document.getElementById('main_content');
    let html = `<h2 style="font-size:16px;margin-bottom:16px;">📊 航次 ${voyageId} 风险趋势与汇总</h2>`;

    html += `<div class="monitor-record-cards">
        <div class="result-card pressure">
            <div class="label">总监测天数</div>
            <div class="value">${summary.total_days}<span style="font-size:14px;color:var(--text2)">天</span></div>
        </div>
        <div class="result-card moisture">
            <div class="label">平均湿度</div>
            <div class="value">${summary.avg_humidity.toFixed(1)}<span style="font-size:14px;color:var(--text2)">%</span></div>
        </div>
        <div class="result-card feasibility">
            <div class="label">最高风险指数</div>
            <div class="value" style="color:${summary.max_risk_score > 0.6 ? 'var(--danger)' : summary.max_risk_score > 0.4 ? 'var(--warn)' : 'var(--success)'}">${summary.max_risk_score.toFixed(3)}</div>
        </div>
        <div class="result-card loss">
            <div class="label">预警总数</div>
            <div class="value" style="color:${summary.warning_count > 5 ? 'var(--danger)' : 'var(--warn)'}">${summary.warning_count}</div>
            <div class="sub">高风险 ${summary.high_risk_count} · 未闭环 ${summary.unresolved_count}</div>
        </div>
    </div>`;

    html += `<div class="viz-section">
        <div class="viz-panel no-margin">
            <h3>📈 综合风险趋势</h3>
            <div class="canvas-wrap"><canvas id="riskTrendChart" width="600" height="320"></canvas></div>
        </div>
        <div class="viz-panel no-margin">
            <h3>📈 温湿度趋势</h3>
            <div class="canvas-wrap"><canvas id="envTrendChart" width="600" height="320"></canvas></div>
        </div>
    </div>`;

    html += `<div class="viz-section">
        <div class="viz-panel no-margin">
            <h3>📈 压损/受潮/摇晃风险分量趋势</h3>
            <div class="canvas-wrap"><canvas id="riskCompChart" width="600" height="320"></canvas></div>
        </div>
        <div class="viz-panel no-margin">
            <h3>📊 处置前后风险对比</h3>
            <div class="canvas-wrap"><canvas id="disposalCompChart" width="600" height="320"></canvas></div>
        </div>
    </div>`;

    main.innerHTML = html;

    requestAnimationFrame(() => {
        drawRiskTrendChart(summary.trend);
        drawEnvTrendChart(summary.trend);
        drawRiskCompChart(summary.trend);
        drawDisposalCompChart(summary.disposal_comparison);
    });
}

function drawRiskTrendChart(trend) {
    const canvas = document.getElementById('riskTrendChart');
    if (!canvas || !trend || trend.length === 0) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const margin = { top: 30, right: 20, bottom: 50, left: 55 };
    const cW = W - margin.left - margin.right;
    const cH = H - margin.top - margin.bottom;

    const maxRisk = 1.0;
    const stepX = trend.length > 1 ? cW / (trend.length - 1) : cW;

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
        ctx.fillText((maxRisk * i / 5).toFixed(2), margin.left - 6, y + 3);
    }

    const zones = [
        { from: 0, to: 0.2, color: 'rgba(102,187,106,0.06)' },
        { from: 0.2, to: 0.4, color: 'rgba(79,195,247,0.06)' },
        { from: 0.4, to: 0.6, color: 'rgba(255,183,77,0.06)' },
        { from: 0.6, to: 0.8, color: 'rgba(239,83,80,0.06)' },
        { from: 0.8, to: 1.0, color: 'rgba(239,83,80,0.12)' },
    ];
    zones.forEach(z => {
        const y1 = margin.top + cH - (z.to / maxRisk) * cH;
        const y2 = margin.top + cH - (z.from / maxRisk) * cH;
        ctx.fillStyle = z.color;
        ctx.fillRect(margin.left, y1, cW, y2 - y1);
    });

    ctx.beginPath();
    ctx.strokeStyle = '#4fc3f7';
    ctx.lineWidth = 2;
    trend.forEach((pt, i) => {
        const x = margin.left + i * stepX;
        const y = margin.top + cH - (pt.risk_score / maxRisk) * cH;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();

    trend.forEach((pt, i) => {
        const x = margin.left + i * stepX;
        const y = margin.top + cH - (pt.risk_score / maxRisk) * cH;
        const color = { normal: '#66bb6a', low: '#4fc3f7', medium: '#ffb74d', high: '#ef5350', critical: '#ef5350' }[pt.warning_level] || '#4fc3f7';
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = '#0f1923';
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.fillStyle = '#e0e8f0';
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'center';
        const dateStr = typeof pt.record_date === 'string' ? pt.record_date.substring(5) : String(pt.record_date).substring(5);
        ctx.fillText(dateStr, x, margin.top + cH + 16);
        ctx.fillText(pt.risk_score.toFixed(2), x, y - 8);
    });

    ctx.fillStyle = '#8899aa';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('综合风险趋势', W / 2, margin.top - 10);
}

function drawEnvTrendChart(trend) {
    const canvas = document.getElementById('envTrendChart');
    if (!canvas || !trend || trend.length === 0) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const margin = { top: 30, right: 55, bottom: 50, left: 55 };
    const cW = W - margin.left - margin.right;
    const cH = H - margin.top - margin.bottom;
    const stepX = trend.length > 1 ? cW / (trend.length - 1) : cW;

    ctx.strokeStyle = '#2a4560';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 5; i++) {
        const y = margin.top + cH - (i / 5) * cH;
        ctx.beginPath();
        ctx.moveTo(margin.left, y);
        ctx.lineTo(W - margin.right, y);
        ctx.stroke();
        ctx.fillStyle = '#4fc3f7';
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText((100 * i / 5).toFixed(0) + '%', margin.left - 6, y + 3);
    }

    for (let i = 0; i <= 5; i++) {
        const y = margin.top + cH - (i / 5) * cH;
        ctx.fillStyle = '#ffb74d';
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText((60 * i / 5).toFixed(0) + '°C', W - margin.right + 6, y + 3);
    }

    ctx.beginPath();
    ctx.strokeStyle = '#4fc3f7';
    ctx.lineWidth = 2;
    trend.forEach((pt, i) => {
        const x = margin.left + i * stepX;
        const y = margin.top + cH - (pt.humidity / 100) * cH;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();

    ctx.beginPath();
    ctx.strokeStyle = '#ffb74d';
    ctx.lineWidth = 2;
    trend.forEach((pt, i) => {
        const x = margin.left + i * stepX;
        const y = margin.top + cH - (pt.temperature / 60) * cH;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();

    trend.forEach((pt, i) => {
        const x = margin.left + i * stepX;
        ctx.fillStyle = '#4fc3f7';
        ctx.beginPath();
        ctx.arc(x, margin.top + cH - (pt.humidity / 100) * cH, 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#ffb74d';
        ctx.beginPath();
        ctx.arc(x, margin.top + cH - (pt.temperature / 60) * cH, 3, 0, Math.PI * 2);
        ctx.fill();
    });

    const legendX = margin.left + 10;
    const legendY = margin.top + 10;
    ctx.fillStyle = '#4fc3f7';
    ctx.fillRect(legendX, legendY, 16, 3);
    ctx.fillStyle = '#8899aa';
    ctx.font = '9px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('湿度', legendX + 20, legendY + 4);
    ctx.fillStyle = '#ffb74d';
    ctx.fillRect(legendX + 50, legendY, 16, 3);
    ctx.fillStyle = '#8899aa';
    ctx.fillText('温度', legendX + 70, legendY + 4);

    trend.forEach((pt, i) => {
        const x = margin.left + i * stepX;
        ctx.fillStyle = '#8899aa';
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'center';
        const dateStr = typeof pt.record_date === 'string' ? pt.record_date.substring(5) : String(pt.record_date).substring(5);
        ctx.fillText(dateStr, x, margin.top + cH + 16);
    });
}

function drawRiskCompChart(trend) {
    const canvas = document.getElementById('riskCompChart');
    if (!canvas || !trend || trend.length === 0) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const margin = { top: 30, right: 20, bottom: 50, left: 55 };
    const cW = W - margin.left - margin.right;
    const cH = H - margin.top - margin.bottom;
    const stepX = trend.length > 1 ? cW / (trend.length - 1) : cW;

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
        ctx.fillText((1.0 * i / 5).toFixed(2), margin.left - 6, y + 3);
    }

    const lines = [
        { key: 'pressure_risk', color: '#4fc3f7', label: '压损风险' },
        { key: 'moisture_risk', color: '#ffb74d', label: '受潮风险' },
        { key: 'shake_risk', color: '#ab47bc', label: '摇晃风险' },
    ];

    lines.forEach(line => {
        ctx.beginPath();
        ctx.strokeStyle = line.color;
        ctx.lineWidth = 2;
        trend.forEach((pt, i) => {
            const x = margin.left + i * stepX;
            const val = pt[line.key] || 0;
            const y = margin.top + cH - val * cH;
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.stroke();
    });

    const legendX = margin.left + 10;
    const legendY = margin.top + 10;
    lines.forEach((line, i) => {
        const lx = legendX + i * 80;
        ctx.fillStyle = line.color;
        ctx.fillRect(lx, legendY, 16, 3);
        ctx.fillStyle = '#8899aa';
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(line.label, lx + 20, legendY + 4);
    });

    trend.forEach((pt, i) => {
        const x = margin.left + i * stepX;
        ctx.fillStyle = '#8899aa';
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'center';
        const dateStr = typeof pt.record_date === 'string' ? pt.record_date.substring(5) : String(pt.record_date).substring(5);
        ctx.fillText(dateStr, x, margin.top + cH + 16);
    });
}

function drawDisposalCompChart(comparison) {
    const canvas = document.getElementById('disposalCompChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    if (!comparison) {
        ctx.fillStyle = '#8899aa';
        ctx.font = '13px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('暂无处置前后对比数据', W / 2, H / 2);
        ctx.font = '11px sans-serif';
        ctx.fillText('处置记录后可查看风险变化对比', W / 2, H / 2 + 20);
        return;
    }

    const margin = { top: 40, right: 20, bottom: 50, left: 55 };
    const cW = W - margin.left - margin.right;
    const cH = H - margin.top - margin.bottom;

    const labels = ['处置前', '处置后', '风险降低'];
    const values = [comparison.before_avg_risk, comparison.after_avg_risk, comparison.risk_reduction];
    const colors = ['#ef5350', '#66bb6a', '#4fc3f7'];
    const maxV = Math.max(...values.map(Math.abs), 0.01) * 1.2;

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
        ctx.fillText((maxV * i / 5).toFixed(3), margin.left - 6, y + 3);
    }

    const barW = cW / 3 * 0.5;
    labels.forEach((label, i) => {
        const x = margin.left + (i + 0.5) * (cW / 3) - barW / 2;
        const h = Math.max(0, (values[i] / maxV) * cH);
        const y = margin.top + cH - h;
        const grad = ctx.createLinearGradient(x, y, x, y + h);
        grad.addColorStop(0, colors[i]);
        grad.addColorStop(1, colors[i] + '80');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.roundRect(x, y, barW, h, [3, 3, 0, 0]);
        ctx.fill();
        ctx.fillStyle = '#e0e8f0';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(values[i].toFixed(4), x + barW / 2, y - 6);
        ctx.fillStyle = '#8899aa';
        ctx.fillText(label, x + barW / 2, margin.top + cH + 16);
    });

    ctx.fillStyle = '#8899aa';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`处置前 ${comparison.before_count}条 vs 处置后 ${comparison.after_count}条`, W / 2, margin.top - 10);
}

async function submitAbnormalReport() {
    const voyageId = document.getElementById('mon_voyage_id').value.trim();
    const recordDate = document.getElementById('mon_record_date').value;
    const eventType = document.getElementById('report_event_type').value;
    const severity = document.getElementById('report_severity').value;
    const description = document.getElementById('report_description').value;

    if (!voyageId) { alert('请输入航次编号'); return; }
    if (!recordDate) { alert('请选择日期'); return; }
    if (!description) { alert('请填写异常描述'); return; }

    try {
        const result = await apiCall('/monitor/abnormal-report', {
            voyage_id: voyageId,
            record_date: recordDate,
            event_type: eventType,
            description: description,
            severity: severity
        });
        document.getElementById('report_description').value = '';
        alert(`异常上报成功！预警ID: ${result.warning_id}\n等级: ${WARNING_LEVEL_LABELS[result.warning_level]}\n${result.warning_message}`);
    } catch (e) {
        alert('上报失败: ' + e.message);
    }
}
