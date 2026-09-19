"""
Audio Metadata Tagging Engine
Embeds creator name, post title, album info, and dates into downloaded audio files
(MP3, M4A, FLAC, OGG, Opus, WAV) for seamless organization in music players.
"""

import os
import re
from typing import Optional

from core.logger import logger

try:
    import mutagen
    from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TPE1, TALB, TDRC, COMM
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    from mutagen.oggvorbis import OggVorbis
    from mutagen.wave import WAVE
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


class AudioTagger:
    """Writes metadata tags into audio files."""

    SUPPORTED_EXTS = {".mp3", ".flac", ".m4a", ".mp4", ".aac", ".ogg", ".opus", ".wav"}

    @classmethod
    def is_supported(cls, file_path: str) -> bool:
        if not file_path:
            return False
        _, ext = os.path.splitext(file_path.lower())
        return ext in cls.SUPPORTED_EXTS

    @classmethod
    def tag_audio_file(
        cls,
        file_path: str,
        artist: str = "",
        title: str = "",
        album: str = "",
        date: str = "",
        comment: str = ""
    ) -> bool:
        """
        Embeds metadata tags into an audio file.

        :param file_path: Full filesystem path to the audio file.
        :param artist: Creator or artist name (e.g. account name).
        :param title: Song/track title (e.g. post title).
        :param album: Album name (e.g. post title or creator).
        :param date: Release year or date string.
        :param comment: Post URL or comments.
        :return: True if tagging succeeded or was unnecessary, False if tagging failed.
        """
        if not MUTAGEN_AVAILABLE:
            logger.debug("mutagen library not installed; skipping audio tagging", category="audio")
            return False

        if not file_path or not os.path.exists(file_path):
            return False

        _, ext = os.path.splitext(file_path.lower())
        if ext not in cls.SUPPORTED_EXTS:
            return False

        # Clean strings
        artist = str(artist or "").strip()
        title = str(title or "").strip()
        album = str(album or "").strip()
        date = str(date or "").strip()
        comment = str(comment or "").strip()

        # Extract 4-digit year from date if formatted as ISO date
        year = ""
        if date:
            year_match = re.match(r"^(\d{4})", date)
            if year_match:
                year = year_match.group(1)

        # Fallback album to artist if not specified
        if not album and artist:
            album = artist

        try:
            if ext == ".mp3":
                return cls._tag_mp3(file_path, artist, title, album, year or date, comment)
            elif ext == ".flac":
                return cls._tag_flac(file_path, artist, title, album, year or date, comment)
            elif ext in (".m4a", ".mp4", ".aac"):
                return cls._tag_mp4(file_path, artist, title, album, year or date, comment)
            elif ext in (".ogg", ".opus"):
                return cls._tag_ogg(file_path, artist, title, album, year or date, comment)
            elif ext == ".wav":
                return cls._tag_wav(file_path, artist, title, album, year or date, comment)
        except Exception as e:
            logger.debug(f"Audio tagging notice for '{os.path.basename(file_path)}': {e}", category="audio")
            return False

        return False

    @classmethod
    def _tag_mp3(cls, path: str, artist: str, title: str, album: str, date: str, comment: str) -> bool:
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            tags = ID3()

        if artist:
            tags.add(TPE1(encoding=3, text=[artist]))
        if title and not tags.get("TIT2"):
            tags.add(TIT2(encoding=3, text=[title]))
        if album and not tags.get("TALB"):
            tags.add(TALB(encoding=3, text=[album]))
        if date and not tags.get("TDRC"):
            tags.add(TDRC(encoding=3, text=[date]))
        if comment and not tags.get("COMM::eng"):
            tags.add(COMM(encoding=3, lang="eng", desc="", text=[comment]))

        # Save as ID3v2.3 for maximum compatibility with Windows Explorer and music players
        tags.save(path, v2_version=3)
        return True

    @classmethod
    def _tag_flac(cls, path: str, artist: str, title: str, album: str, date: str, comment: str) -> bool:
        audio = FLAC(path)
        if artist:
            audio["artist"] = [artist]
        if title and "title" not in audio:
            audio["title"] = [title]
        if album and "album" not in audio:
            audio["album"] = [album]
        if date and "date" not in audio:
            audio["date"] = [date]
        if comment and "comment" not in audio:
            audio["comment"] = [comment]
        audio.save()
        return True

    @classmethod
    def _tag_mp4(cls, path: str, artist: str, title: str, album: str, date: str, comment: str) -> bool:
        audio = MP4(path)
        if audio.tags is None:
            audio.add_tags()

        if artist:
            audio["\xa9ART"] = [artist]
        if title and "\xa9nam" not in audio:
            audio["\xa9nam"] = [title]
        if album and "\xa9alb" not in audio:
            audio["\xa9alb"] = [album]
        if date and "\xa9day" not in audio:
            audio["\xa9day"] = [date]
        if comment and "\xa9cmt" not in audio:
            audio["\xa9cmt"] = [comment]
        audio.save()
        return True

    @classmethod
    def _tag_ogg(cls, path: str, artist: str, title: str, album: str, date: str, comment: str) -> bool:
        audio = mutagen.File(path)
        if audio is None:
            return False
        if artist:
            audio["artist"] = [artist]
        if title and "title" not in audio:
            audio["title"] = [title]
        if album and "album" not in audio:
            audio["album"] = [album]
        if date and "date" not in audio:
            audio["date"] = [date]
        if comment and "comment" not in audio:
            audio["comment"] = [comment]
        audio.save()
        return True

    @classmethod
    def _tag_wav(cls, path: str, artist: str, title: str, album: str, date: str, comment: str) -> bool:
        audio = WAVE(path)
        if audio.tags is None:
            audio.add_tags()
        if artist:
            audio.tags.add(TPE1(encoding=3, text=[artist]))
        if title and not audio.tags.get("TIT2"):
            audio.tags.add(TIT2(encoding=3, text=[title]))
        if album and not audio.tags.get("TALB"):
            audio.tags.add(TALB(encoding=3, text=[album]))
        audio.save()
        return True
