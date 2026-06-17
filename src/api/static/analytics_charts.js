// ═══════════════════════════════════════════════════════
// OsuRender Analytics Charts
// ═══════════════════════════════════════════════════════

// osrparse Key enum bitmask values:
// M1 (mouse left)  = 1, M2 (mouse right) = 2
// K1 (keyboard 1)  = 4, K2 (keyboard 2)  = 8
// Smoke             = 16
const KEY_M1 = 1, KEY_M2 = 2, KEY_K1 = 4, KEY_K2 = 8, KEY_SMOKE = 16;

const CHART_COLORS = {
    accent: '#ff66ab', accent2: '#b366ff',
    blue: '#60a5fa', green: '#4ade80', yellow: '#fbbf24', red: '#f87171',
    purple: '#c084fc', cyan: '#22d3ee', orange: '#fb923c',
    grid: '#2a2a42', muted: '#9898b0'
};

function showChartError(containerId, error) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `<div class="chart-error">
        <i class="fas fa-exclamation-circle"></i> Chart unavailable
        <details><summary>Details</summary><pre>${error}</pre></details>
    </div>`;
}

function apexDefaults(overrides) {
    return Object.assign({
        chart: { background: 'transparent', foreColor: CHART_COLORS.muted, toolbar: { show: false } },
        grid: { borderColor: CHART_COLORS.grid, strokeDashArray: 4 },
        dataLabels: { enabled: false },
        tooltip: { theme: 'dark' },
    }, overrides);
}

// ── downsample for performance on mobile ──
function downsample(arr, maxPoints) {
    if (arr.length <= maxPoints) return arr;
    const step = Math.ceil(arr.length / maxPoints);
    return arr.filter((_, i) => i % step === 0);
}

// ═══════════════════════════════════════════════════════
// Core Charts (hit_counts only — no frames needed)
// ═══════════════════════════════════════════════════════
function renderCoreCharts(stats) {
    const h300 = stats['300s']||0, h100 = stats['100s']||0, h50 = stats['50s']||0, miss = stats['misses']||0;
    const total = h300+h100+h50+miss || 1;
    const acc = ((h300*300+h100*100+h50*50)/(total*300)*100);

    // 1) Hit Distribution - Donut
    try {
        new ApexCharts(document.getElementById('chart-hits'), apexDefaults({
            chart:{type:'donut',height:260,background:'transparent',foreColor:CHART_COLORS.muted},
            series:[h300,h100,h50,miss], labels:['300s','100s','50s','Misses'],
            colors:[CHART_COLORS.blue,CHART_COLORS.green,CHART_COLORS.yellow,CHART_COLORS.red],
            stroke:{show:false},
            plotOptions:{pie:{donut:{size:'60%',labels:{show:true,total:{show:true,label:'Total Hits',color:CHART_COLORS.muted,formatter:()=>total}}}}},
            legend:{position:'bottom',labels:{colors:CHART_COLORS.muted}},
        })).render();
    } catch(e) { showChartError('chart-hits', e.message); }

    // 2) Accuracy Gauge
    try {
        new ApexCharts(document.getElementById('chart-accuracy'), {
            chart:{type:'radialBar',height:260,background:'transparent'},
            series:[parseFloat(acc.toFixed(1))], labels:['Accuracy'],
            colors:[ acc>=98?CHART_COLORS.green:acc>=95?CHART_COLORS.blue:acc>=90?CHART_COLORS.yellow:CHART_COLORS.red ],
            plotOptions:{radialBar:{hollow:{size:'65%'},track:{background:'#2a2a42'},dataLabels:{name:{color:CHART_COLORS.muted,fontSize:'14px'},value:{color:'#eeeef2',fontSize:'28px',fontWeight:800,formatter:v=>v+'%'}}}},
            stroke:{lineCap:'round'}
        }).render();
    } catch(e) { showChartError('chart-accuracy', e.message); }

    // 3) Grade Thresholds
    try {
        const grades = [{name:'SS',min:100},{name:'S',min:95},{name:'A',min:90},{name:'B',min:80},{name:'C',min:70}];
        new ApexCharts(document.getElementById('chart-grade'), apexDefaults({
            chart:{type:'bar',height:260,background:'transparent',foreColor:CHART_COLORS.muted},
            series:[{name:'Threshold',data:grades.map(g=>g.min)},{name:'Your Accuracy',data:grades.map(()=>parseFloat(acc.toFixed(1)))}],
            colors:['#35355a',CHART_COLORS.accent],
            plotOptions:{bar:{borderRadius:4,columnWidth:'60%'}},
            xaxis:{categories:grades.map(g=>g.name),labels:{style:{colors:CHART_COLORS.muted,fontSize:'13px',fontWeight:600}}},
            yaxis:{min:60,max:100,labels:{style:{colors:CHART_COLORS.muted},formatter:v=>v+'%'}},
            legend:{labels:{colors:CHART_COLORS.muted}},
            tooltip:{y:{formatter:v=>v.toFixed(1)+'%'}}
        })).render();
    } catch(e) { showChartError('chart-grade', e.message); }
}

