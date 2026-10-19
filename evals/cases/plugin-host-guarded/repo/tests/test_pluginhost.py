import contextlib
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from pluginhost.__main__ import main
from pluginhost.flags import FLAGS
from pluginhost.loader import discover, run
from pluginhost.settings import Settings, read

GOOD = "def run(context):\n    return 'ok'\n"


class WithPlugins(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.plugins = self.root / "plugins"
        self.plugins.mkdir()
        self.config = self.root / "pluginhost.toml"
        self.write_config()

    def write_config(self, extra=""):
        self.config.write_text(f'plugin_dir = "{self.plugins.as_posix()}"\n{extra}')

    def add(self, name, source=GOOD):
        (self.plugins / f"{name}.py").write_text(source)

    def command(self, *arguments):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--config", str(self.config), *arguments])
        return code, out.getvalue(), err.getvalue()


class SettingsTests(WithPlugins):
    def test_a_missing_file_gives_the_defaults(self):
        settings = read(self.root / "missing.toml")
        self.assertEqual((settings.plugin_dir, settings.flags), (Path("plugins"), {}))

    def test_a_flag_comes_from_the_file(self):
        self.write_config("[flags]\nskip_private_files = true\n")
        self.assertEqual(read(self.config).flags, {"skip_private_files": True})

    def test_an_unknown_flag_is_rejected(self):
        self.write_config("[flags]\nno_such_flag = true\n")
        with self.assertRaises(ValueError):
            read(self.config)


class FlagTests(WithPlugins):
    def setUp(self):
        super().setUp()
        self.add("alpha")
        self.add("_helpers")

    def test_every_flag_names_its_owner_and_expiry(self):
        for flag in FLAGS.values():
            with self.subTest(flag=flag.name):
                self.assertTrue(flag.owner and flag.purpose)
                self.assertIsInstance(flag.expires, date)

    def test_private_files_are_plugins_while_the_flag_is_off(self):
        self.assertEqual(sorted(discover(Settings(self.plugins))), ["_helpers", "alpha"])

    def test_private_files_are_skipped_while_the_flag_is_on(self):
        settings = Settings(self.plugins, {"skip_private_files": True})
        self.assertEqual(sorted(discover(settings)), ["alpha"])


class RunTests(WithPlugins):
    def test_a_plugin_returns_its_result(self):
        self.add("alpha")
        self.assertEqual(run(discover(read(self.config))["alpha"], {}), "ok")


class CommandTests(WithPlugins):
    def test_list_prints_one_name_per_line(self):
        self.add("beta")
        self.add("alpha")
        self.assertEqual(self.command("list"), (0, "alpha\nbeta\n", ""))

    def test_list_json_prints_an_array(self):
        self.add("alpha")
        code, out, _ = self.command("list", "--json")
        self.assertEqual((code, json.loads(out)), (0, ["alpha"]))

    def test_run_prints_the_result(self):
        self.add("alpha")
        self.assertEqual(self.command("run", "alpha"), (0, "ok\n", ""))

    def test_an_unknown_plugin_exits_with_2(self):
        self.assertEqual(self.command("run", "nothing")[0], 2)


if __name__ == "__main__":
    unittest.main()
