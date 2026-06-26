import time
import json
import random
import subprocess
import sys
import os
import requests
import urllib.parse
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# --- تنظیمات ثابت ---
MAX_STALE_SCROLLS = 5


# --- توابع کمکی ---

def custom_log(msg, callback=None):
    """ارسال پیام هم به ترمینال و هم به پنل"""
    if callback:
        callback(msg)
    print(msg)


def initialize_driver(log_callback=None):
    """اتصال به کروم با قابلیت اجرای خودکار در صورت بسته بودن"""
    port = 9223
    chrome_debug_url = f"127.0.0.1:{port}"
    custom_log(f"🔌 در حال تلاش برای اتصال به مرورگر کروم (پورت {port})...", log_callback)

    options = Options()
    options.add_experimental_option("debuggerAddress", chrome_debug_url)

    # تلاش اول برای اتصال
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        custom_log("✅ اتصال به مرورگر باز شده موفق بود.", log_callback)
        return driver
    except Exception:
        custom_log("⚠️ مرورگر باز یافت نشد. در حال اجرای خودکار کروم...", log_callback)

        # لیست مسیرهای احتمالی کروم در ویندوز
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
        ]

        chrome_exe = None
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_exe = path
                break

        if not chrome_exe:
            raise Exception("❌ فایل اجرایی کروم پیدا نشد! لطفاً کروم را دستی باز کنید.")

        # دستور اجرای کروم با پورت دیباگ
        user_data_dir = r"C:\chrome-debug"
        command = f'"{chrome_exe}" --remote-debugging-port={port} --user-data-dir="{user_data_dir}"'

        # اجرای کروم بدون اینکه منتظر بسته شدنش بمانیم
        subprocess.Popen(command, shell=True)

        custom_log("⏳ در حال راه‌اندازی مرورگر... (4 ثانیه صبر)", log_callback)
        time.sleep(4)

        # تلاش دوم برای اتصال
        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            custom_log("✅ کروم خودکار اجرا و متصل شد.", log_callback)
            return driver
        except Exception as e:
            raise Exception(f"❌ خطا در اتصال پس از اجرای خودکار: {str(e)}")


def download_images(image_urls, folder, prefix, log_callback=None):
    """دانلود تصاویر با قابلیت غیرفعال‌سازی"""
    downloaded_paths = []
    if not image_urls:
        return downloaded_paths

    if not os.path.exists(folder):
        os.makedirs(folder)

    for i, url in enumerate(image_urls):
        try:
            response = requests.get(url, stream=True, timeout=10)
            if response.status_code == 200:
                filename = f"{prefix}_{random.randint(1000, 9999)}.jpg"
                filepath = os.path.join(folder, filename)
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(8192):
                        f.write(chunk)
                downloaded_paths.append(filepath)
        except Exception as e:
            custom_log(f"خطا در دانلود عکس: {str(e)}", log_callback)

    return downloaded_paths


def extract_tweet_data(element):
    """استخراج داده‌های یک توییت با دقت بالا برای عکس‌ها"""
    try:
        try:
            user_el = element.find_element(By.XPATH,
                                           ".//div[@data-testid='User-Name']//a[@role='link' and starts-with(@href, '/')]")
            username = user_el.get_attribute('href').split('/')[-1]
            name = user_el.text.split('\n')[0]
        except:
            username = "unknown"
            name = "unknown"

        try:
            text_el = element.find_element(By.XPATH, ".//div[@data-testid='tweetText']")
            text = text_el.text.strip()
        except:
            text = ""

        # --- بخش اصلاح شده برای اطمینان از دریافت عکس ---
        image_urls = []

        # 1. پیدا کردن کادرهای عکس (کانتینرها)
        photo_divs = element.find_elements(By.XPATH, ".//div[@data-testid='tweetPhoto']")

        # 2. اگر کادر عکس هست اما خود عکس (img) هنوز لود نشده، کمی صبر کن
        if len(photo_divs) > 0:
            # تلاش برای پیدا کردن تگ img
            img_check = element.find_elements(By.XPATH, ".//div[@data-testid='tweetPhoto']//img")
            if len(img_check) == 0:
                time.sleep(0.5)  # مکث کوتاه برای لود شدن عکس

        # 3. حالا استخراج نهایی
        img_elements = element.find_elements(By.XPATH, ".//div[@data-testid='tweetPhoto']//img")
        for img in img_elements:
            src = img.get_attribute('src')
            if src:
                parsed = urlparse(src)
                # تبدیل کیفیت به اورجینال
                best_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?format=jpg&name=orig"
                image_urls.append(best_url)
        # -----------------------------------------------

        return {
            "name": name,
            "username": f"@{username}",
            "text": text,
            "image_urls": image_urls
        }
    except Exception:
        return None


