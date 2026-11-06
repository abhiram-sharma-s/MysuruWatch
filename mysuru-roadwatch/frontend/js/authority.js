/**
 * Mysuru RoadWatch — Authority Dashboard Logic
 * Report listing, live filters, status management, inspection modal, CSV export
 */

// Security Passwords for Authority Login
const VALID_SECURITY_PASSWORDS = [
  'admin123',        // Primary default passcode
  'MCC@Mysuru2026',  // Official municipal passcode
  'mysuru2026',
  'admin@mysuru'
];

let allReports = [];
let currentFilterStatus = 'all';
let currentFilterSeverity = 'all';
let currentFilterStartDate = '';
let currentFilterEndDate = '';
let currentSearchQuery = '';
let activeInspectReport = null;

// Real-Time & Login Activity State
let lastLoginNoticeReports = null;
let lastLoginNoticeMeta = null;
let liveMonitorInterval = null;
let knownReportIds = new Set();
let liveReportsReceivedThisSession = [];

document.addEventListener('DOMContentLoaded', () => {
  initAuthoritySecurityLogin();
  initAuthorityFilters();
  initInspectModalActions();
  initExportCsvButton();
  initLoginNoticeBell();
  checkExportSuccessNotice();
});

// Authority Security Login Gatekeeper
function initAuthoritySecurityLogin() {
  // If returning back from export or analytics, seamlessly persist authentication
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const fromPage = urlParams.get('from');
    const ref = (document.referrer || '').toLowerCase();
    if (fromPage === 'export' || fromPage === 'analytics' || ref.indexOf('export') !== -1 || ref.indexOf('analytics') !== -1) {
      sessionStorage.setItem('mysuru_authority_logged_in', 'true');
      localStorage.setItem('mysuru_authority_logged_in', 'true');
    }
  } catch (e) {}

  const overlay = document.getElementById('authorityLoginOverlay');
  const card = document.getElementById('authorityLoginCard');
  const form = document.getElementById('authorityLoginForm');
  const pwdInput = document.getElementById('authorityPasswordInput');
  const toggleBtn = document.getElementById('togglePasswordBtn');
  const logoutBtn = document.getElementById('authorityLogoutBtn');

  // Check if session is already authenticated
  const isAuthenticated = sessionStorage.getItem('mysuru_authority_logged_in') === 'true' ||
                          localStorage.getItem('mysuru_authority_logged_in') === 'true';

  if (isAuthenticated) {
    document.documentElement.classList.add('authority-logged-in');
    if (overlay) overlay.classList.add('hidden');
    loadAuthorityDashboard({ checkLoginNotice: false });
    startRealtimeReportMonitor();
  } else {
    document.documentElement.classList.remove('authority-logged-in');
    if (overlay) overlay.classList.remove('hidden');
    if (pwdInput) setTimeout(() => pwdInput.focus(), 300);
  }

  // Toggle password visibility
  if (toggleBtn && pwdInput) {
    toggleBtn.addEventListener('click', () => {
      if (pwdInput.type === 'password') {
        pwdInput.type = 'text';
        toggleBtn.innerText = '🙈';
      } else {
        pwdInput.type = 'password';
        toggleBtn.innerText = '👁️';
      }
    });
  }

  // Handle Login Form Submit
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const entered = pwdInput.value.trim();

      if (VALID_SECURITY_PASSWORDS.includes(entered)) {
        // Capture previous login timestamp BEFORE saving current login
        const prevLoginIso = localStorage.getItem('roadwatch_authority_last_login');
        const currentLoginIso = new Date().toISOString();
        localStorage.setItem('roadwatch_authority_last_login', currentLoginIso);
        if (prevLoginIso) {
          localStorage.setItem('roadwatch_authority_prev_login', prevLoginIso);
        }

        // Authenticated!
        sessionStorage.setItem('mysuru_authority_logged_in', 'true');
        localStorage.setItem('mysuru_authority_logged_in', 'true');
        document.documentElement.classList.add('authority-logged-in');
        if (overlay) overlay.classList.add('hidden');
        showToast('Access Granted: Welcome, Municipal Authority Officer.', 'success');

        loadAuthorityDashboard({
          checkLoginNotice: true,
          prevLoginIso: prevLoginIso,
          currentLoginIso: currentLoginIso
        });
        startRealtimeReportMonitor();
      } else {
        // Shake card and show error
        if (card) {
          card.classList.remove('shake-animation');
          void card.offsetWidth; // Trigger reflow
          card.classList.add('shake-animation');
        }
        showToast('Access Denied: Incorrect security password. Default is admin123', 'error');
        pwdInput.select();
      }
    });
  }

  // Handle Logout / Lock Panel
  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      sessionStorage.removeItem('mysuru_authority_logged_in');
      localStorage.removeItem('mysuru_authority_logged_in');
      document.documentElement.classList.remove('authority-logged-in');
      stopRealtimeReportMonitor();
      if (overlay) {
        overlay.classList.remove('hidden');
        if (pwdInput) {
          pwdInput.value = '';
          pwdInput.focus();
        }
      }
      showToast('Authority Dashboard locked.', 'info');
    });
  }

  // Re-verify if restored via Back/Forward Cache (bfcache)
  window.addEventListener('pageshow', () => {
    const isAuthed = sessionStorage.getItem('mysuru_authority_logged_in') === 'true' ||
                     localStorage.getItem('mysuru_authority_logged_in') === 'true';
    if (!isAuthed && overlay) {
      document.documentElement.classList.remove('authority-logged-in');
      overlay.classList.remove('hidden');
      stopRealtimeReportMonitor();
      if (pwdInput) {
        pwdInput.value = '';
        setTimeout(() => pwdInput.focus(), 200);
      }
    } else if (isAuthed && overlay) {
      document.documentElement.classList.add('authority-logged-in');
      overlay.classList.add('hidden');
    }
  });
}

