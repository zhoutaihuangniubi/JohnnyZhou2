#!/usr/bin/env python3
"""
每日政经速览 - Automated Daily Podcast Pipeline

Flow:
  1. Fetch news from NewsAPI + NYTimes
  2. Claude selects top articles & generates Chinese podcast script
  3. edge-tts converts script to speech
  4. Compose final mp3
  5. Upload to Buzzsprout (or self-hosted RSS)

Usage:
  python main.py              # full pipeline
  python main.py --dry-run    # generate mp3 only, skip upload
  python main.py --date 2026-05-14  # use specific date for title
"""

import argparse
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from config import load_config
from src.news_fetcher import NewsFetcher
from src.summarizer import Summarizer
from src.tts_generator import generate_speech
from src.audio_processor import generate_transition_sound, compose_segments, get_audio_duration_seconds
from src.rss_feed import RSSFeed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("podcast")


def main():
    parser = argparse.ArgumentParser(description="每日政经速览 Podcast Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Generate mp3 locally, skip upload")
    parser.add_argument("--mock", action="store_true", help="Use sample news data (no API keys needed)")
    parser.add_argument("--date", type=str, help="Override date (YYYY-MM-DD)")
    args = parser.parse_args()

    config = load_config()
    env = config["_env"]

    # --- Validate required keys ---
    ai_provider = config["ai"]["provider"]
    missing = []
    if ai_provider == "claude" and not env.get("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if ai_provider == "deepseek" and not env.get("DEEPSEEK_API_KEY"):
        missing.append("DEEPSEEK_API_KEY")
    if not args.mock and not env.get("NEWSAPI_KEY") and not env.get("NYTIMES_API_KEY"):
        missing.append("NEWSAPI_KEY or NYTIMES_API_KEY (at least one)")
    if missing:
        logger.error("Missing env vars: %s. Set them in .env file.", ", ".join(missing))
        sys.exit(1)

    today = args.date or datetime.now().strftime("%Y-%m-%d")
    today_cn = _format_date_cn(args.date) if args.date else _format_date_cn()
    output_dir = Path(config["output"]["directory"])
    output_dir.mkdir(parents=True, exist_ok=True)
    final_audio = str(output_dir / f"podcast_{today}.mp3")

    # === Step 1: Fetch News ===
    if args.mock:
        logger.info("=== Step 1: Using mock news data ===")
        articles = _mock_articles()
    else:
        logger.info("=== Step 1: Fetching news ===")
        fetcher = NewsFetcher(
            newsapi_key=env["NEWSAPI_KEY"] or "",
            nytimes_key=env["NYTIMES_API_KEY"] or "",
            sources=config["news"]["sources"],
            proxy=env.get("HTTP_PROXY") or "",
        )
        articles = fetcher.fetch_all(max_articles=config["news"]["max_articles_to_fetch"])

        if not articles:
            logger.error("No articles fetched. Check API keys and network. Try --mock for demo.")
            sys.exit(1)
    logger.info("Got %d articles", len(articles))

    # === Step 2: AI Summarization ===
    logger.info("=== Step 2: Generating podcast script with %s ===", ai_provider)
    ai_key = env.get("DEEPSEEK_API_KEY") if ai_provider == "deepseek" else env.get("ANTHROPIC_API_KEY")
    summarizer = Summarizer.create(
        provider=ai_provider,
        api_key=ai_key,
        model=config["ai"]["model"],
        max_tokens=config["ai"].get("max_tokens", 8192),
    )
    result = summarizer.generate_script(
        articles,
        select_n=config["news"]["articles_to_select"],
    )

    title = result.get("title", f"Johnny的每日信息面包 - {today_cn}")
    articles_selected = result.get("articles_selected", [])
    if not articles_selected:
        logger.error("AI returned empty articles_selected. Check script generation.")
        sys.exit(1)

    logger.info("Script title: %s", title)
    logger.info("Selected %d articles", len(articles_selected))

    # === Save script & APA references (same run, guaranteed sync) ===
    _save_script(result, articles, output_dir, today, today_cn)

    # === Step 3: Generate TTS for intro, each article, outro ===
    logger.info("=== Step 3: Generating speech per segment ===")
    tts_cfg = config["tts"]
    intro_template = config["podcast"]["intro_template"]
    intro = intro_template.format(date=today_cn)
    outro = config["podcast"]["outro_text"]

    audio_segments: list[str] = []

    # Intro
    intro_path = str(output_dir / f"intro_{today}.mp3")
    generate_speech(intro, intro_path, voice=tts_cfg["voice"], speed=tts_cfg["speed"],
                    openai_api_key=env.get("OPENAI_API_KEY", ""),
                    fish_audio_key=env.get("FISH_AUDIO_API_KEY") or "")
    audio_segments.append(intro_path)

    # Each article (with 5s pause between segments to avoid Fish Audio rate limit)
    for idx, article in enumerate(articles_selected):
        text = article.get("summary_cn", "")
        if not text:
            continue
        seg_path = str(output_dir / f"news_{today}_{idx}.mp3")
        if idx > 0:
            import time
            time.sleep(5)
        generate_speech(text, seg_path, voice=tts_cfg["voice"], speed=tts_cfg["speed"],
                        openai_api_key=env.get("OPENAI_API_KEY", ""),
                        fish_audio_key=env.get("FISH_AUDIO_API_KEY") or "")
        audio_segments.append(seg_path)

    # Outro (pause before to avoid rate limit)
    import time
    time.sleep(5)
    outro_path = str(output_dir / f"outro_{today}.mp3")
    generate_speech(outro, outro_path, voice=tts_cfg["voice"], speed=tts_cfg["speed"],
                    openai_api_key=env.get("OPENAI_API_KEY", ""),
                    fish_audio_key=env.get("FISH_AUDIO_API_KEY") or "")
    audio_segments.append(outro_path)

    logger.info("Generated %d audio segments", len(audio_segments))

    # === Step 4: Compose final audio with transitions ===
    logger.info("=== Step 4: Composing final podcast mp3 ===")
    # Use user-provided transition sound if available, otherwise generate one
    transition_path = _resolve_transition(output_dir)

    compose_segments(
        audio_segments,
        final_audio,
        transition_path=transition_path,
    )
    duration_sec = get_audio_duration_seconds(final_audio)
    logger.info("Final duration: %.1f seconds (%.1f minutes)", duration_sec, duration_sec / 60)

    # === Step 5: Upload (RSS self-hosted) ===
    show_notes = _build_show_notes(result, articles)
    notes_path = output_dir / f"podcast_{today}_shownotes.txt"
    notes_path.write_text(show_notes)

    if args.dry_run:
        logger.info("=== Dry run: skipping upload. Audio saved to %s ===", final_audio)
        logger.info("Show notes saved: %s", notes_path)
    else:
        logger.info("=== Step 5: Updating RSS feed ===")
        base_url = config["upload"].get("rss_base_url", "")
        if not base_url:
            logger.error("rss_base_url not configured. Skipping upload.")
        else:
            feed_dir = Path("feed")
            feed = RSSFeed(str(feed_dir), base_url)
            # Copy cover image to feed directory if available
            cover_path = Path("data/cover.jpg")
            if cover_path.exists():
                feed_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(cover_path), str(feed_dir / "cover.jpg"))
                logger.info("Cover image copied to feed")
            feed.add_episode(
                audio_path=final_audio,
                title=title,
                description=show_notes,
            )
            logger.info("RSS feed updated! Public URL: %s", base_url)

    # === Cleanup old files ===
    _cleanup_old(output_dir, config["output"]["keep_files_days"])

    logger.info("=== Done! ===")


