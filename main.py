import os
import asyncio
import re
import urllib.parse
import discord
from discord.ext import commands
from playwright.async_api import async_playwright

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TARGET_SITE_URL = os.getenv("TARGET_SITE_URL", "https://example-arabic-cinema-site.com")

# إعداد الصلاحيات بصورة صحيحة لتفادي خطأ missing intents
intents = discord.Intents.default()
intents.message_content = True

# استخدام bot بدلاً من client لدعم البريفكس &
bot = commands.Bot(command_prefix="&", intents=intents)

async def scrape_media_stream(query: str):
    found_media = {"url": None, "referer": None, "type": None}
    search_url = f"{TARGET_SITE_URL}/search?q={urllib.parse.quote(query)}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        page.on("popup", lambda popup: asyncio.create_async_task(popup.close()))

        async def handle_request(request):
            url = request.url
            if re.search(r"\.(m3u8|mp4)(\?|$)", url, re.IGNORECASE):
                if not found_media["url"]:
                    found_media["url"] = url
                    found_media["referer"] = request.headers.get("referer", TARGET_SITE_URL)
                    found_media["type"] = "Direct Stream (m3u8/mp4)"

        page.on("request", handle_request)

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)

            first_result = page.locator(".search-results .item a, .movie-card a").first
            if await first_result.count() > 0:
                await first_result.click()
                await page.wait_for_load_state("domcontentloaded")

            play_button = page.locator("button.play-btn, .player-container iframe, #player").first
            if await play_button.count() > 0:
                await play_button.click(force=True)

            for _ in range(10):
                if found_media["url"]:
                    break
                await asyncio.sleep(0.5)

            if not found_media["url"]:
                for frame in page.frames:
                    if any(domain in frame.url for domain in ["player", "embed", "vidsrc", "stream"]):
                        found_media["url"] = frame.url
                        found_media["referer"] = page.url
                        found_media["type"] = "Embed / iframe Server"
                        break

        except Exception as e:
            print(f"[Error Scraper]: {e}")
        finally:
            await browser.close()

    return found_media

@bot.event
async def on_ready():
    print(f"تم تسجيل الدخول بنجاح كـ: {bot.user.name}")
    print("البوت جاهز لاستقبال الأوامر مثل: &watch")

@bot.command(name="watch")
async def watch(ctx, *, title: str):
    msg = await ctx.send(f"🔍 جاري البحث واستخراج المشغل المباشر لـ: **{title}**...")
    result = await scrape_media_stream(title)

    if result["url"]:
        embed = discord.Embed(
            title=f"🎬 نتائج البحث: {title}",
            color=discord.Color.green(),
            description="تم استخراج رابط المشغل بنجاح."
        )
        embed.add_field(name="نوع السيرفر", value=f"`{result['type']}`", inline=False)
        embed.add_field(name="رابط المشغل", value=f"```{result['url']}```", inline=False)
        if result["referer"]:
            embed.add_field(name="Referer المطلوبة", value=f"`{result['referer']}`", inline=False)

        await msg.edit(content=None, embed=embed)
    else:
        embed = discord.Embed(
            title="❌ لم يتم العثور على رابط",
            description=f"تعذر استخراج رابط مباشر للعمل: **{title}**.",
            color=discord.Color.red()
        )
        await msg.edit(content=None, embed=embed)

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise ValueError("خطأ: لم يتم ضبط DISCORD_TOKEN في متغيرات بيئة Railway!")
    bot.run(DISCORD_TOKEN)
