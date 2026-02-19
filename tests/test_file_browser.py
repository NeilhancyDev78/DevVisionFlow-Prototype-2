"""Tests for the file browser component."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sender.config import SenderConfig
from sender.file_browser import FileBrowser, FileEntry


class TestFileBrowser(unittest.TestCase):
    """Test the FileBrowser navigation and listing."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        # Create some test files
        for name in ("alpha.txt", "beta.png", "gamma.csv"):
            (Path(self._tmpdir) / name).write_text("test content")

        self.config = SenderConfig()
        self.config.send_directory = self._tmpdir
        self.browser = FileBrowser(self.config)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_file_count(self) -> None:
        self.assertEqual(self.browser.file_count, 3)

    def test_is_not_empty(self) -> None:
        self.assertFalse(self.browser.is_empty)

    def test_current_file_default(self) -> None:
        current = self.browser.current_file
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current.name, "alpha.txt")

    def test_next_file(self) -> None:
        self.browser.next_file()
        current = self.browser.current_file
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current.name, "beta.png")

    def test_previous_file_wraps(self) -> None:
        self.browser.previous_file()
        current = self.browser.current_file
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current.name, "gamma.csv")

    def test_next_file_wraps(self) -> None:
        for _ in range(3):
            self.browser.next_file()
        current = self.browser.current_file
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current.name, "alpha.txt")

    def test_refresh_picks_up_new_files(self) -> None:
        (Path(self._tmpdir) / "delta.md").write_text("new")
        self.browser.refresh()
        self.assertEqual(self.browser.file_count, 4)

    def test_empty_directory(self) -> None:
        empty_dir = tempfile.mkdtemp()
        config = SenderConfig()
        config.send_directory = empty_dir
        browser = FileBrowser(config)
        self.assertTrue(browser.is_empty)
        self.assertIsNone(browser.current_file)
        self.assertIsNone(browser.next_file())
        self.assertIsNone(browser.previous_file())
        import shutil
        shutil.rmtree(empty_dir, ignore_errors=True)

    def test_visible_window(self) -> None:
        visible = self.browser.get_visible_window(window_size=5)
        self.assertEqual(len(visible), 3)  # only 3 files, less than window


class TestFileEntry(unittest.TestCase):
    """Test the FileEntry data object."""

    def test_size_human_bytes(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"hello")
            f.flush()
            entry = FileEntry(Path(f.name))
            self.assertEqual(entry.size_human, "5.0 B")
            os.unlink(f.name)

    def test_mime_type(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
            f.write(b"{}")
            f.flush()
            entry = FileEntry(Path(f.name))
            self.assertEqual(entry.mime_type, "application/json")
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
