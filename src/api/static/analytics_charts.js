// OsuRender replay analytics charts.
// These charts only visualize facts available from replay metadata and frames.

// osrparse Key enum bitmask values:
// M1 (mouse left) = 1, M2 (mouse right) = 2, K1 = 4, K2 = 8, Smoke = 16.
const KEY_M1 = 1;
const KEY_M2 = 2;
const KEY_K1 = 4;
const KEY_K2 = 8;
const HIT_KEYS = KEY_M1 | KEY_M2 | KEY_K1 | KEY_K2;

const CHART_COLORS = {
    accent: '#ff66ab',
    accent2: '#22d3ee',
    blue: '#60a5fa',
    green: '#4ade80',
    yellow: '#fbbf24',
    red: '#f87171',
    purple: '#c084fc',
    cyan: '#22d3ee',
    grid: '#2a2a42',
    muted: '#9898b0',
    text: '#eeeef2',
};

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
    }[char]));
}

function showChartError(containerId, error) {
    if (window.activeCharts && window.activeCharts[containerId]) {
        try {
            window.activeCharts[containerId].destroy();
        } catch (e) {}
        window.activeCharts[containerId] = null;
    }
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `<div class="chart-error">
        <i class="fas fa-circle-info"></i>
        <span>Chart unavailable</span>
        <details><summary>Details</summary><pre>${escapeHtml(error)}</pre></details>
    </div>`;
}

function showChartEmpty(containerId, message) {
    if (window.activeCharts && window.activeCharts[containerId]) {
        try {
            window.activeCharts[containerId].destroy();
        } catch (e) {}
        window.activeCharts[containerId] = null;
    }
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `<div class="chart-empty"><i class="fas fa-circle-info"></i><span>${escapeHtml(message)}</span></div>`;
}

function apexDefaults(overrides) {
    return Object.assign({
        chart: {
            background: 'transparent',
            foreColor: CHART_COLORS.muted,
            toolbar: { show: false },
            fontFamily: 'Outfit, sans-serif',
        },
        grid: { borderColor: CHART_COLORS.grid, strokeDashArray: 4 },
        dataLabels: { enabled: false },
        tooltip: { theme: 'dark' },
        legend: { labels: { colors: CHART_COLORS.muted } },
    }, overrides);
}

// Keep track of active chart instances to prevent ghost charts
window.activeCharts = window.activeCharts || {};

function renderChartSafely(containerId, options) {
    const el = document.getElementById(containerId);
    if (!el) return null;

    if (window.activeCharts[containerId]) {
        try {
            window.activeCharts[containerId].destroy();
        } catch (e) {
            console.warn(`Failed to destroy chart ${containerId}:`, e);
        }
        window.activeCharts[containerId] = null;
    }

    el.innerHTML = '';
    const chart = new ApexCharts(el, options);
    window.activeCharts[containerId] = chart;
    chart.render();
    return chart;
}

function downsample(arr, maxPoints) {
    if (arr.length <= maxPoints) return arr;
    const step = Math.ceil(arr.length / maxPoints);
    return arr.filter((_, i) => i % step === 0);
}

function getHitCounts(stats) {
    const h300 = Number(stats['300s'] ?? stats.count_300 ?? 0);
    const h100 = Number(stats['100s'] ?? stats.count_100 ?? 0);
    const h50 = Number(stats['50s'] ?? stats.count_50 ?? 0);
    const miss = Number(stats.misses ?? 0);
    return { h300, h100, h50, miss, total: h300 + h100 + h50 + miss };
}

function calculateAccuracy(counts) {
    if (!counts.total) return 0;
    return ((counts.h300 * 300 + counts.h100 * 100 + counts.h50 * 50) / (counts.total * 300)) * 100;
}

function hitMask(keys) {
    return Number(keys ?? 0) & HIT_KEYS;
}

function extractPressEvents(frames) {
    const events = [];
    let previous = 0;
    for (const frame of frames) {
        const current = hitMask(frame.keys);
        const pressed = current & ~previous;
        if (pressed) {
            if (pressed & KEY_K1) events.push({ t: frame.t, key: 'K1' });
            if (pressed & KEY_K2) events.push({ t: frame.t, key: 'K2' });
            if (pressed & KEY_M1) events.push({ t: frame.t, key: 'M1' });
            if (pressed & KEY_M2) events.push({ t: frame.t, key: 'M2' });
        }
        previous = current;
    }
    return events;
}

