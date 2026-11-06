/**
 * Mysuru RoadWatch — Dedicated Report Export & Date Filtering Page Logic
 * Handles submission date range filtering, live preview, CSV generation, and automatic redirection to authority.html
 */

try {
  sessionStorage.setItem('mysuru_authority_logged_in', 'true');
  localStorage.setItem('mysuru_authority_logged_in', 'true');
} catch (e) {}

let allReports = [];
let filteredReports = [];

document.addEventListener('DOMContentLoaded', () => {
  loadExportReportsData();
  initExportFilters();
  initExportAction();
});

// Fetch all reports from server
async function loadExportReportsData() {
  try {
    const data = await window.roadWatchApi.getReports();
    allReports = data.reports || [];
  } catch (err) {
    console.warn('API error in export center, using fallback demo data:', err);
    allReports = getFallbackDemoReports();
  }

  // Pre-fill query parameters if navigated from authority toolbar
  applyUrlQueryParams();
  filterAndRender();
}

// Read URL parameters
function applyUrlQueryParams() {
  const urlParams = new URLSearchParams(window.location.search);
  const startParam = urlParams.get('start_date');
  const endParam = urlParams.get('end_date');
  const statusParam = urlParams.get('status');
  const severityParam = urlParams.get('severity');
  const searchParam = urlParams.get('search');

  const startInput = document.getElementById('exportStartDate');
  const endInput = document.getElementById('exportEndDate');
  const statusSelect = document.getElementById('exportStatusSelect');
  const severitySelect = document.getElementById('exportSeveritySelect');
  const searchInput = document.getElementById('exportSearchInput');

  if (startParam && startInput) startInput.value = startParam;
  if (endParam && endInput) endInput.value = endParam;
  if (statusParam && statusSelect) statusSelect.value = statusParam;
  if (severityParam && severitySelect) severitySelect.value = severityParam;
  if (searchParam && searchInput) searchInput.value = searchParam;

  if (startParam || endParam) {
    clearPresetActiveClasses();
  }
}

// Date Normalization Helper
function getReportDateYmd(report) {
  if (!report) return '';
  if (report.created_at && typeof report.created_at === 'string' && /^\d{4}-\d{2}-\d{2}/.test(report.created_at)) {
    return report.created_at.slice(0, 10);
  }

  const dateStr = (report.date || '').trim();
  if (!dateStr) return '';

  const isoMatch = dateStr.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})/);
  if (isoMatch) {
    const y = isoMatch[1];
    const m = String(isoMatch[2]).padStart(2, '0');
    const d = String(isoMatch[3]).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  const monthMap = {
    jan: '01', feb: '02', mar: '03', apr: '04', may: '05', jun: '06',
    jul: '07', aug: '08', sep: '09', oct: '10', nov: '11', dec: '12'
  };
  const dmyAlpha = dateStr.match(/^(\d{1,2})[- ]([A-Za-z]{3})[- ](\d{4})/i);
  if (dmyAlpha) {
    const d = String(dmyAlpha[1]).padStart(2, '0');
    const m = monthMap[dmyAlpha[2].toLowerCase()] || '01';
    const y = dmyAlpha[3];
    return `${y}-${m}-${d}`;
  }

  const dmyNum = dateStr.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})/);
  if (dmyNum) {
    const d = String(dmyNum[1]).padStart(2, '0');
    const m = String(dmyNum[2]).padStart(2, '0');
    const y = dmyNum[3];
    return `${y}-${m}-${d}`;
  }

  try {
    const d = new Date(dateStr);
    if (!isNaN(d.getTime())) {
      const year = d.getFullYear();
      const month = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    }
  } catch (e) {}

  return '';
}

function formatYmdFriendly(ymd) {
  if (!ymd) return '';
  const parts = ymd.split('-');
  if (parts.length !== 3) return ymd;
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const mIdx = parseInt(parts[1], 10) - 1;
  const mStr = (mIdx >= 0 && mIdx < 12) ? monthNames[mIdx] : parts[1];
  return `${parts[2]}-${mStr}-${parts[0]}`;
}

// Preset Buttons
function clearPresetActiveClasses() {
  document.querySelectorAll('.csv-preset-btn').forEach(b => b.classList.remove('active'));
}

