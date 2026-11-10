"""Tests for Issue #43:
1. UI cyclic freezing during AV1 compression fixed via BELOW_NORMAL_PRIORITY_CLASS and safe thread limiting.
2. Custom compression presets (SVT-AV1, x265, x264), Opus audio codec support, and custom FFmpeg arguments.
3. Test preset validation (validate_ffmpeg_settings & testCompressionPreset).
4. cum.st canonical creator and post URLs in task construction, post_info.txt, and metadata.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QObject

from bridge.decompressor_bridge import DecompressorBridge
from core.downloader import KemonoDownloader
from core.filter_engine import FilterOptions
from services.ffmpeg_manager import find_ffmpeg
from services.media_compressor import (
    CompressResult,
    CompressSettings,
    _BELOW_NORMAL_PRIORITY,
    _CREATE_NO_WINDOW,
    get_safe_encoder_threads,
    is_encoder_supported,
    select_video_encoder,
    validate_ffmpeg_settings,
    video_command,
)


class DummyWatchlistManager(QObject):
    pass


class TestIssue43Fixes(unittest.TestCase):
    def setUp(self):
        self.ffmpeg = find_ffmpeg() or "ffmpeg.exe"

    def test_safe_encoder_threads_leaves_cores_free(self):
        """Ensures that software encoding leaves at least 1-2 cores free for the OS and UI."""
        with patch("os.cpu_count", return_value=16):
            self.assertEqual(get_safe_encoder_threads(), 14)
        with patch("os.cpu_count", return_value=8):
            self.assertEqual(get_safe_encoder_threads(), 6)
        with patch("os.cpu_count", return_value=4):
            self.assertEqual(get_safe_encoder_threads(), 3)
        with patch("os.cpu_count", return_value=2):
            self.assertEqual(get_safe_encoder_threads(), 1)

    def test_ffmpeg_encode_priority_below_normal(self):
        """Verifies that FFmpeg subprocess is launched with BELOW_NORMAL_PRIORITY_CLASS."""
        from services.media_compressor import _run_ffmpeg_encode

        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.stdout = []
            mock_proc.stderr = MagicMock()
            mock_proc.stderr.read.return_value = ""
            mock_proc.returncode = 0
            mock_proc.wait.return_value = 0
            mock_popen.return_value = mock_proc

            _run_ffmpeg_encode(["ffmpeg", "-version"], "tmp.mp4", 10.0, None, None, None)

            self.assertEqual(mock_popen.call_count, 1)
            if sys.platform == "win32":
                creationflags = mock_popen.call_args[1].get("creationflags", 0)
                self.assertTrue(creationflags & _BELOW_NORMAL_PRIORITY)
                self.assertTrue(creationflags & _CREATE_NO_WINDOW)

    def test_select_video_encoder_svtav1_presets_and_threads(self):
        """Verifies SVT-AV1 preset options, thread limits, and lp parameter."""
        # Auto/Balanced: preset 6
        enc, args, cpu_enc, cpu_args = select_video_encoder(self.ffmpeg, "av1", quality=75, hw_accel="cpu", preset="auto")
        self.assertEqual(enc, "libsvtav1")
        self.assertIn("-preset", args)
        idx = args.index("-preset")
        self.assertEqual(args[idx + 1], "6")
        self.assertIn("-threads", args)
        self.assertIn("-svtav1-params", args)

        # Fast: preset 8
        enc, args, _, _ = select_video_encoder(self.ffmpeg, "av1", quality=75, hw_accel="cpu", preset="fast")
        idx = args.index("-preset")
        self.assertEqual(args[idx + 1], "8")

        # Quality: preset 4
        enc, args, _, _ = select_video_encoder(self.ffmpeg, "av1", quality=75, hw_accel="cpu", preset="quality")
        idx = args.index("-preset")
        self.assertEqual(args[idx + 1], "4")

    def test_video_command_opus_audio_and_custom_args(self):
        """Verifies Opus audio encoding and user-defined extra FFmpeg arguments."""
        with patch("services.media_compressor.is_encoder_supported", return_value=True):
            cmd = video_command(
                self.ffmpeg, "in.mp4", "out.mp4", "av1", 75, "aac",
                audio_setting="opus",
                custom_video_args=["-maxrate", "1500k", "-bufsize", "3000k", "-pix_fmt", "yuv420p10le"],
                preset="quality",
                hw_accel="cpu"
            )
            # Opus flags
            self.assertIn("-c:a", cmd)
            idx_a = cmd.index("-c:a")
            self.assertEqual(cmd[idx_a + 1], "libopus")
            self.assertIn("-vbr", cmd)
            # Custom video args
            self.assertIn("-maxrate", cmd)
            self.assertIn("1500k", cmd)
            self.assertIn("-bufsize", cmd)
            self.assertIn("3000k", cmd)
            self.assertIn("-pix_fmt", cmd)
            # Custom pix_fmt should replace default yuv420p
            self.assertIn("yuv420p10le", cmd)
            self.assertEqual(cmd.count("-pix_fmt"), 1)

    def test_validate_ffmpeg_settings_success(self):
        """Tests live validation of settings when ffmpeg is available."""
        if not find_ffmpeg():
            self.skipTest("FFmpeg binary not present for live test.")
        s = CompressSettings(
            video_format="h264",
            video_quality=75,
            video_hwaccel="cpu",
            video_preset="fast",
            audio_codec="aac",
            ffmpeg=self.ffmpeg
        )
        ok, msg = validate_ffmpeg_settings(self.ffmpeg, s)
        self.assertTrue(ok)
        self.assertIn("Verified", msg)

    def test_decompressor_bridge_test_compression_preset(self):
        """Verifies DecompressorBridge exposes testCompressionPreset slot with result dict."""
        wm = DummyWatchlistManager()
        bridge = DecompressorBridge(wm)
        bridge.videoFormat = "h264"
        bridge.videoHwAccel = "cpu"
        bridge.videoPreset = "fast"
        bridge.audioCodec = "aac"

        res = bridge.testCompressionPreset()
        self.assertIsInstance(res, dict)
        self.assertIn("success", res)
        self.assertIn("message", res)

    def test_cumst_canonical_creator_and_post_urls(self):
        """Verifies that cum.st tasks and post_info.txt use canonical https://cum.st/creators/... URLs."""
        dl = KemonoDownloader(known_manager=MagicMock(), session_manager=MagicMock())
        posts = [{
            "id": "66a73bda",
            "title": "VIDEO CREAM PIE",
            "published": "2026-09-30T12:00:00",
            "user": "268096296",
            "file": {"name": "video.mp4", "path": "/files/video.mp4"}
        }]
        opts = FilterOptions()
        tasks = dl.build_tasks_from_posts(
            posts=posts,
            creator_name="Filou_fitt",
            service="onlyfans",
            domain="cum.st",
            base_dir="C:/Downloads",
            options=opts,
            user_id="268096296"
        )
        self.assertEqual(len(tasks), 1)
        # Check task post_url
        self.assertEqual(tasks[0].post_url, "https://cum.st/creators/onlyfans/268096296/post/66a73bda")

    def test_cumst_canonical_dm_post_url(self):
        """Verifies that cum.st DM posts correctly format /dm/ URLs."""
        dl = KemonoDownloader(known_manager=MagicMock(), session_manager=MagicMock())
        posts = [{
            "id": "dm12345",
            "title": "Private Message",
            "published": "2026-09-30T12:00:00",
            "type": "dm",
            "file": {"name": "dm.mp4", "path": "/files/dm.mp4"}
        }]
        opts = FilterOptions()
        tasks = dl.build_tasks_from_posts(
            posts=posts,
            creator_name="Filou_fitt",
            service="onlyfans",
            domain="cum.st",
            base_dir="C:/Downloads",
            options=opts,
            user_id="268096296"
        )
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].post_url, "https://cum.st/creators/onlyfans/268096296/dm/dm12345")


if __name__ == "__main__":
    unittest.main()