// ═══════════════════════════════════════════════════════
// Timing Charts (life_bar + frames)
// ═══════════════════════════════════════════════════════
function renderLifeBar(lifeBar) {
    const data = downsample(lifeBar, 500).map(e => ({ x: e.t, y: (e.hp * 100).toFixed(1) }));
    new ApexCharts(document.getElementById('chart-lifebar'), apexDefaults({
        chart:{type:'area',height:260,background:'transparent',foreColor:CHART_COLORS.muted},
        series:[{name:'HP %',data}],
        colors:[CHART_COLORS.red],
        stroke:{curve:'smooth',width:2},
        fill:{type:'gradient',gradient:{shadeIntensity:1,opacityFrom:0.5,opacityTo:0.05,stops:[0,90,100]}},
        xaxis:{type:'numeric',labels:{style:{colors:CHART_COLORS.muted},formatter:v=>(v/1000).toFixed(0)+'s'},title:{text:'Time',style:{color:CHART_COLORS.muted}}},
        yaxis:{min:0,max:100,labels:{style:{colors:CHART_COLORS.muted},formatter:v=>v+'%'}},
    })).render();
}

function renderTimingCharts(frames) {
    // Hit Error Distribution — histogram of time deltas between key presses
    try {
        const keyFrames = frames.filter(f => (f.keys & (KEY_K1|KEY_K2|KEY_M1|KEY_M2)) > 0);
        const deltas = [];
        for (let i = 1; i < keyFrames.length; i++) {
            const dt = keyFrames[i].t - keyFrames[i-1].t;
            if (dt > 0 && dt < 500) deltas.push(dt);
        }
        // Bin into 20ms buckets from 0 to 200ms
        const bins = Array(10).fill(0);
        const binLabels = [];
        for (let i = 0; i < 10; i++) { binLabels.push((i*20)+'-'+(i*20+20)+'ms'); }
        deltas.forEach(d => { const idx = Math.min(Math.floor(d/20), 9); bins[idx]++; });
        new ApexCharts(document.getElementById('chart-hiterror'), apexDefaults({
            chart:{type:'bar',height:260,background:'transparent',foreColor:CHART_COLORS.muted},
            series:[{name:'Hits',data:bins}],
            colors:[CHART_COLORS.green],
            plotOptions:{bar:{borderRadius:3,columnWidth:'80%'}},
            xaxis:{categories:binLabels,labels:{style:{colors:CHART_COLORS.muted,fontSize:'9px'},rotate:-45}},
            yaxis:{show:false},
        })).render();
    } catch(e) { showChartError('chart-hiterror', e.message); }

    // Accuracy Over Time — rolling key press density
    try {
        const windowMs = 5000;
        const sampled = downsample(frames, 300);
        const accData = [];
        sampled.forEach(f => {
            const windowFrames = frames.filter(wf => wf.t >= f.t - windowMs && wf.t <= f.t);
            const keyPresses = windowFrames.filter(wf => (wf.keys & (KEY_K1|KEY_K2|KEY_M1|KEY_M2)) > 0).length;
            const total = windowFrames.length || 1;
            accData.push({ x: f.t, y: parseFloat(((keyPresses/total)*100).toFixed(1)) });
        });
        new ApexCharts(document.getElementById('chart-acctime'), apexDefaults({
            chart:{type:'line',height:260,background:'transparent',foreColor:CHART_COLORS.muted},
            series:[{name:'Activity %',data:accData}],
            colors:[CHART_COLORS.blue],
            stroke:{curve:'smooth',width:2},
            xaxis:{type:'numeric',labels:{style:{colors:CHART_COLORS.muted},formatter:v=>(v/1000).toFixed(0)+'s'}},
            yaxis:{min:0,max:100,labels:{style:{colors:CHART_COLORS.muted},formatter:v=>v+'%'}},
        })).render();
    } catch(e) { showChartError('chart-acctime', e.message); }
}

