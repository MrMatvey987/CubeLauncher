import os
from dotenv import load_dotenv

# Загружаем переменные из файла .env
load_dotenv()

# Firebase и авторизация
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID")
MS_REDIRECT_URL = os.getenv("MS_REDIRECT_URL")
CF_API_KEY = os.getenv("CF_API_KEY")

# Email и сторонние сервисы
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL")

# SMTP Настройки
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.yandex.ru")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# URLs
CUBE_VISUALS_URL = os.getenv("CUBE_VISUALS_URL")