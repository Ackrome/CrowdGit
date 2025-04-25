import os
import sys
import subprocess
import platform
import logging

def get_platform():
    """Returns the current operating system."""
    system = platform.system()
    if system == "Windows":
        return "windows"
    elif system == "Darwin":
        return "macos"
    elif system == "Linux":
        return "linux"
    else:
        return "unknown"

def get_icon_path(platform):
    """Returns the appropriate icon path for the given platform."""
    if platform == "windows":
        return os.path.join('icons', "CrowdGit.ico")
    elif platform == "macos":
        return os.path.join('icons', "CrowdGit.icns")
    else:
        return os.path.join('icons', "CrowdGit.png")

def build_crowdgit(main_script="github_sync.py", current_platform=get_platform()):
    """Builds the CrowdGit application using PyInstaller."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    logger.info(f"Building for platform: {current_platform}")

    # Check if PyInstaller is installed
    try:
        import PyInstaller.__main__
    except ImportError:
        logger.info("PyInstaller is not installed. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            import PyInstaller.__main__
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install PyInstaller: {e}")
            sys.exit(1)

    # Check if requirements are installed
    try:
        import aiohttp
        import sv_ttk
        import github
        import certifi
        import requests
        import PIL
        import tkinterdnd2
    except ImportError:
        logger.info("Some requirements are not installed. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install requirements: {e}")
            sys.exit(1)

    # Base PyInstaller command
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        main_script,
        "--name=CrowdGit",
        "--windowed",  # Prevents the console window from appearing
        "--onefile",  # Creates a single executable file
        "--clean",  # Cleans the PyInstaller cache
        "--noconfirm", # Do not ask for confirmation
        "--log-level=INFO",
    ]

    # Add icon if available
    icon_path = get_icon_path(current_platform)
    if icon_path and os.path.exists(icon_path):
        command.append(f"--icon={icon_path}")

    # Add hidden imports for dependencies that PyInstaller might miss
    hidden_imports = [
        "aiohttp",
        "sv_ttk",
        "github",
        "certifi",
        "requests",
        "PIL",
        "tkinterdnd2",
        "urllib3",
        "sqlite3",
        "asyncio",
        "tkinter",
        "tkinter.ttk",
        "base64",
        "json",
        "traceback",
        "os",
        "re",
        "logging",
        "threading",
        "hashlib",
        "atexit",
        "binascii",
        "platform",
        "urllib.request",
        "http.client",
        "requests.exceptions",
        "urllib3.exceptions",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "PIL.ImageTk",
        "tkinter.filedialog",
        "tkinter.messagebox",
    ]
    for hidden_import in hidden_imports:
        command.append(f"--hidden-import={hidden_import}")

    # Add data files (if needed)
    # Example: command.append("--add-data=data_folder/*:data_folder")
    command.append('--add-data=icons;icons')
    # Execute PyInstaller
    logger.info("Running PyInstaller...")
    try:
        subprocess.check_call(command)
        logger.info("PyInstaller finished.")
    except subprocess.CalledProcessError as e:
        logger.error(f"PyInstaller failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_crowdgit()
