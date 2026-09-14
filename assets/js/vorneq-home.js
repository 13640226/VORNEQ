(() => {
  const input = document.getElementById('heroMediaInput');
  const choose = document.getElementById('heroUploadButton');
  const reset = document.getElementById('resetHeroMedia');
  const image = document.getElementById('heroImage');
  const video = document.getElementById('heroVideo');
  const placeholder = document.getElementById('mediaPlaceholder');
  const status = document.getElementById('mediaStatus');

  if (!input || !choose || !reset || !image || !video || !placeholder || !status) return;

  const MAX_FILE_SIZE = 25 * 1024 * 1024;
  let objectUrl = null;

  const clearObjectUrl = () => {
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
      objectUrl = null;
    }
  };

  const clearMedia = () => {
    clearObjectUrl();
    video.pause();
    video.removeAttribute('src');
    video.hidden = true;
    image.removeAttribute('src');
    image.hidden = true;
    placeholder.hidden = false;
    input.value = '';
  };

  const resetMedia = () => {
    clearMedia();
    status.textContent = 'Default';
  };

  const showError = (message) => {
    clearMedia();
    status.textContent = message;
  };

  image.addEventListener('error', () => {
    showError('Image preview failed');
  });

  video.addEventListener('error', () => {
    showError('Video preview failed');
  });

  choose.addEventListener('click', () => input.click());
  reset.addEventListener('click', resetMedia);

  input.addEventListener('change', () => {
    const file = input.files && input.files[0];
    if (!file) return;

    const isImage = file.type.startsWith('image/');
    const isVideo = file.type.startsWith('video/');
    if (!isImage && !isVideo) {
      showError('Unsupported media type');
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      showError('File exceeds 25 MB');
      return;
    }

    clearObjectUrl();
    objectUrl = URL.createObjectURL(file);
    placeholder.hidden = true;

    if (isVideo) {
      image.hidden = true;
      video.hidden = false;
      video.src = objectUrl;
      status.textContent = 'Video preview';
      video.play().catch(() => {
        showError('Video playback failed');
      });
      return;
    }

    video.pause();
    video.removeAttribute('src');
    video.load();
    video.hidden = true;
    image.hidden = false;
    image.src = objectUrl;
    status.textContent = 'Image preview';
  });

  window.addEventListener('beforeunload', clearObjectUrl);
})();
