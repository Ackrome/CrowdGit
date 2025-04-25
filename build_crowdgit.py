import os
import sys
import subprocess
import platform

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
    elif platform == "macos":
        return 
    else:
        return os.path.join('icons', "CrowdGit.png")

def build_crowdgit(current_platform = get_platform()):
    """Builds the CrowdGit application using PyInstaller."""
    print(f"Building for platform: {current_platform}")

    # Check if PyInstaller is installed
    try:
        import PyInstaller.__main__
    except ImportError:
        print("PyInstaller is not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        import PyInstaller.__main__

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
        print("Some requirements are not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    # Base PyInstaller command
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "github_sync.py",
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

    # Execute PyInstaller
    print("Running PyInstaller...")
    subprocess.check_call(command)
    print("PyInstaller finished.")

if __name__ == "__main__":
    build_crowdgit()
