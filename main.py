import os
import re
import asyncio
import urllib.parse
from discord.ext import commands
import discord
from playwright.async_api import async_playwright

# جلب المتغيرات
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TARGET_SITE_URL = os.getenv("TARGET_SITE_URL", "https://wi.txcima.com").rstrip('/')

# إعداد البوت مع الصلاحيات
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="&", intents=intents)

async def scrape_media_stream(query: str):
    found_media = {"url": None, "referer": None, "type": None}
    search_url = f"{TARGET_SITE_URL}/?s={urllib.parse.quote(query)}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # التقاط روابط الفيديو المباشرة أثناء التحميل
        async def handle_request(request):
            url = request.url
            if re.search(r"\.(m3u8|mp4)(\?|$)", url, re.IGNORECASE):
                if not found_media["url"]:
                    found_media["url"] = url
                    found_media["referer"] = request.headers.get("referer", TARGET_SITE_URL)
                    found_media["type"] = "Direct Stream (m3u8/mp4)"

        page.on("request", handle_request)

        try:
            # 1. فتح صفحة البحث
            await page.goto(search_url, wait_until="networkidle", timeout=30000)
            
            # 2. العثور على أول رابط فيلم/مسلسل والنقر عليه
            first_result = page.locator("a[href*='film'], a[href*='series'], .BlockItem a, article a").first
            if await first_result.count() > 0:
                await first_result.click()
                await page.wait_for_load_state("domcontentloaded", timeout=20000)

            # 3. محاولة النقر على مشغل الفيديو
            play_element = page.locator("iframe, .EmbedContainer, #player").first
            if await play_element.count() > 0:
                await play_element.click(force=True)

            # 4. الانتظار لالتقاط الفيديو
            for _ in range(10):
                if found_media["url"]:
                    break
                await asyncio.sleep(1)

            # 5. إذا لم يجد رابط مباشر، يأخذ رابط المشغل المضمن (iframe)
            if not found_media["url"]:
                for frame in page.frames:
                    frame_url = frame.url
                    if any(k in frame_url for k in ["embed", "player", "vidsrc", "stream", "watch"]):
                        if frame_url != page.url and not frame_url.startswith("about:"):
                            found_media["url"] = frame_url
                            found_media["referer"] = page.url
                            found_media["type"] = "Embed Player Server"
                            break

        except Exception as e:
            print(f"[Scraper Error]: {e}")
        finally:
            await browser.close()

    return found_media

@bot.event
async def on_ready():
    print(f"تم تسجيل الدخول بنجاح كـ {bot.user.name}")
    print("البوت جاهز لاستقبال الأوامر مثل &watch")

@bot.command(name="watch")
async def watch(ctx, *, query: str):
    msg = await ctx.send(f"🔍 جاري البحث واستخراج المشغل المباشر لـ: **{query}**...")
    
    try:
        media_data = await scrape_media_stream(query)

        if media_data["url"]:
            embed = discord.Embed(
                title=f"🎬 تم العثور على المشغل لـ: {query}",
                color=discord.Color.green()
            )
            embed.add_field(name="نوع المشغل", value=media_data["type"], inline=False)
            embed.add_field(name="رابط المشغل / البث", value=f"```{media_data['url']}```", inline=False)
            if media_data["referer"]:
                embed.add_field(name="المصدر (Referer)", value=media_data["referer"], inline=False)
            
            await msg.edit(content=None, embed=embed)
        else:
            embed = discord.Embed(
                title="❌ لم يتم العثور على رابط",
                description=f"تعذر استخراج رابط مباشر للعمل: **{query}**.",
                color=discord.Color.red()
            )
            await msg.edit(content=None, embed=embed)

    except Exception as e:
        await msg.edit(content=f"⚠️ حدث خطأ أثناء تنفيذ الأمر: `{e}`")

if __name__ == "__main__":
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("خطأ: DISCORD_TOKEN غير موجود في متغيرات البيئة!")
