import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from pluginhost import config_loader, hooks
from pluginhost.__main__ import main
from pluginhost.loader import PluginError, discover
from pluginhost.settings import read

GOOD = "def run(context):\n    context['ran'] = True\n    return 'ok'\n"
BROKEN = "raise RuntimeError('broken')\n"


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
        self.assertEqual(settings.plugin_dir, Path("plugins"))

    def test_the_plugin_directory_comes_from_the_file(self):
        self.assertEqual(read(self.config).plugin_dir, self.plugins)

    def test_a_plugin_directory_that_is_not_a_string_is_rejected(self):
        self.config.write_text("plugin_dir = 3\n")
        with self.assertRaises(ValueError):
            read(self.config)


class ConfigLoaderTests(WithPlugins):
    def test_a_missing_file_is_an_empty_dictionary(self):
        self.assertEqual(config_loader.load(self.root / "missing.toml"), {})

    def test_the_file_is_returned_as_it_is(self):
        self.write_config('hooks = ["audit"]\n')
        self.assertEqual(config_loader.load(self.config)["hooks"], ["audit"])


class DiscoverTests(WithPlugins):
    def test_plugins_are_found_by_file_name(self):
        self.add("beta")
        self.add("alpha")
        (self.plugins / "notes.txt").write_text("not a plugin")
        self.assertEqual(sorted(discover(read(self.config))), ["alpha", "beta"])

    def test_a_plugin_is_imported_when_it_runs_not_when_it_is_found(self):
        self.add("broken", BROKEN)
        plugin = discover(read(self.config))["broken"]
        with self.assertRaises(PluginError):
            plugin.run({})

    def test_a_plugin_returns_its_result(self):
        self.add("alpha")
        context = {}
        self.assertEqual(discover(read(self.config))["alpha"].run(context), "ok")
        self.assertTrue(context["ran"])


class HookTests(WithPlugins):
    def test_hooks_run_in_the_configured_order_before_the_plugin(self):
        self.add("audit", "def run(context):\n    context['order'] = context.get('order', '') + 'a'\n")
        self.write_config('hooks = ["audit", "audit"]\n')
        context = {}
        hooks.run_before(self.config, discover(read(self.config)), context)
        self.assertEqual(context["order"], "aa")

    def test_a_hook_that_is_not_a_plugin_is_an_error(self):
        self.write_config('hooks = ["missing"]\n')
        with self.assertRaises(PluginError):
            hooks.run_before(self.config, discover(read(self.config)), {})


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

    def test_a_failing_plugin_exits_with_1_and_names_it(self):
        self.add("broken", "def run(context):\n    raise ValueError('bad')\n")
        code, _, err = self.command("run", "broken")
        self.assertEqual(code, 1)
        self.assertIn("broken failed: bad", err)

    def test_an_unknown_plugin_exits_with_2(self):
        self.assertEqual(self.command("run", "nothing")[0], 2)


if __name__ == "__main__":
    unittest.main()
