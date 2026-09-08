#!/usr/bin/env python3
"""VORNEQ Homepage Redesign Script (v2).

Safely applies the homepage philosophy/visual redesign when it is missing,
checks the fetched ``origin/main`` rather than the current working tree,
runs tests, and opens or updates a pull request only when a real diff exists.

The script never merges a pull request.

Usage:
    python scripts/redesign_homepage.py /path/to/VORNEQ
    python scripts/redesign_homepage.py /path/to/VORNEQ \
        --branch redesign/homepage-next \
        --title "redesign: refine homepage"

Environment:
    VORNEQ_BRANCH
    VORNEQ_PR_TITLE
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_BRANCH = "redesign/homepage-philosophy"
DEFAULT_TITLE = "redesign: align homepage with Platform Philosophy v2"
COMMIT_MESSAGE = "redesign: align homepage with Platform Philosophy v2"

TARGET_FILES = (
    "templates/index.html",
    "assets/css/homepage.css",
    "config/tests/test_homepage.py",
    "apps/search/tests/test_pages.py",
)

PR_BODY = """## Summary

Safely applies the VORNEQ homepage philosophy and visual redesign only when
needed, with explicit guards against stale baselines and empty pull requests.

### Guarantees
- reads the latest `origin/main` after `git fetch`;
- keeps Search, Registry, Trust/Reputation, URLs, ADRs and backend behavior intact;
- uses idempotent homepage/test mutations;
- applies the visual refinement as an override patch only when the visual v2
  markers are absent;
