# Regression Report — Library App

**تاریخ:** ۲۰۲۶-۰۹-۰۳

**Scope:** P0 Stabilization

## وضعیت پیش از Patch

`library/views.py` به فیلدها و helperهایی وابسته بود که در `LibraryItem`
وجود نداشتند: فیلدهای دسترسی عمومی، نوع محتوا، ترجمه‌ها، نویسنده، تاریخ
انتشار و PDF، به‌همراه helperهای نمایش چندزبانه و `has_pdf`.

## تغییرات P0

- قرارداد موردنیاز View به‌صورت افزایشی به `LibraryItem` اضافه شد.
- migration متناظر از مدل واقعی Django تولید شد.
- کلاس `AudioItem` بدون تغییر حفظ شد.
- تست‌های قراردادی Library و تست‌های regression Marketplace اضافه شدند.

## وضعیت تأیید

- Contract mismatch در source: اصلاح‌شده
- Migration محلی: اعمال شد
- Test suite محلی: ۱۲ تست موفق
- CI: تا اجرای GitHub Actions در وضعیت Pending باقی می‌ماند
