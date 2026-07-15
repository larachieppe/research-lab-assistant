(function () {
  if (typeof RUN_ID === "undefined") return;

  const badge = document.getElementById("status-badge");
  const result = document.getElementById("result");

  async function poll() {
    const res = await fetch(`/api/runs/${RUN_ID}`);
    if (!res.ok) return;
    const data = await res.json();

    if (data.status === badge.textContent.trim()) {
      if (data.status === "pending" || data.status === "running") {
        setTimeout(poll, 2000);
      }
      return;
    }

    badge.textContent = data.status;
    badge.className = `status status-${data.status}`;
    result.innerHTML = data.html;
    if (window.initEvidenceMap) window.initEvidenceMap();

    if (data.status === "pending" || data.status === "running") {
      setTimeout(poll, 2000);
    }
  }

  setTimeout(poll, 2000);
})();