function renderCoreCharts(stats) {
    const counts = getHitCounts(stats);
    const acc = calculateAccuracy(counts);

    try {
        renderChartSafely('chart-hits', apexDefaults({
            chart: { type: 'donut', height: 260 },
            series: [counts.h300, counts.h100, counts.h50, counts.miss],
            labels: ['300', '100', '50', 'Miss'],
            colors: [CHART_COLORS.blue, CHART_COLORS.green, CHART_COLORS.yellow, CHART_COLORS.red],
            stroke: { show: false },
            plotOptions: {
                pie: {
                    donut: {
                        size: '62%',
                        labels: {
                            show: true,
                            total: {
                                show: true,
                                label: 'Objects',
                                color: CHART_COLORS.muted,
                                formatter: () => counts.total,
                            },
                        },
                    },
                },
            },
            legend: { position: 'bottom', labels: { colors: CHART_COLORS.muted } },
        }));
    } catch (e) {
        showChartError('chart-hits', e.message);
    }

    try {
        renderChartSafely('chart-accuracy', apexDefaults({
            chart: { type: 'radialBar', height: 260 },
            series: [Number(acc.toFixed(2))],
            labels: ['Accuracy'],
            colors: [acc >= 98 ? CHART_COLORS.green : acc >= 95 ? CHART_COLORS.blue : acc >= 90 ? CHART_COLORS.yellow : CHART_COLORS.red],
            plotOptions: {
                radialBar: {
                    hollow: { size: '64%' },
                    track: { background: '#24243a' },
                    dataLabels: {
                        name: { color: CHART_COLORS.muted, fontSize: '13px' },
                        value: {
                            color: CHART_COLORS.text,
                            fontSize: '26px',
                            fontWeight: 800,
                            formatter: value => `${Number(value).toFixed(2)}%`,
                        },
                    },
                },
            },
            stroke: { lineCap: 'round' },
        }));
    } catch (e) {
        showChartError('chart-accuracy', e.message);
    }

    try {
        const maxPoints = Math.max(counts.total * 300, 1);
        const earned = counts.h300 * 300 + counts.h100 * 100 + counts.h50 * 50;
        const lostTo100 = counts.h100 * 200;
        const lostTo50 = counts.h50 * 250;
        const lostToMiss = counts.miss * 300;
        renderChartSafely('chart-judgement-impact', apexDefaults({
            chart: { type: 'bar', height: 260, stacked: true, stackType: '100%' },
            series: [
                { name: 'Earned', data: [earned] },
                { name: 'Lost to 100s', data: [lostTo100] },
                { name: 'Lost to 50s', data: [lostTo50] },
                { name: 'Lost to misses', data: [lostToMiss] },
            ],
            colors: [CHART_COLORS.green, CHART_COLORS.blue, CHART_COLORS.yellow, CHART_COLORS.red],
            plotOptions: { bar: { horizontal: true, borderRadius: 4, barHeight: '48%' } },
            xaxis: {
                max: maxPoints,
                labels: { style: { colors: CHART_COLORS.muted }, formatter: value => `${Number(value).toFixed(0)} pts` },
            },
            yaxis: { labels: { show: false } },
            tooltip: { y: { formatter: value => `${Number(value).toLocaleString()} accuracy points` } },
        }));
    } catch (e) {
        showChartError('chart-judgement-impact', e.message);
    }
}

function renderLifeBar(lifeBar) {
    const data = downsample(lifeBar, 500).map(entry => ({
        x: Number(entry.t),
        y: Number((entry.hp * 100).toFixed(1)),
    }));
    if (!data.length) {
        showChartEmpty('chart-lifebar', 'No life bar samples were stored for this replay.');
        return;
    }

    renderChartSafely('chart-lifebar', apexDefaults({
        chart: { type: 'area', height: 280 },
        series: [{ name: 'HP', data }],
        colors: [CHART_COLORS.red],
        stroke: { curve: 'smooth', width: 2 },
        fill: { type: 'gradient', gradient: { opacityFrom: 0.42, opacityTo: 0.05, stops: [0, 90, 100] } },
        xaxis: { type: 'numeric', labels: { style: { colors: CHART_COLORS.muted }, formatter: value => `${(value / 1000).toFixed(0)}s` } },
        yaxis: { min: 0, max: 100, labels: { style: { colors: CHART_COLORS.muted }, formatter: value => `${value}%` } },
    }));
}

