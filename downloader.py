import os
import re
import time
import requests
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# تنظیمات اولیه
BASE_URL = "https://example.com" # آدرس سایت اصلی (برای محاسبه آدرس‌های نسبی)
TARGET_URL = "https://example.com/my-page" # آدرسی که باید دانلود شود
OUTPUT_DIR = "./downloaded_assets"

def setup_driver():
    """راه‌اندازی مرورگر Headless"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    driver = webdriver.Chrome(options=options)
    return driver

def scroll_to_load_lazy(driver, wait_time=2):
    """اسکرول کردن صفحه تا پایین برای لود شدن عکس‌های Lazy Load"""
    print("در حال اسکرول برای بارگذاری محتوا...")
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    while True:
        # اسکرول به پایین
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        # صبر کردن برای لود شدن محتوا
        time.sleep(wait_time)
        
        # محاسبه ارتفاع جدید
        new_height = driver.execute_script("return document.body.scrollHeight")
        
        if new_height == last_height:
            # اگر ارتفاع تغییر نکرد، یعنی همه چیز لود شده
            break
        last_height = new_height

def get_image_url(img_tag):
    """استخراج آدرس واقعی تصویر از تگ img (src یا data-src)"""
    # اول src را چک می‌کنیم
    src = img_tag.get('src')
    if src and src.startswith(('http://', 'https://')):
        return src
    
    # اگر نبود، ممکن است از data-src یا data-original استفاده شده باشد
    data_src = img_tag.get('data-src') or img_tag.get('data-original') or img_tag.get('data-lazy-src')
    if data_src and data_src.startswith(('http://', 'https://')):
        return data_src
    
    return None

def get_video_url(video_tag):
    """استخراج آدرس واقعی ویدیو"""
    # چک کردن تگ video
    source = video_tag.find_element(By.TAG_NAME, 'source') if video_tag.find_elements(By.TAG_NAME, 'source') else None
    if source:
        src = source.get('src')
        if src and src.startswith(('http://', 'https://')):
            return src
    
    # چک کردن خود تگ video
    src = video_tag.get('src')
    if src and src.startswith(('http://', 'https://')):
        return src
        
    return None

def download_file(url, filename, folder):
    """دانلود یک فایل با نام مشخص"""
    # ایجاد مسیر امن برای نام فایل
    safe_filename = re.sub(r'[^\w\-.]', '_', os.path.basename(urlparse(filename).path))
    file_path = os.path.join(folder, safe_filename)
    
    # اگر فایل قبلاً دانلود شده، دوباره دانلود نکن (اختیاری)
    if os.path.exists(file_path):
        print(f"فایل {safe_filename} از قبل موجود است.")
        return True

    try:
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"دانلود شد: {safe_filename}")
            return True
        else:
            print(f"خطا در دانلود {url}: وضعیت {response.status_code}")
            return False
    except Exception as e:
        print(f"خطا در دانلود {url}: {e}")
        return False

def main():
    print(f"شروع پردازش برای: {TARGET_URL}")
    
    # ایجاد پوشه‌های خروجی
    img_dir = os.path.join(OUTPUT_DIR, "images")
    vid_dir = os.path.join(OUTPUT_DIR, "videos")
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(vid_dir, exist_ok=True)

    driver = setup_driver()
    
    try:
        # 1. باز کردن صفحه هدف
        driver.get(TARGET_URL)
        
        # 2. صبر کردن برای لود اولیه DOM
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            print("زمان لود اولیه صفحه تمام شد، اما ادامه می‌دهیم...")

        # 3. اسکرول کردن برای لود کردن عکس‌های Lazy Load
        scroll_to_load_lazy(driver, wait_time=3)
        
        # 4. استخراج تمام تگ‌های img و video
        images = driver.find_elements(By.TAG_NAME, "img")
        videos = driver.find_elements(By.TAG_NAME, "video")
        
        print(f"{len(images)} تصویر و {len(videos)} ویدیو پیدا شد.")

        # 5. دانلود تصاویر
        downloaded_images = set()
        for img in images:
            url = get_image_url(img)
            if url:
                # جلوگیری از دانلود لوگوهای تکراری یا بسیار کوچک (اختیاری)
                if url not in downloaded_images:
                    # تبدیل آدرس نسبی به مطلق
                    full_url = urljoin(TARGET_URL, url)
                    download_file(full_url, full_url, img_dir)
                    downloaded_images.add(url)

        # 6. دانلود ویدیوها
        downloaded_videos = set()
        for video in videos:
            url = get_video_url(video)
            if url:
                if url not in downloaded_videos:
                    full_url = urljoin(TARGET_URL, url)
                    download_file(full_url, full_url, vid_dir)
                    downloaded_videos.add(url)

        print("عملیات دانلود تکمیل شد.")
        
    except Exception as e:
        print(f"خطایی رخ داد: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
