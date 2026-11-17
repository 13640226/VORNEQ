"""Read-only quality check of Persian Wikipedia search queries (manual, not CI).

Compares the full question with the keyword query built by the production
function ``search_keywords``. Hit = one of the top-3 result titles equals an
expected article title (strict). No OpenAI, no VORNEQ server, no database.

Run from the repository root on a machine with internet access:

    python -X utf8 scripts/ai_eval/fa_wikipedia_search_eval.py

It sends 2 requests per question to fa.wikipedia.org (80 in total) with a
pause between requests and backs off on HTTP 429. Rate-limit errors are
reported separately and never counted as misses.
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from apps.ai_core.engine.evidence_ranking import normalize_text, search_keywords  # noqa: E402

UA = "VORNEQ-GlobalAI-eval/1.0 (read-only search quality check; repository 13640226/VORNEQ)"

# Set 1 was visible while the stop list was written; set 2 is the held-out check.
SET_1 = [
    ("فتوسنتز چیست؟", ["فتوسنتز"]), ("ابن‌سینا که بود؟", ["ابن‌سینا", "ابن سینا"]),
    ("سلول خورشیدی چگونه کار می‌کند؟", ["سلول خورشیدی"]), ("پایتخت آلمان کجاست؟", ["برلین"]),
    ("جهان چند کهکشان دارد؟", ["کهکشان"]), ("چرا آسمان آبی است؟", ["پراکندگی رایلی", "رنگ آسمان"]),
    ("حافظ چه کسی بود؟", ["حافظ"]), ("دمای سطح خورشید چقدر است؟", ["خورشید"]),
    ("زلزله چگونه رخ می‌دهد؟", ["زمین‌لرزه", "زلزله"]), ("تخت جمشید در کدام شهر است؟", ["تخت جمشید"]),
    ("دی‌ان‌ای چیست؟", ["دی‌ان‌ای"]), ("انقلاب صنعتی کی شروع شد؟", ["انقلاب صنعتی"]),
    ("بلندترین کوه ایران کدام است؟", ["دماوند", "قله دماوند"]), ("واکسن چگونه کار می‌کند؟", ["واکسن"]),
    ("خیام چه کتاب‌هایی نوشت؟", ["خیام"]), ("قانون دوم نیوتن را توضیح بده", ["قوانین حرکت نیوتن"]),
    ("اینترنت چگونه به وجود آمد؟", ["اینترنت"]), ("سیاه‌چاله چیست؟", ["سیاه‌چاله"]),
    ("فردوسی شاهنامه را کی سرود؟", ["شاهنامه", "فردوسی"]),
    ("کربن‌دی‌اکسید چه تأثیری بر گرمایش زمین دارد؟", ["گرمایش جهانی", "کربن دی‌اکسید"]),
]
SET_2 = [
    ("مولوی چه کسی بود؟", ["مولوی"]), ("خلیج فارس کجاست؟", ["خلیج فارس"]),
    ("اتم از چه چیزی ساخته شده است؟", ["اتم"]), ("رنسانس چه بود؟", ["رنسانس"]),
    ("هوش مصنوعی چیست؟", ["هوش مصنوعی"]), ("کوروش بزرگ کیست؟", ["کوروش بزرگ"]),
    ("آتشفشان چگونه فوران می‌کند؟", ["آتشفشان", "آتش‌فشان"]),
    ("زبان فارسی از کدام خانواده زبانی است؟", ["زبان فارسی"]),
    ("دریای خزر چقدر عمق دارد؟", ["دریای خزر"]),
    ("نظریه نسبیت را چه کسی ارائه داد؟", ["نظریه نسبیت", "نسبیت عام", "نسبیت خاص"]),
    ("ماه چگونه به وجود آمد؟", ["ماه"]), ("گلستان سعدی دربارهٔ چیست؟", ["گلستان سعدی", "گلستان (کتاب)"]),
    ("پنی‌سیلین را چه کسی کشف کرد؟", ["پنی‌سیلین"]), ("دیابت چیست؟", ["دیابت", "دیابت شیرین"]),
    ("رود نیل از کدام کشورها می‌گذرد؟", ["رود نیل", "نیل"]), ("جنگ جهانی دوم کی تمام شد؟", ["جنگ جهانی دوم"]),
    ("زرافه چه می‌خورد؟", ["زرافه"]), ("ابوریحان بیرونی چه کارهایی کرد؟", ["ابوریحان بیرونی"]),
    ("مس چه کاربردهایی دارد؟", ["مس"]), ("نوروز چه جشنی است؟", ["نوروز"]),
]


def search(query):
    fields = {"action": "query", "format": "json", "formatversion": "2", "list": "search",
              "srsearch": query, "srlimit": "3", "srnamespace": "0", "maxlag": "5"}
    request = urllib.request.Request("https://fa.wikipedia.org/w/api.php?" + urllib.parse.urlencode(fields),
                                     headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read(300_000).decode("utf-8"))
            return [hit["title"] for hit in data.get("query", {}).get("search", [])], None
        except urllib.error.HTTPError as exc:
            error = f"HTTP {exc.code}"
            time.sleep(20 * (attempt + 1))
        except (OSError, ValueError) as exc:
            error = type(exc).__name__
            time.sleep(5)
    return [], error


def strict_hit(titles, expected):
    key = lambda text: normalize_text(text).replace("‌", " ").strip()  # noqa: E731
    wanted = {key(e) for e in expected}
    return any(key(t) in wanted for t in titles)


def main():
    variants = {"raw": lambda q: " ".join(q.split()), "keywords": lambda q: search_keywords(q, "fa")}
    report = {}
    for set_name, questions in (("set_1_seen", SET_1), ("set_2_heldout", SET_2)):
        score = {name: 0 for name in variants}
        errors = {name: 0 for name in variants}
        for question, expected in questions:
            for name, build in variants.items():
                titles, error = search(build(question))
                errors[name] += error is not None
                score[name] += error is None and strict_hit(titles, expected)
                time.sleep(2.0)
        report[set_name] = {"n": len(questions), "hits": score, "errors": errors}
        print(set_name, report[set_name], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
