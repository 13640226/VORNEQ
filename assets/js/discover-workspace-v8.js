document.addEventListener("DOMContentLoaded", () => {
  const grid = document.getElementById("discover-grid");
  const controls = document.querySelector(".discover-view-controls");
  if (!grid || !controls) return;
  const buttons = controls.querySelectorAll("[data-discover-view]");
  controls.hidden = false;
  buttons.forEach(button => button.addEventListener("click", () => {
    grid.classList.toggle("is-list", button.dataset.discoverView === "list");
    buttons.forEach(item => item.setAttribute("aria-pressed", String(item === button)));
  }));
});
