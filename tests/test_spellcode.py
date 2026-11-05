"""spellcode 的测试。

跑法：python -m unittest discover -s tests

# spell:ignore-file
这个文件里到处都是故意写错的词，作为检查器的语料，不该被自己报出来。
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import spellcode  # noqa: E402


# ---------------------------------------------------------------------------
# 拆词
# ---------------------------------------------------------------------------

class TestSplitIdentifier(unittest.TestCase):
    def words(self, ident):
        return [w for w, _, _ in spellcode.split_identifier(ident)]

    def test_snake_case(self):
        self.assertEqual(self.words("recieve_payload"), ["recieve", "payload"])

    def test_camel_case(self):
        self.assertEqual(self.words("recievePayload"), ["recieve", "Payload"])

    def test_pascal_case(self):
        self.assertEqual(self.words("RecievePayload"), ["Recieve", "Payload"])

    def test_screaming_snake(self):
        self.assertEqual(self.words("MAX_LENGHT"), ["MAX", "LENGHT"])

    def test_digit_boundary(self):
        self.assertEqual(self.words("utf8_decode"), ["utf", "8", "decode"])

    def test_acronym_kept_whole(self):
        # HTMLParser 不能被切成 H / T / M / L / Parser
        self.assertEqual(self.words("HTMLParser"), ["HTML", "Parser"])

    def test_acronym_then_digit(self):
        self.assertEqual(self.words("First10HTMLTokens"), ["First", "10", "HTML", "Tokens"])

    def test_leading_and_trailing_underscore(self):
        self.assertEqual(self.words("_private_value_"), ["private", "value"])

    def test_offsets_are_absolute(self):
        out = spellcode.split_identifier("ok_recieve_more")
        self.assertEqual(out[1], ("recieve", 3, 10))

    def test_empty(self):
        self.assertEqual(self.words(""), [])

    def test_double_underscore(self):
        self.assertEqual(self.words("a__b"), ["a", "b"])


# ---------------------------------------------------------------------------
# 不像词的标识符
# ---------------------------------------------------------------------------

class TestIsOpaque(unittest.TestCase):
    def test_too_short(self):
        self.assertTrue(spellcode.is_opaque("ab"))

    def test_digits_only(self):
        self.assertTrue(spellcode.is_opaque("12345"))

    def test_hex_with_digit(self):
        self.assertTrue(spellcode.is_opaque("deadbeef12"))

    def test_go_mod_pseudo_version_hash(self):
        # go.mod 伪版本号里的 9ba8df137936 不能被拆成 ba
        self.assertTrue(spellcode.is_opaque("9ba8df137936"))

    def test_no_vowel(self):
        self.assertTrue(spellcode.is_opaque("xkcdwrt"))

    def test_long_token(self):
        self.assertTrue(spellcode.is_opaque("a" * 24))

    def test_normal_word_is_not_opaque(self):
        self.assertFalse(spellcode.is_opaque("recieve"))

    def test_snake_case_is_not_opaque(self):
        self.assertFalse(spellcode.is_opaque("recieve_payload"))

    def test_acronym_without_vowel_is_skipped(self):
        # HTTP 没有元音，按「不像词」处理；宁可漏掉，也不把缩写当错拼
        self.assertTrue(spellcode.is_opaque("HTTP"))


# ---------------------------------------------------------------------------
# 大小写跟随
# ---------------------------------------------------------------------------

class TestCaseLike(unittest.TestCase):
    def test_lower(self):
        self.assertEqual(spellcode.case_like("recieve", "receive"), "receive")

    def test_title(self):
        self.assertEqual(spellcode.case_like("Recieve", "receive"), "Receive")

    def test_upper(self):
        self.assertEqual(spellcode.case_like("RECIEVE", "receive"), "RECEIVE")

    def test_single_char_source(self):
        self.assertEqual(spellcode.case_like("R", "receive"), "receive")


# ---------------------------------------------------------------------------
# 查词
# ---------------------------------------------------------------------------

class TestLookup(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(spellcode.lookup("recieve"), "receive")

    def test_plural_suffix_keeps_s(self):
        # seperators 只命中词干 seperator，后缀原样带回
        self.assertEqual(spellcode.lookup("seperators"), "separators")

    def test_ed_suffix(self):
        self.assertEqual(spellcode.lookup("supressed"), "suppressed")

    def test_ing_suffix(self):
        self.assertEqual(spellcode.lookup("supressing"), "suppressing")

    def test_exact_inflected_form_wins(self):
        self.assertEqual(spellcode.lookup("recieved"), "received")

    def test_short_word_never_looked_up(self):
        # 两字母的 ba 不该被当成词
        self.assertIsNone(spellcode.lookup("ba"))

    def test_valid_word_that_is_prefix_of_typo_target(self):
        # standard 是正确拼写，不能因为 standar -> standard 而被报
        self.assertIsNone(spellcode.lookup("standard"))

    def test_unknown_word(self):
        self.assertIsNone(spellcode.lookup("kubernetes"))

    def test_case_insensitive(self):
        self.assertEqual(spellcode.lookup("Recieve"), "receive")


# ---------------------------------------------------------------------------
# 单行检查
# ---------------------------------------------------------------------------

class TestCheckLine(unittest.TestCase):
    def findings(self, line):
        return spellcode.check_line(line, 1, "x.py")

    def test_finds_typo_in_comment(self):
        out = self.findings("# we recieve data")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].word, "recieve")
        self.assertEqual(out[0].suggestion, "receive")

    def test_column_points_at_word(self):
        out = self.findings("# we recieve data")
        self.assertEqual(out[0].col, 6)

    def test_finds_typo_in_identifier(self):
        out = self.findings("def recieve_payload():")
        self.assertEqual(out[0].word, "recieve")

    def test_two_typos_on_one_line(self):
        out = self.findings("# recieve the seperate value")
        self.assertEqual([f.word for f in out], ["recieve", "seperate"])

    def test_no_finding_for_clean_line(self):
        self.assertEqual(self.findings("def calculate_total(items):"), [])

    def test_ignore_directive_silences_line(self):
        self.assertEqual(self.findings('x = "recieve"  # spell:ignore'), [])

    def test_ignore_specific_words(self):
        self.assertEqual(self.findings('# recieve  # spell:ignore=recieve'), [])

    def test_ignore_specific_words_leaves_others(self):
        out = self.findings('# recieve seperate  # spell:ignore=recieve')
        self.assertEqual([f.word for f in out], ["seperate"])

    def test_url_is_not_checked(self):
        self.assertEqual(self.findings('u = "https://x.com/seperate/guide"'), [])

    def test_email_is_not_checked(self):
        self.assertEqual(self.findings('mail = "seperate@example.com"'), [])

    def test_semver_is_not_checked(self):
        self.assertEqual(self.findings('v = "v2.1.3"'), [])

    def test_uuid_is_not_checked(self):
        self.assertEqual(
            self.findings('i = "9ba8df13-7936-4a0b-8c1d-2e3f4a5b6c7d"'), [])

    def test_hash_token_is_not_checked(self):
        # FhDomw6BaHU 里的 Ba 是哈希片段，不是词
        self.assertEqual(self.findings('YT = "FhDomw6BaHU"'), [])

    def test_go_mod_hash_is_not_checked(self):
        line = "github.com/x/y v0.0.0-20220510233725-9ba8df137936 // indirect"
        self.assertEqual(self.findings(line), [])

    def test_plural_of_valid_word_is_not_flagged(self):
        # DELETEs 不该被报成 DELET
        self.assertEqual(self.findings("WHEN a user DELETEs /thing"), [])

    def test_three_letter_acronym_is_skipped(self):
        # 阿拉伯字母名 TEH 不是错拼
        self.assertEqual(self.findings("# ARABIC LETTER TEH MARBUTA"), [])

    def test_acronym_inside_base64_is_skipped(self):
        self.assertEqual(self.findings("9tfeE8tTEH6KRtGX+rcuKxGrkLAngPno"), [])

    def test_very_long_line_is_skipped(self):
        self.assertEqual(self.findings("# recieve " + "x" * 2100), [])

    def test_uppercase_typo_is_reported_with_uppercase_fix(self):
        out = self.findings("# RECIEVE DATA")
        self.assertEqual(out[0].suggestion, "RECEIVE")

    def test_title_case_typo_is_reported_with_title_fix(self):
        out = self.findings("# Recieve data")
        self.assertEqual(out[0].suggestion, "Receive")

    def test_span_covers_whole_word(self):
        out = self.findings("# seperators data")
        start, end = out[0].span
        self.assertEqual(end - start, len("seperators"))
        self.assertEqual(out[0].suggestion, "separators")


# ---------------------------------------------------------------------------
# 整段文本
# ---------------------------------------------------------------------------

class TestCheckText(unittest.TestCase):
    def test_ignore_file_directive(self):
        text = "# spell:ignore-file\nrecieve seperate\n"
        self.assertEqual(spellcode.check_text(text, "a.py"), [])

    def test_ignore_next_line(self):
        text = "# spell:ignore-next-line\nrecieve\n"
        self.assertEqual(spellcode.check_text(text, "a.py"), [])

    def test_ignore_next_line_only_skips_one(self):
        text = "# spell:ignore-next-line\nrecieve\nseperate\n"
        out = spellcode.check_text(text, "a.py")
        self.assertEqual([f.word for f in out], ["seperate"])

    def test_line_numbers_are_one_based(self):
        text = "ok\nok\nrecieve\n"
        self.assertEqual(spellcode.check_text(text, "a.py")[0].line, 3)

    def test_multiple_lines(self):
        text = "recieve\nok\nseperate\n"
        out = spellcode.check_text(text, "a.py")
        self.assertEqual([(f.line, f.word) for f in out], [(1, "recieve"), (3, "seperate")])


# ---------------------------------------------------------------------------
# 修正
# ---------------------------------------------------------------------------

class TestFixText(unittest.TestCase):
    def fix(self, text):
        return spellcode.fix_text(text, spellcode.check_text(text, "a.py"))

    def test_single_fix(self):
        self.assertEqual(self.fix("# recieve\n"), "# receive\n")

    def test_two_fixes_on_same_line(self):
        self.assertEqual(self.fix("# recieve seperate\n"), "# receive separate\n")

    def test_fix_keeps_plural(self):
        # 回归：曾经把 recieves 改成 receivees
        self.assertEqual(self.fix("# recieves\n"), "# receives\n")

    def test_fix_keeps_uppercase(self):
        self.assertEqual(self.fix("# RECIEVE\n"), "# RECEIVE\n")

    def test_fix_keeps_indentation(self):
        self.assertEqual(self.fix("    recieve = 1\n"), "    receive = 1\n")

    def test_fix_in_identifier(self):
        self.assertEqual(self.fix("def recieve_payload():\n"), "def receive_payload():\n")

    def test_fix_does_not_touch_ignored_line(self):
        text = '# recieve  # spell:ignore\n'
        self.assertEqual(self.fix(text), text)

    def test_fix_preserves_crlf(self):
        self.assertEqual(self.fix("recieve\r\n"), "receive\r\n")

    def test_fix_multiple_lines(self):
        self.assertEqual(self.fix("recieve\nseperate\n"), "receive\nseparate\n")


# ---------------------------------------------------------------------------
# 文件筛选与读取
# ---------------------------------------------------------------------------

class TestFileSelection(unittest.TestCase):
    def test_lockfile_is_skipped(self):
        self.assertFalse(spellcode._is_scannable("package-lock.json", ()))

    def test_binary_extension_is_skipped(self):
        self.assertFalse(spellcode._is_scannable("logo.png", ()))

    def test_minified_is_skipped(self):
        self.assertFalse(spellcode._is_scannable("app.min.js", ()))

    def test_normal_source_is_scanned(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
            fh.write("x = 1\n")
            path = fh.name
        try:
            self.assertTrue(spellcode._is_scannable(path, ()))
        finally:
            os.unlink(path)

    def test_extra_skip_pattern(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
            fh.write("x = 1\n")
            path = fh.name
        try:
            self.assertFalse(spellcode._is_scannable(path, ("Temp",)))
        finally:
            os.unlink(path)

    def test_read_text_binary_returns_none(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".bin", delete=False) as fh:
            fh.write(b"abc\x00def")
            path = fh.name
        try:
            self.assertIsNone(spellcode.read_text(path))
        finally:
            os.unlink(path)

    def test_read_text_utf8(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".py", delete=False) as fh:
            fh.write("中文 recieve\n".encode("utf-8"))
            path = fh.name
        try:
            self.assertEqual(spellcode.read_text(path), "中文 recieve\n")
        finally:
            os.unlink(path)

    def test_walk_skips_git_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, ".git"))
            with open(os.path.join(tmp, ".git", "config"), "w", encoding="utf-8") as fh:
                fh.write("recieve\n")
            with open(os.path.join(tmp, "a.py"), "w", encoding="utf-8") as fh:
                fh.write("recieve\n")
            files = list(spellcode.iter_files([tmp]))
            self.assertEqual(len(files), 1)
            self.assertTrue(files[0].endswith("a.py"))


# ---------------------------------------------------------------------------
# 召回：40 个真实场景里埋的错拼，一个都不能漏
# ---------------------------------------------------------------------------

RECALL_CASES = [
    ('# recieve the response first', "recieve", "receive"),
    ('def seperate_items(rows):', "seperate", "separate"),
    ("MAX_LENGHT = 100", "LENGHT", "LENGTH"),
    ('msg = "occured while parsing"', "occured", "occurred"),
    ('if enviornment == "prod":', "enviornment", "environment"),
    ('logger.info("retreive failed")', "retreive", "retrieve"),
    ("class Configuartion:", "Configuartion", "Configuration"),
    ("# the arguement is optional", "arguement", "argument"),
    ("total = calcualte(items)", "calcualte", "calculate"),
    ("return resposne.json()", "resposne", "response"),
    ("PRINT_DEBUG_MESSSAGE = True", "MESSSAGE", "MESSAGE"),
    ("# 这一步 seperates 两个阶段", "seperates", "separates"),
    ("    begining = cursor", "begining", "beginning"),
    ("# check the threshhold value", "threshhold", "threshold"),
    ("def handle_request(req):", None, None),
    ("for i in indicies:", "indicies", "indices"),
    ("# this is neccessary", "neccessary", "necessary"),
    ("assert value is not flase", "flase", "false"),
    ("# commited by mistake", "commited", "committed"),
    ("if lenght > 0:", "lenght", "length"),
    ("# the paramater is ignored", "paramater", "parameter"),
    ("retrun_value = 1", "retrun", "return"),
    ("# dependancy graph", "dependancy", "dependency"),
    ("def get_identifer(node):", "identifer", "identifier"),
    ("# serialze to bytes", "serialze", "serialize"),
    ("# a lot of things happen here", None, None),
    ("width = calcualted_width", "calcualted", "calculated"),
    ("# explicite ordering", "explicite", "explicit"),
    ("def intialize(self):", "intialize", "initialize"),
    ("# the messsage queue", "messsage", "message"),
    ("result = evalute(expr)", "evalute", "evaluate"),
    ("# overide the default", "overide", "override"),
    ("# this is truely async", "truely", "truly"),
    ("varable = None", "varable", "variable"),
    ("# compatability layer", "compatability", "compatibility"),
    ("# minimun size is 8", "minimun", "minimum"),
    ("# sent thru the proxy", None, None),
    ("# the answer is obviuos", "obviuos", "obvious"),
    ("# cancelation policy", "cancelation", "cancellation"),
    ("# deserialze the payload", "deserialze", "deserialize"),
]


class TestRecall(unittest.TestCase):
    def test_known_typos_are_all_found(self):
        missed = []
        for line, expected_word, _ in RECALL_CASES:
            found = {f.word for f in spellcode.check_line(line, 1, "x.py")}
            if expected_word and expected_word not in found:
                missed.append((line, expected_word, sorted(found)))
        self.assertEqual(missed, [], f"漏报 {len(missed)} 处")

    def test_corrections_are_right(self):
        wrong = []
        for line, expected_word, expected_fix in RECALL_CASES:
            if not expected_fix:
                continue
            got = {f.word: f.suggestion for f in spellcode.check_line(line, 1, "x.py")}
            if got.get(expected_word) != expected_fix:
                wrong.append((line, expected_word, got.get(expected_word), expected_fix))
        self.assertEqual(wrong, [], f"改错 {len(wrong)} 处")


# ---------------------------------------------------------------------------
# 命令行
# ---------------------------------------------------------------------------

class TestCli(unittest.TestCase):
    def run_cli(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(io.StringIO()):
            code = spellcode.main(argv)
        return code, buf.getvalue()

    def test_clean_tree_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.py"), "w", encoding="utf-8") as fh:
                fh.write("value = 1\n")
            code, out = self.run_cli([tmp])
            self.assertEqual(code, 0)
            self.assertIn("没有发现问题", out)

    def test_findings_exit_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.py"), "w", encoding="utf-8") as fh:
                fh.write("# recieve\n")
            code, out = self.run_cli([tmp])
            self.assertEqual(code, 2)
            self.assertIn("recieve -> receive", out)

    def test_missing_path_exits_one(self):
        code, _ = self.run_cli(["definitely-not-here-12345"])
        self.assertEqual(code, 1)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.py"), "w", encoding="utf-8") as fh:
                fh.write("# recieve\n")
            code, out = self.run_cli(["--json", tmp])
            self.assertEqual(code, 2)
            row = json.loads(out.strip().splitlines()[0])
            self.assertEqual(row["word"], "recieve")
            self.assertEqual(row["suggestion"], "receive")
            self.assertEqual(row["line"], 1)

    def test_fix_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("# recieve\n")
            code, _ = self.run_cli(["--fix", tmp])
            self.assertEqual(code, 0)
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "# receive\n")

    def test_fix_then_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("# recieve\n")
            self.run_cli(["--fix", tmp])
            code, _ = self.run_cli([tmp])
            self.assertEqual(code, 0)

    def test_quiet_prints_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.py"), "w", encoding="utf-8") as fh:
                fh.write("# recieve\n")
            code, out = self.run_cli(["--quiet", tmp])
            self.assertEqual(code, 2)
            self.assertEqual(out.strip(), "")

    def test_stat_only_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.py"), "w", encoding="utf-8") as fh:
                fh.write("# recieve\n")
            code, out = self.run_cli(["--stat", tmp])
            self.assertEqual(code, 2)
            self.assertNotIn("->", out)
            self.assertIn("1 处", out)

    def test_skip_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "skipme.py"), "w", encoding="utf-8") as fh:
                fh.write("# recieve\n")
            code, _ = self.run_cli(["--skip", "skipme", tmp])
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
