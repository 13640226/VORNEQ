(() => {
    "use strict";

    const nav = document.querySelector("[data-homepage-signal-nav]");
    if (!nav) return;

    const links = Array.from(
        nav.querySelectorAll("[data-homepage-signal-link]")
    );
    const progress = nav.querySelector("[data-homepage-signal-progress]");

    const sections = links
        .map((link) => {
            const href = link.getAttribute("href");
            if (!href || !href.startsWith("#")) return null;

            const section = document.getElementById(href.slice(1));
            return section ? { link, section, id: section.id } : null;
        })
        .filter(Boolean);

    if (!sections.length) return;

    const TOTAL_SECTIONS = 7;
    const DIRECT_INTERACTION_SUPPRESSION_MS = 500;
    const SCROLL_KEYS = new Set([
        "ArrowUp",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
        "PageUp",
        "PageDown",
        "Home",
        "End",
        " ",
    ]);

    const reduceMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
    );

    let activeId = null;
    let pendingTargetId = null;
    let lastDirectInteractionAt = 0;

    const getEntry = (id) =>
        sections.find((entry) => entry.id === id) || null;

    const hashId = () => {
        if (!window.location.hash) return null;

        try {
            return decodeURIComponent(window.location.hash.slice(1));
        } catch {
            return window.location.hash.slice(1);
        }
    };

    const setProgress = (index) => {
        if (!progress) return;

        const ratio = (index + 1) / TOTAL_SECTIONS;
        progress.style.setProperty("--signal-progress", String(ratio));
        progress.style.setProperty(
            "--signal-progress-percent",
            `${ratio * 100}%`
        );
    };

    const revealActiveLink = (link) => {
        if (!link) return;

        if (
            Date.now() - lastDirectInteractionAt <
            DIRECT_INTERACTION_SUPPRESSION_MS
        ) {
            return;
        }

        const compact = window.matchMedia("(max-width: 639px)").matches;
        if (!compact) return;

        link.scrollIntoView({
            behavior: "auto",
            block: "nearest",
            inline: "nearest",
        });
    };

    const setActive = (id, { reveal = true } = {}) => {
        const index = sections.findIndex((entry) => entry.id === id);
        if (index < 0) return;

        activeId = id;

        sections.forEach(({ link, id: sectionId }) => {
            if (sectionId === id) {
                link.setAttribute("aria-current", "location");
            } else {
                link.removeAttribute("aria-current");
            }
        });

        setProgress(index);

        if (reveal) {
            revealActiveLink(sections[index].link);
        }
    };

    const measureHeader = () => {
        const header = document.querySelector(".standalone-nav");
        if (!header) return;

        const height = Math.ceil(header.getBoundingClientRect().height);
        if (height > 0) {
            document.documentElement.style.setProperty(
                "--signal-scroll-offset",
                `${height}px`
            );
        }

        // Deliberately do not alter the current scroll position.
    };

    const markDirectInteraction = () => {
        lastDirectInteractionAt = Date.now();
        pendingTargetId = null;
    };

    const onKeyDown = (event) => {
        if (SCROLL_KEYS.has(event.key)) {
            markDirectInteraction();
        }
    };

    const updateHashFromObserver = (id) => {
        if (pendingTargetId) return;
        if (hashId() === id) return;

        const url = new URL(window.location.href);
        url.hash = id;
        window.history.replaceState(window.history.state, "", url);
    };

    const observer = new IntersectionObserver(
        (entries) => {
            const intersecting = entries
                .filter((entry) => entry.isIntersecting)
                .sort((a, b) => {
                    const aDistance = Math.abs(a.boundingClientRect.top);
                    const bDistance = Math.abs(b.boundingClientRect.top);
                    return aDistance - bDistance;
                });

            if (!intersecting.length) return;

            if (pendingTargetId) {
                const pendingEntry = intersecting.find(
                    (entry) => entry.target.id === pendingTargetId
                );

                if (!pendingEntry) {
                    return;
                }

                const resolvedId = pendingTargetId;
                pendingTargetId = null;
                setActive(resolvedId);
                return;
            }

            const id = intersecting[0].target.id;
            setActive(id);
            updateHashFromObserver(id);
        },
        {
            root: null,
            rootMargin: "-20% 0px -55% 0px",
            threshold: [0, 0.01, 0.25, 0.5],
        }
    );

    sections.forEach(({ section }) => observer.observe(section));

    links.forEach((link) => {
        link.addEventListener("click", (event) => {
            const href = link.getAttribute("href");
            if (!href || !href.startsWith("#")) return;

            const id = href.slice(1);
            const target = getEntry(id);
            if (!target) return;

            event.preventDefault();

            // Last Click Wins: no queue; every click replaces the lock.
            pendingTargetId = id;
            setActive(id);

            const url = new URL(window.location.href);
            url.hash = id;
            window.history.pushState(window.history.state, "", url);

            target.section.scrollIntoView({
                behavior: reduceMotion.matches ? "auto" : "smooth",
                block: "start",
            });
        });
    });

    window.addEventListener("pointerdown", markDirectInteraction, {
        passive: true,
    });
    window.addEventListener("touchstart", markDirectInteraction, {
        passive: true,
    });
    window.addEventListener("wheel", markDirectInteraction, {
        passive: true,
    });
    window.addEventListener("keydown", onKeyDown);

    window.addEventListener("popstate", () => {
        // Browser history navigation supersedes any pending Rail target.
        pendingTargetId = null;

        const id = hashId();
        const target = id ? getEntry(id) : null;

        if (!target) {
            // Preserve unrelated/empty hashes. Observer will settle state.
            return;
        }

        setActive(id);

        // Do not create or replace history here. The browser owns popstate.
        // Reconcile only if native history navigation did not expose target.
        window.requestAnimationFrame(() => {
            const rect = target.section.getBoundingClientRect();
            const viewportHeight =
                window.innerHeight || document.documentElement.clientHeight;

            if (rect.bottom <= 0 || rect.top >= viewportHeight) {
                target.section.scrollIntoView({
                    behavior: reduceMotion.matches ? "auto" : "smooth",
                    block: "start",
                });
            }
        });
    });

    const resizeObserver =
        "ResizeObserver" in window
            ? new ResizeObserver(() => measureHeader())
            : null;

    const standaloneNav = document.querySelector(".standalone-nav");
    if (resizeObserver && standaloneNav) {
        resizeObserver.observe(standaloneNav);
    }

    window.addEventListener("resize", measureHeader, { passive: true });

    /*
     * Non-intrusive initialization:
     * measure offset and synchronize state only.
     * Never correct or change the current document scroll position here.
     */
    measureHeader();

    const initialId = hashId();
    const initialTarget = initialId ? getEntry(initialId) : null;

    if (initialTarget) {
        setActive(initialId, { reveal: false });
    } else {
        setActive(sections[0].id, { reveal: false });
    }
})();
