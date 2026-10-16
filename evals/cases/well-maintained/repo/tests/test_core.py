import contextlib
import io
import unittest

from slugkit import MAX_TITLE_LENGTH, slugify
from slugkit.__main__ import main


class SlugifyTests(unittest.TestCase):
    def test_words_are_lowercased_and_joined_by_single_hyphens(self):
        self.assertEqual(slugify("  Hello,   World!  "), "hello-world")

    def test_accents_are_transliterated(self):
        self.assertEqual(slugify("Café Ñandú"), "cafe-nandu")

    def test_letters_without_ascii_transliteration_are_dropped(self):
        self.assertEqual(slugify("Москва 2026"), "2026")
        self.assertEqual(slugify("Ørsted Straße Łódź"), "rsted-strae-odz")
        with self.assertRaises(ValueError):
            slugify("Москва")

    def test_title_at_the_length_limit_is_accepted(self):
        self.assertEqual(slugify("a" * MAX_TITLE_LENGTH), "a" * MAX_TITLE_LENGTH)

    def test_title_over_the_length_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            slugify("a" * (MAX_TITLE_LENGTH + 1))

    def test_titles_without_letters_or_digits_are_rejected(self):
        for title in ("", "!!!", "—"):
            with self.subTest(title=title), self.assertRaises(ValueError):
                slugify(title)

    def test_non_strings_are_rejected(self):
        with self.assertRaises(TypeError):
            slugify(None)


class CommandLineTests(unittest.TestCase):
    def test_prints_the_slug(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["Hello World"]), 0)
        self.assertEqual(output.getvalue(), "hello-world\n")

    def test_title_starting_with_a_hyphen_follows_a_double_dash(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["--", "-30%"]), 0)
        self.assertEqual(output.getvalue(), "30\n")

    def test_invalid_title_exits_with_status_2(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["!!!"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
