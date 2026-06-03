(function () {
  var btn = document.getElementById("theme-toggle");
  if (!btn) return;
  btn.addEventListener("click", function () {
    var root = document.documentElement;
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("perry-theme", next);
  });
})();

/* ---- modal pop-outs ----
   Open:  any element with data-modal-open="ID"
   Close: data-modal-close, the dark backdrop, or Escape. */
(function () {
  function close(m) { if (m) { m.setAttribute("hidden", ""); document.body.classList.remove("modal-open"); } }
  function open(id) {
    var m = document.getElementById(id);
    if (!m) return;
    m.removeAttribute("hidden");
    document.body.classList.add("modal-open");
    var first = m.querySelector("input, select, textarea");
    if (first) setTimeout(function () { first.focus(); }, 30);
  }
  document.addEventListener("click", function (e) {
    var opener = e.target.closest("[data-modal-open]");
    if (opener) { e.preventDefault(); open(opener.getAttribute("data-modal-open")); return; }
    if (e.target.closest("[data-modal-close]")) { close(e.target.closest(".modal")); return; }
    if (e.target.classList.contains("modal")) { close(e.target); }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      var open = document.querySelector(".modal:not([hidden])");
      if (open) close(open);
    }
  });
})();

/* ---- earner accordion toggle ----
   Buttons with class "earner-toggle" and data-target="earner-body-{id}"
   collapse/expand the earner card body. */
(function () {
  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".earner-toggle");
    if (!btn) return;
    var targetId = btn.getAttribute("data-target");
    var body = document.getElementById(targetId);
    if (!body) return;
    var collapsed = body.style.display === "none";
    body.style.display = collapsed ? "" : "none";
    btn.textContent = collapsed ? "▾" : "▸";
  });
})();

/* ---- earner prefill for income-add modal ----
   Buttons with data-prefill-earner="{id}" trigger the income modal
   and pre-select that earner in the dropdown after a short delay. */
(function () {
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-prefill-earner]");
    if (!btn) return;
    var earnerId = btn.getAttribute("data-prefill-earner");
    setTimeout(function () {
      var sel = document.querySelector("#m-income-add select[name='earner_id']");
      if (sel) sel.value = earnerId;
    }, 50);
  });
})();