// Load reports and KPI metrics from API
async function loadAuthorityDashboard({ checkLoginNotice = false, prevLoginIso = null, currentLoginIso = null } = {}) {
  const tableBody = document.getElementById('reportsTableBody');
  if (tableBody) {
    tableBody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:30px;color:var(--text-muted);"><span class="spinner" style="display:inline-block;vertical-align:middle;margin-right:8px;border-top-color:#1a73e8;border-color:rgba(0,0,0,0.1);"></span> Loading Mysuru Road Reports...</td></tr>`;
  }

  try {
    const data = await window.roadWatchApi.getReports();
    allReports = data.reports || [];
    updateKpiMetrics(data.stats || {});
    resetFiltersToAll();
    renderReportsTable();

    // Cache known report IDs for real-time live monitoring
    knownReportIds = new Set(allReports.map(r => r.report_id));

    if (checkLoginNotice) {
      processAndDisplayLoginNotice(allReports, prevLoginIso, currentLoginIso);
    } else {
      // Keep badge updated with count since last login
      const prevIso = localStorage.getItem('roadwatch_authority_prev_login') || localStorage.getItem('roadwatch_authority_last_login');
      if (prevIso) {
        const prevTime = new Date(prevIso).getTime();
        const sinceCount = allReports.filter(r => {
          const t = new Date(r.created_at || (r.date + ' ' + r.time)).getTime();
          return !isNaN(t) && t > prevTime;
        }).length;
        updateLoginNoticeBadge(sinceCount);
      }
    }
  } catch (err) {
    console.warn('Authority fetch error:', err);
    // Fallback seed reports if offline
    allReports = getLocalReportHistory();
    if (!allReports || allReports.length === 0) {
      allReports = getFallbackDemoReports();
    }
    updateKpiMetrics();
    resetFiltersToAll();
    renderReportsTable();
    knownReportIds = new Set(allReports.map(r => r.report_id));

    if (checkLoginNotice) {
      processAndDisplayLoginNotice(allReports, prevLoginIso, currentLoginIso);
    }
    showToast('Loaded local report database.', 'info');
  }
}

// Update KPI cards
function updateKpiMetrics(stats = {}) {
  const total = allReports.length;
  const newCnt = stats.new_reports ?? allReports.filter(r => r.status === 'New').length;
  const criticalCnt = stats.critical_high_reports ?? allReports.filter(r => r.severity === 'Critical' || r.severity === 'High').length;
  const inProgressCnt = stats.in_progress_reports ?? allReports.filter(r => r.status === 'In Progress').length;
  const resolvedCnt = stats.resolved_reports ?? allReports.filter(r => r.status === 'Resolved').length;

  setText('kpiTotalReports', total);
  setText('kpiNewReports', newCnt);
  setText('kpiCriticalReports', criticalCnt);
  setText('kpiInProgressReports', inProgressCnt);
  setText('kpiResolvedReports', resolvedCnt);
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.innerText = text;
}

