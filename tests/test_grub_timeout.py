"""The GRUB steps on a slow disk, and the error a failed step shows.

The web ISO failed on BR2 (2026-11-09) with "Step 'Installing GRUB
bootloader...' failed" while the host was busy: the chroot commands had a
hard timeout of 120 seconds, and the screen said nothing of why. These tests
need no disk and no dialog program.
"""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from unittest import mock

if "dialog" not in sys.modules:
    _stub = types.ModuleType("dialog")
    _stub.Dialog = mock.MagicMock  # type: ignore[attr-defined]
    sys.modules["dialog"] = _stub

installer = importlib.import_module("tkl_installer.installer")
runner = importlib.import_module("tkl_installer.runner")
ui_wrapper = importlib.import_module("tkl_installer.ui_wrapper")


def _timeouts(call) -> list[int | None]:  # noqa: ANN001
    """The timeout of each run() call that ran a chroot command."""
    return [c.kwargs.get("timeout") for c in call.call_args_list]


class GrubTimeoutTest(unittest.TestCase):
    def test_grub_steps_wait_for_a_slow_disk(self) -> None:
        with mock.patch.object(installer, "run") as run:
            installer._install_grub_bios("/mnt/target", "/dev/vda")
            with mock.patch.object(installer.os, "makedirs"):
                installer._install_grub_uefi("/mnt/target")
            installer._update_grub("/mnt/target")
        timeouts = _timeouts(run)
        self.assertEqual(len(timeouts), 3)
        for timeout in timeouts:
            self.assertIsNotNone(timeout)
            # 120 s failed on a busy host; the measured worst case of a
            # throttled disk must fit with room to spare
            self.assertGreaterEqual(timeout, installer.GRUB_TIMEOUT)
        self.assertGreaterEqual(installer.GRUB_TIMEOUT, 1800)

    def test_other_chroot_commands_keep_their_timeout(self) -> None:
        with mock.patch.object(installer, "run") as run:
            installer._chroot("/mnt/target", ["true"])
        self.assertEqual(_timeouts(run), [120])


class StepErrorTest(unittest.TestCase):
    def _ui(self) -> tuple[object, mock.MagicMock]:
        d = mock.MagicMock()
        with mock.patch.object(ui_wrapper.dialog, "Dialog", return_value=d):
            ui = ui_wrapper.UI()
        return ui, d

    def test_a_failed_step_shows_the_command_and_its_error(self) -> None:
        ui, d = self._ui()
        error = runner.RunError(
            ["chroot", "/mnt/target", "grub-install", "--target=x86_64-efi"],
            -1,
            "Timed out after 120s",
        )
        with self.assertRaises(runner.RunError):
            with ui.please_wait("Installing GRUB bootloader..."):
                raise error
        text = d.msgbox.call_args.args[0]
        self.assertIn("Installing GRUB bootloader...", text)
        self.assertIn("grub-install", text)
        self.assertIn("Timed out after 120s", text)

    def test_a_long_error_is_cut_to_its_last_lines(self) -> None:
        ui, d = self._ui()
        stderr = "\n".join("line %d" % n for n in range(100))
        with self.assertRaises(runner.RunError):
            with ui.please_wait("Running update-grub"):
                raise runner.RunError(["update-grub"], 1, stderr)
        text = d.msgbox.call_args.args[0]
        self.assertIn("update-grub", text)
        self.assertIn("line 99", text)
        self.assertNotIn("line 10\n", text)


if __name__ == "__main__":
    unittest.main()