# ۱. منطق جستجو (Search Logic)
def search_logic(query, limit, save_media, log_callback=None, output_file="search.json", image_dir="images"):
    driver = initialize_driver(log_callback)
    wait = WebDriverWait(driver, 20)

    # تبدیل کوئری به لینک جستجوی توییتر
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://x.com/search?q={encoded_query}&src=typed_query&f=live"

    custom_log(f"🔍 رفتن به صفحه جستجو: {query}", log_callback)
    driver.get(search_url)
    time.sleep(5)

    collected_tweets = []
    seen_ids = set()
    stale_count = 0

    while len(collected_tweets) < limit:
        try:
            tweets = driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
        except:
            tweets = []

        new_found = 0
        for tweet in tweets:
            if len(collected_tweets) >= limit: break

            data = extract_tweet_data(tweet)
            if data:
                # اگر متن خالی بود، از تعداد عکس‌ها یا لینک اولین عکس برای یکتا کردن استفاده کن
                img_id = data['image_urls'][0][-10:] if data['image_urls'] else "noimg"
                unique_id = f"{data['username']}-{data['text'][:20]}-{img_id}"
                if unique_id not in seen_ids:
                    seen_ids.add(unique_id)

                    # دانلود عکس اگر تیک زده شده باشد
                    if save_media and data['image_urls']:
                        # استفاده از مسیر پویای image_dir
                        data['images_local'] = download_images(data['image_urls'], image_dir,
                                                               f"search_{data['username']}", log_callback)

                    collected_tweets.append(data)
                    new_found += 1
                    custom_log(f"➕ توییت دریافت شد: {len(collected_tweets)}/{limit}", log_callback)

        if new_found == 0:
            stale_count += 1
            custom_log("... در حال اسکرول برای یافتن موارد بیشتر", log_callback)
        else:
            stale_count = 0

        if stale_count > MAX_STALE_SCROLLS:
            custom_log("⚠️ دیگر توییتی یافت نشد.", log_callback)
            break

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.randint(3, 6))

    # ذخیره خروجی
    output = {"query": query, "count": len(collected_tweets), "results": collected_tweets}

    # استفاده از نام فایل پویا output_file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

    custom_log(f"💾 نتایج در {output_file} ذخیره شد.", log_callback)


# ۲. منطق نظرات (Comments Logic)
def comments_logic(url, limit, save_media, log_callback=None, output_file="comments.json", image_dir="images"):
    driver = initialize_driver(log_callback)
    wait = WebDriverWait(driver, 20)

    custom_log(f"💬 رفتن به توییت: {url}", log_callback)
    driver.get(url)

    # صبر برای لود توییت اصلی
    custom_log("⏳ در حال بارگذاری صفحه...", log_callback)
    time.sleep(5)

    # استخراج توییت اصلی
    main_tweet_data = {}
    try:
        main_article = wait.until(EC.presence_of_element_located((By.XPATH, "(//article[@data-testid='tweet'])[1]")))
        main_tweet_data = extract_tweet_data(main_article)
        custom_log("✅ توییت اصلی شناسایی شد.", log_callback)
        if save_media and main_tweet_data.get('image_urls'):
            # دانلود عکس توییت اصلی در image_dir
            download_images(main_tweet_data['image_urls'], image_dir, "main_tweet", log_callback)
    except:
        custom_log("⚠️ توییت اصلی پیدا نشد (شاید حذف شده باشد).", log_callback)

    comments = []
    seen_comments = set()
    stale_count = 0

    # حلقه اسکرپ کامنت‌ها
    while len(comments) < limit:
        try:
            # انتخاب تمام توییت‌ها به جز اولی (که اصلی است)
            elements = driver.find_elements(By.XPATH, "(//article[@data-testid='tweet'])[position()>1]")
        except:
            elements = []

        new_found = 0
        for el in elements:
            if len(comments) >= limit: break

            data = extract_tweet_data(el)
            if data:
                # اگر متن خالی بود، از تعداد عکس‌ها یا لینک اولین عکس برای یکتا کردن استفاده کن
                img_id = data['image_urls'][0][-10:] if data['image_urls'] else "noimg"
                unique_id = f"{data['username']}-{data['text'][:20]}-{img_id}"
                if unique_id not in seen_comments:
                    seen_comments.add(unique_id)

                    if save_media and data['image_urls']:
                        prefix = f"comment_{data['username'].replace('@', '')}"
                        # استفاده از مسیر پویای image_dir
                        data['images_local'] = download_images(data['image_urls'], image_dir, prefix,
                                                               log_callback)

                    comments.append(data)
                    new_found += 1
                    custom_log(f"💬 کامنت استخراج شد: {len(comments)}/{limit}", log_callback)

        if new_found == 0:
            stale_count += 1
        else:
            stale_count = 0

        if stale_count >= MAX_STALE_SCROLLS:
            custom_log("⚠️ انتهای کامنت‌ها.", log_callback)
            break

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.randint(4, 7))

    # ذخیره
    output = {
        "source_url": url,
        "main_tweet": main_tweet_data,
        "comments_count": len(comments),
        "comments": comments
    }

    # استفاده از نام فایل پویا output_file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

    custom_log(f"💾 نتایج در {output_file} ذخیره شد.", log_callback)
