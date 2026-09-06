document.addEventListener('DOMContentLoaded', () => {
  const backButton = document.querySelector('[data-global-back]');
  if (!backButton) return;

  const homeUrl = backButton.dataset.homeUrl || '/';

  backButton.addEventListener('click', () => {
    let hasInternalReferrer = false;

    if (document.referrer) {
      try {
        const referrerUrl = new URL(document.referrer);
        hasInternalReferrer = referrerUrl.origin === window.location.origin;
      } catch (error) {
        hasInternalReferrer = false;
      }
    }

    if (hasInternalReferrer && window.history.length > 1) {
      window.history.back();
      return;
    }

    window.location.assign(homeUrl);
  });
});
