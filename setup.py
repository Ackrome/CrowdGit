import subprocess
import sys

reqs = [
    "PyGithub",  # основная библиотека для работы с GitHub
    "tkinter",   # интерфейсный фреймворк
    "threading", # стандартный модуль Python
    "os",        # стандартный модуль Python
    "re",        # стандартный модуль Python для работы с регулярными выражениями
    "base64",    # стандартный модуль Python для работы с кодированием/декодированием base64
    "requests",  # для HTTP запросов (возможно, подтягивается через PyGithub)
    "urllib3",   # зависимость для requests
    "chardet",   # опциональная зависимость для кодировок, часто используется с requests
    "certifi",   # используется для проверки SSL сертификатов в requests
    "idna",      # используется для работы с доменами и адресами в requests
    "charset-normalizer",  # альтернатива chardet в новых версиях requests
    "sv-ttk",
    "Pillow",
    "tkinterdnd2",
    "aiohttp",
    "urllib3"
]


for pkg in reqs:
    try:
        __import__(pkg.lower())
    except ImportError:
        print(f"Installing {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])