"""
RSS feed generator for Johnny的每日信息面包 podcast.
Self-hosted via GitHub Pages. No podcast platform needed.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# Podcast metadata
PODCAST_TITLE = "Johnny的每日信息面包"
PODCAST_AUTHOR = "Johnny Zhou"
PODCAST_DESCRIPTION = "信息超有料，小心别噎着。Johnny Zhou，NYU Stern大学生，每天用讲人话的方式精选全球政经科技新闻。政治/经济/科技/投资，轻松有趣但不失专业。"
PODCAST_LANGUAGE = "zh-CN"
PODCAST_IMAGE_URL = ""  # Set later once you have cover art
PODCAST_CATEGORY = "News"
PODCAST_SUBCATEGORY = "Daily News"


class RSSFeed:
    """
    Manage a self-hosted RSS podcast feed.
    Episodes are stored as mp3 files alongside the RSS XML.
    """

    def __init__(self, feed_dir: str, base_url: str):
        """
        feed_dir: local directory containing podcast.xml and mp3 files
        base_url: public URL where feed_dir is served, e.g. https://example.com/feed
        """
        self.feed_dir = Path(feed_dir)
        self.base_url = base_url.rstrip("/")
        self.xml_path = self.feed_dir / "podcast.xml"

    def add_episode(
        self,
        audio_path: str,
        title: str,
        description: str = "",
        pub_date: str | None = None,
    ) -> str:
        """
        Add a new episode to the RSS feed.

        Returns the public URL of the episode's mp3.
        """
        audio_filename = os.path.basename(audio_path)
        audio_url = f"{self.base_url}/{audio_filename}"

        # Copy mp3 into feed directory
        import shutil
        self.feed_dir.mkdir(parents=True, exist_ok=True)
        dest = self.feed_dir / audio_filename
        shutil.copy2(audio_path, dest)
        logger.info("Copied mp3 to feed: %s", dest)

        # Get file info
        file_size = os.path.getsize(audio_path)
        duration = self._get_duration(audio_path)

        if pub_date is None:
            pub_date = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")

        # Build or update the RSS XML
        rss = self._load_or_create(pub_date)

        # Check if this episode already exists (by filename)
        for item in rss.findall(".//item"):
            enclosure = item.find("enclosure")
            if enclosure is not None and audio_filename in (enclosure.get("url") or ""):
                logger.info("Episode already exists in feed: %s", audio_filename)
                return audio_url

        # Create new item
        item = ET.SubElement(rss.find("channel"), "item")
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "description").text = description
        ET.SubElement(item, "pubDate").text = pub_date
        ET.SubElement(item, "guid", isPermaLink="false").text = audio_url

        # Enclosure (audio file)
        ET.SubElement(item, "enclosure", {
            "url": audio_url,
            "length": str(file_size),
            "type": "audio/mpeg",
        })

        # iTunes: duration (HH:MM:SS)
        mm, ss = divmod(int(duration), 60)
        hh, mm = divmod(mm, 60)
        ET.SubElement(item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}duration").text = f"{hh:02d}:{mm:02d}:{ss:02d}"

        # iTunes: episode type (full)
        ET.SubElement(item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}episodeType").text = "full"

        # iTunes: summary
        ET.SubElement(item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}summary").text = description[:4000]

        # Clean up: keep max 60 episodes
        items = rss.findall(".//item")
        if len(items) > 60:
            for old_item in items[:-60]:
                rss.find("channel").remove(old_item)
                # Also remove the old mp3 file
                old_enclosure = old_item.find("enclosure")
                if old_enclosure is not None:
                    old_url = old_enclosure.get("url", "")
                    old_file = self.feed_dir / os.path.basename(old_url)
                    if old_file.exists():
                        old_file.unlink()
                        logger.info("Removed old episode: %s", old_file.name)

        # Write
        self._write_xml(rss)
        logger.info("RSS feed updated with: %s", title)
        return audio_url

    def _load_or_create(self, build_date: str) -> ET.Element:
        """Load existing RSS or create a new one."""
        if self.xml_path.exists():
            try:
                tree = ET.parse(str(self.xml_path))
                return tree.getroot()
            except Exception:
                logger.warning("Failed to parse existing RSS, creating new one")

        return self._create_rss(build_date)

    def _create_rss(self, build_date: str) -> ET.Element:
        """Create a new RSS 2.0 + iTunes podcast feed."""
        rss = ET.Element("rss", {
            "version": "2.0",
            "xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
            "xmlns:content": "http://purl.org/rss/1.0/modules/content/",
        })

        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text = PODCAST_TITLE
        ET.SubElement(channel, "link").text = self.base_url
        ET.SubElement(channel, "language").text = PODCAST_LANGUAGE
        ET.SubElement(channel, "description").text = PODCAST_DESCRIPTION
        ET.SubElement(channel, "lastBuildDate").text = build_date
        ET.SubElement(channel, "author").text = PODCAST_AUTHOR

        # iTunes tags
        ET.SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}author").text = PODCAST_AUTHOR
        ET.SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}summary").text = PODCAST_DESCRIPTION
        ET.SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}explicit").text = "no"

        if PODCAST_IMAGE_URL:
            ET.SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}image", href=PODCAST_IMAGE_URL)

        # Category
        cat = ET.SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}category", text=PODCAST_CATEGORY)
        ET.SubElement(cat, "{http://www.itunes.com/dtds/podcast-1.0.dtd}category", text=PODCAST_SUBCATEGORY)

        return rss

    def _write_xml(self, rss: ET.Element) -> None:
        """Save the RSS XML."""
        self.feed_dir.mkdir(parents=True, exist_ok=True)
        raw = ET.tostring(rss, encoding="unicode")
        # Add XML declaration and pretty-print manually
        lines = raw.replace("><", ">\n<").split("\n")
        self.xml_path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + raw)

    def _get_duration(self, audio_path: str) -> float:
        """Get audio duration in seconds using ffprobe."""
        import json
        import subprocess
        try:
            result = subprocess.run([
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", audio_path,
            ], check=True, capture_output=True, text=True, timeout=10)
            info = json.loads(result.stdout)
            return float(info["format"]["duration"])
        except Exception:
            return 0.0
