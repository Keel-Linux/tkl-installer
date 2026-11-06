"""The dialog wrapper of the installer, with a stand-in for python-dialog.

Each test gives the UI a stand-in dialog.Dialog and records what the UI
asks of it: the texts, the titles, the sizes and the answers it loops on.
No dialog program runs and no terminal is necessary.
"""

from __future__ import annotations

import contextlib
import importlib
import os
import sys
import types
import unittest
from unittest import mock

if "dialog" not in sys.modules:
    _stub = types.ModuleType("dialog")
    _stub.Dialog = mock.MagicMock  # type: ignore[attr-defined]
    sys.modules["dialog"] = _stub

ui_wrapper = importlib.import_module("tkl_installer.ui_wrapper")
runner = importlib.import_module("tkl_installer.runner")

OK = "ok"
CANCEL = "cancel"


def _new_ui() -> tuple[object, mock.MagicMock]:
    """Return a UI and the stand-in of its dialog.Dialog."""
    d = mock.MagicMock()
    d.OK = OK
    d.CANCEL = CANCEL
    with mock.patch.object(ui_wrapper.dialog, "Dialog", return_value=d):
        ui = ui_wrapper.UI()
    return ui, d


@contextlib.contextmanager
def _output(items: list[runner.CommandOutput]):  # noqa: ANN202
    """Stand in for the context managers of runner: yield ITEMS."""
    yield iter(items)


@contextlib.contextmanager
def _failing_output():  # noqa: ANN202
    """Stand in for a runner context manager whose command fails."""
    raise RuntimeError("command failed")
    yield  # pragma: no cover


class TerminalSizeTest(unittest.TestCase):
    def test_a_small_terminal_makes_the_boxes_smaller(self) -> None:
        try:
            with mock.patch.object(
                os,
                "get_terminal_size",
                return_value=os.terminal_size((40, 12)),
            ):
                small = importlib.reload(ui_wrapper)
                self.assertEqual(small._MAX_WIDTH, 40)
                self.assertEqual(small._MAX_HEIGHT, 12)
                self.assertEqual(small._MSG_HEIGHT, 10)
                self.assertEqual(small._MENU_HEIGHT, 12)
        finally:
            importlib.reload(ui_wrapper)


class FormatTableTest(unittest.TestCase):
    def test_no_rows_is_empty(self) -> None:
        self.assertEqual(ui_wrapper._format_table([]), "")

    def test_header_gets_a_rule_and_columns_are_padded(self) -> None:
        text = ui_wrapper._format_table(
            [("sda", "20G")],
            headers=("Disk", "Size"),
            max_width=20,
        )
        lines = text.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("Disk"))
        self.assertEqual(set(lines[1]), {"-"})
        self.assertTrue(lines[2].startswith("sda"))

    def test_wide_rows_get_no_extra_space(self) -> None:
        text = ui_wrapper._format_table([("a" * 30, "b" * 30)], max_width=20)
        self.assertEqual(text, "a" * 30 + "   " + "b" * 30)


class FatalTest(unittest.TestCase):
    def test_module_fatal_shows_the_error_and_exits(self) -> None:
        d = mock.MagicMock()
        with (
            mock.patch.object(ui_wrapper.dialog, "Dialog", return_value=d),
            self.assertRaises(SystemExit) as caught,
        ):
            ui_wrapper.fatal("no disk", 3)
        self.assertEqual(caught.exception.code, 3)
        self.assertIn("no disk", d.msgbox.call_args.args[0])
        self.assertEqual(d.msgbox.call_args.kwargs["title"], "Fatal Error")

    def test_cancel_exits_with_zero(self) -> None:
        ui, d = _new_ui()
        d.menu.return_value = (CANCEL, "")
        with self.assertRaises(SystemExit) as caught:
            ui.choose("Scheme?", [("guided", "Guided")])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("Cancelled by user.", d.msgbox.call_args.args[0])


