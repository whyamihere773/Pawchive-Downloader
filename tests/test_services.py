import unittest
import os
import tempfile
import shutil
from unittest.mock import MagicMock, patch

from services.multipart_downloader import download_multipart_file
from services.link_extractor import LinkExtractor
from services.text_exporter import TextExporter
from services.batch_loader import BatchLoader
from services.bunkr_client import fetch_bunkr_album
from services.erome_client import fetch_erome_album
from services.nhentai_client import fetch_nhentai_gallery
from core.parser import KemonoURLParser
from core.filter_engine import FilterEngine, FilterOptions, FilenameStyles

class TestServicesAndExpansion(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ── 1. Link Extractor Tests ───────────────────────────────────────────────
    def test_link_extractor_platforms(self):
        sample_html = """
        <p>Here is my Mega link: <a href="https://mega.nz/file/abc123XYZ#secretkey">Mega File</a></p>
        <p>Google Drive backup: https://drive.google.com/file/d/1A2B3C4D5E/view?usp=sharing</p>
        <p>Dropbox: https://www.dropbox.com/s/abcdef123456/art_pack.zip?dl=0</p>
        <p>Pixeldrain: https://pixeldrain.com/u/abc12345</p>
        <p>Catbox: https://files.catbox.moe/xyz789.png</p>
        <p>Bunkr: https://bunkr.is/a/myalbum123</p>
        <p>Erome: https://www.erome.com/a/album456</p>
        <p>nHentai: https://nhentai.net/g/999888/</p>
        """
        extracted = LinkExtractor.extract_links_from_text(sample_html)
        self.assertIn("mega", extracted)
        self.assertIn("gdrive", extracted)
        self.assertIn("dropbox", extracted)
        self.assertIn("pixeldrain", extracted)
        self.assertIn("catbox", extracted)
        self.assertIn("bunkr", extracted)
        self.assertIn("erome", extracted)
        self.assertIn("nhentai", extracted)

        flat = LinkExtractor.extract_all_flat(sample_html)
        self.assertGreaterEqual(len(flat), 8)

        formatted = LinkExtractor.format_export_text("Test Post", "Artist", extracted)
        self.assertIn("=== Test Post (Creator: Artist) ===", formatted)
        self.assertIn("[MEGA", formatted)

    # ── 2. Batch Loader Tests ─────────────────────────────────────────────────
    def test_batch_loader_text_and_file(self):
        raw_text = """
        # My favorite creators
        https://pawchive.pw/fanbox/user/68002596
        // Backup link
        https://kemono.su/patreon/user/12345
        https://coomer.su/onlyfans/user/alice
        https://bunkr.is/a/album123
        https://pawchive.pw/fanbox/user/68002596  # Duplicate should be removed
        """
        urls = BatchLoader.parse_urls_from_text(raw_text)
        self.assertEqual(len(urls), 4) # 4 unique URLs

        # Test loading from file
        batch_file = os.path.join(self.test_dir, "test_batch.txt")
        with open(batch_file, "w", encoding="utf-8") as f:
            f.write(raw_text)

        loaded_urls, err = BatchLoader.load_urls_from_file(batch_file)
        self.assertEqual(err, "")
        self.assertEqual(len(loaded_urls), 4)

    # ── 3. Text Exporter Tests ────────────────────────────────────────────────
    def test_text_exporter_txt(self):
        post = {
            "title": "Special 4K Artwork",
            "service": "fanbox",
            "user": "68002596",
            "published": "2026-08-31",
            "content": "<p>Thank you for your support!<br/>Here is the link.</p>"
        }
        comments = [
            {"commenter_name": "Fan1", "published": "2026-08-31", "content": "Awesome artwork!"},
            {"commenter_name": "Fan2", "published": "2026-08-31", "content": "Love the colors!"}
        ]
        target_path = os.path.join(self.test_dir, "post.txt")
        ok = TextExporter.export_post_to_txt(post, comments, target_path)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(target_path))

        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Special 4K Artwork", content)
        self.assertIn("Awesome artwork!", content)

    # ── 4. URL Parser Multi-Provider Tests ────────────────────────────────────
    def test_url_parser_extended_providers(self):
        # Bunkr
        p_bunkr = KemonoURLParser.parse("https://bunkr.is/a/albumXYZ123")
        self.assertTrue(p_bunkr.is_valid)
        self.assertEqual(p_bunkr.provider, "bunkr")
        self.assertTrue(p_bunkr.is_external_provider)

        # Erome
        p_erome = KemonoURLParser.parse("https://www.erome.com/a/eromeAbc")
        self.assertTrue(p_erome.is_valid)
        self.assertEqual(p_erome.provider, "erome")

        # nHentai
        p_nh = KemonoURLParser.parse("https://nhentai.net/g/123456/")
        self.assertTrue(p_nh.is_valid)
        self.assertEqual(p_nh.provider, "nhentai")
        self.assertEqual(p_nh.post_id, "123456")

    # ── 5. Filename Styling Tests ─────────────────────────────────────────────
    def test_filename_custom_styles(self):
        opts_default = FilterOptions(filename_style=FilenameStyles.POST_TITLE)
        self.assertEqual(
            FilterEngine.format_custom_filename("art.png", "My Art", "2026-08-31", 1, 1, opts_default),
            "art.png"
        )

        opts_date = FilterOptions(filename_style=FilenameStyles.DATE_POST_TITLE)
        self.assertEqual(
            FilterEngine.format_custom_filename("art.png", "My Art", "2026-08-31", 1, 1, opts_date),
            "2026-08-31 - My Art - art.png"
        )

        opts_seq = FilterOptions(filename_style=FilenameStyles.DATE_BASED)
        self.assertEqual(
            FilterEngine.format_custom_filename("art.png", "My Art", "2026-08-31", 5, 2, opts_seq),
            "2026-08-31_005_02.png"
        )

        opts_global = FilterOptions(filename_style=FilenameStyles.POST_TITLE_GLOBAL_NUMBERING)
        self.assertEqual(
            FilterEngine.format_custom_filename("art.png", "Chapter 1", "2026-08-31", 3, 4, opts_global),
            "003_Chapter 1_04.png"
        )

    # ── 6. File Size Skip Filter Tests ────────────────────────────────────────
    def test_file_size_skip_filter(self):
        # [200] in skip_words skips any file smaller than 200 MB
        opts = FilterOptions(skip_words="WIP, [200]", skip_scope="files")
        
        # 50 MB file -> should be skipped because 50 < 200
        keep, reason = FilterEngine.should_keep_file("clean_art.zip", opts, file_size=50 * 1024 * 1024)
        self.assertFalse(keep)
        self.assertIn("below minimum threshold", reason)

        # 300 MB file -> should be kept because 300 >= 200
        keep, reason = FilterEngine.should_keep_file("clean_art.zip", opts, file_size=300 * 1024 * 1024)
        self.assertTrue(keep)

    # ── 7. Comments Scope Filter Tests ────────────────────────────────────────
    def test_character_filter_comments_scope(self):
        opts = FilterOptions(characters="Tifa", character_scope="comments")
        post_match = {
            "title": "Generic Art Pack",
            "content": "Solo render",
            "comments_text": "Is that Tifa Lockhart in the background?"
        }
        post_nomatch = {
            "title": "Generic Art Pack",
            "content": "Solo render",
            "comments_text": "Nice drawings"
        }
        self.assertTrue(FilterEngine.should_keep_post(post_match, opts)[0])
    # ── 8. Third-Party Provider 429 Retry Tests ──────────────────────────────
    @patch("services.bunkr_client.requests.Session.get")
    def test_bunkr_429_retry_success(self, mock_get):
        mock_429 = MagicMock(status_code=429)
        mock_200 = MagicMock(status_code=200, text="<html><title>Sample Bunkr</title><a href='https://bunkr.is/v/test.mp4'>video</a></html>")
        mock_get.side_effect = [mock_429, mock_200]
        
        title, files = fetch_bunkr_album("https://bunkr.is/a/album123")
        self.assertEqual(title, "Sample Bunkr")
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["filename"], "test.mp4")

    @patch("services.erome_client.requests.Session.get")
    def test_erome_429_retry_success(self, mock_get):
        mock_429 = MagicMock(status_code=429)
        mock_200 = MagicMock(status_code=200, text='<html><title>Sample Erome</title><meta property="og:title" content="Sample Erome"><source src="https://s1.erome.com/video.mp4"></html>')
        mock_get.side_effect = [mock_429, mock_200]
        
        folder, files = fetch_erome_album("https://www.erome.com/a/abc123")
        self.assertIn("Sample Erome", folder)
        self.assertEqual(len(files), 1)

if __name__ == "__main__":
    unittest.main()
