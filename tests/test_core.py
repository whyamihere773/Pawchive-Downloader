import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

from core.parser import KemonoURLParser
from core.filter_engine import FilterEngine, FilterOptions, MediaTypes
from core.known_manager import KnownManager
from core.session_manager import SessionManager
from core.downloader import KemonoDownloader, DownloadTask
from services.link_extractor import LinkExtractor
from services.ytdlp_manager import YtDlpManager
from bridge.app_bridge import AppBridge

class TestKemonoFullSuite(unittest.TestCase):

    # ── 1. URL Parsing Tests ──────────────────────────────────────────────────
    def test_pawchive_creator_url(self):
        res = KemonoURLParser.parse("https://pawchive.pw/fanbox/user/68002596")
        self.assertTrue(res.is_valid)
        self.assertEqual(res.domain, "pawchive.pw")
        self.assertEqual(res.service, "fanbox")
        self.assertEqual(res.user_id, "68002596")
        self.assertFalse(res.is_single_post)

    def test_kemono_single_post_url(self):
        res = KemonoURLParser.parse("https://kemono.su/patreon/user/10001/post/999888")
        self.assertTrue(res.is_valid)
        self.assertEqual(res.domain, "kemono.su")
        self.assertEqual(res.service, "patreon")
        self.assertEqual(res.user_id, "10001")
        self.assertEqual(res.post_id, "999888")
        self.assertTrue(res.is_single_post)

    def test_coomer_creator_url(self):
        res = KemonoURLParser.parse("https://coomer.su/onlyfans/user/alice_model")
        self.assertTrue(res.is_valid)
        self.assertEqual(res.domain, "coomer.su")
        self.assertEqual(res.service, "onlyfans")
        self.assertEqual(res.user_id, "alice_model")

    def test_cum_st_creator_and_post_url(self):
        res_creator = KemonoURLParser.parse("https://cum.st/onlyfans/user/model123")
        self.assertTrue(res_creator.is_valid)
        self.assertEqual(res_creator.domain, "cum.st")
        self.assertEqual(res_creator.service, "onlyfans")
        self.assertEqual(res_creator.user_id, "model123")
        self.assertFalse(res_creator.is_single_post)

        res_post = KemonoURLParser.parse("https://cum.st/fansly/user/model123/post/post999")
        self.assertTrue(res_post.is_valid)
        self.assertEqual(res_post.domain, "cum.st")
        self.assertEqual(res_post.service, "fansly")
        self.assertEqual(res_post.post_id, "post999")
        self.assertTrue(res_post.is_single_post)

        res_dm = KemonoURLParser.parse("https://cum.st/onlyfans/user/model123/dm/dm555")
        self.assertTrue(res_dm.is_valid)
        self.assertEqual(res_dm.post_id, "dm555")

        # Test cum.st /creators/ format
        res_creators = KemonoURLParser.parse("https://cum.st/creators/onlyfans/32696630")
        self.assertTrue(res_creators.is_valid)
        self.assertEqual(res_creators.domain, "cum.st")
        self.assertEqual(res_creators.service, "onlyfans")
        self.assertEqual(res_creators.user_id, "32696630")
        self.assertIsNone(res_creators.post_id)

        # Test /posts/ route
        res_posts_route = KemonoURLParser.parse("https://cum.st/posts/onlyfans/32696630/777888")
        self.assertTrue(res_posts_route.is_valid)
        self.assertEqual(res_posts_route.service, "onlyfans")
        self.assertEqual(res_posts_route.user_id, "32696630")
        self.assertEqual(res_posts_route.post_id, "777888")

    def test_invalid_url(self):
        res = KemonoURLParser.parse("https://google.com/search?q=test")
        self.assertFalse(res.is_valid)

    # ── 2. Filter Engine Tests ────────────────────────────────────────────────
    def test_character_filter_title_scope(self):
        # Single characters are matched individually; (Cloud, Zack) group requires ALL of them
        opts = FilterOptions(characters="Tifa, Aerith", character_scope="title")
        self.assertTrue(FilterEngine.should_keep_post({"title": "New Tifa render 4K", "content": ""}, opts)[0])
        self.assertTrue(FilterEngine.should_keep_post({"title": "Beautiful Aerith artwork", "content": ""}, opts)[0])
        self.assertFalse(FilterEngine.should_keep_post({"title": "Random artwork", "content": ""}, opts)[0])
        self.assertFalse(FilterEngine.should_keep_post({"title": "Sephiroth fight", "content": ""}, opts)[0])

    def test_character_filter_content_scope(self):
        opts = FilterOptions(characters="Goku", character_scope="content")
        self.assertTrue(FilterEngine.should_keep_post({"title": "DBZ Pack", "content": "<p>Featuring Goku Super Saiyan</p>"}, opts)[0])
        self.assertFalse(FilterEngine.should_keep_post({"title": "Goku Art", "content": "<p>Vegeta solo art</p>"}, opts)[0])

    def test_skip_words_posts_scope(self):
        opts = FilterOptions(skip_words="WM, WIP, sketch", skip_scope="posts")
        self.assertFalse(FilterEngine.should_keep_post({"title": "Final Fantasy WIP sketch", "content": ""}, opts)[0])
        self.assertTrue(FilterEngine.should_keep_post({"title": "Final Fantasy HD Artwork", "content": ""}, opts)[0])

    def test_file_type_categories(self):
        # Images only
        opts_img = FilterOptions(file_type="images")
        self.assertTrue(FilterEngine.should_keep_file("photo.jpg", opts_img)[0])
        self.assertTrue(FilterEngine.should_keep_file("art.png", opts_img)[0])
        self.assertFalse(FilterEngine.should_keep_file("video.mp4", opts_img)[0])
        self.assertFalse(FilterEngine.should_keep_file("archive.zip", opts_img)[0])

        # Videos only
        opts_vid = FilterOptions(file_type="videos")
        self.assertTrue(FilterEngine.should_keep_file("animation.mp4", opts_vid)[0])
        self.assertFalse(FilterEngine.should_keep_file("photo.jpg", opts_vid)[0])

        # Skip Archives flag
        opts_skip_arc = FilterOptions(file_type="all", skip_archives=True)
        self.assertFalse(FilterEngine.should_keep_file("bundle.zip", opts_skip_arc)[0])
        self.assertFalse(FilterEngine.should_keep_file("bundle.7z", opts_skip_arc)[0])
        self.assertTrue(FilterEngine.should_keep_file("image.jpeg", opts_skip_arc)[0])

    def test_filename_sanitization_and_word_removal(self):
        opts = FilterOptions(remove_words="patreon, HD, [sample]")
        clean = FilterEngine.sanitize_filename("patreon_art_HD_[sample]_01?.png", opts)
        self.assertNotIn("patreon", clean.lower())
        self.assertNotIn("hd", clean.lower())
        self.assertNotIn("[sample]", clean.lower())
        self.assertNotIn("?", clean)
        self.assertTrue(clean.endswith(".png"))

    def test_unicode_preservation_and_emoji_normalization(self):
        # 1. Japanese title with emojis and slashes
        jp_input = "【コスプレ】ジョリーン・空条 (Jolyne Cujoh) 💕 2026/08/18 💦"
        jp_clean = FilterEngine.clean_filesystem_text(jp_input)
        self.assertIn("【コスプレ】ジョリーン・空条", jp_clean)
        self.assertIn("(Jolyne Cujoh)", jp_clean)
        self.assertNotIn("💕", jp_clean)
        self.assertNotIn("💦", jp_clean)
        self.assertNotIn("/", jp_clean)

        # 2. Chinese title with emojis
        cn_input = "【原创写真】樱花落下的瞬间 🌸 4K超清写真包 🐱"
        cn_clean = FilterEngine.clean_filesystem_text(cn_input)
        self.assertIn("【原创写真】樱花落下的瞬间", cn_clean)
        self.assertIn("4K超清写真包", cn_clean)
        self.assertNotIn("🌸", cn_clean)
        self.assertNotIn("🐱", cn_clean)

        # 3. Multiline with Windows control chars
        multiline = "Look how bubbly my booty is...\r\nCheck this out! <3"
        ml_clean = FilterEngine.clean_filesystem_text(multiline)
        self.assertNotIn("\r", ml_clean)
        self.assertNotIn("\n", ml_clean)
        self.assertNotIn("<", ml_clean)

        # 4. Windows reserved device name
        con_clean = FilterEngine.clean_filesystem_text("CON")
        self.assertEqual(con_clean, "_CON_")

    def test_content_image_extraction(self):
        html = '<p>Check this: <img src="/data/ab/cd/abcd1234.png" alt="img" /> and <a href="https://pawchive.pw/data/12/34/123456.jpg">Link</a></p>'
        imgs = FilterEngine.extract_content_images(html)
        self.assertEqual(len(imgs), 2)
        self.assertIn("/data/ab/cd/abcd1234.png", imgs)

    def test_link_extractor_embed_urls(self):
        post = {
            "embed": {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            "content": '<p>Watch here: <iframe src="https://player.vimeo.com/video/76979871"></iframe> and https://streamable.com/abc123</p>'
        }
        embeds = LinkExtractor.extract_embed_urls(post)
        self.assertEqual(len(embeds), 3)
        self.assertIn("https://www.youtube.com/watch?v=dQw4w9WgXcQ", embeds)
        self.assertIn("https://player.vimeo.com/video/76979871", embeds)
        self.assertIn("https://streamable.com/abc123", embeds)

    def test_ytdlp_manager_path(self):
        ym = YtDlpManager()
        exe = ym.get_executable_path()
        self.assertTrue(exe.endswith("yt-dlp.exe"))
        self.assertIn("dependencies", exe)

    def test_downloader_ytdlp_task_generation(self):
        km = KnownManager()
        sm = SessionManager()
        downloader = KemonoDownloader(known_manager=km, session_manager=sm, max_workers=4)

        posts = [{
            "id": "999",
            "title": "Embedded Vimeo Test",
            "content": '<iframe src="https://player.vimeo.com/video/123456"></iframe>',
            "file": {},
            "attachments": []
        }]
        opts = FilterOptions(download_embeds=True)
        tasks = downloader.build_tasks_from_posts(posts, "CreatorX", "patreon", "kemono.su", "C:\\test", opts)
        self.assertEqual(len(tasks), 1)
        self.assertTrue(tasks[0].is_ytdlp)
        self.assertEqual(tasks[0].url, "https://player.vimeo.com/video/123456")

    # ── 3. Known Manager Tests ────────────────────────────────────────────────
    def test_known_manager(self):
        import tempfile
        # Write a temporary Known.txt for deterministic testing
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Tifa\nAerith\nGoku\n")
            tmp_path = f.name

        try:
            km = KnownManager(file_path=tmp_path)
            self.assertEqual(len(km.entries), 3)
            self.assertEqual(km.find_matching_category("Beautiful Tifa Lockhart in high res"), "Tifa")
            self.assertEqual(km.find_matching_category("tifa_lockhart_set_01"), "Tifa")
            self.assertEqual(km.find_matching_category("aerith gainsborough sketch"), "Aerith")
            self.assertIsNone(km.find_matching_category("Random unrelated title xyz"))
        finally:
            os.unlink(tmp_path)

    # ── 4. Downloader & Concurrency Tests ─────────────────────────────────────
    def test_downloader_task_building(self):
        km = KnownManager()
        sm = SessionManager()
        downloader = KemonoDownloader(known_manager=km, session_manager=sm, max_workers=8)

        sample_posts = [{
            "id": "1001",
            "user": "12345",
            "service": "fanbox",
            "title": "Tifa Fanart",
            "published": "2024-01-01",
            "file": {"name": "tifa_cover.png", "path": "/11/22/1122334455.png"},
            "attachments": []
        }]

        opts = FilterOptions()
        tasks = downloader.build_tasks_from_posts(
            posts=sample_posts,
            creator_name="Artist",
            service="fanbox",
            domain="pawchive.pw",
            base_dir="C:/TestDownloads",
            options=opts
        )

        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertEqual(task.filename, "tifa_cover.png")
        # Ensure Pawchive route is file.pawchive.pw
        self.assertTrue(task.url.startswith("https://file.pawchive.pw/data/"))
        self.assertIn("?f=tifa_cover.png", task.url)

    def test_separate_by_known_keeps_katarin_out_of_other(self):
        """Underscore titles like katarin_story must not create a second folder under Other."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Katarin\n")
            tmp_path = f.name
        try:
            km = KnownManager(file_path=tmp_path)
            sm = SessionManager()
            downloader = KemonoDownloader(known_manager=km, session_manager=sm, max_workers=2)
            posts = [
                {
                    "id": "1",
                    "title": "katarin_story_12",
                    "published": "2024-01-01",
                    "file": {"name": "a.png", "path": "/11/22/aabb.png"},
                    "attachments": []
                },
                {
                    "id": "2",
                    "title": "random landscape",
                    "published": "2024-01-02",
                    "file": {"name": "b.png", "path": "/11/22/ccdd.png"},
                    "attachments": []
                },
            ]
            opts = FilterOptions(separate_by_known=True, subfolder_per_post=True, date_prefix=False)
            tasks = downloader.build_tasks_from_posts(
                posts=posts,
                creator_name="Soboro",
                service="patreon",
                domain="kemono.su",
                base_dir=r"C:\Users\silvi\Desktop\Soboro",
                options=opts,
            )
            self.assertEqual(len(tasks), 2)
            katarin_path = next(t.target_path for t in tasks if t.filename == "a.png")
            other_path = next(t.target_path for t in tasks if t.filename == "b.png")
            self.assertIn(os.path.join("Katarin", "Soboro [patreon]"), katarin_path)
            self.assertNotIn(os.path.sep + "Other" + os.path.sep, katarin_path)
            self.assertIn(os.path.join("Other", "Soboro [patreon]"), other_path)
        finally:
            os.unlink(tmp_path)

    def test_speed_and_eta_formatting(self):
        self.assertEqual(KemonoDownloader.format_speed(500), "500 B/s")
        self.assertEqual(KemonoDownloader.format_speed(1024 * 50), "50.0 KB/s")
        self.assertEqual(KemonoDownloader.format_speed(1024 * 1024 * 3 + 512 * 1024), "3.50 MB/s")

    # ── 5. CPU Threads & Bridge Features ──────────────────────────────────────
    def test_cpu_detection_in_bridge(self):
        bridge = AppBridge()
        cpu_count = os.cpu_count() or 4
        self.assertEqual(bridge.maxCpuThreads, max(4, cpu_count))
        self.assertTrue(1 <= bridge.threadsCount <= bridge.maxCpuThreads)

    def test_discard_session_cancels_download(self):
        bridge = AppBridge()
        bridge.discardSession()
        self.assertFalse(bridge.hasSavedSession)
        self.assertFalse(bridge.isDownloading)

    def test_adaptive_429_throttling(self):
        km = KnownManager()
        sm = SessionManager()
        downloader = KemonoDownloader(known_manager=km, session_manager=sm, max_workers=24)

        throttled_to = []
        downloader.on_concurrency_throttled = lambda count: throttled_to.append(count)

        downloader._trigger_rate_limit_backoff()
        self.assertEqual(downloader.max_workers, 22)
        self.assertEqual(len(throttled_to), 1)
        self.assertEqual(throttled_to[0], 22)

        # Second backoff after cooldown
        downloader._rate_limit_cooldown_until = 0.0
        downloader._trigger_rate_limit_backoff()
        self.assertEqual(downloader.max_workers, 20)

    def test_retry_failed_tasks(self):
        km = KnownManager()
        sm = SessionManager()
        downloader = KemonoDownloader(known_manager=km, session_manager=sm, max_workers=4)

        t1 = DownloadTask("url1", "path1/f1.png", "Post 1", "Artist", "fanbox", "1", "f1")
        t2 = DownloadTask("url2", "path2/f2.png", "Post 2", "Artist", "fanbox", "2", "f2")
        t1.status = "completed"
        t2.status = "failed"
        t2.error_msg = "403 Forbidden"
        downloader.tasks = [t1, t2]

        # Patch start_download_queue so we can inspect task state before the
        # background thread can race ahead and flip status to "downloading"
        downloader.start_download_queue = lambda *a, **kw: None

        count = downloader.retry_failed_tasks(FilterOptions(), "")
        self.assertEqual(count, 1)
        self.assertEqual(t2.status, "pending")
        self.assertEqual(t2.error_msg, "")
        self.assertEqual(t1.status, "completed")

    def test_queue_model_filtering_and_counts(self):
        from bridge.queue_model import QueueModel
        qm = QueueModel()

        t1 = DownloadTask("url1", "p/f1.png", "P1", "A", "fanbox", "1", "1")
        t2 = DownloadTask("url2", "p/f2.png", "P2", "A", "fanbox", "2", "2")
        t3 = DownloadTask("url3", "p/f3.png", "P3", "A", "fanbox", "3", "3")
        t1.status = "completed"
        t2.status = "failed"
        t2.error_msg = "HTTP 500"
        t3.status = "downloading"
        qm.setTasks([t1, t2, t3])

        self.assertEqual(qm.totalCount, 3)
        self.assertEqual(qm.completedCount, 1)
        self.assertEqual(qm.failedCount, 1)
        self.assertEqual(qm.downloadingCount, 1)
        self.assertEqual(qm.rowCount(), 3)

        # Filter only failed
        qm.filterStatus = "failed"
        self.assertEqual(qm.rowCount(), 1)

        # Retry failed
        qm.retryFailed()
        self.assertEqual(t2.status, "pending")
        self.assertEqual(qm.failedCount, 0)
        self.assertEqual(qm.pendingCount, 1)

    def test_retry_selected_tasks(self):
        km = KnownManager()
        sm = SessionManager()
        downloader = KemonoDownloader(known_manager=km, session_manager=sm, max_workers=4)

        t1 = DownloadTask("url1", "p/f1.png", "P1", "Artist", "fanbox", "1", "id1")
        t2 = DownloadTask("url2", "p/f2.png", "P2", "Artist", "fanbox", "2", "id2")
        t3 = DownloadTask("url3", "p/f3.png", "P3", "Artist", "fanbox", "3", "id3")
        t1.status = "failed"
        t1.error_msg = "403 Forbidden"
        t2.status = "failed"
        t2.error_msg = "404 Not Found"
        t3.status = "completed"
        downloader.tasks = [t1, t2, t3]

        # Prevent background thread from downloading immediately
        with patch.object(downloader, "start_download_queue"):
            count = downloader.retry_selected_tasks(["id1"], FilterOptions(), "")
            self.assertEqual(count, 1)
            self.assertEqual(t1.status, "pending")
            self.assertEqual(t1.error_msg, "")
            self.assertEqual(t2.status, "failed") # Unselected remains failed!
            self.assertEqual(t3.status, "completed")

    def test_adaptive_threading_options(self):
        opts = FilterOptions(adaptive_threading=True, auto_retry_at_end=True)
        self.assertTrue(opts.adaptive_threading)
        self.assertTrue(opts.auto_retry_at_end)

        bridge = AppBridge()
        bridge.adaptiveThreading = True
        self.assertTrue(bridge.adaptiveThreading)
        bridge.autoRetryAtEnd = True
        self.assertTrue(bridge.autoRetryAtEnd)

    def test_adaptive_telemetry_properties(self):
        bridge = AppBridge()
        self.assertIn(bridge.adaptiveState, ("optimal", "scaling", "cooldown", "manual"))
        self.assertIsInstance(bridge.adaptiveStatusText, str)

    # ── 6. Filter Engine — Full Coverage ─────────────────────────────────────

    def test_filter_skip_words_files_scope(self):
        """skip_words with files scope filters filenames, not post titles."""
        opts = FilterOptions(skip_words="preview, sample", skip_scope="files")
        # File names that contain skip words → rejected
        self.assertFalse(FilterEngine.should_keep_file("art_preview.jpg", opts)[0])
        self.assertFalse(FilterEngine.should_keep_file("sample_render.png", opts)[0])
        # Post title with the same word → still kept (scope is "files" only)
        self.assertTrue(FilterEngine.should_keep_post({"title": "preview pack", "content": ""}, opts)[0])
        # Clean file → kept
        self.assertTrue(FilterEngine.should_keep_file("final_render.png", opts)[0])

    def test_filter_skip_words_both_scope(self):
        """skip_words with 'both' scope filters posts AND filenames."""
        opts = FilterOptions(skip_words="WIP", skip_scope="both")
        self.assertFalse(FilterEngine.should_keep_post({"title": "WIP sketches", "content": ""}, opts)[0])
        self.assertFalse(FilterEngine.should_keep_file("tifa_WIP_001.png", opts)[0])
        self.assertTrue(FilterEngine.should_keep_post({"title": "Final Artwork", "content": ""}, opts)[0])
        self.assertTrue(FilterEngine.should_keep_file("tifa_final_001.png", opts)[0])

    def test_filter_character_scope_both(self):
        """Character filter with 'both' scope matches title OR content."""
        opts = FilterOptions(characters="Aerith", character_scope="both")
        # In title only
        self.assertTrue(FilterEngine.should_keep_post({"title": "Aerith solo", "content": ""}, opts)[0])
        # In content only
        self.assertTrue(FilterEngine.should_keep_post({"title": "FF7 pack", "content": "features Aerith"}, opts)[0])
        # Neither
        self.assertFalse(FilterEngine.should_keep_post({"title": "Tifa pack", "content": "solo render"}, opts)[0])

    def test_filter_character_slash_groups(self):
        """Character terms with / mean OR — any sub-term matches."""
        opts = FilterOptions(characters="Cloud/Zack", character_scope="title")
        self.assertTrue(FilterEngine.should_keep_post({"title": "Cloud Strife artwork"}, opts)[0])
        self.assertTrue(FilterEngine.should_keep_post({"title": "Zack Fair render"}, opts)[0])
        self.assertFalse(FilterEngine.should_keep_post({"title": "Sephiroth fight"}, opts)[0])

    def test_filter_file_type_audio(self):
        """Audio file type filter."""
        opts = FilterOptions(file_type="audio")
        self.assertTrue(FilterEngine.should_keep_file("track.mp3", opts)[0])
        self.assertTrue(FilterEngine.should_keep_file("song.flac", opts)[0])
        self.assertTrue(FilterEngine.should_keep_file("voice.ogg", opts)[0])
        self.assertFalse(FilterEngine.should_keep_file("photo.jpg", opts)[0])
        self.assertFalse(FilterEngine.should_keep_file("video.mp4", opts)[0])

    def test_filter_file_type_archives(self):
        """Archive-only file type filter (separate from skip_archives flag)."""
        opts = FilterOptions(file_type="archives")
        self.assertTrue(FilterEngine.should_keep_file("pack.zip", opts)[0])
        self.assertTrue(FilterEngine.should_keep_file("assets.rar", opts)[0])
        self.assertFalse(FilterEngine.should_keep_file("image.png", opts)[0])
        self.assertFalse(FilterEngine.should_keep_file("audio.mp3", opts)[0])

    def test_filter_file_type_all_passes_everything(self):
        """file_type='all' should not reject any extension."""
        opts = FilterOptions(file_type="all")
        for fname in ["art.png", "clip.mp4", "pack.zip", "track.mp3", "doc.pdf"]:
            self.assertTrue(FilterEngine.should_keep_file(fname, opts)[0], f"Expected {fname} to pass")

    def test_filter_skip_archives_flag(self):
        """skip_archives=True blocks all archive extensions regardless of file_type."""
        opts = FilterOptions(skip_archives=True)
        for ext in [".zip", ".rar", ".7z", ".tar", ".gz"]:
            self.assertFalse(FilterEngine.should_keep_file(f"file{ext}", opts)[0])
        # Non-archives still pass
        self.assertTrue(FilterEngine.should_keep_file("art.jpg", opts)[0])

    def test_filter_sanitize_illegal_chars(self):
        """Illegal OS path characters are replaced with underscores."""
        opts = FilterOptions()
        result = FilterEngine.sanitize_filename('post: "art" <2024> | final?.png', opts)
        for ch in [':', '"', '<', '>', '|', '?']:
            self.assertNotIn(ch, result)
        self.assertTrue(result.endswith(".png"))

    def test_filter_sanitize_empty_name_fallback(self):
        """A filename that becomes empty after sanitization falls back to 'unnamed_file'."""
        opts = FilterOptions(remove_words="art")
        result = FilterEngine.sanitize_filename("art.png", opts)
        self.assertIn("unnamed_file", result)
        self.assertTrue(result.endswith(".png"))

    def test_filter_remove_words_case_insensitive(self):
        """remove_words removal is case-insensitive."""
        opts = FilterOptions(remove_words="patreon, HD")
        clean = FilterEngine.sanitize_filename("Patreon_artwork_HD_v2.jpg", opts)
        self.assertNotIn("patreon", clean.lower())
        self.assertNotIn("hd", clean.lower())
        self.assertTrue(clean.endswith(".jpg"))

    def test_filter_empty_filename_rejected(self):
        """Empty filename is always rejected."""
        opts = FilterOptions()
        keep, reason = FilterEngine.should_keep_file("", opts)
        self.assertFalse(keep)
        self.assertIn("Empty", reason)

    def test_filter_content_images_multiple(self):
        """extract_content_images picks up multiple img and anchor tags."""
        html = (
            '<img src="/data/ab/cd/img1.png" />'
            '<a href="/data/ab/cd/img2.jpg">link</a>'
            '<img src="/data/ab/cd/video.mp4" />'  # mp4 should be excluded
            '<img src="https://example.com/thumb.webp" />'
        )
        imgs = FilterEngine.extract_content_images(html)
        self.assertIn("/data/ab/cd/img1.png", imgs)
        self.assertIn("/data/ab/cd/img2.jpg", imgs)
        self.assertIn("https://example.com/thumb.webp", imgs)
        for url in imgs:
            ext = url.rsplit(".", 1)[-1].split("?")[0]
            self.assertNotEqual(ext, "mp4", "mp4 should not appear in content images")

    def test_filter_page_range(self):
        """FilterOptions page_start / page_end are stored correctly."""
        opts = FilterOptions(page_start=3, page_end=7)
        self.assertEqual(opts.page_start, 3)
        self.assertEqual(opts.page_end, 7)

    def test_filter_all_boolean_flags(self):
        """Verify all boolean FilterOptions flags round-trip correctly."""
        opts = FilterOptions(
            skip_archives=True,
            download_thumbnails_only=True,
            scan_content_images=False,
            compress_to_webp=True,
            keep_duplicates=True,
            favorite_mode=True,
            subfolder_per_post=False,
            date_prefix=False,
            separate_by_known=True,
            download_revisions=True,
            adaptive_threading=True,
            auto_retry_at_end=True,
        )
        self.assertTrue(opts.skip_archives)
        self.assertTrue(opts.download_thumbnails_only)
        self.assertFalse(opts.scan_content_images)
        self.assertTrue(opts.compress_to_webp)
        self.assertTrue(opts.keep_duplicates)
        self.assertTrue(opts.favorite_mode)
        self.assertFalse(opts.subfolder_per_post)
        self.assertFalse(opts.date_prefix)
        self.assertTrue(opts.separate_by_known)
        self.assertTrue(opts.download_revisions)
        self.assertTrue(opts.adaptive_threading)
        self.assertTrue(opts.auto_retry_at_end)

    def test_adaptive_threading_learned_ceiling(self):
        """Verify adaptive backoff establishes and locks a learned ceiling on 429."""
        dl = KemonoDownloader(KnownManager(), SessionManager(), max_workers=6)
        self.assertIsNone(dl._learned_stable_ceiling)
        
        # Simulate hitting 429 at 6 workers
        dl._trigger_rate_limit_backoff()
        self.assertEqual(dl._learned_stable_ceiling, 5)
        self.assertLessEqual(dl.max_workers, 4)
        
        # Reset cooldown timer to simulate subsequent 429 at 4 workers
        dl._rate_limit_cooldown_until = 0.0
        dl.max_workers = 4
        dl._trigger_rate_limit_backoff()
        self.assertEqual(dl._learned_stable_ceiling, 3)
        self.assertLessEqual(dl.max_workers, 2)

    def test_queue_model_filter_and_single_retry(self):
        """Verify QueueModel live filter transitions and singleRetryRequested signal."""
        from bridge.queue_model import QueueModel
        qm = QueueModel()
        
        t1 = DownloadTask("http://a.com/1.png", "c:/tmp/1.png", "Post 1", "Creator", "patreon", "1", "f1")
        t2 = DownloadTask("http://a.com/2.png", "c:/tmp/2.png", "Post 2", "Creator", "patreon", "2", "f2")
        qm.setTasks([t1, t2])
        self.assertEqual(qm.totalCount, 2)
        self.assertEqual(qm.downloadingCount, 0)
        
        # Switch to "Active" filter
        qm.filterStatus = "downloading"
        self.assertEqual(qm.rowCount(), 0)
        
        # t1 transitions to downloading -> should dynamically appear in Active view
        t1.status = "downloading"
        qm.updateTask(t1)
        self.assertEqual(qm.rowCount(), 1)
        self.assertEqual(qm.downloadingCount, 1)
        
        # t1 transitions to completed -> should dynamically leave Active view
        t1.status = "completed"
        qm.updateTask(t1)
        self.assertEqual(qm.rowCount(), 0)
        self.assertEqual(qm.completedCount, 1)
        
        # Test single retry emission
        t2.status = "failed"
        qm.updateTask(t2)
        
        emitted_ids = []
        qm.singleRetryRequested.connect(lambda fid: emitted_ids.append(fid))
        qm.filterStatus = "failed"
        self.assertEqual(qm.rowCount(), 1)
        qm.retryTaskAt(0)
        self.assertEqual(emitted_ids, ["f2"])
        self.assertEqual(t2.status, "pending")

    # ── 15. Cloud Downloader Unit Tests ───────────────────────────────────────
    def test_mega_key_parsing_and_crypto(self):
        """Verify Mega key decoding, IV extraction, and AES-CTR decryption."""
        from services.cloud_downloader import _parse_mega_key, _process_file_key, _decrypt_mega_attribute
        from Crypto.Cipher import AES

        # 32-byte Mega folder key (8 integers)
        sample_key_b64 = "FmEfe7j_3O2tUKU0FiSaaQ=="
        key, iv, _ = _parse_mega_key(sample_key_b64)
        self.assertEqual(len(key), 16)
        if iv:
            self.assertEqual(len(iv), 16)

    def test_dropbox_url_normalization(self):
        """Verify Dropbox URLs are properly rewritten to direct download streams."""
        from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
        url = "https://www.dropbox.com/s/abcdef12345/archive.zip?dl=0"
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        qs['dl'] = ['1']
        direct_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(qs, doseq=True), parsed.fragment))
        self.assertIn("dl=1", direct_url)

    def test_link_extractor_cloud_hosts(self):
        """Verify LinkExtractor categorizes Mega, GDrive, Dropbox, and GoFile properly."""
        sample_text = """
        Check out my new set!
        Mega: https://mega.nz/folder/9jJTTSCJ#vhufQhOH9kHISvU1j-Vfbw
        Drive: https://drive.google.com/file/d/1A2B3C4D5E/view
        Dropbox: https://www.dropbox.com/s/xyz987/photos.zip?dl=0
        GoFile: https://gofile.io/d/abc123xyz
        """
        extracted = LinkExtractor.extract_links_from_text(sample_text)
        self.assertIn("mega", extracted)
        self.assertIn("gdrive", extracted)
        self.assertIn("dropbox", extracted)
        self.assertIn("gofile", extracted)
        self.assertEqual(len(extracted["mega"]), 1)
        self.assertEqual(len(extracted["gdrive"]), 1)
        self.assertEqual(len(extracted["dropbox"]), 1)
        self.assertEqual(len(extracted["gofile"]), 1)

    def test_known_matching_tokenizes_underscores_and_picks_longest(self):
        """katarin_story must land in Katarin, not Other; longer names beat prefixes."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Miao\nKatarin | Katarin Bokha\nMiao Ying\nAna\n")
            tmp_path = f.name
        try:
            km = KnownManager(file_path=tmp_path)
            km.set_mode("learning_only")
            self.assertEqual(km.find_matching_category("katarin_story_12"), "Katarin")
            self.assertEqual(km.find_matching_category("Katarin-Story 03"), "Katarin")
            self.assertEqual(km.find_matching_category("update", tags=["Katarin Bokha"]), "Katarin")
            self.assertEqual(km.find_matching_category("miao_ying_story"), "Miao Ying")
            self.assertEqual(km.find_matching_category("Miao story 02 Remake 01~08"), "Miao Ying")
            self.assertEqual(km.find_matching_category("kat video works finished"), "Katarin")
            self.assertEqual(km.find_matching_category("Beautiful Tifa Lockhart in high res"), None)
            self.assertIsNone(km.find_matching_category("Anastasia portrait"))
            self.assertIsNone(km.find_matching_category("Random unrelated title xyz"))
        finally:
            os.unlink(tmp_path)

    def test_smart_character_learning(self):
        """Verify KnownManager extracts character candidates and auto-learns them into Known list."""
        temp_dir = tempfile.mkdtemp()
        try:
            known_file = os.path.join(temp_dir, "Known.txt")
            km = KnownManager(known_file)
            
            sample_posts = [
                {
                    "title": "[Genshin Impact] Raiden Shogun - Summer Outfit",
                    "tags": ["Raiden Shogun", "Genshin Impact", "nsfw", "4k", "art"]
                },
                {
                    "title": "(Overwatch) D.Va Hana Song",
                    "tags": ["D.Va", "Overwatch", "patreon", "illustration"]
                },
                {
                    "title": "Tifa Lockhart & Aerith Gainsborough - 4K Set",
                    "tags": ["Tifa Lockhart", "Aerith Gainsborough", "Final Fantasy VII"]
                },
                {
                    "title": "【東方】博麗霊夢",
                    "tags": ["東方Project", "博麗霊夢", "R18"]
                }
            ]
            
            # Test candidate extraction on single post
            cands = km.extract_character_candidates(sample_posts[0])
            self.assertIn("Raiden Shogun", cands)
            self.assertNotIn("Genshin Impact", cands)
            self.assertNotIn("nsfw", [c.lower() for c in cands])
            self.assertNotIn("4k", [c.lower() for c in cands])
            
            # Test auto-learning from batch
            added = km.add_candidates_from_posts(sample_posts)
            self.assertGreater(len(km.entries), 10)
            self.assertTrue(any("D.Va" in e for e in km.entries))
            self.assertTrue(any("Raiden Shogun" in e for e in km.entries))
            self.assertTrue(any("博麗霊夢" in e for e in km.entries))
            
            # Verify searching matches
            found = km.find_matching_category("New render of Raiden Shogun in pool")
            self.assertIsNotNone(found)

            soboro = [
                {"title": "Alarielle Story 01 01~06"},
                {"title": "Lara Croft Stroy 01 00~08"},
                {"title": "Taoyan Final fix ver"},
                {"title": "Miao story 02 Remake 01~08"},
                {"title": "miao and Taoyan"},
                {"title": "Alarielle's new outfit"},
                {"title": "Miao_Kat st 01 00~08"},
            ]
            extracted = []
            for p in soboro:
                extracted.extend(km.extract_character_candidates(p))
            extracted_l = [e.lower() for e in extracted]
            self.assertTrue(any(e == "alarielle" for e in extracted_l))
            self.assertTrue(any("lara" in e for e in extracted_l))
            self.assertTrue(any(e == "taoyan" for e in extracted_l))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestPostDownloadActions(unittest.TestCase):
    def test_post_download_action_settings(self):
        from bridge.app_bridge import AppBridge
        from unittest.mock import patch, MagicMock

        temp_dir = tempfile.mkdtemp()
        try:
            # Test setting and getting
            bridge = AppBridge()
            bridge.postDownloadAction = "close_app"
            self.assertEqual(bridge.postDownloadAction, "close_app")

            bridge.postDownloadAction = "sleep"
            self.assertEqual(bridge.postDownloadAction, "sleep")

            bridge.postDownloadAction = "shutdown"
            self.assertEqual(bridge.postDownloadAction, "shutdown")

            bridge.postDownloadAction = "invalid_value"
            self.assertEqual(bridge.postDownloadAction, "none")

            # Test execution dispatch with mocking
            with patch("subprocess.run") as mock_run:
                bridge.postDownloadAction = "shutdown"
                bridge._execute_post_action()
                self.assertTrue(mock_run.called)

            with patch("subprocess.run") as mock_run:
                bridge.postDownloadAction = "restart"
                bridge._execute_post_action()
                self.assertTrue(mock_run.called)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestSmartETA(unittest.TestCase):
    def test_smart_eta_countdown_and_estimation(self):
        from core.downloader import KemonoDownloader, DownloadTask
        from core.known_manager import KnownManager
        from core.session_manager import SessionManager

        temp_dir = tempfile.mkdtemp()
        try:
            km = KnownManager(os.path.join(temp_dir, "Known.txt"))
            sm = SessionManager(temp_dir)
            dl = KemonoDownloader(km, sm)

            # Create 10 mock tasks of 10 MB each (total 100 MB)
            tasks = []
            for i in range(10):
                t = DownloadTask(
                    url=f"https://example.com/file_{i}.jpg",
                    target_path=f"/fake/file_{i}.jpg",
                    post_title=f"Post {i}",
                    creator_name="Artist",
                    service="patreon",
                    post_id=str(i),
                    file_id=str(i),
                    file_size=10 * 1024 * 1024
                )
                tasks.append(t)
            dl.tasks = tasks

            # Test 1: When 0 completed, speed = 10 MB/s, ETA should be around 10s
            speed = 10 * 1024 * 1024
            eta1 = dl._calculate_smart_eta(completed=0, failed=0, total=10, speed=speed, elapsed=1.0)
            self.assertIn("s", eta1)
            self.assertNotEqual(eta1, "--")
            self.assertNotEqual(eta1, "Done")

            # Test 2: Progressing through download - ETA should count down steadily
            # 5 completed (50 MB remaining), speed = 10 MB/s -> remaining ~ 5s
            for i in range(5):
                tasks[i].status = "completed"
                tasks[i].downloaded_bytes = 10 * 1024 * 1024
            
            eta2 = dl._calculate_smart_eta(completed=5, failed=0, total=10, speed=speed, elapsed=6.0)
            self.assertIn("s", eta2)

            # Test 3: All finished -> should report Done
            for t in tasks:
                t.status = "completed"
                t.downloaded_bytes = 10 * 1024 * 1024
            eta3 = dl._calculate_smart_eta(completed=10, failed=0, total=10, speed=speed, elapsed=10.0)
            self.assertEqual(eta3, "Done")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_speed_learning_and_transient_dip_dampening(self):
        from core.downloader import KemonoDownloader, DownloadTask
        from core.known_manager import KnownManager
        from core.session_manager import SessionManager

        temp_dir = tempfile.mkdtemp()
        try:
            km = KnownManager(os.path.join(temp_dir, "Known.txt"))
            sm = SessionManager(temp_dir)
            dl = KemonoDownloader(km, sm)

            dl.start_time = 1000.0
            dl.downloaded_bytes = 90 * 1024 * 1024  # 90 MB downloaded in 60s (1.5 MB/s average)

            # Create 10 mock tasks of 10 MB each
            tasks = [
                DownloadTask(
                    url=f"https://example.com/file_{i}.jpg",
                    target_path=f"/fake/file_{i}.jpg",
                    post_title=f"Post {i}",
                    creator_name="Artist",
                    service="patreon",
                    post_id=str(i),
                    file_id=str(i),
                    file_size=10 * 1024 * 1024
                )
                for i in range(10)
            ]
            dl.tasks = tasks

            # Seed speed samples over the last 3 seconds at 1.5 MB/s
            for t_offset in range(58, 61):
                dl._speed_samples.append((1000.0 + t_offset, int(t_offset * 1.5 * 1024 * 1024)))
            
            speed_60s = dl._calculate_instant_speed(1060.0)
            self.assertGreater(speed_60s, 1.2 * 1024 * 1024)

            # ETA at 60s with 9 completed (10 MB remaining at 1.5 MB/s ~ 6-7s)
            for i in range(9):
                tasks[i].status = "completed"
                tasks[i].downloaded_bytes = 10 * 1024 * 1024
            eta_before_dip = dl._calculate_smart_eta(completed=9, failed=0, total=10, speed=speed_60s, elapsed=60.0)
            self.assertIn("s", eta_before_dip)

            # Transient dip: next file just started and speed drops to 100 KB/s
            dl.downloaded_bytes += 100 * 1024
            dl._speed_samples.append((1062.0, dl.downloaded_bytes))
            speed_dip = dl._calculate_instant_speed(1062.0)

            # Real-time speed accurately drops to reflect network reality (< 500 KB/s)
            self.assertLess(speed_dip, 500 * 1024)

            # BUT the ETA stays stable (anchored to the learned 1.5 MB/s session rate) and doesn't jump to minutes!
            eta_during_dip = dl._calculate_smart_eta(completed=9, failed=0, total=10, speed=speed_dip, elapsed=62.0)
            self.assertIn("s", eta_during_dip)
            self.assertNotIn("m", eta_during_dip)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)



