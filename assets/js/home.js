"use strict";

(() => {


  /* ==========================================================
     INTERNAL NAVIGATION
     ========================================================== */

  document
    .querySelectorAll(
      'a[href^="#"]'
    )
    .forEach(link => {

      link.addEventListener(
        "click",
        event => {

          const href =
            link.getAttribute(
              "href"
            );


          if (
            !href ||
            href === "#"
          ) {
            return;
          }


          const target =
            document.querySelector(
              href
            );


          if (!target) {
            return;
          }


          event.preventDefault();


          target.scrollIntoView({
            behavior:
              window.matchMedia(
                "(prefers-reduced-motion: reduce)"
              ).matches
                ? "auto"
                : "smooth",

            block: "start"
          });


          history.replaceState(
            null,
            "",
            href
          );


          if (
            !target.hasAttribute(
              "tabindex"
            )
          ) {

            target.setAttribute(
              "tabindex",
              "-1"
            );
          }


          setTimeout(() => {

            target.focus({
              preventScroll: true
            });

          }, 350);
        }
      );
    });


  /* ==========================================================
     ACTIVE SECTION
     ========================================================== */

  const observedSections =
    document.querySelectorAll(
      "[data-observe-section]"
    );


  const sectionLinks =
    document.querySelectorAll(
      "[data-section-link]"
    );


  if (
    "IntersectionObserver"
    in window
  ) {

    const observer =
      new IntersectionObserver(
        entries => {

          const visible =
            entries
              .filter(entry =>
                entry.isIntersecting
              )
              .sort(
                (a, b) =>
                  b.intersectionRatio -
                  a.intersectionRatio
              )[0];


          if (!visible) {
            return;
          }


          const activeId =
            visible.target.dataset
              .observeSection;


          sectionLinks.forEach(
            link => {

              link.classList.toggle(
                "is-current",
                link.dataset
                  .sectionLink ===
                  activeId
              );
            }
          );
        },
        {
          rootMargin:
            "-30% 0px -55% 0px",

          threshold: [
            0,
            0.1,
            0.25,
            0.5
          ]
        }
      );


    observedSections.forEach(
      section =>
        observer.observe(section)
    );
  }


  /* ==========================================================
     AUDIO
     ========================================================== */

  const audioControllers =
    document.querySelectorAll(
      "[data-audio-controller]"
    );


  let activeAudio =
    null;


  function formatTime(seconds) {

    if (
      !Number.isFinite(seconds)
    ) {
      return "--:--";
    }


    const minutes =
      Math.floor(
        seconds / 60
      );


    const remaining =
      Math.floor(
        seconds % 60
      )
        .toString()
        .padStart(
          2,
          "0"
        );


    return (
      minutes +
      ":" +
      remaining
    );
  }


  audioControllers.forEach(
    controller => {

      const button =
        controller.querySelector(
          ".audio-controller__play"
        );

      const buttonIcon =
        button?.querySelector(
          "span"
        );

      const status =
        controller.querySelector(
          "[data-audio-status]"
        );

      const time =
        controller.querySelector(
          "[data-audio-time]"
        );

      const progress =
        controller.querySelector(
          "[data-audio-progress]"
        );

      const src =
        controller.dataset.audioSrc;


      if (
        !button ||
        !status ||
        !time ||
        !progress ||
        !src
      ) {
        return;
      }


      let audio =
        null;


      function setIdle() {

        if (buttonIcon) {
          buttonIcon.textContent =
            "▶";
        }

        button.setAttribute(
          "aria-label",
          "پخش"
        );
      }


      function createAudio() {

        if (audio) {
          return audio;
        }


        audio =
          new Audio();


        audio.preload =
          "metadata";


        audio.src =
          src;


        audio.addEventListener(
          "loadedmetadata",
          () => {

            status.textContent =
              "آماده";

            time.textContent =
              formatTime(
                audio.duration
              );
          }
        );


        audio.addEventListener(
          "timeupdate",
          () => {

            if (
              !audio.duration
            ) {
              return;
            }


            const ratio =
              (
                audio.currentTime /
                audio.duration
              ) *
              100;


            progress.style.width =
              ratio + "%";


            time.textContent =
              formatTime(
                audio.currentTime
              ) +
              " / " +
              formatTime(
                audio.duration
              );
          }
        );


        audio.addEventListener(
          "play",
          () => {

            activeAudio =
              audio;

            status.textContent =
              "در حال پخش";

            if (buttonIcon) {
              buttonIcon.textContent =
                "❚❚";
            }

            button.setAttribute(
              "aria-label",
              "توقف"
            );
          }
        );


        audio.addEventListener(
          "pause",
          () => {

            if (
              activeAudio === audio
            ) {
              activeAudio = null;
            }


            if (
              audio.currentTime > 0 &&
              audio.currentTime <
              audio.duration
            ) {

              status.textContent =
                "متوقف";
            }


            setIdle();
          }
        );


        audio.addEventListener(
          "ended",
          () => {

            status.textContent =
              "پایان";

            progress.style.width =
              "0%";

            setIdle();
          }
        );


        audio.addEventListener(
          "error",
          () => {

            status.textContent =
              "فایل صوتی هنوز اضافه نشده";

            time.textContent =
              "--:--";

            progress.style.width =
              "0%";

            setIdle();
          }
        );


        return audio;
      }


      button.addEventListener(
        "click",
        async () => {

          const player =
            createAudio();


          if (
            activeAudio &&
            activeAudio !== player
          ) {

            activeAudio.pause();
          }


          if (
            !player.paused
          ) {

            player.pause();
            return;
          }


          status.textContent =
            "در حال بارگذاری";


          try {

            await player.play();

          }
          catch {

            status.textContent =
              "فایل صوتی هنوز اضافه نشده";

            setIdle();
          }
        }
      );
    }
  );


  /* ==========================================================
     FEEDBACK PLACEHOLDER
     ========================================================== */

  document
    .getElementById(
      "feedbackPlaceholder"
    )
    ?.addEventListener(
      "click",
      () => {

        window.alert(
          "صفحهٔ رسمی ثبت نقد و پیشنهاد در فاز بعدی فعال خواهد شد."
        );
      }
    );


})();
