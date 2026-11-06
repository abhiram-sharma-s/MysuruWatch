document.addEventListener('DOMContentLoaded', () => {
  const submitBtn = document.getElementById('submitReportBtn');

  if (submitBtn) {
    submitBtn.addEventListener('click', (event) => {
      event.preventDefault();
      const form = document.getElementById('roadReportForm');

      if (!form) return;

      const reporterName = document.getElementById('reporterName')?.value.trim();
      const location = document.getElementById('reporterLocation')?.value.trim();

      if (!reporterName || !location) {
        alert('Please fill in the reporter name and road location before submitting.');
        return;
      }

      alert('Road condition report submitted successfully. Authorities have been notified.');
      form.reset();
    });
  }
});