class BoxTest(unittest.TestCase):
    def test_infobox_shows_the_text(self) -> None:
        ui, d = _new_ui()
        ui.infobox("Partitioning")
        d.infobox.assert_called_once_with(
            "Partitioning",
            width=ui_wrapper._MAX_WIDTH,
        )

    def test_confirm_yes_and_no(self) -> None:
        ui, d = _new_ui()
        d.yesno.return_value = OK
        self.assertTrue(ui.confirm("Erase the disk?"))
        self.assertFalse(d.yesno.call_args.kwargs["defaultno"])
        d.yesno.return_value = CANCEL
        self.assertFalse(ui.confirm("Erase the disk?", default=False))
        self.assertTrue(d.yesno.call_args.kwargs["defaultno"])

    def test_show_table_with_a_footer_and_no(self) -> None:
        ui, d = _new_ui()
        d.yesno.return_value = CANCEL
        self.assertFalse(
            ui.show_table([("a", "b")], title="Disks", footer="Note"),
        )
        self.assertTrue(d.yesno.call_args.args[0].endswith("\nNote"))
        self.assertEqual(d.yesno.call_args.kwargs["title"], "Disks")

    def test_log_only_messages_show_no_box(self) -> None:
        ui, d = _new_ui()
        ui.step("a")
        ui.ok("b")
        ui.info("c")
        d.msgbox.assert_not_called()
        d.infobox.assert_not_called()

    def test_warning_and_error_show_a_box(self) -> None:
        ui, d = _new_ui()
        ui.warn("low space")
        self.assertEqual(d.msgbox.call_args.kwargs["title"], "Warning")
        ui.error("no space")
        self.assertEqual(d.msgbox.call_args.kwargs["title"], "Error")

    def test_header_shows_the_stage(self) -> None:
        ui, d = _new_ui()
        ui.header("Install")
        self.assertIn("Stage: Install", d.infobox.call_args.args[0])


class PromptTest(unittest.TestCase):
    def test_prompt_without_validator_strips(self) -> None:
        ui, d = _new_ui()
        d.inputbox.return_value = (OK, "  web  ")
        self.assertEqual(ui.prompt("Name?", default="x"), "web")
        self.assertEqual(d.inputbox.call_args.kwargs["init"], "x")

    def test_prompt_loops_until_valid(self) -> None:
        ui, d = _new_ui()
        d.inputbox.side_effect = [(OK, "bad"), (OK, "good")]
        value = ui.prompt(
            "Name?",
            validator=lambda v: (v == "good", "not good"),
        )
        self.assertEqual(value, "good")
        self.assertIn("not good", d.msgbox.call_args.args[0])

    def test_prompt_cancel_exits(self) -> None:
        ui, d = _new_ui()
        d.inputbox.return_value = (CANCEL, "")
        with self.assertRaises(SystemExit):
            ui.prompt("Name?")

    def test_size_units(self) -> None:
        ui, d = _new_ui()
        for raw, size in (
            ("1T", 1024 * 1024),
            ("4G", 4096),
            ("512M", 512),
            ("100", 100),
        ):
            with self.subTest(raw=raw):
                d.inputbox.side_effect = [(OK, raw)]
                self.assertEqual(ui.prompt_size_mb("Swap?", 512), size)

    def test_size_errors_then_a_good_size(self) -> None:
        ui, d = _new_ui()
        d.inputbox.side_effect = [
            (OK, "lots"),
            (OK, "8G"),
            (OK, "0.0001"),
            (OK, "1G"),
        ]
        self.assertEqual(ui.prompt_size_mb("Swap?", 512, max_size=2048), 1024)
        errors = [c.args[0] for c in d.msgbox.call_args_list]
        self.assertIn("plain number", errors[0])
        self.assertIn("Maximum size allowed", errors[1])
        self.assertIn("at least 1 MiB", errors[2])
        self.assertIn("less than", d.inputbox.call_args.args[0])


class SizesFormTest(unittest.TestCase):
    PARTS = [
        ("EFI", "vfat", "/boot/efi", 512),
        ("swap", "swap", "", 1024),
    ]

    def test_form_returns_the_sizes(self) -> None:
        ui, d = _new_ui()
        d.mixedform.return_value = (OK, ["1G", "2T"])
        self.assertEqual(
            ui.prompt_sizes_mb(self.PARTS, 4096),
            [1024, 2 * 1024 * 1024],
        )
        self.assertEqual(d.mixedform.call_args.kwargs["title"], ui_wrapper.TITLE)

    def test_form_back_is_none(self) -> None:
        ui, d = _new_ui()
        d.mixedform.return_value = (CANCEL, [])
        self.assertIsNone(ui.prompt_sizes_mb(self.PARTS, 4096))

    def test_form_shows_errors_and_asks_again(self) -> None:
        ui, d = _new_ui()
        d.mixedform.side_effect = [
            (OK, ["junk", "0"]),
            (OK, ["300", "600M"]),
        ]
        self.assertEqual(ui.prompt_sizes_mb(self.PARTS, 4096), [300, 600])
        text = d.msgbox.call_args.args[0]
        self.assertIn("EFI: Enter sizes", text)
        self.assertIn("swap: Size must be at least 1 MiB.", text)


