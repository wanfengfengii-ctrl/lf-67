const API = '/api';
let lastResult = null;
let lastReq = null;

function getFormData() {
    const v = id => document.getElementById(id).value;
    const humidity = v('humidity');
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
        sea_state: v('sea_state')
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

async function runSimulation() {
    const btn = document.getElementById('btn_simulate');
    btn.disabled = true;
    btn.textContent = '计算中...';
    try {
        const req = getFormData();
        const result = await apiCall('/simulate', req);
        lastResult = result;
        lastReq = req;
        renderResult(req, result);
    } catch (e) {
        alert('模拟失败: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '▶ 运行模拟';
    }
}

async function runComparison() {
    const btn = document.getElementById('btn_simulate');
    btn.disabled = true;
    btn.textContent = '对比中...';
    try {
        const req = getFormData();
        const result = await apiCall('/compare', req);
        lastReq = req;
        renderComparison(req, result);
    } catch (e) {
        alert('对比失败: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '▶ 运行模拟';
    }
}

function renderResult(req, r) {
    const main = document.getElementById('main_content');
    let html = '';

    if (r.warnings && r.warnings.length) {
        const hasDanger = r.is_high_risk;
        html += `<div class="warnings-box ${hasDanger ? 'danger-box' : ''}">
            <h4>${hasDanger ? '⚠ 严重警告' : '⚠ 提示信息'}</h4>
            <ul>${r.warnings.map(w => `<li>${w}</li>`).join('')}</ul>
        </div>`;
    }

    html += `<div class="result-cards">
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
        <div class="result-card execute">
            <div class="label">可执行性</div>
            <div class="value" style="color:${r.can_execute ? 'var(--success)' : 'var(--danger)'}">${r.can_execute ? '可执行' : '不可执行'}</div>
            <div class="sub">总粮包 ${r.total_bags} 包 · 容量 ${r.capacity_used_pct.toFixed(1)}% · 海况 ${SEA_STATE_LABELS[req.sea_state]}</div>
        </div>
    </div>`;

    html += `<div class="viz-section">
        <div class="viz-panel">
            <h3>📐 舱内堆码剖面图</h3>
            <div class="canvas-wrap"><canvas id="crossSection" width="480" height="320"></canvas></div>
        </div>
        <div class="viz-panel">
            <h3>📊 各层承压分布</h3>
            <div class="canvas-wrap"><canvas id="pressureChart" width="480" height="320"></canvas></div>
        </div>
    </div>`;

    html += `<div class="viz-panel" style="margin-bottom:24px;">
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
    let html = `<div class="viz-panel" style="margin-bottom:24px;">
        <h3>⚖ 装载方案对比 ${formalBadge} <span style="font-size:12px;color:var(--text2);font-weight:400;">（最优方案: ${ORDER_LABELS[best]}，损耗率 ${comp.best_loss_rate.toFixed(2)}%）</span></h3>
        <table class="comparison-table">
            <tr>
                <th>装载方式</th>
                <th>底层承压</th>
                <th>受潮风险</th>
                <th>损耗率</th>
                <th>风险等级</th>
                <th>可执行</th>
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
                return `<tr class="${isBest ? 'best' : ''}">
                    <td>${ORDER_LABELS[item.loading_order]} ${isBest ? '⭐' : ''}</td>
                    <td>${r.bottom_pressure_kpa.toFixed(2)} kPa</td>
                    <td>${r.moisture_risk_level}</td>
                    <td style="font-weight:600;color:${r.estimated_loss_rate > 10 ? 'var(--danger)' : 'var(--text)'}">${r.estimated_loss_rate.toFixed(2)}%</td>
                    <td>${riskBadge}</td>
                    <td>${execBadge}</td>
                </tr>`;
            }).join('')}
        </table>
    </div>`;

    html += `<div class="viz-section">
        <div class="viz-panel">
            <h3>📊 损耗率对比</h3>
            <div class="canvas-wrap"><canvas id="compChart" width="480" height="300"></canvas></div>
        </div>
        <div class="viz-panel">
            <h3>📊 底层承压对比</h3>
            <div class="canvas-wrap"><canvas id="compPressure" width="480" height="300"></canvas></div>
        </div>
    </div>`;

    main.innerHTML = html;
    requestAnimationFrame(() => {
        drawComparisonCharts(comp);
    });
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
    const layers = req.layers;

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

        for (let j = 0; j < bagsPerRow; j++) {
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
    if (!canvas1 || !canvas2) return;

    const items = comp.items;
    const labels = items.map(i => ORDER_LABELS[i.loading_order]);
    const lossData = items.map(i => i.result.estimated_loss_rate);
    const pressData = items.map(i => i.result.bottom_pressure_kpa);

    drawBarCompare(canvas1, labels, lossData, '%', '损耗率');
    drawBarCompare(canvas2, labels, pressData, 'kPa', '底层承压');
}

function drawBarCompare(canvas, labels, values, unit, title) {
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const margin = { top: 20, right: 20, bottom: 50, left: 55 };
    const cW = W - margin.left - margin.right;
    const cH = H - margin.top - margin.bottom;

    const maxV = Math.max(...values, 0.01);
    const barW = cW / labels.length * 0.6;
    const gap = cW / labels.length;

    const colors = ['#4fc3f7', '#ffb74d', '#66bb6a', '#ef5350'];

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
            if (lastResult && JSON.stringify(req) !== JSON.stringify(lastAutoReq)) {
                lastAutoReq = req;
                apiCall('/simulate', req).then(result => {
                    lastResult = result;
                    lastReq = req;
                    renderResult(req, result);
                }).catch(() => {});
            }
        } catch (e) {}
    }, 500);
}

document.addEventListener('DOMContentLoaded', () => {
    const inputs = document.querySelectorAll('.panel input, .panel select');
    inputs.forEach(input => {
        input.addEventListener('input', scheduleAutoSimulate);
        input.addEventListener('change', scheduleAutoSimulate);
    });
});
