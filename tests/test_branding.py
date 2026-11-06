"""The installer shows the Keel Linux name, never the TurnKey name.

The commissioning test of 2026-11-06 (the WordPress ISO on a Proxmox VM
on BR1) showed "TurnKey Installer" at the top of each screen of the
installer, and the first boot that follows shows "Keel Linux - First
boot configuration". These tests hold every text that the installer
shows to the operator to the Keel Linux name: the title of each dialog,
the backtitle, the start screen, the console line of the systemd unit
and the help text of the command. The code identifiers (the package
tkl_installer, the command tkl-installer, the LVM volume group
"turnkey") are not texts of a screen and do not change.
"""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent

# ui_wrapper imports python-dialog, which runs the dialog program; a
# stand-in module lets the tests run without a terminal and record each
# call.
if "dialog" not in sys.modules:
    _stub = types.ModuleType("dialog")
    _stub.Dialog = mock.MagicMock  # type: ignore[attr-defined]
    sys.modules["dialog"] = _stub

ui_wrapper = importlib.import_module("tkl_installer.ui_wrapper")

PRODUCT = "Keel Linux"
OLD_NAME = "TurnKey"

# The files that hold the texts the operator sees: the dialogs, the
# command and its help, and the unit that systemd names on the console.
USER_VISIBLE_FILES = (
    "tkl_installer/ui_wrapper.py",
    "tkl-installer",
    "debian/tkl-installer.service",
)


def _new_ui() -> tuple[object, mock.MagicMock]:
    """Return a UI and the stand-in of its dialog.Dialog."""
    dialog_obj = mock.MagicMock()
    dialog_obj.OK = "ok"
    dialog_obj.CANCEL = "cancel"
    with mock.patch.object(
        ui_wrapper.dialog,
        "Dialog",
        return_value=dialog_obj,
    ):
        ui = ui_wrapper.UI()
    return ui, dialog_obj


class TitleTest(unittest.TestCase):
    def test_title_is_keel_linux_installer(self) -> None:
        self.assertEqual(ui_wrapper.TITLE, "Keel Linux Installer")

    def test_product_name_is_keel_linux(self) -> None:
        self.assertEqual(ui_wrapper.PRODUCT, PRODUCT)

    def test_title_agrees_with_first_boot_backtitle(self) -> None:
        # inithooks shows "Keel Linux - First boot configuration"; the
        # installer comes before it and uses the same product name.
        self.assertTrue(ui_wrapper.TITLE.startswith(PRODUCT))


class ScreenTest(unittest.TestCase):
    def test_backtitle_of_every_screen_is_the_title(self) -> None:
        _ui, d = _new_ui()
        d.set_background_title.assert_called_once_with(
            " Keel Linux Installer ",
        )

    def test_message_box_title_defaults_to_the_title(self) -> None:
        ui, d = _new_ui()
        ui.msgbox("Remove the install medium.")
        self.assertEqual(d.msgbox.call_args.kwargs["title"], ui_wrapper.TITLE)

    def test_message_box_keeps_a_given_title(self) -> None:
        ui, d = _new_ui()
        ui.msgbox("text", title="Error")
        self.assertEqual(d.msgbox.call_args.kwargs["title"], "Error")

    def test_table_title_defaults_to_the_title(self) -> None:
        ui, d = _new_ui()
        d.yesno.return_value = "ok"
        self.assertTrue(ui.show_table([("sda", "20G")], headers=("a", "b")))
        self.assertEqual(d.yesno.call_args.kwargs["title"], ui_wrapper.TITLE)

    def test_start_screen_names_keel_linux(self) -> None:
        ui, d = _new_ui()
        ui.app_start()
        text = d.infobox.call_args.args[0]
        self.assertIn("Keel Linux Live Installer", text)
        self.assertNotIn(OLD_NAME, text)


class NoTurnKeyTextTest(unittest.TestCase):
    def test_no_user_visible_file_names_turnkey(self) -> None:
        for name in USER_VISIBLE_FILES:
            with self.subTest(file=name):
                text = (REPO / name).read_text(encoding="utf-8")
                found = [
                    f"{number}: {line.strip()}"
                    for number, line in enumerate(text.splitlines(), 1)
                    if OLD_NAME.lower() in line.lower()
                ]
                self.assertEqual(found, [])

    def test_unit_description_names_keel_linux(self) -> None:
        unit = REPO / "debian/tkl-installer.service"
        lines = unit.read_text(encoding="utf-8").splitlines()
        self.assertIn("Description=tkl-installer: Keel Linux installer", lines)

    def test_command_help_names_keel_linux(self) -> None:
        script = (REPO / "tkl-installer").read_text(encoding="utf-8")
        self.assertEqual(
            script.count('"Opinionated CLI installer for Keel Linux. Also"'),
            2,
        )


if __name__ == "__main__":
    unittest.main()
