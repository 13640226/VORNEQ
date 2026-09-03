# راهنمای راه‌اندازی سامان خرد

## پیش‌نیازها

- Python 3.11 یا بالاتر
- pip

## نصب

```bash
git clone https://github.com/13640226/saman-kherad.git
cd saman-kherad
python -m venv venv
```

فعال‌سازی محیط مجازی در Linux یا macOS:

```bash
source venv/bin/activate
```

فعال‌سازی در Windows PowerShell:

```powershell
.\\venv\\Scripts\\Activate.ps1
```

سپس:

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

متغیرهای `DJANGO_SECRET_KEY`، `DJANGO_DEBUG`،
`DJANGO_ALLOWED_HOSTS` و `DJANGO_CSRF_TRUSTED_ORIGINS` را مطابق
`.env.example` در محیط اجرا تنظیم کنید. پروژه فایل `.env` را خودکار بارگذاری
نمی‌کند.

## تست

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

## تولید

در محیط تولید، `DJANGO_DEBUG=False` باشد و HTTPS و reverse proxy مطابق
تنظیمات استقرار پیکربندی شوند.
