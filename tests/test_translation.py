import unittest
from bridge.translation_manager import TranslationManager

class TestTranslationManager(unittest.TestCase):
    def setUp(self):
        self.tm = TranslationManager()
        self.tm.setLanguage("zh_CN")

    def test_adaptive_threading_translation(self):
        log_msg = "⚡ [Adaptive Threading] Connection stable. Scaling up concurrency to 8/24 threads (ceiling: 24)..."
        translated = self.tm.translateLog(log_msg, "INFO")
        self.assertNotEqual(translated, log_msg)
        self.assertIn("8/24", translated)
        self.assertIn("24", translated)

    def test_chunked_download_translation_with_and_without_spaces(self):
        msg_no_indent = "⚡ Activating 4-part parallel chunked download for test.mp4 (500 MB)"
        msg_with_indent = "  ⚡ Activating 4-part parallel chunked download for test.mp4 (500 MB)"
        
        t1 = self.tm.translateLog(msg_no_indent, "INFO")
        t2 = self.tm.translateLog(msg_with_indent, "INFO")
        
        self.assertNotEqual(t1, msg_no_indent)
        self.assertIn("test.mp4", t1)
        self.assertIn("500 MB", t1)
        self.assertIn("test.mp4", t2)
        self.assertIn("500 MB", t2)

    def test_error_logs_not_translated(self):
        error_msg = "Error downloading test.png: connection timed out"
        res = self.tm.translateLog(error_msg, "ERROR")
        self.assertEqual(res, error_msg)

    def test_english_passthrough(self):
        self.tm.setLanguage("en")
        msg = "⚡ [Adaptive Threading] Connection stable. Scaling up concurrency to 8/24 threads (ceiling: 24)..."
        res = self.tm.translateLog(msg, "INFO")
        self.assertEqual(res, msg)

if __name__ == "__main__":
    unittest.main()
