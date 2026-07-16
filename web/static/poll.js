(function () {
  if (typeof RUN_ID === "undefined") return;

  const badge = document.getElementById("status-badge");
  const result = document.getElementById("result");

  async function poll() {
    const res = await fetch(`/api/runs/${RUN_ID}`);
    if (!res.ok) return;
    const data = await res.json();
    const isActive = data.status === "pending" || data.status === "running";
    const statusChanged = data.status !== badge.textContent.trim();

    // Re-render on every tick while active, not just on a status change -
    // the stage label updates (e.g. "Screening N papers") without the
    // pending/running status itself ever changing.
    if (statusChanged || isActive) {
      badge.textContent = data.status;
      badge.className = `status status-${data.status}`;
      result.innerHTML = data.html;
      if (window.initEvidenceMap) window.initEvidenceMap();
    }

    if (isActive) {
      setTimeout(poll, 2000);
    }
  }

  setTimeout(poll, 2000);
})();
