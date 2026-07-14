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

    if (data.status === "completed") {
      result.innerHTML = `<article class="summary">${data.summary_html}</article>`;
    } else if (data.status === "failed") {
      result.innerHTML = `<p class="error">Pipeline failed: ${data.error}</p>`;
      return;
    } else {
      setTimeout(poll, 2000);
    }
  }

  setTimeout(poll, 2000);
})();
