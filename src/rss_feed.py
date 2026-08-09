"""
RSS 2.0 + iTunes podcast feed generator.
Outputs clean XML manually (avoids ElementTree namespace quirks).
"""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)

PODCAST_TITLE = "Johnny的每日信息面包"
PODCAST_AUTHOR = "Johnny Zhou"
PODCAST_DESCRIPTION = (
    "信息超有料，小心别噎着。Johnny Zhou，NYU Stern大学生，"
    "每天用讲人话的方式精选全球政经科技新闻。"
    "政治/经济/科技/投资，轻松有趣但不失专业。"
)
PODCAST_LANGUAGE = "zh-CN"
PODCAST_CATEGORY = "News"
PODCAST_SUBCATEGORY = "Daily News"
PODCAST_OWNER_EMAIL = "zhoutaihuangniubi@gmail.com"
# Must be a publicly accessible HTTPS URL, 1400x1400 to 3000x3000 pixels
PODCAST_IMAGE_URL = "https://zhoutaihuangniubi.github.io/JohnnyZhou2/cover.jpg"


class RSSFeed:
    def __init__(self, feed_dir: str, base_url: str):
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
        audio_filename = os.path.basename(audio_path)
        audio_url = f"{self.base_url}/{audio_filename}"

        self.feed_dir.mkdir(parents=True, exist_ok=True)
        dest = self.feed_dir / audio_filename
        shutil.copy2(audio_path, dest)
        logger.info("Copied mp3 to feed: %s", dest)

        file_size = os.path.getsize(audio_path)
        duration = self._get_duration(audio_path)
        if pub_date is None:
            pub_date = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")

        mm, ss = divmod(int(duration), 60)
        hh, mm = divmod(mm, 60)
        duration_str = f"{hh:02d}:{mm:02d}:{ss:02d}"

        item_xml = f"""
    <item>
      <title>{escape(title)}</title>
      <description>{escape(description)}</description>
      <itunes:summary>{escape(description[:4000])}</itunes:summary>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:duration>{duration_str}</itunes:duration>
      <enclosure url="{escape(audio_url)}" length="{file_size}" type="audio/mpeg"/>
      <pubDate>{pub_date}</pubDate>
      <guid isPermaLink="false">{escape(audio_url)}</guid>
    </item>"""

        if self.xml_path.exists():
            content = self.xml_path.read_text()
            content = content.replace("</channel>", f"{item_xml}\n</channel>")
        else:
            content = self._build_full_feed(item_xml, pub_date)

        # Keep only last 60 episodes, remove old mp3s
        item_count = content.count("<item>")
        if item_count > 60:
            # Remove oldest items (first ones after <channel>)
            import re
            items = list(re.finditer(r'<item>.*?</item>', content, re.DOTALL))
            for old_match in items[:item_count - 60]:
                content = content.replace(old_match.group(), "", 1)
                # Extract mp3 filename from the removed item and delete it
                enclosure_match = re.search(r'enclosure url="[^"]*/([^"]+\.mp3)"', old_match.group())
                if enclosure_match:
                    old_mp3 = self.feed_dir / enclosure_match.group(1)
                    if old_mp3.exists():
                        old_mp3.unlink()

        self.xml_path.write_text(content)
        logger.info("RSS feed updated: %s", title)
        return audio_url

    def _build_full_feed(self, items_xml: str, build_date: str) -> str:
        img_tag = ""
        if PODCAST_IMAGE_URL:
            img_tag = f"""
    <image>
      <url>{escape(PODCAST_IMAGE_URL)}</url>
      <title>{escape(PODCAST_TITLE)}</title>
      <link>{escape(self.base_url)}</link>
    </image>
    <itunes:image href="{escape(PODCAST_IMAGE_URL)}"/>"""

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
  <title>{escape(PODCAST_TITLE)}</title>
  <link>{escape(self.base_url)}</link>
  <language>{PODCAST_LANGUAGE}</language>
  <description>{escape(PODCAST_DESCRIPTION)}</description>
  <lastBuildDate>{build_date}</lastBuildDate>
  <itunes:author>{escape(PODCAST_AUTHOR)}</itunes:author>
  <itunes:summary>{escape(PODCAST_DESCRIPTION)}</itunes:summary>
  <itunes:explicit>no</itunes:explicit>
  <itunes:owner>
    <itunes:name>{escape(PODCAST_AUTHOR)}</itunes:name>
    <itunes:email>{escape(PODCAST_OWNER_EMAIL)}</itunes:email>
  </itunes:owner>
  <itunes:category text="{PODCAST_CATEGORY}">
    <itunes:category text="{PODCAST_SUBCATEGORY}"/>
  </itunes:category>{img_tag}
{items_xml}
</channel>
</rss>
"""

    def _get_duration(self, audio_path: str) -> float:
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
