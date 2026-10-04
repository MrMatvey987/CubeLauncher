

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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlparse, parse_qs
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import webview
import minecraft_launcher_lib
from dotenv import load_dotenv

# 1. Уникальный App ID для панели задач Windows
if sys.platform == 'win32':
    import ctypes
    myappid = 'cubelauncher.client.ver1.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

ICON_PATH = get_resource_path(r"C:\CubeLauncher\Launcher\images\icon.ico")

from config import (
    FIREBASE_API_KEY,
    FIREBASE_PROJECT_ID,
    MS_CLIENT_ID,
    MS_REDIRECT_URL,
    CF_API_KEY,
    RESEND_API_KEY,
    RESEND_FROM_EMAIL,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    CUBE_VISUALS_URL,
)

load_dotenv()

# ================= НАСТРОЙКИ FIREBASE И AUTH =================
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY", "")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "cube-1c237")
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID", "00000000402b5328")
MS_REDIRECT_URL = os.getenv("MS_REDIRECT_URL", "https://login.live.com/oauth20_desktop.srf")
CF_API_KEY = os.getenv("CF_API_KEY", "")

# ================= НАСТРОЙКИ ОТПРАВКИ ПОЧТЫ =================
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "Cube Launcher ")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.yandex.ru")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

HEADERS = {
    "User-Agent": "CubeLauncher/1.0.0 (https://cubevanilla.millida.trade)"
}

CF_HEADERS = {
    "x-api-key": CF_API_KEY,
    "Accept": "application/json",
    "User-Agent": "CubeLauncher/1.0.0"
}

SESSION = requests.Session()
retries = Retry(total=2, backoff_factor=0.2, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
SESSION.mount("https://", adapter)
SESSION.mount("http://", adapter)

if os.name == "nt":
    BASE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), ".cubelauncher")
else:
    BASE_DIR = os.path.join(os.path.expanduser("~"), ".cubelauncher")

LAUNCHER_DIR = os.path.join(BASE_DIR, "Launcher")
GAME_DIR = os.path.join(BASE_DIR, "Game")
INSTANCES_DIR = os.path.join(GAME_DIR, "instances")

os.makedirs(LAUNCHER_DIR, exist_ok=True)
os.makedirs(GAME_DIR, exist_ok=True)
os.makedirs(INSTANCES_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(LAUNCHER_DIR, "launcher_config.json")
ACCOUNTS_FILE = os.path.join(LAUNCHER_DIR, "accounts.json")
CUBE_USER_FILE = os.path.join(LAUNCHER_DIR, "cube_user.json")
USERS_REGISTRY_FILE = os.path.join(LAUNCHER_DIR, "users_registry.json")

CUBE_VISUALS_URL = "https://lybsonzfsfxhwgiltlht.supabase.co/storage/v1/object/public/Cube/mods/cubevisuals-1.0.jar"

_JAR_CACHE = {}
_MC_VERSIONS_CACHE = None

EMAIL_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Код подтверждения Cube Launcher</title>
</head>
<body style="margin: 0; padding: 0; background-color: #080708; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #f8fafc;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #080708; padding: 40px 10px;">
        <tr>
            <td align="center">
                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 520px; background-color: #181416; border: 1px solid #2e262a; border-radius: 16px; overflow: hidden;">
                    <tr>
                        <td align="center" style="padding: 32px 20px 20px 20px; border-bottom: 1px solid #2e262a;">
                            <div style="font-size: 20px; font-weight: 800; letter-spacing: 2px; color: #f97316; text-transform: uppercase;">
                                &#9632; CUBE LAUNCHER
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 32px 36px 20px 36px; text-align: center;">
                            <h1 style="font-size: 22px; font-weight: 700; margin: 0 0 12px 0; color: #ffffff;">{ACTION_TITLE}</h1>
                            <p style="font-size: 14px; line-height: 1.6; color: #9ca3af; margin: 0 0 24px 0;">
                                {ACTION_DESC}
                            </p>
                            <div style="background-color: #0c0a0b; border: 2px dashed #f97316; border-radius: 12px; padding: 18px 14px; margin: 0 auto 12px auto; max-width: 320px;">
                                <span style="font-size: 34px; font-weight: 800; letter-spacing: 8px; color: #f97316; font-family: monospace; user-select: all; -webkit-user-select: all;">
                                    {VERIFICATION_CODE}
                                </span>
                            </div>
                            <p style="font-size: 11px; color: #9ca3af; margin: 0 0 20px 0;">
                                💡 Нажмите дважды на код, чтобы выделить и скопировать его (Ctrl + C)
                            </p>
                            <p style="font-size: 12px; color: #6b7280; margin: 0; line-height: 1.5;">
                                &#9201; Код действителен в течение <b>5 минут</b>.
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 36px; background-color: #120e10; border-top: 1px solid #2e262a; text-align: center;">
                            <p style="font-size: 11px; color: #4b5563; margin: 0;">© 2026 Cube Launcher. Все права защищены.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

def clean_email_for_key(email):
    return re.sub(r'[^a-zA-Z0-9]', '_', email.strip().lower())

def send_html_mail(to_email, code, is_login=False):
    title = "Подтверждение входа" if is_login else "Подтверждение регистрации"
    desc = "Вы запросили вход в ваш профиль <b style='color: #f8fafc;'>Cube Launcher</b>. Введите код:" if is_login else "Вы запросили создание аккаунта в <b style='color: #f8fafc;'>Cube Launcher</b>. Введите код:"
    html_content = EMAIL_HTML_TEMPLATE.replace("{VERIFICATION_CODE}", code)\
                                      .replace("{ACTION_TITLE}", title)\
                                      .replace("{ACTION_DESC}", desc)
    if RESEND_API_KEY:
        try:
            res = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={"from": RESEND_FROM_EMAIL, "to": [to_email], "subject": f"Код: {code} — Cube Launcher", "html": html_content},
                timeout=8
            )
            if res.status_code in [200, 201]:
                return True, "Письмо отправлено!"
            return False, f"Ошибка Resend: {res.text}"
        except Exception as e:
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
            return False, f"Ошибка SMTP: {e}"

    print(f"\n[ТЕСТОВЫЙ РЕЖИМ] Код подтверждения для {to_email}: {code}\n")
    return True, f"Код сгенерирован (Тестовый режим: {code})"

def load_json(filepath, default_value):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Ошибка чтения {filepath}: {e}")
    return default_value

def save_json(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения {filepath}: {e}")

def download_file_safely(url, dest_path):
    try:
        res = SESSION.get(url, headers=HEADERS, stream=True, timeout=20)
        if res.status_code == 200:
            with open(dest_path, 'wb') as f:
                for chunk in res.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)
            return True
    except Exception as e:
        print(f"Ошибка скачивания {url}: {e}")
    return False

def calculate_sha1(filepath):
    try:
        h = hashlib.sha1()
        with open(filepath, 'rb') as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

def strip_mc_formatting(text):
    if not text:
        return ""
    return re.sub(r'§[0-9a-fk-or]', '', str(text))

def extract_jar_metadata(file_path):
    try:
        stat = os.stat(file_path)
        cache_key = (file_path, stat.st_mtime, stat.st_size)
        if cache_key in _JAR_CACHE:
            return _JAR_CACHE[cache_key]
    except Exception:
        cache_key = None

    base_name = os.path.basename(file_path)
    is_disabled = base_name.endswith(".disabled")
    clean_name = base_name[:-9] if is_disabled else base_name
    
    meta = {
        "filename": base_name,
        "clean_name": clean_name,
        "display_name": clean_name.replace(".jar", "").replace(".zip", ""),
        "version": "v1.0.0",
        "author": "Не указан",
        "icon": "",
        "enabled": not is_disabled
    }

    if not (file_path.endswith(".jar") or file_path.endswith(".jar.disabled")):
        meta["display_name"] = strip_mc_formatting(meta["display_name"])
        return meta

    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            names = set(z.namelist())
            if "fabric.mod.json" in names:
                with z.open("fabric.mod.json") as f:
                    data = json.load(f)
                    meta["display_name"] = data.get("name", meta["display_name"])
                    meta["version"] = data.get("version", meta["version"])
                    authors = data.get("authors", [])
                    if authors:
                        first_auth = authors[0]
                        meta["author"] = first_auth.get("name", str(first_auth)) if isinstance(first_auth, dict) else str(first_auth)
                    icon_path = data.get("icon")
                    if icon_path:
                        if isinstance(icon_path, dict):
                            icon_path = list(icon_path.values())[0]
                        if icon_path in names:
                            icon_bytes = z.read(icon_path)
                            meta["icon"] = f"data:image/png;base64,{base64.b64encode(icon_bytes).decode('utf-8')}"

            elif "quilt.mod.json" in names:
                with z.open("quilt.mod.json") as f:
                    data = json.load(f).get("quilt_loader", {})
                    meta_block = data.get("metadata", {})
                    meta["display_name"] = meta_block.get("name", meta["display_name"])
                    meta["version"] = data.get("version", meta["version"])
                    contributors = meta_block.get("contributors", {})
                    if contributors:
                        meta["author"] = list(contributors.keys())[0]
                    icon_path = meta_block.get("icon")
                    if icon_path and icon_path in names:
                        icon_bytes = z.read(icon_path)
                        meta["icon"] = f"data:image/png;base64,{base64.b64encode(icon_bytes).decode('utf-8')}"

            elif "META-INF/mods.toml" in names:
                text = z.read("META-INF/mods.toml").decode("utf-8", errors="ignore")
                for line in text.splitlines():
                    if "displayName" in line and "=" in line:
                        meta["display_name"] = line.split("=")[1].strip().strip('"\'')
                    elif "version=" in line and "=" in line:
                        meta["version"] = line.split("=")[1].strip().strip('"\'')
                    elif "authors=" in line and "=" in line:
                        meta["author"] = line.split("=")[1].strip().strip('"\'')
                    elif "logoFile=" in line and "=" in line:
                        logo = line.split("=")[1].strip().strip('"\'')
                        if logo in names:
                            icon_bytes = z.read(logo)
                            meta["icon"] = f"data:image/png;base64,{base64.b64encode(icon_bytes).decode('utf-8')}"

            if not meta["icon"]:
                for n in names:
                    if n.endswith("icon.png") or n.endswith("logo.png"):
                        icon_bytes = z.read(n)
                        meta["icon"] = f"data:image/png;base64,{base64.b64encode(icon_bytes).decode('utf-8')}"
                        break
    except Exception:
        pass

    meta["display_name"] = strip_mc_formatting(meta["display_name"])
    if cache_key:
        _JAR_CACHE[cache_key] = meta
    return meta

def ensure_cube_visuals_instance(config):
    instances = config.get("instances", [])
    cube_inst = next((i for i in instances if i.get("id") == "CubeVisuals"), None)
    
    if not cube_inst:
        cube_inst = {
            "id": "CubeVisuals",
            "name": "CubeVisuals",
            "mc_version": "1.21.11",
            "loader": "fabric",
            "loader_version": "latest",
            "icon": "✨"
        }
        instances.insert(0, cube_inst)
        config["instances"] = instances
        save_json(CONFIG_FILE, config)

    inst_dir = os.path.join(INSTANCES_DIR, "CubeVisuals")
    mods_dir = os.path.join(inst_dir, "mods")
    os.makedirs(mods_dir, exist_ok=True)
    for folder in ["shaderpacks", "resourcepacks", "datapacks"]:
        os.makedirs(os.path.join(inst_dir, folder), exist_ok=True)

    def bg_download():
        target_jar = os.path.join(mods_dir, "cubevisuals-1.0.jar")
        if not os.path.exists(target_jar) or os.path.getsize(target_jar) < 10240:
            download_file_safely(CUBE_VISUALS_URL, target_jar)

    threading.Thread(target=bg_download, daemon=True).start()
    return config

def load_config():
    default_config = {
        "launcher_path": LAUNCHER_DIR,
        "game_path": GAME_DIR,
        "active_instance_id": "CubeVisuals",
        "ram_mb": 4096,
        "enable_console": False,
        "jvm_args": "",
        "banner_path": "",
        "instances": [
            {
                "id": "CubeVisuals",
                "name": "CubeVisuals",
                "mc_version": "1.21.11",
                "loader": "fabric",
                "loader_version": "latest",
                "icon": "✨"
            }
        ]
    }
    cfg = load_json(CONFIG_FILE, default_config)
    if "ram_gb" in cfg and "ram_mb" not in cfg:
        cfg["ram_mb"] = cfg["ram_gb"] * 1024
    return ensure_cube_visuals_instance(cfg)

def load_accounts():
    default_accounts = [
        {"username": "MrMatvey987", "type": "offline", "active": True}
    ]
    return load_json(ACCOUNTS_FILE, default_accounts)


