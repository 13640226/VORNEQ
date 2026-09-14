(() => {
  const input = document.getElementById('heroMediaInput');
  const choose = document.getElementById('heroUploadButton');
  const reset = document.getElementById('resetHeroMedia');
  const image = document.getElementById('heroImage');
  const video = document.getElementById('heroVideo');
  const placeholder = document.getElementById('mediaPlaceholder');
  const status = document.getElementById('mediaStatus');

  const MAX_FILE_SIZE = 25 * 1024 * 1024;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let objectUrl = null;

  const setStatus = (message) => {
    if (status) status.textContent = message;
  };

  const clearObjectUrl = () => {
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
      objectUrl = null;
    }
  };

  const clearMedia = () => {
    clearObjectUrl();
    if (video) {
      video.pause();
      video.removeAttribute('src');
      video.load();
      video.hidden = true;
    }
    if (image) {
      image.removeAttribute('src');
      image.hidden = true;
    }
    if (placeholder) placeholder.hidden = false;
    if (input) input.value = '';
  };

  const resetMedia = () => {
    clearMedia();
    setStatus('Optional');
  };

  const showError = (message) => {
    clearMedia();
    setStatus(message);
  };

  const applyMotionPreference = () => {
    if (!video) return;
    video.loop = !reducedMotion.matches;
    if (reducedMotion.matches) video.pause();
  };

  if (video) {
    applyMotionPreference();
    reducedMotion.addEventListener('change', applyMotionPreference);
    video.addEventListener('error', () => {
      showError('Video preview failed');
    });
  }

  if (image) {
    image.addEventListener('error', () => {
      showError('Image preview failed');
    });
  }

  if (choose && input) choose.addEventListener('click', () => input.click());
  if (reset) reset.addEventListener('click', resetMedia);

  if (input) input.addEventListener('change', () => {
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

    if (isImage && !image) {
      showError('Image preview unavailable');
      return;
    }

    if (isVideo && !video) {
      showError('Video preview unavailable');
      return;
    }

    clearObjectUrl();
    objectUrl = URL.createObjectURL(file);
    if (placeholder) placeholder.hidden = true;

    if (isVideo) {
      if (image) {
        image.hidden = true;
        image.removeAttribute('src');
      }
      video.hidden = false;
      video.src = objectUrl;
      setStatus('Video preview');
      applyMotionPreference();
      if (reducedMotion.matches) return;
      video.play().catch(() => {
        showError('Video playback failed');
      });
      return;
    }

    if (video) {
      video.pause();
      video.removeAttribute('src');
      video.load();
      video.hidden = true;
    }
    image.hidden = false;
    image.src = objectUrl;
    setStatus('Image preview');
  });

  window.addEventListener('beforeunload', clearObjectUrl);
})();
