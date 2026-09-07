async def scrape_media_stream(query: str):
    found_media = {"url": None, "referer": None, "type": None}
    
    # بناء رابط البحث لموقع تاكسي السيما
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

        # مراقبة الشبكة لالتقاط أي رابط فيديو مباشر (.m3u8 أو .mp4)
        async def handle_request(request):
            url = request.url
            if re.search(r"\.(m3u8|mp4)(\?|$)", url, re.IGNORECASE):
                if not found_media["url"]:
                    found_media["url"] = url
                    found_media["referer"] = request.headers.get("referer", TARGET_SITE_URL)
                    found_media["type"] = "Direct Stream (m3u8/mp4)"

        page.on("request", handle_request)

        try:
            # 1. الانتقال لصفحة نتائج البحث
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # 2. النقر على أول نتيجة بحث تظهر في تاكسي السيما
            first_card = page.locator(".BlockItem a, .Grid--Movies a, article a, .post-title a").first
            if await first_card.count() > 0:
                await first_card.click()
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(2)

            # 3. محاولة النقر على أزرار المشغلات والسيرفرات داخل صفحة الفيلم
            play_btn = page.locator("iframe, .EmbedContainer, .WatchArea, .PlayBtn, #player").first
            if await play_btn.count() > 0:
                await play_btn.click(force=True)

            # 4. الانتظار لالتقاط رابط البث
            for _ in range(10):
                if found_media["url"]:
                    break
                await asyncio.sleep(1)

            # 5. إذا لم يلتقط ملف ميديا مباشر، يجلب رابط الـ iframe الخاص بالمشغل
            if not found_media["url"]:
                for frame in page.frames:
                    frame_url = frame.url
                    if any(k in frame_url for k in ["embed", "player", "vidsrc", "stream", "watch", "drive"]):
                        if frame_url != page.url and not frame_url.startswith("about:"):
                            found_media["url"] = frame_url
                            found_media["referer"] = page.url
                            found_media["type"] = "Embed Player Server"
                            break

        except Exception as e:
            print(f"[Scraper Exception]: {e}")
        finally:
            await browser.close()

    return found_media