// Render filtered reports in table
function renderReportsTable() {
  const tableBody = document.getElementById('reportsTableBody');
  const countDisplay = document.getElementById('tableCountDisplay');
  if (!tableBody) return;

  let filtered = allReports.filter(r => {
    // Status filter
    if (currentFilterStatus !== 'all' && (r.status || '').toLowerCase() !== currentFilterStatus.toLowerCase()) {
      return false;
    }
    // Severity filter
    if (currentFilterSeverity !== 'all' && (r.severity || '').toLowerCase() !== currentFilterSeverity.toLowerCase()) {
      return false;
    }
    // Submission Date Range filter
    if (currentFilterStartDate || currentFilterEndDate) {
      const repYmd = getReportDateYmd(r);
      if (currentFilterStartDate && repYmd && repYmd < currentFilterStartDate) {
        return false;
      }
      if (currentFilterEndDate && repYmd && repYmd > currentFilterEndDate) {
        return false;
      }
    }
    // Search query
    if (currentSearchQuery) {
      const q = currentSearchQuery.toLowerCase();
      const match = (r.report_id || '').toLowerCase().includes(q)
        || (r.location || '').toLowerCase().includes(q)
        || (r.road_condition || '').toLowerCase().includes(q)
        || (r.description || '').toLowerCase().includes(q);
      if (!match) return false;
    }
    return true;
  });

  if (countDisplay) {
    let countText = `Showing ${filtered.length} of ${allReports.length} reports`;
    if (currentFilterStartDate || currentFilterEndDate) {
      const startLabel = currentFilterStartDate ? formatYmdFriendly(currentFilterStartDate) : 'Earliest';
      const endLabel = currentFilterEndDate ? formatYmdFriendly(currentFilterEndDate) : 'Latest';
      countText += ` (Dates: ${startLabel} to ${endLabel})`;
    }
    countDisplay.innerText = countText;
  }

  if (filtered.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="8">
          <div class="empty-state">
            <div class="icon">🔍</div>
            <h3>No reports found</h3>
            <p>Try adjusting your search query or status filter.</p>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tableBody.innerHTML = filtered.map(report => {
    const mapsBtn = getGoogleMapsButton(report.google_maps_link, report.location);
    const sevBadge = getSeverityBadge(report.severity, false, report.road_condition);
    const arrivalClass = report._justArrived ? 'row-just-arrived' : '';

    return `
      <tr data-id="${report.report_id}" class="${arrivalClass}">
        <td class="report-id-cell" style="cursor:pointer;" onclick="openInspectModal('${report.report_id}')" title="Click to inspect report">${report.report_id}</td>
        <td><strong style="color:var(--text-main);font-weight:600;">${report.road_condition || 'Pothole'}</strong></td>
        <td>${sevBadge}</td>
        <td style="max-width: 200px;">
          <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${report.location}">${report.location}</div>
          <small style="color:var(--text-muted);">${report.road_type || 'City road'}</small>
        </td>
        <td>${mapsBtn}</td>
        <td>
          <div style="font-size:0.82rem;font-weight:600;white-space:nowrap;">${report.date || '—'}</div>
          <small style="color:var(--text-muted);white-space:nowrap;">${report.time || ''}</small>
        </td>
        <td>
          <select class="status-select status-${(report.status || 'new').toLowerCase().replace(' ', '-')}" 
                  onchange="handleTableStatusChange('${report.report_id}', this.value, this)">
            <option value="New" ${report.status === 'New' ? 'selected' : ''}>New</option>
            <option value="Verified" ${report.status === 'Verified' ? 'selected' : ''}>Verified</option>
            <option value="In Progress" ${report.status === 'In Progress' ? 'selected' : ''}>In Progress</option>
            <option value="Resolved" ${report.status === 'Resolved' ? 'selected' : ''}>Resolved</option>
          </select>
        </td>
        <td style="white-space:nowrap;">
          <button class="action-btn" onclick="openInspectModal('${report.report_id}')" title="Inspect report details">
            <span>🔍</span> Inspect
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

// In-line status change dropdown handler
async function handleTableStatusChange(reportId, newStatus, selectEl) {
  try {
    const res = await window.roadWatchApi.updateReportStatus(reportId, newStatus);
    const rep = allReports.find(r => r.report_id === reportId);
    if (rep) rep.status = newStatus;

    if (selectEl) {
      selectEl.className = `status-select status-${newStatus.toLowerCase().replace(' ', '-')}`;
    }

    updateKpiMetrics();
    showToast(`Report ${reportId} marked as ${newStatus}.`, 'success');
  } catch (err) {
    console.warn('Status update error:', err);
    // Local fallback update
    const rep = allReports.find(r => r.report_id === reportId);
    if (rep) rep.status = newStatus;
    updateKpiMetrics();
    showToast(`Status updated to ${newStatus} (Local).`, 'info');
  }
}

// Search and filter initializations
function initAuthorityFilters() {
  const searchInput = document.getElementById('authoritySearchInput');
  const severitySelect = document.getElementById('filterSeveritySelect');
  const refreshBtn = document.getElementById('refreshReportsBtn');

  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      currentSearchQuery = e.target.value.trim();
      renderReportsTable();
    });
  }

  if (severitySelect) {
    severitySelect.addEventListener('change', (e) => {
      currentFilterSeverity = e.target.value;
      renderReportsTable();
    });
  }

  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      loadAuthorityDashboard();
      showToast('Dashboard data refreshed.', 'info');
    });
  }

  // Filter status pills
  document.querySelectorAll('.filter-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      currentFilterStatus = pill.dataset.status;
      renderReportsTable();
    });
  });

  // Submission Date Range filter controls in toolbar
  const startDateInput = document.getElementById('filterStartDate');
  const endDateInput = document.getElementById('filterEndDate');
  const clearDateBtn = document.getElementById('clearDateFilterBtn');

  if (startDateInput) {
    startDateInput.addEventListener('change', (e) => {
      currentFilterStartDate = e.target.value;
      if (clearDateBtn) {
        clearDateBtn.style.display = (currentFilterStartDate || currentFilterEndDate) ? 'inline-block' : 'none';
      }
      renderReportsTable();
    });
  }

  if (endDateInput) {
    endDateInput.addEventListener('change', (e) => {
      currentFilterEndDate = e.target.value;
      if (clearDateBtn) {
        clearDateBtn.style.display = (currentFilterStartDate || currentFilterEndDate) ? 'inline-block' : 'none';
      }
      renderReportsTable();
    });
  }

  if (clearDateBtn) {
    clearDateBtn.addEventListener('click', () => {
      currentFilterStartDate = '';
      currentFilterEndDate = '';
      if (startDateInput) startDateInput.value = '';
      if (endDateInput) endDateInput.value = '';
      clearDateBtn.style.display = 'none';
      renderReportsTable();
      showToast('Date range filter reset to all reports.', 'info');
    });
  }
}

// Inspection Modal
function openInspectModal(reportId) {
  const report = allReports.find(r => r.report_id === reportId);
  if (!report) return;

  activeInspectReport = report;

  const modalImg = document.getElementById('inspectModalImage');
  const imgUrl = report.annotated_image || report.image || '/static/assets/images/sample_pothole_road.jpg';
  if (modalImg) modalImg.src = imgUrl;

  setText('inspectReportId', report.report_id);
  setText('inspectCondition', report.road_condition || 'Pothole');
  const isInvalidModal = (report.severity === 'Invalid') || (report.road_condition && report.road_condition.includes('Invalid'));
  setText('inspectConfidence', isInvalidModal ? '-' : (report.confidence_display || `${Math.round((report.confidence || 0.9) * 100)}%`));
  setText('inspectLocation', report.location || 'Mysuru');
  setText('inspectDescription', report.description || 'No citizen description provided.');
  setText('inspectDateTime', `${report.date || ''} at ${report.time || ''}`);
  setText('inspectReporter', report.reporter_name || 'Citizen');

  const sevEl = document.getElementById('inspectSeverityBadge');
  if (sevEl) sevEl.innerHTML = getSeverityBadge(report.severity, false, report.road_condition);

  const statusEl = document.getElementById('inspectStatusBadge');
  if (statusEl) statusEl.innerHTML = getStatusBadge(report.status);

  const mapsBtnContainer = document.getElementById('inspectMapsButtonContainer');
  if (mapsBtnContainer) {
    mapsBtnContainer.innerHTML = getGoogleMapsButton(report.google_maps_link, report.location);
  }

  const notesInput = document.getElementById('inspectNotesInput');
  if (notesInput) {
    notesInput.value = report.authority_notes || '';
  }

  openModal('inspectReportModal');
}

function initInspectModalActions() {
  const statusBtns = document.querySelectorAll('.inspect-status-btn');
  const saveNotesBtn = document.getElementById('saveInspectNotesBtn');

  statusBtns.forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!activeInspectReport) return;
      const targetStatus = btn.dataset.status;
      const notesVal = document.getElementById('inspectNotesInput')?.value.trim() || '';

      try {
        await window.roadWatchApi.updateReportStatus(activeInspectReport.report_id, targetStatus, notesVal);
        activeInspectReport.status = targetStatus;
        activeInspectReport.authority_notes = notesVal;

        const statusEl = document.getElementById('inspectStatusBadge');
        if (statusEl) statusEl.innerHTML = getStatusBadge(targetStatus);

        renderReportsTable();
        updateKpiMetrics();
        showToast(`Report ${activeInspectReport.report_id} status updated to ${targetStatus}!`, 'success');
      } catch (err) {
        activeInspectReport.status = targetStatus;
        activeInspectReport.authority_notes = notesVal;
        renderReportsTable();
        updateKpiMetrics();
        showToast(`Updated to ${targetStatus} (Local).`, 'info');
      }
    });
  });

  if (saveNotesBtn) {
    saveNotesBtn.addEventListener('click', async () => {
      if (!activeInspectReport) return;
      const notesVal = document.getElementById('inspectNotesInput')?.value.trim() || '';
      try {
        await window.roadWatchApi.updateReportStatus(activeInspectReport.report_id, activeInspectReport.status, notesVal);
        activeInspectReport.authority_notes = notesVal;
        showToast('Authority action notes saved.', 'success');
      } catch (err) {
        showToast('Saved notes locally.', 'info');
      }
    });
  }
}

// ==========================================================================
// Date Normalization & Helpers for Filters & CSV Export
// ==========================================================================

// Extract normalized YYYY-MM-DD from any report object
function getReportDateYmd(report) {
  if (!report) return '';
  // Check created_at (ISO timestamp)
  if (report.created_at && typeof report.created_at === 'string' && /^\d{4}-\d{2}-\d{2}/.test(report.created_at)) {
    return report.created_at.slice(0, 10);
  }

  const dateStr = (report.date || '').trim();
  if (!dateStr) return '';

  // Case: YYYY-MM-DD
  const isoMatch = dateStr.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})/);
  if (isoMatch) {
    const y = isoMatch[1];
    const m = String(isoMatch[2]).padStart(2, '0');
    const d = String(isoMatch[3]).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  // Case: DD-Mon-YYYY (e.g. 29-Oct-2026 or 29 Oct 2026)
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

  // Case: DD-MM-YYYY or DD/MM/YYYY
  const dmyNum = dateStr.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})/);
  if (dmyNum) {
    const d = String(dmyNum[1]).padStart(2, '0');
    const m = String(dmyNum[2]).padStart(2, '0');
    const y = dmyNum[3];
    return `${y}-${m}-${d}`;
  }

  // Fallback Date parser
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

// Convert YYYY-MM-DD to readable 29-Oct-2026
function formatYmdFriendly(ymd) {
  if (!ymd) return '';
  const parts = ymd.split('-');
  if (parts.length !== 3) return ymd;
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const mIdx = parseInt(parts[1], 10) - 1;
  const mStr = (mIdx >= 0 && mIdx < 12) ? monthNames[mIdx] : parts[1];
  return `${parts[2]}-${mStr}-${parts[0]}`;
}

// ==========================================================================
// CSV Export — Redirect to Dedicated Export & Date Filtering Page
// ==========================================================================

// Navigates to dedicated Export & Date Filter Page with any active toolbar date/status filters
function initExportCsvButton() {
  const exportBtn = document.getElementById('exportCsvBtn');
  if (!exportBtn) return;

  exportBtn.addEventListener('click', (e) => {
    e.preventDefault();
    let targetUrl = 'export.html';
    const params = new URLSearchParams();
    if (currentFilterStartDate) params.append('start_date', currentFilterStartDate);
    if (currentFilterEndDate) params.append('end_date', currentFilterEndDate);
    if (currentFilterStatus && currentFilterStatus !== 'all') params.append('status', currentFilterStatus);
    if (currentFilterSeverity && currentFilterSeverity !== 'all') params.append('severity', currentFilterSeverity);
    if (currentSearchQuery) params.append('search', currentSearchQuery);
    if (params.toString()) {
      targetUrl += `?${params.toString()}`;
    }
    window.location.href = targetUrl;
  });
}

// Check for returned export success notice after redirection
function checkExportSuccessNotice() {
  const msg = sessionStorage.getItem('roadwatch_export_success') || localStorage.getItem('roadwatch_export_success');
  if (msg) {
    sessionStorage.removeItem('roadwatch_export_success');
    localStorage.removeItem('roadwatch_export_success');
    setTimeout(() => {
      showToast(msg, 'success', 6000);
    }, 400);
  }
}

function getFallbackDemoReports() {
  return [
    {
      report_id: "RW-001",
      road_condition: "Pothole",
      severity: "High",
      confidence: 0.94,
      confidence_display: "94%",
      image: "/static/assets/images/sample_pothole_road.jpg",
      annotated_image: "/static/assets/images/sample_pothole_road.jpg",
      location: "Sayyaji Rao Road, Near Mysore Palace, Mysuru",
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
      image: "/static/assets/images/sample_pothole_road.jpg",
      annotated_image: "/static/assets/images/sample_pothole_road.jpg",
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
      image: "/static/assets/images/sample_crack_road.jpg",
      annotated_image: "/static/assets/images/sample_crack_road.jpg",
      location: "Devaraja Urs Road, Mysuru Commercial Zone",
      google_maps_link: "https://maps.google.com/?q=12.3082,76.6450",
      description: "Surface crack spanning multiple vehicle lengths.",
      date: "12-Oct-2026",
      time: "02:30 PM",
      status: "Verified"
    }
  ];
}

// ==========================================================================
// Authority Login Notification & Live Real-Time Report Monitoring
// ==========================================================================

/**
 * Initializes the topbar notification bell and view-in-table modal buttons
 */
function initLoginNoticeBell() {
  const bellBtn = document.getElementById('loginNoticeBellBtn');
  const viewNewBtn = document.getElementById('viewNewReportsBtn');

  if (bellBtn) {
    bellBtn.addEventListener('click', () => {
      const prevLogin = localStorage.getItem('roadwatch_authority_prev_login');
      const currLogin = localStorage.getItem('roadwatch_authority_last_login') || new Date().toISOString();

      if (lastLoginNoticeReports !== null) {
        updateLoginNoticeModalContent(lastLoginNoticeReports, prevLogin, currLogin);
      } else {
        const prevTime = prevLogin ? new Date(prevLogin).getTime() : 0;
        const newReports = allReports.filter(r => {
          const t = new Date(r.created_at || (r.date + ' ' + r.time)).getTime();
          return !isNaN(t) && t > prevTime;
        });
        updateLoginNoticeModalContent(newReports, prevLogin, currLogin);
      }
      openModal('loginNoticeModal');
    });
  }

  if (viewNewBtn) {
    viewNewBtn.addEventListener('click', () => {
      closeModal('loginNoticeModal');
      // Set filter status pill to 'New' and update table
      document.querySelectorAll('.filter-pill').forEach(p => {
        p.classList.toggle('active', (p.dataset.status || '').toLowerCase() === 'new');
      });
      currentFilterStatus = 'New';
      renderReportsTable();
      showToast('Filtering table to newly submitted reports.', 'info');
    });
  }
}

/**
 * Evaluates reports submitted between previous and current login, displays modal & toast
 */
function processAndDisplayLoginNotice(reports, prevLoginIso, currentLoginIso) {
  let newSinceLogin = [];

  if (prevLoginIso) {
    const prevTime = new Date(prevLoginIso).getTime();
    newSinceLogin = reports.filter(r => {
      const repTime = new Date(r.created_at || (r.date + ' ' + r.time)).getTime();
      return !isNaN(repTime) && repTime > prevTime;
    });
  } else {
    // First login recorded on this browser session — count pending New reports
    newSinceLogin = reports.filter(r => (r.status || '').toLowerCase() === 'new');
  }

  lastLoginNoticeReports = newSinceLogin;
  lastLoginNoticeMeta = {
    prevLoginIso: prevLoginIso,
    currentLoginIso: currentLoginIso
  };

  updateLoginNoticeModalContent(newSinceLogin, prevLoginIso, currentLoginIso);
  updateLoginNoticeBadge(newSinceLogin.length);

  // Automatically open the Login Notification Modal
  openModal('loginNoticeModal');

  // Also announce with a Toast Notification
  if (newSinceLogin.length > 0) {
    showToast(`🔔 ${newSinceLogin.length} new road damage report(s) submitted since your last login!`, 'info', 6000);
    playNotificationChime();
  } else {
    showToast(`✅ No new reports submitted since your last login. System is up to date.`, 'success', 4000);
  }
}

/**
 * Updates topbar bell badge with count of reports submitted since login
 */
function updateLoginNoticeBadge(count) {
  const badgeEl = document.getElementById('loginNoticeBadge');
  const bellBtn = document.getElementById('loginNoticeBellBtn');

  if (badgeEl) {
    badgeEl.innerText = `${count} New`;
    if (count > 0) {
      badgeEl.className = 'badge badge-critical';
    } else {
      badgeEl.className = 'badge badge-new';
    }
  }

  if (bellBtn) {
    if (count > 0) {
      bellBtn.classList.add('has-new-alert');
    } else {
      bellBtn.classList.remove('has-new-alert');
    }
  }
}

/**
 * Populates the Login Notice Modal preview card and table
 */
function updateLoginNoticeModalContent(reports, prevLoginIso, currentLoginIso) {
  const prevEl = document.getElementById('noticePrevLoginText');
  const currEl = document.getElementById('noticeCurrentLoginText');
  const headlineEl = document.getElementById('noticeCountHeadline');
  const bannerEl = document.getElementById('noticeCountBanner');
  const tableBody = document.getElementById('loginNoticeTableBody');
  const wrapperEl = document.getElementById('loginNoticeReportsWrapper');
  const emptyEl = document.getElementById('loginNoticeEmptyState');
  const emptyDesc = document.getElementById('loginNoticeEmptyDesc');

  if (prevEl) {
    prevEl.innerText = prevLoginIso ? formatDateTimeFriendly(prevLoginIso) : 'Initial Authority Session';
  }
  if (currEl) {
    currEl.innerText = currentLoginIso ? formatDateTimeFriendly(currentLoginIso) : formatDateTimeFriendly(new Date());
  }

  const count = reports ? reports.length : 0;

  if (count > 0) {
    if (bannerEl) bannerEl.className = 'notice-count-banner has-new';
    if (headlineEl) {
      headlineEl.innerHTML = `<strong>${count} New Road Damage Report${count > 1 ? 's' : ''}</strong> submitted between your last login and now`;
    }
    if (wrapperEl) wrapperEl.style.display = 'block';
    if (emptyEl) emptyEl.style.display = 'none';

    if (tableBody) {
      tableBody.innerHTML = reports.map(r => `
        <tr>
          <td><strong style="color:#2563eb;cursor:pointer;" onclick="closeModal('loginNoticeModal');openInspectModal('${r.report_id}')">${r.report_id}</strong></td>
          <td><strong>${r.road_condition || 'Pothole'}</strong></td>
          <td>${getSeverityBadge(r.severity, false, r.road_condition)}</td>
          <td style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${r.location || ''}">${r.location || 'Mysuru'}</td>
          <td style="white-space:nowrap;"><small>${r.date || ''} ${r.time || ''}</small></td>
          <td style="white-space:nowrap;">
            <button class="action-btn" onclick="closeModal('loginNoticeModal');openInspectModal('${r.report_id}')" title="Inspect report details">
              <span>🔍</span> Inspect
            </button>
          </td>
        </tr>
      `).join('');
    }
  } else {
    if (bannerEl) bannerEl.className = 'notice-count-banner no-new';
    if (headlineEl) {
      headlineEl.innerHTML = `<strong>0 New Reports</strong> submitted since your last login`;
    }
    if (wrapperEl) wrapperEl.style.display = 'none';
    if (emptyEl) emptyEl.style.display = 'block';
    if (emptyDesc) {
      emptyDesc.innerText = prevLoginIso
        ? `No new road defects were submitted between ${formatDateTimeFriendly(prevLoginIso)} and now.`
        : 'All current road condition reports are up to date.';
    }
  }
}

/**
 * Formats ISO timestamps or date strings into friendly readable text
 */
function formatDateTimeFriendly(isoOrDateStr) {
  if (!isoOrDateStr) return '—';
  try {
    const d = new Date(isoOrDateStr);
    if (isNaN(d.getTime())) return isoOrDateStr;
    const day = String(d.getDate()).padStart(2, '0');
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const month = months[d.getMonth()];
    const year = d.getFullYear();
    let hours = d.getHours();
    const minutes = String(d.getMinutes()).padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12 || 12;
    return `${day}-${month}-${year} at ${hours}:${minutes} ${ampm}`;
  } catch (e) {
    return isoOrDateStr;
  }
}

/**
 * Clean dual-tone synthesizer audio chime using Web Audio API (zero external assets)
 */
function playNotificationChime() {
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    const ctx = new AudioContextClass();
    const now = ctx.currentTime;

    // First tone (E5: 659.25 Hz)
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(659.25, now);
    gain1.gain.setValueAtTime(0.12, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.32);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.32);

    // Second tone (A5: 880.00 Hz)
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = 'sine';
    osc2.frequency.setValueAtTime(880.0, now + 0.12);
    gain2.gain.setValueAtTime(0.16, now + 0.12);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.52);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.12);
    osc2.stop(now + 0.52);
  } catch (e) {
    // Audio restricted before user gesture — fail gracefully
  }
}

/**
 * Starts real-time live monitoring for reports submitted during login time
 */
function startRealtimeReportMonitor() {
  if (liveMonitorInterval) clearInterval(liveMonitorInterval);

  // Initialize known IDs from currently loaded reports
  knownReportIds = new Set(allReports.map(r => r.report_id));

  // Poll server every 5 seconds for new reports
  liveMonitorInterval = setInterval(async () => {
    // Only continue polling if authority is actively logged in
    if (sessionStorage.getItem('mysuru_authority_logged_in') !== 'true') {
      stopRealtimeReportMonitor();
      return;
    }

    try {
      const data = await window.roadWatchApi.getReports();
      const latestReports = data.reports || [];

      // Detect any reports with IDs not currently known
      const newlyArrived = latestReports.filter(r => !knownReportIds.has(r.report_id));

      if (newlyArrived.length > 0) {
        for (const report of newlyArrived) {
          knownReportIds.add(report.report_id);
          liveReportsReceivedThisSession.push(report);

          // 1. Play audio chime
          playNotificationChime();

          // 2. Display floating live notification alert
          showLiveReportToast(report);

          // 3. Prepend to current reports list with animation flag
          report._justArrived = true;
          allReports.unshift(report);

          // If tracking since-login reports, also add to that list
          if (Array.isArray(lastLoginNoticeReports)) {
            lastLoginNoticeReports.unshift(report);
          }
        }

        // 4. Update KPI metrics cards
        updateKpiMetrics(data.stats || {});

        // 5. Re-render table with animation glow on new rows
        renderReportsTable();

        // 6. Increment topbar bell badge count
        const badgeEl = document.getElementById('loginNoticeBadge');
        if (badgeEl) {
          const currentCount = parseInt(badgeEl.innerText) || 0;
          updateLoginNoticeBadge(currentCount + newlyArrived.length);
        }

        // Clean up animation flag after 4 seconds
        setTimeout(() => {
          newlyArrived.forEach(r => { delete r._justArrived; });
        }, 4000);
      }
    } catch (err) {
      console.debug('[Real-time live report poll error]', err);
    }
  }, 5000);
}

/**
 * Stops the real-time live monitoring timer
 */
function stopRealtimeReportMonitor() {
  if (liveMonitorInterval) {
    clearInterval(liveMonitorInterval);
    liveMonitorInterval = null;
  }
}

/**
 * Displays an attention-grabbing live notification card at top right for reports submitted while logged in
 */
function showLiveReportToast(report) {
  const container = document.getElementById('liveReportAlertContainer');
  if (!container) return;

  const sevLower = (report.severity || 'moderate').toLowerCase();
  const toast = document.createElement('div');
  toast.className = `live-report-toast ${sevLower}`;

  toast.innerHTML = `
    <div class="live-toast-header">
      <span class="live-toast-badge live-pulse-dot">🚨 Live Report</span>
      <span class="live-toast-time">Just now</span>
      <button type="button" class="live-toast-close" title="Dismiss">&times;</button>
    </div>
    <div class="live-toast-body">
      <div class="live-toast-title">New Road Report: <strong>#${report.report_id}</strong> — ${report.road_condition || 'Pothole'}</div>
      <div style="margin-top: 4px; display: flex; align-items: center; gap: 6px;">
        ${getSeverityBadge(report.severity, false, report.road_condition)}
        <span style="font-size: 0.76rem; color: #64748b;">${report.road_type || 'City road'}</span>
      </div>
      <div class="live-toast-loc">📍 ${report.location || 'Mysuru Roadway'}</div>
    </div>
    <div class="live-toast-actions">
      <button type="button" class="btn btn-primary btn-sm" id="inspectLive_${report.report_id}" style="font-size: 0.78rem; padding: 4px 10px;">
        <span>🔍</span> Inspect Now
      </button>
    </div>
  `;

  // Close / dismiss button
  const closeBtn = toast.querySelector('.live-toast-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(60px)';
      setTimeout(() => toast.remove(), 300);
    });
  }

  // Inspect button
  const inspectBtn = toast.querySelector(`#inspectLive_${report.report_id}`);
  if (inspectBtn) {
    inspectBtn.addEventListener('click', () => {
      openInspectModal(report.report_id);
      toast.remove();
    });
  }

  container.appendChild(toast);

  // Auto dismiss after 9 seconds
  setTimeout(() => {
    if (toast.parentElement) {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(60px)';
      setTimeout(() => toast.remove(), 300);
    }
  }, 9000);
}

// Reset all filters to default 'all'
function resetFiltersToAll() {
  currentFilterStatus = 'all';
  currentFilterSeverity = 'all';
  currentFilterStartDate = '';
  currentFilterEndDate = '';
  currentSearchQuery = '';

  document.querySelectorAll('.filter-pill').forEach(p => {
    p.classList.toggle('active', (p.dataset.status || '').toLowerCase() === 'all');
  });

  const sevSelect = document.getElementById('filterSeveritySelect');
  if (sevSelect) sevSelect.value = 'all';

  const startInput = document.getElementById('filterStartDate');
  if (startInput) startInput.value = '';

  const endInput = document.getElementById('filterEndDate');
  if (endInput) endInput.value = '';

  const searchInput = document.getElementById('authoritySearchInput');
  if (searchInput) searchInput.value = '';

  const clearBtn = document.getElementById('clearDateFilterBtn');
  if (clearBtn) clearBtn.style.display = 'none';
}

