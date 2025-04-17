import platform
import subprocess
import winreg
import os


def get_windows_theme():
    """Gets the current Windows theme (light or dark)."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if value == 1 else "dark"
    except FileNotFoundError:
        return "light"  # Default to light if the key is not found
    except Exception as e:
        print(f"Error getting Windows theme: {e}")
        return "light"

def get_macos_theme():
    """Gets the current macOS theme (light or dark)."""
    try:
        command = ["defaults", "read", "-g", "AppleInterfaceStyle"]
        output = subprocess.check_output(command).decode("utf-8").strip()
        return "dark" if output == "Dark" else "light"
    except subprocess.CalledProcessError:
        return "light"  # Default to light if the key is not found
    except Exception as e:
        print(f"Error getting macOS theme: {e}")
        return "light"

def get_linux_theme():
    """Gets the current Linux (GNOME) theme (light or dark)."""
    try:
        command = ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"]
        output = subprocess.check_output(command).decode("utf-8").strip()
        return "dark" if "dark" in output.lower() else "light"
    except subprocess.CalledProcessError:
        return "light"  # Default to light if the key is not found
    except Exception as e:
        print(f"Error getting Linux theme: {e}")
        return "light"

def get_system_theme():
    """Gets the current system theme (light or dark)."""
    system = platform.system()
    if system == "Windows":
        return get_windows_theme()
    elif system == "Darwin":  # macOS
        return get_macos_theme()
    elif system == "Linux":
        return get_linux_theme()
    else:
        return "light"  # Default to light for unsupported systems


# Example usage
#theme = get_system_theme()
#print(f"System theme: {theme}")
