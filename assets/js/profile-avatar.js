document.addEventListener('DOMContentLoaded', () => {
  const editor = document.querySelector('[data-profile-avatar-editor]');
  if (!editor) return;

  const input = editor.querySelector('input[type="file"]');
  const remove = editor.querySelector('input[name="remove_avatar"]');
  const refresh = editor.querySelector('[data-avatar-refresh]');
  const preview = editor.querySelector('[data-avatar-preview]');
  const filename = editor.querySelector('[data-avatar-filename]');
  const initials = editor.dataset.initials || '';
  const serverAvatarUrl = editor.dataset.avatarServerUrl || '';
  let objectUrl = null;

  const renderFallback = () => {
    if (!preview) return;
    preview.innerHTML = '';
    const fallback = document.createElement('span');
    fallback.dataset.avatarFallback = '';
    fallback.textContent = initials;
    preview.appendChild(fallback);
  };

  const renderStoredAvatar = () => {
    if (!preview || !serverAvatarUrl) return;
    preview.innerHTML = '';
    const image = document.createElement('img');
    image.className = 'profile-avatar__image';
    image.width = 112;
    image.height = 112;
    image.alt = '';
    image.dataset.avatarImage = '';
    const separator = serverAvatarUrl.includes('?') ? '&' : '?';
    image.src = `${serverAvatarUrl}${separator}v=${Date.now()}`;
    preview.appendChild(image);
  };

  if (input) {
    input.addEventListener('change', () => {
      const file = input.files && input.files[0];
      if (!file) {
        if (filename) filename.textContent = filename.dataset.emptyLabel || 'No new photo selected';
        return;
      }

      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = URL.createObjectURL(file);

      if (preview) {
        preview.innerHTML = '';
        const image = document.createElement('img');
        image.className = 'profile-avatar__image';
        image.width = 112;
        image.height = 112;
        image.alt = '';
        image.src = objectUrl;
        preview.appendChild(image);
      }

      if (filename) filename.textContent = file.name;
      if (remove) remove.checked = false;
    });
  }

  if (refresh) {
    refresh.addEventListener('click', () => {
      if (!serverAvatarUrl) return;
      if (input) input.value = '';
      if (remove) remove.checked = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
        objectUrl = null;
      }
      renderStoredAvatar();
      if (filename) {
        filename.textContent = filename.dataset.refreshedLabel || 'Current photo refreshed';
      }
    });
  }

  if (remove) {
    remove.addEventListener('change', () => {
      if (!remove.checked) return;
      if (input) input.value = '';
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
        objectUrl = null;
      }
      renderFallback();
    });
  }

  window.addEventListener('beforeunload', () => {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  });
});
