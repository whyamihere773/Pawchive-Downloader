import os
import re
from typing import List, Tuple

class BatchLoader:
    """
    Parses and sanitizes batches of URLs from raw text strings or files.
    """

    @staticmethod
    def parse_urls_from_text(raw_text: str) -> List[str]:
        """
        Extracts valid HTTP/HTTPS URLs from multi-line text, ignoring comments and whitespace.
        """
        if not raw_text:
            return []

        urls = []
        for line in raw_text.splitlines():
            cleaned = line.strip()
            # Ignore empty lines and comment lines
            if not cleaned or cleaned.startswith("#") or cleaned.startswith("//"):
                continue

            # Extract URL portion if line has annotations
            match = re.search(r'https?://[^\s"\'<>]+', cleaned)
            if match:
                urls.append(match.group(0).rstrip(".,;!?'\")>]}"))
            elif "nhentai.net/g/" in cleaned or "saint2.su" in cleaned:
                urls.append(f"https://{cleaned.lstrip('/')}")

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        return deduped

    @classmethod
    def load_urls_from_file(cls, file_path: str) -> Tuple[List[str], str]:
        """
        Reads a batch URL text file.
        Returns: (urls: List[str], error_message: str)
        """
        if not os.path.exists(file_path):
            return [], f"File not found: {file_path}"

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            urls = cls.parse_urls_from_text(content)
            return urls, ""
        except Exception as e:
            return [], f"Error reading batch file: {e}"
