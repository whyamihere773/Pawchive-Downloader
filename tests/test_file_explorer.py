import os
import sys
import unittest
import tempfile
import shutil

from bridge.app_bridge import AppBridge


class TestFileExplorer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        # Create some test files and folders
        os.makedirs(os.path.join(self.temp_dir, "FolderA"), exist_ok=True)
        os.makedirs(os.path.join(self.temp_dir, "FolderB"), exist_ok=True)
        with open(os.path.join(self.temp_dir, "image.png"), "w") as f:
            f.write("fake image data")
        with open(os.path.join(self.temp_dir, "video.mp4"), "w") as f:
            f.write("fake video data")
        with open(os.path.join(self.temp_dir, "archive.zip"), "w") as f:
            f.write("fake archive data")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_list_directory_on_demand(self):
        bridge = AppBridge()
        items = bridge.listDirectory(self.temp_dir, max_entries=100)
        self.assertEqual(len(items), 5)

        # Ensure folders appear first
        self.assertTrue(items[0]["is_dir"])
        self.assertTrue(items[1]["is_dir"])
        dir_names = {items[0]["name"], items[1]["name"]}
        self.assertEqual(dir_names, {"FolderA", "FolderB"})

        # Check file entries
        files = {item["name"]: item for item in items if not item["is_dir"]}
        self.assertIn("image.png", files)
        self.assertEqual(files["image.png"]["ext"], ".png")
        self.assertGreater(files["image.png"]["size"], 0)

    def test_list_directory_max_entries_cap(self):
        bridge = AppBridge()
        items = bridge.listDirectory(self.temp_dir, max_entries=2)
        self.assertEqual(len(items), 2)

    def test_breadcrumbs(self):
        bridge = AppBridge()
        crumbs = bridge.getBreadcrumbs(self.temp_dir)
        self.assertGreaterEqual(len(crumbs), 1)
        # Last crumb should be the temp folder itself
        self.assertEqual(os.path.normpath(crumbs[-1]["path"]), os.path.normpath(self.temp_dir))

    def test_system_drives(self):
        bridge = AppBridge()
        drives = bridge.getSystemDrives()
        self.assertIsInstance(drives, list)
        self.assertGreater(len(drives), 0)
        self.assertIn("path", drives[0])
        self.assertIn("name", drives[0])

    def test_folder_stats_calculation(self):
        folder_a = os.path.join(self.temp_dir, "FolderA")
        with open(os.path.join(folder_a, "subfile1.bin"), "wb") as f:
            f.write(b"12345")
        with open(os.path.join(folder_a, "subfile2.bin"), "wb") as f:
            f.write(b"67890")

        bridge = AppBridge()
        bridge._folder_stats_worker_token = 1
        bridge._compute_folder_stats(folder_a, 1)

        stats = bridge.getFolderStats(folder_a)
        self.assertEqual(stats["files"], 2)
        self.assertEqual(stats["size"], 10)


if __name__ == "__main__":
    unittest.main()
