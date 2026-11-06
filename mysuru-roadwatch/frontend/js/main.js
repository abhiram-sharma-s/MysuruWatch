/**
 * Mysuru RoadWatch — Global Main Utilities
 * Toast notifications, modal handlers, badges, local persistence
 */


// Toast notification helper
function showToast(message, type = 'info', duration = 4000) {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  const iconMap = {
    success: '✅',
    error: '⚠️',
    info: 'ℹ️'
  };

  toast.innerHTML = `<span>${iconMap[type] || 'ℹ️'}</span><div>${message}</div>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// Modal open/close
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove('active');
    document.body.style.overflow = '';
  }
}

// Severity badge generator with optional range indicator
function getSeverityBadge(severity, showRange = false, condition = '') {
  const sev = (severity || 'Moderate').toLowerCase();
  const cond = (condition || '').toLowerCase();
  if (sev.includes('sky') || cond.includes('sky')) {
    return `<span class="badge" style="background:#e0f2fe;color:#0369a1;border:1px solid #7dd3fc;font-weight:700;">Sky Image (Invalid)</span>`;
  }
  if (sev === 'invalid' || sev.includes('invalid') || sev.includes('non-road') || cond.includes('invalid')) {
    return `<span class="badge" style="background:#fee2e2;color:#dc2626;border:1px solid #fca5a5;">Non-Road Image</span>`;
  }
  let badgeClass = 'badge-moderate';
  let label = severity || 'Moderate';

  if (sev === 'critical') {
    badgeClass = 'badge-critical';
    if (showRange) label = 'Critical (90% – 100%)';
  } else if (sev === 'high') {
    badgeClass = 'badge-high';
    if (showRange) label = 'High (80% – 89%)';
  } else if (sev === 'moderate') {
    badgeClass = 'badge-moderate';
    if (showRange) label = 'Moderate (65% – 79%)';
  } else if (sev === 'low') {
    badgeClass = 'badge-low';
    if (showRange) label = 'Low (Below 65%)';
  }

  return `<span class="badge ${badgeClass}">${label}</span>`;
}

// Status badge generator
function getStatusBadge(status) {
  const st = (status || 'New').toLowerCase().replace(' ', '-');
  let badgeClass = 'badge-new';
  if (st === 'verified') badgeClass = 'badge-verified';
  else if (st === 'in-progress') badgeClass = 'badge-in-progress';
  else if (st === 'resolved') badgeClass = 'badge-resolved';

  return `<span class="badge ${badgeClass}">${status || 'New'}</span>`;
}

// Google Maps button generator
function getGoogleMapsButton(mapsLink, locationName = '') {
  let url = mapsLink;
  if (!url || url.trim() === '') {
    // Generate fallback Google Maps search for location in Mysuru
    const query = encodeURIComponent(`${locationName || 'Mysuru'}, Mysuru, Karnataka`);
    url = `https://maps.google.com/?q=${query}`;
  }
  return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="maps-link-btn" title="Open location in Google Maps">
    <span>🗺️</span> View Map
  </a>`;
}

// Local storage helper for recently reported cases
const STORAGE_KEY_RECENT_REPORTS = 'mysuru_roadwatch_my_reports';

function saveReportToLocalHistory(report) {
  try {
    let list = JSON.parse(localStorage.getItem(STORAGE_KEY_RECENT_REPORTS) || '[]');
    // Filter duplicates
    list = list.filter(r => r.report_id !== report.report_id);
    list.unshift(report);
    if (list.length > 20) list.pop();
    localStorage.setItem(STORAGE_KEY_RECENT_REPORTS, JSON.stringify(list));
  } catch (e) {
    console.warn('Could not save to localStorage', e);
  }
}

function getLocalReportHistory() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY_RECENT_REPORTS) || '[]');
  } catch (e) {
    return [];
  }
}

// Sidebar Collapsible Menu Toggle (3-lines symbol hamburger menu)
function initSidebarMenu() {
  const sidebar = document.querySelector('.sidebar');
  if (!sidebar) return;

  // Create backdrop element if missing (for mobile drawer)
  let backdrop = document.querySelector('.sidebar-backdrop');
  if (!backdrop) {
    backdrop = document.createElement('div');
    backdrop.className = 'sidebar-backdrop';
    document.body.appendChild(backdrop);
  }

  // Restore saved preference for desktop (collapsed vs expanded)
  if (window.innerWidth > 980) {
    const isCollapsed = localStorage.getItem('mysuru_sidebar_collapsed') === 'true';
    if (isCollapsed) {
      sidebar.classList.add('collapsed');
    }
  }

  // Toggle handlers for all 3-lines menu buttons
  const menuButtons = document.querySelectorAll('#topbarMenuBtn, #sidebarCollapseBtn, .menu-toggle-btn');
  menuButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (window.innerWidth <= 980) {
        // Mobile drawer toggle
        const isOpen = sidebar.classList.toggle('mobile-open');
        backdrop.classList.toggle('active', isOpen);
      } else {
        // Desktop collapse / expand
        const isCollapsed = sidebar.classList.toggle('collapsed');
        localStorage.setItem('mysuru_sidebar_collapsed', isCollapsed ? 'true' : 'false');
      }
    });
  });

  // Clicking outside on backdrop closes mobile drawer
  backdrop.addEventListener('click', () => {
    sidebar.classList.remove('mobile-open');
    backdrop.classList.remove('active');
  });

  // Clicking a nav link on mobile closes the drawer
  sidebar.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
      if (window.innerWidth <= 980) {
        sidebar.classList.remove('mobile-open');
        backdrop.classList.remove('active');
      }
    });
  });
}

// Global initialization
document.addEventListener('DOMContentLoaded', () => {
  initSidebarMenu();

  // Close modals on overlay backdrop click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        closeModal(overlay.id);
      }
    });
  });

  // Check backend health indicator if present
  const healthPill = document.getElementById('backendStatusPill');
  if (healthPill && window.roadWatchApi) {
    window.roadWatchApi.checkHealth()
      .then(res => {
        healthPill.innerHTML = `🟢 API Online (${res.city})`;
        healthPill.title = `Backend: ${res.database.mode}`;
      })
      .catch(() => {
        healthPill.innerHTML = `🟠 Demo Mode`;
        healthPill.title = `FastAPI server not responding. Connect to port 8000.`;
      });
  }
});

