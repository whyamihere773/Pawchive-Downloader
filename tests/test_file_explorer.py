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

    def test_path_to_url(self):
        bridge = AppBridge()
        test_file = os.path.join(self.temp_dir, "image.png")
        url = bridge.pathToUrl(test_file)
        self.assertTrue(url.startswith("file:///"))
        self.assertIn("image.png", url)

    def test_batch_rename(self):
        bridge = AppBridge()
        # Create test files
        test_file_1 = os.path.join(self.temp_dir, "01_art.png")
        test_file_2 = os.path.join(self.temp_dir, "02_art.png")
        with open(test_file_1, "w") as f:
            f.write("content 1")
        with open(test_file_2, "w") as f:
            f.write("content 2")

        plan = bridge.previewBatchRename(
            self.temp_dir,
            files=["01_art.png", "02_art.png"],
            pattern="Wall_{0index}.{ext}"
        )
        self.assertEqual(len(plan), 2)
        self.assertEqual(plan[0]["new_name"], "Wall_01.png")
        self.assertEqual(plan[1]["new_name"], "Wall_02.png")
        self.assertEqual(plan[0]["status"], "ready")

        res = bridge.executeBatchRename(plan)
        self.assertTrue(res["success"])
        self.assertEqual(res["renamed"], 2)
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "Wall_01.png")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "Wall_02.png")))

    def test_scan_broken_files_and_delete(self):
        bridge = AppBridge()
        zero_file = os.path.join(self.temp_dir, "zero.dat")
        with open(zero_file, "w") as f:
            pass  # 0 bytes
        temp_file = os.path.join(self.temp_dir, "incomplete.part")
        with open(temp_file, "w") as f:
            f.write("in-progress download")

        broken = bridge.scanBrokenFiles(self.temp_dir, recursive=False)
        broken_names = [b["name"] for b in broken]
        self.assertIn("zero.dat", broken_names)
        self.assertIn("incomplete.part", broken_names)

        del_res = bridge.deleteItems([zero_file, temp_file])
        self.assertEqual(del_res["deleted"], 2)
        self.assertFalse(os.path.exists(zero_file))
        self.assertFalse(os.path.exists(temp_file))

    def test_scan_duplicates(self):
        bridge = AppBridge()
        dup1 = os.path.join(self.temp_dir, "dup1.bin")
        dup2 = os.path.join(self.temp_dir, "dup2.bin")
        with open(dup1, "wb") as f:
            f.write(b"IDENTICAL_CONTENT_FOR_HASH_TEST")
        with open(dup2, "wb") as f:
            f.write(b"IDENTICAL_CONTENT_FOR_HASH_TEST")

        duplicates = bridge.scanDuplicates(self.temp_dir, recursive=False)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["count"], 2)
        self.assertEqual(duplicates[0]["wasted_size"], len(b"IDENTICAL_CONTENT_FOR_HASH_TEST"))

    def test_auto_sort_folder(self):
        bridge = AppBridge()
        sort_dir = os.path.join(self.temp_dir, "SortTest")
        os.makedirs(sort_dir, exist_ok=True)
        img = os.path.join(sort_dir, "photo.png")
        vid = os.path.join(sort_dir, "clip.mp4")
        with open(img, "w") as f:
            f.write("image")
        with open(vid, "w") as f:
            f.write("video")

        res = bridge.autoSortFolder(sort_dir, mode="type")
        self.assertEqual(res["moved"], 2)
        self.assertTrue(os.path.exists(os.path.join(sort_dir, "Images", "photo.png")))
        self.assertTrue(os.path.exists(os.path.join(sort_dir, "Videos", "clip.mp4")))


if __name__ == "__main__":
    unittest.main()

