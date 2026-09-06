document.addEventListener('DOMContentLoaded', () => {
  const editor = document.querySelector('[data-profile-avatar-editor]');
  if (!editor) return;

  const form = document.querySelector('[data-profile-edit-form]');
  const save = document.querySelector('[data-profile-save]');
  const input = editor.querySelector('input[type="file"]');
  const remove = editor.querySelector('input[name="remove_avatar"]');
  const refresh = editor.querySelector('[data-avatar-refresh]');
  const reset = editor.querySelector('[data-avatar-reset]');
  const preview = editor.querySelector('[data-avatar-preview]');
  const filename = editor.querySelector('[data-avatar-filename]');
  const loading = editor.querySelector('[data-avatar-loading]');
  const status = editor.querySelector('[data-avatar-status]');
  const initials = editor.dataset.initials || '';
  const serverAvatarUrl = editor.dataset.avatarServerUrl || '';
  let objectUrl = null;

  const setBusy = (busy) => {
    editor.setAttribute('aria-busy', busy ? 'true' : 'false');
    if (loading) loading.hidden = !busy;
  };

  const setStatus = (message, kind = '') => {
    if (!status) return;
    status.textContent = message || '';
    status.dataset.statusKind = kind;
  };

  const setResetVisible = (visible) => {
    if (reset) reset.hidden = !visible;
  };

  const clearObjectUrl = () => {
    if (!objectUrl) return;
    URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  };

  const renderFallback = () => {
    if (!preview) return;
    preview.querySelectorAll(':scope > :not([data-avatar-loading])').forEach((node) => node.remove());
    const fallback = document.createElement('span');
    fallback.dataset.avatarFallback = '';
    fallback.textContent = initials;
    preview.prepend(fallback);
  };

  const renderImage = (src, { busy = false, onLoaded = null, onError = null } = {}) => {
    if (!preview) return;
    preview.querySelectorAll(':scope > :not([data-avatar-loading])').forEach((node) => node.remove());

    const image = document.createElement('img');
    image.className = 'profile-avatar__image';
    image.width = 112;
    image.height = 112;
    image.alt = '';
    image.dataset.avatarImage = '';

    if (busy) setBusy(true);
    image.addEventListener('load', () => {
      setBusy(false);
      if (onLoaded) onLoaded();
    }, { once: true });
    image.addEventListener('error', () => {
      setBusy(false);
      if (onError) onError();
    }, { once: true });

    image.src = src;
    preview.prepend(image);
  };

  const renderStoredAvatar = ({ announce = false } = {}) => {
    if (!serverAvatarUrl) {
      renderFallback();
      return;
    }

    const separator = serverAvatarUrl.includes('?') ? '&' : '?';
    const src = `${serverAvatarUrl}${separator}v=${Date.now()}`;
    if (announce) setStatus(editor.dataset.refreshingLabel || 'Refreshing current photo', 'info');
    renderImage(src, {
      busy: true,
      onLoaded: () => {
        if (announce) setStatus(editor.dataset.refreshedLabel || 'Current photo refreshed', 'success');
      },
      onError: () => {
        setStatus(editor.dataset.loadErrorLabel || 'Could not load the profile photo. Please try again.', 'error');
      },
    });
  };

  const resetPendingAvatarChanges = ({ announce = true } = {}) => {
    if (input) input.value = '';
    if (remove) remove.checked = false;
    clearObjectUrl();
    if (serverAvatarUrl) renderStoredAvatar();
    else renderFallback();
    if (filename) filename.textContent = filename.dataset.emptyLabel || 'No new photo selected';
    setResetVisible(false);
    if (announce) setStatus(editor.dataset.resetLabel || 'Photo changes reset', 'info');
  };

  if (input) {
    input.addEventListener('change', () => {
      const file = input.files && input.files[0];
      if (!file) {
        if (filename) filename.textContent = filename.dataset.emptyLabel || 'No new photo selected';
        return;
      }

      clearObjectUrl();
      objectUrl = URL.createObjectURL(file);
      renderImage(objectUrl, {
        busy: true,
        onLoaded: () => setStatus(editor.dataset.previewingLabel || 'Previewing selected photo', 'info'),
        onError: () => setStatus(editor.dataset.loadErrorLabel || 'Could not load the profile photo. Please try again.', 'error'),
      });

      if (filename) filename.textContent = file.name;
      if (remove) remove.checked = false;
      setResetVisible(true);
    });
  }

  if (refresh) {
    refresh.addEventListener('click', () => {
      resetPendingAvatarChanges({ announce: false });
      renderStoredAvatar({ announce: true });
      if (filename) filename.textContent = filename.dataset.refreshedLabel || 'Current photo refreshed';
    });
  }

  if (remove) {
    remove.addEventListener('change', () => {
      if (!remove.checked) {
        if (serverAvatarUrl) renderStoredAvatar();
        else renderFallback();
        setStatus('', '');
        setResetVisible(false);
        return;
      }

      if (input) input.value = '';
      clearObjectUrl();
      renderFallback();
      if (filename) filename.textContent = filename.dataset.emptyLabel || 'No new photo selected';
      setStatus(editor.dataset.removedLabel || 'Photo will be removed after saving', 'warning');
      setResetVisible(true);
    });
  }

  if (reset) {
    reset.addEventListener('click', () => resetPendingAvatarChanges());
  }

  if (form) {
    form.addEventListener('submit', () => {
      setBusy(true);
      setStatus(editor.dataset.savingLabel || 'Saving profile changes', 'info');
      if (save) save.disabled = true;
    });
  }

  window.addEventListener('beforeunload', clearObjectUrl);
});
