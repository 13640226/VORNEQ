document.addEventListener("DOMContentLoaded", function () {
  const input = document.querySelector("[data-app-search]");
  const cards = Array.from(document.querySelectorAll("[data-app-card]"));
  const status = document.querySelector("[data-app-search-status]");
  const empty = document.querySelector("[data-app-empty-filter]");

  if (!input || !cards.length) return;

  function applyFilter() {
    const query = input.value.toLowerCase().trim();
    let visibleCount = 0;

    cards.forEach(function (card) {
      const label = card.dataset.label || "";
      const slug = card.dataset.slug || "";
      const matches = !query || label.includes(query) || slug.includes(query);
      card.hidden = !matches;
      if (matches) visibleCount += 1;
    });

    if (status) {
      status.textContent = query ? visibleCount + " app" + (visibleCount === 1 ? "" : "s") + " found" : "";
    }
    if (empty) empty.hidden = !query || visibleCount !== 0;
  }

  input.addEventListener("input", applyFilter);
});
