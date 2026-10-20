
from __future__ import annotations
from typing import Optional, Dict, Any, List, Tuple, Union, Callable

import os
import sys
import json
import time
import math
import uuid
import re
import base64
import random
import mimetypes
import threading
import subprocess
import shutil
import shlex
import zipfile
import hashlib
import smtplib
import socket
import struct
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlparse, parse_qs
from io import BytesIO

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import webview
import minecraft_launcher_lib
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("CubeLauncher")

try:
    from pypresence import Presence  # type: ignore
    HAS_DISCORD_RPC = True
except ImportError:
    HAS_DISCORD_RPC = False
    Presence = None  # type: ignore

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pystray
    from pystray import MenuItem as item
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False
    pystray = None  # type: ignore    

if sys.platform == "win32":
    import ctypes
    myappid = "cubelauncher.client.ver1.0"
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        log.debug("SetCurrentProcessExplicitAppUserModelID failed: %s", e)

# Ограничения и параметры системы
FIRESTORE_DOC_LIMIT_BYTES = 1_048_576
MAX_AVATAR_BYTES = 250 * 1024
MAX_VOICE_BYTES = 800 * 1024
MAX_CHAT_IMAGE_BYTES = 800 * 1024
MAX_USERNAME_LEN = 16
MIN_USERNAME_LEN = 3
MAX_BIO_LEN = 300
MAX_DESCRIPTION_CHARS = 300

# Сервер Cube Vanilla по умолчанию
CUBE_VANILLA_ADDRESS = "185.9.145.8:25994"
CUBE_VANILLA_RECOMMENDED_VERSION = "1.21.11"

# Путь к локальному шрифту Minecraft
MINECRAFT_FONT_PATH = r"C:\CubeLauncher\Launcher\fonts\minecraft.ttf"


def get_resource_path(relative_path: str) -> str:
    """Возвращает корректный абсолютный путь к ресурсу (в том числе для сборки PyInstaller)."""
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


ICON_PATH = get_resource_path("images/icon.ico")

# Загрузка переменных окружения
try:
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(_env_path):
        load_dotenv(dotenv_path=_env_path, override=False)
    else:
        load_dotenv(override=False)
except Exception as _e:
    log.warning("dotenv не загрузился: %s", _e)

FIREBASE_API_KEY: str = os.getenv("FIREBASE_API_KEY", "")
FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "cube-1c237")
MS_CLIENT_ID: str = os.getenv("MS_CLIENT_ID", "00000000402b5328")
MS_REDIRECT_URL: str = os.getenv(
    "MS_REDIRECT_URL", "https://login.live.com/oauth20_desktop.srf"
)
CF_API_KEY: str = os.getenv("CF_API_KEY", "")
DISCORD_CLIENT_ID: str = os.getenv("DISCORD_CLIENT_ID", "1219283746592817263")

RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL: str = os.getenv(
    "RESEND_FROM_EMAIL", "Cube Launcher <auth@cubelauncher.ru>"
)

SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.yandex.ru")
try:
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "465"))
except ValueError:
    SMTP_PORT = 465
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

HEADERS: Dict[str, str] = {
    "User-Agent": "CubeLauncher/1.0.0 (https://cubevanilla.millida.trade)"
}
CF_HEADERS: Dict[str, str] = {
    "x-api-key": CF_API_KEY,
    "Accept": "application/json",
    "User-Agent": "CubeLauncher/1.0.0",
}

# Сессия с ретраями
SESSION = requests.Session()
_retries = Retry(
    total=3,
    backoff_factor=0.3,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=frozenset(["GET", "POST", "PATCH", "DELETE", "PUT", "HEAD"]),
)
_adapter = HTTPAdapter(max_retries=_retries, pool_connections=15, pool_maxsize=20)
SESSION.mount("https://", _adapter)
SESSION.mount("http://", _adapter)

# Базовые директории (теперь строго на диске C:\CubeLauncher)
if os.name == "nt":
    BASE_DIR = r"C:\CubeLauncher"
else:
    BASE_DIR = os.path.join(os.path.expanduser("~"), ".cubelauncher")

LAUNCHER_DIR = os.path.join(BASE_DIR, "Launcher")
GAME_DIR = os.path.join(BASE_DIR, "game") # <--- Ваша папка C:\CubeLauncher\game
INSTANCES_DIR = os.path.join(GAME_DIR, "instances")

os.makedirs(LAUNCHER_DIR, exist_ok=True)
os.makedirs(GAME_DIR, exist_ok=True)
os.makedirs(INSTANCES_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(LAUNCHER_DIR, "launcher_config.json")
ACCOUNTS_FILE = os.path.join(LAUNCHER_DIR, "accounts.json")
CUBE_ACCOUNTS_FILE = os.path.join(LAUNCHER_DIR, "cube_accounts.json")
USERS_REGISTRY_FILE = os.path.join(LAUNCHER_DIR, "users_registry.json")
STATS_FILE = os.path.join(LAUNCHER_DIR, "player_stats.json")

CUBE_VISUALS_URL = (
    "https://lybsonzfsfxhwgiltlht.supabase.co/storage/v1/object/public/"
    "Cube/mods/cubevisuals-1.0.jar"
)
MOJANG_MANIFEST_URL = (
    "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
)
MC_STATUS_API = "https://api.mcsrvstat.us/3/"

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-\.]{1,64}$")


def is_safe_id(value: str) -> bool:
    """Проверка идентификатора на безопасность от Path Traversal."""
    if not isinstance(value, str) or not value:
        return False
    if value in (".", "..", ""):
        return False
    if ".." in value or "/" in value or "\\" in value:
        return False
    return bool(_SAFE_ID_RE.match(value))


def safe_join(base: str, *parts: str) -> Optional[str]:
    """Безопасное соединение путей внутри base директории."""
    try:
        target = os.path.normpath(os.path.join(base, *parts))
        base_abs = os.path.abspath(base)
        target_abs = os.path.abspath(target)
        if not target_abs.startswith(base_abs + os.sep) and target_abs != base_abs:
            return None
        return target_abs
    except Exception as e:
        log.warning("safe_join(%s, %s) ошибка: %s", base, parts, e)
        return None


# Каталог серверов (Cube Vanilla всегда на первом месте)
SERVER_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "cubevanilla",
        "name": "Cube Vanilla",
        "address": CUBE_VANILLA_ADDRESS,
        "description": "Наш официальный сервер! Уютное ванильное выживание, стабильный TPS и ламповое сообщество. Рекомендуемая версия: 1.21.11.",
        "license": "both",
        "license_label": "Лицензия + Пиратка",
        "versions": ["1.21.11"],
        "versions_raw": ["1.21"],
        "region": "RU",
        "icon_emoji": "🧊",
        "screenshots": [],
        "website": "https://cubevanilla.millida.trade",
    },
    {
        "id": "hypixel",
        "name": "Hypixel",
        "address": "mc.hypixel.net",
        "description": "Крупнейший международный сервер Minecraft с десятками режимов: BedWars, SkyWars, SkyBlock, Duels, Murder Mystery.",
        "license": "licensed",
        "license_label": "Лицензия",
        "versions": ["1.8.x - 1.21.x"],
        "versions_raw": ["1.8", "1.20", "1.21"],
        "region": "EU/US",
        "icon_emoji": "🏆",
        "screenshots": [
            "https://i.imgur.com/KpVexUf.png",
            "https://i.imgur.com/W3vjPvN.png",
        ],
        "website": "https://hypixel.net",
    },
    {
        "id": "mineblaze",
        "name": "MineBlaze",
        "address": "mc.mineblaze.net",
        "description": "Популярный русскоязычный сервер с режимами: Анархия, Гриф, SkyBlock, BedWars, MurderMystery.",
        "license": "both",
        "license_label": "Лицензия + Пиратка",
        "versions": ["1.12.2 - 1.21"],
        "versions_raw": ["1.12", "1.16", "1.20", "1.21"],
        "region": "RU",
        "icon_emoji": "🔥",
        "screenshots": [],
        "website": "https://mineblaze.net",
    },
    {
        "id": "holyworld",
        "name": "HolyWorld",
        "address": "play.holyworld.ru",
        "description": "Один из популярнейших серверов в СНГ с продуманной Анархией, клановыми войнами и уникальной экономикой.",
        "license": "both",
        "license_label": "Лицензия + Пиратка",
        "versions": ["1.12.2 - 1.20.4"],
        "versions_raw": ["1.12", "1.16", "1.20"],
        "region": "RU",
        "icon_emoji": "⚔️",
        "screenshots": [],
        "website": "https://holyworld.ru",
    },
    {
        "id": "mcskill",
        "name": "McSkill",
        "address": "mc.mcskill.net",
        "description": "Классический проект с индустриальными сборками, RPG, HardCore выживанием и сбалансированным геймплеем.",
        "license": "licensed",
        "license_label": "Лицензия",
        "versions": ["1.7.10 - 1.16.5"],
        "versions_raw": ["1.7", "1.12", "1.16"],
        "region": "RU",
        "icon_emoji": "💎",
        "screenshots": [],
        "website": "https://mcskill.net",
    },
    {
        "id": "grandmine",
        "name": "GrandMine",
        "address": "mc.grandmine.com",
        "description": "Русский сервер мини-игр с BedWars, SkyWars, Anarchy, Survival и быстрой регистрацией.",
        "license": "both",
        "license_label": "Лицензия + Пиратка",
        "versions": ["1.8 - 1.20"],
        "versions_raw": ["1.8", "1.16", "1.20"],
        "region": "RU",
        "icon_emoji": "👑",
        "screenshots": [],
        "website": "https://grandmine.com",
    },
    {
        "id": "minelandia",
        "name": "MineLandia",
        "address": "play.minelandia.net",
        "description": "Сервер для дружной игры: выживание без грифа, Creative миры, BedWars турниры.",
        "license": "both",
        "license_label": "Лицензия + Пиратка",
        "versions": ["1.8 - 1.20"],
        "versions_raw": ["1.8", "1.12", "1.16", "1.20"],
        "region": "RU",
        "icon_emoji": "🌍",
        "screenshots": [],
        "website": "https://minelandia.net",
    },
    {
        "id": "musteryworld",
        "name": "MusteryWorld",
        "address": "mc.musteryworld.ru",
        "description": "Сервер с авторскими мини-играми, PVP-аренами и регулярными ивентами.",
        "license": "both",
        "license_label": "Лицензия + Пиратка",
        "versions": ["1.12 - 1.20"],
        "versions_raw": ["1.12", "1.16", "1.20"],
        "region": "RU",
        "icon_emoji": "🎭",
        "screenshots": [],
        "website": "https://musteryworld.ru",
    },
    {
        "id": "skycube",
        "name": "SkyCube",
        "address": "play.skycube.ru",
        "description": "Проект с акцентом на соревновательный BedWars, SkyWars и Duels.",
        "license": "both",
        "license_label": "Лицензия + Пиратка",
        "versions": ["1.8 - 1.20"],
        "versions_raw": ["1.8", "1.20"],
        "region": "RU",
        "icon_emoji": "🧊",
        "screenshots": [],
        "website": "https://skycube.ru",
    },
    {
        "id": "mcpehub",
        "name": "MCPE Hub",
        "address": "play.mcpehub.com",
        "description": "Кроссплатформенный сервер для игроков на Java и Bedrock изданиях.",
        "license": "both",
        "license_label": "Лицензия + Пиратка",
        "versions": ["1.16 - 1.21"],
        "versions_raw": ["1.16", "1.20", "1.21"],
        "region": "International",
        "icon_emoji": "🌐",
        "screenshots": [],
        "website": "https://mcpehub.com",
    },
    {
        "id": "2b2t",
        "name": "2b2t",
        "address": "connect.2b2t.org",
        "description": "Старейший анархический сервер Minecraft в мире. Абсолютная свобода действий без правил и вайпов.",
        "license": "licensed",
        "license_label": "Лицензия",
        "versions": ["1.20.x"],
        "versions_raw": ["1.20"],
        "region": "US",
        "icon_emoji": "💀",
        "screenshots": [],
        "website": "https://2b2t.org",
    },
    {
        "id": "cubecraft",
        "name": "CubeCraft Games",
        "address": "play.cubecraft.net",
        "description": "Европейский гигант мини-игр: EggWars, Lucky Islands, Tower Defence, SkyBlock.",
        "license": "licensed",
        "license_label": "Лицензия",
        "versions": ["1.8 - 1.21"],
        "versions_raw": ["1.8", "1.20", "1.21"],
        "region": "EU",
        "icon_emoji": "🥚",
        "screenshots": [],
        "website": "https://cubecraft.net",
    },
    {
        "id": "funnygame",
        "name": "FunnyGame",
        "address": "play.funnygame.su",
        "description": "Комплекс режимов для отдыха с друзьями: BuildBattle, MurderMystery, BedWars.",
        "license": "both",
        "license_label": "Лицензия + Пиратка",
        "versions": ["1.8 - 1.19"],
        "versions_raw": ["1.8", "1.16", "1.19"],
        "region": "RU",
        "icon_emoji": "🎪",
        "screenshots": [],
        "website": "https://funnygame.su",
    },
    {
        "id": "vipermc",
        "name": "ViperMC",
        "address": "play.vipermc.net",
        "description": "Классический HCF и Hardcore сервер с активным PVP комьюнити.",
        "license": "both",
        "license_label": "Лицензия + Пиратка",
        "versions": ["1.8 - 1.20"],
        "versions_raw": ["1.8", "1.20"],
        "region": "RU",
        "icon_emoji": "🐍",
        "screenshots": [],
        "website": "https://vipermc.net",
    },
    {
        "id": "spworlds",
        "name": "SPWorlds",
        "address": "mc.spworlds.ru",
        "description": "Приватный сервер с акцентом на отыгрыш роли, живую экономику и города игроков.",
        "license": "licensed",
        "license_label": "Лицензия",
        "versions": ["1.20"],
        "versions_raw": ["1.20"],
        "region": "RU",
        "icon_emoji": "🌱",
        "screenshots": [],
        "website": "https://spworlds.ru",
    },
]

_APP_WINDOW: Optional[webview.Window] = None
_JAR_CACHE: Dict[Any, Dict[str, Any]] = {}
_MOJANG_VERSIONS_CACHE: Optional[Dict[str, Any]] = None
_SERVERS_CACHE: Optional[Dict[str, Any]] = None
_JAR_CACHE_LOCK = threading.Lock()

# HTML шаблон письма
EMAIL_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><title>Код подтверждения Cube Launcher</title></head>
<body style="margin:0;padding:0;background:#080708;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#f8fafc;">
<table border="0" cellpadding="0" cellspacing="0" width="100%" style="background:#080708;padding:40px 10px;">
<tr><td align="center">
<table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width:520px;background:#181416;border:1px solid #2e262a;border-radius:18px;overflow:hidden;box-shadow:0 12px 36px rgba(0,0,0,0.6);">
<tr><td align="center" style="padding:32px 20px 20px 20px;border-bottom:1px solid #2e262a;">
<div style="font-size:22px;font-weight:800;letter-spacing:2px;color:#f97316;text-transform:uppercase;">&#9632; CUBE LAUNCHER</div>
</td></tr>
<tr><td style="padding:32px 36px 20px 36px;text-align:center;">
<h1 style="font-size:22px;font-weight:700;margin:0 0 12px 0;color:#ffffff;">{ACTION_TITLE}</h1>
<p style="font-size:14px;line-height:1.6;color:#9ca3af;margin:0 0 24px 0;">{ACTION_DESC}</p>
<div style="background:#0c0a0b;border:2px dashed #f97316;border-radius:14px;padding:18px 14px;margin:0 auto 12px auto;max-width:320px;">
<span style="font-size:36px;font-weight:800;letter-spacing:10px;color:#f97316;font-family:monospace;user-select:all;-webkit-user-select:all;">{VERIFICATION_CODE}</span>
</div>
<p style="font-size:12px;color:#9ca3af;margin:0 0 20px 0;">💡 Нажмите дважды на код, чтобы скопировать его</p>
<p style="font-size:12px;color:#6b7280;margin:0;line-height:1.5;">&#9201; Срок действия: <b>5 минут</b>.</p>
</td></tr>
<tr><td style="padding:20px 36px;background:#120e10;border-top:1px solid #2e262a;text-align:center;">
<p style="font-size:11px;color:#4b5563;margin:0;">© 2026 Cube Launcher. Все права защищены.</p>
</td></tr>
</table></td></tr></table></body></html>"""


# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================
def clean_email_for_key(email: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "_", email.strip().lower())


def clean_username_for_key(username: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "", username.strip().lower())


_MC_COLOR_RE = re.compile(r"§[0-9a-fk-or]", re.IGNORECASE)
_MC_HEX_RE = re.compile(r"§x(§[0-9a-fA-F]){6}", re.IGNORECASE)


def strip_mc_formatting(text: Optional[str]) -> str:
    if not text:
        return ""
    s = _MC_HEX_RE.sub("", str(text))
    s = _MC_COLOR_RE.sub("", s)
    return s


def send_html_mail(to_email: str, code: str, is_login: bool = False) -> Tuple[bool, str]:
    title = "Подтверждение входа" if is_login else "Подтверждение регистрации"
    desc = (
        "Вы запросили вход в ваш профиль <b style='color: #f8fafc;'>Cube Launcher</b>. Введите код подтверждения:"
        if is_login
        else "Вы запросили создание аккаунта в <b style='color: #f8fafc;'>Cube Launcher</b>. Введите код:"
    )
    html_content = (
        EMAIL_HTML_TEMPLATE
        .replace("{VERIFICATION_CODE}", code)
        .replace("{ACTION_TITLE}", title)
        .replace("{ACTION_DESC}", desc)
    )

    if RESEND_API_KEY:
        try:
            res = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": RESEND_FROM_EMAIL,
                    "to": [to_email],
                    "subject": f"Код: {code} — Cube Launcher",
                    "html": html_content,
                },
                timeout=8,
            )
            if res.status_code in (200, 201):
                return True, "Письмо отправлено!"
            try:
                err = res.json().get("message", res.text)
            except Exception:
                err = res.text
            return False, f"Resend: {err}"
        except Exception as e:
            log.warning("Resend error: %s", e)
            return False, f"Ошибка сети Resend: {e}"

    if SMTP_USER and SMTP_PASSWORD:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Код: {code} — Cube Launcher"
            msg["From"] = SMTP_USER
            msg["To"] = to_email
            msg.attach(MIMEText(html_content, "html", "utf-8"))
            if SMTP_PORT == 465:
                with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=8) as server:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                    server.sendmail(SMTP_USER, [to_email], msg.as_string())
            else:
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=8) as server:
                    server.starttls()
                    server.login(SMTP_USER, SMTP_PASSWORD)
                    server.sendmail(SMTP_USER, [to_email], msg.as_string())
            return True, "Письмо отправлено!"
        except Exception as e:
            log.warning("SMTP error: %s", e)
            return False, f"Ошибка SMTP: {e}"

    log.info("[ТЕСТОВЫЙ РЕЖИМ] Код подтверждения для %s: %s", to_email, code)
    return True, f"Код сгенерирован (Тестовый режим: {code})"


def load_json(filepath: str, default_value: Any) -> Any:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning("Ошибка чтения %s: %s", filepath, e)
    return default_value


def save_json(filepath: str, data: Any) -> bool:
    try:
        tmp_path = filepath + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        os.replace(tmp_path, filepath)
        return True
    except Exception as e:
        log.warning("Ошибка сохранения %s: %s", filepath, e)
        return False


def load_stats() -> Dict[str, int]:
    default_stats = {
        "launcher_seconds": 0,
        "minecraft_seconds": 0,
        "launches": 0,
        "last_session_start": 0,
        "last_mc_start": 0,
        "last_sync": 0,
    }
    data = load_json(STATS_FILE, default_stats)
    if not isinstance(data, dict):
        data = {}
    for k, v in default_stats.items():
        if k not in data:
            data[k] = v
    return data


def save_stats(stats: Dict[str, Any]) -> None:
    save_json(STATS_FILE, stats)


def download_file_safely(url: str, dest_path: str, timeout: int = 25) -> bool:
    try:
        with SESSION.get(url, headers=HEADERS, stream=True, timeout=timeout) as res:
            if res.status_code != 200:
                log.warning("download_file_safely: %s -> %s", url, res.status_code)
                return False
            tmp_path = dest_path + ".part"
            with open(tmp_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)
            os.replace(tmp_path, dest_path)
            return True
    except Exception as e:
        log.warning("Ошибка скачивания %s: %s", url, e)
        return False


def calculate_sha1(filepath: str) -> Optional[str]:
    try:
        h = hashlib.sha1()
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024  # type: ignore
    return f"{n:.1f}TB"


def extract_jar_metadata(file_path: str) -> Dict[str, Any]:
    """Извлекает метаданные .jar/.zip/.disabled с кэшированием по mtime и размеру."""
    try:
        stat = os.stat(file_path)
        cache_key = (file_path, stat.st_mtime, stat.st_size)
        with _JAR_CACHE_LOCK:
            cached = _JAR_CACHE.get(cache_key)
        if cached is not None:
            return cached
    except Exception:
        cache_key = None

    base_name = os.path.basename(file_path)
    is_disabled = base_name.endswith(".disabled")
    clean_name = base_name[:-9] if is_disabled else base_name

    meta: Dict[str, Any] = {
        "filename": base_name,
        "clean_name": clean_name,
        "display_name": clean_name.replace(".jar", "").replace(".zip", ""),
        "version": "v1.0.0",
        "author": "Не указан",
        "icon": "",
        "enabled": not is_disabled,
        "version_type": "release",
    }

    if not (file_path.endswith(".jar") or file_path.endswith(".jar.disabled")):
        meta["display_name"] = strip_mc_formatting(meta["display_name"])
        return meta

    try:
        with zipfile.ZipFile(file_path, "r") as z:
            names = set(z.namelist())
            if "fabric.mod.json" in names:
                with z.open("fabric.mod.json") as f:
                    data = json.loads(f.read().decode("utf-8", errors="ignore"))
                meta["display_name"] = data.get("name", meta["display_name"])
                meta["version"] = str(data.get("version", meta["version"]))
                authors = data.get("authors", [])
                if authors:
                    first = authors[0]
                    meta["author"] = (
                        first.get("name", str(first))
                        if isinstance(first, dict)
                        else str(first)
                    )
                icon_path = data.get("icon")
                if isinstance(icon_path, dict) and icon_path:
                    icon_path = list(icon_path.values())[0]
                if icon_path and icon_path in names:
                    icon_bytes = z.read(icon_path)
                    if len(icon_bytes) < 512 * 1024:
                        meta["icon"] = (
                            "data:image/png;base64,"
                            + base64.b64encode(icon_bytes).decode("utf-8")
                        )
            elif "quilt.mod.json" in names:
                with z.open("quilt.mod.json") as f:
                    data = json.loads(f.read().decode("utf-8", errors="ignore"))
                ql = data.get("quilt_loader", {})
                meta_block = ql.get("metadata", {})
                meta["display_name"] = meta_block.get("name", meta["display_name"])
                meta["version"] = str(ql.get("version", meta["version"]))
            elif "META-INF/mods.toml" in names:
                text = z.read("META-INF/mods.toml").decode("utf-8", errors="ignore")
                for line in text.splitlines():
                    if "displayName" in line and "=" in line:
                        meta["display_name"] = (
                            line.split("=", 1)[1].strip().strip("\"'")
                        )
                    elif line.strip().startswith("version=") and "=" in line:
                        meta["version"] = line.split("=", 1)[1].strip().strip("\"'")
            elif "META-INF/neoforge.mods.toml" in names:
                text = z.read("META-INF/neoforge.mods.toml").decode("utf-8", errors="ignore")
                for line in text.splitlines():
                    if "displayName" in line and "=" in line:
                        meta["display_name"] = (
                            line.split("=", 1)[1].strip().strip("\"'")
                        )
                    elif line.strip().startswith("version=") and "=" in line:
                        meta["version"] = line.split("=", 1)[1].strip().strip("\"'")
    except Exception as e:
        log.debug("extract_jar_metadata(%s): %s", file_path, e)

    meta["display_name"] = strip_mc_formatting(meta["display_name"])
    if cache_key:
        with _JAR_CACHE_LOCK:
            _JAR_CACHE[cache_key] = meta
            if len(_JAR_CACHE) > 600:
                for k in list(_JAR_CACHE.keys())[:150]:
                    _JAR_CACHE.pop(k, None)
    return meta
"""
Cube Launcher - Official Desktop Client
Part 2 of 8: Config Management, LauncherAPI Core, Live Analytics & Cloud State
"""


def ensure_cube_visuals_instance(config: Dict[str, Any]) -> Dict[str, Any]:
    instances = config.get("instances", [])
    cube_inst = next((i for i in instances if i.get("id") == "CubeVisuals"), None)
    if not cube_inst:
        cube_inst = {
            "id": "CubeVisuals",
            "name": "CubeVisuals",
            "mc_version": "1.21.11",
            "loader": "fabric",
            "loader_version": "latest",
            "icon": "✨",
            "custom_icon": "",
        }
        instances.insert(0, cube_inst)
        config["instances"] = instances
        save_json(CONFIG_FILE, config)

    inst_dir = os.path.join(INSTANCES_DIR, "CubeVisuals")
    mods_dir = os.path.join(inst_dir, "mods")
    os.makedirs(mods_dir, exist_ok=True)
    for folder in ("shaderpacks", "resourcepacks", "datapacks"):
        os.makedirs(os.path.join(inst_dir, folder), exist_ok=True)

    def bg_download() -> None:
        target_jar = os.path.join(mods_dir, "cubevisuals-1.0.jar")
        try:
            if not os.path.exists(target_jar) or os.path.getsize(target_jar) < 10240:
                download_file_safely(CUBE_VISUALS_URL, target_jar)
        except Exception as e:
            log.warning("bg_download CubeVisuals: %s", e)

    threading.Thread(target=bg_download, daemon=True, name="cubevisuals-dl").start()
    return config


def load_config() -> Dict[str, Any]:
    default_config: Dict[str, Any] = {
        "launcher_path": LAUNCHER_DIR,
        "game_path": GAME_DIR,
        "active_instance_id": "CubeVisuals",
        "ram_mb": 4096,
        "enable_console": False,
        "jvm_args": "",
        "banner_path": "",
        "show_banner": True,
        "theme": "dark",
        "language": "ru",
        "animations_enabled": True,
        "animation_speed": 1.0,
        "discord_rpc": True,
        "telemetry": True,
        "show_game_activity": True,
        "show_cube_visuals": True,
        "liquid_glass": "off",
        "instances": [
            {
                "id": "CubeVisuals",
                "name": "CubeVisuals",
                "mc_version": "1.21.11",
                "loader": "fabric",
                "loader_version": "latest",
                "icon": "✨",
                "custom_icon": "",
            }
        ],
    }
    cfg = load_json(CONFIG_FILE, default_config)
    if not isinstance(cfg, dict):
        cfg = dict(default_config)
    for k, v in default_config.items():
        if k not in cfg:
            cfg[k] = v
    if "ram_gb" in cfg and "ram_mb" not in cfg:
        try:
            cfg["ram_mb"] = int(cfg["ram_gb"]) * 1024
        except Exception:
            cfg["ram_mb"] = 4096
    return ensure_cube_visuals_instance(cfg)


def load_accounts() -> List[Dict[str, Any]]:
    default_accounts = [{"username": "Player", "type": "offline", "active": True}]
    data = load_json(ACCOUNTS_FILE, default_accounts)
    if not isinstance(data, list):
        data = list(default_accounts)
    return data


def load_cube_accounts() -> List[Dict[str, Any]]:
    data = load_json(CUBE_ACCOUNTS_FILE, [])
    if not isinstance(data, list):
        return []
    return data


class LauncherAPI:
    """Основной мост между Python бэкендом и JavaScript фронтендом через pywebview."""

    def __init__(self) -> None:
        self.config: Dict[str, Any] = load_config()
        self.accounts: List[Dict[str, Any]] = load_accounts()
        self.cube_accounts: List[Dict[str, Any]] = load_cube_accounts()
        self.users_registry: Dict[str, str] = load_json(USERS_REGISTRY_FILE, {})
        if not isinstance(self.users_registry, dict):
            self.users_registry = {}

        self._last_progress_time: float = 0.0
        self._game_process: Optional[subprocess.Popen] = None
        self.active_running_instance_id: Optional[str] = None
        self._current_captcha: Optional[str] = None
        self._current_captcha_created: float = 0.0
        self._discord_rpc: Optional[Any] = None

        self._current_watching_inst: Optional[str] = None
        self._current_watching_type: str = "mods"
        self._last_folder_snapshot: Optional[Any] = None

        self._optifine_cache: Dict[str, Tuple[bool, str, float]] = {}
        self._game_lock = threading.RLock()

        # === Инициализация трея ===
        self._tray_icon: Optional[Any] = None
        self._is_in_tray: bool = False

        # Запускаем трей навсегда с первой секунды
        self._init_tray()

        # Кулдаун отправки статистики в облако
        self._last_cloud_stats_sync: float = 0.0

        # === Статистика лаунчера и игры ===
        self.stats: Dict[str, int] = load_stats()
        self.launcher_session_start: float = time.time()
        self.stats["last_session_start"] = int(self.launcher_session_start)
        self.stats["last_mc_start"] = 0
        save_stats(self.stats)

        # === Поток учёта времени (Live) ===
        self._shutdown = threading.Event()
        self._stats_thread = threading.Thread(
            target=self._stats_tracker_loop, daemon=True, name="stats-tracker"
        )
        self._stats_thread.start()

        # === Поток мгновенных уведомлений сообщений ===
        self._last_seen_msg_ts: Dict[str, int] = {}
        self._notified_chat_cache: Dict[str, int] = {}
        self._notified_cache_order: List[str] = []
        self._notifier_thread = threading.Thread(
            target=self._message_notifier_loop, daemon=True, name="msg-notifier"
        )
        self._notifier_thread.start()

        # === Кэш мониторинга серверов ===
        self.servers_cache: Dict[str, Dict[str, Any]] = {}
        self._servers_cache_lock = threading.Lock()
        self.servers_loading: bool = False

        # === Кэш прямого SLP статуса Cube Vanilla ===
        self._cube_vanilla_cache: Dict[str, Any] = {}
        self._cube_vanilla_lock = threading.Lock()

        if HAS_DISCORD_RPC and self.config.get("discord_rpc"):
            self._init_discord_rpc()

    # ================= СЛУЖЕБНЫЕ МЕТОДЫ =================
    def _eval_js(self, script: str) -> None:
        try:
            if _APP_WINDOW is not None:
                _APP_WINDOW.evaluate_js(script)
        except Exception as e:
            log.debug("JS eval error: %s", e)

    def _show_toast(self, message: Any, type_: str = "info") -> None:
        msg = (
            str(message)
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\n", "\\n")
            .replace("\r", "")
        )
        self._eval_js(f"showToast('{msg}', '{type_}')")

    def _update_status(self, text: Any, progress: Optional[int] = None) -> None:
        txt = (
            str(text)
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\n", " ")
            .replace("\r", "")
        )
        if progress is None:
            self._eval_js(f"updateDownloadStatus('{txt}')")
        else:
            try:
                self._eval_js(f"updateDownloadStatus('{txt}', {int(progress)})")
            except Exception:
                self._eval_js(f"updateDownloadStatus('{txt}')")

    def _init_discord_rpc(self) -> None:
        if not HAS_DISCORD_RPC:
            return
        try:
            self._discord_rpc = Presence(DISCORD_CLIENT_ID)  # type: ignore
            self._discord_rpc.connect()  # type: ignore
            self._discord_rpc.update(  # type: ignore
                state="Готовится к игре",
                details="В лаунчере",
                large_text="Cube Launcher",
            )
        except Exception as e:
            log.warning("[Discord RPC] Не удалось подключиться: %s", e)
            self._discord_rpc = None

    def _update_discord_presence(
        self, details: str = "В лаунчере", state: str = "Готовится к игре"
    ) -> None:
        if not HAS_DISCORD_RPC or not self._discord_rpc:
            return
        try:
            self._discord_rpc.update(  # type: ignore
                details=details, state=state, large_text="Cube Launcher"
            )
        except Exception as e:
            log.debug("[Discord RPC update] %s", e)

    # ================= УЧЁТ ВРЕМЕНИ (LIVE СИНХРОНИЗАЦИЯ) =================
    def _stats_tracker_loop(self) -> None:
        """Посекундно обновляет статистику времени и отправляет Live-данные в UI."""
        last_tick = time.time()
        last_sync = time.time()
        while not self._shutdown.is_set():
            try:
                if self._shutdown.wait(1):
                    break
                now = time.time()
                delta = int(now - last_tick)
                last_tick = now
                self.stats["launcher_seconds"] = int(
                    self.stats.get("launcher_seconds", 0)
                ) + delta

                # Отправляем живые данные в UI лаунчера
                try:
                    stats_json = json.dumps(self.get_stats())
                    self._eval_js(f"updateLiveStats({stats_json})")
                except Exception:
                    pass

                # Каждые 30 секунд сохраняем локально и синхронизируем с Firestore
                if now - last_sync >= 30:
                    last_sync = now
                    self.stats["last_sync"] = int(now)
                    save_stats(self.stats)
                    self._sync_stats_to_cloud() 
                    self._sync_presence()
            except Exception as e:
                log.warning("[stats tracker] %s", e)

    def _firestore_headers(self) -> Dict[str, str]:
        headers = dict(HEADERS)
        if self.cube_user and self.cube_user.get("token"):
            headers["Authorization"] = f"Bearer {self.cube_user['token']}"
        headers["Content-Type"] = "application/json"
        return headers

    def _sync_stats_to_cloud(self, force: bool = False) -> None:
        try:
            user = self.cube_user
            if not user or not user.get("id"):
                return
            if not FIREBASE_API_KEY:
                return

            now = time.time()
            # ЗАДЕРЖКА: отправляем в облако не чаще одного раза в 3 минуты (180 сек),
            # если только это не принудительное сохранение при выходе (force=True)
            if not force and (now - self._last_cloud_stats_sync < 180):
                return
            self._last_cloud_stats_sync = now

            uid = user["id"]
            url = (
                f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}"
                f"/databases/(default)/documents/users/{uid}"
                f"?updateMask.fieldPaths=stat_launcher_seconds"
                f"&updateMask.fieldPaths=stat_minecraft_seconds"
                f"&updateMask.fieldPaths=stat_launches"
                f"&key={FIREBASE_API_KEY}"
            )
            payload = {
                "fields": {
                    "stat_launcher_seconds": {
                        "integerValue": str(int(self.stats.get("launcher_seconds", 0)))
                    },
                    "stat_minecraft_seconds": {
                        "integerValue": str(int(self.stats.get("minecraft_seconds", 0)))
                    },
                    "stat_launches": {
                        "integerValue": str(int(self.stats.get("launches", 0)))
                    },
                }
            }
            res = SESSION.patch(
                url, json=payload, headers=self._firestore_headers(), timeout=6
            )
            if res.status_code not in (200, 201):
                log.debug("Sync stats -> %s: %s", res.status_code, res.text[:200])
        except Exception as e:
            log.debug("[_sync_stats_to_cloud] %s", e)

    def _sync_presence(self) -> None:
        try:
            user = self.cube_user
            if not user or not user.get("id"):
                return
            if not FIREBASE_API_KEY:
                return
            uid = user["id"]
            url = (
                f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}"
                f"/databases/(default)/documents/users/{uid}"
                f"?updateMask.fieldPaths=last_seen&key={FIREBASE_API_KEY}"
            )
            payload = {"fields": {"last_seen": {"integerValue": str(int(time.time()))}}}
            SESSION.patch(
                url, json=payload, headers=self._firestore_headers(), timeout=4
            )
        except Exception as e:
            log.debug("[_sync_presence] %s", e)

    def get_stats(self) -> Dict[str, Any]:
        s = self.stats
        return {
            "status": "ok",
            "launcher_seconds": int(s.get("launcher_seconds", 0)),
            "minecraft_seconds": int(s.get("minecraft_seconds", 0)),
            "launches": int(s.get("launches", 0)),
            "launcher_hours": round(int(s.get("launcher_seconds", 0)) / 3600.0, 1),
            "minecraft_hours": round(int(s.get("minecraft_seconds", 0)) / 3600.0, 1),
        }

    def get_user_stats(self, uid: str) -> Dict[str, Any]:
        try:
            url = (
                f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}"
                f"/databases/(default)/documents/users/{uid}?key={FIREBASE_API_KEY}"
            )
            res = SESSION.get(url, headers=self._firestore_headers(), timeout=5)
            if res.status_code == 200:
                fields = res.json().get("fields", {})
                ls = int(fields.get("stat_launcher_seconds", {}).get("integerValue", 0))
                ms = int(fields.get("stat_minecraft_seconds", {}).get("integerValue", 0))
                lc = int(fields.get("stat_launches", {}).get("integerValue", 0))
                return {
                    "status": "ok",
                    "launcher_seconds": ls,
                    "minecraft_seconds": ms,
                    "launches": lc,
                    "launcher_hours": round(ls / 3600.0, 1),
                    "minecraft_hours": round(ms / 3600.0, 1),
                }
        except Exception as e:
            log.debug("[get_user_stats] %s", e)
        return {
            "status": "error",
            "launcher_seconds": 0,
            "minecraft_seconds": 0,
            "launches": 0,
            "launcher_hours": 0.0,
            "minecraft_hours": 0.0,
        }

    # ================= УВЕДОМЛЕНИЯ О НОВЫХ СООБЩЕНИЯХ =================
    def _message_notifier_loop(self) -> None:
        while not self._shutdown.is_set():
            try:
                if self._shutdown.wait(10):
                    break
                user = self.cube_user
                if not user or not user.get("id"):
                    continue
                my_uid = user["id"]
                friends_url = (
                    f"https://firestore.googleapis.com/v1/projects/"
                    f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
                    f"friend_requests?key={FIREBASE_API_KEY}"
                )
                r = SESSION.get(
                    friends_url, headers=self._firestore_headers(), timeout=6
                )
                if r.status_code != 200:
                    continue
                docs = r.json().get("documents", [])
                friend_uids: List[Tuple[str, str]] = []
                for d in docs:
                    f = d.get("fields", {})
                    if f.get("status", {}).get("stringValue") != "accepted":
                        continue
                    fu = f.get("from_uid", {}).get("stringValue")
                    tu = f.get("to_uid", {}).get("stringValue")
                    from_name = f.get("from_username", {}).get("stringValue", "")
                    to_name = f.get("to_username", {}).get("stringValue", "")
                    if fu == my_uid:
                        friend_uids.append((tu, to_name))
                    elif tu == my_uid:
                        friend_uids.append((fu, from_name))

                for friend_uid, friend_name in friend_uids:
                    if self._shutdown.is_set():
                        return
                    chat_key = f"{min(my_uid, friend_uid)}_{max(my_uid, friend_uid)}"
                    msg_url = (
                        f"https://firestore.googleapis.com/v1/projects/"
                        f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
                        f"chats/{chat_key}/messages?key={FIREBASE_API_KEY}"
                    )
                    mr = SESSION.get(
                        msg_url, headers=self._firestore_headers(), timeout=5
                    )
                    if mr.status_code != 200:
                        continue
                    mdocs = mr.json().get("documents", [])
                    if not mdocs:
                        continue
                    newest_incoming_ts = 0
                    newest_text = ""
                    for md in mdocs:
                        mf = md.get("fields", {})
                        sender = mf.get("sender_uid", {}).get("stringValue", "")
                        ts = int(mf.get("timestamp", {}).get("integerValue", 0))
                        if sender != my_uid and ts > newest_incoming_ts:
                            newest_incoming_ts = ts
                            _t = mf.get("text", {}).get("stringValue", "")
                            _v = mf.get("voice", {}).get("stringValue", "")
                            if _t:
                                newest_text = _t
                            elif _v:
                                newest_text = "🎤 Голосовое сообщение"
                            else:
                                newest_text = "📷 Вложение"
                    if newest_incoming_ts == 0:
                        continue
                    prev_ts = self._notified_chat_cache.get(chat_key, 0)
                    if chat_key not in self._notified_chat_cache:
                        self._notified_chat_cache[chat_key] = newest_incoming_ts
                        self._notified_cache_order.append(chat_key)
                        continue
                    if newest_incoming_ts > prev_ts:
                        self._notified_chat_cache[chat_key] = newest_incoming_ts
                        short = newest_text[:70] + (
                            "..." if len(newest_text) > 70 else ""
                        )
                        safe_name = str(friend_name).replace("'", "\\'")
                        safe_msg = (
                            str(short).replace("'", "\\'").replace("\n", " ")
                        )
                        try:
                            self._eval_js(
                                f"showChatNotification('{safe_name}', "
                                f"'{safe_msg}', '{friend_uid}', '{chat_key}')"
                            )
                        except Exception:
                            pass

                while len(self._notified_cache_order) > 200:
                    old_key = self._notified_cache_order.pop(0)
                    self._notified_chat_cache.pop(old_key, None)
            except Exception as e:
                log.debug("[msg notifier] %s", e)

    # ================= ГОЛОСОВЫЕ СООБЩЕНИЯ =================
    def send_voice_message(
        self, friend_uid: str, base64_audio: str, duration: int = 0
    ) -> Dict[str, str]:
        user = self.cube_user
        if not user:
            return {"status": "error", "message": "Не авторизован"}
        try:
            approx_bytes = len(base64_audio) * 3 // 4 if base64_audio else 0
            if approx_bytes > MAX_VOICE_BYTES:
                return {
                    "status": "error",
                    "message": f"Голосовое сообщение слишком большое "
                    f"({human_bytes(approx_bytes)}). Ограничение — "
                    f"{human_bytes(MAX_VOICE_BYTES)}.",
                }
        except Exception:
            pass
        try:
            chat_id = f"{min(user['id'], friend_uid)}_{max(user['id'], friend_uid)}"
            msg_id = f"msg_{int(time.time() * 1000)}"
            url = (
                f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}"
                f"/databases/(default)/documents/chats/{chat_id}/messages/{msg_id}"
                f"?key={FIREBASE_API_KEY}"
            )
            payload = {
                "fields": {
                    "sender_uid": {"stringValue": user["id"]},
                    "text": {"stringValue": ""},
                    "image": {"stringValue": ""},
                    "voice": {"stringValue": base64_audio or ""},
                    "voice_duration": {"integerValue": str(int(duration))},
                    "timestamp": {
                        "integerValue": str(int(time.time() * 1000))
                    },
                }
            }
            res = SESSION.patch(
                url,
                json=payload,
                headers=self._firestore_headers(),
                timeout=8,
            )
            if res.status_code not in (200, 201):
                return {
                    "status": "error",
                    "message": f"Firestore: {res.status_code}",
                }
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ================= УПРАВЛЕНИЕ ОКНОМ И НАСТРОЙКИ =================
    def minimize(self) -> Dict[str, str]:
        try:
            if _APP_WINDOW:
                _APP_WINDOW.minimize()
        except Exception as e:
            log.debug("minimize error: %s", e)
        return {"status": "ok"}

    # ================= УПРАВЛЕНИЕ ТРЕЕМ И ОКНОМ =================
    def _get_tray_image(self):
        """Загружает иконку для трея или рисует оранжевый квадрат, если файла нет."""
        if os.path.exists(ICON_PATH) and HAS_PIL:
            try:
                return Image.open(ICON_PATH)
            except Exception:
                pass
        if HAS_PIL:
            return Image.new('RGB', (64, 64), color=(249, 115, 22))
        return None

    def _init_tray(self) -> None:
        """Запускает иконку в трее сразу при старте лаунчера."""
        if not HAS_PYSTRAY:
            return
        try:
            tray_img = self._get_tray_image()
            if tray_img and not self._tray_icon:
                menu = pystray.Menu(
                    item('Открыть лаунчер', self.show_from_tray, default=True),
                    item('Закрыть лаунчер', self.quit_app)
                )
                self._tray_icon = pystray.Icon("CubeLauncher", tray_img, "Cube Launcher", menu)
                threading.Thread(target=self._tray_icon.run, daemon=True, name="tray-thread").start()
        except Exception as e:
            log.warning("Ошибка инициализации трея: %s", e)

    def show_from_tray(self, icon=None, item=None) -> None:
        """Открывает окно лаунчера (иконка в трее при этом ОСТАЕТСЯ)."""
        try:
            if _APP_WINDOW:
                _APP_WINDOW.show()
                _APP_WINDOW.restore()
            self._is_in_tray = False
        except Exception as e:
            log.warning("show_from_tray error: %s", e)

    def quit_app(self, icon=None, item=None) -> None:
        """Полное закрытие лаунчера: убирает иконку из трея и завершает процесс."""
        try:
            log.info("Полное завершение работы Cube Launcher...")
            # Удаляем иконку из трея
            if self._tray_icon:
                self._tray_icon.stop()
                self._tray_icon = None

            # Сохраняем статистику в облако
            now = time.time()
            self.stats["last_sync"] = int(now)
            save_stats(self.stats)
            self._sync_stats_to_cloud()

            self._shutdown.set()

            # Отключаем Discord RPC
            if self._discord_rpc:
                try:
                    self._discord_rpc.close()
                except Exception:
                    pass

            # Если была запущена игра — закрываем
            if self._game_process and self._game_process.poll() is None:
                self.kill_game()

            # Закрываем само окно
            if _APP_WINDOW:
                _APP_WINDOW.destroy()
        except Exception as e:
            log.warning("quit_app error: %s", e)
        finally:
            os._exit(0)

    def close(self) -> Dict[str, str]:
        """При нажатии на крестик (✕) окно просто скрывается, а иконка в трее продолжает жить."""
        if not HAS_PYSTRAY:
            return self.quit_app()

        try:
            if _APP_WINDOW:
                _APP_WINDOW.hide()
            self._is_in_tray = True
        except Exception as e:
            log.warning("close error: %s", e)
            self.quit_app()

        return {"status": "ok"}

    def get_config(self) -> Dict[str, Any]:
        return self.config

    def save_settings_auto(
        self,
        ram_mb: Any,
        enable_console: Any,
        jvm_args: Any,
        banner_path: Any,
        theme: Any,
        language: Any,
        animations_enabled: Any,
        animation_speed: Any,
        discord_rpc: Any,
        telemetry: Any,
        show_game_activity: Any,
        show_banner: Any = True,
        liquid_glass: Optional[str] = None,
    ) -> Dict[str, str]:
        try:
            try:
                self.config["ram_mb"] = int(ram_mb) if ram_mb is not None else 4096
            except (TypeError, ValueError):
                self.config["ram_mb"] = 4096
            self.config["enable_console"] = bool(enable_console)
            self.config["jvm_args"] = jvm_args or ""
            if banner_path is not None:
                self.config["banner_path"] = banner_path
            self.config["theme"] = theme or "dark"
            self.config["language"] = language or "ru"
            self.config["animations_enabled"] = bool(animations_enabled)
            try:
                self.config["animation_speed"] = float(animation_speed)
            except (TypeError, ValueError):
                self.config["animation_speed"] = 1.0
            self.config["discord_rpc"] = bool(discord_rpc)
            self.config["telemetry"] = bool(telemetry)
            self.config["show_game_activity"] = bool(show_game_activity)
            self.config["show_banner"] = bool(show_banner)
            if liquid_glass is not None:
                valid = ("off", "frosted", "standard", "transparent")
                self.config["liquid_glass"] = (
                    liquid_glass if liquid_glass in valid else "off"
                )
            save_json(CONFIG_FILE, self.config)
            return {"status": "ok"}
        except Exception as e:
            log.warning("[save_settings_auto] %s", e)
            return {"status": "error", "message": str(e)}

    def start_watching_instance(
        self, instance_id: str, resource_type: str = "mods"
    ) -> Dict[str, str]:
        self._current_watching_inst = instance_id
        self._current_watching_type = resource_type or "mods"
        return {"status": "ok"}

    def stop_watching_instance(self) -> Dict[str, str]:
        self._current_watching_inst = None
        self._last_folder_snapshot = None
        return {"status": "ok"}

    def save_dropped_file_data(
        self, instance_id: str, resource_type: str, filename: str, base64_data: str
    ) -> Dict[str, str]:
        try:
            if not is_safe_id(instance_id):
                return {"status": "error", "message": "Некорректный id сборки"}
            if resource_type not in ("mods", "shaderpacks", "resourcepacks", "datapacks"):
                return {"status": "error", "message": "Некорректный тип ресурса"}
            safe_name = os.path.basename(filename)
            if not safe_name or safe_name in (".", ".."):
                return {"status": "error", "message": "Некорректное имя файла"}
            target_dir = safe_join(INSTANCES_DIR, instance_id, resource_type)
            if not target_dir:
                return {"status": "error", "message": "Ошибка пути"}
            os.makedirs(target_dir, exist_ok=True)
            file_path = os.path.join(target_dir, safe_name)
            data_bytes = base64.b64decode(base64_data)
            with open(file_path, "wb") as f:
                f.write(data_bytes)
            with _JAR_CACHE_LOCK:
                _JAR_CACHE.clear()
            return {"status": "ok", "filename": safe_name}
        except Exception as e:
            log.warning("[save_dropped_file_data] %s", e)
            return {"status": "error", "message": str(e)}

    # ================= УПРАВЛЕНИЕ АККАУНТАМИ CUBE =================
    @property
    def cube_user(self) -> Optional[Dict[str, Any]]:
        active = next((u for u in self.cube_accounts if u.get("active")), None)
        if active is not None:
            return active
        if self.cube_accounts:
            return self.cube_accounts[0]
        return None

    def _normalize_active_cube_account(self) -> None:
        if not self.cube_accounts:
            return
        if not any(u.get("active") for u in self.cube_accounts):
            self.cube_accounts[0]["active"] = True
            save_json(CUBE_ACCOUNTS_FILE, self.cube_accounts)

    def get_cube_accounts_list(self) -> Dict[str, Any]:
        self._normalize_active_cube_account()
        return {
            "status": "ok",
            "accounts": self.cube_accounts,
            "current": self.cube_user,
        }

    def switch_cube_account(self, uid: str) -> Dict[str, Any]:
        found = False
        for u in self.cube_accounts:
            if u.get("id") == uid:
                u["active"] = True
                found = True
            else:
                u["active"] = False
        if not found:
            return {"status": "error", "message": "Аккаунт не найден"}
        save_json(CUBE_ACCOUNTS_FILE, self.cube_accounts)
        self._eval_js("refreshMainProfileUI()")
        user = self.cube_user
        if user:
            self._show_toast(
                f"Вы переключились на аккаунт {user['username']}!", "success"
            )
        return {"status": "ok", "current": user}

    def delete_account_completely(self, username_to_delete: str) -> Dict[str, Any]:
        u_clean = (username_to_delete or "").strip()
        if not u_clean:
            return {"status": "error", "message": "Пустое имя"}
        u_key = clean_username_for_key(u_clean)

        self.accounts = [
            a
            for a in self.accounts
            if a.get("username", "").lower() != u_clean.lower()
        ]
        if self.accounts and not any(a.get("active") for a in self.accounts):
            self.accounts[0]["active"] = True
        save_json(ACCOUNTS_FILE, self.accounts)

        matched_cube = next(
            (
                u
                for u in self.cube_accounts
                if u.get("username", "").lower() == u_clean.lower()
            ),
            None,
        )
        is_cube = False
        if matched_cube:
            is_cube = True
            uid = matched_cube.get("id")
            if uid and FIREBASE_API_KEY:
                try:
                    user_doc = (
                        f"https://firestore.googleapis.com/v1/projects/"
                        f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
                        f"users/{uid}?key={FIREBASE_API_KEY}"
                    )
                    SESSION.delete(
                        user_doc, headers=self._firestore_headers(), timeout=5
                    )
                    uname_doc = (
                        f"https://firestore.googleapis.com/v1/projects/"
                        f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
                        f"usernames/{u_key}?key={FIREBASE_API_KEY}"
                    )
                    SESSION.delete(
                        uname_doc, headers=self._firestore_headers(), timeout=5
                    )
                except Exception as e:
                    log.warning("Ошибка удаления из Firestore: %s", e)
            self.cube_accounts = [
                u
                for u in self.cube_accounts
                if u.get("username", "").lower() != u_clean.lower()
            ]
            if self.cube_accounts and not any(
                u.get("active") for u in self.cube_accounts
            ):
                self.cube_accounts[0]["active"] = True
            save_json(CUBE_ACCOUNTS_FILE, self.cube_accounts)

        if u_key in self.users_registry:
            del self.users_registry[u_key]
            save_json(USERS_REGISTRY_FILE, self.users_registry)

        self._eval_js("refreshMainProfileUI()")
        self._eval_js("refreshData()")
        self._show_toast(f"Аккаунт {u_clean} безвозвратно удалён!", "info")
        return {"status": "ok", "is_cube": is_cube}
    # ================= УПРАВЛЕНИЕ СБОРКАМИ И ФАЙЛАМИ =================
    def delete_instance(self, instance_id: str) -> Dict[str, Any]:
        if instance_id == "CubeVisuals":
            return {
                "status": "error",
                "message": (
                    "Удалить данную сборку невозможно. Пожалуйста, снимите "
                    "галочку 'Показывать сборку CubeVisuals' в настройках."
                ),
            }
        if not is_safe_id(instance_id):
            return {"status": "error", "message": "Некорректный id сборки"}

        instances = self.config.get("instances", [])
        self.config["instances"] = [
            i for i in instances if i["id"] != instance_id
        ]
        if self.config["active_instance_id"] == instance_id:
            if self.config["instances"]:
                self.config["active_instance_id"] = self.config["instances"][0]["id"]
            else:
                self.config["active_instance_id"] = "CubeVisuals"

        inst_dir = safe_join(INSTANCES_DIR, instance_id)
        if inst_dir and os.path.exists(inst_dir):
            try:
                shutil.rmtree(inst_dir)
            except Exception as e:
                log.warning("delete_instance rmtree: %s", e)

        self.config = ensure_cube_visuals_instance(self.config)
        save_json(CONFIG_FILE, self.config)
        return {"status": "ok", "instances": self.config["instances"]}

    def open_instance_folder(self, instance_id: str) -> Dict[str, str]:
        if not is_safe_id(instance_id):
            return {"status": "error", "message": "Некорректный id"}
        inst_dir = safe_join(INSTANCES_DIR, instance_id)
        if not inst_dir:
            return {"status": "error"}
        os.makedirs(inst_dir, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(inst_dir)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", inst_dir])
            else:
                subprocess.Popen(["xdg-open", inst_dir])
        except Exception as e:
            log.warning("open_instance_folder: %s", e)
        return {"status": "ok"}

    def get_instance_files(
        self, instance_id: str, resource_type: str
    ) -> List[Dict[str, Any]]:
        if not is_safe_id(instance_id):
            return []
        if resource_type not in ("mods", "shaderpacks", "resourcepacks", "datapacks"):
            return []
        inst_dir = safe_join(INSTANCES_DIR, instance_id, resource_type)
        if not inst_dir or not os.path.exists(inst_dir):
            return []
        files: List[Dict[str, Any]] = []
        try:
            for f in os.listdir(inst_dir):
                full_path = os.path.join(inst_dir, f)
                if os.path.isfile(full_path):
                    files.append(extract_jar_metadata(full_path))
        except Exception as e:
            log.warning("get_instance_files: %s", e)
        return files

    def toggle_instance_file(
        self, instance_id: str, resource_type: str, filename: str
    ) -> Dict[str, str]:
        if not is_safe_id(instance_id):
            return {"status": "error"}
        if resource_type not in ("mods", "shaderpacks", "resourcepacks", "datapacks"):
            return {"status": "error"}
        inst_dir = safe_join(INSTANCES_DIR, instance_id, resource_type)
        if not inst_dir:
            return {"status": "error"}
        safe_name = os.path.basename(filename)
        old_path = os.path.join(inst_dir, safe_name)
        if safe_name.endswith(".disabled"):
            new_path = os.path.join(inst_dir, safe_name[:-9])
        else:
            new_path = os.path.join(inst_dir, safe_name + ".disabled")
        if os.path.exists(old_path):
            try:
                os.rename(old_path, new_path)
                with _JAR_CACHE_LOCK:
                    _JAR_CACHE.clear()
            except Exception as e:
                log.warning("toggle_instance_file: %s", e)
        return {"status": "ok"}

    def delete_instance_file(
        self, instance_id: str, resource_type: str, filename: str
    ) -> Dict[str, str]:
        if not is_safe_id(instance_id):
            return {"status": "error"}
        if resource_type not in ("mods", "shaderpacks", "resourcepacks", "datapacks"):
            return {"status": "error"}
        inst_dir = safe_join(INSTANCES_DIR, instance_id, resource_type)
        if not inst_dir:
            return {"status": "error"}
        safe_name = os.path.basename(filename)
        file_path = os.path.join(inst_dir, safe_name)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                with _JAR_CACHE_LOCK:
                    _JAR_CACHE.clear()
            except Exception as e:
                log.warning("delete_instance_file: %s", e)
        return {"status": "ok"}

    def select_instance_custom_icon(self) -> Dict[str, Any]:
        if not _APP_WINDOW:
            return {"status": "cancel"}
        file_types = (
            "Изображения (*.png;*.jpg;*.jpeg;*.webp)",
            "Все файлы (*.*)",
        )
        result = _APP_WINDOW.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types
        )
        if result and len(result) > 0:
            path = result[0]
            try:
                mime, _ = mimetypes.guess_type(path)
                if not mime:
                    mime = "image/png"
                with open(path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                return {"status": "ok", "icon_b64": f"data:{mime};base64,{encoded}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "cancel"}

    def select_banner_file(self) -> Dict[str, Any]:
        if not _APP_WINDOW:
            return {"status": "error"}
        file_types = (
            "Медиа файлы (*.mp4;*.png;*.jpg;*.jpeg;*.webp;*.gif)",
            "Все файлы (*.*)",
        )
        result = _APP_WINDOW.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types
        )
        if result and len(result) > 0:
            path = result[0]
            self.config["banner_path"] = path
            save_json(CONFIG_FILE, self.config)
            return {"status": "ok", "path": path}
        return {"status": "cancel"}

    def clear_banner_file(self) -> Dict[str, str]:
        self.config["banner_path"] = ""
        save_json(CONFIG_FILE, self.config)
        return {"status": "ok"}

    def get_banner_data(self) -> Dict[str, Any]:
        path = self.config.get("banner_path", "")
        if not path or not os.path.exists(path):
            default_bg = r"C:\CubeLauncher\Launcher\images\1.21.11.png"
            if os.path.exists(default_bg):
                path = default_bg
            else:
                return {"status": "empty"}
        try:
            mime, _ = mimetypes.guess_type(path)
            if not mime:
                mime = "image/png"
            if mime.startswith("video"):
                return {"status": "video", "path": path.replace("\\", "/")}
            with open(path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            return {"status": "image", "data": f"data:{mime};base64,{encoded}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ================= MOJANG И ЗАГРУЗЧИКИ =================
    def get_all_mojang_versions(self) -> Dict[str, Any]:
        global _MOJANG_VERSIONS_CACHE
        if _MOJANG_VERSIONS_CACHE:
            return _MOJANG_VERSIONS_CACHE
        try:
            res = SESSION.get(MOJANG_MANIFEST_URL, timeout=8)
            if res.status_code == 200:
                data = res.json()
                raw = data.get("versions", [])
                releases, snapshots, old_beta, old_alpha = [], [], [], []
                for v in raw:
                    v_id = v.get("id")
                    v_type = v.get("type")
                    item = {"id": v_id, "type": v_type}
                    if v_type == "release":
                        releases.append(item)
                    elif v_type == "snapshot":
                        snapshots.append(item)
                    elif v_type == "old_beta":
                        old_beta.append(item)
                    else:
                        old_alpha.append(item)
                _MOJANG_VERSIONS_CACHE = {
                    "latest_release": data.get("latest", {}).get("release", "1.21.11"),
                    "latest_snapshot": data.get("latest", {}).get("snapshot", ""),
                    "releases": releases,
                    "snapshots": snapshots,
                    "old_beta": old_beta,
                    "old_alpha": old_alpha,
                    "all": [v.get("id") for v in raw],
                }
                return _MOJANG_VERSIONS_CACHE
        except Exception as e:
            log.warning("Ошибка запроса манифеста Mojang: %s", e)
        fallback = [
            "1.21.1", "1.21", "1.20.6", "1.20.4", "1.20.1",
            "1.19.4", "1.18.2", "1.16.5", "1.12.2", "1.8.9", "1.7.10",
        ]
        return {
            "latest_release": "1.21.11",
            "latest_snapshot": "",
            "releases": [{"id": v, "type": "release"} for v in fallback],
            "snapshots": [],
            "old_beta": [],
            "old_alpha": [],
            "all": fallback,
        }

    def check_optifine_support(self, mc_version: str) -> Dict[str, Any]:
        now = time.time()
        cached = self._optifine_cache.get(mc_version)
        if cached and (now - cached[2]) < 3600:
            return {"supported": cached[0], "message": cached[1]}
        try:
            res = SESSION.get("https://optifine.net/downloads", timeout=5)
            supported = False
            if res.status_code == 200 and f"Minecraft {mc_version}" in res.text:
                supported = True
            msg = (
                f"Версия поддерживается (OptiFine доступен для {mc_version})"
                if supported
                else f"Версия не поддерживается (OptiFine отсутствует для {mc_version})"
            )
            self._optifine_cache[mc_version] = (supported, msg, now)
            return {"supported": supported, "message": msg}
        except Exception:
            return {
                "supported": False,
                "message": f"Не удалось проверить OptiFine для {mc_version}",
            }

    def get_loader_versions(
        self, loader_type: str, mc_version: str
    ) -> List[str]:
        try:
            if loader_type == "fabric":
                res = SESSION.get(
                    f"https://meta.fabricmc.net/v2/versions/loader/{mc_version}",
                    headers=HEADERS,
                    timeout=5,
                )
                if res.status_code == 200:
                    return [item["loader"]["version"] for item in res.json()]
            elif loader_type == "quilt":
                res = SESSION.get(
                    f"https://meta.quiltmc.org/v3/versions/loader/{mc_version}",
                    headers=HEADERS,
                    timeout=5,
                )
                if res.status_code == 200:
                    return [item["loader"]["version"] for item in res.json()]
            elif loader_type == "forge":
                fv = minecraft_launcher_lib.forge.find_forge_version(mc_version)
                if fv:
                    return [fv]
            elif loader_type == "neoforge":
                res = SESSION.get(
                    "https://maven.neoforged.net/api/maven/versions/releases/"
                    "net/neoforged/neoforge",
                    timeout=5,
                )
                if res.status_code == 200:
                    versions = res.json().get("versions", [])
                    matched = [
                        v
                        for v in versions
                        if v.startswith(mc_version.replace("1.", ""))
                    ]
                    if matched:
                        return list(reversed(matched))
        except Exception as e:
            log.debug("get_loader_versions: %s", e)
        return ["latest"]

    def save_instance(self, instance_data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(instance_data, dict):
            return {"status": "error", "message": "Некорректные данные"}
        instances = self.config.get("instances", [])
        inst_id = instance_data.get("id")
        if inst_id:
            if not is_safe_id(str(inst_id)):
                return {"status": "error", "message": "Некорректный id"}
            idx = next(
                (i for i, x in enumerate(instances) if x.get("id") == inst_id),
                -1,
            )
            if idx != -1:
                instances[idx].update(instance_data)
            else:
                instances.append(instance_data)
        else:
            inst_id = f"inst_{int(time.time())}"
            instance_data["id"] = inst_id
            instances.append(instance_data)

        inst_dir = safe_join(INSTANCES_DIR, str(inst_id))
        if inst_dir:
            os.makedirs(inst_dir, exist_ok=True)
            for folder in ("mods", "shaderpacks", "resourcepacks", "datapacks"):
                os.makedirs(os.path.join(inst_dir, folder), exist_ok=True)

        self.config["instances"] = instances
        save_json(CONFIG_FILE, self.config)
        return {"status": "ok", "instances": instances, "id": inst_id}

    def select_instance(self, instance_id: str) -> Dict[str, str]:
        if not is_safe_id(instance_id):
            return {"status": "error"}
        self.config["active_instance_id"] = instance_id
        save_json(CONFIG_FILE, self.config)
        return {"status": "ok"}

    # ================= КАТАЛОГИ MODRINTH И CURSEFORGE =================
    def install_modpack_as_instance(
        self, project_id: str, title: str, icon_url: str, platform: str = "modrinth"
    ) -> Dict[str, str]:
        def run() -> None:
            try:
                self._update_status(f"Получение данных модпака {title}...", 5)

                mc_ver = "1.21.11"
                loader = "fabric"
                loader_ver = "latest"

                try:
                    if platform == "curseforge":
                        res = SESSION.get(
                            f"https://api.curseforge.com/v1/mods/{project_id}",
                            headers=CF_HEADERS,
                            timeout=6,
                        )
                        if res.status_code == 200:
                            data = res.json().get("data", {})
                            latest_files = data.get("latestFiles", [])
                            if latest_files:
                                gv = latest_files[0].get("gameVersions", [])
                                for v in gv:
                                    if re.match(r"^1\.\d+(\.\d+)?$", str(v)):
                                        mc_ver = str(v)
                                        break
                                for l in ("fabric", "forge", "neoforge", "quilt"):
                                    if l in [str(x).lower() for x in gv]:
                                        loader = l
                                        break
                    else:
                        res = SESSION.get(
                            f"https://api.modrinth.com/v2/project/{project_id}",
                            headers=HEADERS,
                            timeout=6,
                        )
                        if res.status_code == 200:
                            p_data = res.json()
                            gv = p_data.get("game_versions", [])
                            releases = [v for v in gv if re.match(r"^1\.\d+(\.\d+)?$", v)]
                            if releases:
                                mc_ver = releases[-1]
                            loaders = p_data.get("loaders", [])
                            for l in ("fabric", "forge", "neoforge", "quilt"):
                                if l in loaders:
                                    loader = l
                                    break
                except Exception as e:
                    log.warning("install_modpack_as_instance: метаданные не получены: %s", e)

                safe_name = "".join(
                    [c for c in title if c.isalnum() or c in (" ", "_", "-")]
                ).rstrip() or "Modpack"
                inst_id = f"modpack_{int(time.time())}"
                new_inst = {
                    "id": inst_id,
                    "name": safe_name,
                    "mc_version": mc_ver,
                    "loader": loader,
                    "loader_version": loader_ver,
                    "icon": "📦",
                    "custom_icon": "",
                    "modpack_source": {
                        "platform": platform,
                        "project_id": project_id,
                        "icon_url": icon_url,
                    },
                }
                self.save_instance(new_inst)

                self._update_status(f"Модпак {safe_name} создан!", 100)
                self._show_toast(
                    f"Модпак {safe_name} добавлен в установки "
                    f"({mc_ver} / {loader})",
                    "success",
                )
                self._eval_js("refreshData()")
                time.sleep(1.2)
                self._eval_js("hideDownloadStatus()")
            except Exception as e:
                log.warning("install_modpack_as_instance: %s", e)
                self._show_toast(f"Ошибка создания модпака: {e}", "error")

        threading.Thread(target=run, daemon=True, name="install-modpack").start()
        return {"status": "ok"}

    def check_instance_updates(self, instance_id: str) -> Dict[str, Any]:
        if not is_safe_id(instance_id):
            return {"status": "error", "message": "Некорректный id"}
        inst = next(
            (i for i in self.config.get("instances", []) if i["id"] == instance_id),
            None,
        )
        if not inst:
            return {"status": "error", "message": "Сборка не найдена"}
        mods_dir = safe_join(INSTANCES_DIR, instance_id, "mods")
        if not mods_dir or not os.path.exists(mods_dir):
            return {"status": "ok", "updates_count": 0, "updates": {}}

        mc_ver = inst.get("mc_version", "1.21.11")
        loader = inst.get("loader", "vanilla").lower()
        loaders_list = [loader] if loader != "vanilla" else []
        if loader == "quilt":
            loaders_list.append("fabric")

        file_hashes: Dict[str, str] = {}
        try:
            for f in os.listdir(mods_dir):
                if f.endswith(".jar") or f.endswith(".jar.disabled"):
                    sha = calculate_sha1(os.path.join(mods_dir, f))
                    if sha:
                        file_hashes[sha] = f
        except Exception as e:
            log.warning("check_instance_updates listdir: %s", e)

        if not file_hashes:
            return {"status": "ok", "updates_count": 0, "updates": {}}

        try:
            body = {
                "hashes": list(file_hashes.keys()),
                "algorithm": "sha1",
                "loaders": loaders_list,
                "game_versions": [mc_ver],
            }
            res = SESSION.post(
                "https://api.modrinth.com/v2/version_files/update",
                json=body,
                headers=HEADERS,
                timeout=8,
            )
            if res.status_code == 200:
                data = res.json()
                updates: Dict[str, Dict[str, Any]] = {}
                for old_hash, ver_data in data.items():
                    local_fname = file_hashes.get(old_hash)
                    if not local_fname:
                        continue
                    files = ver_data.get("files", [])
                    primary = next(
                        (fl for fl in files if fl.get("primary")),
                        files[0] if files else None,
                    )
                    if not primary:
                        continue
                    new_hash = primary.get("hashes", {}).get("sha1")
                    if new_hash and new_hash != old_hash:
                        updates[local_fname] = {
                            "old_filename": local_fname,
                            "new_filename": primary.get("filename"),
                            "new_version": ver_data.get(
                                "version_number", "Новая версия"
                            ),
                            "url": primary.get("url"),
                        }
                return {
                    "status": "ok",
                    "updates_count": len(updates),
                    "updates": updates,
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}
        return {"status": "ok", "updates_count": 0, "updates": {}}

    def update_single_mod(
        self,
        instance_id: str,
        old_filename: str,
        download_url: str,
        new_filename: str,
    ) -> Dict[str, Any]:
        if not is_safe_id(instance_id):
            return {"status": "error", "message": "Некорректный id"}
        mods_dir = safe_join(INSTANCES_DIR, instance_id, "mods")
        if not mods_dir:
            return {"status": "error", "message": "Ошибка пути"}
        old_path = os.path.join(mods_dir, os.path.basename(old_filename))
        new_name = os.path.basename(new_filename)
        new_path = os.path.join(mods_dir, new_name)
        if old_filename.endswith(".disabled") and not new_filename.endswith(
            ".disabled"
        ):
            new_path += ".disabled"
            new_name += ".disabled"
        if download_file_safely(download_url, new_path):
            if os.path.exists(old_path) and old_path != new_path:
                try:
                    os.remove(old_path)
                except Exception as e:
                    log.debug("update_single_mod remove old: %s", e)
            with _JAR_CACHE_LOCK:
                _JAR_CACHE.clear()
            return {"status": "ok", "new_filename": new_name}
        return {"status": "error", "message": "Не удалось скачать файл"}

    def update_all_mods(self, instance_id: str) -> Dict[str, str]:
        if not is_safe_id(instance_id):
            return {"status": "error"}

        def run() -> None:
            try:
                self._update_status("Проверка обновлений модов...", 10)
                updates = self.check_instance_updates(instance_id).get("updates", {})
                total = len(updates)
                if total == 0:
                    self._show_toast("Все моды уже обновлены!", "info")
                    self._eval_js("hideDownloadStatus()")
                    return
                self._update_status(f"Обновление модов (0/{total})...", 20)
                updated_count = 0
                for idx, (old_f, info) in enumerate(updates.items()):
                    self._update_status(
                        f"Обновление ({idx + 1}/{total}): {info['new_filename']}...",
                        20 + int(((idx + 1) / total) * 75),
                    )
                    res = self.update_single_mod(
                        instance_id, old_f, info["url"], info["new_filename"]
                    )
                    if res.get("status") == "ok":
                        updated_count += 1
                self._update_status("Обновление модов завершено!", 100)
                self._show_toast(
                    f"Успешно обновлено модов: {updated_count} из {total}!",
                    "success",
                )
                self._eval_js("refreshModalInstanceFiles()")
                time.sleep(1.2)
                self._eval_js("hideDownloadStatus()")
            except Exception as e:
                self._show_toast(f"Ошибка обновления: {e}", "error")

        threading.Thread(target=run, daemon=True, name="update-all-mods").start()
        return {"status": "ok"}

    def fetch_resources(
        self,
        query: str = "",
        project_type: str = "mods",
        loader: str = "",
        mc_version: str = "",
        page: int = 1,
        limit: int = 10,
        platform: str = "modrinth",
    ) -> Dict[str, Any]:
        limit = max(1, min(int(limit), 50))
        if platform == "curseforge":
            return self._fetch_curseforge(
                query, project_type, loader, mc_version, page, limit
            )
        return self._fetch_modrinth(
            query, project_type, loader, mc_version, page, limit
        )

    def _fetch_modrinth(
        self,
        query: str,
        project_type: str,
        loader: str,
        mc_version: str,
        page: int,
        limit: int,
    ) -> Dict[str, Any]:
        type_map = {
            "mods": "mod",
            "shaders": "shader",
            "resourcepacks": "resourcepack",
            "datapacks": "datapack",
            "modpacks": "modpack",
            "mod": "mod",
        }
        p_type = type_map.get(project_type, "mod")
        facets_list: List[List[str]] = [[f"project_type:{p_type}"]]
        if loader and loader != "vanilla" and p_type in ("mod", "modpack"):
            facets_list.append([f"categories:{loader}"])
        if mc_version:
            facets_list.append([f"versions:{mc_version}"])
        offset = (max(1, page) - 1) * limit
        params = {
            "query": query or "",
            "facets": json.dumps(facets_list),
            "limit": limit,
            "offset": offset,
        }
        try:
            res = SESSION.get(
                "https://api.modrinth.com/v2/search",
                params=params,
                headers=HEADERS,
                timeout=6,
            )
            if res.status_code == 200:
                data = res.json()
                hits = data.get("hits", [])
                total_hits = data.get("total_hits", 0)
                items = []
                for h in hits:
                    items.append(
                        {
                            "id": h["project_id"],
                            "platform": "modrinth",
                            "title": h.get("title", "Без названия"),
                            "desc": h.get("description", "Описание отсутствует"),
                            "icon": h.get("icon_url", ""),
                            "downloads": h.get("downloads", 0),
                            "author": h.get("author", "Неизвестен"),
                            "project_type": h.get("project_type"),
                        }
                    )
                return {
                    "status": "ok",
                    "items": items,
                    "total": total_hits,
                    "page": page,
                    "total_pages": math.ceil(total_hits / limit) if total_hits > 0 else 1,
                }
        except Exception as e:
            log.debug("_fetch_modrinth: %s", e)
        return {"status": "ok", "items": [], "total": 0, "page": 1, "total_pages": 1}

    def _fetch_curseforge(
        self,
        query: str,
        project_type: str,
        loader: str,
        mc_version: str,
        page: int,
        limit: int,
    ) -> Dict[str, Any]:
        cf_class_map = {
            "mods": 6,
            "mod": 6,
            "shaders": 6552,
            "shader": 6552,
            "resourcepacks": 12,
            "resourcepack": 12,
            "datapacks": 6,
            "datapack": 6,
            "modpacks": 4471,
            "modpack": 4471,
        }
        loader_map = {"forge": 1, "fabric": 4, "quilt": 5, "neoforge": 6}
        offset = (max(1, page) - 1) * limit
        params: Dict[str, Any] = {
            "gameId": 432,
            "classId": cf_class_map.get(project_type, 6),
            "searchFilter": query or "",
            "index": offset,
            "pageSize": limit,
            "sortField": 2,
            "sortOrder": "desc",
        }
        if mc_version:
            params["gameVersion"] = mc_version
        if (
            loader
            and loader.lower() in loader_map
            and project_type in ("mods", "mod", "modpacks", "modpack")
        ):
            params["modLoaderType"] = loader_map[loader.lower()]
        try:
            res = SESSION.get(
                "https://api.curseforge.com/v1/mods/search",
                params=params,
                headers=CF_HEADERS,
                timeout=6,
            )
            if res.status_code == 200:
                data = res.json()
                raw_items = data.get("data", [])
                total_hits = data.get("pagination", {}).get("totalCount", 0)
                items = []
                for m in raw_items:
                    logo = m.get("logo", {}) or {}
                    items.append(
                        {
                            "id": str(m["id"]),
                            "platform": "curseforge",
                            "title": m.get("name", "Без названия"),
                            "desc": m.get("summary", "Описание отсутствует"),
                            "icon": logo.get("url") or logo.get("thumbnailUrl") or "",
                            "downloads": m.get("downloadCount", 0),
                            "author": (
                                m["authors"][0]["name"]
                                if m.get("authors")
                                else "Неизвестен"
                            ),
                            "project_type": project_type,
                        }
                    )
                return {
                    "status": "ok",
                    "items": items,
                    "total": total_hits,
                    "page": page,
                    "total_pages": math.ceil(total_hits / limit) if total_hits > 0 else 1,
                }
        except Exception as e:
            log.debug("_fetch_curseforge: %s", e)
        return {"status": "ok", "items": [], "total": 0, "page": 1, "total_pages": 1}

    def get_resource_details(
        self, project_id: str, platform: str = "modrinth"
    ) -> Dict[str, Any]:
        try:
            if platform == "curseforge":
                res_p = SESSION.get(
                    f"https://api.curseforge.com/v1/mods/{project_id}",
                    headers=CF_HEADERS,
                    timeout=6,
                )
                res_v = SESSION.get(
                    f"https://api.curseforge.com/v1/mods/{project_id}/files",
                    headers=CF_HEADERS,
                    timeout=6,
                )
                if res_p.status_code == 200 and res_v.status_code == 200:
                    p_data = res_p.json().get("data", {})
                    v_data = res_v.json().get("data", [])
                    versions = []
                    for f in v_data[:35]:
                        dl_url = f.get("downloadUrl") or (
                            f"https://www.curseforge.com/api/v1/mods/"
                            f"{project_id}/files/{f['id']}/download"
                        )
                        rel_type = "release"
                        if f.get("releaseType") == 2:
                            rel_type = "beta"
                        elif f.get("releaseType") == 3:
                            rel_type = "alpha"
                        versions.append(
                            {
                                "id": str(f["id"]),
                                "name": f.get("displayName", f.get("fileName")),
                                "version_number": f.get("fileName"),
                                "game_versions": f.get("gameVersions", []),
                                "loaders": [
                                    g
                                    for g in f.get("gameVersions", [])
                                    if g.lower() in ("forge", "fabric", "quilt", "neoforge")
                                ],
                                "files": [
                                    {"url": dl_url, "filename": f.get("fileName")}
                                ],
                                "version_type": rel_type,
                            }
                        )
                    versions.sort(
                        key=lambda x: {"release": 0, "beta": 1, "alpha": 2}.get(
                            x["version_type"], 3
                        )
                    )
                    return {
                        "status": "ok",
                        "project": {
                            "id": str(p_data["id"]),
                            "title": p_data.get("name"),
                            "icon": p_data.get("logo", {}).get("url") or "",
                            "project_type": "CurseForge Mod",
                            "gallery": [
                                s.get("url")
                                for s in p_data.get("screenshots", [])
                                if s.get("url")
                            ],
                        },
                        "versions": versions,
                    }
            else:
                res_p = SESSION.get(
                    f"https://api.modrinth.com/v2/project/{project_id}",
                    headers=HEADERS,
                    timeout=6,
                )
                res_v = SESSION.get(
                    f"https://api.modrinth.com/v2/project/{project_id}/version",
                    headers=HEADERS,
                    timeout=6,
                )
                if res_p.status_code == 200 and res_v.status_code == 200:
                    p_data = res_p.json()
                    v_data = res_v.json()
                    versions = []
                    for ver in v_data[:35]:
                        versions.append(
                            {
                                "id": ver["id"],
                                "name": ver["name"],
                                "version_number": ver["version_number"],
                                "game_versions": ver.get("game_versions", []),
                                "loaders": ver.get("loaders", []),
                                "files": ver.get("files", []),
                                "version_type": ver.get("version_type", "release"),
                            }
                        )
                    versions.sort(
                        key=lambda x: {"release": 0, "beta": 1, "alpha": 2}.get(
                            x["version_type"], 3
                        )
                    )
                    return {
                        "status": "ok",
                        "project": {
                            "id": p_data["id"],
                            "title": p_data["title"],
                            "icon": p_data.get("icon_url", ""),
                            "project_type": p_data.get("project_type", "mod"),
                            "gallery": [
                                g["url"]
                                for g in p_data.get("gallery", [])
                                if "url" in g
                            ],
                        },
                        "versions": versions,
                    }
        except Exception as e:
            log.warning("get_resource_details: %s", e)
        return {"status": "error"}

    def auto_install_resource(
        self,
        project_id: str,
        platform: str = "modrinth",
        instance_id: Optional[str] = None,
        resource_type: str = "mods",
    ) -> Dict[str, Any]:
        active_inst_id = instance_id or self.config.get("active_instance_id")
        inst = next(
            (
                i
                for i in self.config.get("instances", [])
                if i["id"] == active_inst_id
            ),
            None,
        )
        if not inst and self.config.get("instances"):
            inst = self.config["instances"][0]
        if not inst:
            return {"status": "error", "message": "Сборка не найдена!"}

        mc_ver = inst.get("mc_version", "1.21.11")
        loader = inst.get("loader", "vanilla").lower()
        is_mod = resource_type == "mods"
        major_minor = (
            ".".join(mc_ver.split(".")[:2]) if "." in mc_ver else mc_ver
        )
        try:
            if platform == "curseforge":
                res_v = SESSION.get(
                    f"https://api.curseforge.com/v1/mods/{project_id}/files",
                    headers=CF_HEADERS,
                    timeout=6,
                )
                if res_v.status_code == 200:
                    files = res_v.json().get("data", [])
                    matched_file = None
                    for f in files:
                        g_vers = [str(g).lower() for g in f.get("gameVersions", [])]
                        mc_ok = (
                            (not mc_ver)
                            or (mc_ver.lower() in g_vers)
                            or any(major_minor in g for g in g_vers)
                            or (not is_mod)
                        )
                        ld_ok = (
                            (
                                (loader == "vanilla")
                                or (loader in g_vers)
                                or (loader == "quilt" and "fabric" in g_vers)
                            )
                            if is_mod
                            else True
                        )
                        if mc_ok and ld_ok:
                            dl_url = f.get("downloadUrl") or (
                                f"https://www.curseforge.com/api/v1/mods/"
                                f"{project_id}/files/{f['id']}/download"
                            )
                            matched_file = {
                                "url": dl_url,
                                "filename": f.get("fileName"),
                            }
                            break
                    if not matched_file and not is_mod and files:
                        f = files[0]
                        matched_file = {
                            "url": f.get("downloadUrl")
                            or (
                                f"https://www.curseforge.com/api/v1/mods/"
                                f"{project_id}/files/{f['id']}/download"
                            ),
                            "filename": f.get("fileName"),
                        }
                    if matched_file:
                        self.install_resource(
                            inst["id"],
                            matched_file["url"],
                            matched_file["filename"],
                            resource_type,
                        )
                        return {"status": "ok", "filename": matched_file["filename"]}
            else:
                res_v = SESSION.get(
                    f"https://api.modrinth.com/v2/project/{project_id}/version",
                    headers=HEADERS,
                    timeout=6,
                )
                if res_v.status_code == 200:
                    versions = res_v.json()
                    matched_file = None
                    for ver in versions:
                        v_mc = ver.get("game_versions", [])
                        v_ld = [l.lower() for l in ver.get("loaders", [])]
                        mc_ok = (
                            (not mc_ver)
                            or (mc_ver in v_mc)
                            or any(major_minor in g for g in v_mc)
                            or (not is_mod)
                        )
                        ld_ok = (
                            (
                                (loader == "vanilla")
                                or (not v_ld)
                                or (loader in v_ld)
                                or (loader == "quilt" and "fabric" in v_ld)
                            )
                            if is_mod
                            else True
                        )
                        if mc_ok and ld_ok:
                            f = next(
                                (
                                    fl
                                    for fl in ver.get("files", [])
                                    if fl.get("primary")
                                ),
                                None,
                            ) or (
                                ver.get("files", [])[0]
                                if ver.get("files")
                                else None
                            )
                            if f:
                                matched_file = f
                                break
                    if not matched_file and not is_mod and versions:
                        ver = versions[0]
                        matched_file = next(
                            (
                                fl
                                for fl in ver.get("files", [])
                                if fl.get("primary")
                            ),
                            None,
                        ) or (
                            ver.get("files", [])[0] if ver.get("files") else None
                        )
                    if matched_file:
                        self.install_resource(
                            inst["id"],
                            matched_file["url"],
                            matched_file["filename"],
                            resource_type,
                        )
                        return {"status": "ok", "filename": matched_file["filename"]}
            return {
                "status": "not_found",
                "message": f"Не удалось подобрать файл под {mc_ver}.",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def install_resource(
        self,
        instance_id: str,
        download_url: str,
        file_name: str,
        resource_type: str,
    ) -> Dict[str, str]:
        if not is_safe_id(instance_id):
            return {"status": "error", "message": "Некорректный id"}
        if resource_type not in ("mods", "shaderpacks", "resourcepacks", "datapacks"):
            return {"status": "error", "message": "Некорректный тип"}

        def run() -> None:
            try:
                target_dir = safe_join(INSTANCES_DIR, instance_id, resource_type)
                if not target_dir:
                    self._show_toast("Ошибка пути установки", "error")
                    return
                os.makedirs(target_dir, exist_ok=True)
                safe_name = os.path.basename(file_name)
                file_path = os.path.join(target_dir, safe_name)
                self._update_status(f"Загрузка {safe_name}...", 10)
                with SESSION.get(
                    download_url,
                    headers=HEADERS,
                    stream=True,
                    timeout=25,
                ) as res:
                    if res.status_code != 200:
                        self._show_toast(
                            f"Ошибка загрузки: HTTP {res.status_code}", "error"
                        )
                        self._eval_js("hideDownloadStatus()")
                        return
                    total_size = int(res.headers.get("content-length", 0))
                    downloaded = 0
                    tmp_path = file_path + ".part"
                    with open(tmp_path, "wb") as f:
                        for chunk in res.iter_content(chunk_size=16384):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    prog = int((downloaded / total_size) * 100)
                                    self._update_status(
                                        f"Загрузка {safe_name}... {prog}%",
                                        prog,
                                    )
                    os.replace(tmp_path, file_path)

                with _JAR_CACHE_LOCK:
                    _JAR_CACHE.clear()
                self._update_status(f"Установлено: {safe_name}", 100)
                self._show_toast(f"Успешно установлен: {safe_name}", "success")
                self._eval_js("refreshModalInstanceFiles()")
                time.sleep(1.2)
                self._eval_js("hideDownloadStatus()")
            except Exception as e:
                self._update_status(f"Ошибка: {e}", 0)
                self._show_toast(f"Ошибка установки: {e}", "error")

        threading.Thread(target=run, daemon=True, name="install-resource").start()
        return {"status": "ok"}
    # ================= MICROSOFT AUTH И ОФФЛАЙН АККАУНТЫ =================
    def check_microsoft_status(self) -> Dict[str, Any]:
        try:
            res = SESSION.get("https://login.live.com", timeout=3.0)
            return {"status": "ok", "connected": (res.status_code < 500)}
        except Exception:
            return {"status": "ok", "connected": False}

    def get_accounts(self) -> List[Dict[str, Any]]:
        return self.accounts

    def add_account(self, username: str) -> Dict[str, Any]:
        u = (username or "").strip()
        if not u:
            return {"status": "error", "message": "Никнейм не может быть пустым"}
        if len(u) < MIN_USERNAME_LEN or len(u) > MAX_USERNAME_LEN:
            return {
                "status": "error",
                "message": f"Никнейм должен быть от {MIN_USERNAME_LEN} до {MAX_USERNAME_LEN} символов",
            }
        if not re.match(r"^[A-Za-z0-9_]+$", u):
            return {
                "status": "error",
                "message": "Никнейм может содержать только латиницу, цифры и _",
            }
        for acc in self.accounts:
            acc["active"] = False
        self.accounts.append(
            {
                "username": u,
                "type": "offline",
                "uuid": str(uuid.uuid3(uuid.NAMESPACE_DNS, u)),
                "active": True,
            }
        )
        save_json(ACCOUNTS_FILE, self.accounts)
        return {"status": "ok", "accounts": self.accounts}

    def start_microsoft_login(self) -> Dict[str, str]:
        try:
            login_url, state, code_verifier = (
                minecraft_launcher_lib.microsoft_account.get_secure_login_data(
                    MS_CLIENT_ID, MS_REDIRECT_URL
                )
            )
            login_win = webview.create_window(
                "Авторизация Microsoft",
                login_url,
                width=540,
                height=680,
                resizable=False,
            )
            handled = False

            def on_page_loaded(*args: Any) -> None:
                nonlocal handled
                if handled:
                    return
                try:
                    win_instance = (
                        args[0]
                        if args and isinstance(args[0], webview.Window)
                        else login_win
                    )
                    cur_url = win_instance.get_current_url()
                    if not cur_url:
                        return
                    parsed = urlparse(cur_url)
                    params = parse_qs(parsed.query)
                    if "code" in params:
                        handled = True
                        auth_code = params["code"][0]
                        try:
                            win_instance.destroy()
                        except Exception:
                            pass
                        self._show_toast(
                            "Авторизация успешна! Получение профиля...", "info"
                        )

                        def complete_auth() -> None:
                            try:
                                login_data = (
                                    minecraft_launcher_lib.microsoft_account.complete_login(
                                        MS_CLIENT_ID,
                                        None,
                                        MS_REDIRECT_URL,
                                        auth_code,
                                        code_verifier,
                                    )
                                )
                                ms_name = login_data.get("name")
                                ms_uuid = login_data.get("id")
                                ms_token = login_data.get("access_token")
                                for acc in self.accounts:
                                    acc["active"] = False
                                self.accounts = [
                                    a
                                    for a in self.accounts
                                    if a.get("username") != ms_name
                                ]
                                self.accounts.append(
                                    {
                                        "username": ms_name,
                                        "type": "microsoft",
                                        "uuid": ms_uuid,
                                        "token": ms_token,
                                        "active": True,
                                    }
                                )
                                save_json(ACCOUNTS_FILE, self.accounts)
                                self._eval_js("refreshData()")
                                self._show_toast(
                                    f"Добро пожаловать, {ms_name}!", "success"
                                )
                            except Exception as err:
                                self._show_toast(f"Ошибка входа: {err}", "error")

                        threading.Thread(
                            target=complete_auth,
                            daemon=True,
                            name="ms-auth-complete",
                        ).start()
                    elif "error" in params:
                        handled = True
                        err_desc = params.get(
                            "error_description", ["Вход был отменён"]
                        )[0]
                        try:
                            win_instance.destroy()
                        except Exception:
                            pass
                        self._show_toast(f"Ошибка: {err_desc}", "error")
                except Exception as e:
                    log.warning("Ошибка URL: %s", e)

            login_win.events.loaded += on_page_loaded  # type: ignore
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def select_account(self, username: str) -> Dict[str, Any]:
        for acc in self.accounts:
            acc["active"] = acc["username"] == username
        save_json(ACCOUNTS_FILE, self.accounts)
        return {"status": "ok", "accounts": self.accounts}

    def delete_account(self, username: str) -> Dict[str, Any]:
        self.accounts = [a for a in self.accounts if a["username"] != username]
        if self.accounts and not any(a.get("active") for a in self.accounts):
            self.accounts[0]["active"] = True
        save_json(ACCOUNTS_FILE, self.accounts)
        return {"status": "ok", "accounts": self.accounts}

    # ================= FIRESTORE OTP & CUBE AUTH =================
    def get_cube_user(self) -> Dict[str, Any]:
        return {"status": "ok", "user": self.cube_user}

    def generate_captcha(self) -> Dict[str, str]:
        a = random.randint(3, 19)
        b = random.randint(2, 15)
        self._current_captcha = str(a + b)
        self._current_captcha_created = time.time()
        return {"status": "ok", "question": f"Сколько будет {a} + {b} = ?"}

    def _check_captcha(self, answer: str) -> bool:
        if not self._current_captcha:
            return False
        if (time.time() - self._current_captcha_created) > 300:
            return False
        return (answer or "").strip() == self._current_captcha

    def _resize_avatar_b64(self, path: str) -> Optional[str]:
        try:
            mime, _ = mimetypes.guess_type(path)
            if not mime:
                mime = "image/png"
            if HAS_PIL and mime.startswith("image"):
                with Image.open(path) as img:
                    img = img.convert("RGBA") if img.mode != "RGBA" else img
                    img.thumbnail((256, 256), Image.LANCZOS)
                    buf = BytesIO()
                    img.save(buf, format="PNG", optimize=True)
                    data = buf.getvalue()
                    if len(data) > MAX_AVATAR_BYTES:
                        img.thumbnail((128, 128), Image.LANCZOS)
                        buf = BytesIO()
                        img.save(buf, format="PNG", optimize=True)
                        data = buf.getvalue()
                    encoded = base64.b64encode(data).decode("utf-8")
                    return f"data:image/png;base64,{encoded}"
            with open(path, "rb") as f:
                data = f.read()
            if len(data) > MAX_AVATAR_BYTES:
                return None
            encoded = base64.b64encode(data).decode("utf-8")
            return f"data:{mime};base64,{encoded}"
        except Exception as e:
            log.warning("_resize_avatar_b64: %s", e)
            return None

    def select_cube_avatar(self) -> Dict[str, Any]:
        if not _APP_WINDOW:
            return {"status": "error"}
        file_types = (
            "Изображения (*.png;*.jpg;*.jpeg;*.webp;*.gif)",
            "Все файлы (*.*)",
        )
        result = _APP_WINDOW.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types
        )
        if result and len(result) > 0:
            path = result[0]
            avatar_data = self._resize_avatar_b64(path)
            if not avatar_data:
                return {
                    "status": "error",
                    "message": (
                        f"Аватарка слишком большая "
                        f"(лимит {human_bytes(MAX_AVATAR_BYTES)}). "
                        "Пожалуйста, выберите изображение меньшего размера."
                    ),
                }
            user = self.cube_user
            if user:
                user["avatar"] = avatar_data
                save_json(CUBE_ACCOUNTS_FILE, self.cube_accounts)
                uid = user.get("id")
                if uid:
                    url = (
                        f"https://firestore.googleapis.com/v1/projects/"
                        f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
                        f"users/{uid}"
                        f"?updateMask.fieldPaths=avatar&key={FIREBASE_API_KEY}"
                    )
                    try:
                        SESSION.patch(
                            url,
                            json={"fields": {"avatar": {"stringValue": avatar_data}}},
                            headers=self._firestore_headers(),
                            timeout=5,
                        )
                    except Exception as e:
                        log.debug("avatar patch: %s", e)
                self._eval_js("refreshMainProfileUI()")
                self._show_toast("Аватарка успешно обновлена!", "success")
                return {"status": "ok", "avatar": avatar_data}
        return {"status": "cancel"}

    def send_registration_code(
        self, username: str, email: str, password: str, captcha_answer: str
    ) -> Dict[str, Any]:
        u = (username or "").strip()
        em = (email or "").strip().lower()
        pw = (password or "").strip()
        clean_u = clean_username_for_key(u)
        if not self._check_captcha(captcha_answer):
            return {
                "status": "error",
                "message": "Неверный ответ капчи! Попробуйте снова.",
            }
        if len(u) < MIN_USERNAME_LEN or len(u) > MAX_USERNAME_LEN or not clean_u:
            return {
                "status": "error",
                "message": (
                    f"Имя пользователя должно быть от {MIN_USERNAME_LEN} "
                    f"до {MAX_USERNAME_LEN} символов (латиница/цифры)"
                ),
            }
        if "@" not in em or "." not in em:
            return {"status": "error", "message": "Введите корректный Email адрес"}
        if len(pw) < 6:
            return {
                "status": "error",
                "message": "Пароль должен содержать не менее 6 символов",
            }
        try:
            uname_url = (
                f"https://firestore.googleapis.com/v1/projects/"
                f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
                f"usernames/{clean_u}?key={FIREBASE_API_KEY}"
            )
            u_check = SESSION.get(
                uname_url, headers=self._firestore_headers(), timeout=5
            )
            if u_check.status_code == 200:
                return {
                    "status": "error",
                    "message": f"Никнейм '{u}' уже занят другим игроком!",
                }
        except Exception:
            pass
        try:
            check_url = (
                f"https://identitytoolkit.googleapis.com/v1/accounts:createAuthUri"
                f"?key={FIREBASE_API_KEY}"
            )
            check_res = SESSION.post(
                check_url,
                json={"identifier": em, "continueUri": "http://localhost"},
                timeout=6,
            )
            if check_res.status_code == 200 and check_res.json().get("registered"):
                return {
                    "status": "error",
                    "message": (
                        "Этот Email уже зарегистрирован! Пожалуйста, "
                        "перейдите во вкладку «Вход»."
                    ),
                }
        except Exception:
            pass
        clean_em = clean_email_for_key(em)
        now = int(time.time())
        firestore_url = (
            f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}"
            f"/databases/(default)/documents/email_verifications/{clean_em}"
            f"?key={FIREBASE_API_KEY}"
        )
        try:
            get_doc = SESSION.get(
                firestore_url, headers=self._firestore_headers(), timeout=5
            )
            if get_doc.status_code == 200:
                fields = get_doc.json().get("fields", {})
                resend_avail = int(
                    fields.get("resend_available_at", {}).get("integerValue", 0)
                )
                if now < resend_avail:
                    return {
                        "status": "error",
                        "message": (
                            f"Подождите {resend_avail - now} сек "
                            "перед повторной отправкой!"
                        ),
                    }
        except Exception:
            pass
        code = str(random.randint(100000, 999999))
        payload = {
            "fields": {
                "code": {"stringValue": code},
                "email": {"stringValue": em},
                "username": {"stringValue": u},
                "expires_at": {"integerValue": str(now + 300)},
                "resend_available_at": {"integerValue": str(now + 60)},
                "attempts": {"integerValue": "0"},
            }
        }
        try:
            SESSION.patch(
                firestore_url,
                json=payload,
                headers=self._firestore_headers(),
                timeout=6,
            )
        except Exception as e:
            log.warning("Ошибка записи Firestore: %s", e)
        ok, msg = send_html_mail(em, code, is_login=False)
        if not ok:
            return {"status": "error", "message": msg}
        self._show_toast("Код подтверждения отправлен на почту!", "success")
        return {"status": "ok", "cooldown": 60, "email": em}

    def verify_and_register(
        self, username: str, email: str, password: str, entered_code: str
    ) -> Dict[str, Any]:
        u = (username or "").strip()
        em = (email or "").strip().lower()
        pw = (password or "").strip()
        code_input = (entered_code or "").strip()
        clean_u = clean_username_for_key(u)
        if len(code_input) != 6:
            return {"status": "error", "message": "Введите 6-значный код!"}
        clean_em = clean_email_for_key(em)
        firestore_url = (
            f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}"
            f"/databases/(default)/documents/email_verifications/{clean_em}"
            f"?key={FIREBASE_API_KEY}"
        )
        try:
            get_doc = SESSION.get(
                firestore_url, headers=self._firestore_headers(), timeout=6
            )
            if get_doc.status_code != 200:
                return {
                    "status": "error",
                    "message": "Код не найден или устарел. Запросите заново.",
                }
            fields = get_doc.json().get("fields", {})
            real_code = fields.get("code", {}).get("stringValue", "")
            expires_at = int(fields.get("expires_at", {}).get("integerValue", 0))
            attempts = int(fields.get("attempts", {}).get("integerValue", 0))
            if int(time.time()) > expires_at:
                return {
                    "status": "error",
                    "message": "Срок действия кода истек! Запросите новый.",
                }
            if attempts >= 5:
                return {
                    "status": "error",
                    "message": "Превышено число попыток! Запросите новый код.",
                }
            if code_input != real_code:
                SESSION.patch(
                    firestore_url,
                    json={
                        "fields": {
                            "attempts": {"integerValue": str(attempts + 1)}
                        }
                    },
                    headers=self._firestore_headers(),
                    timeout=3,
                )
                return {
                    "status": "error",
                    "message": f"Неверный код! Осталось попыток: {4 - attempts}",
                }
        except Exception as e:
            return {"status": "error", "message": f"Ошибка проверки кода: {e}"}
        try:
            sign_up_url = (
                f"https://identitytoolkit.googleapis.com/v1/accounts:signUp"
                f"?key={FIREBASE_API_KEY}"
            )
            res = SESSION.post(
                sign_up_url,
                json={"email": em, "password": pw, "returnSecureToken": True},
                timeout=6,
            )
            res_data = res.json()
            if res.status_code == 200:
                id_token = res_data.get("idToken")
                local_id = res_data.get("localId")
                update_url = (
                    f"https://identitytoolkit.googleapis.com/v1/accounts:update"
                    f"?key={FIREBASE_API_KEY}"
                )
                avatar_url = f"https://minotar.net/helm/{u}/100.png"
                SESSION.post(
                    update_url,
                    json={
                        "idToken": id_token,
                        "displayName": u,
                        "photoUrl": avatar_url,
                        "returnSecureToken": True,
                    },
                    timeout=5,
                )
                user_doc_url = (
                    f"https://firestore.googleapis.com/v1/projects/"
                    f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
                    f"users/{local_id}?key={FIREBASE_API_KEY}"
                )
                user_payload = {
                    "fields": {
                        "uid": {"stringValue": local_id},
                        "username": {"stringValue": u},
                        "username_lower": {"stringValue": clean_u},
                        "email": {"stringValue": em},
                        "avatar": {"stringValue": avatar_url},
                        "bio": {"stringValue": "Игрок Cube Launcher"},
                        "last_seen": {"integerValue": str(int(time.time()))},
                        "is_playing": {"booleanValue": False},
                        "activity_title": {"stringValue": "В лаунчере"},
                        "activity_version": {"stringValue": ""},
                        "activity_loader": {"stringValue": ""},
                        "stat_launcher_seconds": {"integerValue": "0"},
                        "stat_minecraft_seconds": {"integerValue": "0"},
                        "stat_launches": {"integerValue": "0"},
                    }
                }
                SESSION.patch(
                    user_doc_url,
                    json=user_payload,
                    headers={"Authorization": f"Bearer {id_token}"},
                    timeout=5,
                )
                uname_doc_url = (
                    f"https://firestore.googleapis.com/v1/projects/"
                    f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
                    f"usernames/{clean_u}?key={FIREBASE_API_KEY}"
                )
                SESSION.patch(
                    uname_doc_url,
                    json={
                        "fields": {
                            "uid": {"stringValue": local_id},
                            "username": {"stringValue": u},
                        }
                    },
                    headers={"Authorization": f"Bearer {id_token}"},
                    timeout=5,
                )
                for acc in self.cube_accounts:
                    acc["active"] = False
                new_cube_acc = {
                    "username": u,
                    "email": em,
                    "id": local_id,
                    "token": id_token,
                    "avatar": avatar_url,
                    "bio": "Игрок Cube Launcher",
                    "created_at": time.strftime("%Y-%m-%d"),
                    "active": True,
                }
                self.cube_accounts.append(new_cube_acc)
                save_json(CUBE_ACCOUNTS_FILE, self.cube_accounts)
                self.users_registry[clean_u] = em
                save_json(USERS_REGISTRY_FILE, self.users_registry)
                try:
                    SESSION.delete(
                        firestore_url,
                        headers=self._firestore_headers(),
                        timeout=4,
                    )
                except Exception:
                    pass
                self._eval_js("refreshMainProfileUI()")
                self._show_toast(f"Аккаунт {u} успешно создан!", "success")
                return {"status": "ok", "user": new_cube_acc}
            else:
                raw_err = res_data.get("error", {}).get("message", "")
                if "EMAIL_EXISTS" in raw_err:
                    return {
                        "status": "error",
                        "message": (
                            "Этот Email уже зарегистрирован! "
                            "Переключитесь на вкладку «Вход»."
                        ),
                    }
                return {"status": "error", "message": f"Ошибка регистрации: {raw_err}"}
        except Exception as e:
            return {"status": "error", "message": f"Ошибка сети: {e}"}

    def send_login_code(
        self, login_or_email: str, password: str, captcha_answer: str
    ) -> Dict[str, Any]:
        lom = (login_or_email or "").strip()
        pw = (password or "").strip()
        if not self._check_captcha(captcha_answer):
            return {"status": "error", "message": "Неверный ответ капчи!"}
        if not lom or not pw:
            return {"status": "error", "message": "Заполните все поля"}
        target_email = (
            lom.lower()
            if "@" in lom
            else self.users_registry.get(
                clean_username_for_key(lom), f"{lom.lower()}@cube.local"
            )
        )
        try:
            sign_in_url = (
                f"https://identitytoolkit.googleapis.com/v1/accounts:"
                f"signInWithPassword?key={FIREBASE_API_KEY}"
            )
            res = SESSION.post(
                sign_in_url,
                json={
                    "email": target_email,
                    "password": pw,
                    "returnSecureToken": True,
                },
                timeout=6,
            )
            if res.status_code != 200:
                err_msg = res.json().get("error", {}).get("message", "")
                if (
                    "EMAIL_NOT_FOUND" in err_msg
                    or "INVALID_LOGIN_CREDENTIALS" in err_msg
                ):
                    return {
                        "status": "error",
                        "message": (
                            "Такого аккаунта не существует. "
                            "Зарегистрируйте новый аккаунт."
                        ),
                    }
                if "INVALID_PASSWORD" in err_msg:
                    return {"status": "error", "message": "Неверный пароль!"}
                return {
                    "status": "error",
                    "message": "Неверный логин/почта или пароль!",
                }
        except Exception as e:
            return {"status": "error", "message": f"Ошибка сети: {e}"}
        clean_em = clean_email_for_key(target_email)
        now = int(time.time())
        firestore_url = (
            f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}"
            f"/databases/(default)/documents/email_verifications/{clean_em}"
            f"?key={FIREBASE_API_KEY}"
        )
        try:
            get_doc = SESSION.get(
                firestore_url, headers=self._firestore_headers(), timeout=5
            )
            if get_doc.status_code == 200:
                fields = get_doc.json().get("fields", {})
                resend_avail = int(
                    fields.get("resend_available_at", {}).get("integerValue", 0)
                )
                if now < resend_avail:
                    return {
                        "status": "error",
                        "message": (
                            f"Подождите {resend_avail - now} сек "
                            "перед повторной отправкой!"
                        ),
                    }
        except Exception:
            pass
        code = str(random.randint(100000, 999999))
        payload = {
            "fields": {
                "code": {"stringValue": code},
                "email": {"stringValue": target_email},
                "expires_at": {"integerValue": str(now + 300)},
                "resend_available_at": {"integerValue": str(now + 60)},
                "attempts": {"integerValue": "0"},
            }
        }
        try:
            SESSION.patch(
                firestore_url,
                json=payload,
                headers=self._firestore_headers(),
                timeout=6,
            )
        except Exception as e:
            log.warning("Ошибка записи Firestore: %s", e)
        ok, msg = send_html_mail(target_email, code, is_login=True)
        if not ok:
            return {"status": "error", "message": msg}
        self._show_toast("Код для входа отправлен на почту!", "success")
        return {"status": "ok", "cooldown": 60, "email": target_email}

    def verify_and_login(
        self, login_or_email: str, password: str, entered_code: str
    ) -> Dict[str, Any]:
        lom = (login_or_email or "").strip()
        pw = (password or "").strip()
        code_input = (entered_code or "").strip()
        if len(code_input) != 6:
            return {"status": "error", "message": "Введите 6-значный код!"}
        target_email = (
            lom.lower()
            if "@" in lom
            else self.users_registry.get(
                clean_username_for_key(lom), f"{lom.lower()}@cube.local"
            )
        )
        clean_em = clean_email_for_key(target_email)
        firestore_url = (
            f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}"
            f"/databases/(default)/documents/email_verifications/{clean_em}"
            f"?key={FIREBASE_API_KEY}"
        )
        try:
            get_doc = SESSION.get(
                firestore_url, headers=self._firestore_headers(), timeout=6
            )
            if get_doc.status_code != 200:
                return {
                    "status": "error",
                    "message": "Код не найден или устарел. Запросите заново.",
                }
            fields = get_doc.json().get("fields", {})
            real_code = fields.get("code", {}).get("stringValue", "")
            expires_at = int(fields.get("expires_at", {}).get("integerValue", 0))
            attempts = int(fields.get("attempts", {}).get("integerValue", 0))
            if int(time.time()) > expires_at:
                return {
                    "status": "error",
                    "message": "Срок действия кода истек! Запросите новый.",
                }
            if attempts >= 5:
                return {
                    "status": "error",
                    "message": "Превышено число попыток! Запросите новый код.",
                }
            if code_input != real_code:
                SESSION.patch(
                    firestore_url,
                    json={
                        "fields": {
                            "attempts": {"integerValue": str(attempts + 1)}
                        }
                    },
                    headers=self._firestore_headers(),
                    timeout=3,
                )
                return {
                    "status": "error",
                    "message": f"Неверный код! Осталось попыток: {4 - attempts}",
                }
        except Exception as e:
            return {"status": "error", "message": f"Ошибка проверки кода: {e}"}
        try:
            sign_in_url = (
                f"https://identitytoolkit.googleapis.com/v1/accounts:"
                f"signInWithPassword?key={FIREBASE_API_KEY}"
            )
            res = SESSION.post(
                sign_in_url,
                json={
                    "email": target_email,
                    "password": pw,
                    "returnSecureToken": True,
                },
                timeout=6,
            )
            res_data = res.json()
            if res.status_code == 200:
                id_token = res_data.get("idToken")
                local_id = res_data.get("localId")
                u_name = res_data.get("displayName") or lom.split("@")[0]
                avatar_url = res_data.get("profilePicture") or (
                    f"https://minotar.net/helm/{u_name}/100.png"
                )
                user_doc_url = (
                    f"https://firestore.googleapis.com/v1/projects/"
                    f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
                    f"users/{local_id}?key={FIREBASE_API_KEY}"
                )
                u_bio = "Игрок Cube Launcher"
                try:
                    f_res = SESSION.get(
                        user_doc_url,
                        headers={"Authorization": f"Bearer {id_token}"},
                        timeout=4,
                    )
                    if f_res.status_code == 200:
                        f_fields = f_res.json().get("fields", {})
                        u_name = f_fields.get("username", {}).get(
                            "stringValue", u_name
                        )
                        avatar_url = f_fields.get("avatar", {}).get(
                            "stringValue", avatar_url
                        )
                        u_bio = f_fields.get("bio", {}).get("stringValue", u_bio)
                except Exception:
                    pass
                for acc in self.cube_accounts:
                    acc["active"] = False
                existing_acc = next(
                    (
                        a
                        for a in self.cube_accounts
                        if a.get("id") == local_id
                        or a.get("email") == target_email
                    ),
                    None,
                )
                logged_user = {
                    "username": u_name,
                    "email": res_data.get("email"),
                    "id": local_id,
                    "token": id_token,
                    "avatar": avatar_url,
                    "bio": u_bio,
                    "created_at": time.strftime("%Y-%m-%d"),
                    "active": True,
                }
                if existing_acc:
                    existing_acc.update(logged_user)
                else:
                    self.cube_accounts.append(logged_user)
                save_json(CUBE_ACCOUNTS_FILE, self.cube_accounts)
                self.users_registry[clean_username_for_key(u_name)] = res_data.get(
                    "email"
                )
                save_json(USERS_REGISTRY_FILE, self.users_registry)
                try:
                    SESSION.delete(
                        firestore_url,
                        headers=self._firestore_headers(),
                        timeout=4,
                    )
                except Exception:
                    pass
                self._eval_js("refreshMainProfileUI()")
                self._show_toast(f"Добро пожаловать, {u_name}!", "success")
                try:
                    self._sync_stats_to_cloud()
                except Exception:
                    pass
                return {"status": "ok", "user": logged_user}
            else:
                err_msg = res_data.get("error", {}).get("message", "")
                if (
                    "EMAIL_NOT_FOUND" in err_msg
                    or "INVALID_LOGIN_CREDENTIALS" in err_msg
                ):
                    return {
                        "status": "error",
                        "message": (
                            "Такого аккаунта не существует. "
                            "Зарегистрируйте новый."
                        ),
                    }
                return {"status": "error", "message": f"Ошибка входа: {err_msg}"}
        except Exception as e:
            return {"status": "error", "message": f"Ошибка сети: {e}"}

    def _auto_add_offline_game_account(self, username: str) -> None:
        for acc in self.accounts:
            acc["active"] = False
        existing = next(
            (a for a in self.accounts if a.get("username") == username), None
        )
        if existing:
            existing["active"] = True
        else:
            self.accounts.append(
                {
                    "username": username,
                    "type": "offline",
                    "uuid": str(uuid.uuid3(uuid.NAMESPACE_DNS, username)),
                    "active": True,
                }
            )
        save_json(ACCOUNTS_FILE, self.accounts)

    def logout_cube_account(self) -> Dict[str, str]:
        user = self.cube_user
        if user:
            active_id = user.get("id")
            for acc in self.cube_accounts:
                if acc.get("id") == active_id:
                    acc["active"] = False
            remaining = [
                a for a in self.cube_accounts if a.get("id") != active_id
            ]
            if remaining:
                remaining[0]["active"] = True
            save_json(CUBE_ACCOUNTS_FILE, self.cube_accounts)
        self._eval_js("refreshMainProfileUI()")
        self._show_toast("Вы вышли из аккаунта", "info")
        return {"status": "ok"}

    def update_cube_bio(self, bio: str) -> Dict[str, Any]:
        user = self.cube_user
        if not user:
            return {"status": "error"}
        bio_clean = (bio or "").strip()[:MAX_BIO_LEN]
        user["bio"] = bio_clean
        save_json(CUBE_ACCOUNTS_FILE, self.cube_accounts)
        try:
            uid = user.get("id")
            if uid:
                url = (
                    f"https://firestore.googleapis.com/v1/projects/"
                    f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
                    f"users/{uid}"
                    f"?updateMask.fieldPaths=bio&key={FIREBASE_API_KEY}"
                )
                SESSION.patch(
                    url,
                    json={"fields": {"bio": {"stringValue": bio_clean}}},
                    headers=self._firestore_headers(),
                    timeout=4,
                )
        except Exception as e:
            log.debug("update_cube_bio patch: %s", e)
        self._eval_js("refreshMainProfileUI()")
        self._show_toast("Описание обновлено!", "success")
        return {"status": "ok"}

    # ================= ДРУЗЬЯ И ЧАТЫ =================
    def search_and_send_friend_request(self, target_username: str) -> Dict[str, Any]:
        user = self.cube_user
        if not user:
            return {
                "status": "error",
                "message": "Войдите в профиль Cube Launcher, чтобы добавлять друзей!",
            }
        clean_u = clean_username_for_key(target_username or "")
        my_clean_u = clean_username_for_key(user["username"])
        if not clean_u:
            return {"status": "error", "message": "Введите корректный ник игрока!"}
        if clean_u == my_clean_u:
            return {
                "status": "error",
                "message": "Нельзя отправить заявку в друзья самому себе!",
            }
        try:
            uname_url = (
                f"https://firestore.googleapis.com/v1/projects/"
                f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
                f"usernames/{clean_u}?key={FIREBASE_API_KEY}"
            )
            res = SESSION.get(
                uname_url, headers=self._firestore_headers(), timeout=5
            )
            if res.status_code != 200:
                return {
                    "status": "error",
                    "message": f"Игрок с ником '{target_username}' не найден!",
                }
            target_data = res.json().get("fields", {})
            target_uid = target_data.get("uid", {}).get("stringValue")
            target_real_name = target_data.get("username", {}).get(
                "stringValue", target_username
            )
            if not target_uid:
                return {"status": "error", "message": "Не удалось получить ID игрока"}
            req_id = f"{min(user['id'], target_uid)}_{max(user['id'], target_uid)}"
            req_url = (
                f"https://firestore.googleapis.com/v1/projects/"
                f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
                f"friend_requests/{req_id}?key={FIREBASE_API_KEY}"
            )
            payload = {
                "fields": {
                    "from_uid": {"stringValue": user["id"]},
                    "from_username": {"stringValue": user["username"]},
                    "to_uid": {"stringValue": target_uid},
                    "to_username": {"stringValue": target_real_name},
                    "status": {"stringValue": "pending"},
                    "timestamp": {"integerValue": str(int(time.time()))},
                }
            }
            SESSION.patch(
                req_url,
                json=payload,
                headers=self._firestore_headers(),
                timeout=5,
            )
            self._show_toast(
                f"Запрос в друзья отправлен игроку {target_real_name}!", "success"
            )
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_friends_data(self) -> Dict[str, Any]:
        user = self.cube_user
        if not user:
            return {"status": "ok", "friends": [], "incoming": [], "outgoing": []}
        my_uid = user["id"]
        try:
            url = (
                f"https://firestore.googleapis.com/v1/projects/"
                f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
                f"friend_requests?key={FIREBASE_API_KEY}"
            )
            res = SESSION.get(url, headers=self._firestore_headers(), timeout=6)
            docs = (
                res.json().get("documents", []) if res.status_code == 200 else []
            )
            friends: List[Dict[str, Any]] = []
            incoming: List[Dict[str, Any]] = []
            outgoing: List[Dict[str, Any]] = []
            for d in docs:
                f = d.get("fields", {})
                req_id = d["name"].split("/")[-1]
                from_u = f.get("from_uid", {}).get("stringValue")
                to_u = f.get("to_uid", {}).get("stringValue")
                from_name = f.get("from_username", {}).get("stringValue")
                to_name = f.get("to_username", {}).get("stringValue")
                status = f.get("status", {}).get("stringValue")
                if from_u == my_uid or to_u == my_uid:
                    other_uid = to_u if from_u == my_uid else from_u
                    other_name = to_name if from_u == my_uid else from_name
                    if status == "accepted":
                        friends.append(
                            self._fetch_public_profile(other_uid, other_name)
                        )
                    elif status == "pending":
                        if to_u == my_uid:
                            incoming.append(
                                {
                                    "req_id": req_id,
                                    "uid": from_u,
                                    "username": from_name,
                                    "avatar": (
                                        f"https://minotar.net/helm/{from_name}/100.png"
                                    ),
                                }
                            )
                        else:
                            outgoing.append(
                                {
                                    "req_id": req_id,
                                    "uid": to_u,
                                    "username": to_name,
                                    "avatar": (
                                        f"https://minotar.net/helm/{to_name}/100.png"
                                    ),
                                }
                            )
            return {
                "status": "ok",
                "friends": friends,
                "incoming": incoming,
                "outgoing": outgoing,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _fetch_public_profile(
        self, uid: str, fallback_name: str = "Player"
    ) -> Dict[str, Any]:
        try:
            url = (
                f"https://firestore.googleapis.com/v1/projects/"
                f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
                f"users/{uid}?key={FIREBASE_API_KEY}"
            )
            res = SESSION.get(
                url, headers=self._firestore_headers(), timeout=4
            )
            if res.status_code == 200:
                fields = res.json().get("fields", {})
                last_seen = int(
                    fields.get("last_seen", {}).get("integerValue", 0)
                )
                is_online = (int(time.time()) - last_seen) < 90
                ls_sec = int(
                    fields.get("stat_launcher_seconds", {}).get("integerValue", 0)
                )
                ms_sec = int(
                    fields.get("stat_minecraft_seconds", {}).get("integerValue", 0)
                )
                lc_cnt = int(
                    fields.get("stat_launches", {}).get("integerValue", 0)
                )
                return {
                    "uid": uid,
                    "username": fields.get("username", {}).get(
                        "stringValue", fallback_name
                    ),
                    "avatar": fields.get("avatar", {}).get(
                        "stringValue",
                        f"https://minotar.net/helm/{fallback_name}/100.png",
                    ),
                    "bio": fields.get("bio", {}).get(
                        "stringValue", "Игрок Cube Launcher"
                    ),
                    "is_online": is_online,
                    "is_playing": fields.get("is_playing", {}).get(
                        "booleanValue", False
                    ),
                    "activity_title": fields.get("activity_title", {}).get(
                        "stringValue", ""
                    ),
                    "activity_version": fields.get("activity_version", {}).get(
                        "stringValue", ""
                    ),
                    "activity_loader": fields.get("activity_loader", {}).get(
                        "stringValue", ""
                    ),
                    "stat_launcher_seconds": ls_sec,
                    "stat_minecraft_seconds": ms_sec,
                    "stat_launcher_hours": round(ls_sec / 3600.0, 1),
                    "stat_minecraft_hours": round(ms_sec / 3600.0, 1),
                    "stat_launches": lc_cnt,
                }
        except Exception as e:
            log.debug("_fetch_public_profile: %s", e)
        return {
            "uid": uid,
            "username": fallback_name,
            "avatar": f"https://minotar.net/helm/{fallback_name}/100.png",
            "bio": "Игрок Cube Launcher",
            "is_online": False,
            "is_playing": False,
            "activity_title": "",
            "activity_version": "",
            "activity_loader": "",
            "stat_launcher_seconds": 0,
            "stat_minecraft_seconds": 0,
            "stat_launcher_hours": 0.0,
            "stat_minecraft_hours": 0.0,
            "stat_launches": 0,
        }

    def get_public_profile_with_stats(self, uid: str) -> Dict[str, Any]:
        return {"status": "ok", "profile": self._fetch_public_profile(uid)}

    def respond_to_friend_request(self, req_id: str, action: str) -> Dict[str, Any]:
        if not req_id or not re.match(r"^[A-Za-z0-9_]+$", req_id):
            return {"status": "error", "message": "Некорректный id заявки"}
        req_url = (
            f"https://firestore.googleapis.com/v1/projects/"
            f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
            f"friend_requests/{req_id}?key={FIREBASE_API_KEY}"
        )
        try:
            if action == "accept":
                SESSION.patch(
                    f"{req_url}&updateMask.fieldPaths=status",
                    json={"fields": {"status": {"stringValue": "accepted"}}},
                    headers=self._firestore_headers(),
                    timeout=5,
                )
                self._show_toast("Заявка принята! Друг добавлен.", "success")
            else:
                SESSION.delete(
                    req_url, headers=self._firestore_headers(), timeout=5
                )
                self._show_toast("Заявка отклонена/отменена", "info")
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_messages(self, friend_uid: str) -> Dict[str, Any]:
        user = self.cube_user
        if not user:
            return {"status": "ok", "messages": []}
        chat_id = f"{min(user['id'], friend_uid)}_{max(user['id'], friend_uid)}"
        url = (
            f"https://firestore.googleapis.com/v1/projects/"
            f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/"
            f"chats/{chat_id}/messages?key={FIREBASE_API_KEY}"
        )
        try:
            res = SESSION.get(
                url, headers=self._firestore_headers(), timeout=6
            )
            if res.status_code == 200:
                docs = res.json().get("documents", [])
                messages = []
                for d in docs:
                    f = d.get("fields", {})
                    messages.append(
                        {
                            "sender_uid": f.get("sender_uid", {}).get(
                                "stringValue"
                            ),
                            "text": f.get("text", {}).get("stringValue", ""),
                            "image": f.get("image", {}).get("stringValue", ""),
                            "voice": f.get("voice", {}).get("stringValue", ""),
                            "voice_duration": int(
                                f.get("voice_duration", {}).get(
                                    "integerValue", 0
                                )
                            ),
                            "timestamp": int(
                                f.get("timestamp", {}).get("integerValue", 0)
                            ),
                        }
                    )
                messages.sort(key=lambda x: x["timestamp"])
                return {"status": "ok", "messages": messages}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        return {"status": "ok", "messages": []}

    def send_message(
        self, friend_uid: str, text: str = "", image_b64: str = ""
    ) -> Dict[str, Any]:
        user = self.cube_user
        if not user:
            return {"status": "error"}
        if image_b64:
            approx_bytes = len(image_b64) * 3 // 4
            if approx_bytes > MAX_CHAT_IMAGE_BYTES:
                return {
                    "status": "error",
                    "message": (
                        f"Картинка слишком большая ({human_bytes(approx_bytes)}). "
                        f"Лимит — {human_bytes(MAX_CHAT_IMAGE_BYTES)}."
                    ),
                }
        chat_id = f"{min(user['id'], friend_uid)}_{max(user['id'], friend_uid)}"
        msg_id = f"msg_{int(time.time() * 1000)}"
        url = (
            f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}"
            f"/databases/(default)/documents/chats/{chat_id}/messages/{msg_id}"
            f"?key={FIREBASE_API_KEY}"
        )
        payload = {
            "fields": {
                "sender_uid": {"stringValue": user["id"]},
                "text": {"stringValue": text or ""},
                "image": {"stringValue": image_b64 or ""},
                "voice": {"stringValue": ""},
                "voice_duration": {"integerValue": "0"},
                "timestamp": {"integerValue": str(int(time.time() * 1000))},
            }
        }
        try:
            res = SESSION.patch(
                url,
                json=payload,
                headers=self._firestore_headers(),
                timeout=6,
            )
            if res.status_code not in (200, 201):
                return {
                    "status": "error",
                    "message": f"Firestore: {res.status_code}",
                }
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def select_chat_image(self) -> Dict[str, Any]:
        if not _APP_WINDOW:
            return {"status": "cancel"}
        file_types = (
            "Изображения (*.png;*.jpg;*.jpeg;*.webp;*.gif)",
            "Все файлы (*.*)",
        )
        result = _APP_WINDOW.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types
        )
        if result and len(result) > 0:
            path = result[0]
            try:
                with open(path, "rb") as f:
                    data = f.read()
                if len(data) > MAX_CHAT_IMAGE_BYTES:
                    return {
                        "status": "error",
                        "message": (
                            f"Файл слишком большой ({human_bytes(len(data))}). "
                            f"Лимит — {human_bytes(MAX_CHAT_IMAGE_BYTES)}."
                        ),
                    }
                mime, _ = mimetypes.guess_type(path)
                if not mime:
                    mime = "image/png"
                encoded = base64.b64encode(data).decode("utf-8")
                return {"status": "ok", "image": f"data:{mime};base64,{encoded}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "cancel"}

    def _update_cloud_activity(
        self, is_playing: bool, inst: Optional[Dict[str, Any]] = None
    ) -> None:
        user = self.cube_user
        if not user or not user.get("id"):
            return
        uid = user["id"]
        show = self.config.get("show_game_activity", True)
        title = (
            (inst.get("name", "Minecraft") if inst else "Minecraft")
            if (is_playing and show)
            else ("В игре" if is_playing else "В лаунчере")
        )
        mc_ver = (
            inst.get("mc_version", "") if (is_playing and show and inst) else ""
        )
        loader = (
            inst.get("loader", "vanilla").capitalize()
            if (is_playing and show and inst)
            else ""
        )
        url = (
            f"https://firestore.googleapis.com/v1/projects/"
            f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/users/{uid}"
            f"?updateMask.fieldPaths=is_playing"
            f"&updateMask.fieldPaths=activity_title"
            f"&updateMask.fieldPaths=activity_version"
            f"&updateMask.fieldPaths=activity_loader"
            f"&updateMask.fieldPaths=last_seen&key={FIREBASE_API_KEY}"
        )
        payload = {
            "fields": {
                "is_playing": {"booleanValue": is_playing},
                "activity_title": {"stringValue": title},
                "activity_version": {"stringValue": mc_ver},
                "activity_loader": {"stringValue": loader},
                "last_seen": {"integerValue": str(int(time.time()))},
            }
        }
        try:
            SESSION.patch(
                url,
                json=payload,
                headers=self._firestore_headers(),
                timeout=4,
            )
        except Exception as e:
            log.debug("_update_cloud_activity: %s", e)

    # ================= ДИАГНОСТИКА И КРАШ-ОТЧЕТЫ =================
    def _generate_crash_code(self, err_text: str, inst_id: str = "") -> str:
        h = hashlib.md5(
            f"{err_text}_{inst_id}_{time.time()}".encode(
                "utf-8", errors="ignore"
            )
        ).hexdigest().upper()
        return f"CL-{h[0:4]}-{h[4:8]}"

    def _collect_crash_info(
        self,
        inst: Optional[Dict[str, Any]],
        error_text: str,
        exit_code: Optional[int] = None,
    ) -> Dict[str, Any]:
        inst_dir = (
            safe_join(INSTANCES_DIR, inst["id"]) if inst else GAME_DIR
        ) or GAME_DIR
        logs_dir = os.path.join(inst_dir, "logs")
        crash_dir = os.path.join(inst_dir, "crash-reports")
        try:
            os.makedirs(logs_dir, exist_ok=True)
            os.makedirs(crash_dir, exist_ok=True)
        except Exception:
            pass

        last_log_path = ""
        latest_log_mtime = 0
        try:
            for fn in os.listdir(logs_dir):
                fp = os.path.join(logs_dir, fn)
                if os.path.isfile(fp):
                    mt = os.path.getmtime(fp)
                    if mt > latest_log_mtime:
                        latest_log_mtime = mt
                        last_log_path = fp
        except Exception:
            pass

        last_crash_path = ""
        latest_crash_mtime = 0
        try:
            for fn in os.listdir(crash_dir):
                fp = os.path.join(crash_dir, fn)
                if os.path.isfile(fp):
                    mt = os.path.getmtime(fp)
                    if mt > latest_crash_mtime:
                        latest_crash_mtime = mt
                        last_crash_path = fp
        except Exception:
            pass

        short_desc = (error_text or "").strip()[:MAX_DESCRIPTION_CHARS]
        if last_crash_path and os.path.exists(last_crash_path):
            try:
                with open(
                    last_crash_path, "r", encoding="utf-8", errors="ignore"
                ) as f:
                    head = f.read(2500)
                m = re.search(r"Description:\s*(.+)", head)
                if m:
                    short_desc = m.group(1).strip()[:MAX_DESCRIPTION_CHARS]
                else:
                    for line in head.splitlines():
                        line = line.strip()
                        if (
                            line
                            and not line.startswith("----")
                            and "Minecraft Crash Report" not in line
                        ):
                            short_desc = line[:MAX_DESCRIPTION_CHARS]
                            break
            except Exception:
                pass

        crash_code = self._generate_crash_code(
            short_desc + (error_text or ""),
            inst["id"] if inst else "",
        )
        return {
            "status": "ok",
            "code": crash_code,
            "description": short_desc or "Неизвестная ошибка",
            "exit_code": exit_code,
            "instance_id": inst["id"] if inst else None,
            "instance_name": inst.get("name", "Minecraft") if inst else "Minecraft",
            "mc_version": inst.get("mc_version", "") if inst else "",
            "loader": inst.get("loader", "vanilla") if inst else "vanilla",
            "logs_dir": logs_dir,
            "crash_dir": crash_dir,
            "last_log_path": last_log_path,
            "last_crash_path": last_crash_path,
        }

    def open_crash_folder(self, path: str) -> Dict[str, Any]:
        try:
            if not path or not os.path.exists(path):
                return {"status": "error", "message": "Папка не найдена"}
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def open_last_log_file(self, instance_id: str) -> Dict[str, Any]:
        try:
            inst_dir = (
                safe_join(INSTANCES_DIR, instance_id) if instance_id else GAME_DIR
            ) or GAME_DIR
            logs_dir = os.path.join(inst_dir, "logs")
            if not os.path.exists(logs_dir):
                return {"status": "error", "message": "Папка логов не найдена"}
            latest_path, latest_mtime = "", 0
            for fn in os.listdir(logs_dir):
                fp = os.path.join(logs_dir, fn)
                if os.path.isfile(fp):
                    mt = os.path.getmtime(fp)
                    if mt > latest_mtime:
                        latest_mtime = mt
                        latest_path = fp
            if not latest_path:
                return {"status": "error", "message": "Логи не найдены"}
            if os.name == "nt":
                os.startfile(latest_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", latest_path])
            else:
                subprocess.Popen(["xdg-open", latest_path])
            return {"status": "ok", "path": latest_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def open_last_crash_file(self, instance_id: str) -> Dict[str, Any]:
        try:
            inst_dir = (
                safe_join(INSTANCES_DIR, instance_id) if instance_id else GAME_DIR
            ) or GAME_DIR
            crash_dir = os.path.join(inst_dir, "crash-reports")
            if not os.path.exists(crash_dir):
                return {
                    "status": "error",
                    "message": "Папка crash-reports не найдена",
                }
            latest_path, latest_mtime = "", 0
            for fn in os.listdir(crash_dir):
                fp = os.path.join(crash_dir, fn)
                if os.path.isfile(fp):
                    mt = os.path.getmtime(fp)
                    if mt > latest_mtime:
                        latest_mtime = mt
                        latest_path = fp
            if not latest_path:
                return {"status": "error", "message": "Краш-репорты не найдены"}
            if os.name == "nt":
                os.startfile(latest_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", latest_path])
            else:
                subprocess.Popen(["xdg-open", latest_path])
            return {"status": "ok", "path": latest_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        # ================= СЕРВЕРЫ И МОНИТОРИНГ =================
    def get_servers_catalog(self) -> Dict[str, Any]:
        return {"status": "ok", "servers": SERVER_CATALOG}

    def _fetch_single_server_status(
        self, server_address: str
    ) -> Optional[Dict[str, Any]]:
        try:
            url = f"{MC_STATUS_API}{server_address}"
            res = SESSION.get(url, headers=HEADERS, timeout=6)
            if res.status_code != 200:
                return None
            data = res.json()
            online = bool(data.get("online", False))
            players_online, players_max = 0, 0
            motd_clean, icon_b64 = "", ""
            if online:
                players = data.get("players", {}) or {}
                players_online = int(players.get("online", 0) or 0)
                players_max = int(players.get("max", 0) or 0)
                motd = data.get("motd", {}) or {}
                motd_lines = motd.get("clean", []) or motd.get("raw", []) or []
                if isinstance(motd_lines, list):
                    motd_clean = "\n".join(
                        [strip_mc_formatting(str(l)) for l in motd_lines]
                    )
                else:
                    motd_clean = strip_mc_formatting(str(motd_lines))
                icon_field = data.get("icon", "")
                if icon_field and isinstance(icon_field, str):
                    if icon_field.startswith("data:image"):
                        icon_b64 = icon_field
                    elif icon_field.startswith("base64,"):
                        icon_b64 = f"data:image/png;base64,{icon_field[7:]}"
            return {
                "online": online,
                "players_online": players_online,
                "players_max": players_max,
                "motd": motd_clean,
                "icon": icon_b64,
                "last_check": int(time.time()),
            }
        except Exception as e:
            log.debug("[_fetch_single_server_status] %s: %s", server_address, e)
            return None

    def get_cube_vanilla_status(self) -> Dict[str, Any]:
        """
        Прямой Server List Ping (SLP) через сокет без сторонних API.
        Работает стабильно и независимо от внешних сервисов.
        """
        address = CUBE_VANILLA_ADDRESS
        if ":" in address:
            host, port_str = address.split(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 25565
        else:
            host = address
            port = 25565

        def _write_varint(value: int) -> bytes:
            out = b""
            while True:
                b = value & 0x7F
                value >>= 7
                if value:
                    out += bytes([b | 0x80])
                else:
                    out += bytes([b])
                    break
            return out

        def _read_varint(sock: socket.socket) -> int:
            num_read = 0
            result = 0
            while True:
                byte = sock.recv(1)
                if not byte:
                    raise IOError("Connection closed")
                b = byte[0]
                result |= (b & 0x7F) << (7 * num_read)
                num_read += 1
                if num_read > 5:
                    raise IOError("VarInt too big")
                if not (b & 0x80):
                    break
            return result

        def _read_exact(sock: socket.socket, n: int) -> bytes:
            data = b""
            while len(data) < n:
                chunk = sock.recv(n - len(data))
                if not chunk:
                    raise IOError("Connection closed")
                data += chunk
            return data

        try:
            with socket.create_connection((host, port), timeout=4.5) as sock:
                host_bytes = host.encode("utf-8")
                # Пакет Handshake
                handshake = (
                    b"\x00"
                    + _write_varint(47)
                    + _write_varint(len(host_bytes))
                    + host_bytes
                    + struct.pack(">H", port)
                    + _write_varint(1)
                )
                sock.sendall(_write_varint(len(handshake)) + handshake)
                # Пакет запроса статуса
                sock.sendall(b"\x01\x00")
                # Ответ
                _read_varint(sock)
                _read_varint(sock)
                json_length = _read_varint(sock)
                json_bytes = _read_exact(sock, json_length)
                data = json.loads(json_bytes.decode("utf-8", errors="ignore"))

            players = data.get("players", {}) or {}
            return {
                "status": "ok",
                "online": True,
                "players_online": int(players.get("online", 0) or 0),
                "players_max": int(players.get("max", 0) or 0),
                "address": CUBE_VANILLA_ADDRESS,
                "recommended_version": CUBE_VANILLA_RECOMMENDED_VERSION,
            }

        except socket.timeout:
            return {
                "status": "ok",
                "online": False,
                "players_online": 0,
                "players_max": 0,
                "error_text": "Таймаут подключения к Cube Vanilla",
                "address": CUBE_VANILLA_ADDRESS,
                "recommended_version": CUBE_VANILLA_RECOMMENDED_VERSION,
            }
        except ConnectionRefusedError:
            return {
                "status": "ok",
                "online": False,
                "players_online": 0,
                "players_max": 0,
                "error_text": "Сервер выключен",
                "address": CUBE_VANILLA_ADDRESS,
                "recommended_version": CUBE_VANILLA_RECOMMENDED_VERSION,
            }
        except Exception as e:
            return {
                "status": "error",
                "online": False,
                "players_online": 0,
                "players_max": 0,
                "error_text": str(e),
                "address": CUBE_VANILLA_ADDRESS,
                "recommended_version": CUBE_VANILLA_RECOMMENDED_VERSION,
            }

    def refresh_servers_status(self, force: bool = False) -> Dict[str, Any]:
        if self.servers_loading:
            return {"status": "busy"}

        def worker() -> None:
            self.servers_loading = True
            try:
                for srv in SERVER_CATALOG:
                    sid = srv["id"]
                    address = srv["address"]
                    if not force:
                        with self._servers_cache_lock:
                            cached = self.servers_cache.get(sid)
                        if cached and (
                            int(time.time()) - cached.get("last_check", 0)
                        ) < 60:
                            continue
                    status = self._fetch_single_server_status(address)
                    if status:
                        with self._servers_cache_lock:
                            self.servers_cache[sid] = status
            except Exception as e:
                log.debug("[refresh_servers_status] %s", e)
            finally:
                self.servers_loading = False

        threading.Thread(
            target=worker, daemon=True, name="refresh-servers"
        ).start()
        return {"status": "ok"}

    def get_servers_with_status(
        self, force_refresh: bool = False
    ) -> Dict[str, Any]:
        if not self.servers_cache and not self.servers_loading:
            self.refresh_servers_status(force=True)
        if force_refresh:
            self.refresh_servers_status(force=True)
        result = []
        with self._servers_cache_lock:
            for srv in SERVER_CATALOG:
                sid = srv["id"]
                cached = self.servers_cache.get(sid, {})
                item = dict(srv)
                item["online"] = bool(cached.get("online", False))
                item["players_online"] = int(cached.get("players_online", 0))
                item["players_max"] = int(cached.get("players_max", 0))
                item["motd"] = cached.get("motd", "")
                item["status_icon"] = cached.get("icon", "")
                item["last_check"] = int(cached.get("last_check", 0))
                item["is_loading"] = sid not in self.servers_cache
                result.append(item)
        return {"status": "ok", "servers": result, "loading": self.servers_loading}

    def get_server_details(self, server_id: str) -> Dict[str, Any]:
        srv = next((s for s in SERVER_CATALOG if s["id"] == server_id), None)
        if not srv:
            return {"status": "error", "message": "Сервер не найден"}
        with self._servers_cache_lock:
            cached = self.servers_cache.get(server_id, {})
        result = dict(srv)
        result["online"] = bool(cached.get("online", False))
        result["players_online"] = int(cached.get("players_online", 0))
        result["players_max"] = int(cached.get("players_max", 0))
        result["motd"] = cached.get("motd", "")
        result["status_icon"] = cached.get("icon", "")
        result["last_check"] = int(cached.get("last_check", 0))
        return {"status": "ok", "server": result}

    # ================= ДВИЖОК ЗАПУСКА MINECRAFT =================
    def kill_game(self) -> Dict[str, str]:
        with self._game_lock:
            proc = self._game_process
            self._game_process = None
            self.active_running_instance_id = None
        if proc:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
            except Exception as e:
                log.warning("Ошибка остановки: %s", e)
        self._eval_js("setPlayButtonState('default')")
        self._eval_js("hideDownloadStatus()")
        self._show_toast("Игра остановлена", "info")
        return {"status": "ok"}

    def _ensure_version_installed(
        self,
        mc_ver: str,
        loader: str,
        loader_ver: str,
        callback: Dict[str, Any],
        inst: Dict[str, Any],
    ) -> Optional[str]:
        installed_versions = [
            v["id"]
            for v in minecraft_launcher_lib.utils.get_installed_versions(GAME_DIR)
        ]
        target_version: Optional[str] = None

        def set_status(t: str) -> None:
            self._update_status(t)

        if loader == "fabric":
            fab_match = [
                v for v in installed_versions if "fabric" in v.lower() and mc_ver in v
            ]
            if fab_match:
                return fab_match[0]
            if mc_ver not in installed_versions:
                set_status(f"Загрузка Minecraft {mc_ver}...")
                minecraft_launcher_lib.install.install_minecraft_version(
                    mc_ver, GAME_DIR, callback=callback
                )
            set_status(f"Установка Fabric ({mc_ver})...")
            try:
                minecraft_launcher_lib.fabric.install_fabric(
                    mc_ver,
                    GAME_DIR,
                    loader_version=(
                        None if loader_ver == "latest" else loader_ver
                    ),
                    callback=callback,
                )
            except TypeError:
                minecraft_launcher_lib.fabric.install_fabric(
                    mc_ver, GAME_DIR, callback=callback
                )
            installed = minecraft_launcher_lib.utils.get_installed_versions(GAME_DIR)
            fab = [
                v["id"]
                for v in installed
                if "fabric" in v["id"].lower() and mc_ver in v["id"]
            ]
            target_version = fab[0] if fab else mc_ver

        elif loader == "quilt":
            quilt_match = [
                v for v in installed_versions if "quilt" in v.lower() and mc_ver in v
            ]
            if quilt_match:
                return quilt_match[0]
            if mc_ver not in installed_versions:
                set_status(f"Загрузка Minecraft {mc_ver}...")
                minecraft_launcher_lib.install.install_minecraft_version(
                    mc_ver, GAME_DIR, callback=callback
                )
            set_status(f"Установка Quilt ({mc_ver})...")
            try:
                minecraft_launcher_lib.quilt.install_quilt(
                    mc_ver,
                    GAME_DIR,
                    loader_version=(
                        None if loader_ver == "latest" else loader_ver
                    ),
                    callback=callback,
                )
            except TypeError:
                minecraft_launcher_lib.quilt.install_quilt(
                    mc_ver, GAME_DIR, callback=callback
                )
            installed = minecraft_launcher_lib.utils.get_installed_versions(GAME_DIR)
            qlt = [
                v["id"]
                for v in installed
                if "quilt" in v["id"].lower() and mc_ver in v["id"]
            ]
            target_version = qlt[0] if qlt else mc_ver

        elif loader == "forge":
            fv = minecraft_launcher_lib.forge.find_forge_version(mc_ver)
            if fv and fv in installed_versions:
                return fv
            if fv:
                if mc_ver not in installed_versions:
                    set_status(f"Загрузка Minecraft {mc_ver}...")
                    minecraft_launcher_lib.install.install_minecraft_version(
                        mc_ver, GAME_DIR, callback=callback
                    )
                set_status(f"Установка Forge ({mc_ver})...")
                minecraft_launcher_lib.forge.install_forge_version(
                    fv, GAME_DIR, callback=callback
                )
                target_version = fv
            else:
                target_version = mc_ver

        elif loader == "neoforge":
            try:
                nf_ver = minecraft_launcher_lib.neoforge.find_neoforge_version(
                    mc_ver
                )
                if nf_ver and nf_ver in installed_versions:
                    return nf_ver
                if nf_ver:
                    if mc_ver not in installed_versions:
                        set_status(f"Загрузка Minecraft {mc_ver}...")
                        minecraft_launcher_lib.install.install_minecraft_version(
                            mc_ver, GAME_DIR, callback=callback
                        )
                    set_status(f"Установка NeoForge ({mc_ver})...")
                    minecraft_launcher_lib.neoforge.install_neoforge_version(
                        nf_ver, GAME_DIR, callback=callback
                    )
                    target_version = nf_ver
                else:
                    target_version = mc_ver
            except Exception as e:
                log.warning("NeoForge не установлен: %s", e)
                target_version = mc_ver
        else:
            if mc_ver in installed_versions:
                target_version = mc_ver
            else:
                set_status(f"Загрузка Minecraft {mc_ver}...")
                minecraft_launcher_lib.install.install_minecraft_version(
                    mc_ver, GAME_DIR, callback=callback
                )
                target_version = mc_ver

        return target_version

    def launch_active_game(
        self, instance_id: Optional[str] = None
    ) -> Dict[str, Any]:
        with self._game_lock:
            if self._game_process and self._game_process.poll() is None:
                self.kill_game()
                return {"status": "killed"}

        active_inst_id = instance_id or self.config.get("active_instance_id")
        inst = next(
            (i for i in self.config.get("instances", []) if i["id"] == active_inst_id),
            None,
        )
        if not inst:
            inst = (
                self.config["instances"][0]
                if self.config.get("instances")
                else None
            )
        if not inst:
            self._show_toast("Сборка не найдена!", "error")
            return {"status": "error", "message": "Сборка не найдена!"}

        active_accs = [a for a in self.accounts if a.get("active")]
        if not active_accs:
            self._show_toast("Выберите аккаунт перед запуском!", "error")
            return {"status": "error", "message": "Выберите аккаунт перед запуском!"}

        active_acc = active_accs[0]
        ram_mb = self.config.get("ram_mb", 4096)
        inst_dir = safe_join(INSTANCES_DIR, inst["id"])
        if not inst_dir:
            self._show_toast("Некорректный путь сборки", "error")
            return {"status": "error", "message": "Некорректный путь сборки"}
        os.makedirs(inst_dir, exist_ok=True)
        self.active_running_instance_id = inst["id"]

        def run() -> None:
            proc: Optional[subprocess.Popen] = None
            mc_session_start = 0.0
            manual_kill = False
            crashed_error_text = ""
            crashed_exit_code: Optional[int] = None
            stderr_log_path = ""
            try:
                jvm_args = [f"-Xmx{ram_mb}M", f"-Xms{ram_mb}M"]
                custom_jvm = (self.config.get("jvm_args") or "").strip()
                if custom_jvm:
                    try:
                        jvm_args.extend(shlex.split(custom_jvm))
                    except Exception:
                        jvm_args.extend(custom_jvm.split())

                options = {
                    "username": active_acc["username"],
                    "uuid": active_acc.get(
                        "uuid", "00000000-0000-0000-0000-000000000000"
                    ),
                    "token": active_acc.get("token", "0"),
                    "gameDirectory": inst_dir,
                    "jvmArguments": jvm_args,
                }
                java_path = shutil.which("java") or shutil.which("javaw")
                if java_path:
                    options["executablePath"] = java_path

                progress_data = {"max": 100, "curr": 0}

                def set_status(t: str) -> None:
                    self._update_status(t)

                def set_max(m: int) -> None:
                    progress_data["max"] = m if m > 0 else 100

                def set_progress(p: int) -> None:
                    now = time.time()
                    progress_data["curr"] = p
                    if now - self._last_progress_time > 0.08:
                        self._last_progress_time = now
                        pct = int(
                            (progress_data["curr"] / progress_data["max"]) * 100
                        )
                        self._eval_js(
                            f"updateDownloadProgress({min(100, max(0, pct))})"
                        )

                callback = {
                    "setStatus": set_status,
                    "setProgress": set_progress,
                    "setMax": set_max,
                }
                self._eval_js(
                    f"setPlayButtonState('installing', '{inst['id']}')"
                )

                mc_ver = inst.get("mc_version", "1.21.11")
                loader = inst.get("loader", "vanilla").lower()
                loader_ver = inst.get("loader_version", "latest")

                target_version = self._ensure_version_installed(
                    mc_ver, loader, loader_ver, callback, inst
                )
                if not target_version:
                    raise RuntimeError("Не удалось определить версию для запуска")

                self._eval_js(
                    f"setPlayButtonState('launching', '{inst['id']}')"
                )
                set_status("Запуск игры...")

                cmd = minecraft_launcher_lib.command.get_minecraft_command(
                    version=target_version,
                    minecraft_directory=GAME_DIR,
                    options=options,
                )

                if self.config.get("enable_console"):
                    proc = subprocess.Popen(cmd)
                    stderr_log_path = ""
                else:
                    creation_flags = (
                        getattr(subprocess, "CREATE_NO_WINDOW", 0)
                        if os.name == "nt"
                        else 0
                    )
                    inst_dir_logs = os.path.join(inst_dir, "logs")
                    os.makedirs(inst_dir_logs, exist_ok=True)
                    stderr_log_path = os.path.join(
                        inst_dir_logs, "launcher_stderr.log"
                    )
                    stderr_file = open(
                        stderr_log_path,
                        "w",
                        encoding="utf-8",
                        errors="ignore",
                    )
                    proc = subprocess.Popen(
                        cmd,
                        creationflags=creation_flags,
                        stderr=stderr_file,
                        stdout=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL,
                    )

                mc_session_start = time.time()
                self.stats["last_mc_start"] = int(mc_session_start)
                self.stats["launches"] = int(self.stats.get("launches", 0)) + 1
                save_stats(self.stats)
                self._sync_stats_to_cloud()

                with self._game_lock:
                    self._game_process = proc
                self._eval_js(f"setPlayButtonState('running', '{inst['id']}')")
                self._show_toast("Minecraft запущен!", "success")
                set_status("Игра работает!")

                self._update_cloud_activity(True, inst)
                ldr_name = loader.capitalize()
                self._update_discord_presence(
                    f"Играет в {inst['name']}", f"{mc_ver} ({ldr_name})"
                )

                time.sleep(1.5)
                self._eval_js("hideDownloadStatus()")

                if proc:
                    exit_code = proc.wait()
                if stderr_file and not stderr_file.closed:
                    stderr_file.close()
                    with self._game_lock:
                        if self._game_process is None:
                            manual_kill = True
                    if not manual_kill and exit_code is not None and exit_code != 0:
                        crashed_exit_code = exit_code
                        try:
                            if stderr_log_path and os.path.exists(stderr_log_path):
                                with open(
                                    stderr_log_path,
                                    "r",
                                    encoding="utf-8",
                                    errors="ignore",
                                ) as f:
                                    tail = f.read()
                                if tail:
                                    lines = [
                                        ln.strip()
                                        for ln in tail.splitlines()
                                        if ln.strip()
                                    ]
                                    if lines:
                                        crashed_error_text = (
                                            " | ".join(lines[-5:])[:800]
                                        )
                        except Exception:
                            pass
            except Exception as e:
                log.warning("Ошибка запуска: %s", e)
                self._update_status(f"Ошибка: {e}", 0)
                self._show_toast(f"Ошибка запуска: {e}", "error")
                crashed_error_text = str(e)
            finally:
                try:
                    if mc_session_start > 0:
                        delta = int(time.time() - mc_session_start)
                        if delta > 0:
                            self.stats["minecraft_seconds"] = int(
                                self.stats.get("minecraft_seconds", 0)
                            ) + delta
                            save_stats(self.stats)
                            self._sync_stats_to_cloud()
                except Exception as _e:
                    log.debug("[mc stats] %s", _e)

                with self._game_lock:
                    self._game_process = None
                self.active_running_instance_id = None
                self._update_cloud_activity(False)
                self._update_discord_presence("В лаунчере", "Готовится к игре")
                self._eval_js("setPlayButtonState('default')")
                self._eval_js("hideDownloadStatus()")

                if crashed_exit_code is not None or crashed_error_text:
                    try:
                        crash_info = self._collect_crash_info(
                            inst, crashed_error_text, crashed_exit_code
                        )
                        self._show_toast(
                            f"💥 Minecraft вылетел! Код: {crash_info['code']}",
                            "error",
                        )
                        payload = json.dumps(crash_info, ensure_ascii=False)
                        safe = (
                            payload.replace("\\", "\\\\")
                            .replace("'", "\\'")
                            .replace("\n", "\\n")
                            .replace("\r", "")
                        )
                        self._eval_js(f"showCrashModal('{safe}')")
                    except Exception as _ce:
                        log.warning("[crash modal] %s", _ce)
                        self._show_toast("Игра закрыта с ошибкой", "error")
                else:
                    self._show_toast("Игра закрыта", "info")

        threading.Thread(target=run, daemon=True, name="launch-game").start()
        return {"status": "ok"}


# ================= СТИЛИ И ИНТЕРФЕЙС (HTML_CONTENT) =================
HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Cube Launcher</title>
    <style>
        /* Подключение локального шрифта Minecraft */
        @font-face {
            font-family: 'MinecraftCustom';
            src: url('file:///C:/CubeLauncher/Launcher/fonts/minecraft.ttf') format('truetype');
            font-weight: normal;
            font-style: normal;
        }

        :root {
            --bg-main: #0c0a0b;
            --bg-card: #181416;
            --bg-card-hover: #241d21;
            --accent: #f97316;
            --accent-hover: #ea580c;
            --accent-glow: rgba(249, 115, 22, 0.32);
            --text-primary: #f8fafc;
            --text-secondary: #9ca3af;
            --border: #2e262a;
            --border-hover: #483a42;
            --radius-lg: 18px;
            --radius-md: 12px;
            --radius-sm: 8px;
            --radius-pill: 9999px;
            --anim-speed: 0.22s;
            --anim-curve: cubic-bezier(0.16, 1, 0.3, 1);
            --mc-font: 'MinecraftCustom', 'Segoe UI', system-ui, -apple-system, sans-serif;
        }
        [data-theme="light"] {
            --bg-main: #f1f5f9;
            --bg-card: #ffffff;
            --bg-card-hover: #f8fafc;
            --accent: #ea580c;
            --accent-hover: #c2410c;
            --accent-glow: rgba(234, 88, 12, 0.25);
            --text-primary: #0f172a;
            --text-secondary: #64748b;
            --border: #cbd5e1;
            --border-hover: #94a3b8;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: var(--mc-font);
            user-select: none;
            -webkit-user-select: none;
        }

        input, textarea, code, pre, .selectable, [contenteditable="true"] {
            user-select: text !important;
            -webkit-user-select: text !important;
        }

        /* Полностью закруглённые скроллбары */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: var(--bg-main);
            border-radius: var(--radius-pill);
        }
        ::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: var(--radius-pill);
            border: 2px solid var(--bg-main);
            transition: background var(--anim-speed) ease;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: var(--accent);
        }

        /* === МОДАЛЬНЫЕ ОКНА (СКРЫТЫ ПО УМОЛЧАНИЮ) === */
        .modal-overlay {
            position: fixed;
            top: 48px;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.88);
            display: none !important; /* КРИТИЧНО: окно скрыто, пока не вызвано! */
            align-items: center;
            justify-content: center;
            z-index: 9000;
            padding: 16px;
        }
        .modal-overlay.active {
            display: flex !important; /* Показывается ТОЛЬКО при открытии */
        }
        .modal-overlay.high-priority {
            z-index: 10050 !important;
            background: rgba(0, 0, 0, 0.94);
        }
        .modal-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            width: 560px;
            max-height: 88vh;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            overflow-y: auto;
            position: relative;
            box-shadow: 0 16px 48px rgba(0, 0, 0, 0.8);
        }
        .modal-card.large {
            width: 95%;
            max-width: 1050px;
            min-height: 580px;
            max-height: 90vh;
        }
        .modal-card.crash-modal-card {
            width: 640px;
            max-width: 95vw;
            background: linear-gradient(180deg, #1a1216 0%, #181416 100%);
            border: 1px solid rgba(239, 68, 68, 0.5);
            box-shadow: 0 0 40px rgba(239, 68, 68, 0.25);
            border-radius: var(--radius-lg);
            padding: 0;
            overflow: hidden;
        }

        body {
    background-color: #0c0a0b;
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            color: var(--text-primary);
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            border-radius: 0;   /* убирает закругления окна */
            border: none;        /* убирает внешнюю рамку */
            transform: translateZ(0);
        }

        /* Лайтбокс скриншотов (скрыт по умолчанию) */
        .lightbox-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.92);
            display: none !important; /* Скрывает его с экрана */
            align-items: center;
            justify-content: center;
            z-index: 100000;
        }
        .lightbox-overlay.active {
            display: flex !important; /* Показывается только при клике на скриншот */
        }
        .lightbox-close-btn {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid var(--border);
            color: #fff;
            font-size: 18px;
            width: 36px;
            height: 36px;
            border-radius: var(--radius-pill);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Segoe UI', sans-serif !important;
            transition: all var(--anim-speed) ease;
        }
        .lightbox-close-btn:hover {
            background: #ef4444;
        }
        .lightbox-img-wrap {
            position: relative;
            max-width: 85%;
            max-height: 80%;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 16px;
        }
        .lightbox-img {
            max-width: 100%;
            max-height: 75vh;
            border-radius: var(--radius-md);
            border: 1px solid var(--border);
            object-fit: contain;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8);
        }
        .lightbox-nav-btn {
            background: rgba(0, 0, 0, 0.6);
            border: 1px solid var(--border);
            color: #fff;
            font-size: 16px;
            width: 40px;
            height: 40px;
            border-radius: var(--radius-pill);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Segoe UI', sans-serif !important;
            transition: all var(--anim-speed) ease;
        }
        .lightbox-nav-btn:hover {
            background: var(--accent);
            border-color: var(--accent);
        }
        .lightbox-counter {
            position: absolute;
            bottom: 24px;
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 700;
            background: rgba(0, 0, 0, 0.6);
            padding: 6px 14px;
            border-radius: var(--radius-pill);
            border: 1px solid var(--border);
        }

        /* Лайтбокс скриншотов (скрыт по умолчанию) */
        .lightbox-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.92);
            display: none !important; /* Скрывает его с экрана */
            align-items: center;
            justify-content: center;
            z-index: 100000;
        }
        .lightbox-overlay.active {
            display: flex !important; /* Показывается только при клике на скриншот */
        }
        .lightbox-close-btn {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid var(--border);
            color: #fff;
            font-size: 18px;
            width: 36px;
            height: 36px;
            border-radius: var(--radius-pill);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Segoe UI', sans-serif !important;
            transition: all var(--anim-speed) ease;
        }
        .lightbox-close-btn:hover {
            background: #ef4444;
        }
        .lightbox-img-wrap {
            position: relative;
            max-width: 85%;
            max-height: 80%;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 16px;
        }
        .lightbox-img {
            max-width: 100%;
            max-height: 75vh;
            border-radius: var(--radius-md);
            border: 1px solid var(--border);
            object-fit: contain;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8);
        }
        .lightbox-nav-btn {
            background: rgba(0, 0, 0, 0.6);
            border: 1px solid var(--border);
            color: #fff;
            font-size: 16px;
            width: 40px;
            height: 40px;
            border-radius: var(--radius-pill);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Segoe UI', sans-serif !important;
            transition: all var(--anim-speed) ease;
        }
        .lightbox-nav-btn:hover {
            background: var(--accent);
            border-color: var(--accent);
        }
        .lightbox-counter {
            position: absolute;
            bottom: 24px;
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 700;
            background: rgba(0, 0, 0, 0.6);
            padding: 6px 14px;
            border-radius: var(--radius-pill);
            border: 1px solid var(--border);
        }

        /* Liquid Glass стили */
        body[data-liquid-glass="frosted"] .card,
        body[data-liquid-glass="frosted"] .modal-card,
        body[data-liquid-glass="frosted"] .sidebar,
        body[data-liquid-glass="frosted"] .bottom-bar,
        body[data-liquid-glass="frosted"] .titlebar, /* вернули */
        body[data-liquid-glass="frosted"] .friends-container,
        body[data-liquid-glass="frosted"] .inst-card,
        body[data-liquid-glass="frosted"] .account-card,
        body[data-liquid-glass="frosted"] .resource-card,
        body[data-liquid-glass="frosted"] .server-card,
        body[data-liquid-glass="frosted"] .stat-card {
            background: rgba(24, 20, 22, 0.58) !important;
            backdrop-filter: blur(24px) saturate(160%) !important;
            -webkit-backdrop-filter: blur(24px) saturate(160%) !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
        }
        body[data-liquid-glass="standard"] .card,
        body[data-liquid-glass="standard"] .modal-card,
        body[data-liquid-glass="standard"] .sidebar,
        body[data-liquid-glass="standard"] .bottom-bar,
        body[data-liquid-glass="standard"] .titlebar, /* вернули */
        body[data-liquid-glass="standard"] .friends-container,
        body[data-liquid-glass="standard"] .inst-card,
        body[data-liquid-glass="standard"] .account-card,
        body[data-liquid-glass="standard"] .resource-card,
        body[data-liquid-glass="standard"] .server-card,
        body[data-liquid-glass="standard"] .stat-card {
            background: rgba(24, 20, 22, 0.75) !important;
            backdrop-filter: blur(14px) saturate(140%) !important;
            -webkit-backdrop-filter: blur(14px) saturate(140%) !important;
            border: 1px solid rgba(255, 255, 255, 0.10) !important;
            box-shadow: 0 6px 24px rgba(0, 0, 0, 0.45) !important;
        }
        body[data-liquid-glass="transparent"] .card,
        body[data-liquid-glass="transparent"] .modal-card,
        body[data-liquid-glass="transparent"] .sidebar,
        body[data-liquid-glass="transparent"] .bottom-bar,
        body[data-liquid-glass="transparent"] .titlebar, /* вернули */
        body[data-liquid-glass="transparent"] .friends-container,
        body[data-liquid-glass="transparent"] .inst-card,
        body[data-liquid-glass="transparent"] .account-card,
        body[data-liquid-glass="transparent"] .resource-card,
        body[data-liquid-glass="transparent"] .server-card,
        body[data-liquid-glass="transparent"] .stat-card {
            background: rgba(24, 20, 22, 0.38) !important;
            backdrop-filter: blur(8px) saturate(120%) !important;
            -webkit-backdrop-filter: blur(8px) saturate(120%) !important;
            border: 1px solid rgba(255, 255, 255, 0.10) !important;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4) !important;
        }

.titlebar {
            height: 48px;
            background: var(--bg-main);
            transition: background 0.3s ease; /* Плавный переход к прозрачности */
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 16px;
            border-bottom: 1px solid var(--border);
            position: relative;
            z-index: 1000000;
            cursor: move;
            -webkit-app-region: drag;
            app-region: drag;
        }

        /* Непрозрачная шапка ТОЛЬКО во время загрузки */
        body.is-loading .titlebar {
            background: #0c0a0b !important;
            backdrop-filter: none !important;
            -webkit-backdrop-filter: none !important;
        }

        .titlebar-brand {
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 800;
            font-size: 14px;
            letter-spacing: 1.5px;
            color: var(--accent);
            pointer-events: none;
        }
        .window-controls {
            display: flex;
            gap: 8px;
            z-index: 10002;
            cursor: default;
        }
        .win-btn {
            width: 28px;
            height: 28px;
            border-radius: var(--radius-pill);
            border: none;
            background: var(--bg-card);
            color: var(--text-secondary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
            transition: all var(--anim-speed) var(--anim-curve);
        }
        .win-btn:hover {
            background: var(--border);
            color: var(--text-primary);
            transform: scale(1.08);
        }
        .win-btn.close:hover {
            background: #ef4444;
            color: white;
            box-shadow: 0 0 12px rgba(239, 68, 68, 0.5);
        }

        /* Каркас лаунчера */
        .app-body {
            display: flex;
            flex: 1;
            overflow: hidden;
            margin-bottom: 38px;
        }
        .sidebar {
            width: 235px;
            background: var(--bg-main);
            border-right: 1px solid var(--border);
            padding: 16px 12px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            z-index: 10;
        }
        .nav-btn {
            padding: 11px 16px;
            border-radius: var(--radius-md);
            border: 1px solid transparent;
            background: transparent;
            color: var(--text-secondary);
            text-align: left;
            font-size: 13px;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 12px;
            transition: all var(--anim-speed) var(--anim-curve);
        }
        .nav-btn:hover {
            background: var(--bg-card);
            color: var(--text-primary);
            transform: translateX(4px);
        }
        .nav-btn.active {
            background: var(--accent-glow);
            border-color: var(--accent);
            color: var(--accent);
            box-shadow: 0 0 14px var(--accent-glow);
        }

        .sidebar-profile {
            margin-top: auto;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 10px 12px;
            display: flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
            transition: all var(--anim-speed) var(--anim-curve);
        }
        .sidebar-profile:hover {
            border-color: var(--accent);
            transform: translateY(-2px);
            box-shadow: 0 4px 16px var(--accent-glow);
        }
        .sidebar-profile-avatar {
            width: 38px;
            height: 38px;
            border-radius: var(--radius-pill);
            object-fit: cover;
            border: 2px solid var(--accent);
            background: #241d21;
            flex-shrink: 0;
        }
        .sidebar-profile-info {
            display: flex;
            flex-direction: column;
            overflow: hidden;
            flex: 1;
        }
        .sidebar-profile-name {
            font-weight: 800;
            font-size: 13px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            color: var(--text-primary);
        }
        .sidebar-profile-sub {
            font-size: 11px;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 4px;
        }

        /* Контент и страницы */
        .content {
            flex: 1;
            padding: 24px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 16px;
            background: transparent;
        }
        .page {
            display: none;
            flex-direction: column;
            gap: 16px;
            height: 100%;
            animation: pageFadeIn 0.28s var(--anim-curve);
        }
        .page.active {
            display: flex;
        }
        @keyframes pageFadeIn {
            from {
                opacity: 0;
                transform: translateY(8px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        /* Универсальные закруглённые карточки и кнопки */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            transition: all var(--anim-speed) var(--anim-curve);
        }
        .card:hover {
            border-color: var(--border-hover);
        }

        .btn {
            padding: 9px 18px;
            border-radius: var(--radius-pill);
            border: none;
            background: linear-gradient(135deg, #f97316, #ea580c);
            color: white;
            font-weight: 800;
            font-size: 13px;
            cursor: pointer;
            box-shadow: 0 4px 14px var(--accent-glow);
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            white-space: nowrap;
            transition: all var(--anim-speed) var(--anim-curve);
        }
        .btn:disabled {
            opacity: 0.45;
            cursor: not-allowed;
            background: var(--border) !important;
            box-shadow: none !important;
            transform: none !important;
        }
        .btn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px var(--accent-glow);
        }
        .btn:active:not(:disabled) {
            transform: translateY(1px);
        }
        .btn-danger {
            background: linear-gradient(135deg, #ef4444, #dc2626) !important;
            box-shadow: 0 4px 14px rgba(239, 68, 68, 0.35) !important;
        }
        .btn-secondary {
            background: var(--border);
            box-shadow: none;
            color: var(--text-primary);
        }
        .btn-secondary:hover:not(:disabled) {
            background: var(--bg-card-hover);
            border-color: var(--accent);
        }
        .btn-ms {
            background: linear-gradient(135deg, #0078d4, #005a9e) !important;
            box-shadow: 0 4px 14px rgba(0, 120, 212, 0.35) !important;
        }
        .btn-installed {
            background: var(--bg-card-hover) !important;
            color: var(--text-secondary) !important;
            border: 1px solid var(--border) !important;
            box-shadow: none !important;
            cursor: default !important;
            transform: none !important;
        }
        .btn-update-available {
            background: linear-gradient(135deg, #eab308, #ca8a04) !important;
            color: #000 !important;
            font-weight: 800 !important;
        }

        /* Закруглённые поля ввода */
        input[type="text"],
        input[type="email"],
        input[type="password"],
        textarea {
            padding: 10px 16px;
            border-radius: var(--radius-md);
            border: 1px solid var(--border);
            background: var(--bg-main);
            color: var(--text-primary);
            outline: none;
            font-size: 13px;
            font-family: var(--mc-font);
            transition: all var(--anim-speed) ease;
        }
        input[type="text"]:focus,
        input[type="email"]:focus,
        input[type="password"]:focus,
        textarea:focus {
            border-color: var(--accent);
            box-shadow: 0 0 12px var(--accent-glow);
        }

        /* Кастомные закруглённые селекты */
        select {
            appearance: none;
            -webkit-appearance: none;
            padding: 10px 36px 10px 16px;
            border-radius: var(--radius-md);
            border: 1px solid var(--border);
            background: var(--bg-main) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23f97316' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E") no-repeat right 12px center;
            background-size: 14px;
            color: var(--text-primary);
            outline: none;
            font-size: 13px;
            font-family: var(--mc-font);
            cursor: pointer;
            transition: all var(--anim-speed) ease;
        }
        select:focus {
            border-color: var(--accent);
            box-shadow: 0 0 12px var(--accent-glow);
        }

        /* Кастомный закруглённый чекбокс */
        input[type="checkbox"] {
            appearance: none;
            -webkit-appearance: none;
            width: 22px;
            height: 22px;
            background: var(--bg-main);
            border: 2px solid var(--border);
            border-radius: var(--radius-sm);
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            outline: none;
            transition: all 0.2s var(--anim-curve);
            flex-shrink: 0;
            vertical-align: middle;
            margin: 0;
        }
        input[type="checkbox"]:hover {
            border-color: var(--accent);
            box-shadow: 0 0 10px var(--accent-glow);
        }
        input[type="checkbox"]:checked {
            background-color: var(--accent);
            border-color: var(--accent);
            background-size: 14px 14px;
            background-repeat: no-repeat;
            background-position: center;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='3.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='20 6 9 17 4 12'%3E%3C/polyline%3E%3C/svg%3E");
            box-shadow: 0 0 12px var(--accent-glow);
            transform: scale(1.05);
        }

        /* Ползунки Range с закруглением */
        .range-slider {
            width: 100%;
            accent-color: var(--accent);
            cursor: pointer;
            height: 6px;
            border-radius: var(--radius-pill);
            background: var(--border);
            outline: none;
            transition: all var(--anim-speed) ease;
        }

        /* Интерактивные всплывающие Toast-уведомления */
        .toast-container {
            position: fixed;
            bottom: 50px;
            right: 20px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            z-index: 99999;
            pointer-events: none;
        }
        .toast-item {
            background: var(--bg-card);
            border: 1px solid var(--accent);
            border-left: 6px solid var(--accent);
            padding: 12px 18px;
            border-radius: var(--radius-md);
            font-size: 13px;
            font-weight: 700;
            min-width: 260px;
            max-width: 400px;
            pointer-events: auto;
            box-shadow: 0 8px 24px rgba(0,0,0,0.6);
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            animation: toastSlide 0.28s var(--anim-curve);
        }
        @keyframes toastSlide {
            from {
                transform: translateX(40px) scale(0.95);
                opacity: 0;
            }
            to {
                transform: translateX(0) scale(1);
                opacity: 1;
            }
        }
        .toast-item.error { border-color: #ef4444; border-left-color: #ef4444; }
        .toast-item.success { border-color: #22c55e; border-left-color: #22c55e; }
        .toast-item.info { border-color: #3b82f6; border-left-color: #3b82f6; }
        .toast-copy-badge {
            background: var(--accent);
            color: #fff;
            padding: 4px 10px;
            border-radius: var(--radius-pill);
            font-size: 11px;
            cursor: pointer;
            border: none;
            font-weight: 800;
            flex-shrink: 0;
            transition: transform 0.15s ease;
        }
        .toast-copy-badge:hover {
            transform: scale(1.06);
        }
        /* Уведомления чата */
        .chat-notification-container {
            position: fixed;
            bottom: 50px;
            left: 20px;
            display: flex;
            flex-direction: column-reverse;
            gap: 10px;
            z-index: 99998;
            pointer-events: none;
        }
        .chat-notification-toast {
            background: var(--bg-card);
            border: 1px solid var(--accent);
            border-left: 6px solid var(--accent);
            padding: 12px 16px;
            border-radius: var(--radius-md);
            font-size: 13px;
            min-width: 270px;
            max-width: 350px;
            pointer-events: auto;
            display: flex;
            gap: 12px;
            align-items: center;
            cursor: pointer;
            box-shadow: 0 8px 24px rgba(0,0,0,0.6);
            animation: chatNotifSlide 0.25s var(--anim-curve);
        }
        @keyframes chatNotifSlide {
            from { transform: translateX(-30px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .chat-notification-toast .chat-notif-avatar {
            width: 38px;
            height: 38px;
            border-radius: var(--radius-pill);
            object-fit: cover;
            border: 2px solid var(--accent);
            flex-shrink: 0;
        }
        .chat-notification-toast .chat-notif-text-wrap {
            display: flex;
            flex-direction: column;
            gap: 2px;
            overflow: hidden;
            flex: 1;
        }
        .chat-notification-toast .chat-notif-name {
            font-weight: 800;
            font-size: 13px;
            color: var(--accent);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .chat-notification-toast .chat-notif-text {
            font-size: 12px;
            color: var(--text-secondary);
            line-height: 1.3;
        }

        /* Баннер на главной */
        .banner-container {
            position: relative;
            width: 100%;
            min-height: 290px;
            border-radius: var(--radius-lg);
            border: 1px solid var(--border);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            padding: 28px;
            background: linear-gradient(135deg, rgba(249,115,22,0.18), var(--bg-card));
        }
        .banner-media {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            z-index: 1;
            opacity: 0.65;
        }
        .banner-overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(to top, rgba(12,10,11,0.95) 0%, rgba(12,10,11,0.3) 60%, transparent 100%);
            z-index: 2;
        }
        .banner-content {
            position: relative;
            z-index: 3;
        }

        /* Виджет Cube Vanilla */
        .cube-vanilla-widget {
            background: linear-gradient(135deg, rgba(249,115,22,0.12), var(--bg-card));
            border-color: var(--accent);
            border-radius: var(--radius-lg);
            padding: 18px 22px;
            box-shadow: 0 4px 20px rgba(249, 115, 22, 0.1);
        }
        .cv-status-dot {
            display: inline-block;
            position: relative;
            width: 12px;
            height: 12px;
            border-radius: var(--radius-pill);
            margin-left: 6px;
        }
        .cv-status-dot.online {
            background: #22c55e;
            box-shadow: 0 0 10px #22c55e;
        }
        .cv-status-dot.offline {
            background: #64748b;
        }

        /* Карточки сборок (Установки) */
        .installations-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
            gap: 16px;
        }
        .inst-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 18px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            cursor: pointer;
            transition: all var(--anim-speed) var(--anim-curve);
        }
        .inst-card:hover {
            border-color: var(--accent);
            background: var(--bg-card-hover);
            transform: translateY(-3px);
            box-shadow: 0 8px 24px rgba(249, 115, 22, 0.15);
        }
        .inst-card.active {
            border-color: var(--accent);
            box-shadow: 0 0 20px var(--accent-glow);
        }
        .inst-card-info {
            display: flex;
            align-items: center;
            gap: 14px;
            flex: 1;
            overflow: hidden;
        }
        .inst-card-icon-preview {
            width: 46px;
            height: 46px;
            border-radius: var(--radius-md);
            object-fit: cover;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 26px;
            background: var(--bg-main);
            border: 1px solid var(--border);
            flex-shrink: 0;
        }
        .inst-card-texts {
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .inst-card-title {
            font-weight: 800;
            font-size: 16px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .inst-card-sub {
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 3px;
        }

        /* Серверный каталог */
        .servers-toolbar {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 12px 16px;
        }
        .servers-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(430px, 1fr));
            gap: 14px;
        }
        .server-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 16px 18px;
            display: flex;
            gap: 14px;
            cursor: pointer;
            align-items: flex-start;
            position: relative;
            overflow: hidden;
            transition: all var(--anim-speed) var(--anim-curve);
        }
        .server-card:hover {
            border-color: var(--accent);
            background: var(--bg-card-hover);
            transform: translateY(-3px);
            box-shadow: 0 8px 24px rgba(249, 115, 22, 0.16);
        }
        .server-card-offline {
            opacity: 0.74;
        }
        .server-icon-wrap {
            position: relative;
            flex-shrink: 0;
            width: 66px;
            height: 66px;
            border-radius: var(--radius-md);
            background: var(--bg-main);
            border: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }
        .server-icon-img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            image-rendering: pixelated;
        }
        .server-icon-emoji {
            font-size: 34px;
        }
        .server-status-dot {
            position: absolute;
            bottom: 4px;
            right: 4px;
            width: 14px;
            height: 14px;
            border-radius: var(--radius-pill);
            border: 2px solid var(--bg-card);
        }
        .server-status-dot.online {
            background: #22c55e;
            box-shadow: 0 0 8px #22c55e;
        }
        .server-status-dot.offline {
            background: #64748b;
        }
        .server-info {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 6px;
            overflow: hidden;
            min-width: 0;
        }
        .server-title-row {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }
        .server-name {
            font-size: 16px;
            font-weight: 800;
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .server-address {
            font-size: 11px;
            font-family: 'Consolas', monospace;
            color: var(--text-secondary);
            background: var(--bg-main);
            padding: 3px 8px;
            border-radius: var(--radius-pill);
            border: 1px solid var(--border);
            white-space: nowrap;
            cursor: pointer;
            transition: all var(--anim-speed) ease;
        }
        .server-address:hover {
            border-color: var(--accent);
            color: var(--accent);
        }
        .server-badges {
            display: flex;
            gap: 5px;
            flex-wrap: wrap;
        }
        .badge-license, .badge-nolicense, .badge-both, .badge-version, .badge-players {
            font-size: 10px;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: var(--radius-pill);
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }
        .badge-license { background: rgba(59, 130, 246, 0.18); border: 1px solid #3b82f6; color: #60a5fa; }
        .badge-nolicense { background: rgba(168, 85, 247, 0.18); border: 1px solid #a855f7; color: #c084fc; }
        .badge-both { background: rgba(16, 185, 129, 0.18); border: 1px solid #10b981; color: #34d399; }
        .badge-version { background: var(--bg-main); border: 1px solid var(--border); color: var(--text-secondary); font-family: 'Consolas', monospace; }
        .badge-players { background: rgba(34, 197, 94, 0.18); border: 1px solid #22c55e; color: #4ade80; font-weight: 800; }
        .badge-players.offline { background: rgba(100, 116, 139, 0.18); border-color: #64748b; color: #94a3b8; }
        .server-motd-preview {
            font-size: 12px;
            color: var(--text-secondary);
            line-height: 1.35;
            font-family: 'Consolas', monospace;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .server-desc-preview {
            font-size: 11px;
            color: var(--text-secondary);
            line-height: 1.35;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        /* Кастомный выпадающий список версий */
        .version-dropdown-btn {
            background: var(--bg-main);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 9px 14px;
            font-size: 13px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            min-height: 40px;
            transition: all var(--anim-speed) ease;
        }
        .version-dropdown-btn:hover {
            border-color: var(--accent);
        }
        .version-dropdown-list {
            display: none;
            position: absolute;
            top: calc(100% + 6px);
            left: 0;
            right: 0;
            background: var(--bg-card);
            border: 1px solid var(--accent);
            border-radius: var(--radius-md);
            max-height: 230px;
            overflow-y: auto;
            z-index: 500;
            box-shadow: 0 10px 30px rgba(0,0,0,0.7);
            animation: menuPopup 0.2s var(--anim-curve);
        }
        @keyframes menuPopup {
            from { opacity: 0; transform: translateY(-6px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .version-dropdown-item {
            padding: 10px 14px;
            cursor: pointer;
            font-size: 13px;
            border-bottom: 1px solid var(--border);
            transition: background var(--anim-speed) ease;
        }
        .version-dropdown-item:last-child {
            border-bottom: none;
        }
        .version-dropdown-item:hover {
            background: var(--bg-card-hover);
            color: var(--accent);
        }

        /* Друзья и чат */
        .friends-container {
            display: grid;
            grid-template-columns: 320px 1fr;
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            background: var(--bg-card);
            flex: 1;
            min-height: 520px;
            overflow: hidden;
        }
        .friends-sidebar {
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            background: var(--bg-main);
        }
        .friends-top-tabs {
            display: flex;
            border-bottom: 1px solid var(--border);
        }
        .friends-top-tab-btn {
            flex: 1;
            padding: 12px 6px;
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all var(--anim-speed) ease;
        }
        .friends-top-tab-btn.active {
            color: var(--accent);
            border-bottom-color: var(--accent);
            background: var(--bg-card);
        }
        .friends-list-panel {
            flex: 1;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
        }
        .friend-row-item {
            padding: 12px 14px;
            display: flex;
            align-items: center;
            gap: 12px;
            border-bottom: 1px solid var(--border);
            cursor: pointer;
            transition: background var(--anim-speed) ease;
        }
        .friend-row-item:hover, .friend-row-item.active {
            background: var(--bg-card-hover);
        }
        .friend-avatar-wrapper {
            position: relative;
            flex-shrink: 0;
        }
        .friend-row-avatar {
            width: 42px;
            height: 42px;
            border-radius: var(--radius-pill);
            object-fit: cover;
            background: #000;
            border: 1.5px solid var(--border);
        }
        .friend-status-dot {
            width: 11px;
            height: 11px;
            border-radius: var(--radius-pill);
            background: #22c55e;
            position: absolute;
            bottom: 0;
            right: 0;
            border: 2px solid var(--bg-card);
        }
        .friend-status-dot.offline {
            background: #64748b;
        }
        .friends-right-panel {
            display: flex;
            flex-direction: column;
            background: var(--bg-card);
            overflow: hidden;
        }
        .chat-header {
            padding: 14px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .chat-body-messages {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .msg-bubble {
            max-width: 68%;
            padding: 12px 16px;
            border-radius: var(--radius-lg);
            font-size: 13px;
            line-height: 1.45;
            display: flex;
            flex-direction: column;
            gap: 4px;
            animation: msgPop 0.2s var(--anim-curve);
        }
        @keyframes msgPop {
            from { transform: scale(0.9); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
        }
        .msg-bubble.mine {
            align-self: flex-end;
            background: linear-gradient(135deg, #f97316, #ea580c);
            color: #fff;
            border-bottom-right-radius: 4px;
        }
        .msg-bubble.theirs {
            align-self: flex-start;
            background: var(--bg-main);
            border: 1px solid var(--border);
            border-bottom-left-radius: 4px;
        }
        .chat-input-bar {
            padding: 12px 16px;
            border-top: 1px solid var(--border);
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .mic-record-btn {
            width: 40px;
            height: 40px;
            border-radius: var(--radius-pill);
            border: 1px solid var(--border);
            background: var(--bg-main);
            color: var(--text-primary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            flex-shrink: 0;
            transition: all var(--anim-speed) ease;
        }
        .mic-record-btn.recording {
            background: #ef4444;
            border-color: #ef4444;
            color: #fff;
            animation: micPulse 1.2s infinite ease-in-out;
        }
        @keyframes micPulse {
            0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.55); }
            70% { box-shadow: 0 0 0 12px rgba(239, 68, 68, 0); }
            100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        .mic-timer-badge {
            font-size: 11px;
            font-weight: 800;
            color: #ef4444;
            background: rgba(239, 68, 68, 0.12);
            padding: 4px 10px;
            border-radius: var(--radius-pill);
            border: 1px solid rgba(239, 68, 68, 0.4);
            display: none;
            flex-shrink: 0;
        }
        .mic-timer-badge.active {
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        /* Нижняя панель состояния */
        .bottom-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            height: 38px;
            background: var(--bg-main);
            border-top: 1px solid var(--border);
            display: flex;
            align-items: center;
            padding: 0 16px;
            gap: 12px;
            z-index: 2000;
        }
        .bottom-bar-progress {
            position: absolute;
            bottom: 0;
            left: 0;
            height: 3px;
            background: var(--accent);
            width: 0%;
            transition: width 0.15s ease;
        }

        /* Экран загрузки лаунчера */
        #loadingScreen {
            position: fixed;
            top: 48px; /* Начинается ровно под верхней панелью */
            left: 0; right: 0; bottom: 0;
            background: #0c0a0b;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 99999;
            transition: opacity 0.6s var(--anim-curve);
        }
        #loadingScreen.hidden {
            opacity: 0;
            pointer-events: none;
        }
        .loader-spinner {
            width: 64px;
            height: 64px;
            border: 5px solid rgba(249, 115, 22, 0.2);
            border-top: 5px solid #f97316;
            border-radius: var(--radius-pill);
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .loader-text {
            margin-top: 24px;
            font-size: 20px;
            font-weight: 800;
            color: #f8fafc;
            letter-spacing: 2px;
        }
        .loader-subtext {
            margin-top: 8px;
            font-size: 13px;
            color: #9ca3af;
            letter-spacing: 1px;
        }
    </style>
</head>
<body class="is-loading" data-theme="dark" data-liquid-glass="off">

    <!-- Экран первичной загрузки лаунчера -->
    <div id="loadingScreen">
        <div class="loader-spinner"></div>
        <div class="loader-text">CUBE LAUNCHER</div>
        <div class="loader-subtext">Загрузка модулей и ресурсов...</div>
    </div>

    <!-- Заголовок окна -->
    <div class="titlebar pywebview-drag-region">
<div class="titlebar-brand">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>
    CUBE LAUNCHER <span class="beta-badge">ßeтa</span>
</div>
        <div class="window-controls">
            <button class="win-btn" onclick="window.pywebview.api.minimize()" title="Свернуть">&#8722;</button>
            <button class="win-btn close" onclick="window.pywebview.api.close()" title="Закрыть">&#10005;</button>
        </div>
    </div>

    <div class="app-body">
        <!-- Боковое меню -->
        <div class="sidebar">
            <button class="nav-btn active" onclick="switchPage('play', event)"><span data-i18n="nav_play">🎮 Главная</span></button>
            <button class="nav-btn" onclick="switchPage('installations', event)"><span data-i18n="nav_installations">📦 Установки</span></button>
            <button class="nav-btn" onclick="switchPage('servers', event)"><span data-i18n="nav_servers">🌐 Сервера</span></button>
            <button class="nav-btn" onclick="switchPage('modpacks', event)"><span data-i18n="nav_modpacks">🎁 Модпаки</span></button>
            <button class="nav-btn" onclick="switchPage('friends', event)"><span data-i18n="nav_friends">👥 Друзья</span></button>
            <button class="nav-btn" onclick="switchPage('accounts', event)"><span data-i18n="nav_accounts">👤 Аккаунты</span></button>
            <button class="nav-btn" onclick="switchPage('settings', event)"><span data-i18n="nav_settings">⚙️ Настройки</span></button>
            
            <div class="sidebar-profile" id="sidebarProfileBtn" onclick="openProfileModal()">
                <img id="sidebarProfileAvatar" class="sidebar-profile-avatar" src="https://minotar.net/helm/Steve/100.png">
                <div class="sidebar-profile-info">
                    <div id="sidebarProfileName" class="sidebar-profile-name">Войти в профиль</div>
                    <div id="sidebarProfileSub" class="sidebar-profile-sub">✨ Cube Account</div>
                </div>
            </div>
        </div>

        <!-- Контент страниц -->
        <div class="content">
            <div id="globalMsBanner" class="ms-warning-banner" style="display: none; padding: 12px 18px; border-radius: var(--radius-md); background: rgba(234, 179, 8, 0.15); border: 1px solid rgba(234, 179, 8, 0.4); color: #fef08a; font-size: 13px; font-weight: 700;">
                <span style="font-size: 18px; margin-right: 8px;">⚠️</span>
                <span>Нет стабильной связи с серверами авторизации Microsoft.</span>
            </div>

            <!-- Главная вкладка (ВОТ ЭТОТ ТЕГ БЫЛ СЛУЧАЙНО СТЁРТ) -->
            <div id="play" class="page active">

                <!-- Официальный сервер Cube Vanilla -->
                <div class="card cube-vanilla-widget" id="cubeVanillaWidget">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
                        <!-- Левая часть: Картинка + вся информация о сервере -->
                        <div style="display: flex; align-items: center; gap: 16px; flex: 1; min-width: 280px;">
                            <img id="cvServerIcon" 
     src="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/poke-ball.png" 
     alt="Cube Vanilla"
                                 style="width: 64px; height: 64px; border-radius: var(--radius-md); object-fit: cover; border: 2px solid var(--accent); flex-shrink: 0; background: var(--bg-main);">
                            
                            <div style="display: flex; flex-direction: column;">
                                <div style="font-size: 11px; color: var(--accent); font-weight: 800; letter-spacing: 1.5px;">НАШ ОФИЦИАЛЬНЫЙ СЕРВЕР</div>
                                <div style="font-size: 22px; font-weight: 800; color: var(--text-primary); display: flex; align-items: center; gap: 6px; margin-top: 2px;">
                                    Cube Vanilla
                                    <span id="cvStatusDot" class="cv-status-dot offline"></span>
                                </div>
                                <div style="font-size: 13px; color: var(--text-secondary); margin-top: 4px;">
                                    IP: <b class="server-address" onclick="copyServerAddress('185.9.145.8:25994', 'Cube Vanilla')">185.9.145.8:25994</b>
                                    &nbsp;•&nbsp; Рекомендуемая версия: <b style="color: var(--accent);">1.21.11</b>
                                </div>
                                <div id="cvPlayersInfo" style="margin-top: 6px; font-size: 13px; color: var(--text-secondary);">⏳ Проверка статуса...</div>
                            </div>
                        </div>

                        <!-- Правая часть: Кнопки скопировать и обновить -->
                        <div style="display: flex; gap: 8px; align-items: center;">
                            <button class="btn btn-secondary" style="padding: 8px 16px;" onclick="copyServerAddress('185.9.145.8:25994', 'Cube Vanilla')">📋 Скопировать IP</button>
                            <button class="btn" style="padding: 8px 16px;" onclick="refreshCubeVanilla()">🔄 Обновить</button>
                        </div>
                    </div>
                </div>

                <div class="card" style="flex-direction: row; align-items: center; justify-content: space-between; margin-top: auto; border-radius: var(--radius-lg);">
                    <div>
                        <div style="font-size: 11px; font-weight: 800; color: var(--text-secondary); letter-spacing: 1px;" data-i18n="active_inst_label">АКТИВНАЯ СБОРКА</div>
                        <div id="activeInstTitle" style="font-size: 18px; font-weight: 800; color: var(--accent); margin-top: 4px;">Загрузка...</div>
                    </div>
                    <button class="btn" id="mainPlayBtn" style="padding: 14px 48px; font-size: 16px;" onclick="launchGame()" data-i18n="btn_play">ИГРАТЬ</button>
                </div>
            </div> <!-- закрывает #play -->

            <!-- Вкладка установок -->
            <div id="installations" class="page">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h2 data-i18n="inst_title">Сборки и Установки</h2>
                    <button class="btn" onclick="openCreateModal(false)" data-i18n="btn_create_inst">+ Создать установку</button>
                </div>
                <div style="font-size: 13px; color: var(--text-secondary);" data-i18n="inst_hint">💡 Нажмите на сборку, чтобы управлять модами, шейдерами и настройками!</div>
                <div class="installations-grid" id="installationsGrid"></div>
            </div>

            <!-- Вкладка серверов -->
            <div id="servers" class="page">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                    <div>
                        <h2 data-i18n="servers_title">🌐 Каталог серверов</h2>
                        <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;" id="serversLastUpdateLabel">Обновляется автоматически</div>
                    </div>
                    <button class="btn btn-refresh-servers" id="btnRefreshServers" onclick="refreshServersList(true, true)">🔄 Обновить сервера</button>
                </div>
                <div class="servers-toolbar">
                    <input type="text" id="serversSearchInput" placeholder="🔍 Поиск по названию или IP..." style="flex: 2; min-width: 180px;" oninput="applyServersFilter()">
                    <select id="serversLicenseFilter" style="flex: 1; min-width: 140px;" onchange="applyServersFilter()">
                        <option value="all">Все типы доступа</option>
                        <option value="licensed">🔵 Только лицензия</option>
                        <option value="pirate">🟣 Только пиратка</option>
                        <option value="both">🟢 Лицензия + Пиратка</option>
                    </select>
                    <select id="serversRegionFilter" style="flex: 1; min-width: 140px;" onchange="applyServersFilter()">
                        <option value="all">🌍 Все регионы</option>
                        <option value="RU">🇷🇺 Россия</option>
                        <option value="EU">🇪🇺 Европа</option>
                        <option value="US">🇺🇸 США</option>
                        <option value="EU/US">🌐 EU/US</option>
                        <option value="International">🌏 Международный</option>
                    </select>
                    <div style="position: relative; flex: 1; min-width: 160px;">
                        <div id="customVersionDropdownBtn" class="version-dropdown-btn" onclick="toggleVersionDropdown()">
                            <span id="selectedVersionText">Все версии</span>
                            <span style="color: var(--accent); font-size: 11px;">▼</span>
                        </div>
                        <div id="customVersionDropdownList" class="version-dropdown-list"></div>
                    </div>
                    <select id="serversStatusFilter" style="flex: 1; min-width: 130px;" onchange="applyServersFilter()">
                        <option value="all">Все статусы</option>
                        <option value="online">🟢 Только онлайн</option>
                        <option value="offline">🔴 Только оффлайн</option>
                    </select>
                </div>
                <div id="serversLoadingIndicator" style="display: none; padding: 24px; text-align: center; color: var(--text-secondary);">
                    <div style="font-size: 32px; margin-bottom: 8px;">⏳</div>
                    <div>Опрашиваем сервера Minecraft...</div>
                </div>
                <div class="servers-grid" id="serversGrid"></div>
                <div id="serversEmpty" style="display: none; padding: 40px 20px; text-align: center; color: var(--text-secondary);">
                    <div style="font-size: 42px; margin-bottom: 10px;">🔍</div>
                    <div>Серверы не найдены. Попробуйте сбросить фильтры.</div>
                </div>
                <div class="pagination-container" id="serversPagination" style="display: none; justify-content: center; gap: 12px; margin-top: 14px;">
                    <button class="pagination-btn btn btn-secondary" id="serversPrevPage" onclick="changeServersPage(-1)">◀ Назад</button>
                    <span id="serversPageInfo" style="font-size: 13px; font-weight: 700; align-self: center;">Страница 1 из 1</span>
                    <button class="pagination-btn btn btn-secondary" id="serversNextPage" onclick="changeServersPage(1)">Вперёд ▶</button>
                </div>
            </div>

            <!-- Вкладка модпаков -->
            <div id="modpacks" class="page">
                <h2 data-i18n="modpacks_title">Каталог Модпаков</h2>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <input type="text" id="modpackSearchInput" placeholder="Поиск модпаков по названию..." style="flex: 2;" oninput="onModpackSearchInput()">
                    <select id="modpackCatalogPlatform" style="flex: 1;" onchange="triggerModpackSearch(1)">
                        <option value="modrinth">🟢 Modrinth</option>
                        <option value="curseforge">🔥 CurseForge</option>
                    </select>
                    <select id="modpackLoaderFilter" style="flex: 1;" onchange="triggerModpackSearch(1)">
                        <option value="">Все загрузчики</option>
                        <option value="fabric">Fabric</option>
                        <option value="forge">Forge</option>
                        <option value="neoforge">NeoForge</option>
                        <option value="quilt">Quilt</option>
                    </select>
                    <select id="modpackVersionFilter" style="flex: 1;" onchange="triggerModpackSearch(1)">
                        <option value="">Все версии</option>
                    </select>
                </div>
                <div class="catalog-grid" id="modpacksGrid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(460px, 1fr)); gap: 12px; margin-top: 10px;"></div>
                <div class="pagination-container" id="modpacksPagination" style="display: flex; justify-content: center; gap: 12px; margin-top: 14px;">
                    <button class="pagination-btn btn btn-secondary" id="modpackPrevPage" onclick="changeModpackPage(-1)">◀ Назад</button>
                    <span id="modpackPageInfo" style="font-size: 13px; font-weight: 700; align-self: center;">Страница 1 из 1</span>
                    <button class="pagination-btn btn btn-secondary" id="modpackNextPage" onclick="changeModpackPage(1)">Вперёд ▶</button>
                </div>
            </div>

            <!-- Вкладка друзей -->
            <div id="friends" class="page">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h2 data-i18n="friends_title">Друзья и Сообщения</h2>
                    <div style="display: flex; gap: 8px;">
                        <input type="text" id="friendSearchNickInput" placeholder="Никнейм игрока для заявки...">
                        <button class="btn" onclick="sendFriendRequestAction()">+ Добавить</button>
                    </div>
                </div>
                <div class="friends-container">
                    <div class="friends-sidebar">
                        <div class="friends-top-tabs">
                            <button class="friends-top-tab-btn active" id="subtabFriendsBtn" onclick="switchFriendsSubTab('friends', event)">Друзья (<span id="friendsCountBadge">0</span>)</button>
                            <button class="friends-top-tab-btn" id="subtabRequestsBtn" onclick="switchFriendsSubTab('requests', event)">Заявки (<span id="requestsCountBadge">0</span>)</button>
                        </div>
                        <div id="friendsListContainer" class="friends-list-panel"></div>
                        <div id="requestsListContainer" class="friends-list-panel" style="display: none;"></div>
                    </div>
                    <div class="friends-right-panel" id="friendsRightPanel">
                        <div style="flex: 1; display: flex; align-items: center; justify-content: center; color: var(--text-secondary); text-align: center; padding: 20px;">
                            Выберите друга из списка слева для просмотра профиля или начала диалога
                        </div>
                    </div>
                </div>
            </div>

            <!-- Вкладка аккаунтов -->
            <div id="accounts" class="page">
                <h2 data-i18n="accounts_title">Управление аккаунтами Minecraft</h2>
                <div class="accounts-auth-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                    <div class="card" style="justify-content: space-between; border-radius: var(--radius-lg);">
                        <div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="font-size: 22px;">👤</span>
                                <h3 style="font-size: 16px;">Оффлайн аккаунт</h3>
                            </div>
                            <p style="font-size: 13px; color: var(--text-secondary); margin-top: 6px;">Быстрый вход без лицензии. Введите никнейм для игры.</p>
                            <div class="form-group" style="margin-top: 14px; display: flex; flex-direction: column; gap: 6px;">
                                <label style="font-size: 11px; font-weight: 800; color: var(--text-secondary);">Никнейм в игре</label>
                                <input type="text" id="accInput" placeholder="Введите ваш ник...">
                            </div>
                        </div>
                        <button class="btn" style="margin-top: 14px;" onclick="addOfflineAccount()">Добавить оффлайн-профиль</button>
                    </div>

                    <div class="card" style="border-color: rgba(0, 120, 212, 0.4); justify-content: space-between; border-radius: var(--radius-lg);">
                        <div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <svg width="22" height="22" viewBox="0 0 23 23"><path fill="#f25022" d="M1 1h10v10H1z"/><path fill="#00a4ef" d="M1 12h10v10H1z"/><path fill="#7fba00" d="M12 1h10v10H12z"/><path fill="#ffb900" d="M12 12h10v10H12z"/></svg>
                                <h3 style="font-size: 16px;">Microsoft Лицензия</h3>
                            </div>
                            <p style="font-size: 13px; color: var(--text-secondary); margin-top: 6px; line-height: 1.45;">Официальный безопасный вход через учетную запись Microsoft.</p>
                        </div>
                        <button class="btn btn-ms" style="padding: 13px 20px; font-size: 14px; margin-top: 14px;" onclick="startMicrosoftAuth()">🌐 Войти через Microsoft</button>
                    </div>
                </div>

                <div class="card" style="margin-top: 6px; border-radius: var(--radius-lg);">
                    <h3 style="font-size: 16px;">Сохранённые аккаунты</h3>
                    <div id="accountsList" style="display: flex; flex-direction: column; gap: 10px; margin-top: 10px;"></div>
                </div>
            </div>

            <!-- Вкладка настроек -->
            <div id="settings" class="page">
                <h2 data-i18n="settings_title">Настройки Лаунчера</h2>
                <div class="card" style="max-width: 650px; border-radius: var(--radius-lg);">
                    <div class="settings-tag-marker" style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 1.5px; text-transform: uppercase;">🖼️ Интерфейс</div>
                    <div style="display: flex; align-items: center; gap: 10px; margin-top: 4px;">
                        <input type="checkbox" id="settingShowBannerToggle" onchange="onBannerToggleChange(this.checked)">
                        <label for="settingShowBannerToggle" style="cursor: pointer; font-size: 13px; font-weight: 700;">Показывать виджет сервера Cube Vanilla на главной</label>
                    </div>

                    <div class="settings-tag-marker" style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 1.5px; text-transform: uppercase; margin-top: 14px;">🎨 Тема и Язык</div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <label style="font-size: 13px; font-weight: 700;">Язык интерфейса</label>
                        <select id="settingLangSelect" onchange="onLanguageSelectChange(this.value)">
                            <option value="ru">Русский (RU)</option>
                            <option value="en">English (US)</option>
                        </select>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
                        <label style="font-size: 13px; font-weight: 700;">Тема оформления</label>
                        <select id="settingThemeSelect" onchange="onThemeSelectChange(this.value)">
                            <option value="dark">🌙 Тёмная (Dark)</option>
                            <option value="light">☀️ Светлая (Light)</option>
                        </select>
                    </div>

                    <div class="form-group" style="margin-top: 8px; display: flex; flex-direction: column; gap: 6px;">
                        <label style="font-size: 11px; font-weight: 800; color: var(--text-secondary);">Пользовательский баннер фона</label>
                        <div style="display: flex; gap: 8px;">
                            <input type="text" id="settingBannerPath" readonly placeholder="По умолчанию" style="flex: 1;">
                            <button class="btn btn-secondary" onclick="browseBanner()">Обзор...</button>
                            <button class="btn btn-danger" onclick="clearBanner()">✕</button>
                        </div>
                    </div>

                    <!-- Анимации -->
                    <div style="display: flex; flex-direction: column; margin-top: 10px;">
                        <div style="display: flex; align-items: center; justify-content: space-between;">
                            <div style="display: flex; align-items: center; gap: 10px;">
                                <input type="checkbox" id="settingAnimationsToggle" onchange="onAnimationsToggleChange(this.checked)">
                                <label for="settingAnimationsToggle" style="cursor: pointer; font-size: 13px; font-weight: 700;">Включить плавные анимации</label>
                            </div>
                            <button id="animSubmenuChevronBtn" class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="toggleAnimSubmenu()">▼</button>
                        </div>
                        <div id="animSubmenuContainer" style="display: none; flex-direction: column; gap: 8px; background: var(--bg-main); border-radius: var(--radius-md); padding: 12px 14px; margin-top: 8px; border: 1px solid var(--border);">
                            <div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: 700;">
                                <span>Скорость анимаций:</span>
                                <span id="animSpeedValueLabel" style="color: var(--accent);">1.0x (200ms)</span>
                            </div>
                            <input type="range" id="settingAnimSpeedSlider" class="range-slider" min="0.5" max="2.0" step="0.1" value="1.0" oninput="onAnimSpeedSliderInput(this.value)">
                        </div>
                    </div>

                    <!-- Liquid Glass эффект -->
                    <div class="settings-tag-marker" style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 1.5px; text-transform: uppercase; margin-top: 14px;">✨ Эффект Liquid Glass (BETA)</div>
                    <div style="display: flex; flex-direction: column;">
                        <div style="display: flex; align-items: center; justify-content: space-between;">
                            <div style="display: flex; align-items: center; gap: 10px;">
                                <input type="checkbox" id="settingLiquidGlassToggle" onchange="onLiquidGlassToggleChange(this.checked)">
                                <label for="settingLiquidGlassToggle" style="cursor: pointer; font-size: 13px; font-weight: 700;">Включить стеклянный блюр (BETA)</label>
                            </div>
                            <button id="liquidGlassChevronBtn" class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="toggleLiquidGlassSubmenu()">▼</button>
                        </div>
                        <div id="liquidGlassSubmenuContainer" style="display: none; flex-direction: column; gap: 8px; background: var(--bg-main); border-radius: var(--radius-md); padding: 12px 14px; margin-top: 8px; border: 1px solid var(--border);">
                            <div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: 700;">
                                <span>Режим стекла:</span>
                                <span id="liquidGlassValueLabel" style="color: var(--accent);">Стандартное</span>
                            </div>
                            <input type="range" id="settingLiquidGlassSlider" class="range-slider" min="0" max="3" step="1" value="1" oninput="onLiquidGlassSliderInput(this.value)">
                            <div style="display: flex; justify-content: space-between; gap: 6px; margin-top: 6px;">
                                <span class="badge-version" id="lgBadge0">Выкл</span>
                                <span class="badge-version" id="lgBadge1">Матовое</span>
                                <span class="badge-version" id="lgBadge2">Стандарт</span>
                                <span class="badge-version" id="lgBadge3">Прозрачное</span>
                            </div>
                        </div>
                    </div>

                    <!-- Сборки и активность -->
                    <div class="settings-tag-marker" style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 1.5px; text-transform: uppercase; margin-top: 14px;">📦 Сборки и Друзья</div>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <input type="checkbox" id="settingShowCubeVisualsToggle" onchange="onCubeVisualsToggleChange(this.checked)">
                        <label for="settingShowCubeVisualsToggle" style="cursor: pointer; font-size: 13px; font-weight: 700;">Показывать сборку CubeVisuals</label>
                    </div>
                    <div style="display: flex; align-items: center; gap: 10px; margin-top: 6px;">
                        <input type="checkbox" id="settingShowActivityToggle" onchange="triggerAutoSave()">
                        <label for="settingShowActivityToggle" style="cursor: pointer; font-size: 13px; font-weight: 700;">Транслировать друзьям, в какую сборку я играю</label>
                    </div>

                    <!-- Производительность и память -->
                    <div class="settings-tag-marker" style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 1.5px; text-transform: uppercase; margin-top: 14px;">⚡ Производительность и Память</div>
                    <div class="form-group" style="display: flex; flex-direction: column; gap: 6px;">
                        <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: 700;">
                            <label>Выделение памяти (RAM)</label>
                            <span id="ramMbLabel" style="color: var(--accent);">4096 МБ (4.0 ГБ)</span>
                        </div>
                        <input type="range" id="settingRamSlider" class="range-slider" min="1024" max="16384" step="512" value="4096" oninput="onRamSliderInput(this.value)">
                    </div>

                    <div class="form-group" style="margin-top: 8px; display: flex; flex-direction: column; gap: 6px;">
                        <label style="font-size: 11px; font-weight: 800; color: var(--text-secondary);">Дополнительные JVM аргументы</label>
                        <input type="text" id="settingJvm" placeholder="-XX:+UseG1GC" oninput="triggerAutoSave()">
                    </div>

                    <div style="display: flex; align-items: center; gap: 10px; margin-top: 8px;">
                        <input type="checkbox" id="settingConsole" onchange="triggerAutoSave()">
                        <label for="settingConsole" style="cursor: pointer; font-size: 13px; font-weight: 700;">Показывать консоль разработчика при запуске</label>
                    </div>

                    <!-- Интеграции -->
                    <div class="settings-tag-marker" style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 1.5px; text-transform: uppercase; margin-top: 14px;">🌐 Интеграции</div>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <input type="checkbox" id="settingDiscordRpcToggle" onchange="triggerAutoSave()">
                        <label for="settingDiscordRpcToggle" style="cursor: pointer; font-size: 13px; font-weight: 700;">Discord Rich Presence (Статус в Discord)</label>
                    </div>
                    <div style="display: flex; align-items: center; gap: 10px; margin-top: 6px;">
                        <input type="checkbox" id="settingTelemetryToggle" onchange="triggerAutoSave()">
                        <label for="settingTelemetryToggle" style="cursor: pointer; font-size: 13px; font-weight: 700;">Анонимная телеметрия лаунчера</label>
                    </div>
                    <!-- О лаунчере и версии -->
                    <div class="settings-tag-marker" style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 1.5px; text-transform: uppercase; margin-top: 14px;">ℹ️ О лаунчере</div>
                    
                    <div style="display: flex; flex-direction: column;">
                        <!-- Верхняя строка: Версия + Кнопка проверки + Стрелочка -->
                        <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="font-size: 13px; font-weight: 700;">Версия Cube Launcher:</span>
                                <span class="badge-version" style="color: var(--accent); font-weight: 800; padding: 4px 8px;">v1.0.0</span>
                                <span class="beta-badge" style="font-size: 9px; padding: 2px 6px;">Beta</span>
                            </div>
                            
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <button class="btn btn-secondary" id="btnCheckLauncherUpdate" style="padding: 5px 12px; font-size: 11px;" onclick="checkLauncherUpdates()">
                                    🔄 Проверить обновления
                                </button>
                                <button id="aboutSubmenuChevronBtn" class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="toggleAboutSubmenu()">
                                    ▼
                                </button>
                            </div>
                        </div>

                        <!-- Выпадающий блок с подробностями о версии -->
                        <div id="aboutSubmenuContainer" style="display: none; flex-direction: column; gap: 10px; background: var(--bg-main); border-radius: var(--radius-md); padding: 14px 16px; margin-top: 10px; border: 1px solid var(--border);">
                            <div style="display: flex; justify-content: space-between; font-size: 12px; border-bottom: 1px solid var(--border); padding-bottom: 6px;">
                                <span style="color: var(--text-secondary);">Текущая сборка:</span>
                                <span style="font-weight: 700; color: var(--text-primary);">v1.0.0-beta.4 (2026)</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; font-size: 12px; border-bottom: 1px solid var(--border); padding-bottom: 6px;">
                                <span style="color: var(--text-secondary);">Тип релиза:</span>
                                <span style="color: #60a5fa; font-weight: 700;">Public Beta (Открытое тестирование)</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; font-size: 12px; border-bottom: 1px solid var(--border); padding-bottom: 6px;">
                                <span style="color: var(--text-secondary);">Статус обновлений:</span>
                                <span id="launcherUpdateStatusText" style="color: #22c55e; font-weight: 700;">✓ Установлена актуальная версия</span>
                            </div>
                            <div style="font-size: 11px; color: var(--text-secondary); line-height: 1.5; margin-top: 4px;">
                                Официальный клиент Cube Launcher для серверов Minecraft. Все права защищены © 2026.
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Контейнеры всплывающих уведомлений -->
    <div class="toast-container" id="toastContainer"></div>
    <div class="chat-notification-container" id="chatNotificationContainer"></div>

    <!-- Нижняя полоса статуса -->
    <div class="bottom-bar">
        <div id="bottomBarStatus" style="font-size: 12px; color: var(--text-secondary); font-weight: 700;">Готов к запуску</div>
        <div class="bottom-bar-progress" id="bottomBarProgress"></div>
    </div>
    <!-- ================= МОДАЛЬНЫЕ ОКНА ================= -->

    <!-- Модальное окно деталей сервера -->
    <div class="modal-overlay" id="serverDetailModal">
        <div class="modal-card large" style="max-width: 900px; border-radius: var(--radius-lg);">
            <div style="display: flex; justify-content: flex-end;">
                <button class="btn btn-secondary" style="border-radius: var(--radius-pill); padding: 6px 14px;" onclick="closeModal('serverDetailModal')">✕</button>
            </div>
            <div class="server-detail-header" style="display: flex; gap: 18px; align-items: center; padding-bottom: 16px; border-bottom: 1px solid var(--border);">
                <img id="sdIcon" class="server-detail-icon" src="" onerror="this.style.display='none'" style="width: 82px; height: 82px; border-radius: var(--radius-md); object-fit: cover; border: 2px solid var(--accent); background: var(--bg-main);">
                <div style="flex: 1; min-width: 0;">
                    <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                        <h2 id="sdName" style="font-size: 24px; font-weight: 800;">Server</h2>
                        <span id="sdLicenseBadge" class="badge-license">Лицензия</span>
                        <span id="sdPlayersBadge" class="badge-players">👥 0/0</span>
                    </div>
                    <div id="sdAddress" class="server-address" style="margin-top: 8px; display: inline-block; font-size: 13px; padding: 4px 12px;" onclick="copyServerAddressFromDetail()">play.example.com</div>
                    <div id="sdMotdBox" style="margin-top: 8px; font-family: 'Consolas', monospace; font-size: 12px; color: var(--text-secondary); white-space: pre-wrap; line-height: 1.4;"></div>
                </div>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <button class="btn" onclick="copyServerAddressFromDetail()">📋 Скопировать IP</button>
                    <button class="btn btn-secondary" id="sdWebsiteBtn" onclick="openServerWebsite()">🔗 Сайт проекта</button>
                </div>
            </div>

            <div class="server-detail-tabs" style="display: flex; gap: 8px; border-bottom: 1px solid var(--border); padding-bottom: 10px;">
                <button class="tab-btn active btn btn-secondary" onclick="switchServerDetailTab('desc', event)">📄 Описание</button>
                <button class="tab-btn btn btn-secondary" onclick="switchServerDetailTab('shots', event)">🖼️ Скриншоты</button>
                <button class="tab-btn btn btn-secondary" onclick="switchServerDetailTab('comments', event)">💬 Отзывы</button>
                <button class="tab-btn btn btn-secondary" onclick="switchServerDetailTab('rating', event)">⭐ Рейтинг</button>
            </div>

            <div id="sdtDesc" style="display: flex; flex-direction: column; gap: 12px;">
                <div style="background: var(--bg-main); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 16px 18px; font-size: 13px; line-height: 1.6;" id="sdDescriptionText">...</div>
                <div style="display: flex; gap: 10px; flex-wrap: wrap; font-size: 12px;">
                    <span id="sdRegionBadge" class="badge-version">🌍 —</span>
                    <span id="sdVersionsBadge" class="badge-version">🎮 —</span>
                </div>
            </div>

            <div id="sdtShots" style="display: none; flex-direction: column; gap: 8px;">
                <div id="sdScreenshotsStrip" class="server-screenshot-strip" style="display: flex; gap: 10px; overflow-x: auto; padding: 6px 0;"></div>
                <div id="sdScreenshotsEmpty" class="server-empty-screenshots" style="font-size: 13px; color: var(--text-secondary); padding: 16px; text-align: center; background: var(--bg-main); border-radius: var(--radius-md);">У этого сервера пока нет добавленных скриншотов.</div>
            </div>

            <div id="sdtComments" style="display: none; flex-direction: column; gap: 12px;">
                <div style="display: flex; gap: 10px; align-items: flex-start;">
                    <img id="sdMyAvatar" class="server-comment-avatar" src="https://minotar.net/helm/Steve/100.png" style="width: 38px; height: 38px; border-radius: var(--radius-pill); border: 1px solid var(--border);">
                    <div style="flex: 1; display: flex; flex-direction: column; gap: 8px;">
                        <textarea id="sdCommentInput" rows="2" placeholder="Оставьте честный отзыв о сервере..." style="resize: vertical;"></textarea>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div id="sdStarsInput" style="display: flex; gap: 4px; cursor: pointer; font-size: 22px; color: var(--text-secondary);">
                                <span data-star="1">★</span><span data-star="2">★</span><span data-star="3">★</span><span data-star="4">★</span><span data-star="5">★</span>
                            </div>
                            <button class="btn" onclick="submitServerComment()">💬 Опубликовать</button>
                        </div>
                    </div>
                </div>
                <div id="sdCommentsList" style="display: flex; flex-direction: column; gap: 8px; max-height: 320px; overflow-y: auto;"></div>
            </div>

            <div id="sdtRating" style="display: none; flex-direction: column; gap: 14px; align-items: center; padding: 20px;">
                <div id="sdRatingBig" style="font-size: 58px; font-weight: 800; color: var(--accent); line-height: 1;">0.0</div>
                <div id="sdRatingStars" class="server-rating-stars" style="font-size: 26px; color: #facc15;">☆☆☆☆☆</div>
                <div id="sdRatingCount" style="font-size: 13px; color: var(--text-secondary);">На основе 0 отзывов</div>
                <div id="sdRatingBars" style="width: 100%; max-width: 420px; display: flex; flex-direction: column; gap: 6px;"></div>
            </div>
        </div>
    </div>

    <!-- Модальное окно краш-репорта -->
    <div class="modal-overlay high-priority" id="crashModal">
        <div class="modal-card crash-modal-card" style="border-radius: var(--radius-lg);">
            <div class="crash-header" style="background: linear-gradient(135deg, #7f1d1d, #450a0a); padding: 22px 26px; display: flex; align-items: center; gap: 14px; border-bottom: 1px solid rgba(239, 68, 68, 0.3);">
                <div class="crash-header-icon" style="font-size: 34px;">💥</div>
                <div class="crash-header-text" style="display: flex; flex-direction: column; gap: 2px;">
                    <div class="crash-header-title" style="font-size: 20px; font-weight: 800; color: #fff;">Minecraft неожиданно закрылся!</div>
                    <div class="crash-header-subtitle" id="crashInstanceSubtitle" style="font-size: 12px; color: #fca5a5;">—</div>
                </div>
            </div>
            <div class="crash-body" style="padding: 22px 26px; display: flex; flex-direction: column; gap: 16px; max-height: 55vh; overflow-y: auto;">
                <div class="crash-code-box" style="background: #0a0608; border: 2px dashed #ef4444; border-radius: var(--radius-md); padding: 14px 18px; display: flex; align-items: center; justify-content: space-between;">
                    <div>
                        <div class="crash-code-label" style="font-size: 11px; color: #9ca3af; font-weight: 800; letter-spacing: 1px;">КОД ОШИБКИ ДЛЯ ТЕХПОДДЕРЖКИ</div>
                        <div class="crash-code-value" id="crashCodeValue" style="font-family: 'Consolas', monospace; font-size: 19px; font-weight: 800; color: #ef4444;">CL-0000-0000</div>
                    </div>
                    <button class="btn btn-secondary" style="padding: 6px 14px; font-size: 11px;" onclick="copyCrashCode()">📋 Скопировать</button>
                </div>
                <div>
                    <div style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 1px; text-transform: uppercase; margin-bottom: 4px;">ОПИСАНИЕ ОШИБКИ</div>
                    <div class="crash-description" id="crashDescriptionValue" style="background: var(--bg-main); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px 16px; font-size: 12px; line-height: 1.5; font-family: 'Consolas', monospace; white-space: pre-wrap; max-height: 140px; overflow-y: auto;">—</div>
                </div>
                <div>
                    <div style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 1px; text-transform: uppercase; margin-bottom: 6px;">ДЕЙСТВИЯ</div>
                    <div class="crash-actions-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                        <button class="btn btn-secondary" onclick="openLastLog()">📄 Открыть последний лог</button>
                        <button class="btn btn-secondary" onclick="openLogsFolder()">📁 Папка logs</button>
                        <button class="btn btn-secondary" onclick="openCrashFolder()">💥 Папка crash-reports</button>
                        <button class="btn btn-secondary" onclick="openLastCrash()">📄 Открыть crash-report</button>
                    </div>
                </div>
            </div>
            <div class="crash-footer" style="padding: 16px 26px 22px 26px; display: flex; gap: 10px; border-top: 1px solid var(--border); background: #120e10;">
                <button class="btn crash-close-btn" style="flex: 1; padding: 12px;" onclick="closeCrashModal()">Понятно, закрыть</button>
            </div>
        </div>
    </div>

    <!-- Модалка удаления аккаунта Cube Launcher -->
    <div class="modal-overlay high-priority" id="deleteAccountModal">
        <div class="modal-card" style="max-width: 480px; border-radius: var(--radius-lg);">
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 28px;">⚠️</span>
                <h3 style="color: #ef4444; font-size: 18px;">Удаление аккаунта Cube Launcher</h3>
            </div>
            <p style="font-size: 14px; font-weight: 700; line-height: 1.4;">Вы уверены, что хотите удалить свой профиль Cube Launcher?</p>
            <p style="font-size: 12px; color: var(--text-secondary); line-height: 1.4;">Это действие необратимо. Будет стёрта вся статистика, привязанные друзья, сообщения и никнейм.</p>
            <div style="display: flex; align-items: center; gap: 10px; background: var(--bg-main); padding: 12px; border-radius: var(--radius-md); border: 1px solid var(--border);">
                <input type="checkbox" id="delAccStep1Check" onchange="onDeleteAccountStep1Change(this.checked)">
                <label for="delAccStep1Check" style="font-size: 13px; font-weight: 700; cursor: pointer;">Я подтверждаю безвозвратное удаление</label>
            </div>
            <div id="delAccStep2Box" style="display: none; flex-direction: column; gap: 8px;">
                <label style="font-size: 12px; color: var(--text-secondary); font-weight: 700;">Введите точное имя аккаунта (<b id="delAccTargetNameDisplay" style="color: var(--accent);"></b>):</label>
                <input type="text" id="delAccConfirmInput" placeholder="Имя аккаунта..." oninput="onDeleteAccountInputChange()" autocomplete="off">
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 10px;">
                <button class="btn btn-secondary" onclick="closeModal('deleteAccountModal')">Отмена</button>
                <button class="btn btn-danger" id="btnConfirmDeleteAccount" disabled onclick="executeDeleteAccount()">Удалить навсегда</button>
            </div>
        </div>
    </div>

    <!-- Модалка профиля Cube Launcher и авторизации -->
    <div class="modal-overlay" id="profileModal">
        <div class="modal-card" style="border-radius: var(--radius-lg); max-width: 520px;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 12px;">
                <h3 id="modalAuthHeaderTitle" style="font-size: 17px; font-weight: 800;">Профиль Cube Launcher</h3>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <button class="btn btn-secondary" style="padding: 5px 12px; font-size: 13px; font-weight: 800;" onclick="showAddCubeAccountForm()">+ Другой</button>
                    <button class="btn btn-secondary" style="padding: 5px 10px;" onclick="closeModal('profileModal')">✕</button>
                </div>
            </div>

            <!-- Список переключения между аккаунтами -->
            <div id="cubeAccountsSwitchList" style="display: none; flex-direction: column; gap: 8px; background: var(--bg-main); padding: 12px; border-radius: var(--radius-md); border: 1px solid var(--border);">
                <div style="font-size: 11px; font-weight: 800; color: var(--accent); text-transform: uppercase;">Смена профиля</div>
                <div id="cubeAccountsListInner" style="display: flex; flex-direction: column; gap: 6px;"></div>
            </div>

            <!-- Форма авторизации/регистрации -->
            <div id="cubeNotLoggedView" style="display: flex; flex-direction: column; gap: 12px;">
                <div style="display: flex; gap: 8px; margin-bottom: 4px;">
                    <button class="btn" id="cubeModeLoginBtn" style="flex: 1;" onclick="setCubeAuthMode('login')">Вход</button>
                    <button class="btn btn-secondary" id="cubeModeRegBtn" style="flex: 1;" onclick="setCubeAuthMode('register')">Регистрация</button>
                </div>
                <div class="form-group" style="display: flex; flex-direction: column; gap: 6px;"><label id="lblCubeLogin" style="font-size: 11px; font-weight: 800; color: var(--text-secondary);">Никнейм или Email</label><input type="text" id="cubeInputLogin" placeholder="Ваш никнейм или почта..."></div>
                <div class="form-group" id="groupCubeEmail" style="display: none; flex-direction: column; gap: 6px;"><label style="font-size: 11px; font-weight: 800; color: var(--text-secondary);">Email адрес</label><input type="email" id="cubeInputEmail" placeholder="example@mail.ru"></div>
                <div class="form-group" style="display: flex; flex-direction: column; gap: 6px;"><label style="font-size: 11px; font-weight: 800; color: var(--text-secondary);">Пароль</label><div class="password-field-wrap" style="position: relative; display: flex; align-items: center;"><input type="password" id="cubeInputPassword" placeholder="••••••••" style="width: 100%; padding-right: 42px;"><button type="button" class="password-eye-btn" style="position: absolute; right: 12px; background: none; border: none; cursor: pointer; color: var(--text-secondary);" onclick="togglePassVisibility('cubeInputPassword', this)">👁️</button></div></div>
                <div class="form-group" id="groupCubePassRepeat" style="display: none; flex-direction: column; gap: 6px;"><label style="font-size: 11px; font-weight: 800; color: var(--text-secondary);">Повторите пароль</label><div class="password-field-wrap" style="position: relative; display: flex; align-items: center;"><input type="password" id="cubeInputPasswordRepeat" placeholder="••••••••" style="width: 100%; padding-right: 42px;"><button type="button" class="password-eye-btn" style="position: absolute; right: 12px; background: none; border: none; cursor: pointer; color: var(--text-secondary);" onclick="togglePassVisibility('cubeInputPasswordRepeat', this)">👁️</button></div></div>
                <div class="form-group" style="display: flex; flex-direction: column; gap: 6px;">
                    <label style="font-size: 11px; font-weight: 800; color: var(--text-secondary);">Проверка против ботов</label>
                    <div class="captcha-box" style="background: var(--bg-main); border: 1px solid var(--border); padding: 10px 14px; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: space-between; font-weight: 800; color: var(--accent);"><span id="captchaQuestionText">Загрузка...</span><button class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="refreshCaptcha()">🔄</button></div>
                    <input type="text" id="cubeCaptchaInput" placeholder="Введите ответ...">
                </div>
                <button class="btn" id="cubeSubmitBtn" style="padding: 13px; margin-top: 4px;" onclick="submitCubeAuth()">Войти в аккаунт</button>
            </div>

            <!-- Экран ввода 6-значного кода подтверждения -->
            <div id="cubeOtpVerificationView" style="display: none; flex-direction: column; gap: 14px; text-align: center;">
                <div style="font-size: 42px;">📧</div>
                <h3 id="otpHeaderActionText" style="font-size: 19px; font-weight: 800;">Подтверждение почты</h3>
                <p style="font-size: 13px; color: var(--text-secondary); line-height: 1.5;">Мы отправили 6-значный код на почту <br><b id="otpTargetEmailText" class="selectable" style="color: var(--text-primary);">example@mail.ru</b></p>
                <div class="form-group" style="margin: 6px 0;"><input type="text" id="cubeOtpCodeInput" class="otp-input-field" maxlength="6" placeholder="000000" inputmode="numeric" autocomplete="one-time-code" style="font-size: 26px; letter-spacing: 10px; text-align: center; border-radius: var(--radius-md); border: 2px dashed var(--accent); background: var(--bg-main);"></div>
                <button class="btn" id="btnConfirmOtpMain" style="padding: 13px; font-size: 14px;" onclick="confirmOtpAction()">✨ Подтвердить</button>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
                    <button class="btn btn-secondary" style="padding: 7px 14px; font-size: 12px;" onclick="backToAuthForm()">◀ Назад</button>
                    <button class="btn btn-secondary" id="btnResendOtp" style="padding: 7px 14px; font-size: 12px;" onclick="resendOtpCode()">Отправить заново</button>
                </div>
            </div>

            <!-- Экран авторизованного профиля -->
            <div id="cubeLoggedView" style="display: none; flex-direction: column; gap: 14px;">
                <div class="cube-profile-banner" style="display: flex; gap: 16px; align-items: flex-start; background: linear-gradient(135deg, rgba(249,115,22,0.12), transparent); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 18px;">
                    <img id="cubeFullAvatar" class="cube-profile-big-avatar" src="" style="width: 74px; height: 74px; border-radius: var(--radius-pill); object-fit: cover; border: 3px solid var(--accent); background: #231c20; flex-shrink: 0;">
                    <div style="flex: 1; min-width: 0;">
                        <h2 id="cubeFullUsername" style="font-size: 22px; font-weight: 800;">Username</h2>
                        <div id="cubeFullEmail" style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">Email</div>
                        <div class="profile-actions-row" style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px;">
                            <button class="btn btn-secondary" style="padding: 7px 12px; font-size: 12px;" onclick="changeCubeAvatar()">📷 Аватар</button>
                            <button class="btn btn-secondary" style="padding: 7px 12px; font-size: 12px;" onclick="logoutCube()">🚪 Выйти</button>
                            <button class="btn btn-danger" style="padding: 7px 12px; font-size: 12px;" onclick="openDeleteAccountModal(currentCubeUser.username)">🗑️ Удалить</button>
                        </div>
                    </div>
                </div>

                <div class="stats-grid" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                    <div class="stat-card" style="background: var(--bg-main); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px 16px; display: flex; flex-direction: column; gap: 4px;"><span class="stat-icon">🕒</span><div class="stat-value" id="myStatLauncherHours" style="font-size: 18px; font-weight: 800; color: var(--accent);">0с</div><div class="stat-label" style="font-size: 10px; color: var(--text-secondary); font-weight: 800; text-transform: uppercase;">В лаунчере</div></div>
                    <div class="stat-card" style="background: var(--bg-main); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px 16px; display: flex; flex-direction: column; gap: 4px;"><span class="stat-icon">🎮</span><div class="stat-value" id="myStatMinecraftHours" style="font-size: 18px; font-weight: 800; color: var(--accent);">0с</div><div class="stat-label" style="font-size: 10px; color: var(--text-secondary); font-weight: 800; text-transform: uppercase;">В игре</div></div>
                    <div class="stat-card" style="background: var(--bg-main); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px 16px; display: flex; flex-direction: column; gap: 4px;"><span class="stat-icon">🚀</span><div class="stat-value" id="myStatLaunches" style="font-size: 18px; font-weight: 800; color: var(--accent);">0</div><div class="stat-label" style="font-size: 10px; color: var(--text-secondary); font-weight: 800; text-transform: uppercase;">Запусков</div></div>
                </div>

                <div class="form-group" style="display: flex; flex-direction: column; gap: 6px;"><label style="font-size: 11px; font-weight: 800; color: var(--text-secondary);">О себе</label><textarea id="cubeBioText" rows="3" placeholder="Расскажите о себе друзьям..."></textarea></div>
                <div style="display: flex; justify-content: flex-end;"><button class="btn" onclick="saveCubeBio()">💾 Сохранить</button></div>
            </div>
        </div>
    </div>

    <!-- Модалка просмотра профиля другого игрока -->
    <div class="modal-overlay" id="profileViewModal">
        <div class="modal-card" style="max-width: 620px; border-radius: var(--radius-lg);">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 12px;">
                <h3 style="font-size: 17px; font-weight: 800;">Профиль игрока</h3>
                <button class="btn btn-secondary" style="padding: 5px 10px;" onclick="closeModal('profileViewModal')">✕</button>
            </div>
            <div class="cube-profile-banner" style="display: flex; gap: 16px; align-items: center; background: linear-gradient(135deg, rgba(249,115,22,0.12), transparent); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 18px;">
                <img id="pvAvatar" class="cube-profile-big-avatar" src="https://minotar.net/helm/Steve/100.png" style="width: 74px; height: 74px; border-radius: var(--radius-pill); object-fit: cover; border: 3px solid var(--accent); background: #231c20;">
                <div style="flex: 1; min-width: 0;">
                    <h2 id="pvUsername" style="font-size: 22px; font-weight: 800;">Player</h2>
                    <div id="pvStatus" style="font-size: 12px; color: var(--text-secondary); margin-top: 4px; font-weight: 700;">Не в сети</div>
                    <div id="pvActivityWrap" style="margin-top: 8px; display: none;"><div class="activity-pill" id="pvActivity"></div></div>
                </div>
            </div>
            <div>
                <div style="font-size: 11px; font-weight: 800; color: var(--accent); margin-bottom: 8px; text-transform: uppercase;">СТАТИСТИКА ИГРОКА</div>
                <div class="stats-grid" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                    <div class="stat-card" style="background: var(--bg-main); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px 16px; display: flex; flex-direction: column; gap: 4px;"><span class="stat-icon">🕒</span><div class="stat-value" id="pvStatLauncherHours" style="font-size: 18px; font-weight: 800; color: var(--accent);">0с</div><div class="stat-label" style="font-size: 10px; color: var(--text-secondary); font-weight: 800; text-transform: uppercase;">В лаунчере</div></div>
                    <div class="stat-card" style="background: var(--bg-main); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px 16px; display: flex; flex-direction: column; gap: 4px;"><span class="stat-icon">🎮</span><div class="stat-value" id="pvStatMinecraftHours" style="font-size: 18px; font-weight: 800; color: var(--accent);">0с</div><div class="stat-label" style="font-size: 10px; color: var(--text-secondary); font-weight: 800; text-transform: uppercase;">В игре</div></div>
                    <div class="stat-card" style="background: var(--bg-main); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px 16px; display: flex; flex-direction: column; gap: 4px;"><span class="stat-icon">🚀</span><div class="stat-value" id="pvStatLaunches" style="font-size: 18px; font-weight: 800; color: var(--accent);">0</div><div class="stat-label" style="font-size: 10px; color: var(--text-secondary); font-weight: 800; text-transform: uppercase;">Запусков</div></div>
                </div>
            </div>
            <div>
                <div style="font-size: 11px; font-weight: 800; color: var(--text-secondary); margin-bottom: 6px; text-transform: uppercase;">О себе</div>
                <div id="pvBio" style="padding: 14px; background: var(--bg-main); border-radius: var(--radius-md); border: 1px solid var(--border); font-size: 13px; line-height: 1.5;">Игрок Cube Launcher</div>
            </div>
            <div style="display: flex; gap: 8px; justify-content: flex-end;">
                <button class="btn" id="pvWriteMsgBtn">💬 Написать сообщение</button>
            </div>
        </div>
    </div>

    <!-- Модалка создания/редактирования сборки -->
    <div class="modal-overlay" id="createModal">
        <div class="modal-card" style="border-radius: var(--radius-lg); max-width: 520px;">
            <h3 id="modalInstTitle" style="font-size: 18px; font-weight: 800;">Создать установку</h3>
            <input type="hidden" id="modalInstId"><input type="hidden" id="modalInstCustomIcon">
            <div class="form-group" style="display: flex; flex-direction: column; gap: 6px;"><label style="font-size: 11px; font-weight: 800; color: var(--text-secondary);">Название сборки</label><input type="text" id="modalInstName" placeholder="Моя сборка"></div>
            <div class="form-group" style="display: flex; flex-direction: column; gap: 6px;">
                <label style="font-size: 11px; font-weight: 800; color: var(--text-secondary);">Иконка установки</label>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <div id="instIconPreview" class="inst-card-icon-preview">🟧</div>
                    <input type="text" id="modalInstIcon" value="🟧" style="width: 54px; text-align: center;" oninput="updateIconPreview(document.getElementById('modalInstCustomIcon').value, this.value)">
                    <button class="btn btn-secondary" style="font-size: 11px; padding: 7px 12px;" onclick="chooseCustomIcon()">Выбрать файл...</button>
                    <button class="btn btn-secondary" style="font-size: 11px; padding: 7px 12px;" onclick="resetIcon()">Сбросить</button>
                </div>
            </div>
            <div class="form-group" style="display: flex; flex-direction: column; gap: 6px;">
                <label style="font-size: 11px; font-weight: 800; color: var(--text-secondary);">Категория версий</label>
                <select id="modalVersionTypeSelect" onchange="filterVersionList()">
                    <option value="release">Релизы (Releases)</option>
                    <option value="snapshot">Снапшоты (Snapshots)</option>
                    <option value="old_beta">Beta версии</option>
                    <option value="old_alpha">Alpha / Classic</option>
                    <option value="all">Все версии</option>
                </select>
            </div>
            <div class="form-group" style="display: flex; flex-direction: column; gap: 6px;"><label style="font-size: 11px; font-weight: 800; color: var(--text-secondary);">Версия Minecraft</label><select id="modalMcVer" onchange="onMcVerChange()"></select></div>
            <div class="form-group" style="display: flex; flex-direction: column; gap: 6px;">
                <label style="font-size: 11px; font-weight: 800; color: var(--text-secondary);">Модификатор (Loader)</label>
                <select id="modalLoader" onchange="onLoaderChange()">
                    <option value="vanilla">Vanilla (Чистый клиент)</option>
                    <option value="fabric">Fabric</option>
                    <option value="forge">Forge</option>
                    <option value="neoforge">NeoForge</option>
                    <option value="quilt">Quilt</option>
                </select>
            </div>
            <div class="form-group" style="display: flex; flex-direction: column; gap: 6px;"><label style="font-size: 11px; font-weight: 800; color: var(--text-secondary);">Версия загрузчика</label><select id="modalLoaderVer"><option value="latest">Последняя (Latest)</option></select></div>
            <div class="form-group" id="optifineSupportBox" style="display: none; background: var(--bg-main); padding: 12px 14px; border-radius: var(--radius-md); border: 1px solid var(--border);">
                <div style="font-size: 11px; font-weight: 800; color: var(--accent); margin-bottom: 6px;">✨ ПРОВЕРКА OPTIFINE</div>
                <div id="optifineStatusText" style="font-size: 12px; font-weight: 700; margin-bottom: 8px;"></div>
                <div style="display: flex; align-items: center; gap: 8px;"><input type="checkbox" id="optifineInstallCheck"><label for="optifineInstallCheck" style="font-size: 12px; cursor: pointer; font-weight: 700;">Установить OptiFine автоматически</label></div>
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 10px;">
                <button class="btn btn-secondary" onclick="closeModal('createModal')">Отмена</button>
                <button class="btn" onclick="saveModalInstance()">Сохранить</button>
            </div>
        </div>
    </div>

    <!-- Модалка управления модами и файлами сборки -->
    <div class="modal-overlay" id="instanceViewModal">
        <div class="modal-card large" id="instViewCard" style="border-radius: var(--radius-lg);">
            <div class="drop-zone-overlay" id="instDropOverlay" style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(249, 115, 22, 0.16); border: 3px dashed var(--accent); border-radius: var(--radius-lg); display: none; align-items: center; justify-content: center; z-index: 50; pointer-events: none;"><div class="drop-zone-text" style="font-size: 18px; font-weight: 800; color: #fff; background: var(--bg-card); padding: 16px 28px; border-radius: var(--radius-md); border: 1px solid var(--accent);">📥 Перетащите .jar или .zip файлы сюда</div></div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h2 id="instViewTitle" style="font-size: 22px; font-weight: 800;">Сборка</h2>
                <div style="display: flex; gap: 8px;">
                    <button class="btn" id="modalPlayBtn" onclick="launchCurrentInstance()">🚀 Запустить</button>
                    <button class="btn btn-secondary" onclick="openActiveInstFolder()">📁 Папка</button>
                    <button class="btn btn-secondary" onclick="editCurrentInstance()">✏️ Изменить</button>
                    <button class="btn btn-danger" id="modalDeleteInstBtn" onclick="deleteCurrentInstance()">🗑️ Удалить</button>
                    <button class="btn btn-secondary" onclick="closeModal('instanceViewModal')">✕</button>
                </div>
            </div>
            <div class="tab-bar" style="display: flex; gap: 8px; border-bottom: 1px solid var(--border); padding-bottom: 10px;">
                <button class="tab-btn active btn btn-secondary" onclick="switchInstTab('mods', event)">🧩 Моды</button>
                <button class="tab-btn btn btn-secondary" onclick="switchInstTab('shaderpacks', event)">✨ Шейдеры</button>
                <button class="tab-btn btn btn-secondary" onclick="switchInstTab('resourcepacks', event)">🎨 Ресурспаки</button>
                <button class="tab-btn btn btn-secondary" onclick="switchInstTab('datapacks', event)">⚙️ Датапаки</button>
            </div>
            <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
                <input type="text" id="instSearchInput" placeholder="🔍 Поиск в сборке..." style="flex: 2;" oninput="applyInstalledFilter()">
                <select id="instStatusFilter" style="flex: 1;" onchange="applyInstalledFilter()">
                    <option value="all">Все файлы</option>
                    <option value="enabled">Включённые</option>
                    <option value="disabled">Отключённые</option>
                    <option value="updates">Требуют обновления</option>
                    <option value="release">Release</option>
                    <option value="beta">Beta</option>
                    <option value="alpha">Alpha</option>
                </select>
                <button class="btn" onclick="openAddModsModal()">+ Каталог проектов</button>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    <button class="btn btn-secondary" style="font-size: 12px; padding: 7px 14px;" onclick="checkModUpdates()" id="btnCheckUpdates">🔄 Проверить обновления</button>
                    <button class="btn btn-update-available" style="font-size: 12px; padding: 7px 14px; display: none;" onclick="updateAllMods()" id="btnUpdateAllMods">🚀 Обновить всё (0)</button>
                    <button class="btn btn-secondary" style="font-size: 12px; padding: 7px 12px;" onclick="toggleSelectedFiles(true)">Вкл. выбранные</button>
                    <button class="btn btn-secondary" style="font-size: 12px; padding: 7px 12px;" onclick="toggleSelectedFiles(false)">Выкл. выбранные</button>
                    <button class="btn btn-danger" style="font-size: 12px; padding: 7px 12px;" onclick="deleteSelectedFiles()" title="Удалить выбранные">🗑️</button>
                </div>
            </div>
            <div class="mods-table-header" style="display: flex; align-items: center; gap: 14px; padding: 10px 14px; background: var(--bg-main); border: 1px solid var(--border); border-radius: var(--radius-md); font-size: 11px; font-weight: 800; color: var(--text-secondary); text-transform: uppercase;">
                <input type="checkbox" id="selectAllModsCheck" class="mod-check" onchange="toggleSelectAllMods(this.checked)" title="Выбрать все">
                <div style="width: 44px;">Иконка</div>
                <div style="flex: 2;">Название / Автор</div>
                <div style="flex: 1.4;">Версия</div>
                <div style="width: 44px; text-align: center;">Статус</div>
                <div style="width: 90px; text-align: right;">Действия</div>
            </div>
            <div id="instFilesList" style="display: flex; flex-direction: column; gap: 8px; flex: 1; max-height: 420px; overflow-y: auto;"></div>
        </div>
    </div>

    <!-- Модалка каталога модификаций Modrinth/CurseForge -->
    <div class="modal-overlay" id="addModsModal">
        <div class="modal-card large" style="border-radius: var(--radius-lg);">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 style="font-size: 18px; font-weight: 800;">Каталог Модификаций</h3>
                <button class="btn btn-secondary" style="padding: 5px 10px;" onclick="closeModal('addModsModal')">✕</button>
            </div>
            <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
                <input type="text" id="modSearchInput" placeholder="Поиск дополнений..." style="flex: 2;" oninput="onModSearchInput()">
                <select id="modCatalogPlatform" style="flex: 1;" onchange="triggerAutoSearch(1)">
                    <option value="modrinth">🟢 Modrinth</option>
                    <option value="curseforge">🔥 CurseForge</option>
                </select>
                <select id="modTargetInstance" style="flex: 1;" onchange="onTargetInstanceChange()"></select>
                <select id="modTypeSelect" style="flex: 1;" onchange="triggerAutoSearch(1)">
                    <option value="mods">Моды</option>
                    <option value="shaders">Шейдеры</option>
                    <option value="resourcepacks">Ресурспаки</option>
                    <option value="datapacks">Датапаки</option>
                </select>
                <select id="modLoaderFilter" style="flex: 1;" onchange="triggerAutoSearch(1)">
                    <option value="">Все загрузчики</option>
                    <option value="fabric">Fabric</option>
                    <option value="forge">Forge</option>
                    <option value="quilt">Quilt</option>
                    <option value="neoforge">NeoForge</option>
                </select>
                <select id="modVersionFilter" style="flex: 1;" onchange="triggerAutoSearch(1)">
                    <option value="">Все версии</option>
                </select>
                <select id="modReleaseTypeFilter" style="flex: 1;" onchange="triggerAutoSearch(1)">
                    <option value="">Все релизы</option>
                    <option value="release">🚀 Release</option>
                    <option value="beta">🧪 Beta</option>
                    <option value="alpha">🧬 Alpha</option>
                </select>
            </div>
            <div class="catalog-grid" id="catalogGrid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(460px, 1fr)); gap: 12px; max-height: 420px; overflow-y: auto;"></div>
            <div class="pagination-container" id="modsPagination" style="display: flex; justify-content: center; gap: 12px; margin-top: 14px;">
                <button class="pagination-btn btn btn-secondary" id="modPrevPage" onclick="changeModPage(-1)">◀ Назад</button>
                <span id="modPageInfo" style="font-size: 13px; font-weight: 700; align-self: center;">Страница 1 из 1</span>
                <button class="pagination-btn btn btn-secondary" id="modNextPage" onclick="changeModPage(1)">Вперёд ▶</button>
            </div>
        </div>
    </div>

    <!-- Модалка просмотра файлов проекта -->
    <div class="modal-overlay" id="modDetailsModal">
        <div class="modal-card large" style="border-radius: var(--radius-lg);">
            <div style="display: flex; gap: 16px; align-items: center;">
                <img id="detailIcon" src="" style="width: 58px; height: 58px; border-radius: var(--radius-md); object-fit: cover; border: 1px solid var(--border);">
                <div style="flex: 1;">
                    <h2 id="detailTitle" style="font-size: 20px; font-weight: 800;">Название</h2>
                    <div id="detailMeta" style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">ID</div>
                </div>
                <button class="btn btn-secondary" style="padding: 5px 10px;" onclick="closeModal('modDetailsModal')">✕</button>
            </div>
            <div class="gallery-track" id="detailGallery" style="display: flex; gap: 10px; overflow-x: auto; width: 100%; padding: 8px 0;"></div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h4 style="margin-top: 6px; font-weight: 800;">Доступные версии:</h4>
                <select id="detailReleaseFilter" onchange="filterDetailVersions()" style="font-size: 12px; padding: 6px 14px;">
                    <option value="">Все типы</option>
                    <option value="release">🚀 Release</option>
                    <option value="beta">🧪 Beta</option>
                    <option value="alpha">🧬 Alpha</option>
                </select>
            </div>
            <div id="detailVersionsList" style="display: flex; flex-direction: column; gap: 8px; max-height: 240px; overflow-y: auto;"></div>
        </div>
    </div>

    <!-- Лайтбокс скриншотов -->
    <div class="lightbox-overlay" id="galleryLightbox">
        <button class="lightbox-close-btn" onclick="closeLightbox()">✕</button>
        <div class="lightbox-img-wrap">
            <button class="lightbox-nav-btn prev" onclick="changeLightboxImg(-1)">◀</button>
            <img id="lightboxMainImg" class="lightbox-img" src="">
            <button class="lightbox-nav-btn next" onclick="changeLightboxImg(1)">▶</button>
        </div>
        <div class="lightbox-counter" id="lightboxCounter">1 / 1</div>
    </div>

    <!-- ================= JAVASCRIPT ЛОГИКА ================= -->
    <script>
// ================= СОСТОЯНИЕ КЛИЕНТА =================
let currentLang = 'ru';
let globalConfig = {};
let currentViewingInstId = null;
let currentResourceTab = 'mods';
let searchDebounceTimer = null;
let autoSaveTimer = null;
let gameState = 'default';
let activeRunningId = null;
let cachedModUpdates = {};
let currentCubeUser = null;
let cubeAuthMode = 'login';
let targetAccountToDelete = null;
let mojangVersionsData = { releases: [], snapshots: [], old_beta: [], old_alpha: [], all: [] };
let modpackPage = 1, modpackTotalPages = 1;
let modCatalogPage = 1, modCatalogTotalPages = 1;
let currentRawCatalogItems = [];
let cachedInstalledFiles = [];
let cachedDetailVersions = [];
let currentLightboxGallery = [];
let currentLightboxIndex = 0;
let pendingAuthData = null;
let pendingAuthType = 'login';
let otpCooldownTimer = null;
let currentSelectedFriendUid = null;
let isAnimSubmenuOpen = false;
let isLiquidGlassSubmenuOpen = false;
let friendsPoller = null;
let chatPoller = null;
let currentProfileViewUid = null;
let currentCrashInfo = null;
let mediaRecorder = null;
let recordedChunks = [];
let recordingStartTime = 0;
let recordingTimerInterval = null;
let currentRecordingFriendUid = null;
const LIQUID_GLASS_VARIANTS = ['off', 'frosted', 'standard', 'transparent'];
let allServersData = [];
let currentServerDetail = null;
let currentServerDetailTab = 'desc';
let currentCommentRating = 5;
let serversCommentsCache = {};
let currentServerPage = 1;
const SERVERS_PER_PAGE = 6;
let selectedServerVersion = "";

// ================= ФОРМАТИРОВАНИЕ =================
function formatSeconds(totalSeconds) {
    totalSeconds = Math.max(0, Math.floor(totalSeconds || 0));
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const parts = [];
    if (hours > 0) parts.push(`${hours}ч`);
    if (minutes > 0 || hours > 0) parts.push(`${minutes}м`);
    parts.push(`${seconds}с`);
    return parts.join(' ');
}
function formatReleaseType(t) {
    const map = { release: '🚀 Release', beta: '🧪 Beta', alpha: '🧬 Alpha' };
    return map[t] || (t ? `📦 ${t}` : '');
}
function getReleaseBadgeClass(t) {
    if (t === 'beta') return 'badge-beta';
    if (t === 'alpha') return 'badge-alpha';
    return 'badge-release';
}
function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function escapeAttr(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

// ================= АУДИОСИСТЕМА =================
let audioCtx = null;
function getAudioContext() {
    if (!audioCtx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (AC) audioCtx = new AC();
    }
    if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
    return audioCtx;
}
function playUiSound(type = 'click') {
    try {
        const ctx = getAudioContext();
        if (!ctx) return;
        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        if (type === 'click') {
            osc.type = 'sine';
            osc.frequency.setValueAtTime(650, now);
            osc.frequency.exponentialRampToValueAtTime(140, now + 0.04);
            gain.gain.setValueAtTime(0.08, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);
            osc.start(now);
            osc.stop(now + 0.04);
        } else if (type === 'tab') {
            osc.type = 'sine';
            osc.frequency.setValueAtTime(420, now);
            osc.frequency.exponentialRampToValueAtTime(260, now + 0.035);
            gain.gain.setValueAtTime(0.06, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.035);
            osc.start(now);
            osc.stop(now + 0.035);
        } else if (type === 'checkbox') {
            osc.type = 'sine';
            osc.frequency.setValueAtTime(750, now);
            osc.frequency.exponentialRampToValueAtTime(950, now + 0.03);
            gain.gain.setValueAtTime(0.07, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.03);
            osc.start(now);
            osc.stop(now + 0.03);
        } else if (type === 'success') {
            osc.type = 'sine';
            osc.frequency.setValueAtTime(523, now);
            osc.frequency.setValueAtTime(659, now + 0.08);
            osc.frequency.setValueAtTime(784, now + 0.16);
            gain.gain.setValueAtTime(0.09, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.28);
            osc.start(now);
            osc.stop(now + 0.28);
        } else if (type === 'error') {
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(190, now);
            osc.frequency.linearRampToValueAtTime(100, now + 0.14);
            gain.gain.setValueAtTime(0.12, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.14);
            osc.start(now);
            osc.stop(now + 0.14);
        } else if (type === 'launch') {
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(220, now);
            osc.frequency.exponentialRampToValueAtTime(880, now + 0.18);
            gain.gain.setValueAtTime(0.12, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
            osc.start(now);
            osc.stop(now + 0.2);
        } else if (type === 'notify') {
            osc.type = 'sine';
            osc.frequency.setValueAtTime(880, now);
            osc.frequency.setValueAtTime(1175, now + 0.09);
            gain.gain.setValueAtTime(0.1, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
            osc.start(now);
            osc.stop(now + 0.2);
        } else if (type === 'crash') {
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(320, now);
            osc.frequency.exponentialRampToValueAtTime(80, now + 0.4);
            gain.gain.setValueAtTime(0.14, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
            osc.start(now);
            osc.stop(now + 0.4);
        }
    } catch (e) {}
}

let isAboutSubmenuOpen = false;

// Открытие / закрытие стрелочки
function toggleAboutSubmenu() {
    isAboutSubmenuOpen = !isAboutSubmenuOpen;
    const subBox = document.getElementById('aboutSubmenuContainer');
    const chevron = document.getElementById('aboutSubmenuChevronBtn');
    if (subBox) subBox.style.display = isAboutSubmenuOpen ? 'flex' : 'none';
    if (chevron) chevron.textContent = isAboutSubmenuOpen ? '▲' : '▼';
}

// Проверка обновлений с анимацией и уведомлением
async function checkLauncherUpdates() {
    const btn = document.getElementById('btnCheckLauncherUpdate');
    const statusText = document.getElementById('launcherUpdateStatusText');
    
    if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳ Проверка...';
    }
    
    // Имитация опроса сервера обновлений
    setTimeout(() => {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '🔄 Проверить обновления';
        }
        if (statusText) {
            statusText.textContent = '✓ У вас самая свежая версия (v1.0.0 Beta)';
            statusText.style.color = '#22c55e';
        }
        showToast("У вас установлена последняя версия Cube Launcher!", "success");
    }, 1200);
}

document.addEventListener('click', (e) => {
    if (e.target.closest('.btn') || e.target.closest('.win-btn') || e.target.closest('.pagination-btn')) playUiSound('click');
    else if (e.target.closest('.nav-btn') || e.target.closest('.tab-btn') || e.target.closest('.friends-top-tab-btn')) playUiSound('tab');
});
document.addEventListener('change', (e) => {
    if (e.target.matches('input[type="checkbox"]')) playUiSound('checkbox');
});

// ================= ИНТЕРАКТИВНОЕ КОПИРОВАНИЕ IP И УВЕДОМЛЕНИЯ =================
function copyServerAddress(address, serverName = '') {
    try {
        navigator.clipboard.writeText(address);
    } catch (e) {
        const dummy = document.createElement('textarea');
        dummy.value = address;
        document.body.appendChild(dummy);
        dummy.select();
        document.execCommand('copy');
        document.body.removeChild(dummy);
    }

    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'toast-item success';
    const sName = serverName ? ` «${escapeHtml(serverName)}»` : '';
    toast.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 2px; overflow: hidden;">
            <div style="font-weight: 800; font-size: 13px;">✅ IP скопирован!</div>
            <div style="font-size: 11px; color: var(--text-secondary); font-family: 'Consolas', monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(address)}${sName}</div>
        </div>
        <button class="toast-copy-badge" onclick="event.stopPropagation(); navigator.clipboard.writeText('${escapeAttr(address)}'); showToast('Скопировано повторно', 'info');">Копия</button>
    `;
    container.appendChild(toast);
    playUiSound('success');
    setTimeout(() => { if (toast.parentNode) toast.remove(); }, 4000);
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast-item ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    if (type === 'success') playUiSound('success');
    else if (type === 'error') playUiSound('error');
    setTimeout(() => { if (toast.parentNode) toast.remove(); }, 3500);
}

function showChatNotification(friendName, messageText, friendUid, chatKey) {
    const cont = document.getElementById('chatNotificationContainer');
    if (!cont) return;
    const toast = document.createElement('div');
    toast.className = 'chat-notification-toast';
    const avatarUrl = `https://minotar.net/helm/${encodeURIComponent(friendName)}/100.png`;
    toast.innerHTML =
        `<img class="chat-notif-avatar" src="${avatarUrl}" onerror="this.src='https://minotar.net/helm/Steve/100.png'">` +
        `<div class="chat-notif-text-wrap"><div class="chat-notif-name">${escapeHtml(friendName)}</div>` +
        `<div class="chat-notif-text">${escapeHtml(messageText)}</div></div>`;
    toast.onclick = () => {
        try {
            const navBtns = document.querySelectorAll('.nav-btn');
            let friendsBtn = null;
            navBtns.forEach(b => { if (b.textContent.includes('Друз')) friendsBtn = b; });
            if (friendsBtn) { friendsBtn.click(); setTimeout(() => openChatMessenger(friendUid, friendName), 250); }
        } catch (e) {}
        toast.remove();
    };
    cont.appendChild(toast);
    playUiSound('notify');
    setTimeout(() => { if (toast.parentNode) toast.remove(); }, 8000);
}

function updateDownloadStatus(text, val) {
    const s = document.getElementById('bottomBarStatus');
    if (s) s.textContent = text;
    if (val !== undefined && val !== null) {
        const p = document.getElementById('bottomBarProgress');
        if (p) p.style.width = val + '%';
    }
}
function updateDownloadProgress(val) {
    const p = document.getElementById('bottomBarProgress');
    if (p) p.style.width = val + '%';
}
function hideDownloadStatus() {
    const s = document.getElementById('bottomBarStatus');
    if (s) s.textContent = 'Готов к запуску';
    const p = document.getElementById('bottomBarProgress');
    if (p) p.style.width = '0%';
}

// ================= ЭКРАН ЗАГРУЗКИ =================
function hideLoadingScreen() {
    document.body.classList.remove('is-loading'); // Снимает сплошной цвет, шапка становится прозрачной
    const ls = document.getElementById('loadingScreen');
    if (!ls) return;
    ls.classList.add('hidden');
    setTimeout(() => { if (ls.parentNode) ls.remove(); }, 700);
}

// ================= LIVE СТАТИСТИКА =================
function updateLiveStats(stats) {
    const map = {
        myStatLauncherHours: 'launcher_seconds',
        myStatMinecraftHours: 'minecraft_seconds'
    };
    for (const [id, key] of Object.entries(map)) {
        const el = document.getElementById(id);
        if (el && stats[key] !== undefined) el.textContent = formatSeconds(stats[key]);
    }
    const l = document.getElementById('myStatLaunches');
    if (l && stats.launches !== undefined) l.textContent = stats.launches;
    const pvL = document.getElementById('pvStatLauncherHours');
    const pvM = document.getElementById('pvStatMinecraftHours');
    const pvLc = document.getElementById('pvStatLaunches');
    if (pvL && stats.launcher_seconds !== undefined) pvL.textContent = formatSeconds(stats.launcher_seconds);
    if (pvM && stats.minecraft_seconds !== undefined) pvM.textContent = formatSeconds(stats.minecraft_seconds);
    if (pvLc && stats.launches !== undefined) pvLc.textContent = stats.launches;
}

// ================= СЕРВЕР CUBE VANILLA =================
async function refreshCubeVanilla() {
    const dot = document.getElementById('cvStatusDot');
    const info = document.getElementById('cvPlayersInfo');
    if (dot) dot.className = 'cv-status-dot offline';
    if (info) info.innerHTML = '⏳ Проверка статуса сервера...';
    try {
        const res = await window.pywebview.api.get_cube_vanilla_status();
        if (res && res.status === 'ok') {
            if (res.online) {
                if (dot) dot.className = 'cv-status-dot online';
                if (info) info.innerHTML = `🟢 Онлайн: <b style="color: #22c55e;">${res.players_online}</b> / ${res.players_max} игроков`;
            } else {
                if (dot) dot.className = 'cv-status-dot offline';
                if (info) info.innerHTML = '<span style="color: #ef4444;">🔴 Сервер оффлайн</span>';
            }
        } else {
            if (info) info.innerHTML = '<span style="color: #ef4444;">⚠️ Не удалось проверить</span>';
        }
    } catch (e) {
        if (info) info.innerHTML = '<span style="color: #ef4444;">⚠️ Ошибка соединения</span>';
    }
}

// ================= ПЕРЕКЛЮЧЕНИЕ БАННЕРА =================
function onBannerToggleChange(enabled) {
    globalConfig.show_banner = enabled;
    const widget = document.getElementById('cubeVanillaWidget');
    if (widget) widget.style.display = enabled ? 'flex' : 'none';
    triggerAutoSave();
}

// ================= СЕРВЕРА =================
function onServersTabOpened() {
    const needForce = allServersData.length === 0;
    refreshServersList(needForce, false);
}

async function refreshServersList(forceRefresh = false, showToastFlag = true) {
    const btn = document.getElementById('btnRefreshServers');
    const loadingEl = document.getElementById('serversLoadingIndicator');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ ...'; }
    if (showToastFlag) showToast("🔄 Опрос серверов...", "info");
    if (allServersData.length === 0 && loadingEl) loadingEl.style.display = 'block';
    try {
        const res = await window.pywebview.api.get_servers_with_status(forceRefresh);
        if (res && res.status === 'ok') {
            allServersData = res.servers || [];
            if (loadingEl) loadingEl.style.display = 'none';
            const label = document.getElementById('serversLastUpdateLabel');
            if (label && !res.loading) {
                const now = new Date();
                label.textContent = `Обновлено в ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
            }
            applyServersFilter();
            if (res.loading && loadingEl) loadingEl.style.display = 'block';
        }
    } catch (e) {
        if (loadingEl) loadingEl.style.display = 'none';
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '🔄 Обновить сервера'; }
    }
}

function applyServersFilter() {
    // Автоматически ставим иконку CV на главную страницу:
    const cv = allServersData.find(s => s.id === 'cubevanilla');
    if (cv && cv.status_icon) {
        const homeImg = document.getElementById('cvServerIcon');
        if (homeImg) homeImg.src = cv.status_icon;
    }

    const grid = document.getElementById('serversGrid');
    const emptyEl = document.getElementById('serversEmpty');
    const pagEl = document.getElementById('serversPagination');
    if (!grid) return;
    const query = (document.getElementById('serversSearchInput')?.value || '').toLowerCase().trim();
    const licenseFilter = document.getElementById('serversLicenseFilter')?.value || 'all';
    const regionFilter = document.getElementById('serversRegionFilter')?.value || 'all';
    const statusFilter = document.getElementById('serversStatusFilter')?.value || 'all';

    const filtered = allServersData.filter(s => {
        if (query && !(s.name||'').toLowerCase().includes(query) && !(s.address||'').toLowerCase().includes(query)) return false;
        if (licenseFilter !== 'all' && s.license !== licenseFilter) return false;
        if (regionFilter !== 'all' && s.region !== regionFilter) return false;
        if (selectedServerVersion && !(s.versions_raw || []).some(v => v.startsWith(selectedServerVersion))) return false;
        if (statusFilter === 'online' && !s.online) return false;
        if (statusFilter === 'offline' && s.online) return false;
        return true;
    });

    filtered.sort((a, b) => {
        if (a.online !== b.online) return a.online ? -1 : 1;
        return (b.players_online || 0) - (a.players_online || 0);
    });

    const totalPages = Math.ceil(filtered.length / SERVERS_PER_PAGE) || 1;
    if (currentServerPage > totalPages) currentServerPage = totalPages;
    if (currentServerPage < 1) currentServerPage = 1;
    const startIdx = (currentServerPage - 1) * SERVERS_PER_PAGE;
    const pageItems = filtered.slice(startIdx, startIdx + SERVERS_PER_PAGE);

    grid.innerHTML = '';
    if (pageItems.length === 0) {
        if (emptyEl) emptyEl.style.display = 'block';
        if (pagEl) pagEl.style.display = 'none';
    } else {
        if (emptyEl) emptyEl.style.display = 'none';
        if (pagEl) pagEl.style.display = 'flex';
        pageItems.forEach(srv => grid.appendChild(buildServerCard(srv)));
    }
    const info = document.getElementById('serversPageInfo');
    if (info) info.textContent = `Страница ${currentServerPage} из ${totalPages}`;
    const prevBtn = document.getElementById('serversPrevPage');
    const nextBtn = document.getElementById('serversNextPage');
    if (prevBtn) prevBtn.disabled = currentServerPage <= 1;
    if (nextBtn) nextBtn.disabled = currentServerPage >= totalPages;
}

function changeServersPage(delta) {
    currentServerPage += delta;
    applyServersFilter();
    document.getElementById('serversGrid')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function buildServerCard(srv) {
    const card = document.createElement('div');
    card.className = `server-card ${srv.online ? '' : 'server-card-offline'}`;
    card.onclick = () => openServerDetail(srv.id);
    const iconHtml = srv.status_icon
        ? `<img class="server-icon-img" src="${escapeAttr(srv.status_icon)}" onerror="this.style.display='none'">`
        : `<span class="server-icon-emoji">${srv.icon_emoji || '🌐'}</span>`;
    const lic = srv.license || 'licensed';
    const licLabelMap = {
        licensed: { cls: 'badge-license', txt: 'Лицензия' },
        pirate: { cls: 'badge-nolicense', txt: 'Пиратка' },
        both: { cls: 'badge-both', txt: 'Лиц. + Пиратка' }
    };
    const licInfo = licLabelMap[lic] || licLabelMap.licensed;
    const playersText = srv.online ? `👥 ${srv.players_online}/${srv.players_max}` : '👥 Оффлайн';
    const playersCls = srv.online ? 'badge-players' : 'badge-players offline';
    let motdPreview = (srv.motd || '').split('\n')[0].slice(0, 70);
    const versText = (srv.versions && srv.versions.length) ? srv.versions[0] : '—';
    const desc = (srv.description || '').slice(0, 150);

    card.innerHTML =
        `<div class="server-icon-wrap">${iconHtml}<div class="server-status-dot ${srv.online ? 'online' : 'offline'}"></div></div>` +
        `<div class="server-info">` +
        `<div class="server-title-row"><span class="server-name">${escapeHtml(srv.name)}</span><span class="server-address" onclick="event.stopPropagation(); copyServerAddress('${escapeAttr(srv.address)}', '${escapeAttr(srv.name)}')">${escapeHtml(srv.address)}</span></div>` +
        `<div class="server-badges"><span class="${licInfo.cls}">${licInfo.txt}</span><span class="badge-version">🎮 ${escapeHtml(versText)}</span><span class="${playersCls}">${playersText}</span></div>` +
        (motdPreview ? `<div class="server-motd-preview">${escapeHtml(motdPreview)}</div>` : '') +
        `<div class="server-desc-preview">${escapeHtml(desc)}</div>` +
        `</div>` +
        `<div class="server-side-actions"><button class="btn" style="padding: 7px 14px; font-size: 11px;" onclick="event.stopPropagation(); copyServerAddress('${escapeAttr(srv.address)}', '${escapeAttr(srv.name)}')">📋 IP</button></div>`;
    return card;
}

// ================= КАСТОМНЫЙ ВЫПАДАЮЩИЙ СПИСОК ВЕРСИЙ =================
function toggleVersionDropdown() {
    const list = document.getElementById('customVersionDropdownList');
    if (!list) return;
    if (list.style.display === 'none' || !list.style.display) {
        list.innerHTML = '';
        const allOpt = document.createElement('div');
        allOpt.className = 'version-dropdown-item';
        allOpt.textContent = 'Все версии';
        allOpt.onclick = () => {
            selectedServerVersion = '';
            document.getElementById('selectedVersionText').textContent = 'Все версии';
            list.style.display = 'none';
            currentServerPage = 1;
            applyServersFilter();
        };
        list.appendChild(allOpt);
        const releases = mojangVersionsData.releases || [];
        releases.forEach(v => {
            const opt = document.createElement('div');
            opt.className = 'version-dropdown-item';
            opt.textContent = v.id;
            opt.onclick = () => {
                selectedServerVersion = v.id;
                document.getElementById('selectedVersionText').textContent = v.id;
                list.style.display = 'none';
                currentServerPage = 1;
                applyServersFilter();
            };
            list.appendChild(opt);
        });
        list.style.display = 'block';
    } else {
        list.style.display = 'none';
    }
}

document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('customVersionDropdownList');
    const btn = document.getElementById('customVersionDropdownBtn');
    if (dropdown && dropdown.style.display === 'block' && btn && !btn.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.style.display = 'none';
    }
});

// ================= СТРАНИЦЫ И ТЕМАТИКА =================
function switchPage(pageId, evt) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(pageId).classList.add('active');
    if (evt) evt.currentTarget.classList.add('active');
    if (pageId === 'modpacks') triggerModpackSearch(1);
    if (pageId === 'friends') loadFriendsListAndRequests();
    if (pageId === 'servers') onServersTabOpened();
}

function showModal(id) { const m = document.getElementById(id); if (m) m.classList.add('active'); }
function closeModal(id) {
    const m = document.getElementById(id);
    if (m) m.classList.remove('active');
    if (id === 'instanceViewModal') window.pywebview.api.stop_watching_instance();
}

function applyTheme(theme) { document.body.setAttribute('data-theme', theme); }
function onThemeSelectChange(val) { applyTheme(val); triggerAutoSave(); }
function onLanguageSelectChange(lang) { triggerAutoSave(); showToast(`Язык переключен: ${lang.toUpperCase()}`, "info"); }

function onRamSliderInput(val, autoSave = true) {
    document.getElementById('ramMbLabel').textContent = `${val} МБ (${(val / 1024).toFixed(1)} ГБ)`;
    if (autoSave) triggerAutoSave();
}

function onAnimationsToggleChange(enabled, autoSave = true) {
    const chevron = document.getElementById('animSubmenuChevronBtn');
    const subBox = document.getElementById('animSubmenuContainer');
    if (enabled) {
        if (chevron) chevron.style.display = 'inline-flex';
        onAnimSpeedSliderInput(document.getElementById('settingAnimSpeedSlider').value, false);
    } else {
        if (chevron) chevron.style.display = 'none';
        if (subBox) subBox.style.display = 'none';
        document.documentElement.style.setProperty('--anim-speed', '0s');
    }
    if (autoSave) triggerAutoSave();
}

function toggleAnimSubmenu() {
    isAnimSubmenuOpen = !isAnimSubmenuOpen;
    const subBox = document.getElementById('animSubmenuContainer');
    const chevron = document.getElementById('animSubmenuChevronBtn');
    if (subBox) subBox.style.display = isAnimSubmenuOpen ? 'flex' : 'none';
    if (chevron) chevron.textContent = isAnimSubmenuOpen ? '▲' : '▼';
}

function onAnimSpeedSliderInput(val, autoSave = true) {
    document.getElementById('animSpeedValueLabel').textContent = `${val}x (${Math.round(200/val)}ms)`;
    document.documentElement.style.setProperty('--anim-speed', `${(0.2/val).toFixed(2)}s`);
    if (autoSave) triggerAutoSave();
}

function applyLiquidGlass(variant) {
    if (!LIQUID_GLASS_VARIANTS.includes(variant)) variant = 'off';
    document.body.setAttribute('data-liquid-glass', variant);
}

function onLiquidGlassToggleChange(enabled, autoSave = true) {
    const chevron = document.getElementById('liquidGlassChevronBtn');
    const subBox = document.getElementById('liquidGlassSubmenuContainer');
    const slider = document.getElementById('settingLiquidGlassSlider');
    if (enabled) {
        if (chevron) chevron.style.display = 'inline-flex';
        if (slider && parseInt(slider.value) === 0) slider.value = 2;
        onLiquidGlassSliderInput(slider ? slider.value : 2, false);
    } else {
        if (chevron) chevron.style.display = 'none';
        if (subBox) subBox.style.display = 'none';
        applyLiquidGlass('off');
        if (slider) slider.value = 0;
        updateLiquidGlassBadges(0);
    }
    if (autoSave) triggerAutoSave();
}

function toggleLiquidGlassSubmenu() {
    isLiquidGlassSubmenuOpen = !isLiquidGlassSubmenuOpen;
    const subBox = document.getElementById('liquidGlassSubmenuContainer');
    const chevron = document.getElementById('liquidGlassChevronBtn');
    if (subBox) subBox.style.display = isLiquidGlassSubmenuOpen ? 'flex' : 'none';
    if (chevron) chevron.textContent = isLiquidGlassSubmenuOpen ? '▲' : '▼';
}

function updateLiquidGlassBadges(idx) {
    for (let i = 0; i < 4; i++) {
        const b = document.getElementById('lgBadge' + i);
        if (b) b.classList.toggle('active', i === idx);
    }
}

function onLiquidGlassSliderInput(val, autoSave = true) {
    const idx = Math.max(0, Math.min(3, parseInt(val)));
    applyLiquidGlass(LIQUID_GLASS_VARIANTS[idx]);
    updateLiquidGlassBadges(idx);
    if (autoSave) triggerAutoSave();
}

function onCubeVisualsToggleChange(isChecked) {
    globalConfig.show_cube_visuals = isChecked;
    triggerAutoSave();
    renderInstallations();
    renderActiveInstance();
}

// ================= АККАУНТЫ MINECRAFT И ПРОФИЛЬ CUBE =================
async function deleteMinecraftAccount(username) {
    const confirmed = confirm(`Удалить аккаунт "${username}" из списка лаунчера?`);
    if (!confirmed) return;
    try {
        await window.pywebview.api.delete_account(username);
        showToast(`Аккаунт ${username} удалён`, "info");
        await refreshData();
    } catch (e) {
        showToast("Ошибка удаления", "error");
    }
}

function openDeleteAccountModal(username) {
    targetAccountToDelete = username;
    document.getElementById('delAccTargetNameDisplay').textContent = username;
    document.getElementById('delAccStep1Check').checked = false;
    document.getElementById('delAccStep2Box').style.display = 'none';
    document.getElementById('delAccConfirmInput').value = '';
    document.getElementById('btnConfirmDeleteAccount').disabled = true;
    showModal('deleteAccountModal');
    playUiSound('error');
}

function onDeleteAccountStep1Change(isChecked) {
    const step2Box = document.getElementById('delAccStep2Box');
    step2Box.style.display = isChecked ? 'flex' : 'none';
    if (isChecked) document.getElementById('delAccConfirmInput').focus();
}

function onDeleteAccountInputChange() {
    const val = document.getElementById('delAccConfirmInput').value.trim();
    const btn = document.getElementById('btnConfirmDeleteAccount');
    btn.disabled = !(targetAccountToDelete && val.toLowerCase() === targetAccountToDelete.toLowerCase());
}

async function executeDeleteAccount() {
    if (!targetAccountToDelete) return;
    const u = targetAccountToDelete;
    closeModal('deleteAccountModal');
    closeModal('profileModal');
    showToast("Удаление профиля...", "info");
    await window.pywebview.api.delete_account_completely(u);
    targetAccountToDelete = null;
}

function showAddCubeAccountForm() {
    document.getElementById('cubeLoggedView').style.display = 'none';
    document.getElementById('cubeAccountsSwitchList').style.display = 'none';
    document.getElementById('cubeNotLoggedView').style.display = 'flex';
    refreshCaptcha();
}

function setCubeAuthMode(mode) {
    cubeAuthMode = mode;
    document.getElementById('cubeModeLoginBtn').className = `btn ${mode === 'login' ? '' : 'btn-secondary'}`;
    document.getElementById('cubeModeRegBtn').className = `btn ${mode === 'register' ? '' : 'btn-secondary'}`;
    document.getElementById('groupCubeEmail').style.display = mode === 'register' ? 'flex' : 'none';
    document.getElementById('groupCubePassRepeat').style.display = mode === 'register' ? 'flex' : 'none';
    document.getElementById('cubeSubmitBtn').textContent = mode === 'register' ? 'Зарегистрироваться' : 'Войти в аккаунт';
}

function togglePassVisibility(inputId, btn) {
    const el = document.getElementById(inputId);
    if (el.type === 'password') { el.type = 'text'; btn.textContent = '🔒'; }
    else { el.type = 'password'; btn.textContent = '👁️'; }
}

async function refreshCaptcha() {
    const res = await window.pywebview.api.generate_captcha();
    document.getElementById('captchaQuestionText').textContent = res.question;
    document.getElementById('cubeCaptchaInput').value = '';
}

async function submitCubeAuth() {
    const loginVal = document.getElementById('cubeInputLogin').value;
    const passVal = document.getElementById('cubeInputPassword').value;
    const captchaVal = document.getElementById('cubeCaptchaInput').value;
    if (cubeAuthMode === 'login') {
        showToast("Проверка данных...", "info");
        const res = await window.pywebview.api.send_login_code(loginVal, passVal, captchaVal);
        if (res.status === 'ok') {
            pendingAuthType = 'login';
            pendingAuthData = { login: loginVal, password: passVal };
            document.getElementById('otpTargetEmailText').textContent = res.email;
            document.getElementById('cubeOtpCodeInput').value = '';
            document.getElementById('cubeNotLoggedView').style.display = 'none';
            document.getElementById('cubeOtpVerificationView').style.display = 'flex';
            startOtpCooldown(res.cooldown || 60);
        } else {
            showToast(res.message, "error");
            refreshCaptcha();
        }
    } else {
        const emailVal = document.getElementById('cubeInputEmail').value;
        const passRepeat = document.getElementById('cubeInputPasswordRepeat').value;
        if (passVal !== passRepeat) {
            showToast("Пароли не совпадают!", "error");
            return;
        }
        showToast("Отправка кода...", "info");
        const res = await window.pywebview.api.send_registration_code(loginVal, emailVal, passVal, captchaVal);
        if (res.status === 'ok') {
            pendingAuthType = 'register';
            pendingAuthData = { username: loginVal, email: emailVal, password: passVal };
            document.getElementById('otpTargetEmailText').textContent = emailVal;
            document.getElementById('cubeOtpCodeInput').value = '';
            document.getElementById('cubeNotLoggedView').style.display = 'none';
            document.getElementById('cubeOtpVerificationView').style.display = 'flex';
            startOtpCooldown(res.cooldown || 60);
        } else {
            showToast(res.message, "error");
            refreshCaptcha();
        }
    }
}

function startOtpCooldown(sec) {
    clearInterval(otpCooldownTimer);
    const btn = document.getElementById('btnResendOtp');
    btn.disabled = true;
    let rem = sec;
    btn.textContent = `Повтор (${rem}s)`;
    otpCooldownTimer = setInterval(() => {
        rem--;
        if (rem <= 0) {
            clearInterval(otpCooldownTimer);
            btn.disabled = false;
            btn.textContent = 'Отправить заново';
        } else {
            btn.textContent = `Повтор (${rem}s)`;
        }
    }, 1000);
}

async function resendOtpCode() {
    if (!pendingAuthData) return;
    showToast("Отправка нового кода...", "info");
    let res;
    if (pendingAuthType === 'login') {
        res = await window.pywebview.api.send_login_code(pendingAuthData.login, pendingAuthData.password, "0");
    } else {
        res = await window.pywebview.api.send_registration_code(pendingAuthData.username, pendingAuthData.email, pendingAuthData.password, "0");
    }
    if (res.status === 'ok') startOtpCooldown(res.cooldown || 60);
    else showToast(res.message, "error");
}

function backToAuthForm() {
    document.getElementById('cubeOtpVerificationView').style.display = 'none';
    document.getElementById('cubeNotLoggedView').style.display = 'flex';
    refreshCaptcha();
}

async function confirmOtpAction() {
    if (!pendingAuthData) return;
    const code = document.getElementById('cubeOtpCodeInput').value;
    if (!code || code.trim().length !== 6) {
        showToast("Введите 6-значный код!", "error");
        return;
    }
    showToast("Проверка кода...", "info");
    let res;
    if (pendingAuthType === 'login') {
        res = await window.pywebview.api.verify_and_login(pendingAuthData.login, pendingAuthData.password, code);
    } else {
        res = await window.pywebview.api.verify_and_register(pendingAuthData.username, pendingAuthData.email, pendingAuthData.password, code);
    }
    if (res.status === 'ok') {
        pendingAuthData = null;
        await refreshData();
        await refreshMainProfileUI();
    } else {
        showToast(res.message, "error");
    }
}

async function changeCubeAvatar() {
    const res = await window.pywebview.api.select_cube_avatar();
    if (res?.status === 'ok') await refreshMainProfileUI();
}

async function logoutCube() {
    try {
        await window.pywebview.api.logout_cube_account();
        await refreshData();
        await refreshMainProfileUI();
        await refreshCaptcha();
    } catch (e) {
        showToast('Ошибка выхода', 'error');
    }
}

async function saveCubeBio() {
    const bio = document.getElementById('cubeBioText').value;
    await window.pywebview.api.update_cube_bio(bio);
}

async function openProfileModal() {
    await refreshMainProfileUI();
    await refreshCaptcha();
    showModal('profileModal');
}

async function openProfileViewModal(uid, fallbackName) {
    try {
        const res = await window.pywebview.api.get_public_profile_with_stats(uid);
        if (!res || res.status !== 'ok') {
            showToast('Не удалось открыть профиль', 'error');
            return;
        }
        const p = res.profile;
        document.getElementById('pvAvatar').src = p.avatar || `https://minotar.net/helm/${fallbackName}/100.png`;
        document.getElementById('pvUsername').textContent = p.username || fallbackName || 'Player';
        document.getElementById('pvStatus').innerHTML = p.is_online
            ? `<span style="color: #22c55e; font-weight: 800;">● В сети</span>`
            : `<span style="color: var(--text-secondary); font-weight: 700;">● Не в сети</span>`;
        const actWrap = document.getElementById('pvActivityWrap');
        if (p.is_playing) {
            document.getElementById('pvActivity').textContent = `🎮 ${p.activity_title || 'Minecraft'}`;
            actWrap.style.display = 'block';
        } else {
            actWrap.style.display = 'none';
        }
        document.getElementById('pvStatLauncherHours').textContent = formatSeconds(p.stat_launcher_seconds || 0);
        document.getElementById('pvStatMinecraftHours').textContent = formatSeconds(p.stat_minecraft_seconds || 0);
        document.getElementById('pvStatLaunches').textContent = p.stat_launches || 0;
        document.getElementById('pvBio').textContent = p.bio || 'Игрок Cube Launcher';
        document.getElementById('pvWriteMsgBtn').onclick = () => {
            closeModal('profileViewModal');
            const navBtns = document.querySelectorAll('.nav-btn');
            let friendsBtn = null;
            navBtns.forEach(b => { if (b.textContent.includes('Друз')) friendsBtn = b; });
            if (friendsBtn) {
                friendsBtn.click();
                setTimeout(() => openChatMessenger(uid, p.username || fallbackName), 250);
            }
        };
        showModal('profileViewModal');
    } catch (e) {
        showToast('Ошибка загрузки профиля', 'error');
    }
}

// ================= МОДПАКИ =================
function onModpackSearchInput() {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => triggerModpackSearch(1), 260);
}

async function triggerModpackSearch(page = 1) {
    modpackPage = page;
    const grid = document.getElementById('modpacksGrid');
    grid.innerHTML = '<div style="grid-column: 1/-1; padding: 24px; text-align: center; color: var(--text-secondary);">⏳ Загрузка каталога модпаков...</div>';
    const query = document.getElementById('modpackSearchInput').value;
    const platform = document.getElementById('modpackCatalogPlatform').value || 'modrinth';
    const loader = document.getElementById('modpackLoaderFilter').value;
    const ver = document.getElementById('modpackVersionFilter').value;
    const res = await window.pywebview.api.fetch_resources(query, "modpacks", loader, ver, modpackPage, 10, platform);
    modpackTotalPages = res.total_pages || 1;
    renderModpackItems(res.items, platform);
    document.getElementById('modpackPageInfo').textContent = `Страница ${modpackPage} из ${modpackTotalPages}`;
    document.getElementById('modpackPrevPage').disabled = modpackPage <= 1;
    document.getElementById('modpackNextPage').disabled = modpackPage >= modpackTotalPages;
}

function changeModpackPage(delta) {
    const p = modpackPage + delta;
    if (p >= 1 && p <= modpackTotalPages) triggerModpackSearch(p);
}

function renderModpackItems(items, platform = "modrinth") {
    const grid = document.getElementById('modpacksGrid');
    grid.innerHTML = (items || []).length === 0
        ? `<div style="grid-column: 1/-1; padding: 24px; text-align: center; color: var(--text-secondary);">Модпаки не найдены</div>`
        : '';
    (items || []).forEach(item => {
        const card = document.createElement('div');
        card.className = 'card';
        card.style.cssText = "display: flex; flex-direction: row; gap: 14px; align-items: center; border-radius: var(--radius-lg); padding: 14px 16px;";
        const safeTitle = escapeAttr(item.title);
        const safeIcon = escapeAttr(item.icon || '');
        card.innerHTML =
            `<img src="${safeIcon || 'https://cdn-icons-png.flaticon.com/512/3344/3344384.png'}" style="width: 58px; height: 58px; border-radius: var(--radius-md); object-fit: cover; background: #1a1618; border: 1px solid var(--border); flex-shrink: 0;" onerror="this.src='https://cdn-icons-png.flaticon.com/512/3344/3344384.png'">` +
            `<div style="flex: 1; display: flex; flex-direction: column; gap: 3px; overflow: hidden;">` +
            `<div style="display: flex; align-items: center; gap: 8px;"><span style="font-weight: 800; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(item.title)}</span><span class="badge-type badge-mr">Modpack</span></div>` +
            `<div style="font-size: 11px; color: var(--text-secondary);">Автор: ${escapeHtml(item.author)} • ⬇ ${(item.downloads || 0).toLocaleString()}</div>` +
            `<div style="font-size: 11px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(item.desc)}</div>` +
            `</div>` +
            `<button class="btn" style="padding: 8px 14px; font-size: 11px;" onclick="window.pywebview.api.install_modpack_as_instance('${escapeAttr(item.id)}', '${safeTitle}', '${safeIcon}', '${escapeAttr(platform)}')">⬇ Установить</button>`;
        grid.appendChild(card);
    });
}

// ================= КАТАЛОГ ДОПОЛНЕНИЙ В СБОРКУ =================
function openAddModsModal() {
    showModal('addModsModal');
    if (currentViewingInstId) document.getElementById('modTargetInstance').value = currentViewingInstId;
    triggerAutoSearch(1);
}

function onTargetInstanceChange() { triggerAutoSearch(1); }

function onModSearchInput() {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => triggerAutoSearch(1), 260);
}

async function triggerAutoSearch(page = 1) {
    modCatalogPage = page;
    const grid = document.getElementById('catalogGrid');
    grid.innerHTML = '<div style="grid-column: 1/-1; padding: 24px; text-align: center; color: var(--text-secondary);">⏳ Загрузка дополнений...</div>';
    const query = document.getElementById('modSearchInput').value;
    const platform = document.getElementById('modCatalogPlatform').value || 'modrinth';
    const resType = document.getElementById('modTypeSelect').value;
    const loader = document.getElementById('modLoaderFilter').value;
    const ver = document.getElementById('modVersionFilter').value;
    const targetInstId = document.getElementById('modTargetInstance').value || globalConfig.active_instance_id;
    cachedInstalledFiles = await window.pywebview.api.get_instance_files(targetInstId, resType);
    const res = await window.pywebview.api.fetch_resources(query, resType, loader, ver, modCatalogPage, 10, platform);
    modCatalogTotalPages = res.total_pages || 1;
    currentRawCatalogItems = res.items || [];
    renderCurrentCatalogPage();
    document.getElementById('modPageInfo').textContent = `Страница ${modCatalogPage} из ${modCatalogTotalPages}`;
    document.getElementById('modPrevPage').disabled = modCatalogPage <= 1;
    document.getElementById('modNextPage').disabled = modCatalogPage >= modCatalogTotalPages;
}

function renderCurrentCatalogPage() {
    const grid = document.getElementById('catalogGrid');
    if (!grid) return;
    const installedCleanNames = new Set(cachedInstalledFiles.map(f => (f.clean_name || '').toLowerCase().replace(/[^a-z0-9]/g, '')));
    const itemsToRender = currentRawCatalogItems || [];
    grid.innerHTML = itemsToRender.length === 0 ? `<div style="grid-column: 1/-1; padding: 24px; text-align: center; color: var(--text-secondary);">Ничего не найдено</div>` : '';
    itemsToRender.forEach(item => {
        const card = document.createElement('div');
        card.className = 'card';
        card.style.cssText = "display: flex; flex-direction: row; gap: 14px; align-items: center; border-radius: var(--radius-lg); padding: 12px 14px;";
        const isCf = item.platform === 'curseforge';
        const platBadge = isCf ? '<span class="badge-type badge-cf">CurseForge</span>' : '<span class="badge-type badge-mr">Modrinth</span>';
        const fallbackImg = isCf ? 'https://media.forgecdn.net/avatars/thumbnails/282/467/256/256/637289313020452406.png' : 'https://cdn-icons-png.flaticon.com/512/3344/3344384.png';
        const isInstalled = installedCleanNames.has((item.title || '').toLowerCase().replace(/[^a-z0-9]/g, ''));
        let actionBtnHtml = `<button class="btn" style="padding: 7px 12px; font-size: 11px;" onclick="smartInstallResource('${escapeAttr(item.id)}', '${escapeAttr(item.platform)}')">⬇ Установить</button>`;
        if (isInstalled) actionBtnHtml = `<button class="btn btn-installed" style="padding: 7px 12px; font-size: 11px;">✓ Установлен</button>`;
        card.innerHTML =
            `<img src="${escapeAttr(item.icon || fallbackImg)}" style="width: 52px; height: 52px; border-radius: var(--radius-md); object-fit: cover; background: #1a1618; border: 1px solid var(--border); flex-shrink: 0;" onerror="this.src='${fallbackImg}'">` +
            `<div style="flex: 1; display: flex; flex-direction: column; gap: 2px; overflow: hidden;">` +
            `<div style="display: flex; align-items: center; gap: 8px;"><span style="font-weight: 800; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(item.title)}</span>${platBadge}</div>` +
            `<div style="font-size: 11px; color: var(--text-secondary);">Автор: ${escapeHtml(item.author)} • ⬇ ${(item.downloads || 0).toLocaleString()}</div>` +
            `<div style="font-size: 11px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(item.desc)}</div>` +
            `</div>` +
            `<div style="display: flex; flex-direction: column; gap: 6px; flex-shrink: 0;">${actionBtnHtml}<button class="btn btn-secondary" style="padding: 6px 10px; font-size: 11px;" onclick="openResourceDetails('${escapeAttr(item.id)}', '${escapeAttr(item.platform)}')">Файлы</button></div>`;
        grid.appendChild(card);
    });
}

function changeModPage(delta) {
    const p = modCatalogPage + delta;
    if (p >= 1 && p <= modCatalogTotalPages) triggerAutoSearch(p);
}

async function smartInstallResource(projectId, platform) {
    const instId = document.getElementById('modTargetInstance').value || globalConfig.active_instance_id;
    const rType = document.getElementById('modTypeSelect').value || 'mods';
    showToast("Подбор совместимого файла...", "info");
    const res = await window.pywebview.api.auto_install_resource(projectId, platform, instId, rType);
    if (res.status === 'not_found' || res.status === 'error') showToast(res.message || "Не найдено", "error");
}

async function openResourceDetails(projectId, platform = "modrinth") {
    const details = await window.pywebview.api.get_resource_details(projectId, platform);
    if (details.status !== 'ok') return showToast('Ошибка получения данных', 'error');
    const p = details.project;
    document.getElementById('detailIcon').src = p.icon || 'https://cdn-icons-png.flaticon.com/512/3344/3344384.png';
    document.getElementById('detailTitle').textContent = p.title;
    document.getElementById('detailMeta').textContent = `ID: ${p.id} • ${platform.toUpperCase()}`;
    const gal = document.getElementById('detailGallery');
    gal.innerHTML = '';
    currentLightboxGallery = p.gallery || [];
    currentLightboxGallery.forEach((img, idx) => {
        const i = document.createElement('img');
        i.style.cssText = "height: 110px; border-radius: var(--radius-md); object-fit: cover; border: 1px solid var(--border); cursor: pointer;";
        i.src = img;
        i.onclick = () => openLightbox(idx);
        gal.appendChild(i);
    });
    cachedDetailVersions = details.versions || [];
    document.getElementById('detailReleaseFilter').value = '';
    renderDetailVersions();
    showModal('modDetailsModal');
}

function filterDetailVersions() { renderDetailVersions(); }

async function renderDetailVersions() {
    const vList = document.getElementById('detailVersionsList');
    vList.innerHTML = '';
    const relFilter = document.getElementById('detailReleaseFilter').value;
    (cachedDetailVersions || []).forEach(v => {
        const vType = v.version_type || 'release';
        if (relFilter && vType !== relFilter) return;
        const f = (v.files || []).find(fl => fl.primary) || (v.files ? v.files[0] : null);
        if (!f) return;
        const row = document.createElement('div');
        row.style.cssText = 'background: var(--bg-main); padding: 9px 14px; border-radius: var(--radius-md); border: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; font-size: 12px; gap: 10px;';
        row.innerHTML =
            `<div style="overflow: hidden; flex: 1;"><div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">` +
            `<strong style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(v.name)}</strong>` +
            `<span class="badge-type ${getReleaseBadgeClass(vType)}" style="font-size: 9px; padding: 2px 6px;">${formatReleaseType(vType)}</span></div>` +
            `<div style="font-size: 10px; color: var(--text-secondary);">MC: ${(v.game_versions || []).slice(0,4).join(', ')}</div></div>` +
            `<button class="btn" style="padding: 5px 12px; font-size: 11px;" onclick="installFile('${escapeAttr(f.url)}', '${escapeAttr(f.filename)}')">Скачать</button>`;
        vList.appendChild(row);
    });
    if (vList.children.length === 0) vList.innerHTML = '<div style="padding: 14px; text-align: center; color: var(--text-secondary); font-size: 12px;">Версий не найдено</div>';
}

function installFile(url, filename) {
    const instId = document.getElementById('modTargetInstance').value || globalConfig.active_instance_id;
    const rType = document.getElementById('modTypeSelect').value || 'mods';
    window.pywebview.api.install_resource(instId, url, filename, rType);
}

// ================= ОФФЛАЙН И MICROSOFT =================
async function selectAccount(u) {
    await window.pywebview.api.select_account(u);
    await refreshData();
}

async function addOfflineAccount() {
    const u = document.getElementById('accInput').value;
    if (!u.trim()) { showToast("Введите никнейм!", "error"); return; }
    const res = await window.pywebview.api.add_account(u);
    if (res.status === 'ok') {
        document.getElementById('accInput').value = '';
        await refreshData();
        showToast("Аккаунт добавлен!", "success");
    } else if (res.message) {
        showToast(res.message, "error");
    }
}

async function startMicrosoftAuth() {
    showToast("Открытие окна Microsoft...", "info");
    await window.pywebview.api.start_microsoft_login();
}

// ================= ЛАЙТБОКС =================
function openLightbox(index) {
    if (!currentLightboxGallery || currentLightboxGallery.length === 0) return;
    currentLightboxIndex = index;
    updateLightboxView();
    document.getElementById('galleryLightbox').classList.add('active');
}
function closeLightbox() { document.getElementById('galleryLightbox').classList.remove('active'); }
function changeLightboxImg(delta) {
    if (!currentLightboxGallery || currentLightboxGallery.length === 0) return;
    currentLightboxIndex = (currentLightboxIndex + delta + currentLightboxGallery.length) % currentLightboxGallery.length;
    updateLightboxView();
}
function updateLightboxView() {
    document.getElementById('lightboxMainImg').src = currentLightboxGallery[currentLightboxIndex];
    document.getElementById('lightboxCounter').textContent = `${currentLightboxIndex + 1} / ${currentLightboxGallery.length}`;
}
document.addEventListener('keydown', (e) => {
    if (document.getElementById('galleryLightbox').classList.contains('active')) {
        if (e.key === 'Escape') closeLightbox();
        if (e.key === 'ArrowLeft') changeLightboxImg(-1);
        if (e.key === 'ArrowRight') changeLightboxImg(1);
    }
    if (document.getElementById('crashModal').classList.contains('active') && e.key === 'Escape') closeCrashModal();
    if (document.getElementById('serverDetailModal').classList.contains('active') && e.key === 'Escape') closeModal('serverDetailModal');
});

// ================= КРАШ-ОТЧЕТЫ =================
function showCrashModal(payloadJson) {
    try {
        let payload = typeof payloadJson === 'string' ? JSON.parse(payloadJson) : payloadJson;
        currentCrashInfo = payload;
        document.getElementById('crashCodeValue').textContent = payload.code || 'CL-0000-0000';
        document.getElementById('crashDescriptionValue').textContent = payload.description || 'Неизвестная ошибка';
        document.getElementById('crashInstanceSubtitle').textContent = `${payload.instance_name || 'Minecraft'} • MC ${payload.mc_version || '?'}`;
        playUiSound('crash');
        showModal('crashModal');
    } catch (e) {
        showToast('Minecraft закрылся с ошибкой', "error");
    }
}
function closeCrashModal() { closeModal('crashModal'); currentCrashInfo = null; }
function copyCrashCode() {
    if (!currentCrashInfo || !currentCrashInfo.code) return;
    try {
        navigator.clipboard.writeText(currentCrashInfo.code);
        showToast("Код скопирован!", "success");
    } catch (e) {
        showToast(currentCrashInfo.code, "info");
    }
}
function openLastLog() { if (currentCrashInfo?.instance_id) window.pywebview.api.open_last_log_file(currentCrashInfo.instance_id); }
function openLogsFolder() { if (currentCrashInfo?.logs_dir) window.pywebview.api.open_crash_folder(currentCrashInfo.logs_dir); }
function openCrashFolder() { if (currentCrashInfo?.crash_dir) window.pywebview.api.open_crash_folder(currentCrashInfo.crash_dir); }
function openLastCrash() { if (currentCrashInfo?.instance_id) window.pywebview.api.open_last_crash_file(currentCrashInfo.instance_id); }

// ================= СБОРКИ =================
async function loadMojangVersions() {
    mojangVersionsData = await window.pywebview.api.get_all_mojang_versions();
    filterVersionList();
}

function filterVersionList() {
    const vType = document.getElementById('modalVersionTypeSelect').value;
    const sel = document.getElementById('modalMcVer');
    sel.innerHTML = '';
    let list = [];
    if (vType === 'release') list = mojangVersionsData.releases || [];
    else if (vType === 'snapshot') list = mojangVersionsData.snapshots || [];
    else if (vType === 'old_beta') list = mojangVersionsData.old_beta || [];
    else if (vType === 'old_alpha') list = mojangVersionsData.old_alpha || [];
    else list = (mojangVersionsData.all || []).map(v => ({ id: v, type: 'version' }));
    list.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.id;
        opt.textContent = `${v.id} (${v.type})`;
        sel.appendChild(opt);
    });
    const modpackVerSel = document.getElementById('modpackVersionFilter');
    const modVerSel = document.getElementById('modVersionFilter');
    if (modpackVerSel && modpackVerSel.children.length <= 1) {
        (mojangVersionsData.releases || []).slice(0, 35).forEach(v => {
            const opt = document.createElement('option');
            opt.value = v.id;
            opt.textContent = v.id;
            modpackVerSel.appendChild(opt);
            if (modVerSel) modVerSel.appendChild(opt.cloneNode(true));
        });
    }
    onMcVerChange();
}

async function onMcVerChange() {
    const mcVer = document.getElementById('modalMcVer').value;
    const loader = document.getElementById('modalLoader').value;
    const box = document.getElementById('optifineSupportBox');
    const txt = document.getElementById('optifineStatusText');
    if (loader === 'vanilla' && mcVer) {
        box.style.display = 'block';
        txt.textContent = "⏳ Проверка OptiFine...";
        const res = await window.pywebview.api.check_optifine_support(mcVer);
        txt.textContent = res.message;
        txt.style.color = res.supported ? "#22c55e" : "#ef4444";
    } else {
        box.style.display = 'none';
    }
    onLoaderChange(false);
}

async function onLoaderChange(triggerCheck = true) {
    const loader = document.getElementById('modalLoader').value;
    const mcVer = document.getElementById('modalMcVer').value;
    const loaderSelect = document.getElementById('modalLoaderVer');
    loaderSelect.innerHTML = `<option value="latest">Последняя (Latest)</option>`;
    if (triggerCheck) await onMcVerChange();
    if (loader !== 'vanilla' && mcVer) {
        const versions = await window.pywebview.api.get_loader_versions(loader, mcVer);
        versions.forEach(fv => {
            const opt = document.createElement('option');
            opt.value = fv;
            opt.textContent = fv;
            loaderSelect.appendChild(opt);
        });
    }
}

async function chooseCustomIcon() {
    const res = await window.pywebview.api.select_instance_custom_icon();
    if (res?.status === 'ok') {
        document.getElementById('modalInstCustomIcon').value = res.icon_b64;
        updateIconPreview(res.icon_b64, "");
    }
}

function resetIcon() {
    document.getElementById('modalInstCustomIcon').value = "none";
    document.getElementById('modalInstIcon').value = "";
    updateIconPreview("none", "");
}

function updateIconPreview(customIcon, emoji = "🟧") {
    const p = document.getElementById('instIconPreview');
    if (customIcon && customIcon !== "none") {
        p.innerHTML = `<img src="${escapeAttr(customIcon)}" style="width: 100%; height: 100%; object-fit: cover; border-radius: var(--radius-md);">`;
    } else if (customIcon === "none" || (!emoji && !customIcon)) {
        p.innerHTML = `<span style="font-size: 16px; color: var(--text-secondary);">∅</span>`;
    } else {
        p.innerHTML = emoji || "🟧";
    }
}

function setupDragAndDrop() {
    const overlay = document.getElementById('instDropOverlay');
    if (!overlay) return;
    window.addEventListener('dragover', (e) => {
        e.preventDefault();
        if (document.getElementById('instanceViewModal').classList.contains('active')) overlay.classList.add('drag-over');
    });
    window.addEventListener('dragleave', (e) => {
        if (!e.relatedTarget || e.relatedTarget.nodeName === 'HTML') overlay.classList.remove('drag-over');
    });
    window.addEventListener('drop', async (e) => {
        e.preventDefault();
        overlay.classList.remove('drag-over');
        if (!currentViewingInstId) return;
        if (!document.getElementById('instanceViewModal').classList.contains('active')) return;
        const files = e.dataTransfer.files;
        if (!files || files.length === 0) return;
        showToast(`Импорт ${files.length} файл(ов)...`, "info");
        for (const file of files) {
            if (file.name.endsWith('.jar') || file.name.endsWith('.zip')) {
                const reader = new FileReader();
                reader.onload = async () => {
                    const b64 = reader.result.split(',')[1];
                    await window.pywebview.api.save_dropped_file_data(currentViewingInstId, currentResourceTab, file.name, b64);
                    await refreshModalInstanceFiles();
                };
                reader.readAsDataURL(file);
            }
        }
        showToast("Файлы перенесены!", "success");
    });
}

async function checkMsServerStatus() {
    try {
        const res = await window.pywebview.api.check_microsoft_status();
        const banner = document.getElementById('globalMsBanner');
        if (banner) banner.style.display = (res && res.connected === false) ? 'flex' : 'none';
    } catch (e) {}
}

function onDeleteCubeVisualsAttempt() {
    playUiSound('error');
    showToast("Сборку CubeVisuals нельзя удалить (снимите галочку в настройках).", "error");
}

function renderActiveInstance() {
    const insts = globalConfig.instances || [];
    let active = insts.find(i => i.id === globalConfig.active_instance_id) || insts[0];
    if (active && active.id === 'CubeVisuals' && globalConfig.show_cube_visuals === false) {
        active = insts.find(i => i.id !== 'CubeVisuals') || active;
    }
    if (active) {
        const iconDisplay = active.custom_icon
            ? `<img src="${escapeAttr(active.custom_icon)}" style="width: 22px; height: 22px; border-radius: var(--radius-sm); object-fit: cover; vertical-align: middle; margin-right: 6px;">`
            : (active.icon ? `${active.icon} ` : '');
        document.getElementById('activeInstTitle').innerHTML = `${iconDisplay}${escapeHtml(active.name)} (${escapeHtml(active.mc_version)})`;
    }
}

function renderInstallations() {
    const grid = document.getElementById('installationsGrid');
    if (!grid) return;
    grid.innerHTML = '';
    let insts = globalConfig.instances || [];
    if (globalConfig.show_cube_visuals === false) insts = insts.filter(i => i.id !== 'CubeVisuals');
    insts.forEach(inst => {
        const card = document.createElement('div');
        card.className = `inst-card ${inst.id === globalConfig.active_instance_id ? 'active' : ''}`;
        card.onclick = () => openInstanceMenu(inst.id);
        const isRunning = gameState === 'running' && activeRunningId === inst.id;
        const isBusy = (gameState === 'launching' || gameState === 'installing') && activeRunningId === inst.id;
        let btnText = '▶ Играть', btnClass = 'btn', btnAction = `launchInstanceDirect('${escapeAttr(inst.id)}')`;
        if (isRunning) {
            btnText = '⏹ Стоп';
            btnClass = 'btn btn-danger';
            btnAction = 'window.pywebview.api.kill_game()';
        } else if (isBusy) {
            btnText = '⏳ Запуск...';
            btnClass = 'btn';
            btnAction = '';
        }
        let iconHtml = `<div class="inst-card-icon-preview">${inst.icon || '🟧'}</div>`;
        if (inst.custom_icon) iconHtml = `<img src="${escapeAttr(inst.custom_icon)}" class="inst-card-icon-preview">`;
        card.innerHTML =
            `<div class="inst-card-info">${iconHtml}` +
            `<div class="inst-card-texts"><div class="inst-card-title">${escapeHtml(inst.name)}</div>` +
            `<div class="inst-card-sub">${escapeHtml(inst.mc_version)} • ${escapeHtml((inst.loader||'vanilla').toUpperCase())}</div></div></div>` +
            `<button class="${btnClass}" ${isBusy ? 'disabled' : ''} onclick="event.stopPropagation(); ${btnAction}">${btnText}</button>`;
        grid.appendChild(card);
    });
}

async function launchInstanceDirect(instId) {
    await window.pywebview.api.select_instance(instId);
    await refreshData();
    playUiSound('launch');
    window.pywebview.api.launch_active_game(instId);
}

function renderAccounts(accounts) {
    const list = document.getElementById('accountsList');
    if (!list) return;
    list.innerHTML = '';
    (accounts || []).forEach(acc => {
        const isMs = acc.type === 'microsoft';
        const item = document.createElement('div');
        item.className = `card ${acc.active ? 'active' : ''}`;
        item.style.cssText = "display: flex; flex-direction: row; align-items: center; justify-content: space-between; padding: 14px 18px; border-radius: var(--radius-lg);";
        const safeUser = escapeAttr(acc.username);
        item.innerHTML =
            `<div style="display: flex; align-items: center; gap: 12px;"><span style="font-size: 24px;">${isMs ? '🔷' : '👤'}</span>` +
            `<div><div style="font-weight: 800; display: flex; align-items: center; gap: 8px; ${acc.active ? 'color: var(--accent);' : ''}">${escapeHtml(acc.username)}` +
            `<span class="badge-type ${isMs ? 'badge-ms' : 'badge-offline'}">${isMs ? 'Microsoft' : 'Оффлайн'}</span>` +
            `${acc.active ? '<span style="color: var(--accent); font-size: 12px;">★ Активен</span>' : ''}</div></div></div>` +
            `<div style="display: flex; gap: 8px;">${!acc.active ? `<button class="btn" style="padding: 6px 14px; font-size: 12px;" onclick="selectAccount('${safeUser}')">Выбрать</button>` : ''}` +
            `<button class="btn btn-danger" style="padding: 6px 14px; font-size: 12px;" onclick="deleteMinecraftAccount('${safeUser}')">Удалить</button></div>`;
        list.appendChild(item);
    });
}

function populateTargetInstancesSelect() {
    const select = document.getElementById('modTargetInstance');
    if (!select) return;
    select.innerHTML = '';
    (globalConfig.instances || []).forEach(inst => {
        const opt = document.createElement('option');
        opt.value = inst.id;
        opt.textContent = `${inst.name} (${inst.mc_version})`;
        select.appendChild(opt);
    });
}

function openCreateModal(isEdit = false, instId = null) {
    const titleEl = document.getElementById('modalInstTitle');
    document.getElementById('optifineInstallCheck').checked = false;
    if (isEdit && instId) {
        const inst = globalConfig.instances.find(i => i.id === instId);
        if (!inst) return;
        document.getElementById('modalInstId').value = inst.id;
        document.getElementById('modalInstName').value = inst.name;
        document.getElementById('modalInstIcon').value = inst.icon || '';
        document.getElementById('modalInstCustomIcon').value = inst.custom_icon || '';
        document.getElementById('modalMcVer').value = inst.mc_version;
        document.getElementById('modalLoader').value = inst.loader;
        titleEl.textContent = 'Изменить сборку';
        updateIconPreview(inst.custom_icon, inst.icon);
    } else {
        document.getElementById('modalInstId').value = '';
        document.getElementById('modalInstName').value = `Minecraft ${mojangVersionsData.latest_release || '1.21.11'}`;
        document.getElementById('modalInstIcon').value = '🟧';
        document.getElementById('modalInstCustomIcon').value = '';
        document.getElementById('modalLoader').value = 'vanilla';
        titleEl.textContent = 'Создать установку';
        updateIconPreview('', '🟧');
    }
    showModal('createModal');
    onMcVerChange();
}

async function saveModalInstance() {
    const id = document.getElementById('modalInstId').value;
    const name = document.getElementById('modalInstName').value || 'Моя сборка';
    const icon = document.getElementById('modalInstIcon').value || '🟧';
    const customIcon = document.getElementById('modalInstCustomIcon').value;
    const mcVer = document.getElementById('modalMcVer').value;
    const loader = document.getElementById('modalLoader').value;
    const loaderVer = document.getElementById('modalLoaderVer').value;
    const optifineInstall = document.getElementById('optifineInstallCheck').checked;
    await window.pywebview.api.save_instance({
        id: id || undefined, name,
        icon: customIcon === 'none' ? '' : icon,
        custom_icon: customIcon === 'none' ? '' : customIcon,
        mc_version: mcVer, loader, loader_version: loaderVer, optifine_install: optifineInstall
    });
    closeModal('createModal');
    await refreshData();
    showToast("Сборка сохранена!", "success");
}

function editCurrentInstance() {
    if (!currentViewingInstId) return;
    const id = currentViewingInstId;
    closeModal('instanceViewModal');
    openCreateModal(true, id);
}

async function openInstanceMenu(instId) {
    currentViewingInstId = instId;
    cachedModUpdates = {};
    const inst = globalConfig.instances.find(i => i.id === instId);
    if (!inst) return;
    document.getElementById('instViewTitle').textContent = `${inst.name}`;
    currentResourceTab = 'mods';
    setPlayButtonState(gameState, activeRunningId);
    const delBtn = document.getElementById('modalDeleteInstBtn');
    if (delBtn) {
        if (inst.id === 'CubeVisuals') {
            delBtn.className = "btn btn-secondary";
            delBtn.style.opacity = "0.45";
            delBtn.onclick = () => onDeleteCubeVisualsAttempt();
        } else {
            delBtn.className = "btn btn-danger";
            delBtn.style.opacity = "1";
            delBtn.onclick = () => deleteCurrentInstance();
        }
    }
    window.pywebview.api.start_watching_instance(currentViewingInstId, currentResourceTab);
    await refreshModalInstanceFiles();
    showModal('instanceViewModal');
    checkModUpdates(false);
}

async function switchInstTab(tab, evt) {
    currentResourceTab = tab;
    document.querySelectorAll('#instanceViewModal .tab-btn').forEach(b => b.classList.remove('active'));
    if (evt) evt.currentTarget.classList.add('active');
    window.pywebview.api.start_watching_instance(currentViewingInstId, currentResourceTab);
    await refreshModalInstanceFiles();
}

async function checkModUpdates(showNotification = true) {
    if (!currentViewingInstId) return;
    const btnCheck = document.getElementById('btnCheckUpdates');
    const btnUpdateAll = document.getElementById('btnUpdateAllMods');
    if (btnCheck) btnCheck.textContent = "⏳...";
    const res = await window.pywebview.api.check_instance_updates(currentViewingInstId);
    if (btnCheck) btnCheck.textContent = '🔄 Проверить обновления';
    if (res.status === 'ok') {
        cachedModUpdates = res.updates || {};
        const count = res.updates_count || 0;
        if (btnUpdateAll) {
            if (count > 0) {
                btnUpdateAll.style.display = "inline-flex";
                btnUpdateAll.textContent = `🚀 Обновить всё (${count})`;
            } else {
                btnUpdateAll.style.display = "none";
            }
        }
        await refreshModalInstanceFiles();
        if (showNotification) {
            if (count > 0) showToast(`Найдено обновлений: ${count}`, "success");
            else showToast("Все файлы актуальны!", "info");
        }
    }
}

async function updateAllMods() {
    if (!currentViewingInstId) return;
    await window.pywebview.api.update_all_mods(currentViewingInstId);
    cachedModUpdates = {};
    const btn = document.getElementById('btnUpdateAllMods');
    if (btn) btn.style.display = "none";
}

async function updateSingleMod(filename) {
    if (!currentViewingInstId || !cachedModUpdates[filename]) return;
    const info = cachedModUpdates[filename];
    showToast(`Обновление ${info.new_filename}...`, "info");
    const res = await window.pywebview.api.update_single_mod(currentViewingInstId, filename, info.url, info.new_filename);
    if (res.status === 'ok') {
        delete cachedModUpdates[filename];
        await refreshModalInstanceFiles();
    }
}

async function refreshModalInstanceFiles() {
    if (!currentViewingInstId) return;
    const selectAllBox = document.getElementById('selectAllModsCheck');
    if (selectAllBox) selectAllBox.checked = false;
    cachedInstalledFiles = await window.pywebview.api.get_instance_files(currentViewingInstId, currentResourceTab);
    applyInstalledFilter();
}

function applyInstalledFilter() {
    const list = document.getElementById('instFilesList');
    if (!list) return;
    const q = (document.getElementById('instSearchInput').value || '').toLowerCase().trim();
    const statusFilter = document.getElementById('instStatusFilter').value || 'all';
    const filtered = cachedInstalledFiles.filter(f => {
        const matchQuery = !q || (f.display_name?.toLowerCase().includes(q)) || (f.filename?.toLowerCase().includes(q)) || (f.author?.toLowerCase().includes(q));
        if (!matchQuery) return false;
        const hasUpdate = !!cachedModUpdates[f.filename];
        if (statusFilter === 'enabled') return f.enabled;
        if (statusFilter === 'disabled') return !f.enabled;
        if (statusFilter === 'updates') return hasUpdate;
        if (statusFilter === 'release') return (f.version_type || 'release') === 'release';
        if (statusFilter === 'beta') return f.version_type === 'beta';
        if (statusFilter === 'alpha') return f.version_type === 'alpha';
        return true;
    });

    list.innerHTML = filtered.length === 0 ? `<div style="padding: 24px; text-align: center; color: var(--text-secondary);">Файлы не найдены.</div>` : '';
    const fallbackModIcon = "https://cdn-icons-png.flaticon.com/512/3344/3344384.png";

    filtered.forEach(f => {
        const row = document.createElement('div');
        row.style.cssText = "display: flex; align-items: center; gap: 14px; padding: 10px 14px; background: var(--bg-main); border: 1px solid var(--border); border-radius: var(--radius-md);";
        if (!f.enabled) row.style.opacity = '0.55';

        const updateInfo = cachedModUpdates[f.filename];
        const updateBadge = updateInfo ? `<span class="badge-type badge-mr" style="font-size: 10px; padding: 2px 6px;">⬆ ${escapeHtml(updateInfo.new_version)}</span>` : '';
        const updateBtn = updateInfo ? `<button class="btn btn-update-available" style="padding: 5px 8px; font-size: 11px;" onclick="updateSingleMod('${escapeAttr(f.filename)}')">🔄</button>` : '';
        const relType = f.version_type || 'release';
        const relBadge = `<span class="badge-type ${getReleaseBadgeClass(relType)}" style="font-size: 9px; padding: 2px 6px;">${formatReleaseType(relType)}</span>`;

        row.innerHTML =
            `<input type="checkbox" class="mod-check mod-item-check" value="${escapeAttr(f.filename)}">` +
            `<img src="${escapeAttr(f.icon || fallbackModIcon)}" style="width: 44px; height: 44px; border-radius: var(--radius-md); object-fit: cover; background: var(--bg-card); border: 1px solid var(--border); flex-shrink: 0;" onerror="this.src='${fallbackModIcon}'">` +
            `<div style="flex: 2; display: flex; flex-direction: column; overflow: hidden;"><div style="font-weight: 800; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(f.display_name)}</div><div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">👤 ${escapeHtml(f.author || 'Не указан')}</div></div>` +
            `<div style="flex: 1.4; display: flex; flex-direction: column; overflow: hidden; gap: 2px;"><div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;"><span style="font-size: 11px; font-weight: 700; color: #60a5fa;">${escapeHtml(f.version || 'v1.0.0')}</span>${relBadge}${updateBadge}</div>` +
            `<span style="font-size: 10px; color: var(--text-secondary); font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(f.clean_name)}</span></div>` +
            `<label style="position: relative; display: inline-block; width: 44px; height: 22px; flex-shrink: 0;"><input type="checkbox" ${f.enabled ? 'checked' : ''} onchange="toggleFile('${escapeAttr(f.filename)}')" style="opacity: 0; width: 0; height: 0;"><span style="position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: ${f.enabled ? '#22c55e' : '#33292e'}; border-radius: var(--radius-pill); border: 1px solid var(--border); transition: all 0.2s ease;"></span></label>` +
            `<div style="display: flex; gap: 4px; align-items: center; justify-content: flex-end; width: 90px;">${updateBtn}` +
            `<button class="btn btn-danger" style="padding: 6px 10px; font-size: 11px;" onclick="deleteFile('${escapeAttr(f.filename)}')">🗑️</button></div>`;
        list.appendChild(row);
    });
}

function toggleSelectAllMods(checked) {
    document.querySelectorAll('.mod-item-check').forEach(cb => { cb.checked = checked; });
}

function getSelectedFilenames() {
    const s = [];
    document.querySelectorAll('.mod-item-check:checked').forEach(cb => s.push(cb.value));
    return s;
}

async function toggleSelectedFiles(targetState) {
    const files = getSelectedFilenames();
    if (files.length === 0) return showToast("Отметьте файлы галочкой!", "info");
    for (const fname of files) {
        const isCurrentlyDisabled = fname.endsWith('.disabled');
        if (targetState && isCurrentlyDisabled) await window.pywebview.api.toggle_instance_file(currentViewingInstId, currentResourceTab, fname);
        else if (!targetState && !isCurrentlyDisabled) await window.pywebview.api.toggle_instance_file(currentViewingInstId, currentResourceTab, fname);
    }
    await refreshModalInstanceFiles();
}

async function deleteSelectedFiles() {
    const files = getSelectedFilenames();
    if (files.length === 0) return showToast("Отметьте файлы галочкой!", "info");
    for (const fname of files) await window.pywebview.api.delete_instance_file(currentViewingInstId, currentResourceTab, fname);
    await refreshModalInstanceFiles();
}

async function toggleFile(fname) {
    await window.pywebview.api.toggle_instance_file(currentViewingInstId, currentResourceTab, fname);
    await refreshModalInstanceFiles();
}

async function deleteFile(fname) {
    await window.pywebview.api.delete_instance_file(currentViewingInstId, currentResourceTab, fname);
    await refreshModalInstanceFiles();
}

function openActiveInstFolder() {
    if (currentViewingInstId) window.pywebview.api.open_instance_folder(currentViewingInstId);
}

async function deleteCurrentInstance() {
    if (currentViewingInstId === 'CubeVisuals') return onDeleteCubeVisualsAttempt();
    await window.pywebview.api.delete_instance(currentViewingInstId);
    closeModal('instanceViewModal');
    await refreshData();
}

function launchCurrentInstance() {
    if (currentViewingInstId) {
        playUiSound('launch');
        window.pywebview.api.launch_active_game(currentViewingInstId);
    }
}

function launchGame() {
    playUiSound('launch');
    window.pywebview.api.launch_active_game();
}

function setPlayButtonState(state, runningInstId = null) {
    gameState = state;
    activeRunningId = (state === 'running' || state === 'launching' || state === 'installing') ? runningInstId : null;
    const mainBtn = document.getElementById('mainPlayBtn');
    const modalBtn = document.getElementById('modalPlayBtn');
    if (mainBtn) {
        if (state === 'installing') { mainBtn.textContent = "⏳ ..."; mainBtn.disabled = true; }
        else if (state === 'launching') { mainBtn.textContent = "🚀 ..."; mainBtn.disabled = true; }
        else if (state === 'running') { mainBtn.textContent = "⏹ Закрыть"; mainBtn.className = "btn btn-danger"; mainBtn.disabled = false; mainBtn.onclick = () => window.pywebview.api.kill_game(); }
        else { mainBtn.textContent = 'ИГРАТЬ'; mainBtn.className = "btn"; mainBtn.disabled = false; mainBtn.onclick = () => launchGame(); }
    }
    if (modalBtn) {
        if (state === 'running' && (!runningInstId || runningInstId === currentViewingInstId)) {
            modalBtn.textContent = "⏹ Закрыть"; modalBtn.className = "btn btn-danger"; modalBtn.disabled = false; modalBtn.onclick = () => window.pywebview.api.kill_game();
        } else if (state === 'installing' || state === 'launching') {
            modalBtn.textContent = state === 'installing' ? "⏳..." : "🚀..."; modalBtn.className = "btn"; modalBtn.disabled = true;
        } else {
            modalBtn.textContent = '🚀 Запустить'; modalBtn.className = "btn"; modalBtn.disabled = false; modalBtn.onclick = () => launchCurrentInstance();
        }
    }
    renderInstallations();
}

// ================= ДЕТАЛИ СЕРВЕРА =================
async function openServerDetail(serverId) {
    try {
        const res = await window.pywebview.api.get_server_details(serverId);
        if (!res || res.status !== 'ok') { showToast('Не удалось загрузить сервер', 'error'); return; }
        currentServerDetail = res.server;
        const srv = res.server;
        const sdIcon = document.getElementById('sdIcon');
        if (srv.status_icon) { sdIcon.src = srv.status_icon; sdIcon.style.display = 'block'; }
        else sdIcon.style.display = 'none';
        document.getElementById('sdName').textContent = srv.name;
        document.getElementById('sdAddress').textContent = srv.address;
        const licBadge = document.getElementById('sdLicenseBadge');
        const lic = srv.license || 'licensed';
        if (lic === 'licensed') { licBadge.className = 'badge-license'; licBadge.textContent = 'Лицензия'; }
        else if (lic === 'pirate') { licBadge.className = 'badge-nolicense'; licBadge.textContent = 'Пиратка'; }
        else { licBadge.className = 'badge-both'; licBadge.textContent = 'Лиц. + Пиратка'; }
        const pb = document.getElementById('sdPlayersBadge');
        if (srv.online) { pb.className = 'badge-players'; pb.textContent = `👥 ${srv.players_online}/${srv.players_max}`; }
        else { pb.className = 'badge-players offline'; pb.textContent = `👥 Оффлайн`; }
        const motdBox = document.getElementById('sdMotdBox');
        if (srv.motd) { motdBox.textContent = srv.motd; motdBox.style.display = 'block'; }
        else motdBox.style.display = 'none';
        document.getElementById('sdDescriptionText').textContent = srv.description || 'Нет описания';
        document.getElementById('sdRegionBadge').textContent = `🌍 ${srv.region || '—'}`;
        document.getElementById('sdVersionsBadge').textContent = `🎮 ${(srv.versions || []).join(', ') || '—'}`;
        const webBtn = document.getElementById('sdWebsiteBtn');
        if (srv.website) { webBtn.style.display = 'inline-flex'; webBtn.onclick = () => { try { window.open(srv.website); } catch (e) { showToast(srv.website, 'info'); } }; }
        else webBtn.style.display = 'none';
        renderServerScreenshots(srv.screenshots || []);
        await loadServerComments(serverId);
        if (currentCubeUser) document.getElementById('sdMyAvatar').src = currentCubeUser.avatar || `https://minotar.net/helm/${currentCubeUser.username}/100.png`;
        switchServerDetailTab('desc', null, true);
        document.getElementById('sdCommentInput').value = '';
        currentCommentRating = 5;
        updateStarsInput(5);
        showModal('serverDetailModal');
    } catch (e) { showToast('Ошибка загрузки сервера', 'error'); }
}

function renderServerScreenshots(shots) {
    const strip = document.getElementById('sdScreenshotsStrip');
    const empty = document.getElementById('sdScreenshotsEmpty');
    strip.innerHTML = '';
    if (!shots || shots.length === 0) { strip.style.display = 'none'; empty.style.display = 'block'; return; }
    strip.style.display = 'flex'; empty.style.display = 'none';
    shots.forEach((url, idx) => {
        const img = document.createElement('img');
        img.style.cssText = "height: 130px; border-radius: var(--radius-md); object-fit: cover; border: 1px solid var(--border); cursor: pointer; flex-shrink: 0;";
        img.src = url;
        img.onerror = () => img.remove();
        img.onclick = () => {
            currentLightboxGallery = shots.slice();
            currentLightboxIndex = idx;
            updateLightboxView();
            document.getElementById('galleryLightbox').classList.add('active');
        };
        strip.appendChild(img);
    });
}

function switchServerDetailTab(tab, evt, silent = false) {
    currentServerDetailTab = tab;
    if (evt) { document.querySelectorAll('#serverDetailModal .tab-btn').forEach(b => b.classList.remove('active')); evt.currentTarget.classList.add('active'); }
    else if (silent) { document.querySelectorAll('#serverDetailModal .tab-btn').forEach((b, i) => { b.classList.remove('active'); if (['desc', 'shots', 'comments', 'rating'][i] === tab) b.classList.add('active'); }); }
    document.getElementById('sdtDesc').style.display = tab === 'desc' ? 'flex' : 'none';
    document.getElementById('sdtShots').style.display = tab === 'shots' ? 'flex' : 'none';
    document.getElementById('sdtComments').style.display = tab === 'comments' ? 'flex' : 'none';
    document.getElementById('sdtRating').style.display = tab === 'rating' ? 'flex' : 'none';
    if (tab === 'rating' && currentServerDetail) {
        const comments = serversCommentsCache[currentServerDetail.id] || loadServerCommentsFromLocal(currentServerDetail.id);
        renderServerRating(currentServerDetail.id, comments);
    }
}

function copyServerAddressFromDetail() { if (currentServerDetail) copyServerAddress(currentServerDetail.address, currentServerDetail.name); }
function openServerWebsite() { if (currentServerDetail?.website) { try { window.open(currentServerDetail.website); } catch (e) { showToast(currentServerDetail.website, 'info'); } } }

function loadServerCommentsFromLocal(serverId) {
    try {
        const raw = localStorage.getItem(`cube_server_comments_${serverId}`);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch (e) { return []; }
}
function saveServerCommentsToLocal(serverId, arr) { try { localStorage.setItem(`cube_server_comments_${serverId}`, JSON.stringify(arr)); } catch (e) {} }

async function loadServerComments(serverId) {
    const list = document.getElementById('sdCommentsList');
    list.innerHTML = '<div style="text-align: center; color: var(--text-secondary); font-size: 12px; padding: 12px;">⏳ Загрузка отзывов...</div>';
    const comments = loadServerCommentsFromLocal(serverId);
    serversCommentsCache[serverId] = comments;
    renderServerComments(serverId, comments);
}

function renderServerComments(serverId, comments) {
    const list = document.getElementById('sdCommentsList');
    if (!comments || comments.length === 0) { list.innerHTML = '<div style="text-align: center; color: var(--text-secondary); font-size: 12px; padding: 20px;">Пока нет отзывов</div>'; return; }
    list.innerHTML = '';
    const sorted = comments.slice().sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
    sorted.forEach(c => {
        const row = document.createElement('div');
        row.style.cssText = "background: var(--bg-main); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 10px 14px; display: flex; gap: 10px; align-items: flex-start;";
        const stars = '★'.repeat(c.rating || 0) + '☆'.repeat(5 - (c.rating || 0));
        row.innerHTML =
            `<img src="${escapeAttr(c.avatar || 'https://minotar.net/helm/Steve/100.png')}" style="width: 36px; height: 36px; border-radius: var(--radius-pill); border: 1px solid var(--border); flex-shrink: 0;" onerror="this.src='https://minotar.net/helm/Steve/100.png'">` +
            `<div style="flex: 1; min-width: 0;"><div style="display: flex; justify-content: space-between; align-items: center;">` +
            `<div><span style="font-size: 13px; font-weight: 800; color: var(--accent);">${escapeHtml(c.author || 'Player')}</span><span style="font-size: 10px; color: var(--text-secondary); margin-left: 6px;">${escapeHtml(c.date || '')}</span></div>` +
            `<span style="font-size: 12px; color: #facc15;">${stars}</span></div>` +
            `<div style="font-size: 12px; line-height: 1.45; margin-top: 4px; word-wrap: break-word;">${escapeHtml(c.text || '')}</div></div>`;
        list.appendChild(row);
    });
}

function updateStarsInput(rating) {
    const container = document.getElementById('sdStarsInput');
    if (!container) return;
    container.querySelectorAll('span[data-star]').forEach(s => {
        const v = parseInt(s.getAttribute('data-star'));
        s.style.color = v <= rating ? '#facc15' : 'var(--text-secondary)';
    });
    currentCommentRating = rating;
}

document.addEventListener('click', (e) => {
    const star = e.target.closest('#sdStarsInput span[data-star]');
    if (star) updateStarsInput(parseInt(star.getAttribute('data-star')));
});

async function submitServerComment() {
    if (!currentServerDetail) return;
    if (!currentCubeUser) { showToast("Войдите в профиль Cube Launcher!", "error"); return; }
    const inp = document.getElementById('sdCommentInput');
    const text = inp.value.trim();
    if (!text) { showToast("Напишите текст отзыва!", "error"); return; }
    const serverId = currentServerDetail.id;
    const comments = loadServerCommentsFromLocal(serverId);
    const newComment = {
        author: currentCubeUser.username,
        avatar: currentCubeUser.avatar || `https://minotar.net/helm/${currentCubeUser.username}/100.png`,
        text, rating: currentCommentRating,
        date: new Date().toLocaleDateString('ru-RU'),
        timestamp: Date.now()
    };
    comments.push(newComment);
    saveServerCommentsToLocal(serverId, comments);
    inp.value = '';
    currentCommentRating = 5;
    updateStarsInput(5);
    showToast("Отзыв опубликован!", "success");
    serversCommentsCache[serverId] = comments;
    renderServerComments(serverId, comments);
    renderServerRating(serverId, comments);
}

function renderServerRating(serverId, comments) {
    const count = comments.length;
    let avg = 0;
    if (count > 0) avg = comments.reduce((acc, c) => acc + (c.rating || 0), 0) / count;
    document.getElementById('sdRatingBig').textContent = avg.toFixed(1);
    const starsFull = Math.round(avg);
    document.getElementById('sdRatingStars').textContent = '★'.repeat(starsFull) + '☆'.repeat(5 - starsFull);
    document.getElementById('sdRatingCount').textContent = `На основе ${count} отзывов`;
    const bars = document.getElementById('sdRatingBars');
    bars.innerHTML = '';
    for (let s = 5; s >= 1; s--) {
        const cnt = comments.filter(c => (c.rating || 0) === s).length;
        const pct = count > 0 ? Math.round((cnt / count) * 100) : 0;
        const bar = document.createElement('div');
        bar.style.cssText = 'display: flex; align-items: center; gap: 8px; font-size: 12px;';
        bar.innerHTML = `<span style="width: 40px; color: var(--text-secondary);">${s} ★</span>` +
            `<div style="flex: 1; height: 8px; background: var(--bg-main); border-radius: var(--radius-pill); overflow: hidden; border: 1px solid var(--border);">` +
            `<div style="height: 100%; width: ${pct}%; background: linear-gradient(90deg, #f97316, #eab308);"></div></div>` +
            `<span style="width: 40px; text-align: right; color: var(--text-secondary);">${cnt}</span>`;
        bars.appendChild(bar);
    }
}

// ================= ДРУЗЬЯ И ЧАТЫ =================
function switchFriendsSubTab(sub, evt) {
    document.querySelectorAll('.friends-top-tab-btn').forEach(b => b.classList.remove('active'));
    if (evt) evt.currentTarget.classList.add('active');
    document.getElementById('friendsListContainer').style.display = sub === 'friends' ? 'flex' : 'none';
    document.getElementById('requestsListContainer').style.display = sub === 'requests' ? 'flex' : 'none';
}

async function sendFriendRequestAction() {
    const inp = document.getElementById('friendSearchNickInput');
    const nick = inp.value.trim();
    if (!nick) return showToast("Введите ник игрока!", "error");
    showToast("Поиск игрока...", "info");
    const res = await window.pywebview.api.search_and_send_friend_request(nick);
    if (res.status === 'ok') {
        inp.value = '';
        loadFriendsListAndRequests();
    } else {
        showToast(res.message, "error");
    }
}

async function loadFriendsListAndRequests() {
    const res = await window.pywebview.api.get_friends_data();
    if (res.status !== 'ok') return;
    document.getElementById('friendsCountBadge').textContent = (res.friends || []).length;
    document.getElementById('requestsCountBadge').textContent = (res.incoming || []).length + (res.outgoing || []).length;
    const fList = document.getElementById('friendsListContainer');
    fList.innerHTML = (res.friends || []).length === 0 ? '<div style="padding: 24px; color: var(--text-secondary); text-align: center; font-size: 13px;">У вас пока нет друзей</div>' : '';
    (res.friends || []).forEach(f => {
        const item = document.createElement('div');
        item.className = `friend-row-item ${currentSelectedFriendUid === f.uid ? 'active' : ''}`;
        item.onclick = () => openFriendProfileView(f);
        const subStatus = f.is_online ? (f.is_playing ? '🎮 В игре' : 'В сети') : 'Не в сети';
        item.innerHTML = `<div class="friend-avatar-wrapper"><img class="friend-row-avatar" src="${escapeAttr(f.avatar)}"><div class="friend-status-dot ${f.is_online ? '' : 'offline'}"></div></div>` +
            `<div style="flex: 1; overflow: hidden;"><div style="font-weight: 800; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(f.username)}</div>` +
            `<div style="font-size: 11px; color: var(--text-secondary);">${subStatus}</div></div>`;
        fList.appendChild(item);
    });

    const rList = document.getElementById('requestsListContainer');
    rList.innerHTML = '';
    if ((res.incoming || []).length > 0) {
        rList.innerHTML += '<div style="padding: 10px 14px 4px 14px; font-size: 11px; font-weight: 800; color: var(--accent);">ВХОДЯЩИЕ ЗАЯВКИ</div>';
        res.incoming.forEach(r => {
            const row = document.createElement('div');
            row.className = 'friend-row-item';
            row.innerHTML = `<img class="friend-row-avatar" src="${escapeAttr(r.avatar)}"><div style="flex: 1;"><div style="font-weight: 800; font-size: 13px;">${escapeHtml(r.username)}</div></div>` +
                `<div style="display: flex; gap: 6px;"><button class="btn" style="padding: 6px 12px; font-size: 11px;" onclick="respondFriendReq('${escapeAttr(r.req_id)}', 'accept')">Принять</button>` +
                `<button class="btn btn-secondary" style="padding: 6px 12px; font-size: 11px;" onclick="respondFriendReq('${escapeAttr(r.req_id)}', 'decline')">Отклонить</button></div>`;
            rList.appendChild(row);
        });
    }
    if ((res.outgoing || []).length > 0) {
        rList.innerHTML += '<div style="padding: 10px 14px 4px 14px; font-size: 11px; font-weight: 800; color: var(--text-secondary);">ИСХОДЯЩИЕ ЗАЯВКИ</div>';
        res.outgoing.forEach(r => {
            const row = document.createElement('div');
            row.className = 'friend-row-item';
            row.innerHTML = `<img class="friend-row-avatar" src="${escapeAttr(r.avatar)}"><div style="flex: 1;"><div style="font-weight: 800; font-size: 13px;">${escapeHtml(r.username)}</div>` +
                `<div style="font-size: 11px; color: var(--text-secondary);">В ожидании ответа...</div></div>` +
                `<button class="btn btn-danger" style="padding: 6px 12px; font-size: 11px;" onclick="respondFriendReq('${escapeAttr(r.req_id)}', 'decline')">Отмена</button>`;
            rList.appendChild(row);
        });
    }
}

async function respondFriendReq(reqId, action) {
    await window.pywebview.api.respond_to_friend_request(reqId, action);
    loadFriendsListAndRequests();
}

function openFriendProfileView(friend) {
    currentSelectedFriendUid = friend.uid;
    loadFriendsListAndRequests();
    clearInterval(chatPoller);
    let activityHtml = '<div style="color: var(--text-secondary); font-size: 13px;">Сейчас не в игре</div>';
    if (friend.is_playing) activityHtml = `<div class="activity-pill" style="display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: var(--radius-md); background: rgba(249, 115, 22, 0.14); border: 1px solid var(--accent); color: var(--accent); font-size: 13px; font-weight: 800;">🎮 ${escapeHtml(friend.activity_title || 'Minecraft')} ${escapeHtml(friend.activity_version || '')}</div>`;
    const right = document.getElementById('friendsRightPanel');
    right.innerHTML =
        `<div class="chat-header"><div style="display: flex; align-items: center; gap: 12px;"><img class="friend-row-avatar" src="${escapeAttr(friend.avatar)}">` +
        `<div><div style="font-weight: 800; font-size: 16px;">${escapeHtml(friend.username)}</div>` +
        `<div style="font-size: 11px; color: ${friend.is_online ? '#22c55e' : 'var(--text-secondary)'}; font-weight: 700;">${friend.is_online ? '● В сети' : 'Не в сети'}</div></div></div>` +
        `<div style="display: flex; gap: 8px;"><button class="btn btn-secondary" onclick="openProfileViewModal('${escapeAttr(friend.uid)}', '${escapeAttr(friend.username)}')">👤 Полный профиль</button>` +
        `<button class="btn" onclick="openChatMessenger('${escapeAttr(friend.uid)}', '${escapeAttr(friend.username)}')">💬 Диалог</button></div></div>` +
        `<div style="padding: 24px; display: flex; flex-direction: column; gap: 18px;">` +
        `<div><div style="font-size: 11px; font-weight: 800; color: var(--accent); margin-bottom: 6px;">СТАТУС ИГРЫ</div>${activityHtml}</div>` +
        `<div><div style="font-size: 11px; font-weight: 800; color: var(--text-secondary); margin-bottom: 8px;">СТАТИСТИКА</div>` +
        `<div class="stats-grid" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">` +
        `<div class="stat-card" style="background: var(--bg-main); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px 16px; display: flex; flex-direction: column; gap: 4px;"><span class="stat-icon">🕒</span><div class="stat-value" style="font-size: 14px; font-weight: 800; color: var(--accent);">${formatSeconds(friend.stat_launcher_seconds || 0)}</div><div class="stat-label" style="font-size: 10px; color: var(--text-secondary); font-weight: 800; text-transform: uppercase;">В лаунчере</div></div>` +
        `<div class="stat-card" style="background: var(--bg-main); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px 16px; display: flex; flex-direction: column; gap: 4px;"><span class="stat-icon">🎮</span><div class="stat-value" style="font-size: 14px; font-weight: 800; color: var(--accent);">${formatSeconds(friend.stat_minecraft_seconds || 0)}</div><div class="stat-label" style="font-size: 10px; color: var(--text-secondary); font-weight: 800; text-transform: uppercase;">В игре</div></div>` +
        `<div class="stat-card" style="background: var(--bg-main); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px 16px; display: flex; flex-direction: column; gap: 4px;"><span class="stat-icon">🚀</span><div class="stat-value" style="font-size: 18px; font-weight: 800; color: var(--accent);">${friend.stat_launches || 0}</div><div class="stat-label" style="font-size: 10px; color: var(--text-secondary); font-weight: 800; text-transform: uppercase;">Запусков</div></div>` +
        `</div></div>` +
        `<div><div style="font-size: 11px; font-weight: 800; color: var(--text-secondary); margin-bottom: 6px;">О СЕБЕ</div>` +
        `<div style="padding: 14px; background: var(--bg-main); border-radius: var(--radius-md); border: 1px solid var(--border); font-size: 13px; line-height: 1.5;">${escapeHtml(friend.bio || 'Пользователь не указал информацию о себе.')}</div></div></div>`;
}

function openChatMessenger(friendUid, friendName) {
    const right = document.getElementById('friendsRightPanel');
    right.innerHTML =
        `<div class="chat-header"><div style="font-weight: 800; font-size: 16px;">Диалог с ${escapeHtml(friendName)}</div>` +
        `<button class="btn btn-secondary" style="padding: 6px 14px; font-size: 12px;" onclick="loadFriendsListAndRequests()">◀ Профиль</button></div>` +
        `<div class="chat-body-messages" id="chatMessagesView"></div>` +
        `<div class="chat-input-bar">` +
        `<button class="btn btn-secondary" style="border-radius: var(--radius-pill); padding: 8px 12px;" onclick="sendChatImageFile('${escapeAttr(friendUid)}')" title="Отправить картинку">📷</button>` +
        `<button class="mic-record-btn" id="micRecordBtn" onmousedown="startVoiceRecording('${escapeAttr(friendUid)}')" onmouseup="stopVoiceRecording(true)" onmouseleave="stopVoiceRecording(true)" title="Записать голосовое">🎤</button>` +
        `<div class="mic-timer-badge" id="micTimerBadge">● 0:00</div>` +
        `<input type="text" id="chatInputMessageText" placeholder="Напишите сообщение..." style="flex: 1;" onkeydown="if(event.key==='Enter') sendChatMessageText('${escapeAttr(friendUid)}')">` +
        `<button class="btn" onclick="sendChatMessageText('${escapeAttr(friendUid)}')">Отправить</button></div>`;
    fetchAndRenderMessages(friendUid);
    clearInterval(chatPoller);
    chatPoller = setInterval(() => fetchAndRenderMessages(friendUid), 3000);
}

async function fetchAndRenderMessages(friendUid) {
    const res = await window.pywebview.api.get_messages(friendUid);
    const box = document.getElementById('chatMessagesView');
    if (!box || res.status !== 'ok') return;
    const uRes = await window.pywebview.api.get_cube_user();
    const myUid = uRes.user ? uRes.user.id : null;
    box.innerHTML = '';
    (res.messages || []).forEach(m => {
        const bubble = document.createElement('div');
        const isMine = m.sender_uid === myUid;
        bubble.className = `msg-bubble ${isMine ? 'mine' : 'theirs'}`;
        const imgPart = m.image ? `<img src="${escapeAttr(m.image)}" style="max-width: 100%; border-radius: var(--radius-md); margin-top: 4px;">` : '';
        let voicePart = '';
        if (m.voice && m.voice.startsWith('data:audio')) {
            const dur = m.voice_duration || 0;
            const mm = Math.floor(dur / 60); const ss = String(dur % 60).padStart(2, '0');
            const uniqueId = 'vp_' + Math.random().toString(36).substring(2, 10);
            voicePart = `<div style="display: flex; align-items: center; gap: 10px; min-width: 180px;"><button class="btn btn-secondary" style="width: 34px; height: 34px; border-radius: var(--radius-pill); padding: 0; display: flex; align-items: center; justify-content: center;" onclick="playVoiceMsg('${uniqueId}', this)">▶</button>` +
                `<div style="flex: 1; display: flex; align-items: center; gap: 3px; height: 26px;"><div style="width: 3px; height: 40%; background: currentColor; border-radius: 2px; opacity: 0.7;"></div><div style="width: 3px; height: 75%; background: currentColor; border-radius: 2px; opacity: 0.7;"></div>` +
                `<div style="width: 3px; height: 100%; background: currentColor; border-radius: 2px; opacity: 0.7;"></div><div style="width: 3px; height: 60%; background: currentColor; border-radius: 2px; opacity: 0.7;"></div>` +
                `<div style="width: 3px; height: 90%; background: currentColor; border-radius: 2px; opacity: 0.7;"></div><div style="width: 3px; height: 40%; background: currentColor; border-radius: 2px; opacity: 0.7;"></div></div>` +
                `<span style="font-size: 11px; font-weight: 800; opacity: 0.9;">${mm}:${ss}</span><audio id="${uniqueId}" src="${m.voice}" preload="none"></audio></div>`;
        }
        const textPart = m.text ? `<div>${escapeHtml(m.text)}</div>` : '';
        bubble.innerHTML = voicePart + textPart + imgPart;
        box.appendChild(bubble);
    });
    box.scrollTop = box.scrollHeight;
}

function playVoiceMsg(audioId, btn) {
    const audioEl = document.getElementById(audioId);
    if (!audioEl) return;
    if (audioEl.paused) {
        document.querySelectorAll('audio').forEach(a => { if (a.id !== audioId) { a.pause(); a.currentTime = 0; } });
        document.querySelectorAll('.btn').forEach(b => { if (b.textContent === '⏸') b.textContent = '▶'; });
        audioEl.play();
        btn.textContent = '⏸';
        audioEl.onended = () => { btn.textContent = '▶'; };
    } else {
        audioEl.pause();
        btn.textContent = '▶';
    }
}

async function sendChatMessageText(friendUid) {
    const inp = document.getElementById('chatInputMessageText');
    const txt = inp.value.trim();
    if (!txt) return;
    inp.value = '';
    await window.pywebview.api.send_message(friendUid, txt, "");
    fetchAndRenderMessages(friendUid);
}

async function sendChatImageFile(friendUid) {
    const res = await window.pywebview.api.select_chat_image();
    if (res.status === 'ok') {
        await window.pywebview.api.send_message(friendUid, "", res.image);
        fetchAndRenderMessages(friendUid);
    } else if (res.status === 'error' && res.message) {
        showToast(res.message, "error");
    }
}

async function startVoiceRecording(friendUid) {
    try {
        if (mediaRecorder && mediaRecorder.state === 'recording') return;
        currentRecordingFriendUid = friendUid;
        recordedChunks = [];
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        let options = {};
        if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) options = { mimeType: 'audio/webm;codecs=opus' };
        else if (MediaRecorder.isTypeSupported('audio/webm')) options = { mimeType: 'audio/webm' };
        mediaRecorder = new MediaRecorder(stream, options);
        mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) recordedChunks.push(e.data); };
        mediaRecorder.onstop = () => { stream.getTracks().forEach(t => t.stop()); };
        mediaRecorder.start();
        recordingStartTime = Date.now();
        const btn = document.getElementById('micRecordBtn');
        if (btn) { btn.classList.add('recording'); btn.textContent = '⏹'; }
        const badge = document.getElementById('micTimerBadge');
        if (badge) { badge.classList.add('active'); badge.textContent = '● 0:00'; }
        recordingTimerInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
            const mm = Math.floor(elapsed / 60); const ss = String(elapsed % 60).padStart(2, '0');
            if (badge) badge.textContent = `● ${mm}:${ss}`;
        }, 250);
    } catch (err) {
        showToast('Доступ к микрофону не предоставлен', 'error');
    }
}

async function stopVoiceRecording(sendIt = true) {
    if (!mediaRecorder || mediaRecorder.state !== 'recording') return;
    const friendUid = currentRecordingFriendUid;
    const durationSec = Math.floor((Date.now() - recordingStartTime) / 1000);
    clearInterval(recordingTimerInterval);
    recordingTimerInterval = null;
    const btn = document.getElementById('micRecordBtn');
    if (btn) { btn.classList.remove('recording'); btn.textContent = '🎤'; }
    const badge = document.getElementById('micTimerBadge');
    if (badge) { badge.classList.remove('active'); badge.textContent = '● 0:00'; }
    mediaRecorder.onstop = async () => {
        if (sendIt) {
            if (durationSec < 1) { showToast("Слишком короткое голосовое", "error"); return; }
            showToast("Отправка...", "info");
            const blob = new Blob(recordedChunks, { type: 'audio/webm' });
            const reader = new FileReader();
            reader.onloadend = async () => {
                const b64 = reader.result;
                const res = await window.pywebview.api.send_voice_message(friendUid, b64, durationSec);
                if (res.status === 'error' && res.message) showToast(res.message, "error");
                if (document.getElementById('chatMessagesView')) fetchAndRenderMessages(friendUid);
            };
            reader.readAsDataURL(blob);
        }
        recordedChunks = [];
        currentRecordingFriendUid = null;
    };
    mediaRecorder.stop();
}

// ================= ФОНОВЫЙ БАННЕР =================
async function loadBannerMedia() {
    try {
        const res = await window.pywebview.api.get_banner_data();
        if (res && res.status === 'image' && res.data) {
            document.body.style.backgroundImage = `url("${res.data}")`;
            document.body.style.backgroundSize = "cover";
            document.body.style.backgroundPosition = "center";
            document.body.style.backgroundRepeat = "no-repeat";
        }
    } catch (e) {
        console.log("Ошибка загрузки фона:", e);
    }
}

async function browseBanner() {
    const res = await window.pywebview.api.select_banner_file();
    if (res && res.status === 'ok') {
        document.getElementById('settingBannerPath').value = res.path;
        await loadBannerMedia();
        showToast("Баннер обновлен!", "success");
    }
}

async function clearBanner() {
    await window.pywebview.api.clear_banner_file();
    document.getElementById('settingBannerPath').value = '';
    await loadBannerMedia();
}

// ================= АВТОСОХРАНЕНИЕ НАСТРОЕК =================
function triggerAutoSave() {
    clearTimeout(autoSaveTimer);
    autoSaveTimer = setTimeout(async () => {
        const ramMb = document.getElementById('settingRamSlider').value;
        const jvm = document.getElementById('settingJvm').value;
        const consoleEnabled = document.getElementById('settingConsole').checked;
        const theme = document.getElementById('settingThemeSelect').value;
        const lang = document.getElementById('settingLangSelect').value;
        const anims = document.getElementById('settingAnimationsToggle').checked;
        const speed = document.getElementById('settingAnimSpeedSlider').value;
        const showAct = document.getElementById('settingShowActivityToggle').checked;
        const rpc = document.getElementById('settingDiscordRpcToggle').checked;
        const telem = document.getElementById('settingTelemetryToggle').checked;
        const showBanner = document.getElementById('settingShowBannerToggle')?.checked ?? true;
        const lgSlider = document.getElementById('settingLiquidGlassSlider');
        const lgToggle = document.getElementById('settingLiquidGlassToggle');
        let lgVal = 'off';
        if (lgToggle && lgToggle.checked && lgSlider) {
            const idx = Math.max(0, Math.min(3, parseInt(lgSlider.value)));
            lgVal = LIQUID_GLASS_VARIANTS[idx];
            if (lgVal === 'off') lgVal = 'standard';
        }
        await window.pywebview.api.save_settings_auto(
            ramMb, consoleEnabled, jvm, null, theme, lang,
            anims, speed, rpc, telem, showAct, showBanner, lgVal
        );
    }, 300);
}

// ================= UI ПРОФИЛЯ CUBE =================
async function refreshMainProfileUI() {
    const resCube = await window.pywebview.api.get_cube_accounts_list();
    const accounts = resCube.accounts || [];
    currentCubeUser = resCube.current;
    const avatarEl = document.getElementById('sidebarProfileAvatar');
    const nameEl = document.getElementById('sidebarProfileName');
    const subEl = document.getElementById('sidebarProfileSub');
    if (currentCubeUser) {
        avatarEl.src = currentCubeUser.avatar || `https://minotar.net/helm/${currentCubeUser.username}/100.png`;
        nameEl.textContent = currentCubeUser.username;
        subEl.textContent = "✨ Cube Profile";
        document.getElementById('cubeNotLoggedView').style.display = 'none';
        document.getElementById('cubeOtpVerificationView').style.display = 'none';
        document.getElementById('cubeLoggedView').style.display = 'flex';
        document.getElementById('cubeFullAvatar').src = currentCubeUser.avatar || `https://minotar.net/helm/${currentCubeUser.username}/100.png`;
        document.getElementById('cubeFullUsername').textContent = currentCubeUser.username;
        document.getElementById('cubeFullEmail').textContent = currentCubeUser.email || '';
        document.getElementById('cubeBioText').value = currentCubeUser.bio || '';
        refreshMyStats();
        const switchBox = document.getElementById('cubeAccountsSwitchList');
        const switchInner = document.getElementById('cubeAccountsListInner');
        switchInner.innerHTML = '';
        const otherAccounts = accounts.filter(a => a.id !== currentCubeUser.id);
        if (otherAccounts.length > 0) {
            switchBox.style.display = 'flex';
            otherAccounts.forEach(acc => {
                const row = document.createElement('div');
                row.style.cssText = "display: flex; align-items: center; justify-content: space-between; padding: 6px 12px; background: var(--bg-card); border-radius: var(--radius-md); border: 1px solid var(--border);";
                const safeAvatar = escapeAttr(acc.avatar || `https://minotar.net/helm/${acc.username}/100.png`);
                const safeId = escapeAttr(acc.id || '');
                row.innerHTML = `<div style="display: flex; align-items: center; gap: 8px; overflow: hidden;"><img src="${safeAvatar}" style="width: 28px; height: 28px; border-radius: var(--radius-pill); object-fit: cover; flex-shrink: 0;">` +
                    `<div style="display: flex; flex-direction: column; overflow: hidden;"><span style="font-size: 13px; font-weight: 800;">${escapeHtml(acc.username)}</span>` +
                    `<span style="font-size: 10px; color: var(--text-secondary);">${escapeHtml(acc.email || '')}</span></div></div>` +
                    `<button class="btn" style="padding: 4px 12px; font-size: 11px; flex-shrink: 0;" onclick="switchCubeAccount('${safeId}')">Войти</button>`;
                switchInner.appendChild(row);
            });
        } else switchBox.style.display = 'none';
    } else {
        avatarEl.src = 'https://minotar.net/helm/Steve/100.png';
        nameEl.textContent = 'Войти в профиль';
        subEl.textContent = '✨ Cube Account';
        document.getElementById('cubeNotLoggedView').style.display = 'flex';
        document.getElementById('cubeOtpVerificationView').style.display = 'none';
        document.getElementById('cubeLoggedView').style.display = 'none';
        document.getElementById('cubeAccountsSwitchList').style.display = 'none';
    }
}

async function refreshMyStats() {
    try {
        const res = await window.pywebview.api.get_stats();
        if (res && res.status === 'ok') {
            document.getElementById('myStatLauncherHours').textContent = formatSeconds(res.launcher_seconds);
            document.getElementById('myStatMinecraftHours').textContent = formatSeconds(res.minecraft_seconds);
            document.getElementById('myStatLaunches').textContent = res.launches || 0;
        }
    } catch (e) {}
}

async function switchCubeAccount(uid) {
    showToast("Переключение профиля...", "info");
    const res = await window.pywebview.api.switch_cube_account(uid);
    if (res && res.status === 'ok') {
        await refreshData();
        await refreshMainProfileUI();
    } else if (res?.message) {
        showToast(res.message, "error");
    }
}

// ================= ОБНОВЛЕНИЕ ДАННЫХ =================
async function refreshData() {
    try {
        globalConfig = await window.pywebview.api.get_config();
        const accounts = await window.pywebview.api.get_accounts();
        const ramMb = globalConfig.ram_mb || 4096;
        document.getElementById('settingRamSlider').value = ramMb;
        onRamSliderInput(ramMb, false);
        document.getElementById('settingJvm').value = globalConfig.jvm_args || '';
        document.getElementById('settingConsole').checked = !!globalConfig.enable_console;
        document.getElementById('settingBannerPath').value = globalConfig.banner_path || '';
        applyTheme(globalConfig.theme || 'dark');
        applyLanguage(globalConfig.language || 'ru');
        const showBanner = globalConfig.show_banner !== false;
        const bannerToggle = document.getElementById('settingShowBannerToggle');
        if (bannerToggle) bannerToggle.checked = showBanner;
        const widget = document.getElementById('cubeVanillaWidget');
        if (widget) widget.style.display = showBanner ? 'flex' : 'none';
        const anims = globalConfig.animations_enabled !== false;
        document.getElementById('settingAnimationsToggle').checked = anims;
        document.getElementById('settingAnimSpeedSlider').value = globalConfig.animation_speed || 1.0;
        onAnimationsToggleChange(anims, false);
        const lgVal = globalConfig.liquid_glass || 'off';
        const lgIdx = Math.max(0, LIQUID_GLASS_VARIANTS.indexOf(lgVal));
        const lgToggle = document.getElementById('settingLiquidGlassToggle');
        const lgSlider = document.getElementById('settingLiquidGlassSlider');
        if (lgToggle) lgToggle.checked = (lgIdx > 0);
        if (lgSlider) lgSlider.value = lgIdx;
        onLiquidGlassToggleChange(lgIdx > 0, false);
        document.getElementById('settingShowActivityToggle').checked = globalConfig.show_game_activity !== false;
        document.getElementById('settingDiscordRpcToggle').checked = globalConfig.discord_rpc !== false;
        document.getElementById('settingTelemetryToggle').checked = globalConfig.telemetry !== false;
        document.getElementById('settingShowCubeVisualsToggle').checked = globalConfig.show_cube_visuals !== false;
        await loadBannerMedia();
        renderActiveInstance();
        renderInstallations();
        renderAccounts(accounts);
        populateTargetInstancesSelect();
        refreshCubeVanilla();
    } catch (e) {
        showToast("Ошибка загрузки: " + (e.message || e), "error");
    }
}

function applyLanguage(lang) {
    currentLang = lang === 'en' ? 'en' : 'ru';
    const el = document.getElementById('settingLangSelect');
    if (el) el.value = currentLang;
}

// ================= ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ =================
async function waitForPywebviewApi(maxWaitMs = 15000) {
    const start = Date.now();
    while (Date.now() - start < maxWaitMs) {
        if (window.pywebview && window.pywebview.api) return true;
        await new Promise(r => setTimeout(r, 100));
    }
    return false;
}

async function initApp() {
    if (window.__cubeInited) return;
    window.__cubeInited = true;

    const loadingStart = Date.now();
    const MIN_LOADING_MS = 3000;

    const ready = await waitForPywebviewApi();
    if (!ready) {
        showToast('Не удалось установить соединение с клиентом', 'error');
        const elapsed = Date.now() - loadingStart;
        const wait = Math.max(0, MIN_LOADING_MS - elapsed);
        setTimeout(hideLoadingScreen, wait);
        return;
    }

    try { await loadMojangVersions(); } catch (e) {}
    try { await refreshData(); } catch (e) {}
    try { await refreshMainProfileUI(); } catch (e) {}
    try { checkMsServerStatus(); } catch (e) {}
    try { setupDragAndDrop(); } catch (e) {}
    try { refreshServersList(false, false); } catch (e) {}

    setInterval(() => { if (currentCubeUser) refreshMyStats(); }, 20000);
    friendsPoller = setInterval(() => {
        if (document.getElementById('friends')?.classList.contains('active')) loadFriendsListAndRequests();
    }, 10000);

    const elapsed = Date.now() - loadingStart;
    const wait = Math.max(0, MIN_LOADING_MS - elapsed);
    setTimeout(hideLoadingScreen, wait);
}

window.addEventListener('pywebviewready', initApp);
setTimeout(() => { if (window.pywebview && window.pywebview.api) initApp(); }, 800);
setTimeout(hideLoadingScreen, 12000);
    </script>
</body>
</html>
"""


# ================= ЗАПУСК ПРИЛОЖЕНИЯ =================
def _check_env_keys() -> None:
    missing = []
    if not FIREBASE_API_KEY:
        missing.append("FIREBASE_API_KEY — авторизация, друзья, чаты, облачная статистика")
    if not RESEND_API_KEY and not (SMTP_USER and SMTP_PASSWORD):
        missing.append("RESEND_API_KEY / SMTP — отправка кодов подтверждения")
    if not CF_API_KEY:
        missing.append("CF_API_KEY — каталог CurseForge")
    if missing:
        log.warning("Предупреждение: отсутствуют ключи конфигурации .env:")
        for m in missing:
            log.warning("   • %s", m)


def main() -> None:
    global _APP_WINDOW

    _check_env_keys()

    try:
        log.info(
            "Версии библиотек: pywebview=%s | minecraft_launcher_lib=%s",
            getattr(webview, "__version__", "?"),
            getattr(minecraft_launcher_lib, "__version__", "?"),
        )
    except Exception:
        pass

    api = LauncherAPI()

    icon = ICON_PATH if os.path.exists(ICON_PATH) else None
    if not icon:
        log.info("Иконка приложения не найдена: %s", ICON_PATH)

    _APP_WINDOW = webview.create_window(
        title="Cube Launcher",
        html=HTML_CONTENT,
        js_api=api,
        width=1200,
        height=770,
        resizable=True,
        frameless=True,
        easy_drag=False,
    )

    try:
        webview.start(icon=icon, debug=False, gui="edgechromium")
    except Exception as e:
        log.warning("edgechromium недоступен (%s). Запуск в стандартном режиме...", e)
        try:
            webview.start(icon=icon, debug=False)
        except Exception as e2:
            log.error("Критическая ошибка запуска pywebview: %s", e2)
            raise


if __name__ == "__main__":
    main()
