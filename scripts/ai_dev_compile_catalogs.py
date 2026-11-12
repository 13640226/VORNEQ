"""Compile existing local gettext catalogs for isolated development tests only."""
from pathlib import Path
from babel.messages import mofile, pofile

project = Path(__file__).resolve().parent.parent
for language in ("de", "fa"):
    locale = project / "locale" / language / "LC_MESSAGES"
    with (locale / "django.po").open("rb") as src:
        catalog = pofile.read_po(src, locale=language, abort_invalid=True)
    with (locale / "django.mo").open("wb") as out:
        mofile.write_mo(out, catalog, use_fuzzy=False)
    print("LOCAL_TRANSLATION_COMPILED=" + language)