- runs the full Django test suite unless `--skip-tests` is supplied;
- refuses to create a PR when `origin/main...HEAD` has no diff;
- never merges automatically.
"""

PHILOSOPHY_INDICATORS = (
    "The Discoverable Knowledge Platform",
    "Context, not Score",
    "Evidence, not Truth",
    "Portable Identity",
    "Verification produces inspectable findings",
)

CSS_INDICATORS = (
    "global-home-float",
    "global-home__visual::after",
    "global-home__feed-heading::after",
    "position:sticky",
)

CSS_PATCH_MARKER = "/* redesign_homepage.py visual-v2 override */"

CSS_V2_OVERRIDE = r"""
/* redesign_homepage.py visual-v2 override */
.global-home{position:relative;isolation:isolate;overflow:hidden;background:radial-gradient(circle at 88% 4%,color-mix(in srgb,var(--color-accent) 14%,transparent),transparent 29rem),radial-gradient(circle at 8% 36%,color-mix(in srgb,var(--color-accent) 5%,transparent),transparent 25rem),var(--color-bg-page)}
.global-home::before{content:"";position:absolute;z-index:-1;inset:0 0 auto;height:38rem;pointer-events:none;opacity:.42;background-image:linear-gradient(color-mix(in srgb,var(--color-border) 44%,transparent) 1px,transparent 1px),linear-gradient(90deg,color-mix(in srgb,var(--color-border) 44%,transparent) 1px,transparent 1px);background-size:48px 48px;mask-image:linear-gradient(to bottom,#000,transparent 88%)}
.global-home__shell{width:min(var(--container-width),calc(100% - 2 * var(--space-5)))}
.global-home__hero{position:relative;padding:clamp(var(--space-7),7vw,var(--space-9)) 0 var(--space-8)}
.global-home__brand-row{grid-template-columns:minmax(0,1.45fr) minmax(240px,.55fr);gap:clamp(var(--space-6),6vw,var(--space-9));margin-bottom:var(--space-7)}
.global-home__brand-copy{max-width:820px}
.global-home__title{max-width:12ch;font-size:clamp(2.6rem,6.6vw,var(--font-size-display));line-height:.94;letter-spacing:-.05em;text-wrap:balance}
.global-home__lede{max-width:64ch;line-height:1.7}
.global-home__brand-copy>.global-home__kicker:last-child{display:inline-flex;margin-top:var(--space-5);padding:var(--space-2) var(--space-3);border:1px solid color-mix(in srgb,var(--color-accent) 28%,var(--color-border));border-radius:var(--radius-pill);background:color-mix(in srgb,var(--color-bg-elevated) 88%,transparent);letter-spacing:.06em;text-transform:none}
.global-home__visual{position:relative;min-height:280px}
.global-home__visual::before,.global-home__visual::after{content:"";position:absolute;border:1px solid color-mix(in srgb,var(--color-accent) 22%,transparent);border-radius:50%;pointer-events:none}
.global-home__visual::before{width:240px;aspect-ratio:1}
.global-home__visual::after{width:300px;aspect-ratio:1;border-style:dashed;opacity:.55}
.global-home__globe{position:relative;width:min(100%,230px);filter:drop-shadow(0 22px 42px color-mix(in srgb,var(--color-accent) 20%,transparent));animation:global-home-float 8s ease-in-out infinite}
.global-home__search-surface{position:relative;border-color:color-mix(in srgb,var(--color-border) 64%,var(--color-accent) 36%);border-radius:calc(var(--radius-lg) + 4px);background:color-mix(in srgb,var(--color-bg-elevated) 91%,transparent);box-shadow:var(--shadow-medium),0 18px 54px color-mix(in srgb,var(--color-accent) 7%,transparent)}
.global-home__dashboard{padding:var(--space-8) 0 var(--space-9)}
.global-home__dashboard-grid{grid-template-columns:minmax(0,1.8fr) minmax(300px,.72fr);gap:clamp(var(--space-5),4vw,var(--space-7))}
.global-home__feed-heading{position:relative;padding-bottom:var(--space-4);border-bottom:1px solid var(--color-border)}
.global-home__feed-heading::after{content:"";position:absolute;inset:auto auto -1px 0;width:72px;height:2px;background:var(--color-accent)}
.global-home__featured{position:relative;overflow:hidden;padding:clamp(var(--space-5),4vw,var(--space-7));border-radius:calc(var(--radius-lg) + 4px)}
.global-home__result{position:relative;min-height:190px;transition:transform var(--motion-duration-base) var(--motion-easing-out),border-color var(--motion-duration-base) var(--motion-easing-standard),box-shadow var(--motion-duration-base) var(--motion-easing-standard)}
.global-home__result:hover{transform:translateY(-3px);border-color:color-mix(in srgb,var(--color-border) 58%,var(--color-accent) 42%);box-shadow:var(--shadow-medium)}
.global-home__right-rail{position:sticky;top:var(--space-5)}
.global-home__rail-block{position:relative;overflow:hidden;background:color-mix(in srgb,var(--color-bg-elevated) 97%,transparent)}
.global-home__rail-block::after{content:"";position:absolute;inset:0 0 auto;height:2px;background:linear-gradient(90deg,var(--color-accent),transparent);opacity:.38}
@keyframes global-home-float{0%,100%{transform:translateY(0) rotate(0)}50%{transform:translateY(-8px) rotate(1.5deg)}}
@media(max-width:820px){.global-home__dashboard-grid{grid-template-columns:1fr}.global-home__right-rail{position:static;grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:620px){.global-home__shell{width:min(var(--container-width),calc(100% - 2 * var(--space-3)))}.global-home__brand-row{grid-template-columns:1fr}.global-home__visual{display:none}.global-home__results-grid,.global-home__right-rail{grid-template-columns:1fr}.global-home__result{min-height:0}}
@media(prefers-reduced-motion:reduce){.global-home__globe{animation:none}.global-home__result{transition:none}}
""".strip()


def run_command(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(args))
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        text=True,
        capture_output=capture,
    )


def require_program(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required program not found: {name}")


def ensure_clean(repo: Path) -> None:
    result = run_command(
        ["git", "status", "--porcelain"],
        cwd=repo,
        capture=True,
    )
    if result.stdout.strip():
        raise RuntimeError(
            "Repository contains uncommitted changes:\n" + result.stdout
        )


def fetch_origin(repo: Path) -> None:
    run_command(["git", "fetch", "origin", "main"], cwd=repo)


def read_from_ref(repo: Path, ref: str, path: str) -> str:
    result = run_command(
        ["git", "show", f"{ref}:{path}"],
        cwd=repo,
        capture=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def redesign_already_applied_to_origin_main(repo: Path) -> bool:
    index_text = read_from_ref(repo, "origin/main", "templates/index.html")
    css_text = read_from_ref(repo, "origin/main", "assets/css/homepage.css")
    return all(item in index_text for item in PHILOSOPHY_INDICATORS) and all(
        item in css_text for item in CSS_INDICATORS
    )


def branch_exists(repo: Path, branch: str) -> bool:
    result = run_command(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo,
        check=False,
    )
    return result.returncode == 0


def prepare_branch(repo: Path, branch: str) -> None:
    if branch_exists(repo, branch):
        run_command(["git", "checkout", branch], cwd=repo)
        run_command(["git", "rebase", "origin/main"], cwd=repo)
    else:
        run_command(["git", "checkout", "-b", branch, "origin/main"], cwd=repo)


def replace_once_if_present(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Expected source text not found:\n{old[:160]}")
    return text.replace(old, new, 1)


def modify_index(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    text = replace_once_if_present(
        text,
        '{% block title %}VORNEQ — {% trans "The Global Knowledge Platform" %}{% endblock %}',
        '{% block title %}VORNEQ — {% trans "The Discoverable Knowledge Platform" %}{% endblock %}',
    )

    old_hero = (
        '          <p class="global-home__lede">{% trans "Search knowledge, products, media, documents, and audio from one connected discovery surface." %}</p>'
    )
    new_hero = old_hero + "\n" + (
        '          <p class="global-home__lede">{% trans "VORNEQ does not decide what is true, trustworthy, or valuable. It makes discovery, attribution, evidence, context, and capability inspectable." %}</p>\n'
        '          <p class="global-home__kicker">{% trans "Context, not Score · Evidence, not Truth · Portable Identity" %}</p>'
    )
    if "VORNEQ does not decide what is true" not in text:
        text = replace_once_if_present(text, old_hero, new_hero)

    text = text.replace(
        "Verification is evidence about an assertion; it is not truth itself.",
        "Verification produces inspectable findings and evidence about an assertion; it does not establish final truth.",
    )

    apps_marker = (
        '        <section id="apps" class="right-rail__block global-home__rail-block" '
        'aria-labelledby="apps-title" data-homepage-signal-section>'
    )
    identity_block = (
        '        <section id="identity" class="right-rail__block global-home__rail-block" aria-labelledby="identity-title">\n'
        '          <p class="global-home__kicker">{% trans "Portable identity" %}</p>\n'
        '          <h2 id="identity-title">{% trans "Identity across experiences, not app-local." %}</h2>\n'
        '          <p>{% trans "Identity is designed to be portable across experiences rather than app-local." %}</p>\n'
        '        </section>\n\n'
    )
    if 'id="identity"' not in text:
        text = replace_once_if_present(text, apps_marker, identity_block + apps_marker)

    path.write_text(text, encoding="utf-8")


def update_css(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if all(item in text for item in CSS_INDICATORS):
        return
    if CSS_PATCH_MARKER not in text:
        text = text.rstrip() + "\n\n" + CSS_V2_OVERRIDE + "\n"
        path.write_text(text, encoding="utf-8")


def update_search_tests(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '"Verification is evidence about an assertion",',
        '"Verification produces inspectable findings and evidence about an assertion",',
    )
    path.write_text(text, encoding="utf-8")


def update_homepage_tests(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if 'id="identity"' not in text and 'id=\\"identity\\"' not in text:
        anchor = '        self.assertContains(response, \'id="platform"\')\n'
        if anchor in text:
            text = text.replace(
                anchor,
                anchor + '        self.assertContains(response, \'id="identity"\')\n',
                1,
            )

    if "Identity is designed to be portable across experiences rather than app-local." not in text:
        insertion = '''\n    def test_homepage_renders_platform_philosophy_without_overclaiming(self):\n        response = self.get_english_home()\n        self.assertEqual(response.status_code, 200)\n        self.assertContains(response, "The Discoverable Knowledge Platform")\n        self.assertContains(response, "VORNEQ does not decide what is true, trustworthy, or valuable.")\n        self.assertContains(response, "Context, not Score · Evidence, not Truth · Portable Identity")\n        self.assertContains(response, "Verification produces inspectable findings and evidence about an assertion")\n        self.assertContains(response, "Identity is designed to be portable across experiences rather than app-local.")\n        self.assertNotContains(response, "Your identity moves across experiences")\n'''
        text = text.rstrip() + "\n" + insertion

    path.write_text(text, encoding="utf-8")


def apply_mutations(repo: Path) -> None:
    modify_index(repo / "templates/index.html")
    update_css(repo / "assets/css/homepage.css")
    update_homepage_tests(repo / "config/tests/test_homepage.py")
    update_search_tests(repo / "apps/search/tests/test_pages.py")


def working_tree_has_changes(repo: Path) -> bool:
    result = run_command(
        ["git", "status", "--porcelain", "--", *TARGET_FILES],
        cwd=repo,
        capture=True,
    )
    return bool(result.stdout.strip())


def run_full_tests(repo: Path) -> None:
    python = shutil.which("python") or shutil.which("python3")
    if python is None:
        raise RuntimeError("Python interpreter not found")
    run_command([python, "manage.py", "test"], cwd=repo)


def commit_and_push(repo: Path, branch: str) -> bool:
    if not working_tree_has_changes(repo):
        print("No working-tree changes were produced.")
        return False

    run_command(["git", "add", "--", *TARGET_FILES], cwd=repo)
    run_command(["git", "commit", "-m", COMMIT_MESSAGE], cwd=repo)
    run_command(["git", "push", "--set-upstream", "origin", branch], cwd=repo)
    return True


def branch_has_diff_from_main(repo: Path) -> bool:
    result = run_command(
        ["git", "diff", "--quiet", "origin/main...HEAD"],
        cwd=repo,
        check=False,
    )
    return result.returncode == 1


def open_or_update_pr(repo: Path, branch: str, title: str) -> None:
    if not branch_has_diff_from_main(repo):
        print("No diff exists between origin/main and HEAD; PR creation skipped.")
        return

    existing = run_command(
        [
            "gh", "pr", "list", "--head", branch, "--state", "open",
            "--json", "number", "--jq", ".[0].number // empty",
        ],
        cwd=repo,
        capture=True,
    )
    pr_number = existing.stdout.strip()

    if pr_number:
        run_command(
            ["gh", "pr", "edit", pr_number, "--title", title, "--body", PR_BODY],
            cwd=repo,
        )
    else:
        run_command(
            [
                "gh", "pr", "create", "--base", "main", "--head", branch,
                "--title", title, "--body", PR_BODY,
            ],
            cwd=repo,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo_path", help="Path to the VORNEQ repository")
    parser.add_argument(
        "--branch",
        default=os.environ.get("VORNEQ_BRANCH", DEFAULT_BRANCH),
        help="Feature branch name",
    )
    parser.add_argument(
        "--title",
        default=os.environ.get("VORNEQ_PR_TITLE", DEFAULT_TITLE),
        help="Pull-request title",
    )
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Attempt idempotent mutations even when origin/main already contains v2",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(args.repo_path).expanduser().resolve()

    if not repo.is_dir() or not (repo / ".git").exists() or not (repo / "manage.py").exists():
        raise RuntimeError(f"Invalid VORNEQ repository path: {repo}")

    require_program("git")
    require_program("gh")
    ensure_clean(repo)
    fetch_origin(repo)

    if redesign_already_applied_to_origin_main(repo) and not args.force:
        print("Homepage redesign is already present on origin/main. No action needed.")
        return 0

    prepare_branch(repo, args.branch)
    apply_mutations(repo)

    if not working_tree_has_changes(repo):
        print("Mutations produced no changes. No commit or PR is necessary.")
        return 0

    if not args.skip_tests:
        run_full_tests(repo)

    if commit_and_push(repo, args.branch):
        open_or_update_pr(repo, args.branch, args.title)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
