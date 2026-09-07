# Discord Scraper Bot

بوت Discord مكتوب بلغة Python ويدعم الأمر `&watch` للبحث في صفحة عامة مصرح لك بالوصول إليها واستخراج روابط الوسائط أو صفحات المشغل الظاهرة فيها.

> استخدمه فقط مع المواقع والمحتوى الذي تملك حق الوصول إليه أو لديك إذن صريح لمعالجته. لا تستخدم حساب مستخدم عاديًا كبوت، ولا تتجاوز أنظمة الحماية أو شروط الخدمة.

## المتطلبات

يحتاج المشروع إلى Python 3.10 أو أحدث، وحساب Bot رسمي من [Discord Developer Portal](https://discord.com/developers/applications). يجب تفعيل **Message Content Intent** للبوت من لوحة Discord ومن خلال الكود.

## التثبيت المحلي

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
```

في بيئة Linux قد تحتاج إلى:

```bash
python -m playwright install --with-deps chromium
```

## الإعداد والتشغيل

انسخ `.env.example` إلى `.env` أو عيّن المتغيرات مباشرة في بيئة التشغيل. أهم متغير هو `DISCORD_TOKEN`، ولا تضع التوكن داخل Git أو داخل `config.json`.

```bash
export DISCORD_TOKEN="ضع_توكن_البوت_هنا"
python main.py
```

بعد تسجيل دخول البوت إلى الخادم، استخدم:

```text
&watch اسم البحث
&watch https://example.com/page
```

## Docker

```bash
docker build -t discord-scraper .
docker run --rm -e DISCORD_TOKEN="ضع_التوكن" discord-scraper
```

## ملاحظات الإصدار

تمت إضافة `discord.py` إلى الاعتماديات، وإصلاح الاستيراد الناقص لـ `os`، وتحسين معالجة المهلات والأخطاء، وإضافة تحقق من المدخلات، وتحديد معدل للأمر، وتحديث طريقة التشغيل لتُظهر سبب نقص التوكن بدل الفشل الصامت.
