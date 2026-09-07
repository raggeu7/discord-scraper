import asyncio
import json
import logging
import os
import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional

import discord
from discord.ext import commands
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("discord-scraper")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
TARGET_SITE_URL = os.getenv("TARGET_SITE_URL", "https://shaiid4u.co").strip().rstrip("/")
SEARCH_PATH = os.getenv("SEARCH_PATH", "/search").strip() or "/search"
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "&")
SCRAPE_TIMEOUT_SECONDS = max(5, int(os.getenv("SCRAPE_TIMEOUT_SECONDS", "30")))
MAX_QUERY_LENGTH = 300


@dataclass
class MediaResult:
    url: Optional[str] = None
    referer: Optional[str] = None
    kind: Optional[str] = None


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


def is_http_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def find_candidate_urls(value: object) -> list[str]:
    """Find ordinary HTTP(S) URLs in JSON-like data without assuming a fixed schema."""
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return re.findall(r"https?://[^\s\"'<>\\]+", text)


def choose_candidate(urls: list[str]) -> Optional[str]:
    keywords = ("embed", "player", "stream", "m3u8", "mp4", "/media/page/")
    for url in urls:
        if any(keyword in url.lower() for keyword in keywords):
            return url.rstrip(".,)")
    return None


async def scrape_media_stream(query_or_url: str) -> MediaResult:
    query_or_url = query_or_url.strip()
    if not query_or_url:
        raise ValueError("يجب إدخال اسم أو رابط صالح.")
    if len(query_or_url) > MAX_QUERY_LENGTH:
        raise ValueError(f"المدخل طويل جدًا؛ الحد الأقصى هو {MAX_QUERY_LENGTH} حرفًا.")

    is_url = is_http_url(query_or_url)
    target_url = query_or_url if is_url else f"{TARGET_SITE_URL}{SEARCH_PATH}?s={urllib.parse.quote_plus(query_or_url)}"
    result = MediaResult()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
                )
            )
            page = await context.new_page()

            def handle_request(request) -> None:
                url = request.url
                if result.url is None and re.search(r"\.(m3u8|mp4)(?:\?|$)", url, re.IGNORECASE):
                    result.url = url
                    result.referer = request.headers.get("referer") or page.url
                    result.kind = "Direct media request"

            page.on("request", handle_request)
            await page.goto(target_url, wait_until="domcontentloaded", timeout=SCRAPE_TIMEOUT_SECONDS * 1000)
            await page.wait_for_timeout(1500)
            body_text = (await page.locator("body").inner_text()).strip().lower()
            if body_text in {"forbidden", "access denied"} or "just a moment" in body_text:
                raise RuntimeError("الموقع منع الوصول الآلي من هذا السيرفر.")

            if not is_url:
                first_card = page.locator(
                    "a.show-card, a[href*='/film/'], a[href*='/series/'], a[href*='video'], a[href*='watch'], .media-block a, article a"
                ).first
                if await first_card.count():
                    await first_card.click(timeout=5000)
                    await page.wait_for_load_state("domcontentloaded", timeout=SCRAPE_TIMEOUT_SECONDS * 1000)
                    await page.wait_for_timeout(1000)

            if result.url is None:
                script_element = page.locator("script#scrape-page-bootstrap-v23").first
                if await script_element.count():
                    raw_json = await script_element.text_content()
                    if raw_json:
                        try:
                            candidates = find_candidate_urls(json.loads(raw_json))
                        except json.JSONDecodeError:
                            candidates = find_candidate_urls(raw_json)
                        candidate = choose_candidate(candidates)
                        if candidate:
                            result.url = candidate
                            result.referer = page.url
                            result.kind = "Page data / media source candidate"

            if result.url is None:
                for frame in page.frames:
                    frame_url = frame.url
                    if frame_url != page.url and not frame_url.startswith("about:") and any(
                        key in frame_url.lower() for key in ("embed", "player", "stream")
                    ):
                        result.url = frame_url
                        result.referer = page.url
                        result.kind = "Embedded player page"
                        break
        except PlaywrightTimeoutError:
            raise TimeoutError("انتهت مهلة فتح الصفحة أو انتظارها.")
        finally:
            await browser.close()

    return result


@bot.event
async def on_ready() -> None:
    logger.info("تم تسجيل الدخول بنجاح باسم %s", bot.user)
    logger.info("البوت جاهز. استخدم %s%s <اسم أو رابط>", COMMAND_PREFIX, "watch")


@bot.command(name="watch")
@commands.cooldown(rate=1, per=15, type=commands.BucketType.user)
async def watch(ctx: commands.Context, *, query_or_url: str) -> None:
    message = await ctx.send("جاري معالجة المدخل واستخراج البيانات...")
    try:
        result = await scrape_media_stream(query_or_url)
        if result.url:
            embed = discord.Embed(title="تم العثور على رابط", color=discord.Color.green())
            embed.add_field(name="المدخل", value=query_or_url[:1024], inline=False)
            embed.add_field(name="النوع", value=result.kind or "غير محدد", inline=False)
            embed.add_field(name="الرابط", value=result.url[:1024], inline=False)
            if result.referer:
                embed.add_field(name="المصدر", value=result.referer[:1024], inline=False)
            await message.edit(content=None, embed=embed)
        else:
            await message.edit(content="لم يتم العثور على رابط مناسب في الصفحة.")
    except (ValueError, TimeoutError, RuntimeError) as exc:
        await message.edit(content=f"تعذر إكمال الطلب: {exc}")
    except Exception:
        logger.exception("Unexpected error while processing watch command")
        await message.edit(content="حدث خطأ غير متوقع. راجع سجل التشغيل للتفاصيل.")


@watch.error
async def watch_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"حاول مرة أخرى بعد {error.retry_after:.1f} ثانية.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"الاستخدام الصحيح: `{COMMAND_PREFIX}watch <اسم أو رابط>`")
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        logger.error(
            "Command error: %s",
            error,
            exc_info=(type(error), error, error.__traceback__),
        )
        await ctx.send("تعذر تنفيذ الأمر بسبب خطأ في الطلب.")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN غير محدد. عيّنه كمتغير بيئة قبل تشغيل البوت.")
    asyncio.run(bot.start(DISCORD_TOKEN))