function renderInputCharts(frames) {
    const pressEvents = extractPressEvents(frames);

    try {
        if (pressEvents.length < 2) {
            showChartEmpty('chart-tap-intervals', 'Not enough discrete input events to chart tap intervals.');
        } else {
            const bins = [
                { label: '<80ms', min: 0, max: 80, count: 0 },
                { label: '80-120ms', min: 80, max: 120, count: 0 },
                { label: '120-180ms', min: 120, max: 180, count: 0 },
                { label: '180-260ms', min: 180, max: 260, count: 0 },
                { label: '260-380ms', min: 260, max: 380, count: 0 },
                { label: '380ms+', min: 380, max: Infinity, count: 0 },
            ];
            for (let i = 1; i < pressEvents.length; i++) {
                const delta = pressEvents[i].t - pressEvents[i - 1].t;
                if (delta <= 0 || delta > 1000) continue;
                const bin = bins.find(item => delta >= item.min && delta < item.max);
                if (bin) bin.count += 1;
            }
            renderChartSafely('chart-tap-intervals', apexDefaults({
                chart: { type: 'bar', height: 260 },
                series: [{ name: 'Intervals', data: bins.map(bin => bin.count) }],
                colors: [CHART_COLORS.cyan],
                plotOptions: { bar: { borderRadius: 4, columnWidth: '68%' } },
                xaxis: { categories: bins.map(bin => bin.label), labels: { style: { colors: CHART_COLORS.muted } } },
                yaxis: { labels: { style: { colors: CHART_COLORS.muted } } },
                tooltip: { y: { formatter: value => `${value} intervals` } },
            }));
        }
    } catch (e) {
        showChartError('chart-tap-intervals', e.message);
    }

    try {
        const keyCounts = { K1: 0, K2: 0, M1: 0, M2: 0 };
        pressEvents.forEach(event => {
            keyCounts[event.key] += 1;
        });
        renderChartSafely('chart-input-balance', apexDefaults({
            chart: { type: 'bar', height: 260 },
            series: [{ name: 'Presses', data: [keyCounts.K1, keyCounts.K2, keyCounts.M1, keyCounts.M2] }],
            colors: [CHART_COLORS.accent],
            plotOptions: { bar: { borderRadius: 4, columnWidth: '56%' } },
            xaxis: { categories: ['K1', 'K2', 'M1', 'M2'], labels: { style: { colors: CHART_COLORS.muted, fontWeight: 700 } } },
            yaxis: { labels: { style: { colors: CHART_COLORS.muted } } },
            tooltip: { y: { formatter: value => `${value} presses` } },
        }));
    } catch (e) {
        showChartError('chart-input-balance', e.message);
    }
}

function renderCursorCharts(frames) {
    try {
        const container = document.getElementById('chart-heatmap');
        container.innerHTML = '<div class="heatmap-container"><canvas id="heatmap-canvas" width="512" height="384"></canvas></div>';
        const canvas = document.getElementById('heatmap-canvas');
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#10101e';
        ctx.fillRect(0, 0, 512, 384);

        const sampled = downsample(frames, 3500);
        sampled.forEach(frame => {
            const x = Math.max(0, Math.min(511, Number(frame.x)));
            const y = Math.max(0, Math.min(383, Number(frame.y)));
            ctx.beginPath();
            ctx.arc(x, y, 2, 0, Math.PI * 2);
            ctx.fillStyle = hitMask(frame.keys) ? 'rgba(255,102,171,0.28)' : 'rgba(34,211,238,0.06)';
            ctx.fill();
        });
    } catch (e) {
        showChartError('chart-heatmap', e.message);
    }

    try {
        const speedData = [];
        for (let i = 1; i < frames.length; i++) {
            const previous = frames[i - 1];
            const current = frames[i];
            const dt = current.t - previous.t;
            if (dt <= 0 || dt > 250) continue;
            const dx = current.x - previous.x;
            const dy = current.y - previous.y;
            const speed = (Math.sqrt(dx * dx + dy * dy) / dt) * 1000;
            if (Number.isFinite(speed)) {
                speedData.push({ x: current.t, y: Number(speed.toFixed(0)) });
            }
        }
        renderChartSafely('chart-cursorspeed', apexDefaults({
            chart: { type: 'area', height: 300 },
            series: [{ name: 'Cursor speed', data: downsample(speedData, 450) }],
            colors: [CHART_COLORS.green],
            stroke: { curve: 'smooth', width: 1.8 },
            fill: { type: 'gradient', gradient: { opacityFrom: 0.35, opacityTo: 0.04 } },
            xaxis: { type: 'numeric', labels: { style: { colors: CHART_COLORS.muted }, formatter: value => `${(value / 1000).toFixed(0)}s` } },
            yaxis: { labels: { style: { colors: CHART_COLORS.muted }, formatter: value => `${Number(value).toFixed(0)}` } },
            tooltip: { y: { formatter: value => `${Number(value).toFixed(0)} px/s` } },
        }));
    } catch (e) {
        showChartError('chart-cursorspeed', e.message);
    }
}