function applyDatePreset(preset) {
  const startInput = document.getElementById('exportStartDate');
  const endInput = document.getElementById('exportEndDate');
  if (!startInput || !endInput) return;

  const now = new Date();
  const formatYmd = (d) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  };

  const todayStr = formatYmd(now);

  if (preset === 'all') {
    startInput.value = '';
    endInput.value = '';
  } else if (preset === 'today') {
    startInput.value = todayStr;
    endInput.value = todayStr;
  } else if (preset === 'yesterday') {
    const yest = new Date(now);
    yest.setDate(now.getDate() - 1);
    const yestStr = formatYmd(yest);
    startInput.value = yestStr;
    endInput.value = yestStr;
  } else if (preset === 'last7') {
    const d7 = new Date(now);
    d7.setDate(now.getDate() - 6);
    startInput.value = formatYmd(d7);
    endInput.value = todayStr;
  } else if (preset === 'last30') {
    const d30 = new Date(now);
    d30.setDate(now.getDate() - 29);
    startInput.value = formatYmd(d30);
    endInput.value = todayStr;
  } else if (preset === 'thisMonth') {
    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
    startInput.value = formatYmd(firstDay);
    endInput.value = todayStr;
  }
}

// Filter listeners
function initExportFilters() {
  const startInput = document.getElementById('exportStartDate');
  const endInput = document.getElementById('exportEndDate');
  const statusSelect = document.getElementById('exportStatusSelect');
  const severitySelect = document.getElementById('exportSeveritySelect');
  const searchInput = document.getElementById('exportSearchInput');
  const refreshBtn = document.getElementById('refreshExportDataBtn');

  if (startInput) {
    startInput.addEventListener('change', () => {
      clearPresetActiveClasses();
      filterAndRender();
    });
  }

  if (endInput) {
    endInput.addEventListener('change', () => {
      clearPresetActiveClasses();
      filterAndRender();
    });
  }

  if (statusSelect) statusSelect.addEventListener('change', filterAndRender);
  if (severitySelect) severitySelect.addEventListener('change', filterAndRender);
  if (searchInput) searchInput.addEventListener('input', filterAndRender);

  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      loadExportReportsData();
      showToast('Export data refreshed.', 'info');
    });
  }

  document.querySelectorAll('.csv-preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      clearPresetActiveClasses();
      btn.classList.add('active');
      applyDatePreset(btn.dataset.preset);
      filterAndRender();
    });
  });
}

// Compute filtered reports and update UI
function filterAndRender() {
  const startInput = document.getElementById('exportStartDate');
  const endInput = document.getElementById('exportEndDate');
  const statusSelect = document.getElementById('exportStatusSelect');
  const severitySelect = document.getElementById('exportSeveritySelect');
  const searchInput = document.getElementById('exportSearchInput');

  const start = startInput ? startInput.value.trim() : '';
  const end = endInput ? endInput.value.trim() : '';
  const status = statusSelect ? statusSelect.value : 'all';
  const severity = severitySelect ? severitySelect.value : 'all';
  const query = searchInput ? searchInput.value.trim().toLowerCase() : '';

  filteredReports = allReports.filter(r => {
    const ymd = getReportDateYmd(r);
    // Date bounds
    if (start && ymd && ymd < start) return false;
    if (end && ymd && ymd > end) return false;

    // Status
    if (status !== 'all' && (r.status || '').toLowerCase() !== status.toLowerCase()) return false;

    // Severity
    if (severity !== 'all' && (r.severity || '').toLowerCase() !== severity.toLowerCase()) return false;

    // Search
    if (query) {
      const match = (r.report_id || '').toLowerCase().includes(query)
        || (r.location || '').toLowerCase().includes(query)
        || (r.road_condition || '').toLowerCase().includes(query)
        || (r.description || '').toLowerCase().includes(query);
      if (!match) return false;
    }

    return true;
  });

  updateSummaryCard(start, end, status, severity);
  renderPreviewTable();
}

