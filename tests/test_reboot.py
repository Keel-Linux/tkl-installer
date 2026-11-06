"""The reboot at the end of the install, with or without the live medium.

The installer asks the operator to remove the live medium before the
reboot. The reboot program is a file of that medium: with the medium out,
its exec fails with EIO (VM 9367 on BR1, 2026-11-06), and the kernel's own
reboot (SysRq b) must take over. No program runs and no machine reboots
here: run and the trigger file are stand-ins.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import tempfile
import unittest
from unittest import mock

installer = importlib.import_module("tkl_installer.installer")


class RebootNow(unittest.TestCase):
    def setUp(self) -> None:
        handle, self.trigger = tempfile.mkstemp()
        os.close(handle)
        patcher = mock.patch.object(installer, "SYSRQ_TRIGGER", self.trigger)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(os.unlink, self.trigger)
        sync = mock.patch.object(installer.os, "sync")
        self.sync = sync.start()
        self.addCleanup(sync.stop)

    def written(self) -> str:
        with open(self.trigger, encoding="ascii") as handle:
            return handle.read()

    def test_the_reboot_program_reboots_when_it_runs(self) -> None:
        done = subprocess.CompletedProcess(["reboot"], 0)
        with mock.patch.object(installer, "run", return_value=done) as run:
            installer.reboot_now()
        run.assert_called_once_with(["reboot"], destructive=True, check=False)
        self.sync.assert_called_once_with()
        self.assertEqual(self.written(), "")

    def test_a_medium_that_is_gone_gives_the_kernel_reboot(self) -> None:
        gone = OSError(5, "Input/output error", "reboot")
        with mock.patch.object(installer, "run", side_effect=gone):
            with self.assertLogs(installer.log, "WARNING") as logs:
                installer.reboot_now()
        self.assertEqual(self.written(), "b")
        self.assertIn("the kernel reboots", logs.output[0])
        self.sync.assert_called_once_with()

    def test_a_reboot_program_that_fails_gives_the_kernel_reboot(self) -> None:
        failed = subprocess.CompletedProcess(["reboot"], 1)
        with mock.patch.object(installer, "run", return_value=failed):
            with self.assertLogs(installer.log, "WARNING") as logs:
                installer.reboot_now()
        self.assertEqual(self.written(), "b")
        self.assertIn("reboot exited 1", logs.output[0])


if __name__ == "__main__":
    unittest.main()