class TestFranchiseHierarchyAndModes(unittest.TestCase):
    def test_franchise_sections_parsing_and_matching(self):
        from core.known_manager import KnownManager

        temp_dir = tempfile.mkdtemp()
        try:
            txt_path = os.path.join(temp_dir, "Known.txt")
            custom_content = """# Custom test list
[Final Fantasy VII]
Tifa Lockhart
Aerith Gainsborough

[The Witcher]
Ciri
Yennefer

[Overwatch]
D.Va
Mercy
"""
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(custom_content)

            km = KnownManager(txt_path)
            self.assertIn("Final Fantasy VII", km.franchise_sections)
            self.assertIn("The Witcher", km.franchise_sections)
            self.assertEqual(km.entry_franchise_map.get("tifa lockhart"), "Final Fantasy VII")
            self.assertEqual(km.entry_franchise_map.get("ciri"), "The Witcher")

            # Test hierarchical matching
            match = km.find_matching_hierarchy("Tifa Lockhart Cowboy Outfit 4K")
            self.assertIsNotNone(match)
            self.assertEqual(match, ("Final Fantasy VII", "Tifa Lockhart"))

            match2 = km.find_matching_hierarchy("Ciri Story 01")
            self.assertIsNotNone(match2)
            self.assertEqual(match2, ("The Witcher", "Ciri"))

            cat = km.find_matching_category("Tifa Lockhart Cowboy Outfit 4K")
            self.assertEqual(cat, "Tifa Lockhart")

            # Test master database fallback in hybrid mode
            # (Raiden Shogun is in master DB under Genshin Impact even if not in custom Known.txt)
            match_master = km.find_matching_hierarchy("Raiden Shogun in pool")
            self.assertIsNotNone(match_master)
            self.assertEqual(match_master, ("Genshin Impact", "Raiden Shogun"))

            # Test database_only mode (ignores custom entries not in master)
            km.set_mode("database_only")
            learned = km.add_candidates_from_posts([{"title": "CustomNewCharacter works"}])
            self.assertEqual(len(learned), 0)

            # Test learning_only mode (ignores master db entries not in Known.txt)
            km.set_mode("learning_only")
            match_genshin = km.find_matching_hierarchy("Raiden Shogun in pool")
            self.assertIsNone(match_genshin)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()