// Update the dynamic summary banner & buttons
function updateSummaryCard(start, end, status, severity) {
  const summaryBox = document.getElementById('exportSummaryBox');
  const iconEl = document.getElementById('exportSummaryIcon');
  const headlineEl = document.getElementById('exportCountHeadline');
  const subtextEl = document.getElementById('exportSubtext');
  const rangeBadge = document.getElementById('exportRangeBadge');
  const filenamePreview = document.getElementById('exportFilenamePreview');
  const startExportBtn = document.getElementById('startExportBtn');
  const btnCountSpan = document.getElementById('exportBtnCount');

  // Range text
  let rangeDesc = 'All Dates';
  if (start && end) {
    rangeDesc = (start === end) ? formatYmdFriendly(start) : `${formatYmdFriendly(start)} to ${formatYmdFriendly(end)}`;
  } else if (start) {
    rangeDesc = `From ${formatYmdFriendly(start)}`;
  } else if (end) {
    rangeDesc = `Until ${formatYmdFriendly(end)}`;
  }

  if (rangeBadge) rangeBadge.innerText = rangeDesc;

  // Filename calculation
  let fileSlug = 'All_Dates';
  if (start && end) {
    fileSlug = `${start}_to_${end}`;
  } else if (start) {
    fileSlug = `from_${start}`;
  } else if (end) {
    fileSlug = `until_${end}`;
  }
  const filename = `Mysuru_RoadWatch_Reports_${fileSlug}.csv`;
  if (filenamePreview) filenamePreview.innerText = filename;

  if (btnCountSpan) btnCountSpan.innerText = filteredReports.length;

  if (filteredReports.length > 0) {
    if (summaryBox) {
      summaryBox.style.background = '#f0fdf4';
      summaryBox.style.borderColor = '#bbf7d0';
    }
    if (iconEl) iconEl.innerText = '✅';
    if (headlineEl) {
      headlineEl.innerText = `${filteredReports.length} Report(s) Ready to Export`;
      headlineEl.style.color = '#166534';
    }
    if (subtextEl) {
      let msg = `Filtered by dates: ${rangeDesc}.`;
      if (status !== 'all') msg += ` Status: ${status}.`;
      if (severity !== 'all') msg += ` Severity: ${severity}.`;
      subtextEl.innerText = msg;
      subtextEl.style.color = '#15803d';
    }
    if (startExportBtn) {
      startExportBtn.disabled = false;
      startExportBtn.style.opacity = '1';
      startExportBtn.style.cursor = 'pointer';
      startExportBtn.innerHTML = `<span>📥</span> Export & Download CSV (${filteredReports.length} Reports)`;
    }
  } else {
    if (summaryBox) {
      summaryBox.style.background = '#fef2f2';
      summaryBox.style.borderColor = '#fecaca';
    }
    if (iconEl) iconEl.innerText = '⚠️';
    if (headlineEl) {
      headlineEl.innerText = '0 Reports Match the Selected Filter';
      headlineEl.style.color = '#991b1b';
    }
    if (subtextEl) {
      subtextEl.innerText = `No reports found for ${rangeDesc}. Try adjusting or clearing your date bounds.`;
      subtextEl.style.color = '#b91c1c';
    }
    if (startExportBtn) {
      startExportBtn.disabled = true;
      startExportBtn.style.opacity = '0.5';
      startExportBtn.style.cursor = 'not-allowed';
      startExportBtn.innerHTML = `<span>📥</span> No Matching Reports to Export`;
    }
  }
}

