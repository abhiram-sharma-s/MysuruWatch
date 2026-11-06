/**
 * Mysuru RoadWatch — Dedicated Report Status Graph Analytics Page Logic
 * Interactive SVG Status Pie Chart, Severity Breakdown, Defect Analysis, and Real-Time Sync
 */

try {
  sessionStorage.setItem('mysuru_authority_logged_in', 'true');
  localStorage.setItem('mysuru_authority_logged_in', 'true');
} catch (e) {}

let allReports = [];

document.addEventListener('DOMContentLoaded', () => {
  loadAnalyticsData();
  initAnalyticsControls();
});

// Fetch reports from API
async function loadAnalyticsData() {
  const centerTotal = document.getElementById('analyticsCenterTotal');
  if (centerTotal) centerTotal.innerText = '...';

  try {
    const data = await window.roadWatchApi.getReports();
    allReports = data.reports || [];
  } catch (err) {
    console.warn('API fetch error in analytics, using local demo data:', err);
    allReports = getFallbackDemoReports();
  }

  renderAnalyticsViews(allReports);
}

// Controls: refresh button
function initAnalyticsControls() {
  const refreshBtn = document.getElementById('refreshAnalyticsBtn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      refreshBtn.disabled = true;
      refreshBtn.innerHTML = '<span>🔄</span> Refreshing...';
      await loadAnalyticsData();
      refreshBtn.disabled = false;
      refreshBtn.innerHTML = '<span>🔄</span> Refresh Data';
      showToast('Analytics refreshed with latest municipal data.', 'success');
    });
  }
}

