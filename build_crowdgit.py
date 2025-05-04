import os
import sys
import subprocess
import platform
import logging

def get_platform():
    """Возвращает текущую операционную систему."""
    system = platform.system()
    if system == "Windows":
        return "windows"
    elif system == "Darwin": # macOS
        return "macos"
    elif system == "Linux":
        return "linux"
    else:
        return "unknown"

def get_icon_path(platform_name):
    """Возвращает соответствующий путь к иконке для данной платформы."""
    if platform_name == "windows":
        return os.path.join('icons', "CrowdGit.ico")
    elif platform_name == "macos":
        return os.path.join('icons', "CrowdGit.icns")
    else: # Linux и другие
        return os.path.join('icons', "CrowdGit.png") # Предполагаем PNG для Linux

def build_crowdgit(main_script="github_sync.py", current_platform=get_platform()):
    """Собирает приложение CrowdGit с помощью PyInstaller."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    logger.info(f"Сборка для платформы: {current_platform}")

    # Проверка, установлен ли PyInstaller
    try:
        import PyInstaller.__main__
    except ImportError:
        logger.info("PyInstaller не установлен. Установка...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            import PyInstaller.__main__ # Повторный импорт после установки
        except subprocess.CalledProcessError as e:
            logger.error(f"Не удалось установить PyInstaller: {e}")
            sys.exit(1)
        except ImportError:
             logger.error("Не удалось импортировать PyInstaller даже после попытки установки.")
             sys.exit(1)


    # Проверка, установлены ли зависимости (опционально, но полезно)
    # Можно добавить проверку requirements.txt, как в вашем оригинальном коде, если он есть
    try:
        import aiohttp
        import sv_ttk
        import github
        import certifi
        import requests
        import PIL
        import tkinterdnd2
    except ImportError:
        logger.info("Некоторые зависимости не установлены. Установка из requirements.txt...")
        try:
            # Убедитесь, что файл requirements.txt существует в том же каталоге
            requirements_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
            if os.path.exists(requirements_path):
                 subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_path])
            else:
                 logger.warning("Файл requirements.txt не найден. Пропуск установки зависимостей.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Не удалось установить зависимости: {e}")
            # Решите, следует ли прерывать сборку, если зависимости не установлены
            # sys.exit(1)

    # Базовая команда PyInstaller
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        main_script,
        "--name=CrowdGit",
        "--windowed",  # Предотвращает появление окна консоли
        "--onefile",  # Создает один исполняемый файл
        "--clean",  # Очищает кэш PyInstaller перед сборкой
        "--noconfirm", # Не запрашивать подтверждение перезаписи
        "--log-level=INFO",
    ]

    # Добавление иконки, если она существует
    icon_path = get_icon_path(current_platform)
    if icon_path and os.path.exists(icon_path):
        command.append(f"--icon={icon_path}")
    else:
        logger.warning(f"Файл иконки не найден по пути: {icon_path}")


    # Добавление скрытых импортов для зависимостей, которые PyInstaller может пропустить
    hidden_imports = [
        "aiohttp", "sv_ttk", "github", "certifi", "requests", "PIL",
        "tkinterdnd2", "urllib3", "sqlite3", "asyncio", "tkinter", "tkinter.ttk",
        "base64", "json", "traceback", "os", "re", "logging", "threading",
        "hashlib", "atexit", "binascii", "platform", "urllib.request", "http.client",
        "requests.exceptions", "urllib3.exceptions", "PIL.Image", "PIL.ImageDraw",
        "PIL.ImageFont", "PIL.ImageTk", "tkinter.filedialog", "tkinter.messagebox",
    ]
    for hidden_import in hidden_imports:
        command.append(f"--hidden-import={hidden_import}")

    # Добавление файлов данных (например, папки icons)
    # ИСПРАВЛЕНИЕ: Используем os.pathsep в качестве разделителя
    data_to_add = os.path.join('icons') # Путь к папке icons
    if os.path.exists(data_to_add):
         # Формат: --add-data "исходный_путь{разделитель}путь_назначения_в_сборке"
         command.append(f"--add-data={data_to_add}{os.pathsep}icons")
    else:
         logger.warning(f"Папка с данными '{data_to_add}' не найдена. Пропуск добавления данных.")


    # Выполнение PyInstaller
    logger.info("Запуск PyInstaller...")
    logger.info(f"Команда: {' '.join(command)}") # Выводим команду для отладки
    try:
        subprocess.check_call(command)
        logger.info("PyInstaller успешно завершил работу.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка PyInstaller: {e}")
        logger.error(f"Код возврата: {e.returncode}")
        # Можно добавить вывод stdout и stderr для детальной диагностики
        # logger.error(f"Stdout: {e.stdout}")
        # logger.error(f"Stderr: {e.stderr}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Произошла непредвиденная ошибка во время выполнения PyInstaller: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_crowdgit()