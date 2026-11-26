(() => {
 const controls = document.querySelector('[data-note-controls]');
 const results = document.getElementById('note-results');
 if (!controls || !results) return;
 controls.hidden = false;
 controls.addEventListener('click', event => {
  const button = event.target.closest('[data-note-layout]');
  if (!button) return;
  results.classList.toggle('is-list', button.dataset.noteLayout === 'list');
  controls.querySelectorAll('[data-note-layout]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
 });
 controls.querySelector('input').addEventListener('input', event => {
  const query = event.target.value.trim().toLocaleLowerCase();
  let matches = 0;
  results.querySelectorAll('.note-card').forEach(card => { card.hidden = !card.textContent.toLocaleLowerCase().includes(query); if (!card.hidden) matches++; });
  document.querySelector('[data-note-empty]').hidden = matches !== 0;
 });
})();