def _format_date_cn(date_str: str | None = None) -> str:
    """Convert YYYY-MM-DD to Chinese date like '2026年5月18号'."""
    from datetime import datetime
    if date_str:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        dt = datetime.now()
    return f"{dt.year}年{dt.month}月{dt.day}号"


def _build_show_notes(result: dict, articles: list[dict]) -> str:
    """Build podcast show notes: one-line summaries + APA references."""
    from datetime import datetime
    selected = result.get("articles_selected", [])
    datestr = datetime.now().strftime("%Y, %B %d")

    lines = ["本期要点：", ""]
    for i, a in enumerate(selected):
        one_line = a.get("one_line", "") or a.get("title", "")
        lines.append(f"{i+1}. {one_line}")

    lines += ["", "---", "", "参考资料（APA）：", ""]
    for a in selected:
        src = a.get("source", "")
        t = a.get("title", "")
        url = a.get("original_url", "") or ""
        if not url:
            for orig in articles:
                if t[:50] in orig.get("title", ""):
                    url = orig.get("url", "") or url
                    break
        lines.append(f"{src}. ({datestr}). *{t}*. {url}")

    return "\n".join(lines)


def _save_script(result: dict, articles: list[dict], output_dir: Path, date_str: str, date_cn: str) -> str:
    """Save podcast script and APA references alongside the audio."""
    from datetime import datetime
    selected = result.get("articles_selected", [])
    title = result.get("title", f"Johnny的每日信息面包 - {date_cn}")
    datestr = datetime.now().strftime("%Y, %B %d")

    lines = [f"# {title}", "",
             f"*{date_cn}*  |  真实新闻数据", "",
             "---", "",
             "## 今日梗概", "",
             "> 以下为节目简介中的一句话摘要。", ""]

    for i, a in enumerate(selected):
        one_line = a.get("one_line", "") or a.get("title", "")
        lines.append(f"{i+1}. {one_line}")
    lines.append("")

    lines += ["---", "",
             "## 播客音频稿", "",
             "> 以下为语音朗读用稿，不含 APA 引用。APA 引用见文末。", ""]

    for i, a in enumerate(selected):
        lines.append(f"### {i+1}. {a.get('title', '')}")
        lines.append("")
        lines.append(a.get("summary_cn", ""))
        lines.append("")

    lines += ["---", "", "## APA References（节目简介下方）", ""]
    for a in selected:
        src = a.get("source", "")
        t = a.get("title", "")
        url = a.get("original_url", "") or ""
        # Try to find real URL from original articles
        if not url:
            for orig in articles:
                if t[:50] in orig.get("title", ""):
                    url = orig.get("url", "") or url
                    break
        lines.append(f"{src}. ({datestr}). *{t}*. {url}")
        lines.append("")

    content = "\n".join(lines)
    script_path = output_dir / f"podcast_{date_str}.md"
    script_path.write_text(content)
    logger.info("Script saved: %s", script_path)
    return str(script_path)


