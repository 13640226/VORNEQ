# راهنمای ناوبری ایزوله

این سند الگوی ناوبری مستقل (standalone navigation) در پروژهٔ سامان خرد را توضیح می‌دهد. هدف این الگو، افزودن ناوبری به صفحات منتخب بدون تغییر سراسری `base.html` و بدون اثرگذاری روی مسیرهای نامرتبط است.

## اهداف معماری

- ایزوله‌سازی کامل: فقط صفحه‌ای که stylesheet و partial را لود می‌کند تغییر می‌کند.
- عدم تغییر `base.html`: صفحات موجود می‌توانند بدون بازطراحی ساختار پایه، ناوبری مستقل داشته باشند.
- RTL-first و سازگار با زبان فارسی.
- حفظ هویت بصری Dark / Epistemic با accent طلایی در صفحات عمومی.
- قابلیت override محلی برای صفحات auth در صورت نیاز به accent متفاوت.
- responsive در breakpoint `640px`.

## فایل‌های مشترک

Partial ناوبری:

`templates/partials/_standalone_nav.html`

Stylesheet مشترک:

`assets/css/standalone-nav.css`

این stylesheet عمداً `.site-header` را مخفی می‌کند. بنابراین فقط باید در صفحاتی لود شود که قرار است هدر اصلی با standalone navigation جایگزین شود.

## ساختار Partial

Partial شامل این مسیرهاست:

- Home
- Library
- Marketplace
- Login یا Logout بر اساس وضعیت احراز هویت

مسیرهای Home، Library و Marketplace بر اساس `request.LANGUAGE_CODE` ساخته می‌شوند. Active state نیز با `request.path` تعیین می‌شود.

## استفاده در صفحاتی که از `base.html` ارث می‌برند

در template صفحه، stylesheet را داخل `extra_head` اضافه کنید:

```django
{% block extra_head %}
    {{ block.super }}
    <link rel="stylesheet" href="{% static 'css/standalone-nav.css' %}">
{% endblock %}
```

سپس در ابتدای `content`، partial را include کنید:

```django
{% block content %}
    {% include "partials/_standalone_nav.html" %}

    <!-- محتوای صفحه -->
{% endblock %}
```

این الگو در صفحات عمومی مانند Library و Marketplace استفاده می‌شود.

## استفاده در صفحات standalone

برای templateهایی که از `base.html` ارث نمی‌برند و ساختار کامل HTML دارند، stylesheet را مستقیماً در `<head>` اضافه کنید:

```django
<link rel="stylesheet" href="{% static 'css/standalone-nav.css' %}">
```

و بلافاصله بعد از `<body>`، partial را include کنید:

```django
<body>
    {% include "partials/_standalone_nav.html" %}
```

به دلیل rule موجود در stylesheet، `.site-header` قبلی در همان صفحه مخفی می‌شود.

## تم بصری

مقادیر اصلی ناوبری مشترک:

- پس‌زمینه: نزدیک به `#0B0B0D`
- متن اصلی: نزدیک به `#F3EEE5`
- Active عمومی: `#E2BD84`
- فونت: `Tahoma, Arial, sans-serif`
- جهت: `rtl`
- breakpoint موبایل: `640px`

در صفحات auth می‌توان در خود template، override محلی اضافه کرد؛ برای مثال accent قرمز/زرشکی، بدون تغییر stylesheet مشترک.

## قواعد ایزوله‌سازی

هنگام افزودن standalone navigation به صفحهٔ جدید:

1. ابتدا ساختار واقعی template را بررسی کنید.
2. اگر صفحه از `base.html` ارث می‌برد، از `extra_head` و `content` استفاده کنید.
3. اگر صفحه standalone است، stylesheet را مستقیماً در `<head>` و partial را بعد از `<body>` قرار دهید.
4. `base.html` را فقط برای این feature تغییر ندهید.
5. از افزودن selectorهای عمومی جدید که روی صفحات دیگر اثر می‌گذارند خودداری کنید.
6. هر PR را تا حد ممکن کوچک و محدود به templateهای همان flow نگه دارید.

## CI

CI باید قبل از اجرای تست‌ها static files را collect کند:

```bash
python manage.py collectstatic --noinput
```

این مرحله برای سازگاری با `CompressedManifestStaticFilesStorage` ضروری است تا referenceهای `{% static %}` جدید در manifest موجود باشند.

## پوشش فعلی

Standalone navigation اکنون در این بخش‌ها استفاده می‌شود:

- Library
- Marketplace
- Login
- Signup
- Password Reset
- Password Reset Done
- Password Reset From Key
- Password Reset From Key Done
- Logout
- Email Confirm
- Verification Sent
- Email Management
- Password Change
- Password Set
- Inactive Account
- Signup Closed

در زمان نگارش این سند، تمام templateهای موجود در `templates/account/` که در scope این rollout بودند پوشش داده شده‌اند.

## چک‌لیست برای صفحهٔ جدید

- [ ] ساختار template بررسی شده است.
- [ ] `standalone-nav.css` فقط در همان صفحه/flow لود می‌شود.
- [ ] `_standalone_nav.html` در جای صحیح include شده است.
- [ ] هدر قبلی دو بار نمایش داده نمی‌شود.
- [ ] RTL و mobile layout بررسی شده است.
- [ ] مسیرهای nav معتبر هستند.
- [ ] CI شامل `collectstatic --noinput` سبز است.
- [ ] در صورت امکان، smoke-test مرورگری روی محیط واقعی انجام شده است.

## نکتهٔ نگهداری

اگر تعداد صفحات با تم‌های متفاوت افزایش پیدا کرد، به‌جای گسترش overrideهای inline در templateها، می‌توان یک لایهٔ theme modifier مشخص برای standalone navigation طراحی کرد. تا زمانی که تعداد این موارد کم است، override محلی ایزوله و کم‌ریسک‌تر است.
