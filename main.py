from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import uvicorn
import os
import re
import uuid  # اضافه شده برای تولید اسم فایل تصادفی
import zipfile


# ایمپورت ماژول‌های اسکریپت
try:
    import scraper
    import profile_scraper
except ImportError as e:
    print(f"خطا در ایمپورت ماژول‌های اسکریپت: {e}")

app = FastAPI(title="Twitter Scraper System")

# دیکشنری برای نگهداری وضعیت
system_state = {
    "is_running": False,
    "logs": [],
    "last_file": None  # نام آخرین فایل تولید شده در اینجا ذخیره می‌شود
}


def log_message(msg: str):
    print(f"[SERVER] {msg}")
    system_state["logs"].append(msg)


def run_scraping_logic(mode: str, url: str, count: int, download_img: bool, extras: dict):
    system_state["is_running"] = True
    system_state["last_file"] = None
    log_message(f"🚀 شروع عملیات: {mode}")

    # 1. تمیز کردن ورودی (مثلاً حذف https://x.com/...)
    clean_name = sanitize_filename(url)
    if len(clean_name) > 20:
        clean_name = clean_name[-20:]  # اگر اسم خیلی طولانی بود، 20 حرف آخر را بردار

    # 2. تولید شناسه کوتاه
    unique_id = str(uuid.uuid4())[:6]

    # 3. ساخت نام پایه: (اسم ورودی)_(روش)_(شناسه)
    base_name = f"{clean_name}_{mode}_{unique_id}"

    # 4. نام فایل جیسون و نام پوشه عکس
    output_filename = f"{base_name}.json"
    images_folder = f"{base_name}_images"
    # -----------------------------------

    log_message(f"📂 نام خروجی: {output_filename}")

    try:
        # ارسال نام فایل (output_file) و نام پوشه (image_dir) به توابع اسکرپر
        if mode == 'search':
            scraper.search_logic(
                url, count, download_img,
                log_callback=log_message,
                output_file=output_filename,
                image_dir=images_folder  #  ارسال نام پوشه
            )
        elif mode == 'comments':
            scraper.comments_logic(
                url, count, download_img,
                log_callback=log_message,
                output_file=output_filename,
                image_dir=images_folder  #  ارسال نام پوشه
            )
        elif mode == 'profile':
            get_followers = extras.get('followers', False) if extras else False
            get_following = extras.get('following', False) if extras else False
            profile_scraper.profile_logic(
                url, count, download_img,
                get_followers=get_followers,
                get_following=get_following,
                log_callback=log_message,
                output_file=output_filename,
                image_dir=images_folder  #  ارسال نام پوشه
            )

        system_state["last_file"] = output_filename
        log_message("✅ پایان موفقیت‌آمیز.")
    except Exception as e:
        log_message(f"❌ خطا: {str(e)}")
    finally:
        system_state["is_running"] = False


def sanitize_filename(text):
    """حذف کاراکترهای غیرمجاز برای نام فایل و پوشه"""
    # کاراکترهای غیرمجاز را حذف و فاصله را با _ جایگزین می‌کند
    return re.sub(r'[\\/*?:"<>|]', "", text).replace(" ", "_")

# endpoint ها

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return FileResponse("index.html")


@app.get("/style.css")
async def serve_css():
    return FileResponse("style.css")


@app.get("/script.js")
async def serve_js():
    return FileResponse("script.js")


# اضافه کردن Endpoint جدید برای دانلود فایل
@app.get("/download/{filename}")
async def download_file(filename: str):
    """
    این تابع فایل جیسون و پوشه تصاویر مربوطه را پیدا کرده،
    آن‌ها را زیپ می‌کند و برای دانلود می‌فرستد.
    """
    # مسیر فایل جیسون
    json_path = filename

    # بررسی وجود فایل جیسون
    if not os.path.exists(json_path):
        return JSONResponse(content={"error": "File not found"}, status_code=404)

    # تشخیص نام پایه (حذف .json) برای پیدا کردن پوشه تصاویر
    # مثال: Elon_profile.json -> Elon_profile
    base_name = os.path.splitext(filename)[0]
    image_folder = f"{base_name}_images"

    # نام فایل زیپ خروجی
    zip_filename = f"{base_name}.zip"

    try:
        # ساخت فایل زیپ
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            #  افزودن فایل JSON به زیپ
            zipf.write(json_path, arcname=filename)

            #  افزودن پوشه تصاویر (اگر وجود داشته باشد)
            if os.path.exists(image_folder):
                for root, dirs, files in os.walk(image_folder):
                    for file in files:
                        # مسیر کامل فایل روی سیستم
                        file_path = os.path.join(root, file)
                        # مسیری که داخل فایل زیپ ذخیره می‌شود (تا ساختار پوشه حفظ شود)
                        arcname = os.path.join(image_folder, file)
                        zipf.write(file_path, arcname=arcname)

        # ارسال فایل زیپ به کاربر
        return FileResponse(zip_filename, filename=zip_filename, media_type='application/zip')

    except Exception as e:
        return JSONResponse(content={"error": f"Error creating zip: {str(e)}"}, status_code=500)


@app.post("/start-scrape")
async def start_scrape_api(request: Request, background_tasks: BackgroundTasks):
    if system_state["is_running"]:
        return JSONResponse(content={"status": "error", "message": "System Busy"}, status_code=400)

    data = await request.json()
    background_tasks.add_task(
        run_scraping_logic,
        data.get('mode'),
        data.get('url'),
        int(data.get('count', 50)),
        data.get('download_img', False),
        data.get('extras', {})
    )
    return {"status": "success", "message": "Started"}


@app.get("/get-logs")
async def get_logs_api():
    logs_to_send = list(system_state["logs"])
    system_state["logs"] = []
    # ارسال نام فایل تولید شده به فرانت
    return {
        "logs": logs_to_send,
        "is_running": system_state["is_running"],
        "last_file": system_state["last_file"]
    }


if __name__ == "__main__":
    print("--- Server Running at http://127.0.0.1:8000 ---")
    uvicorn.run(app, host="127.0.0.1", port=8000)