// ═══════════════════════════════════════════════════════
// Cursor Charts (frames only)
// ═══════════════════════════════════════════════════════
function renderCursorCharts(frames) {
    // Cursor Heatmap — canvas 2D density
    try {
        const container = document.getElementById('chart-heatmap');
        container.innerHTML = '<div class="heatmap-container"><canvas id="heatmap-canvas" width="512" height="384"></canvas></div>';
        const canvas = document.getElementById('heatmap-canvas');
        const ctx = canvas.getContext('2d');
        // Black background
        ctx.fillStyle = '#0a0a18';
        ctx.fillRect(0, 0, 512, 384);
        // Draw each frame as a translucent dot
        const sampled = downsample(frames, 3000);
        sampled.forEach(f => {
            const x = Math.max(0, Math.min(511, f.x));
            const y = Math.max(0, Math.min(383, f.y));
            ctx.beginPath();
            ctx.arc(x, y, 2, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(255,102,171,0.08)';
            ctx.fill();
        });
        // Second pass — brighter for key presses
        sampled.filter(f => (f.keys & (KEY_K1|KEY_K2|KEY_M1|KEY_M2)) > 0).forEach(f => {
            ctx.beginPath();
            ctx.arc(Math.max(0,Math.min(511,f.x)), Math.max(0,Math.min(383,f.y)), 3, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(255,102,171,0.3)';
            ctx.fill();
        });
    } catch(e) { showChartError('chart-heatmap', e.message); }

    // Aim Offset Scatter — cursor positions relative to playfield center
    try {
        const centerX = 256, centerY = 192;
        const keyFrames = downsample(frames.filter(f => (f.keys & (KEY_K1|KEY_K2|KEY_M1|KEY_M2)) > 0), 500);
        const scatterData = keyFrames.map(f => [f.x - centerX, f.y - centerY]);
        new ApexCharts(document.getElementById('chart-aimoffset'), apexDefaults({
            chart:{type:'scatter',height:300,background:'transparent',foreColor:CHART_COLORS.muted,zoom:{enabled:false}},
            series:[{name:'Offset',data:scatterData}],
            colors:[CHART_COLORS.accent],
            xaxis:{type:'numeric',min:-256,max:256,tickAmount:4,title:{text:'X Offset (px)',style:{color:CHART_COLORS.muted}},labels:{style:{colors:CHART_COLORS.muted}}},
            yaxis:{min:-192,max:192,title:{text:'Y Offset (px)',style:{color:CHART_COLORS.muted}},labels:{style:{colors:CHART_COLORS.muted}}},
            markers:{size:3,strokeWidth:0,hover:{size:5}},
        })).render();
    } catch(e) { showChartError('chart-aimoffset', e.message); }

    // Cursor Speed Over Time
    try {
        const sampled = downsample(frames, 500);
        const speedData = [];
        for (let i = 1; i < sampled.length; i++) {
            const dt = sampled[i].t - sampled[i-1].t;
            if (dt <= 0) continue;
            const dx = sampled[i].x - sampled[i-1].x;
            const dy = sampled[i].y - sampled[i-1].y;
            const speed = Math.sqrt(dx*dx + dy*dy) / dt; // px/ms
            speedData.push({ x: sampled[i].t, y: parseFloat((speed * 1000).toFixed(0)) }); // px/s
        }
        new ApexCharts(document.getElementById('chart-cursorspeed'), apexDefaults({
            chart:{type:'area',height:300,background:'transparent',foreColor:CHART_COLORS.muted},
            series:[{name:'Speed (px/s)',data:downsample(speedData,300)}],
            colors:[CHART_COLORS.cyan],
            stroke:{curve:'smooth',width:1.5},
            fill:{type:'gradient',gradient:{shadeIntensity:1,opacityFrom:0.4,opacityTo:0.05}},
            xaxis:{type:'numeric',labels:{style:{colors:CHART_COLORS.muted},formatter:v=>(v/1000).toFixed(0)+'s'}},
            yaxis:{labels:{style:{colors:CHART_COLORS.muted}}},
        })).render();
    } catch(e) { showChartError('chart-cursorspeed', e.message); }
}

// ═══════════════════════════════════════════════════════
// Rhythm Charts (frames)
// ═══════════════════════════════════════════════════════
function renderRhythmCharts(frames) {
    // Combo Over Time — simulate via key press counting
    try {
        const sampled = downsample(frames, 500);
        let combo = 0, comboData = [];
        sampled.forEach(f => {
            if ((f.keys & (KEY_K1|KEY_K2|KEY_M1|KEY_M2)) > 0) { combo++; }
            comboData.push({ x: f.t, y: combo });
        });
        new ApexCharts(document.getElementById('chart-combo'), apexDefaults({
            chart:{type:'area',height:260,background:'transparent',foreColor:CHART_COLORS.muted},
            series:[{name:'Combo',data:downsample(comboData,300)}],
            colors:[CHART_COLORS.purple],
            stroke:{curve:'stepline',width:2},
            fill:{type:'gradient',gradient:{shadeIntensity:1,opacityFrom:0.4,opacityTo:0.05}},
            xaxis:{type:'numeric',labels:{style:{colors:CHART_COLORS.muted},formatter:v=>(v/1000).toFixed(0)+'s'}},
            yaxis:{labels:{style:{colors:CHART_COLORS.muted}}},
        })).render();
    } catch(e) { showChartError('chart-combo', e.message); }

    // Key Press Cadence — K1 vs K2 over time bins
    try {
        const maxT = frames[frames.length-1].t;
        const binCount = 20;
        const binSize = maxT / binCount;
        const k1Bins = Array(binCount).fill(0);
        const k2Bins = Array(binCount).fill(0);
        const labels = [];
        for (let i = 0; i < binCount; i++) { labels.push(((i*binSize)/1000).toFixed(0)+'s'); }
        frames.forEach(f => {
            const idx = Math.min(Math.floor(f.t / binSize), binCount-1);
            if (f.keys & KEY_K1) k1Bins[idx]++;
            if (f.keys & KEY_K2) k2Bins[idx]++;
            // Also count mouse as primary/secondary
            if (f.keys & KEY_M1) k1Bins[idx]++;
            if (f.keys & KEY_M2) k2Bins[idx]++;
        });
        new ApexCharts(document.getElementById('chart-keys'), apexDefaults({
            chart:{type:'bar',height:260,background:'transparent',foreColor:CHART_COLORS.muted,stacked:true},
            series:[{name:'K1/M1',data:k1Bins},{name:'K2/M2',data:k2Bins}],
            colors:[CHART_COLORS.accent,CHART_COLORS.accent2],
            plotOptions:{bar:{borderRadius:2,columnWidth:'70%'}},
            xaxis:{categories:labels,labels:{style:{colors:CHART_COLORS.muted,fontSize:'9px'},rotate:-45},tickAmount:10},
            yaxis:{labels:{style:{colors:CHART_COLORS.muted}}},
            legend:{labels:{colors:CHART_COLORS.muted}},
        })).render();
    } catch(e) { showChartError('chart-keys', e.message); }
}

// ═══════════════════════════════════════════════════════
// Meta Charts (computed from all sources)
// ═══════════════════════════════════════════════════════
function renderMetaCharts(frames, analyticsData) {
    // Skill Radar
    try {
        const stats = analyticsData.hit_counts || {};
        const perf = analyticsData.performance || {};
        const h300 = stats['300s']||stats.count_300||0, h100 = stats['100s']||stats.count_100||0;
        const h50 = stats['50s']||stats.count_50||0, miss = stats.misses||0;
        const total = h300+h100+h50+miss || 1;
        const acc = (h300*300+h100*100+h50*50)/(total*300)*100;
        // Compute metrics
        const keyFrames = frames.filter(f => (f.keys & (KEY_K1|KEY_K2|KEY_M1|KEY_M2)) > 0);
        let speeds = [];
        for (let i = 1; i < Math.min(frames.length, 2000); i++) {
            const dt = frames[i].t - frames[i-1].t;
            if (dt > 0) speeds.push(Math.sqrt((frames[i].x-frames[i-1].x)**2 + (frames[i].y-frames[i-1].y)**2)/dt);
        }
        const avgSpeed = speeds.length ? speeds.reduce((a,b)=>a+b,0)/speeds.length : 0;
        const maxSpeed = speeds.length ? Math.max(...speeds) : 0;
        // Normalize to 0-100 scale
        const aimScore = Math.min(100, avgSpeed * 200);
        const speedScore = Math.min(100, maxSpeed * 100);
        const comboScore = Math.min(100, ((stats.max_combo||0) / total) * 100);
        const ppScore = Math.min(100, (perf.pp||0) / 5);
        new ApexCharts(document.getElementById('chart-radar'), {
            chart:{type:'radar',height:300,background:'transparent',foreColor:CHART_COLORS.muted,toolbar:{show:false}},
            series:[{name:'Performance',data:[
                parseFloat(acc.toFixed(1)),
                parseFloat(aimScore.toFixed(1)),
                parseFloat(speedScore.toFixed(1)),
                parseFloat(comboScore.toFixed(1)),
                parseFloat(ppScore.toFixed(1)),
                parseFloat((100 - miss/total*100).toFixed(1))
            ]}],
            labels:['Accuracy','Aim','Speed','Combo','PP','Consistency'],
            colors:[CHART_COLORS.accent],
            fill:{opacity:0.2},
            stroke:{width:2},
            markers:{size:3},
            yaxis:{show:false},
            xaxis:{labels:{style:{colors:CHART_COLORS.muted,fontSize:'11px'}}},
        }).render();
    } catch(e) { showChartError('chart-radar', e.message); }

    // Section Report Card
    try {
        const maxT = frames[frames.length-1].t;
        const sectionCount = 5;
        const sectionSize = maxT / sectionCount;
        const container = document.getElementById('chart-sections');
        let html = '<table class="report-table"><thead><tr><th>Section</th><th>Time</th><th>Key Presses</th><th>Avg Speed</th><th>Grade</th></tr></thead><tbody>';
        for (let i = 0; i < sectionCount; i++) {
            const start = i * sectionSize, end = (i+1) * sectionSize;
            const sectionFrames = frames.filter(f => f.t >= start && f.t < end);
            const keys = sectionFrames.filter(f => (f.keys & (KEY_K1|KEY_K2|KEY_M1|KEY_M2)) > 0).length;
            let speeds = [];
            for (let j = 1; j < sectionFrames.length; j++) {
                const dt = sectionFrames[j].t - sectionFrames[j-1].t;
                if (dt > 0) speeds.push(Math.sqrt((sectionFrames[j].x-sectionFrames[j-1].x)**2 + (sectionFrames[j].y-sectionFrames[j-1].y)**2)/dt*1000);
            }
            const avgSpd = speeds.length ? (speeds.reduce((a,b)=>a+b,0)/speeds.length).toFixed(0) : '0';
            const density = sectionFrames.length ? keys / sectionFrames.length : 0;
            let grade, gradeClass;
            if (density > 0.4) { grade='S'; gradeClass='grade-s'; }
            else if (density > 0.3) { grade='A'; gradeClass='grade-a'; }
            else if (density > 0.2) { grade='B'; gradeClass='grade-b'; }
            else { grade='C'; gradeClass='grade-c'; }
            html += `<tr><td>Section ${i+1}</td><td>${(start/1000).toFixed(0)}s–${(end/1000).toFixed(0)}s</td><td>${keys}</td><td>${avgSpd} px/s</td><td><span class="grade-cell ${gradeClass}">${grade}</span></td></tr>`;
        }
        html += '</tbody></table>';
        container.innerHTML = html;
    } catch(e) { showChartError('chart-sections', e.message); }
}

// ═══════════════════════════════════════════════════════
// Main Analytics Loader
// ═══════════════════════════════════════════════════════
let analyticsLoaded = false;
async function loadAnalytics(jobId) {
    if (analyticsLoaded) return;
    analyticsLoaded = true;

    try {
        const res = await fetch(`/v1/jobs/${jobId}/analytics`);
        if (res.status === 202) {
            analyticsLoaded = false;
            return; // Analytics not ready, allow retry
        }
        if (!res.ok) return;
        const data = await res.json();

        // Life bar
        if (data.life_bar && data.life_bar.length > 0) {
            try { renderLifeBar(data.life_bar); }
            catch(e) { showChartError('chart-lifebar', e.message); }
        }

        // Frame-dependent charts
        if (data.frames_url) {
            try {
                const framesRes = await fetch(data.frames_url);
                const buffer = await framesRes.arrayBuffer();
                const ds = new DecompressionStream('gzip');
                const decompressed = new Response(new Blob([buffer]).stream().pipeThrough(ds));
                const frames = await decompressed.json();

                try { renderTimingCharts(frames); }
                catch(e) { showChartError('chart-hiterror', e.message); }

                try { renderCursorCharts(frames); }
                catch(e) { showChartError('chart-heatmap', e.message); }

                try { renderRhythmCharts(frames); }
                catch(e) { showChartError('chart-combo', e.message); }

                try { renderMetaCharts(frames, data); }
                catch(e) { showChartError('chart-radar', e.message); }
            } catch(e) {
                console.error('Failed to fetch/decompress frames:', e);
                ['chart-lifebar','chart-hiterror','chart-acctime','chart-heatmap','chart-aimoffset','chart-cursorspeed','chart-combo','chart-keys','chart-radar','chart-sections'].forEach(id => showChartError(id, 'Frame data unavailable'));
            }
        } else {
            // No frames — clear skeletons
            ['chart-lifebar','chart-hiterror','chart-acctime','chart-heatmap','chart-aimoffset','chart-cursorspeed','chart-combo','chart-keys','chart-radar','chart-sections'].forEach(id => {
                const el = document.getElementById(id);
                if (el && el.querySelector('.chart-skeleton')) el.innerHTML = '<div class="chart-error"><i class="fas fa-info-circle"></i> No frame data available for this replay</div>';
            });
        }
    } catch(e) {
        console.error('Analytics load failed:', e);
    }
}
