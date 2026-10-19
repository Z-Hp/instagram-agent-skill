"""
The six scripts on Persian input, plus English golden values that must not
move. The English numbers are the ones published in the README.

Run from the repo root, standard library only:

    python -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
for folder in ("ig-human", "ig-reel", "ig-caption", "ig-viral"):
    sys.path.insert(0, os.path.join(SKILLS, folder))

import beats      # noqa: E402
import caption    # noqa: E402
import detect     # noqa: E402
import hookscore  # noqa: E402
import humanize   # noqa: E402
import swipe      # noqa: E402

Z = "‌"
LEX = humanize.load_lexicon()

FA_DRAFT = (
    f"من می{Z}خواهم با هوش مصنوعی ۱۸ میلیون تومان صرفه{Z}جویی کنم. "
    f"این کار ۵ ساعت طول می{Z}کشید. حالا ۲۰ دقیقه است! "
    f"شما هم می{Z}توانید؛ فقط کافی است امروز شروع کنید. "
    f"«پرامپت» را کپی کنید و نتیجه را برای من بفرستید، چون می{Z}خواهم بدانم "
    f"در کار شما چه تغییری داد و چقدر وقت آزاد کرد."
)


class Humanize(unittest.TestCase):
    def test_keeps_every_half_space(self):
        clean, report = humanize.humanize(FA_DRAFT, LEX)
        self.assertEqual(clean.count(Z), FA_DRAFT.count(Z))
        self.assertEqual(report["invisible"], [])

    def test_em_dash_becomes_the_persian_comma(self):
        clean, _ = humanize.humanize("این روش — اگر درست اجرا شود — جواب می‌دهد.", LEX)
        self.assertEqual(clean.strip(), "این روش، اگر درست اجرا شود، جواب می‌دهد.")

    def test_em_dash_is_still_a_latin_comma_in_english(self):
        clean, _ = humanize.humanize("It works — if you ship it.", LEX)
        self.assertEqual(clean.strip(), "It works, if you ship it.")

    def test_fixes_the_missing_half_space(self):
        clean, report = humanize.humanize("من می خواهم مدل ها را مقایسه کنم.", LEX)
        self.assertEqual(clean.strip(), f"من می{Z}خواهم مدل{Z}ها را مقایسه کنم.")
        self.assertTrue(report["persian"])

    def test_still_strips_a_zero_width_space(self):
        clean, report = humanize.humanize("می​خواهم یاد بگیرم", LEX)
        self.assertNotIn("​", clean)
        self.assertEqual(report["invisible"][0]["count"], 1)

    def test_still_strips_a_half_space_hidden_in_english(self):
        clean, _ = humanize.humanize(f"Con{Z}tent is king.", LEX)
        self.assertEqual(clean.strip(), "Content is king.")


class Detect(unittest.TestCase):
    def test_correct_persian_is_not_a_fingerprint(self):
        results, _, verdict = detect.run(FA_DRAFT, LEX)
        self.assertEqual(results["FINGERPRINT"][0], 100.0)
        self.assertNotEqual(verdict, "FLAGGED")

    def test_english_only_checks_sit_out_on_persian(self):
        results, _, _ = detect.run(FA_DRAFT, LEX)
        self.assertIsNone(results["SLOP DENSITY"][0])
        self.assertIsNone(results["VOICE"][0])
        self.assertIsNotNone(results["BURSTINESS"][0])

    def test_persian_words_are_counted(self):
        self.assertGreater(len(detect.words(FA_DRAFT)), 25)

    def test_english_still_runs_all_five(self):
        results, _, _ = detect.run("I wrote this myself and I'm proud of it. " * 8, LEX)
        self.assertTrue(all(results[c][0] is not None for c in detect.CHECKS))


class HookScore(unittest.TestCase):
    def test_english_scores_match_the_readme(self):
        for hook, score, verdict in [
            ("Nobody tells you that your first 30 reels are supposed to flop", 85.6, "STRONG"),
            ("I lost $18,000 because of one missing contract.", 81.4, "STRONG"),
            ("Stop scrolling if you want to grow on Instagram in 2026 🔥", 54.4, "OK"),
            ("Hey guys, today I wanted to talk about content strategy", 9.6, "WEAK"),
        ]:
            _, overall, v, _ = hookscore.run(hook)
            self.assertEqual((round(overall, 1), v), (score, verdict), hook)

    def test_persian_hook_has_words(self):
        results, _, _, _ = hookscore.run("۱۸ میلیون تومان را به‌خاطر یک قرارداد از دست دادم.")
        self.assertIn("10 words", results["LENGTH"][1])
        self.assertEqual(results["LENGTH"][0], 100.0)

    def test_persian_scores_only_what_it_can(self):
        results, _, _, _ = hookscore.run("۱۸ میلیون تومان را به‌خاطر یک قرارداد از دست دادم.")
        self.assertEqual(hookscore.scored(results), 2)
        for name in ("STAKES", "FRONTLOAD", "ADDRESS"):
            self.assertIsNone(results[name][0])


class Beats(unittest.TestCase):
    SCRIPT = ("۱۸ میلیون تومان را به‌خاطر یک قرارداد از دست دادم.\n"
              "این بند را الان در همه قراردادهایم می‌گذارم.\n"
              "پرداخت هنگام تحویل، نه هنگام تأیید.\n"
              "همین یک بند ۱۸ میلیون تومان برای من ارزش داشت.")

    def test_persian_script_has_a_length(self):
        a = beats.analyse(self.SCRIPT)
        self.assertEqual(a["total_words"], 34)          # 10 + 8 + 6 + 10
        self.assertGreater(a["total_seconds"], 0)

    def test_loop_found_and_stopwords_ignored(self):
        notes = " ".join(beats.analyse(self.SCRIPT)["notes"])
        self.assertIn("Loops:", notes)
        self.assertNotIn("را", notes.split("Loops:")[1].split("from the hook")[0])

    def test_warns_the_rate_is_english_unless_given(self):
        self.assertIn("English speaking rate", " ".join(beats.analyse(self.SCRIPT)["notes"]))
        self.assertNotIn("English speaking rate",
                         " ".join(beats.analyse(self.SCRIPT, wpm=150)["notes"]))

    def test_english_timing_unchanged(self):
        a = beats.analyse("I lost $18,000 because of one missing contract.\n"
                          "That one word change is worth $18,000 to me.")
        self.assertEqual(a["total_words"], 17)          # 8 + 9, "$18,000" is one
        self.assertNotIn("English speaking rate", " ".join(a["notes"]))


class Caption(unittest.TestCase):
    def test_persian_hashtags_count_against_the_cap(self):
        text = ("یک بند در قرارداد ۱۸ میلیون تومان برایم هزینه داشت.\n\n"
                "#هوش_مصنوعی #آموزش #پرامپت #چت‌جی‌پی‌تی #فریلنسر #قرارداد")
        a = caption.analyse(text)
        self.assertEqual(len(a["hashtags"]), 6)
        self.assertIn("#چت‌جی‌پی‌تی", a["hashtags"])
        status = {c["check"]: c["status"] for c in a["checks"]}
        self.assertEqual(status["HASHTAGS"], "FAIL")

    def test_one_ask_sits_out_on_persian(self):
        a = caption.analyse("کلمه پرامپت را کامنت کنید تا برایتان بفرستم.")
        status = {c["check"]: c["status"] for c in a["checks"]}
        self.assertEqual(status["ONE ASK"], "SKIP")

    def test_search_term_found_however_it_is_typed(self):
        a = caption.analyse("این آموزش هوش‌مصنوعي برای مبتدی‌هاست.", keywords=["هوش مصنوعی"])
        status = {c["check"]: c["status"] for c in a["checks"]}
        self.assertEqual(status["SEARCH TERMS"], "PASS")


class Swipe(unittest.TestCase):
    def test_persian_rows_and_digits(self):
        import tempfile
        rows = ("account\tfollowers\tmedian\tviews\thook\n"
                "@fa_ai\t۹۰۰۰\t۳۰۰۰\t۱۸۰۰۰۰\tاین پرامپت را بدزدید، دو سال طول کشید\n")
        with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(rows)
        try:
            parsed = swipe.read_rows(fh.name)
        finally:
            os.unlink(fh.name)
        a = swipe.analyse(parsed, swipe.load_formulas(swipe.HOOKS))
        reel = a["reels"][0]
        self.assertEqual(reel["outlier"], 60.0)
        self.assertEqual(reel["words"], 8)


class WindowsConsole(unittest.TestCase):
    """Persian through stdin and stdout, with no -X utf8 and no PYTHONUTF8.
    On Windows this used to come back as mojibake."""

    def test_stdin_round_trip(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
        p = subprocess.run(
            [sys.executable, "-B", os.path.join(SKILLS, "ig-human", "humanize.py"), "-", "--json"],
            input=FA_DRAFT.encode("utf-8"), capture_output=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace"))
        out = json.loads(p.stdout.decode("utf-8"))
        self.assertEqual(out["text"].strip(), FA_DRAFT)


if __name__ == "__main__":
    unittest.main()
