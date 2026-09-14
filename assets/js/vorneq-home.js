(() => {
  const input = document.getElementById('heroMediaInput');
  const choose = document.getElementById('heroUploadButton');
  const reset = document.getElementById('resetHeroMedia');
  const image = document.getElementById('heroImage');
  const video = document.getElementById('heroVideo');
  const placeholder = document.getElementById('mediaPlaceholder');
  const status = document.getElementById('mediaStatus');

  if (!input || !choose || !reset || !image || !video || !placeholder || !status) return;

  let objectUrl = null;

  const clearObjectUrl = () => {
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
      objectUrl = null;
    }
  };

  const resetMedia = () => {
    clearObjectUrl();
    video.pause();
    video.removeAttribute('src');
    video.hidden = true;
    image.removeAttribute('src');
    image.hidden = true;
    placeholder.hidden = false;
    status.textContent = 'Default';
    input.value = '';
  };

  choose.addEventListener('click', () => input.click());
  reset.addEventListener('click', resetMedia);

  input.addEventListener('change', () => {
    const file = input.files && input.files[0];
    if (!file) return;

    const isImage = file.type.startsWith('image/');
    const isVideo = file.type.startsWith('video/');
    if (!isImage && !isVideo) {
      resetMedia();
      return;
    }

    clearObjectUrl();
    objectUrl = URL.createObjectURL(file);
    placeholder.hidden = true;

    if (isVideo) {
      image.hidden = true;
      video.hidden = false;
      video.src = objectUrl;
      video.play().catch(() => {});
      status.textContent = 'Video preview';
      return;
    }

    video.pause();
    video.hidden = true;
    image.hidden = false;
    image.src = objectUrl;
    status.textContent = 'Image preview';
  });

  window.addEventListener('beforeunload', clearObjectUrl);
})();