def _resolve_transition(output_dir: Path) -> str:
    """Find user-provided transition audio, convert if needed, or generate one."""
    # Check for mp3 version first (already converted)
    mp3_path = Path("data/transition.mp3")
    if mp3_path.exists():
        logger.info("Using custom transition: %s", mp3_path)
        return str(mp3_path.absolute())

    # Check for m4a and convert to mp3
    m4a_path = Path("data/transition.m4a")
    if m4a_path.exists():
        logger.info("Converting custom transition from m4a to mp3...")
        import subprocess
        subprocess.run([
            "ffmpeg", "-y", "-i", str(m4a_path.absolute()),
            "-b:a", "128k", str(mp3_path.absolute()),
        ], check=True, capture_output=True)
        logger.info("Using custom transition: %s", mp3_path)
        return str(mp3_path.absolute())

    # Fallback: generate a simple transition
    transition_path = str(output_dir / "transition.mp3")
    from src.audio_processor import generate_transition_sound
    generate_transition_sound(transition_path, duration=3.0)
    return transition_path


def _mock_articles() -> list[dict]:
    """Return sample news articles for testing the pipeline without real APIs."""
    return [
        {
            "title": "Federal Reserve Holds Rates Steady Amid Inflation Uncertainty",
            "description": "The Federal Reserve kept interest rates unchanged at its May meeting, citing persistent inflation concerns and mixed economic signals. Officials signaled they would maintain a cautious approach.",
            "source": "Reuters",
            "url": "",
        },
        {
            "title": "China and U.S. Trade Talks Resume After Months of Stalled Negotiations",
            "description": "Senior trade officials from Beijing and Washington met in Geneva to discuss tariff reductions and market access, marking the first high-level talks in over six months.",
            "source": "The New York Times",
            "url": "",
        },
        {
            "title": "Oil Prices Surge on Middle East Supply Concerns",
            "description": "Brent crude rose above $85 per barrel as geopolitical tensions in the Strait of Hormuz raised fears of supply disruptions, impacting global energy markets.",
            "source": "Bloomberg",
            "url": "",
        },
        {
            "title": "European Central Bank Hints at Rate Cut as Eurozone Growth Slows",
            "description": "ECB President Christine Lagarde indicated that easing could begin as early as July, responding to weaker-than-expected manufacturing data across the eurozone.",
            "source": "Financial Times",
            "url": "",
        },
        {
            "title": "AI Regulation Bill Gains Bipartisan Support in U.S. Senate",
            "description": "A landmark bill requiring safety assessments for advanced AI models advanced through committee with support from both parties, signaling growing urgency around tech governance.",
            "source": "The Washington Post",
            "url": "",
        },
        {
            "title": "Japan's Economy Returns to Growth on Strong Exports",
            "description": "Japan's GDP grew at an annualized 2.1% in Q1 2026, driven by robust auto and semiconductor exports, though domestic consumption remained weak.",
            "source": "The Economist",
            "url": "",
        },
        {
            "title": "Global Chip Shortage Eases but New Supply Chain Risks Emerge",
            "description": "While semiconductor supply has improved, industry leaders warn that geopolitical tensions and rare earth mineral dependencies could create new bottlenecks.",
            "source": "Bloomberg",
            "url": "",
        },
        {
            "title": "Supreme Court to Hear Major Antitrust Case Against Tech Giants",
            "description": "The U.S. Supreme Court agreed to review a case challenging the market dominance of major technology platforms, with implications for future regulation of the digital economy.",
            "source": "The Washington Post",
            "url": "",
        },
        {
            "title": "U.S. Dollar Weakens as Global Reserve Diversification Accelerates",
            "description": "Central banks in Asia and the Middle East increased holdings of alternative reserve currencies, pushing the dollar index to a six-month low.",
            "source": "Financial Times",
            "url": "",
        },
        {
            "title": "Climate Summit Reaches Landmark Agreement on Carbon Pricing",
            "description": "Nearly 150 nations agreed to a global carbon pricing framework at the UN climate summit, aiming to accelerate the transition away from fossil fuels.",
            "source": "Reuters",
            "url": "",
        },
        {
            "title": "Housing Affordability Crisis Deepens in Major U.S. Cities",
            "description": "New data shows home prices outpacing wage growth by a factor of three in cities like New York, San Francisco, and Miami, raising concerns about economic inequality.",
            "source": "The New York Times",
            "url": "",
        },
        {
            "title": "India Overtakes China as Fastest-Growing Major Economy",
            "description": "IMF data shows India's economy expanding at 7.2% annually, surpassing China's 4.8% growth rate, fueled by manufacturing investments and a young workforce.",
            "source": "The Economist",
            "url": "",
        },
    ]


def _cleanup_old(output_dir: Path, keep_days: int) -> None:
    """Remove audio files older than keep_days."""
    import time
    cutoff = time.time() - keep_days * 86400
    for f in output_dir.glob("*.mp3"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            logger.info("Cleaned up old file: %s", f.name)


if __name__ == "__main__":
    main()
