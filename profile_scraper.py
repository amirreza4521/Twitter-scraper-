import time
import subprocess
import json
import random
import sys
import os
import requests
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

#  تنظیمات ثابت
MAX_STALE_SCROLLS = 10


#  توابع کمکی

def custom_log(msg, callback=None):
    """ارسال پیام به پنل و کنسول"""
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
    downloaded_paths = []
    if not image_urls:
        return downloaded_paths

    if not os.path.exists(folder):
        os.makedirs(folder)

    for i, url in enumerate(image_urls):
        try:
            response = requests.get(url, stream=True, timeout=15)
            if response.status_code == 200:
                filename = f"{prefix}_{random.randint(10000, 99999)}.jpg"
                filepath = os.path.join(folder, filename)
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(8192):
                        f.write(chunk)
                downloaded_paths.append(filepath)
        except Exception:
            pass
    return downloaded_paths


def extract_tweet_data(element):
    """استخراج داده‌های یک توییت در پروفایل"""
    try:
        try:
            text = element.find_element(By.XPATH, ".//div[@data-testid='tweetText']").text.strip()
        except:
            text = ""

        image_urls = []
        img_elements = element.find_elements(By.XPATH, ".//div[@data-testid='tweetPhoto']//img")
        for img in img_elements:
            src = img.get_attribute('src')
            if src:
                parsed = urlparse(src)
                best_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?format=jpg&name=orig"
                image_urls.append(best_url)

        try:
            link_el = element.find_element(By.XPATH, ".//a[contains(@href, '/status/') and .//time]")
            tweet_link = link_el.get_attribute('href')
        except:
            tweet_link = "unknown"

        return {"text": text, "image_urls": image_urls, "link": tweet_link}
    except:
        return None


def get_users_list(driver, url_suffix, limit=20, log_callback=None):
    """تابع کمکی برای استخراج لیست فالوورها/فالویینگ‌ها"""
    base_url = driver.current_url.split('/')[0] + "//" + driver.current_url.split('/')[2] + "/" + \
               driver.current_url.split('/')[3]
    target = f"{base_url}/{url_suffix}"

    custom_log(f"👥 در حال رفتن به صفحه {url_suffix}...", log_callback)
    driver.get(target)
    time.sleep(4)

    users = []
    seen = set()

    try:
        start_time = time.time()
        while len(users) < limit and (time.time() - start_time) < 30:
            elements = driver.find_elements(By.XPATH,
                                            "//div[@data-testid='UserCell']//a[@role='link']//div[@dir='ltr']/span")
            for el in elements:
                username = el.text
                if username and username not in seen:
                    seen.add(username)
                    users.append(username)

            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(1)

    except Exception as e:
        custom_log(f"⚠️ خطا در دریافت لیست {url_suffix}: {str(e)}", log_callback)

    custom_log(f"✅ تعداد {len(users)} کاربر از لیست {url_suffix} استخراج شد.", log_callback)
    return users


# تابع اصلی: Profile Logic
def profile_logic(url, limit, save_media, get_followers=False, get_following=False, log_callback=None, output_file=None, image_dir="images"):
    driver = initialize_driver(log_callback)
    wait = WebDriverWait(driver, 15)

    # بررسی فرمت URL
    if "x.com" not in url and "twitter.com" not in url:
        # اگر فقط یوزرنیم داده شد
        url = f"https://x.com/{url.replace('@', '')}"

    custom_log(f"👤 رفتن به پروفایل: {url}", log_callback)
    driver.get(url)
    time.sleep(5)

    # استخراج اطلاعات هدر (Header Info)
    profile_info = {}
    try:
        header = wait.until(EC.visibility_of_element_located((By.XPATH, "//div[@data-testid='primaryColumn']")))

        try:
            name = header.find_element(By.XPATH, ".//div[@data-testid='UserName']//span/span").text
            username = header.find_element(By.XPATH, ".//div[@data-testid='UserName']//div[contains(@dir, 'ltr')]").text
            profile_info['name'] = name
            profile_info['username'] = username
        except:
            pass

        try:
            f_count = header.find_element(By.XPATH, ".//a[contains(@href, '/followers')]//span").text
            profile_info['followers_stat'] = f_count
        except:
            pass

        custom_log(f"✅ اطلاعات پایه پروفایل دریافت شد: {profile_info.get('username', 'Unknown')}", log_callback)
    except Exception as e:
        custom_log("⚠️ عدم توانایی در استخراج هدر پروفایل.", log_callback)

    #  استخراج توییت‌ها (Timeline)
    tweets = []
    seen_tweets = set()
    stale_count = 0

    custom_log(f"📜 شروع اسکرپ توییت‌ها (هدف: {limit} عدد)...", log_callback)

    while len(tweets) < limit:
        try:
            elements = driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
        except:
            elements = []

        new_found = 0
        for el in elements:
            if len(tweets) >= limit: break

            data = extract_tweet_data(el)
            if data:
                # استفاده از لینک یا متن به عنوان شناسه یکتا
                # استفاده از لینک اگر بود، اگر نه ترکیب متن و بخشی از لینک عکس
                if data['link'] != "unknown":
                    uid = data['link']
                else:
                    # اگر لینک توییت پیدا نشد، از متن + شناسه عکس استفاده کن تا تکراری نشه
                    img_sig = data['image_urls'][0][-15:] if data['image_urls'] else "txt"
                    uid = f"{data['text'][:30]}_{img_sig}"

                if uid not in seen_tweets:
                    seen_tweets.add(uid)

                    if save_media and data['image_urls']:
                        # استفاده از متغیر image_dir برای ذخیره در پوشه درست
                        data['local_images'] = download_images(data['image_urls'], image_dir,
                                                               f"profile_{len(tweets)}", log_callback)

                    tweets.append(data)
                    new_found += 1
                    custom_log(f"📝 توییت {len(tweets)}/{limit} دریافت شد.", log_callback)

        if new_found == 0:
            stale_count += 1
        else:
            stale_count = 0

        if stale_count >= MAX_STALE_SCROLLS:
            custom_log("⚠️ انتهای تایم‌لاین پروفایل.", log_callback)
            break

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.randint(3, 6))

    #   اختیاری: لیست فالوور/فالویینگ
    followers_list = []
    following_list = []

    if get_followers:
        followers_list = get_users_list(driver, "followers", limit=30, log_callback=log_callback)
        driver.get(url)

    if get_following:
        following_list = get_users_list(driver, "following", limit=30, log_callback=log_callback)

    # 4. ذخیره خروجی
    final_data = {
        "profile_info": profile_info,
        "tweets_count": len(tweets),
        "tweets": tweets,
        "followers_list": followers_list,
        "following_list": following_list
    }

    if output_file is None:
        filename = f"profile_{profile_info.get('username', 'data').replace('@', '')}.json"
    else:
        filename = output_file

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)

    custom_log(f"💾 تمام اطلاعات در فایل {filename} ذخیره شد.", log_callback)
