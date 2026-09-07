import os
import re
import json
import asyncio
import urllib.parse
import discord
from discord.ext import commands
from playwright.async_api import async_playwright

# جلب المتغيرات من بيئة التشغيل
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TARGET_SITE_URL = os.getenv("TARGET_SITE_URL", "https://shaiid4u.co").rstrip('/')

# إعداد البوت والصلاحيات
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="&", intents=intents)

async def scrape_media_stream(query_or_url: str):
    found_media = {"url": None, "referer": None, "type": None}
    
    # التحقق مما إذا كان المدخل رابطاً أم اسم فيلم
    is_url = query_or_url.startswith("http://") or query_or_url.startswith("https://")
    target_url = query_or_url if is_url else f"{TARGET_SITE_URL}/?s={urllib.parse.quote(query_or_url)}"

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

        # التقاط أي شبكة مباشرة (.m3u8 أو .mp4)
        async def handle_request(request):
            url = request.url
            if re.search(r"\.(m3u8|mp4)(\?|$)", url, re.IGNORECASE):
                if not found_media["url"]:
                    found_media["url"] = url
                    found_media["referer"] = request.headers.get("referer", TARGET_SITE_URL)
                    found_media["type"] = "Direct Stream (m3u8/mp4)"

        page.on("request", handle_request)

        try:
            # 1. الانتقال للرابط المباشر أو صفحة البحث
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # 2. إذا كان بحثاً عادياً، نقر على أول نتيجة ليدخل صفحة الفيلم
            if not is_url:
                first_card = page.locator("a[href*='film'], a[href*='video'], a[href*='watch'], .media-block a, article a").first
                if await first_card.count() > 0:
                    await first_card.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(2)

            # 3. فحص واستخراج البيانات من كائن JSON المحمي (scrape-page-bootstrap-v23)
            script_element = page.locator("script#scrape-page-bootstrap-v23")
            if await script_element.count() > 0:
                json_content = await script_element.inner_text()
                data = json.loads(json_content)
                
                # استخراج الرابط المباشر للمشغل من التشفير
                json_str = json.dumps(data)
                urls = re.findall(r'https?://[^\s"\'\\]+', json_str)
                for url in urls:
                    if any(k in url for k in ["embed", "player", "vidsrc", "m3u8", "stream"]):
                        found_media["url"] = url
                        found_media["referer"] = page.url
                        found_media["type"] = "Extracted Json Stream"
                        break

            # 4. خيار احتياطي: جلب روابط الـ iframe الخارجية إن وجدت
            if not found_media["url"]:
                for frame in page.frames:
                    if any(k in frame.url for k in ["embed", "player", "vidsrc", "stream"]):
                        if frame.url != page.url and not frame.url.startswith("about:"):
                            found_media["url"] = frame.url
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
    print("البوت جاهز لاستقبال الرابط أو الاسم عبر &watch")

@bot.command(name="watch")
async def watch(ctx, *, query_or_url: str):
    msg = await ctx.send(f"🔍 جاري المعالجة واستخراج المشغل لـ: **{query_or_url}**...")
    
    try:
        media_data = await scrape_media_stream(query_or_url)

        if media_data["url"]:
            embed = discord.Embed(
                title=f"🎬 تم العثور على المشغل!",
                color=discord.Color.green()
            )
            embed.add_field(name="المدخل", value=query_or_url, inline=False)
            embed.add_field(name="نوع المشغل", value=media_data["type"], inline=False)
            embed.add_field(name="رابط المشغل / البث", value=f"```{media_data['url']}```", inline=False)
            if media_data["referer"]:
                embed.add_field(name="المصدر (Referer)", value=media_data["referer"], inline=False)
            
            await msg.edit(content=None, embed=embed)
        else:
            embed = discord.Embed(
                title="❌ لم يتم العثور على رابط",
                description=f"تعذر استخراج رابط المشغل من المدخل المرفق.",
                color=discord.Color.red()
            )
            await msg.edit(content=None, embed=embed)

    except Exception as e:
        await msg.edit(content=f"⚠️ حدث خطأ أثناء تنفيذ الأمر: `{e}`")

if __name__ == "__main__":
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("خطأ: DISCORD_TOKEN غير محدد في متغيرات البيئة!")