// Render the preview table
function renderPreviewTable() {
  const tbody = document.getElementById('exportPreviewTableBody');
  const countEl = document.getElementById('previewTableCount');
  if (!tbody) return;

  if (countEl) {
    countEl.innerText = `Showing ${filteredReports.length} record(s) matching your date filter (Total in database: ${allReports.length})`;
  }

  if (filteredReports.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6">
          <div class="empty-state" style="padding: 30px 15px;">
            <div class="icon">🔍</div>
            <h3>No reports match this date range</h3>
            <p>Please widen your From/To dates or select 'All Dates' preset above.</p>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filteredReports.map(r => {
    const sevBadge = (typeof getSeverityBadge === 'function') 
      ? getSeverityBadge(r.severity, false, r.road_condition) 
      : `<span class="badge badge-moderate">${r.severity || 'Moderate'}</span>`;

    const st = (r.status || 'New').toLowerCase().replace(' ', '-');

    return `
      <tr>
        <td><strong style="color:var(--color-primary);">${r.report_id}</strong></td>
        <td><strong>${r.road_condition || 'Pothole'}</strong></td>
        <td>${sevBadge}</td>
        <td style="max-width: 220px;">
          <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${r.location || ''}">
            ${r.location || 'Mysuru Road'}
          </div>
          <small style="color:var(--text-muted);">${r.road_type || 'City road'}</small>
        </td>
        <td>
          <div style="font-size:0.82rem;font-weight:600;white-space:nowrap;">${r.date || '—'}</div>
          <small style="color:var(--text-muted);">${r.time || ''}</small>
        </td>
        <td>
          <span class="badge badge-${st}">${r.status || 'New'}</span>
        </td>
      </tr>
    `;
  }).join('');
}

// Export Trigger & Automatic Redirection
function initExportAction() {
  const exportBtn = document.getElementById('startExportBtn');
  if (!exportBtn) return;

  exportBtn.addEventListener('click', () => {
    if (!filteredReports || filteredReports.length === 0) {
      showToast('No reports match the selected date range to download.', 'warning');
      return;
    }

    const startInput = document.getElementById('exportStartDate');
    const endInput = document.getElementById('exportEndDate');
    const start = startInput ? startInput.value.trim() : '';
    const end = endInput ? endInput.value.trim() : '';

    // 1. Build CSV content
    const headers = [
      'Report ID',
      'Road Condition',
      'Severity',
      'AI Confidence',
      'Location',
      'Google Maps Link',
      'Status',
      'Submission Date',
      'Submission Time',
      'ISO Timestamp',
      'Reporter Name',
      'Road Type',
      'Description',
      'Authority Notes'
    ];

    const rows = filteredReports.map(r => [
      `"${r.report_id || ''}"`,
      `"${r.road_condition || ''}"`,
      `"${r.severity || ''}"`,
      `"${r.confidence_display || (r.confidence ? Math.round(r.confidence * 100) + '%' : '-')}"`,
      `"${(r.location || '').replace(/"/g, '""')}"`,
      `"${r.google_maps_link || ''}"`,
      `"${r.status || 'New'}"`,
      `"${r.date || ''}"`,
      `"${r.time || ''}"`,
      `"${r.created_at || ''}"`,
      `"${(r.reporter_name || 'Mysuru Citizen').replace(/"/g, '""')}"`,
      `"${(r.road_type || 'City road').replace(/"/g, '""')}"`,
      `"${(r.description || '').replace(/"/g, '""')}"`,
      `"${(r.authority_notes || '').replace(/"/g, '""')}"`
    ]);

    // UTF-8 BOM (\uFEFF) for Excel compatibility
    const csvContent = 'data:text/csv;charset=utf-8,\uFEFF' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);

    let fileSlug = 'All_Dates';
    if (start && end) {
      fileSlug = `${start}_to_${end}`;
    } else if (start) {
      fileSlug = `from_${start}`;
    } else if (end) {
      fileSlug = `until_${end}`;
    }
    const filename = `Mysuru_RoadWatch_Reports_${fileSlug}.csv`;

    // 2. Trigger direct download
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();

    // 3. Format date range label for feedback message
    let rangeDesc = 'All Dates';
    if (start && end) rangeDesc = `${formatYmdFriendly(start)} to ${formatYmdFriendly(end)}`;
    else if (start) rangeDesc = `from ${formatYmdFriendly(start)}`;
    else if (end) rangeDesc = `until ${formatYmdFriendly(end)}`;

    const successMessage = `Exported ${filteredReports.length} report(s) (${rangeDesc}) to CSV successfully.`;
    sessionStorage.setItem('roadwatch_export_success', successMessage);

    // 4. Show download and redirection notice
    const redirectBox = document.getElementById('redirectNoticeBox');
    const countdownEl = document.getElementById('redirectCountdown');
    if (redirectBox) {
      redirectBox.style.display = 'block';
      redirectBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    showToast('CSV downloaded successfully! Redirecting to Authority Dashboard...', 'success', 3000);

    // 5. Countdown and Redirect to authority.html
    let secondsLeft = 2;
    if (countdownEl) countdownEl.innerText = secondsLeft;

    const interval = setInterval(() => {
      secondsLeft -= 1;
      if (countdownEl) countdownEl.innerText = secondsLeft;
      if (secondsLeft <= 0) {
        clearInterval(interval);
        window.location.href = 'authority.html?from=export';
      }
    }, 1000);
  });
}

function getFallbackDemoReports() {
  return [
    {
      report_id: "RW-001",
      road_condition: "Pothole",
      severity: "High",
      confidence: 0.94,
      confidence_display: "94%",
      location: "Sayyaji Rao Road, Near Mysore Palace Gate, Mysuru",
      google_maps_link: "https://maps.google.com/?q=12.3051,76.6551",
      description: "Severe pothole right before palace junction.",
      date: "12-Oct-2026",
      time: "10:15 AM",
      status: "New"
    },
    {
      report_id: "RW-002",
      road_condition: "Severe Pothole Cluster",
      severity: "Critical",
      confidence: 0.96,
      confidence_display: "96%",
      location: "KRS Road, Near Vijayanagar 2nd Stage, Mysuru",
      google_maps_link: "https://maps.google.com/?q=12.3385,76.6110",
      description: "Multiple connected potholes across outer lane.",
      date: "12-Oct-2026",
      time: "11:45 AM",
      status: "In Progress"
    },
    {
      report_id: "RW-003",
      road_condition: "Road Crack",
      severity: "Moderate",
      confidence: 0.89,
      confidence_display: "89%",
      location: "Devaraja Urs Road, Mysuru Commercial Zone",
      google_maps_link: "https://maps.google.com/?q=12.3082,76.6450",
      description: "Surface crack spanning multiple vehicle lengths.",
      date: "12-Oct-2026",
      time: "02:30 PM",
      status: "Verified"
    }
  ];
}

