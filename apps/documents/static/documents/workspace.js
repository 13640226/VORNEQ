(() => {
 const controls = document.querySelector('[data-doc-controls]');
 const results = document.getElementById('doc-results');
 if (!controls || !results) return;
 controls.hidden = false;
 controls.addEventListener('click', event => {
  const button = event.target.closest('[data-doc-layout]');
  if (!button) return;
  results.classList.toggle('is-list', button.dataset.docLayout === 'list');
  controls.querySelectorAll('[data-doc-layout]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
 });
 controls.querySelector('input').addEventListener('input', event => {
  const query = event.target.value.trim().toLocaleLowerCase();
  results.querySelectorAll('.document-card').forEach(card => { card.hidden = !card.textContent.toLocaleLowerCase().includes(query); });
 });
})();
