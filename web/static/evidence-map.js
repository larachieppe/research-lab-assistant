function initEvidenceMap() {
  const root = document.getElementById("result");
  if (!root) return;

  let current = null;

  function clear() {
    root.querySelectorAll(".highlighted").forEach(function (el) {
      el.classList.remove("highlighted");
    });
    current = null;
  }

  function highlight(n) {
    if (current === n) {
      clear();
      return;
    }
    clear();
    current = n;

    root.querySelectorAll('[data-cite="' + n + '"]').forEach(function (el) {
      el.classList.add("highlighted");
    });

    const node = root.querySelector('.evidence-node[data-node="' + n + '"]');
    if (node) node.classList.add("highlighted");

    const refs = root.querySelectorAll(".references ol > li");
    if (refs[n - 1]) {
      refs[n - 1].classList.add("highlighted");
      refs[n - 1].scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }

  root.querySelectorAll(".cite-marker").forEach(function (el) {
    el.addEventListener("click", function () {
      highlight(parseInt(el.dataset.cite, 10));
    });
  });

  root.querySelectorAll(".evidence-node").forEach(function (el) {
    el.addEventListener("click", function () {
      highlight(parseInt(el.dataset.node, 10));
    });
  });
}

window.initEvidenceMap = initEvidenceMap;
document.addEventListener("DOMContentLoaded", initEvidenceMap);