let analyticsLoaded = false;
async function loadAnalytics(jobId) {
    if (analyticsLoaded) return;
    analyticsLoaded = true;

    try {
        const res = await fetch(`/v1/jobs/${jobId}/analytics`);
        if (res.status === 202) {
            analyticsLoaded = false;
            return;
        }
        if (!res.ok) return;
        const data = await res.json();

        try {
            renderLifeBar(data.life_bar || []);
        } catch (e) {
            showChartError('chart-lifebar', e.message);
        }

        if (!data.frames_url) {
            ['chart-tap-intervals', 'chart-input-balance', 'chart-heatmap', 'chart-cursorspeed'].forEach(id => {
                showChartEmpty(id, 'No replay frame data is available for this chart.');
            });
            return;
        }

        try {
            const framesRes = await fetch(data.frames_url);
            const buffer = await framesRes.arrayBuffer();
            let frames;
            if ('DecompressionStream' in window) {
                const ds = new DecompressionStream('gzip');
                const decompressed = new Response(new Blob([buffer]).stream().pipeThrough(ds));
                frames = await decompressed.json();
            } else {
                throw new Error('This browser cannot decompress analytics frames.');
            }

            renderInputCharts(frames);
            renderCursorCharts(frames);
        } catch (e) {
            console.error('Failed to fetch/decompress frames:', e);
            ['chart-tap-intervals', 'chart-input-balance', 'chart-heatmap', 'chart-cursorspeed'].forEach(id => {
                showChartError(id, 'Frame data unavailable');
            });
        }
    } catch (e) {
        console.error('Analytics load failed:', e);
    }
}

// ─── TAB SWITCHING ───
function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
    document.getElementById('pane-' + (tab === 'details' ? 'details' : 'replay')).classList.add('active');
}

// ─── CHART GROUP TOGGLE ───
function toggleGroup(id) {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('collapsed');
}

// ─── PIPELINE STEPPER ───
let pipelineLocked = false;
const STEPS = ['queued','setup','render','upload','done'];
const STEP_IDS = ['ps-queued','ps-setup','ps-render','ps-upload','ps-done'];
function setPipelineStage(stage, failed) {
    if (pipelineLocked) return;
    if (stage === 'done' || failed) pipelineLocked = true;
    const idx = STEPS.indexOf(stage);
    STEP_IDS.forEach((id, i) => {
        const el = document.getElementById(id);
        el.className = 'pipeline-step';
        if (failed && i <= idx) { el.classList.add(i === idx ? 'failed' : 'done'); }
        else if (i < idx || (stage === 'done' && i === idx)) el.classList.add('done');
        else if (i === idx) el.classList.add('active');
        else el.classList.add('pending');
        const dot = el.querySelector('.pipeline-dot');
        if (!failed && (i < idx || (stage === 'done' && i === idx))) dot.innerHTML = '<i class="fas fa-check"></i>';
        else if (failed && i === idx) dot.innerHTML = '<i class="fas fa-xmark"></i>';
        else dot.textContent = (i + 1).toString();
    });
    const fillPct = failed ? ((idx + 1) / STEPS.length * 100) : (idx / (STEPS.length - 1) * 100);
    document.getElementById('pipeline-fill').style.width = fillPct + '%';
}
let currentPipelineStage = 'queued';