class MenuTest(unittest.TestCase):
    def test_choose_returns_the_tag(self) -> None:
        ui, d = _new_ui()
        d.menu.return_value = (OK, "lvm")
        tag = ui.choose("Scheme?", [("guided", "a"), ("lvm", "b")], default=1)
        self.assertEqual(tag, "lvm")
        self.assertEqual(d.menu.call_args.kwargs["default_item"], "lvm")

    def test_choose_from_list_uses_the_items_as_tags(self) -> None:
        ui, d = _new_ui()
        d.menu.return_value = (OK, "sdb")
        self.assertEqual(ui.choose_from_list("Disk?", ["sda", "sdb"]), "sdb")
        self.assertEqual(
            d.menu.call_args.kwargs["choices"],
            [("sda", ""), ("sdb", "")],
        )


class PleaseWaitTest(unittest.TestCase):
    def test_success(self) -> None:
        ui, d = _new_ui()
        with ui.please_wait("Formatting"):
            pass
        self.assertIn("Formatting", d.infobox.call_args.args[0])
        d.msgbox.assert_not_called()

    def test_failure_shows_the_step_and_raises(self) -> None:
        ui, d = _new_ui()
        with self.assertRaises(ValueError), ui.please_wait("Formatting"):
            raise ValueError
        self.assertIn("'Formatting' failed", d.msgbox.call_args.args[0])


class ProgressTest(unittest.TestCase):
    def test_gauge_follows_percent_and_lines(self) -> None:
        ui, d = _new_ui()
        ui.progress(
            iter(
                [
                    runner.CommandOutput(line="a", percent=None),
                    runner.CommandOutput(line="b", percent=50),
                    runner.CommandOutput(line="", percent=75),
                    runner.CommandOutput(line="", percent=None),
                ],
            ),
            title="Copy",
        )
        d.gauge_start.assert_called_once()
        updates = [c.args[0] for c in d.gauge_update.call_args_list]
        self.assertEqual(updates, [0, 50, 75])
        d.gauge_stop.assert_called_once()

    def test_gauge_stops_on_an_error(self) -> None:
        ui, d = _new_ui()

        def broken():  # noqa: ANN202
            yield runner.CommandOutput(line="a", percent=None)
            raise RuntimeError

        with self.assertRaises(RuntimeError):
            ui.progress(broken())
        d.gauge_stop.assert_called_once()

    def test_apt_get_actions(self) -> None:
        ui, d = _new_ui()
        for command, title in (
            ("install", "Installing Packages"),
            ("REMOVE", "Removing Packages"),
            ("purge", "Purging Packages"),
        ):
            with (
                self.subTest(command=command),
                mock.patch.object(
                    ui_wrapper,
                    "run_apt_progress",
                    return_value=_output([]),
                ),
            ):
                self.assertIsNone(ui.progress_apt_get(["x"], command))
                self.assertEqual(
                    d.gauge_start.call_args.kwargs["title"],
                    title,
                )

    def test_apt_get_unknown_command_is_fatal(self) -> None:
        ui, _d = _new_ui()
        with (
            mock.patch.object(ui_wrapper.dialog, "Dialog"),
            self.assertRaises(SystemExit) as caught,
        ):
            ui.progress_apt_get(["x"], "upgrade")
        self.assertEqual(caught.exception.code, 999)

    def test_apt_get_failure_raises(self) -> None:
        ui, _d = _new_ui()
        with (
            mock.patch.object(
                ui_wrapper,
                "run_apt_progress",
                return_value=_failing_output(),
            ),
            self.assertRaises(RuntimeError),
        ):
            ui.progress_apt_get(["x"], "install")

    def test_unsquashfs(self) -> None:
        ui, d = _new_ui()
        with mock.patch.object(
            ui_wrapper,
            "run_unsquashfs_progress",
            return_value=_output([]),
        ):
            self.assertIsNone(ui.progress_unsquashfs("fs.squashfs", "/t"))
        self.assertEqual(
            d.gauge_start.call_args.kwargs["title"],
            "Extracting Filesystem",
        )
        with (
            mock.patch.object(
                ui_wrapper,
                "run_unsquashfs_progress",
                return_value=_failing_output(),
            ),
            self.assertRaises(RuntimeError),
        ):
            ui.progress_unsquashfs("fs.squashfs", "/t")

    def test_command(self) -> None:
        ui, d = _new_ui()
        with mock.patch.object(
            ui_wrapper,
            "run_command_progress",
            return_value=_output([]),
        ):
            self.assertIsNone(ui.progress_command(["true"], title="Grub"))
        self.assertEqual(d.gauge_start.call_args.kwargs["title"], "Grub")
        with (
            mock.patch.object(
                ui_wrapper,
                "run_command_progress",
                return_value=_failing_output(),
            ),
            self.assertRaises(RuntimeError),
        ):
            ui.progress_command(["false"])


if __name__ == "__main__":
    unittest.main()