class LauncherAPI:
    def __init__(self):
        self.window = None
        self.config = load_config()
        self.accounts = load_accounts()
        self.cube_user = load_json(CUBE_USER_FILE, None)
        self.users_registry = load_json(USERS_REGISTRY_FILE, {})
        self._last_progress_time = 0
        self.game_process = None
        self.active_running_instance_id = None
        self._current_captcha = None

        self._current_watching_inst = None
        self._current_watching_type = 'mods'
        self._last_folder_snapshot = None
        threading.Thread(target=self._folder_watcher_loop, daemon=True).start()

    # ================= REALTIME FOLDER WATCHER =================
    def _folder_watcher_loop(self):
        while True:
            time.sleep(0.7)
            if self._current_watching_inst:
                target_dir = os.path.join(INSTANCES_DIR, self._current_watching_inst, self._current_watching_type or 'mods')
                if os.path.exists(target_dir):
                    try:
                        current_files = os.listdir(target_dir)
                        snapshot = []
                        for f in current_files:
                            fp = os.path.join(target_dir, f)
                            if os.path.isfile(fp):
                                st = os.stat(fp)
                                snapshot.append((f, st.st_mtime, st.st_size))
                        snapshot.sort()

                        if self._last_folder_snapshot is not None and snapshot != self._last_folder_snapshot:
                            self._last_folder_snapshot = snapshot
                            _JAR_CACHE.clear()
                            self._eval_js("silentRefreshModalFiles()")
                        elif self._last_folder_snapshot is None:
                            self._last_folder_snapshot = snapshot
                    except Exception:
                        pass

    def start_watching_instance(self, instance_id, resource_type='mods'):
        self._current_watching_inst = instance_id
        self._current_watching_type = resource_type
        self._last_folder_snapshot = None
        return {"status": "ok"}

    def stop_watching_instance(self):
        self._current_watching_inst = None
        self._last_folder_snapshot = None
        return {"status": "ok"}

    # ================= DRAG & DROP =================
    def save_dropped_file_data(self, instance_id, resource_type, filename, b64_content):
        try:
            target_dir = os.path.join(INSTANCES_DIR, instance_id, resource_type)
            os.makedirs(target_dir, exist_ok=True)
            raw = base64.b64decode(b64_content)
            target_file = os.path.join(target_dir, filename)
            with open(target_file, "wb") as f:
                f.write(raw)
            _JAR_CACHE.clear()
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _eval_js(self, script):
        if self.window:
            try:
                self.window.evaluate_js(script)
            except Exception:
                pass

    def _show_toast(self, message, toast_type="info"):
        self._eval_js(f"showToast({json.dumps(message)}, {json.dumps(toast_type)})")

    def _update_status(self, text, val=None):
        if val is not None:
            self._eval_js(f"updateDownloadStatus({json.dumps(text)}, {int(val)})")
        else:
            self._eval_js(f"updateDownloadStatus({json.dumps(text)})")

    def minimize(self):
        if self.window:
            self.window.minimize()

    def close(self):
        if self.window:
            self.window.destroy()

    def get_config(self):
        return self.config

    def save_settings_auto(self, ram_mb, enable_console, jvm_args, banner_path=None):
        try:
            self.config["ram_mb"] = int(ram_mb)
        except Exception:
            self.config["ram_mb"] = 4096
        self.config["enable_console"] = bool(enable_console)
        self.config["jvm_args"] = str(jvm_args or "")
        if banner_path is not None:
            self.config["banner_path"] = str(banner_path)
        save_json(CONFIG_FILE, self.config)
        return {"status": "ok"}

    def select_banner_file(self):
        if not self.window:
            return {"status": "error"}
        file_types = ('Медиа файлы (*.mp4;*.png;*.jpg;*.jpeg;*.webp;*.gif)', 'Все файлы (*.*)')
        result = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types)
        if result and len(result) > 0:
            path = result[0]
            self.config["banner_path"] = path
            save_json(CONFIG_FILE, self.config)
            return {"status": "ok", "path": path}
        return {"status": "cancel"}

    def clear_banner_file(self):
        self.config["banner_path"] = ""
        save_json(CONFIG_FILE, self.config)
        return {"status": "ok"}

    def get_banner_data(self):
        path = self.config.get("banner_path", "")
        if not path or not os.path.exists(path):
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

    # ================= FIRESTORE EMAIL OTP & FIREBASE AUTH =================
    def get_cube_user(self):
        return {"status": "ok", "user": self.cube_user}

    def generate_captcha(self):
        a = random.randint(3, 19)
        b = random.randint(2, 15)
        ans = a + b
        self._current_captcha = str(ans)
        return {"status": "ok", "question": f"Сколько будет {a} + {b} = ?"}

    def select_cube_avatar(self):
        if not self.window:
            return {"status": "error"}
        file_types = ('Изображения (*.png;*.jpg;*.jpeg;*.webp;*.gif)', 'Все файлы (*.*)')
        result = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types)
        if result and len(result) > 0:
            path = result[0]
            try:
                mime, _ = mimetypes.guess_type(path)
                if not mime:
                    mime = "image/png"
                with open(path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                    avatar_data = f"data:{mime};base64,{encoded}"

                if self.cube_user:
                    self.cube_user["avatar"] = avatar_data
                    save_json(CUBE_USER_FILE, self.cube_user)
                    self._eval_js("refreshMainProfileUI()")
                    self._show_toast("Аватарка успешно обновлена!", "success")
                    return {"status": "ok", "avatar": avatar_data}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "cancel"}

    def send_registration_code(self, username, email, password, captcha_answer):
        u = username.strip()
        em = email.strip().lower()
        pw = password.strip()

        if self._current_captcha and captcha_answer.strip() != self._current_captcha:
            return {"status": "error", "message": "Неверный ответ капчи! Попробуйте снова."}
        if len(u) < 3:
            return {"status": "error", "message": "Имя пользователя должно быть от 3 символов"}
        if "@" not in em or "." not in em:
            return {"status": "error", "message": "Введите корректный Email адрес"}
        if len(pw) < 6:
            return {"status": "error", "message": "Пароль должен содержать не менее 6 символов"}

        try:
            check_url = f"https://identitytoolkit.googleapis.com/v1/accounts:createAuthUri?key={FIREBASE_API_KEY}"
            check_res = SESSION.post(check_url, json={"identifier": em, "continueUri": "http://localhost"}, timeout=6)
            if check_res.status_code == 200 and check_res.json().get("registered"):
                return {"status": "error", "message": "Пользователь с такой почтой уже зарегистрирован!"}
        except Exception:
            pass

        clean_em = clean_email_for_key(em)
        now = int(time.time())
        firestore_url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/email_verifications/{clean_em}?key={FIREBASE_API_KEY}"
        
        try:
            get_doc = SESSION.get(firestore_url, timeout=5)
            if get_doc.status_code == 200:
                fields = get_doc.json().get("fields", {})
                resend_avail = int(fields.get("resend_available_at", {}).get("integerValue", 0))
                if now < resend_avail:
                    wait_sec = resend_avail - now
                    return {"status": "error", "message": f"Подождите {wait_sec} сек перед повторной отправкой!"}
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
                "attempts": {"integerValue": "0"}
            }
        }
        try:
            SESSION.patch(firestore_url, json=payload, timeout=6)
        except Exception as e:
            print("Ошибка Firestore:", e)

        ok, msg = send_html_mail(em, code, is_login=False)
        if not ok:
            return {"status": "error", "message": msg}

        self._show_toast("Код подтверждения отправлен на почту!", "success")
        return {"status": "ok", "cooldown": 60, "email": em}

    def verify_and_register(self, username, email, password, entered_code):
        u = username.strip()
        em = email.strip().lower()
        pw = password.strip()
        code_input = entered_code.strip()

        if len(code_input) != 6:
            return {"status": "error", "message": "Введите 6-значный код!"}

        clean_em = clean_email_for_key(em)
        firestore_url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/email_verifications/{clean_em}?key={FIREBASE_API_KEY}"
        
        try:
            get_doc = SESSION.get(firestore_url, timeout=6)
            if get_doc.status_code != 200:
                return {"status": "error", "message": "Код не найден или устарел. Запросите заново."}

            fields = get_doc.json().get("fields", {})
            real_code = fields.get("code", {}).get("stringValue", "")
            expires_at = int(fields.get("expires_at", {}).get("integerValue", 0))
            attempts = int(fields.get("attempts", {}).get("integerValue", 0))

            if int(time.time()) > expires_at:
                return {"status": "error", "message": "Срок действия кода истек! Запросите новый."}
            if attempts >= 5:
                return {"status": "error", "message": "Превышено число попыток! Запросите новый код."}
            if code_input != real_code:
                SESSION.patch(firestore_url, json={"fields": {"attempts": {"integerValue": str(attempts + 1)}}}, timeout=3)
                return {"status": "error", "message": f"Неверный код! Осталось попыток: {4 - attempts}"}
        except Exception as e:
            return {"status": "error", "message": f"Ошибка проверки: {e}"}

        try:
            sign_up_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
            payload = {"email": em, "password": pw, "returnSecureToken": True}
            res = SESSION.post(sign_up_url, json=payload, timeout=6)
            res_data = res.json()
            if res.status_code == 200:
                id_token = res_data.get("idToken")
                local_id = res_data.get("localId")

                update_url = f"https://identitytoolkit.googleapis.com/v1/accounts:update?key={FIREBASE_API_KEY}"
                avatar_url = f"https://minotar.net/helm/{u}/100.png"
                SESSION.post(update_url, json={
                    "idToken": id_token, "displayName": u, "photoUrl": avatar_url, "returnSecureToken": True
                }, timeout=5)

                self.cube_user = {
                    "username": u, "email": em, "id": local_id, "token": id_token,
                    "avatar": avatar_url, "bio": "Игрок Cube Launcher", "created_at": time.strftime("%Y-%m-%d")
                }
                save_json(CUBE_USER_FILE, self.cube_user)
                self.users_registry[u.lower()] = em
                save_json(USERS_REGISTRY_FILE, self.users_registry)

                try:
                    SESSION.delete(firestore_url, timeout=4)
                except Exception:
                    pass

                self._auto_add_offline_game_account(u)
                self._eval_js("refreshMainProfileUI()")
                self._show_toast(f"Аккаунт {u} успешно создан!", "success")
                return {"status": "ok", "user": self.cube_user}
            else:
                return {"status": "error", "message": res_data.get("error", {}).get("message", "Ошибка регистрации")}
        except Exception as e:
            return {"status": "error", "message": f"Ошибка сети: {e}"}

    def send_login_code(self, login_or_email, password, captcha_answer):
        lom = login_or_email.strip()
        pw = password.strip()

        if self._current_captcha and captcha_answer.strip() != self._current_captcha:
            return {"status": "error", "message": "Неверный ответ капчи!"}
        if not lom or not pw:
            return {"status": "error", "message": "Заполните все поля"}

        target_email = lom.lower() if "@" in lom else self.users_registry.get(lom.lower(), f"{lom.lower()}@cube.local")

        try:
            sign_in_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
            res = SESSION.post(sign_in_url, json={"email": target_email, "password": pw, "returnSecureToken": True}, timeout=6)
            if res.status_code != 200:
                return {"status": "error", "message": "Неверный логин/почта или пароль!"}
        except Exception as e:
            return {"status": "error", "message": f"Ошибка сети: {e}"}

        clean_em = clean_email_for_key(target_email)
        now = int(time.time())
        firestore_url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/email_verifications/{clean_em}?key={FIREBASE_API_KEY}"
        
        try:
            get_doc = SESSION.get(firestore_url, timeout=5)
            if get_doc.status_code == 200:
                fields = get_doc.json().get("fields", {})
                resend_avail = int(fields.get("resend_available_at", {}).get("integerValue", 0))
                if now < resend_avail:
                    wait_sec = resend_avail - now
                    return {"status": "error", "message": f"Подождите {wait_sec} сек перед повторной отправкой!"}
        except Exception:
            pass

        code = str(random.randint(100000, 999999))
        payload = {
            "fields": {
                "code": {"stringValue": code},
                "email": {"stringValue": target_email},
                "expires_at": {"integerValue": str(now + 300)},
                "resend_available_at": {"integerValue": str(now + 60)},
                "attempts": {"integerValue": "0"}
            }
        }
        try:
            SESSION.patch(firestore_url, json=payload, timeout=6)
        except Exception as e:
            print("Ошибка записи Firestore:", e)

        ok, msg = send_html_mail(target_email, code, is_login=True)
        if not ok:
            return {"status": "error", "message": msg}

        self._show_toast("Код для входа отправлен на почту!", "success")
        return {"status": "ok", "cooldown": 60, "email": target_email}

    def verify_and_login(self, login_or_email, password, entered_code):
        lom = login_or_email.strip()
        pw = password.strip()
        code_input = entered_code.strip()

        if len(code_input) != 6:
            return {"status": "error", "message": "Введите 6-значный код!"}

        target_email = lom.lower() if "@" in lom else self.users_registry.get(lom.lower(), f"{lom.lower()}@cube.local")
        clean_em = clean_email_for_key(target_email)
        firestore_url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/email_verifications/{clean_em}?key={FIREBASE_API_KEY}"

        try:
            get_doc = SESSION.get(firestore_url, timeout=6)
            if get_doc.status_code != 200:
                return {"status": "error", "message": "Код не найден или устарел. Запросите заново."}

            fields = get_doc.json().get("fields", {})
            real_code = fields.get("code", {}).get("stringValue", "")
            expires_at = int(fields.get("expires_at", {}).get("integerValue", 0))
            attempts = int(fields.get("attempts", {}).get("integerValue", 0))

            if int(time.time()) > expires_at:
                return {"status": "error", "message": "Срок действия кода истек! Запросите новый."}
            if attempts >= 5:
                return {"status": "error", "message": "Превышено число попыток! Запросите новый код."}
            if code_input != real_code:
                SESSION.patch(firestore_url, json={"fields": {"attempts": {"integerValue": str(attempts + 1)}}}, timeout=3)
                return {"status": "error", "message": f"Неверный код! Осталось попыток: {4 - attempts}"}
        except Exception as e:
            return {"status": "error", "message": f"Ошибка проверки: {e}"}

        try:
            sign_in_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
            payload = {"email": target_email, "password": pw, "returnSecureToken": True}
            res = SESSION.post(sign_in_url, json=payload, timeout=6)
            res_data = res.json()
            if res.status_code == 200:
                id_token = res_data.get("idToken")
                local_id = res_data.get("localId")
                u_name = res_data.get("displayName") or lom.split("@")[0]
                avatar_url = res_data.get("profilePicture") or f"https://minotar.net/helm/{u_name}/100.png"

                self.cube_user = {
                    "username": u_name, "email": res_data.get("email"), "id": local_id,
                    "token": id_token, "avatar": avatar_url, "bio": "Игрок Cube Launcher", "created_at": time.strftime("%Y-%m-%d")
                }
                save_json(CUBE_USER_FILE, self.cube_user)
                self.users_registry[u_name.lower()] = res_data.get("email")
                save_json(USERS_REGISTRY_FILE, self.users_registry)

                try:
                    SESSION.delete(firestore_url, timeout=4)
                except Exception:
                    pass

                self._auto_add_offline_game_account(u_name)
                self._eval_js("refreshMainProfileUI()")
                self._show_toast(f"Добро пожаловать, {u_name}!", "success")
                return {"status": "ok", "user": self.cube_user}
            return {"status": "error", "message": "Ошибка входа"}
        except Exception as e:
            return {"status": "error", "message": f"Ошибка сети: {e}"}

    def _auto_add_offline_game_account(self, username):
        for acc in self.accounts:
            acc["active"] = False
        existing = next((a for a in self.accounts if a.get("username") == username), None)
        if existing:
            existing["active"] = True
        else:
            self.accounts.append({
                "username": username,
                "type": "offline",
                "uuid": str(uuid.uuid3(uuid.NAMESPACE_DNS, username)),
                "active": True
            })
        save_json(ACCOUNTS_FILE, self.accounts)

    def logout_cube_account(self):
        self.cube_user = None
        if os.path.exists(CUBE_USER_FILE):
            try:
                os.remove(CUBE_USER_FILE)
            except Exception:
                pass
        self._eval_js("refreshMainProfileUI()")
        self._show_toast("Вы вышли из профиля Cube Launcher", "info")
        return {"status": "ok"}

    def update_cube_bio(self, bio):
        if not self.cube_user:
            return {"status": "error"}
        self.cube_user["bio"] = bio.strip()
        save_json(CUBE_USER_FILE, self.cube_user)
        self._eval_js("refreshMainProfileUI()")
        self._show_toast("Описание обновлено!", "success")
        return {"status": "ok"}

    # ================= MICROSOFT AUTH =================
    def check_microsoft_status(self):
        try:
            res = SESSION.get("https://login.live.com", timeout=2.0)
            return {"status": "ok", "connected": (res.status_code < 500)}
        except Exception:
            return {"status": "ok", "connected": False}

    def get_accounts(self):
        return self.accounts

    def add_account(self, username):
        u = username.strip()
        if not u:
            return {"status": "error", "message": "Никнейм не может быть пустым"}
        for acc in self.accounts:
            acc["active"] = False
        self.accounts.append({
            "username": u,
            "type": "offline",
            "uuid": str(uuid.uuid3(uuid.NAMESPACE_DNS, u)),
            "active": True
        })
        save_json(ACCOUNTS_FILE, self.accounts)
        return {"status": "ok", "accounts": self.accounts}

    def start_microsoft_login(self):
        try:
            login_url, state, code_verifier = minecraft_launcher_lib.microsoft_account.get_secure_login_data(
                MS_CLIENT_ID, MS_REDIRECT_URL
            )

            login_win = webview.create_window(
                "Авторизация Microsoft",
                login_url,
                width=540,
                height=680,
                resizable=False
            )

            handled = False

            def on_page_loaded(*args):
                nonlocal handled
                if handled:
                    return
                try:
                    win_instance = args[0] if args and isinstance(args[0], webview.Window) else login_win
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

                        self._show_toast("Авторизация успешна! Получение профиля...", "info")

                        def complete_auth():
                            try:
                                login_data = minecraft_launcher_lib.microsoft_account.complete_login(
                                    MS_CLIENT_ID, None, MS_REDIRECT_URL, auth_code, code_verifier
                                )
                                ms_name = login_data.get("name")
                                ms_uuid = login_data.get("id")
                                ms_token = login_data.get("access_token")

                                for acc in self.accounts:
                                    acc["active"] = False

                                self.accounts = [a for a in self.accounts if a.get("username") != ms_name]
                                self.accounts.append({
                                    "username": ms_name, "type": "microsoft", "uuid": ms_uuid, "token": ms_token, "active": True
                                })
                                save_json(ACCOUNTS_FILE, self.accounts)
                                self._eval_js("refreshData()")
                                self._show_toast(f"Добро пожаловать, {ms_name}!", "success")
                            except Exception as err:
                                self._show_toast(f"Ошибка входа: {err}", "error")

                        threading.Thread(target=complete_auth, daemon=True).start()

                    elif "error" in params:
                        handled = True
                        err_desc = params.get("error_description", ["Вход был отменён"])[0]
                        try:
                            win_instance.destroy()
                        except Exception:
                            pass
                        self._show_toast(f"Ошибка: {err_desc}", "error")

                except Exception as e:
                    print("Ошибка URL:", e)

            login_win.events.loaded += on_page_loaded
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def select_account(self, username):
        for acc in self.accounts:
            acc["active"] = (acc["username"] == username)
        save_json(ACCOUNTS_FILE, self.accounts)
        return {"status": "ok", "accounts": self.accounts}

    def delete_account(self, username):
        self.accounts = [a for a in self.accounts if a["username"] != username]
        if self.accounts and not any(a.get("active") for a in self.accounts):
            self.accounts[0]["active"] = True
        save_json(ACCOUNTS_FILE, self.accounts)
        return {"status": "ok", "accounts": self.accounts}

    # ================= СБОРКИ / ВЕРСИИ =================
    def get_mc_versions(self):
        global _MC_VERSIONS_CACHE
        if _MC_VERSIONS_CACHE:
            return _MC_VERSIONS_CACHE
        try:
            versions = minecraft_launcher_lib.utils.get_version_list()
            _MC_VERSIONS_CACHE = [v["id"] for v in versions if v["type"] == "release"][:40]
            return _MC_VERSIONS_CACHE
        except Exception:
            return ["1.21.11", "1.21.1", "1.20.4", "1.20.1", "1.19.4", "1.16.5"]

    def get_loader_versions(self, loader_type, mc_version):
        try:
            if loader_type == "fabric":
                res = SESSION.get(f"https://meta.fabricmc.net/v2/versions/loader/{mc_version}", headers=HEADERS, timeout=4)
                if res.status_code == 200:
                    return [item["loader"]["version"] for item in res.json()]
            elif loader_type == "quilt":
                res = SESSION.get(f"https://meta.quiltmc.org/v3/versions/loader/{mc_version}", headers=HEADERS, timeout=4)
                if res.status_code == 200:
                    return [item["loader"]["version"] for item in res.json()]
            elif loader_type == "forge":
                fv = minecraft_launcher_lib.forge.find_forge_version(mc_version)
                if fv:
                    return [fv]
        except Exception:
            pass
        return ["latest"]

    def save_instance(self, instance_data):
        instances = self.config.get("instances", [])
        inst_id = instance_data.get("id")
        if inst_id:
            existing = next((i for i in instances if i["id"] == inst_id), None)
            if existing:
                existing.update(instance_data)
        else:
            inst_id = f"inst_{int(time.time())}"
            instance_data["id"] = inst_id
            instances.append(instance_data)

        inst_dir = os.path.join(INSTANCES_DIR, inst_id)
        os.makedirs(inst_dir, exist_ok=True)
        for folder in ["mods", "shaderpacks", "resourcepacks", "datapacks"]:
            os.makedirs(os.path.join(inst_dir, folder), exist_ok=True)

        self.config["instances"] = instances
        save_json(CONFIG_FILE, self.config)
        return {"status": "ok", "instances": instances, "id": inst_id}

    def select_instance(self, instance_id):
        self.config["active_instance_id"] = instance_id
        save_json(CONFIG_FILE, self.config)
        return {"status": "ok"}

    def delete_instance(self, instance_id):
        instances = self.config.get("instances", [])
        self.config["instances"] = [i for i in instances if i["id"] != instance_id]
        if self.config["active_instance_id"] == instance_id:
            if self.config["instances"]:
                self.config["active_instance_id"] = self.config["instances"][0]["id"]
            else:
                self.config["active_instance_id"] = "CubeVisuals"
        
        inst_dir = os.path.join(INSTANCES_DIR, instance_id)
        if os.path.exists(inst_dir):
            try:
                shutil.rmtree(inst_dir)
            except Exception:
                pass

        self.config = ensure_cube_visuals_instance(self.config)
        save_json(CONFIG_FILE, self.config)
        return {"status": "ok", "instances": self.config["instances"]}

    def open_instance_folder(self, instance_id):
        inst_dir = os.path.join(INSTANCES_DIR, instance_id)
        os.makedirs(inst_dir, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(inst_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", inst_dir])
            else:
                subprocess.Popen(["xdg-open", inst_dir])
        except Exception:
            pass
        return {"status": "ok"}

    def get_instance_files(self, instance_id, resource_type):
        inst_dir = os.path.join(INSTANCES_DIR, instance_id, resource_type)
        if not os.path.exists(inst_dir):
            return []
        files = []
        for f in os.listdir(inst_dir):
            full_path = os.path.join(inst_dir, f)
            if os.path.isfile(full_path):
                meta = extract_jar_metadata(full_path)
                files.append(meta)
        return files

    def toggle_instance_file(self, instance_id, resource_type, filename):
        inst_dir = os.path.join(INSTANCES_DIR, instance_id, resource_type)
        old_path = os.path.join(inst_dir, filename)
        if filename.endswith(".disabled"):
            new_path = os.path.join(inst_dir, filename[:-9])
        else:
            new_path = os.path.join(inst_dir, filename + ".disabled")
        if os.path.exists(old_path):
            try:
                os.rename(old_path, new_path)
                _JAR_CACHE.clear()
            except Exception:
                pass
        return {"status": "ok"}

    def delete_instance_file(self, instance_id, resource_type, filename):
        inst_dir = os.path.join(INSTANCES_DIR, instance_id, resource_type)
        file_path = os.path.join(inst_dir, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                _JAR_CACHE.clear()
            except Exception:
                pass
        return {"status": "ok"}

    def install_modpack_as_instance(self, project_id, title, icon_url, platform="modrinth"):
        def run():
            try:
                self._update_status(f"Подготовка модпака {title}...", 10)
                safe_name = "".join([c for c in title if c.isalnum() or c in (' ', '_', '-')]).rstrip()
                inst_id = f"modpack_{int(time.time())}"
                new_inst = {
                    "id": inst_id, "name": safe_name, "mc_version": "1.21.1",
                    "loader": "fabric", "loader_version": "latest", "icon": "📦"
                }
                self.save_instance(new_inst)
                self._update_status(f"Модпак {safe_name} создан!", 100)
                self._show_toast(f"Модпак {safe_name} добавлен в установки!", "success")
                self._eval_js("refreshData()")
                time.sleep(1.2)
                self._eval_js("hideDownloadStatus()")
            except Exception as e:
                self._show_toast(f"Ошибка создания модпака: {e}", "error")

        threading.Thread(target=run, daemon=True).start()
        return {"status": "ok"}

    def check_instance_updates(self, instance_id):
        inst = next((i for i in self.config.get("instances", []) if i["id"] == instance_id), None)
        if not inst:
            return {"status": "error", "message": "Сборка не найдена"}

        mods_dir = os.path.join(INSTANCES_DIR, instance_id, "mods")
        if not os.path.exists(mods_dir):
            return {"status": "ok", "updates_count": 0, "updates": {}}

        mc_ver = inst.get("mc_version", "1.21.11")
        loader = inst.get("loader", "vanilla").lower()
        loaders_list = [loader] if loader != "vanilla" else []
        if loader == "quilt":
            loaders_list.append("fabric")

        file_hashes = {}
        for f in os.listdir(mods_dir):
            if f.endswith(".jar") or f.endswith(".jar.disabled"):
                fpath = os.path.join(mods_dir, f)
                sha = calculate_sha1(fpath)
                if sha:
                    file_hashes[sha] = f

        if not file_hashes:
            return {"status": "ok", "updates_count": 0, "updates": {}}

        try:
            body = {
                "hashes": list(file_hashes.keys()),
                "algorithm": "sha1",
                "loaders": loaders_list,
                "game_versions": [mc_ver]
            }
            res = SESSION.post("https://api.modrinth.com/v2/version_files/update", json=body, headers=HEADERS, timeout=8)
            if res.status_code == 200:
                data = res.json()
                updates = {}
                for old_hash, ver_data in data.items():
                    local_fname = file_hashes.get(old_hash)
                    if not local_fname:
                        continue
                    files = ver_data.get("files", [])
                    primary = next((fl for fl in files if fl.get("primary")), files[0] if files else None)
                    if not primary:
                        continue
                    new_hash = primary.get("hashes", {}).get("sha1")
                    if new_hash and new_hash != old_hash:
                        updates[local_fname] = {
                            "old_filename": local_fname,
                            "new_filename": primary.get("filename"),
                            "new_version": ver_data.get("version_number", "Новая версия"),
                            "url": primary.get("url")
                        }
                return {"status": "ok", "updates_count": len(updates), "updates": updates}
        except Exception as e:
            return {"status": "error", "message": str(e)}

        return {"status": "ok", "updates_count": 0, "updates": {}}

    def update_single_mod(self, instance_id, old_filename, download_url, new_filename):
        mods_dir = os.path.join(INSTANCES_DIR, instance_id, "mods")
        old_path = os.path.join(mods_dir, old_filename)
        new_path = os.path.join(mods_dir, new_filename)

        if old_filename.endswith(".disabled") and not new_filename.endswith(".disabled"):
            new_path += ".disabled"
            new_filename += ".disabled"

        if download_file_safely(download_url, new_path):
            if os.path.exists(old_path) and old_path != new_path:
                try:
                    os.remove(old_path)
                except Exception:
                    pass
            _JAR_CACHE.clear()
            return {"status": "ok", "new_filename": new_filename}
        return {"status": "error", "message": "Не удалось скачать файл"}

    def update_all_mods(self, instance_id):
        def run():
            try:
                self._update_status("Проверка обновлений модов...", 10)
                check_res = self.check_instance_updates(instance_id)
                updates = check_res.get("updates", {})
                total = len(updates)
                if total == 0:
                    self._show_toast("Все моды уже обновлены!", "info")
                    self._eval_js("hideDownloadStatus()")
                    return

                self._update_status(f"Обновление модов (0/{total})...", 20)
                updated_count = 0
                for idx, (old_f, info) in enumerate(updates.items()):
                    self._update_status(f"Обновление ({idx+1}/{total}): {info['new_filename']}...", 20 + int(((idx+1)/total)*75))
                    res = self.update_single_mod(instance_id, old_f, info["url"], info["new_filename"])
                    if res.get("status") == "ok":
                        updated_count += 1

                self._update_status("Обновление модов завершено!", 100)
                self._show_toast(f"Успешно обновлено модов: {updated_count} из {total}!", "success")
                self._eval_js("refreshModalInstanceFiles()")
                time.sleep(1.2)
                self._eval_js("hideDownloadStatus()")
            except Exception as e:
                self._show_toast(f"Ошибка обновления: {e}", "error")

        threading.Thread(target=run, daemon=True).start()
        return {"status": "ok"}

    def fetch_resources(self, query="", project_type="mods", loader="", mc_version="", page=1, limit=10, platform="modrinth"):
        if platform == "curseforge":
            return self._fetch_curseforge(query, project_type, loader, mc_version, page, limit)
        return self._fetch_modrinth(query, project_type, loader, mc_version, page, limit)

    def _fetch_modrinth(self, query, project_type, loader, mc_version, page, limit):
        type_map = {
            "mods": "mod", "shaders": "shader", "resourcepacks": "resourcepack",
            "datapacks": "datapack", "modpacks": "modpack", "mod": "mod"
        }
        p_type = type_map.get(project_type, "mod")
        facets_list = [[f"project_type:{p_type}"]]
        if loader and loader != "vanilla" and p_type in ["mod", "modpack"]:
            facets_list.append([f"categories:{loader}"])
        if mc_version:
            facets_list.append([f"versions:{mc_version}"])

        offset = (max(1, page) - 1) * limit
        url = "https://api.modrinth.com/v2/search"
        params = {"query": query or "", "facets": json.dumps(facets_list), "limit": limit, "offset": offset}
        try:
            res = SESSION.get(url, params=params, headers=HEADERS, timeout=5)
            if res.status_code == 200:
                data = res.json()
                hits = data.get("hits", [])
                total_hits = data.get("total_hits", 0)
                items = []
                for h in hits:
                    items.append({
                        "id": h["project_id"], "platform": "modrinth", "title": h.get("title", "Без названия"),
                        "desc": h.get("description", "Описание отсутствует"), "icon": h.get("icon_url", ""),
                        "downloads": h.get("downloads", 0), "author": h.get("author", "Неизвестen"), "project_type": h.get("project_type")
                    })
                return {"status": "ok", "items": items, "total": total_hits, "page": page, "total_pages": math.ceil(total_hits / limit) if total_hits > 0 else 1}
        except Exception:
            pass
        return {"status": "ok", "items": [], "total": 0, "page": 1, "total_pages": 1}

    def _fetch_curseforge(self, query, project_type, loader, mc_version, page, limit):
        cf_class_map = {"mods": 6, "mod": 6, "shaders": 6552, "shader": 6552, "resourcepacks": 12, "resourcepack": 12, "datapacks": 6, "datapack": 6, "modpacks": 4471, "modpack": 4471}
        loader_map = {"forge": 1, "fabric": 4, "quilt": 5, "neoforge": 6}
        offset = (max(1, page) - 1) * limit
        params = {"gameId": 432, "classId": cf_class_map.get(project_type, 6), "searchFilter": query or "", "index": offset, "pageSize": limit, "sortField": 2, "sortOrder": "desc"}
        if mc_version:
            params["gameVersion"] = mc_version
        if loader and loader.lower() in loader_map and project_type in ["mods", "mod", "modpacks", "modpack"]:
            params["modLoaderType"] = loader_map[loader.lower()]

        try:
            res = SESSION.get("https://api.curseforge.com/v1/mods/search", params=params, headers=CF_HEADERS, timeout=5)
            if res.status_code == 200:
                data = res.json()
                raw_items = data.get("data", [])
                total_hits = data.get("pagination", {}).get("totalCount", 0)
                items = []
                for m in raw_items:
                    logo = m.get("logo", {})
                    items.append({
                        "id": str(m["id"]), "platform": "curseforge", "title": m.get("name", "Без названия"),
                        "desc": m.get("summary", "Описание отсутствует"), "icon": logo.get("url") or logo.get("thumbnailUrl") or "",
                        "downloads": m.get("downloadCount", 0), "author": m["authors"][0]["name"] if m.get("authors") else "Неизвестен", "project_type": project_type
                    })
                return {"status": "ok", "items": items, "total": total_hits, "page": page, "total_pages": math.ceil(total_hits / limit) if total_hits > 0 else 1}
        except Exception:
            pass
        return {"status": "ok", "items": [], "total": 0, "page": 1, "total_pages": 1}

    def get_resource_details(self, project_id, platform="modrinth"):
        try:
            if platform == "curseforge":
                res_p = SESSION.get(f"https://api.curseforge.com/v1/mods/{project_id}", headers=CF_HEADERS, timeout=6)
                res_v = SESSION.get(f"https://api.curseforge.com/v1/mods/{project_id}/files", headers=CF_HEADERS, timeout=6)
                if res_p.status_code == 200 and res_v.status_code == 200:
                    p_data = res_p.json().get("data", {})
                    v_data = res_v.json().get("data", [])
                    versions = []
                    for f in v_data[:35]:
                        dl_url = f.get("downloadUrl") or f"https://www.curseforge.com/api/v1/mods/{project_id}/files/{f['id']}/download"
                        versions.append({
                            "id": str(f["id"]), "name": f.get("displayName", f.get("fileName")), "version_number": f.get("fileName"),
                            "game_versions": f.get("gameVersions", []), "loaders": [g for g in f.get("gameVersions", []) if g.lower() in ["forge", "fabric", "quilt", "neoforge"]],
                            "files": [{"url": dl_url, "filename": f.get("fileName")}]
                        })
                    return {
                        "status": "ok",
                        "project": {
                            "id": str(p_data["id"]), "title": p_data.get("name"),
                            "icon": p_data.get("logo", {}).get("url") or "", "project_type": "CurseForge Mod",
                            "gallery": [s.get("url") for s in p_data.get("screenshots", []) if s.get("url")]
                        },
                        "versions": versions
                    }
            else:
                res_p = SESSION.get(f"https://api.modrinth.com/v2/project/{project_id}", headers=HEADERS, timeout=6)
                res_v = SESSION.get(f"https://api.modrinth.com/v2/project/{project_id}/version", headers=HEADERS, timeout=6)
                if res_p.status_code == 200 and res_v.status_code == 200:
                    p_data = res_p.json()
                    v_data = res_v.json()
                    return {
                        "status": "ok",
                        "project": {
                            "id": p_data["id"], "title": p_data["title"], "icon": p_data.get("icon_url", ""),
                            "project_type": p_data.get("project_type", "mod"), "gallery": [g["url"] for g in p_data.get("gallery", []) if "url" in g]
                        },
                        "versions": [
                            {
                                "id": ver["id"], "name": ver["name"], "version_number": ver["version_number"],
                                "game_versions": ver.get("game_versions", []), "loaders": ver.get("loaders", []), "files": ver.get("files", [])
                            } for ver in v_data[:35]
                        ]
                    }
        except Exception as e:
            print("Error details:", e)
        return {"status": "error"}

    def auto_install_resource(self, project_id, platform="modrinth", instance_id=None, resource_type="mods"):
        active_inst_id = instance_id or self.config.get("active_instance_id")
        inst = next((i for i in self.config.get("instances", []) if i["id"] == active_inst_id), None)
        if not inst and self.config.get("instances"):
            inst = self.config["instances"][0]
        if not inst:
            return {"status": "error", "message": "Сборка не найдена!"}

        mc_ver = inst.get("mc_version", "1.21.11")
        loader = inst.get("loader", "vanilla").lower()
        is_mod = (resource_type == "mods")
        major_minor = ".".join(mc_ver.split(".")[:2]) if "." in mc_ver else mc_ver

        try:
            if platform == "curseforge":
                res_v = SESSION.get(f"https://api.curseforge.com/v1/mods/{project_id}/files", headers=CF_HEADERS, timeout=6)
                if res_v.status_code == 200:
                    files = res_v.json().get("data", [])
                    matched_file = None
                    for f in files:
                        g_vers = [str(g).lower() for g in f.get("gameVersions", [])]
                        mc_ok = (not mc_ver) or (mc_ver.lower() in g_vers) or any(major_minor in g for g in g_vers) or (not is_mod)
                        ld_ok = (loader == "vanilla") or (loader in g_vers) or (loader == "quilt" and "fabric" in g_vers) if is_mod else True
                        if mc_ok and ld_ok:
                            dl_url = f.get("downloadUrl") or f"https://www.curseforge.com/api/v1/mods/{project_id}/files/{f['id']}/download"
                            matched_file = {"url": dl_url, "filename": f.get("fileName")}
                            break
                    if not matched_file and not is_mod and files:
                        f = files[0]
                        matched_file = {"url": f.get("downloadUrl") or f"https://www.curseforge.com/api/v1/mods/{project_id}/files/{f['id']}/download", "filename": f.get("fileName")}
                    if matched_file:
                        self.install_resource(inst["id"], matched_file["url"], matched_file["filename"], resource_type)
                        return {"status": "ok", "filename": matched_file["filename"]}
            else:
                res_v = SESSION.get(f"https://api.modrinth.com/v2/project/{project_id}/version", headers=HEADERS, timeout=6)
                if res_v.status_code == 200:
                    versions = res_v.json()
                    matched_file = None
                    for ver in versions:
                        v_mc = ver.get("game_versions", [])
                        v_ld = [l.lower() for l in ver.get("loaders", [])]
                        mc_ok = (not mc_ver) or (mc_ver in v_mc) or any(major_minor in g for g in v_mc) or (not is_mod)
                        ld_ok = (loader == "vanilla") or (not v_ld) or (loader in v_ld) or (loader == "quilt" and "fabric" in v_ld) if is_mod else True
                        if mc_ok and ld_ok:
                            f = next((fl for fl in ver.get("files", []) if fl.get("primary")), None) or (ver.get("files", [])[0] if ver.get("files") else None)
                            if f:
                                matched_file = f
                                break
                    if not matched_file and not is_mod and versions:
                        ver = versions[0]
                        matched_file = next((fl for fl in ver.get("files", []) if fl.get("primary")), None) or (ver.get("files", [])[0] if ver.get("files") else None)
                    if matched_file:
                        self.install_resource(inst["id"], matched_file["url"], matched_file["filename"], resource_type)
                        return {"status": "ok", "filename": matched_file["filename"]}
            return {"status": "not_found", "message": f"Не удалось подобрать файл под {mc_ver}."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def install_resource(self, instance_id, download_url, file_name, resource_type):
        def run():
            try:
                target_dir = os.path.join(INSTANCES_DIR, instance_id, resource_type)
                os.makedirs(target_dir, exist_ok=True)
                file_path = os.path.join(target_dir, file_name)

                self._update_status(f"Загрузка {file_name}...", 10)
                res = SESSION.get(download_url, headers=HEADERS, stream=True, timeout=20)
                total_size = int(res.headers.get('content-length', 0))
                downloaded = 0

                with open(file_path, 'wb') as f:
                    for chunk in res.iter_content(chunk_size=16384):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                prog = int((downloaded / total_size) * 100)
                                self._update_status(f"Загрузка {file_name}... {prog}%", prog)

                _JAR_CACHE.clear()
                self._update_status(f"Установлено: {file_name}", 100)
                self._show_toast(f"Успешно установлен: {file_name}", "success")
                self._eval_js("refreshModalInstanceFiles()")
                time.sleep(1.2)
                self._eval_js("hideDownloadStatus()")
            except Exception as e:
                self._update_status(f"Ошибка: {e}", 0)
                self._show_toast(f"Ошибка установки: {e}", "error")

        threading.Thread(target=run, daemon=True).start()
        return {"status": "ok"}

    def kill_game(self):
        proc = self.game_process
        self.game_process = None
        self.active_running_instance_id = None
        if proc:
            try:
                proc.terminate()
                time.sleep(0.15)
                if proc.poll() is None:
                    proc.kill()
            except Exception as e:
                print("Ошибка остановки:", e)
        self._eval_js("setPlayButtonState('default')")
        self._eval_js("hideDownloadStatus()")
        self._show_toast("Игра остановлена", "info")
        return {"status": "ok"}

    def launch_active_game(self, instance_id=None):
        if self.game_process and self.game_process.poll() is None:
            self.kill_game()
            return {"status": "killed"}

        active_inst_id = instance_id or self.config.get("active_instance_id")
        inst = next((i for i in self.config.get("instances", []) if i["id"] == active_inst_id), None)
        if not inst:
            inst = self.config["instances"][0] if self.config.get("instances") else None
        if not inst:
            self._show_toast("Сборка не найдена!", "error")
            return {"status": "error", "message": "Сборка не найдена!"}

        active_accs = [a for a in self.accounts if a.get("active")]
        if not active_accs:
            self._show_toast("Выберите аккаунт перед запуском!", "error")
            return {"status": "error", "message": "Выберите аккаунт перед запуском!"}

        active_acc = active_accs[0]
        ram_mb = self.config.get("ram_mb", 4096)
        inst_dir = os.path.join(INSTANCES_DIR, inst["id"])
        os.makedirs(inst_dir, exist_ok=True)
        self.active_running_instance_id = inst["id"]

        def run():
            proc = None
            try:
                jvm_args = [f"-Xmx{ram_mb}M", f"-Xms{ram_mb}M"]
                custom_jvm = (self.config.get("jvm_args") or "").strip()
                if custom_jvm:
                    try:
                        jvm_args.extend(shlex.split(custom_jvm))
                    except Exception:
                        jvm_args.extend(custom_jvm.split())

                options = {
                    "username": active_acc["username"], "uuid": active_acc.get("uuid", "00000000-0000-0000-0000-000000000000"),
                    "token": active_acc.get("token", "0"), "gameDirectory": inst_dir, "jvmArguments": jvm_args
                }
                java_path = shutil.which("java") or shutil.which("javaw")
                if java_path:
                    options["executablePath"] = java_path

                progress_data = {"max": 100, "curr": 0}
                def set_status(t): self._update_status(t)
                def set_max(m): progress_data["max"] = m if m > 0 else 100
                def set_progress(p):
                    now = time.time()
                    progress_data["curr"] = p
                    if now - self._last_progress_time > 0.08:
                        self._last_progress_time = now
                        pct = int((progress_data["curr"] / progress_data["max"]) * 100)
                        self._eval_js(f"updateDownloadProgress({min(100, max(0, pct))})")

                callback = {"setStatus": set_status, "setProgress": set_progress, "setMax": set_max}
                self._eval_js(f"setPlayButtonState('installing', '{inst['id']}')")

                mc_ver = inst.get("mc_version", "1.21.11")
                loader = inst.get("loader", "vanilla").lower()
                loader_ver = inst.get("loader_version", "latest")
                target_version = None

                installed_versions = [v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(GAME_DIR)]

                if loader == "fabric":
                    fab_match = [v for v in installed_versions if "fabric" in v.lower() and mc_ver in v]
                    if fab_match:
                        target_version = fab_match[0]
                    else:
                        if mc_ver not in installed_versions:
                            set_status(f"Загрузка Minecraft {mc_ver}...")
                            minecraft_launcher_lib.install.install_minecraft_version(mc_ver, GAME_DIR, callback=callback)
                        set_status(f"Установка Fabric ({mc_ver})...")
                        minecraft_launcher_lib.fabric.install_fabric(mc_ver, GAME_DIR, loader_version=None if loader_ver == "latest" else loader_ver, callback=callback)
                        installed = minecraft_launcher_lib.utils.get_installed_versions(GAME_DIR)
                        fab = [v["id"] for v in installed if "fabric" in v["id"].lower() and mc_ver in v["id"]]
                        target_version = fab[0] if fab else mc_ver

                elif loader == "quilt":
                    quilt_match = [v for v in installed_versions if "quilt" in v.lower() and mc_ver in v]
                    if quilt_match:
                        target_version = quilt_match[0]
                    else:
                        if mc_ver not in installed_versions:
                            set_status(f"Загрузка Minecraft {mc_ver}...")
                            minecraft_launcher_lib.install.install_minecraft_version(mc_ver, GAME_DIR, callback=callback)
                        set_status(f"Установка Quilt ({mc_ver})...")
                        minecraft_launcher_lib.quilt.install_quilt(mc_ver, GAME_DIR, loader_version=None if loader_ver == "latest" else loader_ver, callback=callback)
                        installed = minecraft_launcher_lib.utils.get_installed_versions(GAME_DIR)
                        qlt = [v["id"] for v in installed if "quilt" in v["id"].lower() and mc_ver in v["id"]]
                        target_version = qlt[0] if qlt else mc_ver

                elif loader == "forge":
                    fv = minecraft_launcher_lib.forge.find_forge_version(mc_ver)
                    if fv and fv in installed_versions:
                        target_version = fv
                    elif fv:
                        if mc_ver not in installed_versions:
                            set_status(f"Загрузка Minecraft {mc_ver}...")
                            minecraft_launcher_lib.install.install_minecraft_version(mc_ver, GAME_DIR, callback=callback)
                        set_status(f"Установка Forge ({mc_ver})...")
                        minecraft_launcher_lib.forge.install_forge_version(fv, GAME_DIR, callback=callback)
                        target_version = fv
                    else:
                        target_version = mc_ver
                else:
                    if mc_ver in installed_versions:
                        target_version = mc_ver
                    else:
                        set_status(f"Загрузка Minecraft {mc_ver}...")
                        minecraft_launcher_lib.install.install_minecraft_version(mc_ver, GAME_DIR, callback=callback)
                        target_version = mc_ver

                self._eval_js(f"setPlayButtonState('launching', '{inst['id']}')")
                set_status("Запуск игры...")

                cmd = minecraft_launcher_lib.command.get_minecraft_command(version=target_version, minecraft_directory=GAME_DIR, options=options)

                if self.config.get("enable_console"):
                    proc = subprocess.Popen(cmd)
                else:
                    proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

                self.game_process = proc
                self._eval_js(f"setPlayButtonState('running', '{inst['id']}')")
                self._show_toast("Minecraft запущен!", "success")
                set_status("Игра работает!")
                time.sleep(1.5)
                self._eval_js("hideDownloadStatus()")

                if proc:
                    proc.wait()

            except Exception as e:
                print(f"Ошибка запуска: {e}")
                self._update_status(f"Ошибка: {e}", 0)
                self._show_toast(f"Ошибка запуска: {e}", "error")
            finally:
                self.game_process = None
                self.active_running_instance_id = None
                self._eval_js("setPlayButtonState('default')")
                self._eval_js("hideDownloadStatus()")
                self._show_toast("Игра закрыта", "info")

        threading.Thread(target=run, daemon=True).start()
        return {"status": "ok"}


HTML_CONTENT = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Cube Launcher</title>
    <style>
        :root {
            --bg-main: #0c0a0b;
            --bg-card: #181416;
            --bg-card-hover: #231c20;
            --accent: #f97316;
            --accent-glow: rgba(249, 115, 22, 0.25);
            --text-primary: #f8fafc;
            --text-secondary: #9ca3af;
            --border: #2e262a;
            --radius-lg: 16px;
            --radius-md: 10px;
            --radius-sm: 6px;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            user-select: none;
            -webkit-user-select: none;
        }

        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #080708; border-radius: 4px; }
        ::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 4px;
            border: 1px solid rgba(249, 115, 22, 0.1);
        }
        ::-webkit-scrollbar-thumb:hover { background: var(--accent); }

        body {
            background-color: var(--bg-main);
            color: var(--text-primary);
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            border-radius: var(--radius-lg);
            border: 1px solid var(--border);
            transform: translateZ(0);
        }

        .titlebar {
            height: 48px;
            background: #080708;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 16px;
            border-bottom: 1px solid var(--border);
            position: relative;
            z-index: 10001;
            cursor: move;
        }

        .titlebar-brand {
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 800;
            font-size: 14px;
            letter-spacing: 1.2px;
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
            border-radius: 50%;
            border: none;
            background: var(--bg-card);
            color: var(--text-secondary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            transition: background 0.15s;
        }

        .win-btn:hover { background: var(--border); color: var(--text-primary); }
        .win-btn.close:hover { background: #ef4444; color: white; }

        .app-body { display: flex; flex: 1; overflow: hidden; margin-bottom: 38px; }

        .sidebar {
            width: 230px;
            background: #080708;
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
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .nav-btn:hover { background: var(--bg-card); color: var(--text-primary); }
        .nav-btn.active { background: var(--accent-glow); border-color: var(--accent); color: var(--accent); }

        .sidebar-profile {
            margin-top: auto;
            background: #141012;
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 10px 12px;
            display: flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
            transition: all 0.15s;
        }
        .sidebar-profile:hover {
            border-color: var(--accent);
            background: #1e171b;
            transform: translateY(-2px);
        }
        .sidebar-profile-avatar {
            width: 38px;
            height: 38px;
            border-radius: 50%;
            object-fit: cover;
            border: 2px solid var(--accent);
            background: #231c20;
            flex-shrink: 0;
        }
        .sidebar-profile-info {
            display: flex;
            flex-direction: column;
            overflow: hidden;
            flex: 1;
        }
        .sidebar-profile-name {
            font-weight: 700;
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

        .content { flex: 1; padding: 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; }
        .page { display: none; flex-direction: column; gap: 16px; height: 100%; }
        .page.active { display: flex; }

        .ms-warning-banner {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            background: rgba(234, 179, 8, 0.12);
            border: 1px solid rgba(234, 179, 8, 0.4);
            border-radius: var(--radius-md);
            color: #fef08a;
            font-size: 13px;
            font-weight: 600;
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .banner-container {
            position: relative;
            width: 100%;
            min-height: 320px;
            border-radius: var(--radius-md);
            border: 1px solid var(--border);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            padding: 28px;
            background: linear-gradient(135deg, rgba(249,115,22,0.15), var(--bg-card));
        }

        .banner-media {
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            object-fit: cover;
            z-index: 1;
            opacity: 0.65;
        }

        .banner-overlay {
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background: linear-gradient(to top, rgba(15,13,14,0.95) 0%, rgba(15,13,14,0.3) 60%, transparent 100%);
            z-index: 2;
        }

        .banner-content { position: relative; z-index: 3; }

        .btn {
            padding: 8px 16px;
            border-radius: var(--radius-md);
            border: none;
            background: linear-gradient(135deg, #f97316, #ea580c);
            color: white;
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
            box-shadow: 0 4px 12px var(--accent-glow);
            transition: all 0.15s;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            white-space: nowrap;
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            background: var(--border) !important;
            box-shadow: none !important;
        }

        .btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 6px 18px var(--accent-glow); }
        .btn-danger { background: linear-gradient(135deg, #ef4444, #dc2626) !important; }
        .btn-secondary { background: var(--border); box-shadow: none; }
        .btn-secondary:hover:not(:disabled) { background: #3d3238; }
        .btn-ms { background: linear-gradient(135deg, #0078d4, #005a9e) !important; box-shadow: 0 4px 12px rgba(0, 120, 212, 0.3) !important; }

        /* Кнопка "Установлено" */
        .btn-installed {
            background: #231c20 !important;
            color: #9ca3af !important;
            border: 1px solid #3d3238 !important;
            box-shadow: none !important;
            cursor: default !important;
            transform: none !important;
        }

        /* Кнопка "Обновить" */
        .btn-update-available {
            background: linear-gradient(135deg, #eab308, #ca8a04) !important;
            color: #000 !important;
            font-weight: 800 !important;
            box-shadow: 0 4px 12px rgba(234, 179, 8, 0.3) !important;
        }

        input, select, textarea {
            padding: 10px 14px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border);
            background: #080708;
            color: var(--text-primary);
            outline: none;
            font-size: 14px;
        }

        /* КАСТОМНЫЕ ТЁМНО-ОРАНЖЕВЫЕ ЧЕКБОКСЫ */
        input[type="checkbox"] {
            appearance: none;
            -webkit-appearance: none;
            width: 18px;
            height: 18px;
            background: #141012;
            border: 1.5px solid #3d3238;
            border-radius: 5px;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s ease;
            position: relative;
            flex-shrink: 0;
            vertical-align: middle;
            margin: 0;
            outline: none;
        }

        input[type="checkbox"]:hover {
            border-color: var(--accent);
            box-shadow: 0 0 8px var(--accent-glow);
        }

        input[type="checkbox"]:checked {
            background: linear-gradient(135deg, #f97316, #ea580c);
            border-color: #f97316;
            box-shadow: 0 0 10px var(--accent-glow);
        }

        input[type="checkbox"]:checked::after {
            content: '';
            width: 4px;
            height: 8px;
            border: solid white;
            border-width: 0 2px 2px 0;
            transform: rotate(45deg) translate(-1px, -1px);
            display: block;
        }

        .password-field-wrap {
            position: relative;
            display: flex;
            align-items: center;
        }
        .password-field-wrap input { width: 100%; padding-right: 40px; }
        .password-eye-btn {
            position: absolute; right: 10px; background: transparent; border: none;
            color: var(--text-secondary); cursor: pointer; font-size: 16px;
        }

        .range-slider { width: 100%; accent-color: var(--accent); cursor: pointer; height: 6px; }

        .installations-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
            gap: 16px;
        }

        .accounts-auth-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }

        @media (max-width: 768px) {
            .accounts-auth-grid { grid-template-columns: 1fr; }
        }

        .inst-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 18px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            cursor: pointer;
            transition: all 0.15s;
        }

        .inst-card:hover { border-color: var(--accent); background: var(--bg-card-hover); transform: translateY(-2px); }
        .inst-card.active { border-color: var(--accent); box-shadow: 0 0 16px var(--accent-glow); }

        .inst-card-info {
            display: flex;
            align-items: center;
            gap: 14px;
            flex: 1;
            overflow: hidden;
        }

        .inst-card-texts { display: flex; flex-direction: column; overflow: hidden; }
        .inst-card-title { font-weight: 700; font-size: 16px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .inst-card-sub { font-size: 12px; color: var(--text-secondary); margin-top: 3px; }

        .tab-bar { display: flex; gap: 8px; border-bottom: 1px solid var(--border); padding-bottom: 10px; }
        .tab-btn {
            padding: 8px 16px;
            border-radius: var(--radius-sm);
            background: transparent;
            border: 1px solid transparent;
            color: var(--text-secondary);
            font-weight: 600;
            cursor: pointer;
        }
        .tab-btn.active { background: var(--bg-card); border-color: var(--accent); color: var(--accent); }

        .bottom-bar {
            position: fixed;
            bottom: 0; left: 0; right: 0;
            height: 38px;
            background: #080708;
            border-top: 1px solid var(--border);
            display: flex;
            align-items: center;
            padding: 0 16px;
            gap: 12px;
            z-index: 2000;
        }

        .bottom-bar-progress {
            position: absolute;
            bottom: 0; left: 0;
            height: 3px;
            background: var(--accent);
            width: 0%;
            transition: width 0.15s;
        }

        .toast-container {
            position: fixed;
            bottom: 50px; right: 20px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            z-index: 9999;
            pointer-events: none;
        }

        .toast-item {
            background: #181315;
            border: 1px solid var(--accent);
            border-left: 5px solid var(--accent);
            color: var(--text-primary);
            padding: 12px 18px;
            border-radius: var(--radius-sm);
            font-size: 13px;
            font-weight: 600;
            min-width: 250px;
            max-width: 380px;
            pointer-events: auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
        }

        .toast-item.error { border-color: #ef4444; border-left-color: #ef4444; }
        .toast-item.success { border-color: #22c55e; border-left-color: #22c55e; }
        .toast-item.info { border-color: #3b82f6; border-left-color: #3b82f6; }

        .modal-overlay {
            position: fixed;
            top: 48px; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.88);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            padding: 16px;
        }

        .modal-overlay.active { display: flex; }

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
        }

        .modal-card.large {
            width: 95%;
            max-width: 1100px;
            min-height: 600px;
            max-height: 90vh;
        }

        /* ЗОНА ПЕРЕТАСКИВАНИЯ ФАЙЛОВ */
        .drop-zone-overlay {
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(249, 115, 22, 0.15);
            border: 3px dashed var(--accent);
            border-radius: var(--radius-lg);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 50;
            backdrop-filter: blur(4px);
            pointer-events: none;
        }
        .drop-zone-overlay.drag-over { display: flex; }
        .drop-zone-text {
            font-size: 20px; font-weight: 800; color: #fff; background: #181416;
            padding: 16px 28px; border-radius: 12px; border: 1px solid var(--accent);
            box-shadow: 0 0 20px var(--accent-glow);
        }

        .form-group { display: flex; flex-direction: column; gap: 6px; }
        .form-group label { font-size: 12px; color: var(--text-secondary); text-transform: uppercase; font-weight: 600; }

        .account-card {
            background: #080708;
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 14px 18px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: all 0.15s;
        }

        .account-card.active { border-color: var(--accent); box-shadow: 0 0 10px var(--accent-glow); }

        .badge-type {
            font-size: 10px; padding: 3px 8px; border-radius: 4px;
            font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
        }
        .badge-offline { background: #33292e; color: #a1a1aa; }
        .badge-ms { background: rgba(0, 120, 212, 0.2); border: 1px solid #0078d4; color: #60a5fa; }
        .badge-cf { background: rgba(241, 100, 54, 0.2); border: 1px solid #f16436; color: #f16436; }
        .badge-mr { background: rgba(34, 197, 94, 0.2); border: 1px solid #22c55e; color: #22c55e; }
        .badge-cube { background: rgba(249, 115, 22, 0.2); border: 1px solid var(--accent); color: var(--accent); }

        .captcha-box {
            background: #080708; border: 1px solid var(--border); padding: 10px 14px;
            border-radius: var(--radius-sm); display: flex; align-items: center;
            justify-content: space-between; font-weight: 700; color: var(--accent);
        }

        .otp-input-field {
            font-size: 26px !important;
            letter-spacing: 12px !important;
            text-align: center !important;
            font-weight: 800 !important;
            color: var(--accent) !important;
            padding: 14px !important;
            border: 2px dashed var(--accent) !important;
            background: #0a0809 !important;
        }

        /* АППАРАТНЫЙ НЕЗАВИСАЮЩИЙ GPU-СКЕЛЕТОН */
        @keyframes shimmerGpu {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .skeleton-shimmer {
            position: relative;
            background-color: #171214;
            overflow: hidden;
            border-radius: var(--radius-sm);
        }

        .skeleton-shimmer::after {
            position: absolute;
            top: 0; right: 0; bottom: 0; left: 0;
            transform: translateX(-100%);
            background: linear-gradient(90deg, rgba(249, 115, 22, 0) 0%, rgba(249, 115, 22, 0.18) 50%, rgba(249, 115, 22, 0) 100%);
            animation: shimmerGpu 1.1s infinite linear;
            content: '';
            will-change: transform;
        }

        .skeleton-card {
            background: #080708;
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 12px 14px;
            display: flex;
            gap: 14px;
            align-items: center;
            min-height: 82px;
        }

        .cube-profile-banner {
            position: relative;
            background: linear-gradient(135deg, rgba(249, 115, 22, 0.2), #181416);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 24px;
            display: flex;
            align-items: center;
            gap: 20px;
        }
        .cube-profile-big-avatar {
            width: 80px; height: 80px; border-radius: 50%;
            border: 3px solid var(--accent); object-fit: cover; background: #080708;
        }

        .mods-table-header {
            display: flex; align-items: center; gap: 14px; padding: 10px 14px;
            background: #110d0f; border: 1px solid var(--border); border-radius: var(--radius-sm);
            font-size: 12px; font-weight: 700; color: var(--text-secondary); text-transform: uppercase;
        }

        .mod-row {
            display: flex; align-items: center; gap: 14px; padding: 10px 14px;
            background: #0a0809; border: 1px solid var(--border); border-radius: var(--radius-sm);
            transition: all 0.15s;
        }
        .mod-row:hover { background: #141012; border-color: rgba(249, 115, 22, 0.3); }
        .mod-row.disabled { opacity: 0.55; background: #080607; }

        .mod-check { width: 18px; height: 18px; }
        .mod-row-icon {
            width: 44px; height: 44px; border-radius: 8px; object-fit: cover;
            background: #181416; border: 1px solid var(--border); flex-shrink: 0;
        }
        .mod-row-info { display: flex; flex-direction: column; flex: 2; overflow: hidden; }
        .mod-row-title { font-weight: 700; font-size: 14px; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .mod-row-author { font-size: 11px; color: var(--text-secondary); margin-top: 2px; }
        .mod-row-ver-box { flex: 1.4; display: flex; flex-direction: column; overflow: hidden; gap: 2px; }
        .mod-row-ver-tag { font-size: 11px; font-weight: 700; color: #60a5fa; }
        .mod-row-filename { font-size: 10px; color: var(--text-secondary); font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

        .switch { position: relative; display: inline-block; width: 42px; height: 22px; flex-shrink: 0; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider {
            position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
            background-color: #33292e; transition: .15s; border-radius: 22px; border: 1px solid var(--border);
        }
        .slider:before {
            position: absolute; content: ""; height: 14px; width: 14px; left: 3px; bottom: 3px;
            background-color: white; transition: .15s; border-radius: 50%;
        }
        input:checked + .slider { background-color: #22c55e; border-color: #22c55e; }
        input:checked + .slider:before { transform: translateX(20px); }

        .catalog-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(460px, 1fr));
            gap: 12px; align-content: start;
        }
        .resource-card {
            background: #080708; border: 1px solid var(--border); border-radius: var(--radius-md);
            padding: 12px 14px; display: flex; gap: 14px; align-items: center; transition: all 0.15s; min-height: 82px;
        }
        .resource-card:hover { border-color: var(--accent); background: #141012; }
        .resource-card-img { width: 54px; height: 54px; border-radius: var(--radius-sm); object-fit: cover; background: #1a1618; border: 1px solid var(--border); flex-shrink: 0; }
        .resource-card-center { flex: 1; display: flex; flex-direction: column; gap: 3px; overflow: hidden; }
        .resource-card-title-row { display: flex; align-items: center; gap: 8px; overflow: hidden; }
        .resource-card-title { font-weight: 700; font-size: 13px; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .resource-card-meta { font-size: 11px; color: var(--text-secondary); }
        .resource-card-desc { font-size: 11px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .resource-card-actions { display: flex; flex-direction: column; gap: 6px; flex-shrink: 0; }

        .pagination-container {
            display: flex; align-items: center; justify-content: center; gap: 12px;
            margin-top: 15px; padding-top: 12px; border-top: 1px solid var(--border);
        }
        .pagination-btn {
            background: var(--bg-card); border: 1px solid var(--border); color: var(--text-primary);
            width: 32px; height: 32px; border-radius: var(--radius-sm); cursor: pointer;
        }
        .pagination-btn:disabled { opacity: 0.3; cursor: not-allowed; }

        /* ПОЛНОЭКРАННАЯ ГАЛЕРЕЯ (LIGHTBOX) */
        .lightbox-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.94);
            z-index: 99999;
            display: none;
            align-items: center;
            justify-content: center;
            flex-direction: column;
        }
        .lightbox-overlay.active { display: flex; }
        .lightbox-img-wrap {
            position: relative;
            max-width: 90vw;
            max-height: 80vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .lightbox-img {
            max-width: 100%;
            max-height: 80vh;
            border-radius: var(--radius-md);
            border: 2px solid var(--border);
            box-shadow: 0 0 30px rgba(0,0,0,0.8);
            object-fit: contain;
        }
        .lightbox-nav-btn {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(24, 20, 22, 0.85);
            border: 1px solid var(--border);
            color: #fff;
            width: 44px;
            height: 44px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .lightbox-nav-btn:hover { background: var(--accent); border-color: var(--accent); }
        .lightbox-nav-btn.prev { left: -60px; }
        .lightbox-nav-btn.next { right: -60px; }
        .lightbox-close-btn {
            position: absolute;
            top: 20px;
            right: 24px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            color: #fff;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .lightbox-close-btn:hover { background: #ef4444; }
        .lightbox-counter {
            margin-top: 14px;
            font-size: 13px;
            color: var(--text-secondary);
            font-weight: 600;
        }
    </style>
</head>
<body>

    <div class="titlebar pywebview-drag-region">
        <div class="titlebar-brand">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>
            CUBE LAUNCHER
        </div>

        <div class="window-controls">
            <button class="win-btn" onclick="window.pywebview.api.minimize()" title="Свернуть">&#8722;</button>
            <button class="win-btn close" onclick="window.pywebview.api.close()" title="Закрыть">&#10005;</button>
        </div>
    </div>

    <div class="app-body">
        <div class="sidebar">
            <button class="nav-btn active" onclick="switchPage('play', event)">🎮 Главная</button>
            <button class="nav-btn" onclick="switchPage('installations', event)">📦 Установки</button>
            <button class="nav-btn" onclick="switchPage('modpacks', event)">🎁 Модпаки</button>
            <button class="nav-btn" onclick="switchPage('accounts', event)">👤 Аккаунты</button>
            <button class="nav-btn" onclick="switchPage('settings', event)">⚙️ Настройки</button>

            <div class="sidebar-profile" id="sidebarProfileBtn" onclick="openProfileModal()">
                <img id="sidebarProfileAvatar" class="sidebar-profile-avatar" src="https://minotar.net/helm/Steve/100.png">
                <div class="sidebar-profile-info">
                    <div id="sidebarProfileName" class="sidebar-profile-name">Войти в профиль</div>
                    <div id="sidebarProfileSub" class="sidebar-profile-sub">✨ Cube Account</div>
                </div>
            </div>
        </div>

        <div class="content">

            <div id="globalMsBanner" class="ms-warning-banner" style="display: none;">
                <span style="font-size: 18px;">⚠️</span>
                <span>Нет связи с серверами Microsoft. Используйте оффлайн-аккаунт для одиночной игры и обычных серверов.</span>
            </div>

            <div id="play" class="page active">
                <div class="banner-container" id="mainBanner">
                    <div id="bannerMediaWrapper"></div>
                    <div class="banner-overlay"></div>
                    <div class="banner-content">
                        <h1 style="font-size: 32px;">Cube Launcher</h1>
                        <p style="color: var(--text-secondary); margin-top: 6px; font-size: 15px;">
                            Выберите сборку и нажимайте Играть!
                        </p>
                    </div>
                </div>

                <div class="card" style="flex-direction: row; align-items: center; justify-content: space-between; margin-top: auto;">
                    <div>
                        <div style="font-size: 12px; color: var(--text-secondary);">АКТИВНАЯ СБОРКА</div>
                        <div id="activeInstTitle" style="font-size: 18px; font-weight: 700; color: var(--accent);">Загрузка...</div>
                    </div>
                    <button class="btn" id="mainPlayBtn" style="padding: 14px 44px; font-size: 16px;" onclick="launchGame()">ИГРАТЬ</button>
                </div>
            </div>

            <div id="installations" class="page">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h2>Сборки и Установки</h2>
                    <button class="btn" onclick="openCreateModal()">+ Создать установку</button>
                </div>
                <div style="font-size: 13px; color: var(--text-secondary);">💡 Нажмите на сборку, чтобы открыть список её модов, шейдеров и настроек!</div>
                <div class="installations-grid" id="installationsGrid"></div>
            </div>

            <div id="modpacks" class="page">
                <h2>Каталог Модпаков</h2>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <input type="text" id="modpackSearchInput" placeholder="Поиск модпаков..." style="flex: 2;" oninput="onModpackSearchInput()">
                    <select id="modpackCatalogPlatform" style="flex: 1;" onchange="triggerModpackSearch(1)">
                        <option value="modrinth">🟢 Modrinth</option>
                        <option value="curseforge">🔥 CurseForge</option>
                    </select>
                    <select id="modpackLoaderFilter" style="flex: 1;" onchange="triggerModpackSearch(1)">
                        <option value="">Все загрузчики</option>
                        <option value="fabric">Fabric</option>
                        <option value="forge">Forge</option>
                        <option value="quilt">Quilt</option>
                    </select>
                    <select id="modpackVersionFilter" style="flex: 1;" onchange="triggerModpackSearch(1)">
                        <option value="">Все версии</option>
                    </select>
                </div>
                <div class="catalog-grid" id="modpacksGrid"></div>

                <div class="pagination-container" id="modpacksPagination">
                    <button class="pagination-btn" id="modPrevPage" onclick="changeModpackPage(-1)">◀</button>
                    <span id="modPageInfo" style="font-size: 13px;">Страница 1 из 1</span>
                    <button class="pagination-btn" id="modNextPage" onclick="changeModpackPage(1)">▶</button>
                </div>
            </div>

            <div id="accounts" class="page">
                <h2>Управление аккаунтами</h2>

                <div class="accounts-auth-grid">
                    <div class="card" style="justify-content: space-between;">
                        <div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="font-size: 20px;">👤</span>
                                <h3 style="font-size: 16px;">Оффлайн аккаунт</h3>
                            </div>
                            <p style="font-size: 13px; color: var(--text-secondary); margin-top: 6px;">
                                Вход без лицензии. Введите никнейм для игры.
                            </p>
                            <div class="form-group" style="margin-top: 14px;">
                                <label>Никнейм в игре</label>
                                <input type="text" id="accInput" placeholder="Введите ваш ник...">
                            </div>
                        </div>
                        <button class="btn" style="margin-top: 14px;" onclick="addOfflineAccount()">Добавить оффлайн-профиль</button>
                    </div>

                    <div class="card" style="border-color: rgba(0, 120, 212, 0.4); justify-content: space-between;">
                        <div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <svg width="20" height="20" viewBox="0 0 23 23"><path fill="#f25022" d="M1 1h10v10H1z"/><path fill="#00a4ef" d="M1 12h10v10H1z"/><path fill="#7fba00" d="M12 1h10v10H12z"/><path fill="#ffb900" d="M12 12h10v10H12z"/></svg>
                                <h3 style="font-size: 16px;">Microsoft Лицензия</h3>
                            </div>
                            <p style="font-size: 13px; color: var(--text-secondary); margin-top: 6px; line-height: 1.4;">
                                Вход через официальную учетную запись. Поддерживает лицензионные скины и серверы.
                            </p>
                        </div>
                        <button class="btn btn-ms" id="msLoginBtn" style="padding: 13px 20px; font-size: 14px; margin-top: 14px;" onclick="startMicrosoftAuth()">
                            🌐 Войти через Microsoft
                        </button>
                    </div>
                </div>

                <div class="card" style="margin-top: 6px;">
                    <h3>Сохраненные аккаунты</h3>
                    <div id="accountsList" style="display: flex; flex-direction: column; gap: 10px;"></div>
                </div>
            </div>

            <div id="settings" class="page">
                <h2>Настройки Лаунчера</h2>
                <div class="card" style="max-width: 600px;">
                    <div class="form-group">
                        <label>Фоновый баннер (Изображение / Видео)</label>
                        <div style="display: flex; gap: 10px;">
                            <input type="text" id="settingBannerPath" readonly placeholder="По умолчанию" style="flex: 1;">
                            <button class="btn btn-secondary" onclick="browseBanner()">Обзор...</button>
                            <button class="btn btn-danger" onclick="clearBanner()">✕</button>
                        </div>
                    </div>

                    <div class="form-group">
                        <div style="display: flex; justify-content: space-between;">
                            <label>Оперативная память (RAM)</label>
                            <span id="ramMbLabel" style="font-weight: 700; color: var(--accent);">4096 МБ (4.0 ГБ)</span>
                        </div>
                        <input type="range" id="settingRamSlider" class="range-slider" min="1024" max="16384" step="512" value="4096" oninput="onRamSliderInput(this.value)">
                    </div>

                    <div class="form-group">
                        <label>Дополнительные JVM аргументы</label>
                        <input type="text" id="settingJvm" placeholder="-XX:+UseG1GC" oninput="triggerAutoSave()">
                    </div>

                    <div style="display: flex; align-items: center; gap: 10px;">
                        <input type="checkbox" id="settingConsole" onchange="triggerAutoSave()">
                        <label for="settingConsole">Показывать консоль при запуске</label>
                    </div>
                </div>
            </div>

        </div>
    </div>

    <div class="toast-container" id="toastContainer"></div>

    <div class="bottom-bar">
        <div id="bottomBarStatus" style="font-size: 12px; color: var(--text-secondary);">Готов к запуску</div>
        <div class="bottom-bar-progress" id="bottomBarProgress"></div>
    </div>

    <!-- ОКНО ПРОФИЛЯ CUBE LAUNCHER -->
    <div class="modal-overlay" id="profileModal">
        <div class="modal-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 id="modalAuthHeaderTitle">Профиль Cube Launcher</h3>
                <button class="btn btn-secondary" onclick="closeModal('profileModal')">✕</button>
            </div>

            <div id="cubeNotLoggedView" style="display: flex; flex-direction: column; gap: 12px;">
                <div style="display: flex; gap: 8px; margin-bottom: 4px;">
                    <button class="btn" id="cubeModeLoginBtn" style="flex: 1;" onclick="setCubeAuthMode('login')">Вход</button>
                    <button class="btn btn-secondary" id="cubeModeRegBtn" style="flex: 1;" onclick="setCubeAuthMode('register')">Регистрация</button>
                </div>

                <div class="form-group">
                    <label id="lblCubeLogin">Никнейм или Email</label>
                    <input type="text" id="cubeInputLogin" placeholder="Ваш никнейм или почта...">
                </div>

                <div class="form-group" id="groupCubeEmail" style="display: none;">
                    <label>Email адрес</label>
                    <input type="email" id="cubeInputEmail" placeholder="example@mail.ru">
                </div>

                <div class="form-group">
                    <label>Пароль</label>
                    <div class="password-field-wrap">
                        <input type="password" id="cubeInputPassword" placeholder="••••••••">
                        <button type="button" class="password-eye-btn" onclick="togglePassVisibility('cubeInputPassword', this)">👁️</button>
                    </div>
                </div>

                <div class="form-group" id="groupCubePassRepeat" style="display: none;">
                    <label>Повторите пароль</label>
                    <div class="password-field-wrap">
                        <input type="password" id="cubeInputPasswordRepeat" placeholder="••••••••">
                        <button type="button" class="password-eye-btn" onclick="togglePassVisibility('cubeInputPasswordRepeat', this)">👁️</button>
                    </div>
                </div>

                <div class="form-group">
                    <label>Проверка (Капча)</label>
                    <div class="captcha-box">
                        <span id="captchaQuestionText">Загрузка...</span>
                        <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px;" onclick="refreshCaptcha()">🔄</button>
                    </div>
                    <input type="text" id="cubeCaptchaInput" placeholder="Введите ответ...">
                </div>

                <button class="btn" id="cubeSubmitBtn" style="padding: 12px; margin-top: 4px;" onclick="submitCubeAuth()">Войти в аккаунт</button>
            </div>

            <div id="cubeOtpVerificationView" style="display: none; flex-direction: column; gap: 14px; text-align: center;">
                <div style="font-size: 38px;">📧</div>
                <h3 id="otpHeaderActionText" style="font-size: 18px;">Подтверждение почты</h3>
                <p style="font-size: 13px; color: var(--text-secondary); line-height: 1.5;">
                    Мы отправили 6-значный код на почту <br>
                    <b id="otpTargetEmailText" style="color: var(--text-primary);">example@mail.ru</b>
                </p>

                <div class="form-group" style="margin: 6px 0;">
                    <input type="text" id="cubeOtpCodeInput" class="otp-input-field" maxlength="6" placeholder="000000">
                </div>

                <button class="btn" id="btnConfirmOtpMain" style="padding: 12px; font-size: 14px;" onclick="confirmOtpAction()">✨ Подтвердить</button>

                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
                    <button class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px;" onclick="backToAuthForm()">◀ Назад</button>
                    <button class="btn btn-secondary" id="btnResendOtp" style="padding: 6px 12px; font-size: 12px;" onclick="resendOtpCode()">Отправить заново</button>
                </div>
            </div>

            <div id="cubeLoggedView" style="display: none; flex-direction: column; gap: 14px;">
                <div class="cube-profile-banner">
                    <img id="cubeFullAvatar" class="cube-profile-big-avatar" src="">
                    <div style="flex: 1;">
                        <h2 id="cubeFullUsername" style="font-size: 22px;">Username</h2>
                        <div id="cubeFullEmail" style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">Email</div>
                        <div style="display: flex; gap: 6px; margin-top: 8px;">
                            <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="changeCubeAvatar()">📷 Сменить аватар</button>
                        </div>
                    </div>
                    <button class="btn btn-danger" onclick="logoutCube()">🚪 Выйти</button>
                </div>

                <div class="form-group">
                    <label>О себе</label>
                    <textarea id="cubeBioText" rows="3" placeholder="Расскажите о себе..."></textarea>
                </div>
                <div style="display: flex; justify-content: flex-end;">
                    <button class="btn" onclick="saveCubeBio()">💾 Сохранить</button>
                </div>
            </div>
        </div>
    </div>

    <!-- МОДАЛЬНЫЕ ОКНА УСТАНОВОК И ДЕТАЛЕЙ -->
    <div class="modal-overlay" id="createModal">
        <div class="modal-card">
            <h3 id="modalInstTitle">Создать установку</h3>
            <input type="hidden" id="modalInstId">
            <div class="form-group">
                <label>Название</label>
                <input type="text" id="modalInstName" placeholder="Моя сборка">
            </div>
            <div class="form-group">
                <label>Иконка</label>
                <input type="text" id="modalInstIcon" value="🟧">
            </div>
            <div class="form-group">
                <label>Версия Minecraft</label>
                <select id="modalMcVer" onchange="onMcVerChange()"></select>
            </div>
            <div class="form-group">
                <label>Загрузчик модов</label>
                <select id="modalLoader" onchange="onLoaderChange()">
                    <option value="vanilla">Vanilla (Чистый)</option>
                    <option value="fabric">Fabric</option>
                    <option value="forge">Forge</option>
                    <option value="quilt">Quilt</option>
                </select>
            </div>
            <div class="form-group">
                <label>Версия загрузчика</label>
                <select id="modalLoaderVer"><option value="latest">Последняя (Latest)</option></select>
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 10px;">
                <button class="btn btn-secondary" onclick="closeModal('createModal')">Отмена</button>
                <button class="btn" onclick="saveModalInstance()">Сохранить</button>
            </div>
        </div>
    </div>

    <!-- ОКНО СБОРКИ С DRAG-AND-DROP И ПОИСКОМ/ФИЛЬТРАМИ -->
    <div class="modal-overlay" id="instanceViewModal">
        <div class="modal-card large" id="instViewCard">
            
            <div class="drop-zone-overlay" id="instDropOverlay">
                <div class="drop-zone-text">📥 Перетащите .jar или .zip файлы сюда</div>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h2 id="instViewTitle" style="font-size: 22px;">Сборка</h2>
                <div style="display: flex; gap: 8px;">
                    <button class="btn" id="modalPlayBtn" onclick="launchCurrentInstance()">🚀 Запустить</button>
                    <button class="btn btn-secondary" onclick="openActiveInstFolder()">📁 Папка</button>
                    <button class="btn btn-secondary" onclick="editCurrentInstance()">✏️ Изменить</button>
                    <button class="btn btn-danger" onclick="deleteCurrentInstance()">🗑️ Удалить</button>
                    <button class="btn btn-secondary" onclick="closeModal('instanceViewModal')">✕</button>
                </div>
            </div>

            <div class="tab-bar">
                <button class="tab-btn active" onclick="switchInstTab('mods', event)">🧩 Моды</button>
                <button class="tab-btn" onclick="switchInstTab('shaderpacks', event)">✨ Шейдеры</button>
                <button class="tab-btn" onclick="switchInstTab('resourcepacks', event)">🎨 Ресурспаки</button>
                <button class="tab-btn" onclick="switchInstTab('datapacks', event)">⚙️ Датапаки</button>
            </div>

            <!-- ПАНЕЛЬ ПОИСКА И ФИЛЬТРОВ ДЛЯ УСТАНОВЛЕННЫХ МОДОВ -->
            <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
                <input type="text" id="instSearchInput" placeholder="🔍 Поиск по названию, файлу, автору..." style="flex: 2;" oninput="applyInstalledFilter()">
                <select id="instStatusFilter" style="flex: 1;" onchange="applyInstalledFilter()">
                    <option value="all">Все файлы</option>
                    <option value="enabled">Только включенные</option>
                    <option value="disabled">Только выключенные</option>
                    <option value="updates">Требуют обновления</option>
                </select>
                <button class="btn" onclick="openAddModsModal()">+ Каталог проектов</button>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    <button class="btn btn-secondary" style="font-size: 12px; padding: 6px 12px;" onclick="checkModUpdates()" id="btnCheckUpdates">🔄 Проверить обновления</button>
                    <button class="btn btn-update-available" style="font-size: 12px; padding: 6px 12px; display: none;" onclick="updateAllMods()" id="btnUpdateAllMods">🚀 Обновить всё (0)</button>
                    <button class="btn btn-secondary" style="font-size: 12px; padding: 6px 10px;" onclick="toggleSelectedFiles(true)">Вкл. выбранные</button>
                    <button class="btn btn-secondary" style="font-size: 12px; padding: 6px 10px;" onclick="toggleSelectedFiles(false)">Выкл. выбранные</button>
                    <button class="btn btn-danger" style="font-size: 12px; padding: 6px 10px;" onclick="deleteSelectedFiles()" title="Удалить выбранные">🗑️</button>
                </div>
            </div>

            <div class="mods-table-header">
                <input type="checkbox" id="selectAllModsCheck" class="mod-check" onchange="toggleSelectAllMods(this.checked)" title="Выбрать все">
                <div style="width: 44px;">Иконка</div>
                <div style="flex: 2;">Название проекта / Автор</div>
                <div style="flex: 1.4;">Версия мода</div>
                <div style="width: 42px; text-align: center;">Статус</div>
                <div style="width: 90px; text-align: right;">Действия</div>
            </div>

            <div id="instFilesList" style="display: flex; flex-direction: column; gap: 8px; flex: 1; max-height: 440px; overflow-y: auto;"></div>
        </div>
    </div>

    <!-- КАТАЛОГ С ФИЛЬТРАМИ -->
    <div class="modal-overlay" id="addModsModal">
        <div class="modal-card large">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3>Каталог Модификаций</h3>
                <button class="btn btn-secondary" onclick="closeModal('addModsModal')">✕</button>
            </div>

            <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
                <input type="text" id="modSearchInput" placeholder="Поиск проектов..." style="flex: 2;" oninput="onModSearchInput()">
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
            </div>

            <div class="catalog-grid" id="catalogGrid" style="max-height: 420px; overflow-y: auto;"></div>

            <div class="pagination-container" id="modsPagination">
                <button class="pagination-btn" id="modPrevPage" onclick="changeModPage(-1)">◀</button>
                <span id="modPageInfo" style="font-size: 13px;">Страница 1 из 1</span>
                <button class="pagination-btn" id="modNextPage" onclick="changeModPage(1)">▶</button>
            </div>
        </div>
    </div>

    <!-- ДЕТАЛИ МОДА -->
    <div class="modal-overlay" id="modDetailsModal">
        <div class="modal-card large">
            <div style="display: flex; gap: 16px; align-items: center;">
                <img id="detailIcon" src="" style="width: 58px; height: 58px; border-radius: 10px; object-fit: cover; border: 1px solid var(--border);">
                <div style="flex: 1;">
                    <h2 id="detailTitle" style="font-size: 18px;">Название</h2>
                    <div id="detailMeta" style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">ID</div>
                </div>
                <button class="btn btn-secondary" onclick="closeModal('modDetailsModal')">✕</button>
            </div>

            <div class="gallery-track" id="detailGallery" style="display: flex; gap: 10px; overflow-x: auto; width: 100%; padding: 8px 0;"></div>

            <h4 style="margin-top: 6px;">Файлы и версии:</h4>
            <div id="detailVersionsList" style="display: flex; flex-direction: column; gap: 6px; max-height: 240px; overflow-y: auto;"></div>
        </div>
    </div>

    <!-- ПОЛНОЭКРАННЫЙ ПРОСМОТР СКРИНШОТОВ (LIGHTBOX) -->
    <div class="lightbox-overlay" id="galleryLightbox">
        <button class="lightbox-close-btn" onclick="closeLightbox()">✕</button>
        <div class="lightbox-img-wrap">
            <button class="lightbox-nav-btn prev" onclick="changeLightboxImg(-1)">◀</button>
            <img id="lightboxMainImg" class="lightbox-img" src="">
            <button class="lightbox-nav-btn next" onclick="changeLightboxImg(1)">▶</button>
        </div>
        <div class="lightbox-counter" id="lightboxCounter">1 / 1</div>
    </div>

    <script>
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

        let modpackPage = 1, modpackTotalPages = 1;
        let modCatalogPage = 1, modCatalogTotalPages = 1;
        let currentRawCatalogItems = [];
        let cachedInstalledFiles = [];

        let currentLightboxGallery = [];
        let currentLightboxIndex = 0;

        let pendingAuthData = null;
        let pendingAuthType = 'login';
        let otpCooldownTimer = null;

        let audioCtx = null;
        function getAudioContext() {
            if (!audioCtx) {
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                if (AudioContext) audioCtx = new AudioContext();
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
                    osc.frequency.setValueAtTime(600, now);
                    osc.frequency.exponentialRampToValueAtTime(120, now + 0.04);
                    gain.gain.setValueAtTime(0.1, now);
                    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);
                    osc.start(now);
                    osc.stop(now + 0.04);
                } else if (type === 'tab') {
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(450, now);
                    osc.frequency.exponentialRampToValueAtTime(280, now + 0.035);
                    gain.gain.setValueAtTime(0.06, now);
                    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.035);
                    osc.start(now);
                    osc.stop(now + 0.035);
                } else if (type === 'success') {
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(523, now);
                    osc.frequency.setValueAtTime(659, now + 0.08);
                    osc.frequency.setValueAtTime(784, now + 0.16);
                    gain.gain.setValueAtTime(0.1, now);
                    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.28);
                    osc.start(now);
                    osc.stop(now + 0.28);
                } else if (type === 'error') {
                    osc.type = 'sawtooth';
                    osc.frequency.setValueAtTime(180, now);
                    osc.frequency.linearRampToValueAtTime(110, now + 0.12);
                    gain.gain.setValueAtTime(0.12, now);
                    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);
                    osc.start(now);
                    osc.stop(now + 0.12);
                } else if (type === 'launch') {
                    osc.type = 'triangle';
                    osc.frequency.setValueAtTime(220, now);
                    osc.frequency.exponentialRampToValueAtTime(880, now + 0.18);
                    gain.gain.setValueAtTime(0.12, now);
                    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
                    osc.start(now);
                    osc.stop(now + 0.2);
                }
            } catch (e) {}
        }

        document.addEventListener('click', (e) => {
            if (e.target.closest('.btn') || e.target.closest('.win-btn') || e.target.closest('.pagination-btn')) {
                playUiSound('click');
            } else if (e.target.closest('.nav-btn') || e.target.closest('.tab-btn')) {
                playUiSound('tab');
            }
        });

        function showToast(message, type = 'info') {
            const container = document.getElementById('toastContainer');
            if (!container) return;
            const toast = document.createElement('div');
            toast.className = `toast-item ${type}`;
            toast.innerHTML = `<span>${message}</span>`;
            container.appendChild(toast);
            if (type === 'success') playUiSound('success');
            else if (type === 'error') playUiSound('error');
            setTimeout(() => toast.remove(), 3500);
        }

        function updateDownloadStatus(text, val) {
            document.getElementById('bottomBarStatus').textContent = text;
            if (val !== undefined && val !== null) {
                document.getElementById('bottomBarProgress').style.width = val + '%';
            }
        }

        function updateDownloadProgress(val) {
            document.getElementById('bottomBarProgress').style.width = val + '%';
        }

        function hideDownloadStatus() {
            document.getElementById('bottomBarStatus').textContent = "Готов к запуску";
            document.getElementById('bottomBarProgress').style.width = '0%';
        }

        function setPlayButtonState(state, runningInstId = null) {
            gameState = state;
            activeRunningId = (state === 'running' || state === 'launching' || state === 'installing') ? runningInstId : null;
            const mainBtn = document.getElementById('mainPlayBtn');
            const modalBtn = document.getElementById('modalPlayBtn');

            if (mainBtn) {
                if (state === 'installing') {
                    mainBtn.textContent = "⏳ Установка...";
                    mainBtn.disabled = true;
                } else if (state === 'launching') {
                    mainBtn.textContent = "🚀 Запуск...";
                    mainBtn.disabled = true;
                } else if (state === 'running') {
                    mainBtn.textContent = "⏹ Закрыть игру";
                    mainBtn.className = "btn btn-danger";
                    mainBtn.disabled = false;
                    mainBtn.onclick = () => window.pywebview.api.kill_game();
                } else {
                    mainBtn.textContent = "ИГРАТЬ";
                    mainBtn.className = "btn";
                    mainBtn.disabled = false;
                    mainBtn.onclick = () => launchGame();
                }
            }

            if (modalBtn) {
                if (state === 'running' && (!runningInstId || runningInstId === currentViewingInstId)) {
                    modalBtn.textContent = "⏹ Закрыть игру";
                    modalBtn.className = "btn btn-danger";
                    modalBtn.disabled = false;
                    modalBtn.onclick = () => window.pywebview.api.kill_game();
                } else if (state === 'installing' || state === 'launching') {
                    modalBtn.textContent = state === 'installing' ? "⏳ Установка..." : "🚀 Запуск...";
                    modalBtn.className = "btn";
                    modalBtn.disabled = true;
                } else {
                    modalBtn.textContent = "🚀 Запустить";
                    modalBtn.className = "btn";
                    modalBtn.disabled = false;
                    modalBtn.onclick = () => launchCurrentInstance();
                }
            }
            renderInstallations();
        }

        function switchPage(pageId, evt) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(pageId).classList.add('active');
            if (evt) evt.target.classList.add('active');
            if (pageId === 'modpacks') triggerModpackSearch(1);
        }

        function showModal(id) { document.getElementById(id).classList.add('active'); }
        function closeModal(id) {
            document.getElementById(id).classList.remove('active');
            if (id === 'instanceViewModal') {
                window.pywebview.api.stop_watching_instance();
            }
        }

        window.addEventListener('pywebviewready', () => {
            refreshData();
            loadMcVersions();
            refreshMainProfileUI();
            checkMsServerStatus();
            setupDragAndDrop();
        });

        function setupDragAndDrop() {
            const card = document.getElementById('instViewCard');
            const overlay = document.getElementById('instDropOverlay');
            if (!card || !overlay) return;

            window.addEventListener('dragover', (e) => {
                e.preventDefault();
                if (document.getElementById('instanceViewModal').classList.contains('active')) {
                    overlay.classList.add('drag-over');
                }
            });

            window.addEventListener('dragleave', (e) => {
                if (!e.relatedTarget || e.relatedTarget.nodeName === 'HTML') {
                    overlay.classList.remove('drag-over');
                }
            });

            window.addEventListener('drop', async (e) => {
                e.preventDefault();
                overlay.classList.remove('drag-over');
                if (!currentViewingInstId || !document.getElementById('instanceViewModal').classList.contains('active')) return;

                const files = e.dataTransfer.files;
                if (!files || files.length === 0) return;

                showToast(`Загрузка ${files.length} файл(ов)...`, "info");
                for (let file of files) {
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
                showToast("Файлы успешно перенесены в сборку!", "success");
            });
        }

        async function checkMsServerStatus() {
            try {
                const res = await window.pywebview.api.check_microsoft_status();
                const banner = document.getElementById('globalMsBanner');
                if (banner) {
                    banner.style.display = (res && res.connected === false) ? 'flex' : 'none';
                }
            } catch (e) {}
        }

        async function refreshMainProfileUI() {
            const resCube = await window.pywebview.api.get_cube_user();
            currentCubeUser = resCube.user;

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
            } else {
                avatarEl.src = 'https://minotar.net/helm/Steve/100.png';
                nameEl.textContent = 'Войти в профиль';
                subEl.textContent = '✨ Cube Account';
                document.getElementById('cubeNotLoggedView').style.display = 'flex';
                document.getElementById('cubeOtpVerificationView').style.display = 'none';
                document.getElementById('cubeLoggedView').style.display = 'none';
            }
        }

        async function openProfileModal() {
            await refreshCaptcha();
            showModal('profileModal');
        }

        function setCubeAuthMode(mode) {
            cubeAuthMode = mode;
            document.getElementById('cubeModeLoginBtn').className = `btn ${mode === 'login' ? '' : 'btn-secondary'}`;
            document.getElementById('cubeModeRegBtn').className = `btn ${mode === 'register' ? '' : 'btn-secondary'}`;
            document.getElementById('groupCubeEmail').style.display = mode === 'register' ? 'flex' : 'none';
            document.getElementById('groupCubePassRepeat').style.display = mode === 'register' ? 'flex' : 'none';
            document.getElementById('lblCubeLogin').textContent = mode === 'register' ? 'Никнейм (Логин)' : 'Никнейм или Email';
            document.getElementById('cubeSubmitBtn').textContent = mode === 'register' ? '📧 Получить код регистрации' : '📧 Получить код для входа';
        }

        function togglePassVisibility(inputId, btn) {
            const el = document.getElementById(inputId);
            if (el.type === 'password') {
                el.type = 'text';
                btn.textContent = '🔒';
            } else {
                el.type = 'password';
                btn.textContent = '👁️';
            }
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
                showToast("Проверка данных и отправка кода...", "info");
                const res = await window.pywebview.api.send_login_code(loginVal, passVal, captchaVal);
                if (res.status === 'ok') {
                    pendingAuthType = 'login';
                    pendingAuthData = { login: loginVal, password: passVal };
                    document.getElementById('otpHeaderActionText').textContent = "Подтверждение входа";
                    document.getElementById('btnConfirmOtpMain').textContent = "🚀 Войти в аккаунт";
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
                showToast("Отправка кода на почту...", "info");
                const res = await window.pywebview.api.send_registration_code(loginVal, emailVal, passVal, captchaVal);
                if (res.status === 'ok') {
                    pendingAuthType = 'register';
                    pendingAuthData = { username: loginVal, email: emailVal, password: passVal };
                    document.getElementById('otpHeaderActionText').textContent = "Подтверждение регистрации";
                    document.getElementById('btnConfirmOtpMain').textContent = "✨ Подтвердить и создать аккаунт";
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
                    btn.textContent = "Отправить заново";
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
                res = await window.pywebview.api.send_login_code(
                    pendingAuthData.login, pendingAuthData.password, document.getElementById('cubeCaptchaInput').value || "0"
                );
            } else {
                res = await window.pywebview.api.send_registration_code(
                    pendingAuthData.username, pendingAuthData.email, pendingAuthData.password, document.getElementById('cubeCaptchaInput').value || "0"
                );
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
                closeModal('profileModal');
                await refreshData();
            } else {
                showToast(res.message, "error");
            }
        }

        async function changeCubeAvatar() {
            const res = await window.pywebview.api.select_cube_avatar();
            if (res && res.status === 'ok') await refreshMainProfileUI();
        }

        async function logoutCube() {
            await window.pywebview.api.logout_cube_account();
            closeModal('profileModal');
            await refreshData();
        }

        async function saveCubeBio() {
            const bio = document.getElementById('cubeBioText').value;
            await window.pywebview.api.update_cube_bio(bio);
        }

        async function startMicrosoftAuth() {
            showToast("Открываем окно входа Microsoft...", "info");
            await window.pywebview.api.start_microsoft_login();
        }

        async function addOfflineAccount() {
            const u = document.getElementById('accInput').value;
            if (!u.trim()) {
                showToast("Введите никнейм!", "error");
                return;
            }
            const res = await window.pywebview.api.add_account(u);
            if (res.status === 'ok') {
                document.getElementById('accInput').value = '';
                await refreshData();
                showToast("Оффлайн аккаунт добавлен!", "success");
            }
        }

        async function selectAccount(u) {
            await window.pywebview.api.select_account(u);
            await refreshData();
            showToast(`Аккаунт ${u} выбран!`, "info");
        }

        async function deleteAccount(u) {
            await window.pywebview.api.delete_account(u);
            await refreshData();
            showToast(`Аккаунт ${u} удален`, "info");
        }

        async function refreshData() {
            globalConfig = await window.pywebview.api.get_config();
            const accounts = await window.pywebview.api.get_accounts();

            const ramMb = globalConfig.ram_mb || 4096;
            document.getElementById('settingRamSlider').value = ramMb;
            onRamSliderInput(ramMb, false);

            document.getElementById('settingJvm').value = globalConfig.jvm_args || '';
            document.getElementById('settingConsole').checked = !!globalConfig.enable_console;
            document.getElementById('settingBannerPath').value = globalConfig.banner_path || '';

            loadBannerMedia();
            renderActiveInstance();
            renderInstallations();
            renderAccounts(accounts);
            populateTargetInstancesSelect();
        }

        async function loadBannerMedia() {
            const res = await window.pywebview.api.get_banner_data();
            const wrapper = document.getElementById('bannerMediaWrapper');
            wrapper.innerHTML = '';
            if (res.status === 'image') {
                wrapper.innerHTML = `<img class="banner-media" src="${res.data}">`;
            } else if (res.status === 'video') {
                wrapper.innerHTML = `<video class="banner-media" src="${res.path}" autoplay loop muted></video>`;
            }
        }

        function onRamSliderInput(val, autoSave = true) {
            const gb = (val / 1024).toFixed(1);
            document.getElementById('ramMbLabel').textContent = `${val} МБ (${gb} ГБ)`;
            if (autoSave) triggerAutoSave();
        }

        function triggerAutoSave() {
            clearTimeout(autoSaveTimer);
            autoSaveTimer = setTimeout(async () => {
                const ramMb = document.getElementById('settingRamSlider').value;
                const jvm = document.getElementById('settingJvm').value;
                const consoleEnabled = document.getElementById('settingConsole').checked;
                await window.pywebview.api.save_settings_auto(ramMb, consoleEnabled, jvm);
            }, 300);
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

        async function loadMcVersions() {
            const versions = await window.pywebview.api.get_mc_versions();
            const selects = ['modalMcVer', 'modVersionFilter', 'modpackVersionFilter'];
            selects.forEach(id => {
                const el = document.getElementById(id);
                if (!el) return;
                el.innerHTML = id === 'modalMcVer' ? '' : '<option value="">Все версии</option>';
                versions.forEach(v => {
                    const opt = document.createElement('option');
                    opt.value = v;
                    opt.textContent = v;
                    el.appendChild(opt);
                });
            });
            onMcVerChange();
        }

        async function onMcVerChange() { onLoaderChange(); }

        async function onLoaderChange() {
            const loader = document.getElementById('modalLoader').value;
            const mcVer = document.getElementById('modalMcVer').value;
            const loaderSelect = document.getElementById('modalLoaderVer');
            loaderSelect.innerHTML = '<option value="latest">Последняя (Latest)</option>';

            if (loader !== 'vanilla') {
                const versions = await window.pywebview.api.get_loader_versions(loader, mcVer);
                versions.forEach(fv => {
                    const opt = document.createElement('option');
                    opt.value = fv;
                    opt.textContent = fv;
                    loaderSelect.appendChild(opt);
                });
            }
        }

        function renderActiveInstance() {
            const insts = globalConfig.instances || [];
            const active = insts.find(i => i.id === globalConfig.active_instance_id) || insts[0];
            if (active) {
                document.getElementById('activeInstTitle').textContent = `${active.icon || '🟧'} ${active.name} (${active.mc_version})`;
            }
        }

        function renderInstallations() {
            const grid = document.getElementById('installationsGrid');
            grid.innerHTML = '';
            const insts = globalConfig.instances || [];

            insts.forEach(inst => {
                const card = document.createElement('div');
                card.className = `inst-card ${inst.id === globalConfig.active_instance_id ? 'active' : ''}`;
                card.setAttribute('data-inst-id', inst.id);
                card.onclick = () => openInstanceMenu(inst.id);

                const isRunning = gameState === 'running' && activeRunningId === inst.id;
                const isBusy = (gameState === 'launching' || gameState === 'installing') && activeRunningId === inst.id;

                let btnText = '▶ Играть';
                let btnClass = 'btn';
                let btnAction = `launchInstanceDirect('${inst.id}')`;

                if (isRunning) {
                    btnText = '⏹ Закрыть';
                    btnClass = 'btn btn-danger';
                    btnAction = 'window.pywebview.api.kill_game()';
                } else if (isBusy) {
                    btnText = '⏳ Запуск...';
                    btnClass = 'btn';
                    btnAction = '';
                }

                card.innerHTML = `
                    <div class="inst-card-info">
                        <div style="font-size: 30px;">${inst.icon || '🟧'}</div>
                        <div class="inst-card-texts">
                            <div class="inst-card-title">${inst.name}</div>
                            <div class="inst-card-sub">${inst.mc_version} • ${inst.loader.toUpperCase()}</div>
                        </div>
                    </div>
                    <button class="${btnClass} inst-play-btn" ${isBusy ? 'disabled' : ''} onclick="event.stopPropagation(); ${btnAction}">
                        ${btnText}
                    </button>
                `;
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
            list.innerHTML = '';
            if (accounts.length === 0) {
                list.innerHTML = '<div class="empty-state" style="color: var(--text-secondary); padding: 10px;">Нет сохраненных аккаунтов. Добавьте профиль выше!</div>';
                return;
            }

            accounts.forEach(acc => {
                const isMs = acc.type === 'microsoft';
                const item = document.createElement('div');
                item.className = `account-card ${acc.active ? 'active' : ''}`;
                item.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 22px;">${isMs ? '🔷' : '👤'}</span>
                        <div>
                            <div style="font-weight: 700; display: flex; align-items: center; gap: 8px; ${acc.active ? 'color: var(--accent);' : ''}">
                                ${acc.username}
                                <span class="badge-type ${isMs ? 'badge-ms' : 'badge-offline'}">${isMs ? 'Microsoft' : 'Оффлайн'}</span>
                                ${acc.active ? '<span style="color: var(--accent); font-size: 12px;">★ Активен</span>' : ''}
                            </div>
                        </div>
                    </div>
                    <div style="display: flex; gap: 8px;">
                        ${!acc.active ? `<button class="btn" style="padding: 6px 14px; font-size: 12px;" onclick="selectAccount('${acc.username}')">Выбрать</button>` : ''}
                        <button class="btn btn-danger" style="padding: 6px 14px; font-size: 12px;" onclick="deleteAccount('${acc.username}')">Удалить</button>
                    </div>
                `;
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

        async function openInstanceMenu(instId) {
            currentViewingInstId = instId;
            cachedModUpdates = {};
            const inst = globalConfig.instances.find(i => i.id === instId);
            if (!inst) return;
            document.getElementById('instViewTitle').textContent = `${inst.icon} ${inst.name}`;
            currentResourceTab = 'mods';
            setPlayButtonState(gameState, activeRunningId);
            
            window.pywebview.api.start_watching_instance(currentViewingInstId, currentResourceTab);
            
            await refreshModalInstanceFiles();
            showModal('instanceViewModal');
            checkModUpdates(false);
        }

        async function switchInstTab(tab, evt) {
            currentResourceTab = tab;
            document.querySelectorAll('#instanceViewModal .tab-btn').forEach(b => b.classList.remove('active'));
            if (evt) evt.target.classList.add('active');
            window.pywebview.api.start_watching_instance(currentViewingInstId, currentResourceTab);
            await refreshModalInstanceFiles();
        }

        async function checkModUpdates(showNotification = true) {
            if (!currentViewingInstId) return;
            const btnCheck = document.getElementById('btnCheckUpdates');
            const btnUpdateAll = document.getElementById('btnUpdateAllMods');
            if (btnCheck) btnCheck.textContent = "⏳ Проверка...";

            const res = await window.pywebview.api.check_instance_updates(currentViewingInstId);
            if (btnCheck) btnCheck.textContent = "🔄 Проверить обновления";

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
                    else showToast("Все моды обновлены!", "info");
                }
            } else if (showNotification) {
                showToast("Ошибка проверки: " + res.message, "error");
            }
        }

        async function updateAllMods() {
            if (!currentViewingInstId) return;
            await window.pywebview.api.update_all_mods(currentViewingInstId);
            cachedModUpdates = {};
            const btnUpdateAll = document.getElementById('btnUpdateAllMods');
            if (btnUpdateAll) btnUpdateAll.style.display = "none";
        }

        async function updateSingleMod(filename) {
            if (!currentViewingInstId || !cachedModUpdates[filename]) return;
            const info = cachedModUpdates[filename];
            showToast(`Обновление ${info.new_filename}...`, "info");
            const res = await window.pywebview.api.update_single_mod(currentViewingInstId, filename, info.url, info.new_filename);
            if (res.status === 'ok') {
                delete cachedModUpdates[filename];
                showToast(`Мод ${info.new_filename} обновлён!`, "success");
                await refreshModalInstanceFiles();
                const remaining = Object.keys(cachedModUpdates).length;
                const btnUpdateAll = document.getElementById('btnUpdateAllMods');
                if (btnUpdateAll) {
                    btnUpdateAll.style.display = remaining > 0 ? "inline-flex" : "none";
                    btnUpdateAll.textContent = `🚀 Обновить всё (${remaining})`;
                }
            } else {
                showToast("Ошибка: " + res.message, "error");
            }
        }

        async function silentRefreshModalFiles() {
            if (!currentViewingInstId) return;
            cachedInstalledFiles = await window.pywebview.api.get_instance_files(currentViewingInstId, currentResourceTab);
            applyInstalledFilter();
        }

        async function refreshModalInstanceFiles() {
            if (!currentViewingInstId) return;
            const list = document.getElementById('instFilesList');
            const selectAllBox = document.getElementById('selectAllModsCheck');
            if (selectAllBox) selectAllBox.checked = false;

            renderFileSkeletons(list, 3);
            cachedInstalledFiles = await window.pywebview.api.get_instance_files(currentViewingInstId, currentResourceTab);
            applyInstalledFilter();
        }

        function applyInstalledFilter() {
            const list = document.getElementById('instFilesList');
            if (!list) return;

            const q = (document.getElementById('instSearchInput').value || '').toLowerCase().trim();
            const statusFilter = document.getElementById('instStatusFilter').value || 'all';

            let filtered = cachedInstalledFiles.filter(f => {
                const matchQuery = !q || (f.display_name && f.display_name.toLowerCase().includes(q)) ||
                                   (f.filename && f.filename.toLowerCase().includes(q)) ||
                                   (f.author && f.author.toLowerCase().includes(q));
                if (!matchQuery) return false;

                const hasUpdate = !!cachedModUpdates[f.filename];
                if (statusFilter === 'enabled') return f.enabled;
                if (statusFilter === 'disabled') return !f.enabled;
                if (statusFilter === 'updates') return hasUpdate;
                return true;
            });

            list.innerHTML = filtered.length === 0 ? `<div class="empty-state" style="padding: 20px; text-align: center; color: var(--text-secondary);">Ничего не найдено в этой папке.</div>` : '';
            
            const fallbackModIcon = "https://cdn-icons-png.flaticon.com/512/3344/3344384.png";

            filtered.forEach(f => {
                const row = document.createElement('div');
                row.className = `mod-row ${!f.enabled ? 'disabled' : ''}`;
                
                const updateInfo = cachedModUpdates[f.filename];
                const updateBadge = updateInfo ? `<span class="badge-type badge-mr" style="font-size: 10px; padding: 2px 6px;">⬆ ${updateInfo.new_version}</span>` : '';
                const updateBtn = updateInfo ? `<button class="btn btn-update-available" style="padding: 5px 8px; font-size: 11px;" onclick="updateSingleMod('${f.filename}')" title="Обновить до ${updateInfo.new_version}">🔄</button>` : '';

                row.innerHTML = `
                    <input type="checkbox" class="mod-check mod-item-check" value="${f.filename}">
                    <img class="mod-row-icon" src="${f.icon || fallbackModIcon}" onerror="this.src='${fallbackModIcon}'">
                    
                    <div class="mod-row-info">
                        <div class="mod-row-title">${f.display_name}</div>
                        <div class="mod-row-author">👤 ${f.author || 'Автор не указан'}</div>
                    </div>

                    <div class="mod-row-ver-box">
                        <div class="mod-row-ver-tag">
                            <span>${f.version || 'v1.0.0'}</span>
                            ${updateBadge}
                        </div>
                        <span class="mod-row-filename">${f.clean_name}</span>
                    </div>

                    <label class="switch" title="Включить / Выключить">
                        <input type="checkbox" ${f.enabled ? 'checked' : ''} onchange="toggleFile('${f.filename}', this.checked)">
                        <span class="slider"></span>
                    </label>

                    <div style="display: flex; gap: 4px; align-items: center; justify-content: flex-end; width: 90px;">
                        ${updateBtn}
                        <button class="btn btn-danger" style="padding: 5px 8px; font-size: 11px;" onclick="deleteFile('${f.filename}')" title="Удалить файл">🗑️</button>
                    </div>
                `;
                list.appendChild(row);
            });
        }

        function renderFileSkeletons(container, count = 3) {
            container.innerHTML = '';
            for (let i = 0; i < count; i++) {
                const sk = document.createElement('div');
                sk.className = 'mod-row';
                sk.innerHTML = `
                    <div class="skeleton-shimmer" style="width: 18px; height: 18px;"></div>
                    <div class="skeleton-shimmer" style="width: 44px; height: 44px; border-radius: 8px;"></div>
                    <div style="flex: 2; display: flex; flex-direction: column; gap: 6px;">
                        <div class="skeleton-shimmer" style="width: 60%; height: 14px;"></div>
                        <div class="skeleton-shimmer" style="width: 35%; height: 10px;"></div>
                    </div>
                    <div style="flex: 1.4; display: flex; flex-direction: column; gap: 6px;">
                        <div class="skeleton-shimmer" style="width: 50%; height: 12px;"></div>
                        <div class="skeleton-shimmer" style="width: 70%; height: 10px;"></div>
                    </div>
                    <div class="skeleton-shimmer" style="width: 42px; height: 22px; border-radius: 20px;"></div>
                    <div class="skeleton-shimmer" style="width: 32px; height: 24px; border-radius: 6px;"></div>
                `;
                container.appendChild(sk);
            }
        }

        function renderCatalogSkeletons(container, count = 6) {
            container.innerHTML = '';
            for (let i = 0; i < count; i++) {
                const sk = document.createElement('div');
                sk.className = 'skeleton-card';
                sk.innerHTML = `
                    <div class="skeleton-shimmer" style="width: 54px; height: 54px; border-radius: 6px; flex-shrink: 0;"></div>
                    <div style="flex: 1; display: flex; flex-direction: column; gap: 8px; overflow: hidden;">
                        <div class="skeleton-shimmer" style="width: 65%; height: 14px;"></div>
                        <div class="skeleton-shimmer" style="width: 45%; height: 10px;"></div>
                        <div class="skeleton-shimmer" style="width: 90%; height: 10px;"></div>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 6px; flex-shrink: 0;">
                        <div class="skeleton-shimmer" style="width: 80px; height: 26px; border-radius: 6px;"></div>
                    </div>
                `;
                container.appendChild(sk);
            }
        }

        function toggleSelectAllMods(checked) {
            document.querySelectorAll('.mod-item-check').forEach(cb => { cb.checked = checked; });
        }

        function getSelectedFilenames() {
            const selected = [];
            document.querySelectorAll('.mod-item-check:checked').forEach(cb => { selected.push(cb.value); });
            return selected;
        }

        async function toggleSelectedFiles(targetState) {
            const files = getSelectedFilenames();
            if (files.length === 0) {
                showToast("Выберите хотя бы один файл галочкой!", "info");
                return;
            }
            for (const fname of files) {
                const isCurrentlyDisabled = fname.endsWith('.disabled');
                if (targetState && isCurrentlyDisabled) {
                    await window.pywebview.api.toggle_instance_file(currentViewingInstId, currentResourceTab, fname);
                } else if (!targetState && !isCurrentlyDisabled) {
                    await window.pywebview.api.toggle_instance_file(currentViewingInstId, currentResourceTab, fname);
                }
            }
            await refreshModalInstanceFiles();
            showToast("Выбранные файлы обновлены", "success");
        }

        async function deleteSelectedFiles() {
            const files = getSelectedFilenames();
            if (files.length === 0) {
                showToast("Выберите хотя бы один файл галочкой!", "info");
                return;
            }
            for (const fname of files) {
                await window.pywebview.api.delete_instance_file(currentViewingInstId, currentResourceTab, fname);
            }
            await refreshModalInstanceFiles();
            showToast("Выбранные файлы удалены", "info");
        }

        async function toggleFile(fname, isChecked) {
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
            await window.pywebview.api.delete_instance(currentViewingInstId);
            closeModal('instanceViewModal');
            await refreshData();
        }

        function editCurrentInstance() {
            const inst = globalConfig.instances.find(i => i.id === currentViewingInstId);
            if (!inst) return;
            document.getElementById('modalInstId').value = inst.id;
            document.getElementById('modalInstName').value = inst.name;
            document.getElementById('modalInstIcon').value = inst.icon || '🟧';
            closeModal('instanceViewModal');
            showModal('createModal');
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

        function openCreateModal() {
            document.getElementById('modalInstId').value = '';
            document.getElementById('modalInstName').value = '';
            showModal('createModal');
        }

        async function saveModalInstance() {
            const id = document.getElementById('modalInstId').value;
            const name = document.getElementById('modalInstName').value || 'Моя сборка';
            const icon = document.getElementById('modalInstIcon').value || '🟧';
            const mcVer = document.getElementById('modalMcVer').value;
            const loader = document.getElementById('modalLoader').value;
            const loaderVer = document.getElementById('modalLoaderVer').value;

            await window.pywebview.api.save_instance({
                id: id || undefined, name, icon, mc_version: mcVer, loader, loader_version: loaderVer
            });
            closeModal('createModal');
            await refreshData();
        }

        function onModpackSearchInput() {
            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => triggerModpackSearch(1), 250);
        }

        async function triggerModpackSearch(page = 1) {
            modpackPage = page;
            const grid = document.getElementById('modpacksGrid');
            renderCatalogSkeletons(grid, 6);

            const query = document.getElementById('modpackSearchInput').value;
            const platform = document.getElementById('modpackCatalogPlatform').value || 'modrinth';
            const loader = document.getElementById('modpackLoaderFilter').value;
            const ver = document.getElementById('modpackVersionFilter').value;
            
            const res = await window.pywebview.api.fetch_resources(query, "modpacks", loader, ver, modpackPage, 10, platform);
            modpackTotalPages = res.total_pages || 1;
            renderModpackItems(res.items, platform);
            document.getElementById('modpackPageInfo').textContent = `Страница ${modpackPage} из ${modpackTotalPages}`;
            document.getElementById('modPrevPage').disabled = modpackPage <= 1;
            document.getElementById('modNextPage').disabled = modpackPage >= modpackTotalPages;
        }

        function changeModpackPage(delta) {
            const p = modpackPage + delta;
            if (p >= 1 && p <= modpackTotalPages) triggerModpackSearch(p);
        }

        function renderModpackItems(items, platform = "modrinth") {
            const grid = document.getElementById('modpacksGrid');
            grid.innerHTML = items.length === 0 ? `<div class="empty-state" style="grid-column: 1/-1; padding: 20px; text-align: center; color: var(--text-secondary);">Ничего не найдено</div>` : '';
            items.forEach(item => {
                const card = document.createElement('div');
                card.className = 'resource-card';
                card.innerHTML = `
                    <img class="resource-card-img" src="${item.icon || 'https://cdn-icons-png.flaticon.com/512/3344/3344384.png'}" onerror="this.src='https://cdn-icons-png.flaticon.com/512/3344/3344384.png'">
                    <div class="resource-card-center">
                        <div class="resource-card-title-row">
                            <span class="resource-card-title">${item.title}</span>
                            <span class="badge-type badge-mr">Modpack</span>
                        </div>
                        <div class="resource-card-meta">Автор: ${item.author} • ⬇ ${(item.downloads || 0).toLocaleString()}</div>
                        <div class="resource-card-desc">${item.desc}</div>
                    </div>
                    <button class="btn" style="padding: 8px 14px; font-size: 11px;" onclick="window.pywebview.api.install_modpack_as_instance('${item.id}', '${item.title.replace(/'/g, "\\'")}', '${item.icon}', '${platform}')">⬇ Установить</button>
                `;
                grid.appendChild(card);
            });
        }

        function openAddModsModal() {
            showModal('addModsModal');
            if (currentViewingInstId) {
                document.getElementById('modTargetInstance').value = currentViewingInstId;
            }
            triggerAutoSearch(1);
        }

        function onTargetInstanceChange() { triggerAutoSearch(1); }
        function onModSearchInput() {
            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => triggerAutoSearch(1), 250);
        }

        async function triggerAutoSearch(page = 1) {
            modCatalogPage = page;
            const grid = document.getElementById('catalogGrid');
            renderCatalogSkeletons(grid, 6);

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
            const installedDisplayNames = new Set(cachedInstalledFiles.map(f => (f.display_name || '').toLowerCase().replace(/[^a-z0-9]/g, '')));

            let itemsToRender = currentRawCatalogItems || [];

            grid.innerHTML = itemsToRender.length === 0 ? `<div class="empty-state" style="grid-column: 1/-1; padding: 20px; text-align: center; color: var(--text-secondary);">Ничего не найдено</div>` : '';

            itemsToRender.forEach(item => {
                const card = document.createElement('div');
                card.className = 'resource-card';
                const isCf = item.platform === 'curseforge';
                const platBadge = isCf ? '<span class="badge-type badge-cf">CurseForge</span>' : '<span class="badge-type badge-mr">Modrinth</span>';
                const fallbackImg = isCf ? 'https://media.forgecdn.net/avatars/thumbnails/282/467/256/256/637289313020452406.png' : 'https://cdn-icons-png.flaticon.com/512/3344/3344384.png';

                const itemClean = (item.title || '').toLowerCase().replace(/[^a-z0-9]/g, '');
                const isInstalled = installedCleanNames.has(itemClean) || installedDisplayNames.has(itemClean);
                
                let actionBtnHtml = `<button class="btn" style="padding: 6px 12px; font-size: 11px;" onclick="smartInstallResource('${item.id}', '${item.platform}')">⬇ Установить</button>`;
                if (isInstalled) {
                    actionBtnHtml = `<button class="btn btn-installed" style="padding: 6px 12px; font-size: 11px;">✓ Установлено</button>`;
                }

                card.innerHTML = `
                    <img class="resource-card-img" src="${item.icon || fallbackImg}" onerror="this.src='${fallbackImg}'">
                    <div class="resource-card-center">
                        <div class="resource-card-title-row">
                            <span class="resource-card-title">${item.title}</span>
                            ${platBadge}
                        </div>
                        <div class="resource-card-meta">Автор: ${item.author} • ⬇ ${(item.downloads || 0).toLocaleString()}</div>
                        <div class="resource-card-desc">${item.desc}</div>
                    </div>
                    <div class="resource-card-actions">
                        ${actionBtnHtml}
                        <button class="btn btn-secondary" style="padding: 6px 10px; font-size: 11px;" onclick="openResourceDetails('${item.id}', '${item.platform}')">Файлы</button>
                    </div>
                `;
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
            showToast("Поиск подходящей версии под сборку...", "info");
            const res = await window.pywebview.api.auto_install_resource(projectId, platform, instId, rType);
            if (res.status === 'not_found') {
                showToast(res.message, "error");
            } else if (res.status === 'error') {
                showToast("Ошибка установки: " + res.message, "error");
            }
        }

        async function openResourceDetails(projectId, platform = "modrinth") {
            const details = await window.pywebview.api.get_resource_details(projectId, platform);
            if (details.status !== 'ok') {
                showToast('Ошибка загрузки данных', 'error');
                return;
            }
            const p = details.project;
            document.getElementById('detailIcon').src = p.icon || 'https://cdn-icons-png.flaticon.com/512/3344/3344384.png';
            document.getElementById('detailTitle').textContent = p.title;
            document.getElementById('detailMeta').textContent = `ID: ${p.id} • ${platform.toUpperCase()}`;

            const gal = document.getElementById('detailGallery');
            gal.innerHTML = '';
            currentLightboxGallery = p.gallery || [];
            
            currentLightboxGallery.forEach((img, idx) => {
                const i = document.createElement('img');
                i.style.cssText = "height: 110px; border-radius: 8px; object-fit: cover; border: 1px solid var(--border); cursor: pointer; transition: transform 0.15s;";
                i.src = img;
                i.onmouseover = () => i.style.transform = "scale(1.04)";
                i.onmouseleave = () => i.style.transform = "scale(1.0)";
                i.onclick = () => openLightbox(idx);
                gal.appendChild(i);
            });

            const vList = document.getElementById('detailVersionsList');
            vList.innerHTML = '';

            const instId = document.getElementById('modTargetInstance').value || globalConfig.active_instance_id;
            const rType = document.getElementById('modTypeSelect').value || 'mods';
            const instFiles = await window.pywebview.api.get_instance_files(instId, rType);
            const installedCleanNames = new Set(instFiles.map(f => (f.clean_name || '').toLowerCase()));

            (details.versions || []).forEach(v => {
                const f = (v.files || []).find(fl => fl.primary) || (v.files ? v.files[0] : null);
                if (!f) return;

                const isInstalled = installedCleanNames.has((f.filename || '').toLowerCase());
                let btnHtml = `<button class="btn" style="padding: 4px 10px; font-size: 11px;" onclick="installFile('${f.url}', '${f.filename}')">Скачать</button>`;
                if (isInstalled) {
                    btnHtml = `<button class="btn btn-installed" style="padding: 4px 10px; font-size: 11px;">✓ Установлено</button>`;
                }

                const row = document.createElement('div');
                row.style.cssText = 'background: #080708; padding: 8px 12px; border-radius: 6px; border: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; font-size: 12px;';
                row.innerHTML = `
                    <div>
                        <strong>${v.name}</strong>
                        <div style="font-size: 10px; color: var(--text-secondary);">MC: ${(v.game_versions || []).slice(0, 3).join(', ')} • ${(v.loaders || []).join(', ')}</div>
                    </div>
                    ${btnHtml}
                `;
                vList.appendChild(row);
            });

            showModal('modDetailsModal');
        }

        function openLightbox(index) {
            if (!currentLightboxGallery || currentLightboxGallery.length === 0) return;
            currentLightboxIndex = index;
            updateLightboxView();
            document.getElementById('galleryLightbox').classList.add('active');
        }

        function closeLightbox() {
            document.getElementById('galleryLightbox').classList.remove('active');
        }

        function changeLightboxImg(delta) {
            if (!currentLightboxGallery || currentLightboxGallery.length === 0) return;
            currentLightboxIndex = (currentLightboxIndex + delta + currentLightboxGallery.length) % currentLightboxGallery.length;
            updateLightboxView();
        }

        function updateLightboxView() {
            const img = document.getElementById('lightboxMainImg');
            const counter = document.getElementById('lightboxCounter');
            img.src = currentLightboxGallery[currentLightboxIndex];
            counter.textContent = `${currentLightboxIndex + 1} / ${currentLightboxGallery.length}`;
        }

        document.addEventListener('keydown', (e) => {
            if (document.getElementById('galleryLightbox').classList.contains('active')) {
                if (e.key === 'Escape') closeLightbox();
                if (e.key === 'ArrowLeft') changeLightboxImg(-1);
                if (e.key === 'ArrowRight') changeLightboxImg(1);
            }
        });

        function installFile(url, filename) {
            const instId = document.getElementById('modTargetInstance').value || globalConfig.active_instance_id;
            const rType = document.getElementById('modTypeSelect').value || 'mods';
            window.pywebview.api.install_resource(instId, url, filename, rType);
        }
    </script>
</body>
</html>
"""

def main():
    api = LauncherAPI()
    window = webview.create_window(
        title="Cube Launcher",
        html=HTML_CONTENT,
        js_api=api,
        width=1180,
        height=760,
        resizable=True,
        frameless=True,
        easy_drag=True
    )
    api.window = window
    webview.start(icon=ICON_PATH, debug=False)

if __name__ == "__main__":
    main()