// ─── LOG PARSING ───
let logsSeen = 0, currentLogsUrl = null;
function formatJson(str) {
    try {
        const obj = JSON.parse(str);
        return JSON.stringify(obj, null, 2).replace(
            /("(\\u[\da-fA-F]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
            m => { let c='log-json-number'; if(/^"/.test(m)){c=/:$/.test(m)?'log-json-key':'log-json-string';}else if(/true|false/.test(m)){c='log-json-boolean';} return '<span class="'+c+'">'+escapeHtml(m)+'</span>'; }
        );
    } catch(e) { return null; }
}

function parseLogLine(line) {
    if (!line.trim()) return '';
    let html = '<div class="log-line">';
    const tm = line.match(/^(\[\d{2}:\d{2}:\d{2}\])(.*)/);
    let content = line;
    if (tm) { html += `<span class="log-time">${tm[1]}</span>`; content = tm[2]; }
    if (content.trim().startsWith('{') && content.trim().endsWith('}')) {
        const j = formatJson(content);
        if (j) return html + `<pre style="margin:0">${j}</pre></div>`;
    }
    const dp = content.match(/Progress:\s*(\d+)%,\s*Speed:\s*([\d.]+)x,\s*ETA:\s*(.+)/);
    if (dp) {
        document.getElementById('progress-bar').style.width = dp[1]+'%';
        document.getElementById('progress-text').innerText = `Rendering — ${dp[1]}% (${dp[2]}x, ETA: ${dp[3]})`;
        return '';
    }
    const safeContent = escapeHtml(content);
    if (content.match(/\b(Error|failed|invalid)\b/i)) html += `<span class="log-error"><i class="fas fa-circle-xmark"></i> ${safeContent}</span>`;
    else if (content.match(/\b(Finished!|success|Loaded|Initialized!|loaded\.)\b/)) html += `<span class="log-success"><i class="fas fa-circle-check"></i> ${safeContent}</span>`;
    else if (content.match(/\bWarning\b/i)) html += `<span class="log-warn"><i class="fas fa-triangle-exclamation"></i> ${safeContent}</span>`;
    else if (content.includes('Downloading')||content.includes('Starting')||content.includes('Uploading')) html += `<span class="log-info"><i class="fas fa-circle-info"></i> ${safeContent}</span>`;
    else html += safeContent;
    html += '</div>';
    return html;
}

function updatePipelineFromLog(line) {
    if (pipelineLocked) return;
    if (line.includes("Setting up osu! directory") || line.includes("Downloading replay") || line.includes("Downloading beatmap") || line.includes("Downloading skin")) {
        currentPipelineStage = 'setup'; setPipelineStage('setup', false);
        document.getElementById('progress-text').innerText = 'Downloading assets...';
    } else if (line.includes("Starting danser render")) {
        currentPipelineStage = 'render'; setPipelineStage('render', false);
        document.getElementById('progress-text').innerText = 'Rendering...';
    } else if (line.includes("Uploading video")) {
        currentPipelineStage = 'upload'; setPipelineStage('upload', false);
        document.getElementById('progress-bar').style.width = '100%';
        document.getElementById('progress-text').innerText = 'Uploading to cloud storage...';
    }
}

async function fetchLogs(url) {
    try {
        const r = await fetch(url + '?t=' + Date.now());
        if (!r.ok) return;
        const text = await r.text();
        if (text.length > logsSeen) {
            const chunk = text.substring(logsSeen);
            logsSeen = text.length;
            let h = '';
            for (let line of chunk.split(/[\r\n]+/)) {
                if (!line.trim()) continue;
                updatePipelineFromLog(line);
                h += parseLogLine(line);
            }
            if (h) {
                const el = document.getElementById('logs');
                el.innerHTML += h;
                el.scrollTop = el.scrollHeight;
            }
        }
    } catch(e) { console.error(e); }
}

function refreshLogs() {
    if (currentLogsUrl) { logsSeen = 0; document.getElementById('logs').innerHTML = ''; fetchLogs(currentLogsUrl); }
}

let chartsRenderedCore = false;

// ─── POLLING ───
async function check() {
    try {
        let r = await fetch('/v1/jobs/' + window.JOB_ID);
        if (!r.ok) { setTimeout(check, 3000); return; }
        let d = await r.json();

        const badge = document.getElementById('status-badge');
        badge.innerText = d.status;
        badge.className = 'badge badge-' + d.status;
        document.getElementById('detail-status').innerText = d.status;
        if (d.updated_at) document.getElementById('detail-updated').innerText = new Date(d.updated_at).toLocaleString();

        if (d.config && Object.keys(d.config).length > 0) {
            document.getElementById('config-display').innerText = JSON.stringify(d.config, null, 2);
        }

        if (d.config && d.config.replay_stats) {
            const s = d.config.replay_stats;
            document.getElementById('stats-section').style.display = 'block';
            document.getElementById('stat-300').innerText = s['300s'] !== undefined ? s['300s'] : '-';
            document.getElementById('stat-100').innerText = s['100s'] !== undefined ? s['100s'] : '-';
            document.getElementById('stat-50').innerText = s['50s'] !== undefined ? s['50s'] : '-';
            document.getElementById('stat-miss').innerText = s['misses'] !== undefined ? s['misses'] : '-';
            document.getElementById('stat-combo').innerText = s['max_combo'] ? s['max_combo']+'x' : '-';
            document.getElementById('stat-stars').innerText = s['star_rating'] ? parseFloat(s['star_rating']).toFixed(2)+'★' : '-';
            document.getElementById('stat-pp').innerText = s['pp'] ? parseFloat(s['pp']).toFixed(2)+'pp' : '-';
            if (!chartsRenderedCore) {
                renderCoreCharts(s);
                chartsRenderedCore = true;
            }
            if (d.has_analytics) {
                loadAnalytics(window.JOB_ID);
            } else if (d.status === 'completed' || d.status === 'failed') {
                ['chart-lifebar','chart-tap-intervals','chart-input-balance','chart-heatmap','chart-cursorspeed'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el && el.querySelector('.chart-skeleton')) el.innerHTML = '<div class="chart-error"><i class="fas fa-info-circle"></i> No frame data available for this replay</div>';
                });
            }
        }

        if (d.artifacts && d.artifacts.logs_url) {
            currentLogsUrl = d.artifacts.logs_url;
            await fetchLogs(d.artifacts.logs_url);
        }

        if (d.status === 'completed') {
            setPipelineStage('done', false);
            document.getElementById('progress-section').style.display = 'none';
            document.getElementById('video-section').style.display = 'block';
            let v = document.getElementById('v');
            if (!v.getAttribute('src') && v.innerHTML.trim() === '') {
                v.setAttribute('src', d.artifacts.video_url);
                document.getElementById('d').href = d.artifacts.video_url;
            }
            return;
        } else if (d.status === 'failed') {
            setPipelineStage(currentPipelineStage, true);
            document.getElementById('progress-bar').style.width = '100%';
            document.getElementById('progress-bar').style.background = '#ff4d4d';
            document.getElementById('progress-text').innerText = 'Render failed.';
            document.getElementById('progress-text').style.color = '#ff4d4d';
            if (d.error_message) {
                document.getElementById('error-row').style.display = 'flex';
                document.getElementById('detail-error').innerText = d.error_message;
            }
            return;
        } else if (d.status === 'queued') {
            setPipelineStage('queued', false);
        } else if (d.status === 'downloading') {
            setPipelineStage('setup', false);
        } else if (d.status === 'rendering') {
            if (currentPipelineStage === 'queued' || currentPipelineStage === 'setup') {
                currentPipelineStage = 'render';
            }
            setPipelineStage(currentPipelineStage, false);
        }

        setTimeout(check, 3000);
    } catch(e) { setTimeout(check, 3000); }
}

// ─── INIT ───
document.addEventListener('DOMContentLoaded', () => {
    const _initStatus = window.INIT_STATUS;
    const _initError = window.INIT_ERROR;
    setPipelineStage('queued', false);
    if (_initStatus === 'completed') {
        setPipelineStage('done', false);
        document.getElementById('progress-section').style.display = 'none';
        document.getElementById('video-section').style.display = 'block';
    } else if (_initStatus === 'failed') {
        setPipelineStage('queued', true);
        document.getElementById('progress-bar').style.width = '100%';
        document.getElementById('progress-bar').style.background = '#ff4d4d';
        document.getElementById('progress-text').innerText = 'Render failed.';
    }
    if (_initError) {
        document.getElementById('error-row').style.display = 'flex';
    }
    if (window.JOB_ID) {
        check();
    }
});
