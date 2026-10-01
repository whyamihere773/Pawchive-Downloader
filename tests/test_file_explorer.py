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

    def test_detect_next_index(self):
        bridge = AppBridge()
        folder1 = os.path.join(self.temp_dir, "Folder 1")
        folder2 = os.path.join(self.temp_dir, "Folder 2")
        os.makedirs(folder1, exist_ok=True)
        os.makedirs(folder2, exist_ok=True)

        # Empty folder returns 1
        self.assertEqual(bridge.detectNextIndex(folder1), 1)

        # Create files 1 to 100 in folder 1
        with open(os.path.join(folder1, "file_001.png"), "w") as f:
            f.write("a")
        with open(os.path.join(folder1, "file_100.png"), "w") as f:
            f.write("b")

        # Scanning folder 1 directly detects next index 101
        self.assertEqual(bridge.detectNextIndex(folder1), 101)

        # Folder 2 has unnumbered files, but previous sibling is Folder 1 (ending at 100) -> detects 101
        with open(os.path.join(folder2, "image_raw.png"), "w") as f:
            f.write("c")
        self.assertEqual(bridge.detectNextIndex(folder2), 101)

    def test_batch_rename_start_index(self):
        bridge = AppBridge()
        test_file_1 = os.path.join(self.temp_dir, "a.jpg")
        test_file_2 = os.path.join(self.temp_dir, "b.jpg")
        with open(test_file_1, "w") as f:
            f.write("1")
        with open(test_file_2, "w") as f:
            f.write("2")

        plan = bridge.previewBatchRename(
            self.temp_dir,
            files=["a.jpg", "b.jpg"],
            pattern="Photo_{00index}.{ext}",
            start_index=101
        )
        self.assertEqual(len(plan), 2)
        self.assertEqual(plan[0]["new_name"], "Photo_101.jpg")
        self.assertEqual(plan[1]["new_name"], "Photo_102.jpg")

    def test_batch_rename_multi_folder_continuous_sequence(self):
        bridge = AppBridge()
        multi_dir = os.path.join(self.temp_dir, "MultiSet")
        f1 = os.path.join(multi_dir, "Set1")
        f2 = os.path.join(multi_dir, "Set2")
        os.makedirs(f1, exist_ok=True)
        os.makedirs(f2, exist_ok=True)
        with open(os.path.join(f1, "img_a.png"), "w") as f:
            f.write("1")
        with open(os.path.join(f1, "img_b.png"), "w") as f:
            f.write("2")
        with open(os.path.join(f2, "img_c.png"), "w") as f:
            f.write("3")
        with open(os.path.join(f2, "img_d.png"), "w") as f:
            f.write("4")

        # Recursive preview across subfolders with continuous index starting at 1
        plan = bridge.previewBatchRename(
            multi_dir,
            files=[],
            pattern="Pic_{index}.{ext}",
            start_index=1,
            include_subfolders=True
        )
        self.assertEqual(len(plan), 4)
        indices = [int(p["new_name"].replace("Pic_", "").replace(".png", "")) for p in plan]
        self.assertEqual(indices, [1, 2, 3, 4])
        self.assertEqual(plan[0]["new_name"], "Pic_1.png")
        self.assertEqual(plan[1]["new_name"], "Pic_2.png")
        self.assertEqual(plan[2]["new_name"], "Pic_3.png")
        self.assertEqual(plan[3]["new_name"], "Pic_4.png")

    def test_batch_rename_move_to_folder(self):
        bridge = AppBridge()
        sub_dir = os.path.join(self.temp_dir, "SubPack")
        dest_dir = os.path.join(self.temp_dir, "Flattened")
        os.makedirs(sub_dir, exist_ok=True)
        os.makedirs(dest_dir, exist_ok=True)

        f1 = os.path.join(sub_dir, "file1.txt")
        f2 = os.path.join(sub_dir, "file2.txt")
        with open(f1, "w") as f:
            f.write("content 1")
        with open(f2, "w") as f:
            f.write("content 2")

        plan = bridge.previewBatchRename(
            sub_dir,
            files=["file1.txt", "file2.txt"],
            pattern="Item_{0index}.{ext}",
            start_index=1,
            move_to_folder=True,
            destination_folder=dest_dir
        )
        self.assertEqual(len(plan), 2)
        self.assertTrue(plan[0]["is_move"])
        self.assertEqual(os.path.normpath(plan[0]["new_path"]), os.path.normpath(os.path.join(dest_dir, "Item_01.txt")))
        self.assertEqual(os.path.normpath(plan[1]["new_path"]), os.path.normpath(os.path.join(dest_dir, "Item_02.txt")))

        res = bridge.executeBatchRename(plan)
        self.assertTrue(res["success"])
        self.assertEqual(res["renamed"], 2)
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "Item_01.txt")))
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "Item_02.txt")))
        self.assertFalse(os.path.exists(f1))
        self.assertFalse(os.path.exists(f2))

    def test_gallery_bookmarks(self):
        bridge = AppBridge()
        # Initial bookmarks should contain defaults
        initial_bms = bridge.getGalleryBookmarks()
        self.assertIsInstance(initial_bms, list)

        # Add a bookmark
        folder_a = os.path.join(self.temp_dir, "FolderA")
        added = bridge.addGalleryBookmark(folder_a, "My Folder A")
        self.assertTrue(added)
        self.assertTrue(bridge.isGalleryBookmarked(folder_a))

        # Adding same bookmark again should return False
        added_duplicate = bridge.addGalleryBookmark(folder_a, "Duplicate")
        self.assertFalse(added_duplicate)

        # Verify it appears in bookmarks list
        bms = bridge.getGalleryBookmarks()
        match = [b for b in bms if os.path.normpath(b.get("path", "")) == os.path.normpath(folder_a)]
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0]["name"], "My Folder A")

        # Remove the bookmark
        removed = bridge.removeGalleryBookmark(folder_a)
        self.assertTrue(removed)
        self.assertFalse(bridge.isGalleryBookmarked(folder_a))

        # Removing non-existent returns False
        removed_again = bridge.removeGalleryBookmark(folder_a)
        self.assertFalse(removed_again)


if __name__ == "__main__":
    unittest.main()