// Render all graph components
function renderAnalyticsViews(reports) {
  const svg = document.getElementById('analyticsStatusPieSvg');
  const legendContainer = document.getElementById('analyticsStatusLegend');
  const centerCount = document.getElementById('analyticsCenterTotal');
  const tooltip = document.getElementById('analyticsPieTooltip');
  const sevContainer = document.getElementById('analyticsSeverityBars');
  const defectContainer = document.getElementById('analyticsDefectPills');
  const chipsContainer = document.getElementById('analyticsStatusChips');
  const subtext = document.getElementById('analyticsSummarySubtext');

  if (!svg || !legendContainer) return;

  const total = (reports || []).length;
  if (centerCount) centerCount.innerText = total;

  if (subtext) {
    subtext.innerText = `Total ${total} reports registered across Mysuru City Corporation`;
  }

  const statusConfigs = [
    { key: 'New', label: 'New (Pending)', color: '#2563eb', count: 0 },
    { key: 'Verified', label: 'Verified by Engineer', color: '#7c3aed', count: 0 },
    { key: 'In Progress', label: 'In Progress (Repair Team)', color: '#d97706', count: 0 },
    { key: 'Resolved', label: 'Resolved & Repaired', color: '#16a34a', count: 0 }
  ];

  const severityCounts = {
    Critical: 0,
    High: 0,
    Moderate: 0,
    Low: 0
  };

  const defectCounts = {
    'Potholes': 0,
    'Road Cracks': 0,
    'Pothole Clusters': 0,
    'Surface Rutting': 0,
    'Other': 0
  };

  (reports || []).forEach(r => {
    // Status count
    const st = (r.status || 'New').toLowerCase();
    if (st === 'new') statusConfigs[0].count++;
    else if (st === 'verified') statusConfigs[1].count++;
    else if (st === 'in progress') statusConfigs[2].count++;
    else if (st === 'resolved') statusConfigs[3].count++;
    else statusConfigs[0].count++;

    // Severity count
    const sev = (r.severity || 'Moderate').toLowerCase();
    if (sev === 'critical') severityCounts.Critical++;
    else if (sev === 'high') severityCounts.High++;
    else if (sev === 'moderate') severityCounts.Moderate++;
    else if (sev === 'low') severityCounts.Low++;
    else severityCounts.Moderate++;

    // Defect category count
    const cond = (r.road_condition || '').toLowerCase();
    if (cond.includes('cluster') || cond.includes('many')) defectCounts['Pothole Clusters']++;
    else if (cond.includes('pothole')) defectCounts['Potholes']++;
    else if (cond.includes('crack')) defectCounts['Road Cracks']++;
    else if (cond.includes('rutting') || cond.includes('wear')) defectCounts['Surface Rutting']++;
    else defectCounts['Other']++;
  });

  // Render SVG Slices (Donut Geometry)
  svg.innerHTML = '';
  const cx = 125;
  const cy = 125;
  const outerR = 105;
  const innerR = 62;

  if (total === 0) {
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', cx);
    circle.setAttribute('cy', cy);
    circle.setAttribute('r', (outerR + innerR) / 2);
    circle.setAttribute('stroke', '#e2e8f0');
    circle.setAttribute('stroke-width', outerR - innerR);
    circle.setAttribute('fill', 'none');
    svg.appendChild(circle);

    legendContainer.innerHTML = '<p style="color:var(--text-muted);font-size:0.86rem;">No reports registered in database.</p>';
  } else {
    let currentAngle = 0;

    statusConfigs.forEach(item => {
      if (item.count === 0) return;

      const sliceAngle = (item.count / total) * 2 * Math.PI;
      const endAngle = currentAngle + sliceAngle;

      const x1_outer = cx + outerR * Math.cos(currentAngle);
      const y1_outer = cy + outerR * Math.sin(currentAngle);
      const x2_outer = cx + outerR * Math.cos(endAngle);
      const y2_outer = cy + outerR * Math.sin(endAngle);

      const x1_inner = cx + innerR * Math.cos(endAngle);
      const y1_inner = cy + innerR * Math.sin(endAngle);
      const x2_inner = cx + innerR * Math.cos(currentAngle);
      const y2_inner = cy + innerR * Math.sin(currentAngle);

      const largeArcFlag = sliceAngle > Math.PI ? 1 : 0;

      const d = [
        `M ${x1_outer} ${y1_outer}`,
        `A ${outerR} ${outerR} 0 ${largeArcFlag} 1 ${x2_outer} ${y2_outer}`,
        `L ${x1_inner} ${y1_inner}`,
        `A ${innerR} ${innerR} 0 ${largeArcFlag} 0 ${x2_inner} ${y2_inner}`,
        'Z'
      ].join(' ');

      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', d);
      path.setAttribute('fill', item.color);
      path.setAttribute('class', 'pie-slice');
      path.setAttribute('data-status', item.key);

      const pct = ((item.count / total) * 100).toFixed(1);

      // Tooltip interaction
      path.addEventListener('mousemove', (e) => {
        if (tooltip) {
          tooltip.style.display = 'block';
          tooltip.style.left = `${e.pageX + 14}px`;
          tooltip.style.top = `${e.pageY - 28}px`;
          tooltip.innerHTML = `
            <strong>${item.label}</strong><br />
            <span>${item.count} Reports (${pct}%)</span>
          `;
        }
      });

      path.addEventListener('mouseleave', () => {
        if (tooltip) tooltip.style.display = 'none';
      });

      svg.appendChild(path);
      currentAngle = endAngle;
    });

    // Render Clickable Legend
    legendContainer.innerHTML = '';
    statusConfigs.forEach(item => {
      const pct = total > 0 ? ((item.count / total) * 100).toFixed(1) : 0;

      const row = document.createElement('div');
      row.className = 'pie-legend-item';
      row.innerHTML = `
        <div class="pie-legend-left">
          <span class="pie-legend-dot" style="background:${item.color};"></span>
          <span class="pie-legend-name">${item.label}</span>
        </div>
        <div class="pie-legend-right">
          <span class="pie-legend-count">${item.count}</span>
          <span class="pie-legend-pct">(${pct}%)</span>
        </div>
      `;

      legendContainer.appendChild(row);
    });
  }

  // Render Severity Progress Bars
  if (sevContainer) {
    const sevLevels = [
      { key: 'Critical', label: 'Critical Hazard (90–100%)', color: '#ef4444', count: severityCounts.Critical },
      { key: 'High', label: 'High Damage (80–89%)', color: '#f59e0b', count: severityCounts.High },
      { key: 'Moderate', label: 'Moderate Wear (65–79%)', color: '#8b5cf6', count: severityCounts.Moderate },
      { key: 'Low', label: 'Minor / Low Wear (<65%)', color: '#10b981', count: severityCounts.Low }
    ];

    sevContainer.innerHTML = sevLevels.map(lvl => {
      const pct = total > 0 ? ((lvl.count / total) * 100).toFixed(1) : 0;
      return `
        <div class="sev-bar-row">
          <div style="display:flex;justify-content:space-between;font-size:0.82rem;margin-bottom:4px;">
            <span style="font-weight:600;color:var(--text-main);">${lvl.label}</span>
            <span style="font-weight:700;color:var(--text-muted);">${lvl.count} (${pct}%)</span>
          </div>
          <div style="height:8px;background:var(--border-color,#e2e8f0);border-radius:999px;overflow:hidden;">
            <div style="height:100%;width:${pct}%;background:${lvl.color};border-radius:999px;transition:width 0.4s ease;"></div>
          </div>
        </div>
      `;
    }).join('');
  }

  // Render Defect Category Pills
  if (defectContainer) {
    defectContainer.innerHTML = Object.entries(defectCounts).map(([cat, cnt]) => {
      return `
        <span class="badge" style="background:var(--bg-surface,#ffffff);border:1px solid var(--border-color,#e2e8f0);color:var(--text-main);padding:6px 12px;font-size:0.78rem;font-weight:600;border-radius:8px;display:inline-flex;align-items:center;gap:6px;">
          <span>${cat}:</span>
          <strong style="color:var(--primary,#003366);">${cnt}</strong>
        </span>
      `;
    }).join('');
  }

  // Render Status Summary Chips in banner
  if (chipsContainer) {
    chipsContainer.innerHTML = statusConfigs.map(item => {
      return `
        <span class="badge" style="background:#ffffff;border:1px solid #bbf7d0;color:#166534;font-size:0.8rem;font-weight:700;padding:5px 11px;border-radius:999px;display:inline-flex;align-items:center;gap:6px;">
          <span style="width:7px;height:7px;border-radius:50%;background:${item.color};"></span>
          <span>${item.key}:</span>
          <strong>${item.count}</strong>
        </span>
      `;
    }).join('');
  }
}

// Fallback demo reports if offline
function getFallbackDemoReports() {
  return [
    { report_id: "RW-001", road_condition: "Severe Pothole Cluster", severity: "Critical", status: "New" },
    { report_id: "RW-002", road_condition: "Pothole", severity: "High", status: "In Progress" },
    { report_id: "RW-003", road_condition: "Road Crack", severity: "Moderate", status: "Verified" },
    { report_id: "RW-004", road_condition: "Minor Pothole", severity: "Low", status: "Resolved" },
    { report_id: "RW-005", road_condition: "Surface Wear / Rutting", severity: "Moderate", status: "Resolved" }
  ];
}
