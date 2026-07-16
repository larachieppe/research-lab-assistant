(function () {
  if (typeof RUN_ID === "undefined") return;

  const badge = document.getElementById("status-badge");
  const result = document.getElementById("result");

  async function poll() {
    const res = await fetch(`/api/runs/${RUN_ID}`);
    if (!res.ok) return;
    const data = await res.json();
    const wasActive = badge.textContent.trim() === "pending" || badge.textContent.trim() === "running";
    const isActive = data.status === "pending" || data.status === "running";

    if (wasActive && !isActive) {
      // The run just finished - reload instead of patching #result in place.
      // The follow-up form, "Feature on homepage" button, and children list
      // all live outside #result and are only rendered server-side at
      // initial page load (when the run was still pending, so their
      // conditions were false) - a full reload is the only way they end up
      // showing the real final state instead of never appearing at all.
      window.location.reload();
      return;
    }

    if (isActive) {
      badge.textContent = data.status;
      badge.className = `status status-${data.status}`;
      result.innerHTML = data.html;
      if (window.initEvidenceMap) window.initEvidenceMap();
      setTimeout(poll, 2000);
    }
  }

  setTimeout(poll, 2000);
})();
