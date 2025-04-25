import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import re
from base64 import b64decode, b64encode
import base64
from github import Github, GithubException
import json
import traceback
from AddFilesWindow import AddFilesWindow
from LoadWindow import LoadWindow
from ToolTip import ToolTip
from PIL import Image, ImageDraw, ImageFont, ImageTk
from get_theme import get_system_theme
import sv_ttk
import time
import requests
from requests.exceptions import ReadTimeout
from tkinterdnd2 import DND_FILES, TkinterDnD
import asyncio
import aiohttp
from aiohttp import ClientSession
from http.client import IncompleteRead
import urllib3
import hashlib
import sqlite3
import atexit
import binascii
import certifi
import platform
from urllib.request import urlopen


TIMEOUT = 400

# Configure logging - Changed to 'w' mode to overwrite the log file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler("app.log", mode='w'),  # Log to a file, overwrite each time
        logging.StreamHandler()  # Log to console
    ]
)


system = platform.system()
# Define the database file path in the AppData directorysystem = platform.system()
if system == "Windows":
    APP_DATA_DIR = os.path.join(os.getenv('APPDATA'), 'CrowdGit')
elif system.lower() in ["darwin","macos"]:  # macOS
    APP_DATA_DIR = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'CrowdGit')
elif system == "Linux":
    APP_DATA_DIR = os.path.join(os.path.expanduser('~'), '.config', 'CrowdGit')



os.makedirs(APP_DATA_DIR, exist_ok=True)  # Create the directory if it doesn't exist
DATABASE_FILE = os.path.join(APP_DATA_DIR, "file_metadata.db")
SETTINGS_FILE = os.path.join(APP_DATA_DIR, "saved_settings.json")

class SyncApp:
    def __init__(self, root):  # Инициализация приложения
        self.root = root
        self.root.title("CrowdGit")
        self.cancel_flag = False
        self.timeout = TIMEOUT
        
        self.base_url = "https://api.github.com" # Ensure base_url is set correctly
        
        # Set the icon
        try:
            self.root.iconphoto(True, tk.PhotoImage(file="CrowdGit.png"))
        except tk.TclError:
            logging.error("Icon file 'CrowdGit.png' not found.")
        
        
        logging.info("Application started.")
        # Смотрим, юзер уже работал с приложением или нет
        settings = self.load_settings()
        GITHUB_TOKEN = settings.get("token", "")
        STUDENT_NAME = settings.get("student", "")
        PATH = settings.get("path", os.getcwd())
        THEME = settings.get("theme", get_system_theme())
        self.folder_structure = settings.get("structure")
        

        self.token_var = tk.StringVar(value=GITHUB_TOKEN if GITHUB_TOKEN else "")
        self.path_var = tk.StringVar(value=PATH if PATH else "")
        self.path_var.set(PATH)
        self.student_var = tk.StringVar(value=STUDENT_NAME if STUDENT_NAME else "")
        self.repo_var = tk.StringVar(value="kvdep/CoolSekeleton")
        self.base = tk.StringVar(value="FU")
        self.progress_running = False
        self.all_logs = tk.BooleanVar(value=False)
        self.uploaded = tk.IntVar(value=0)  # Initialize uploaded counter to 0
        
        
        self.folder_dict = {
            "seminar": "sem",
            "lecture": "lec",
            "hw": "hw",
            "data": "data",
            "other": "other",
        }
        self.buttons = {}
        self.create_widgets()
        self.create_buttons()
        self.grid_layout()
        self.create_rotated_button()
        self.update_rotated_button_colors()
                
        self.set_theme(THEME) # Применим тему
        
        self.token_var.trace_add(
            "write", lambda *args: self.check_token()
        )  # Добавляем отслеживание изменений токена
        self.token_var.set(GITHUB_TOKEN + " ")
        self.token_var.set(GITHUB_TOKEN)

        # Move the logic that depends on buttons here
        if not self.folder_structure:
            self.create_folder_structure()
            self.save_settings()
        
        logging.info("Folder structure loaded.")
        try:
            if len(self.folder_structure.items()):
                self.buttons["add_files_btn"].grid()
            else:
                self.buttons["add_files_btn"].grid_remove()
        except:
            pass

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(7, weight=1)
        
        
        self.file_hash_cache = {}  # Initialize the file hash cache
        self.blob_cache = {}  # Initialize the cache
        self.session = None
        self.create_database()
        atexit.register(self.close_database)
        self.processed = tk.IntVar(value=0) # Add processed counter
        
    # Блок внешнего вида
    def create_buttons(self):
        logging.info("Creating buttons.")
        # Создание кнопок
        self.buttons["add_files_btn"] = ttk.Button(self.root, text="Добавить файлы", command=self.open_add_files_window)
        self.buttons["create_btn"] = ttk.Button(self.root, text="Создать структуру", command=self.run_create_structure)
        self.buttons["sync_btn"] = ttk.Button(self.root, text="Синхронизировать", command=self.run_sync)
        self.buttons["all_logs_entry"] = ttk.Checkbutton(self.root, text="Все логи", variable=self.all_logs)
        self.buttons["save_btn"] = ttk.Button(self.root, text="Сохранить профиль", command=self.save_settings)
        self.buttons["create_info"] = ttk.Label(self.root, text="Скачает сюда всю структуру папок с Git. Подпапку не создаст. Не нашли нужную папку?")
        self.buttons["uploaded_info"] = ttk.Label(self.root, text="Загружено:")
        self.buttons["uploaded_show"] = ttk.Label(self.root, textvariable=self.uploaded)
        self.buttons["log_scroll"] = ttk.Scrollbar(self.root, orient="vertical", command=self.log_text.yview)
        self.buttons["log_text"] = self.log_text
        self.buttons["example_label"] = ttk.Label(self.root, text="Пример верного path: 'FU\\course_2\\semester_4\\nm_Численные Методы\\hw\\nm_hw_4_Kidysyuk.ipynb'")
        self.buttons["progress"] = self.progress
        self.buttons["add_files_btn"].grid(row=10, column=0, padx=5, pady=5)
        self.buttons["about_btn"] = ttk.Button(self.root, text="О программе", command=self.show_about_menu)
        self.buttons["about_btn"].grid(row=10, column=3, padx=5, pady=2)

        # --- Новая кнопка для открытия окна загрузки ---
        self.buttons["load_btn"] = ttk.Button(self.root, text="Загрузить с GitHub", command=self.open_load_window)
        self.buttons["load_btn"].grid(row=6, column=1, padx=5, pady=5) # Разместите кнопку где удобно

        
        self.buttons["cancel_btn"] = ttk.Button(self.root, text="Отмена", command=self.cancel_operation)
        self.buttons["cancel_btn"].grid(row=8, column=3, padx=5, pady=5) # Добавляем кнопку отмены
        self.buttons["cancel_btn"].grid_remove() # Скрываем кнопку по умолчанию


        
        # Add tooltips
        ToolTip(
            self.buttons["add_files_btn"],
            "Открывает окно для добавления файлов в локальную структуру.\n"
            "В этом окне вы можете выбрать файлы, указать их тип (домашнее задание, лекция и т.д.),\n"
            "а также указать номер задания. После этого файлы будут скопированы в соответствующие папки.",
        )
        ToolTip(
            self.buttons["create_btn"],
            "Скачивает структуру папок из репозитория GitHub в указанную локальную директорию.\n"
            "Это действие создаст локальные папки, соответствующие структуре репозитория.\n"
            "Если папки уже существуют, они не будут перезаписаны.",
        )
        ToolTip(
            self.buttons["sync_btn"],
            "Синхронизирует локальные файлы с репозиторием GitHub.\n"
            "Проверяет наличие изменений в локальных файлах и загружает их на GitHub.\n"
            "Также проверяет наличие новых файлов на GitHub и скачивает их локально.",
        )
        ToolTip(
            self.buttons["all_logs_entry"],
            "Включает отображение всех логов, включая информацию о пропущенных файлах.\n"
            "Полезно для отладки и проверки, какие файлы не были синхронизированы.",
        )
        ToolTip(
            self.buttons["save_btn"],
            "Сохраняет текущие настройки профиля (токен, имя студента).\n"
            "Сохраненные настройки будут автоматически загружены при следующем запуске приложения.",
        )
        ToolTip(
            self.buttons["create_info"],
            "Информация о том, как работает создание структуры.\n"
            "Приложение скачивает структуру папок с GitHub и создает их локально.\n"
            "Подпапки не создаются, если их нет в репозитории.",
        )
        ToolTip(
            self.buttons["uploaded_info"],
            "Показывает количество файлов, загруженных на GitHub.\n"
            "Счетчик обновляется после каждой успешной синхронизации.",
        )
        ToolTip(
            self.buttons["example_label"],
            "Показывает пример правильного пути к файлу.\n"
            "Файлы должны быть расположены в папках, соответствующих структуре репозитория.\n"
            "Имя файла должно соответствовать шаблону: 'abbrev_type_num_student.ext'.",
        )

        ToolTip(self.token_entry, "Введите ваш персональный токен доступа к GitHub.\n"
                "Токен можно сгенерировать в настройках вашего аккаунта GitHub.")
        ToolTip(self.path_entry, "Укажите путь к локальной папке, где будет храниться структура.\n"
                "Это место, куда будут скачаны файлы с GitHub и куда будут загружаться ваши локальные изменения.")
        ToolTip(self.student_entry, "Введите вашу фамилию.\n"
                "Это имя будет использоваться в именах файлов при синхронизации.")
        ToolTip(self.repo_entry, "Укажите имя репозитория на GitHub в формате 'username/repository'.\n"
                "Например: 'kvdep/CoolSekeleton'.")
        ToolTip(self.base_entry, "Укажите базовую папку для вашей структуры.\n"
                "Например: 'FU'.")
        
        ToolTip(self.log_text, "Здесь отображаются логи работы приложения.\n"
                "Вы можете отслеживать процесс синхронизации и создания структуры.")
        
        ToolTip(self.browse_btn, "Нажмите, чтобы выбрать папку для локальной структуры.")
        
        ToolTip(self.progress, "Индикатор выполнения текущей операции.")

        ToolTip(
            self.buttons["about_btn"],
            "Открывает меню с информацией о программе и настройками внешнего вида.",
        )
        
        ToolTip(self.buttons["load_btn"],
                "Открывает окно для просмотра содержимого репозитория на GitHub и скачивания файлов.\n"
                "Поддерживается скачивание обычных файлов и сборка файлов, разделенных на части.")
        
    def load_theme(self):
        """Loads the system theme and applies it to the application."""
        system_theme = get_system_theme()
        self.set_theme(system_theme)

    def show_about_menu(self):
        """Displays the 'About' menu with options for 'Creators' and 'Appearance'."""
        about_menu = tk.Menu(self.root, tearoff=0)
        about_menu.add_command(label="Создатели", command=self.show_creators)
        about_menu.add_command(label="Внешний вид", command=self.show_appearance_options)

        # Calculate the position for the menu
        x = self.buttons["about_btn"].winfo_rootx()
        y = self.buttons["about_btn"].winfo_rooty() + self.buttons["about_btn"].winfo_height()

        about_menu.tk_popup(x, y)

    def show_creators(self):
        """Displays information about the creators of the application."""
        creators_text = (
            "Программисты kvdep и ackrome столкнулись с непростой задачей: создать программу, "
            "которая должна была стать инновационной, но оставаться простой в использовании. "
            "Ночи за кодом, бесконечные дебаты о структуре и неожиданные ошибки стали их рутиной. "
            "Каждая строчка кода требовала проверки, а баланс между креативностью и функциональностью "
            "казался недостижимым. «Это как собрать пазл вслепую», — шутил ackrome, пока kvdep искал "
            "решение очередного бага. Несмотря на трудности, их упорство привело к результату — "
            "программа ожила, став символом их совместных усилий и страсти к программированию."
        )
        creators_window = tk.Toplevel(self.root)
        creators_window.title("Создатели")
        label = ttk.Label(creators_window, text=creators_text, wraplength=400, justify="left", padding=10)
        label.pack()
        creators_window.transient(self.root)  # Make it a child of the main window
        creators_window.grab_set()  # Make it modal

    def show_appearance_options(self):
        """Displays options for changing the application's appearance."""
        appearance_window = tk.Toplevel(self.root)
        appearance_window.title("Внешний вид")

        # Add theme options here (e.g., light, dark)
        ttk.Label(appearance_window, text="Выберите тему:").grid(row=0, column=0, sticky="nsew")


        # Example: Add a button to switch to a dark theme
        dark_theme_btn = ttk.Button(appearance_window, text="Темная тема", command=lambda: self.set_theme("dark"))
        dark_theme_btn.grid(row=1, column=0, sticky='nsew')


        # Example: Add a button to switch to a light theme
        light_theme_btn = ttk.Button(appearance_window, text="Светлая тема", command=lambda: self.set_theme("light"))
        light_theme_btn.grid(row=2, column=0, sticky='nsew')
        
        # Example: Add a button to switch to a light theme
        light_theme_btn = ttk.Button(appearance_window, text="Использовать системную", command=lambda: self.load_theme())
        light_theme_btn.grid(row=3, column=0, sticky='nsew')
    
    def set_theme(self, theme):
        """Sets the application's theme (light or dark)."""
        if theme in ["dark", "light"]:
            sv_ttk.set_theme(theme)
            self.update_tooltips_theme()
            self.update_rotated_button_colors()
            self.save_settings() # Сохраним тему
        else:
            logging.info("Unknown theme")
            
    def update_tooltips_theme(self):
        """Update the theme of all tooltips."""
        for widget in self.root.winfo_children():
            self.update_tooltip_theme_recursive(widget)

    def update_tooltip_theme_recursive(self, widget):
        """Recursively update the theme of tooltips in a widget and its children."""
        if isinstance(widget, tk.Canvas):
            for item in widget.find_all():
                tags = widget.gettags(item)
                for tag in tags:
                    if tag.startswith("tooltip_"):
                        tooltip_instance = widget.itemcget(item, "tooltip_instance")
                        if tooltip_instance:
                            tooltip_instance.update_theme()
        for child in widget.winfo_children():
            self.update_tooltip_theme_recursive(child)

    def set_buttons_visibility(self, visible):
        # Set button visibility
        for button in self.buttons.values():
            if visible:
                button.grid()
            else:
                button.grid_remove()

    def create_widgets(self):
        logging.info("Creating widgets.")
        # Создание виджетов
        ttk.Label(self.root, text="GitHub Token:").grid(row=0, column=0, sticky="w")
        self.token_entry = ttk.Entry(self.root, textvariable=self.token_var, width=40, show="*", validate="key")

        ttk.Label(self.root, text="Локальный путь:").grid(row=1, column=0, sticky="w")
        self.path_entry = ttk.Entry(self.root, textvariable=self.path_var, width=35)
        self.browse_btn = ttk.Button(self.root, text="Обзор", command=self.select_path)

        ttk.Label(self.root, text="Фамилия студента:").grid(row=2, column=0, sticky="w")
        self.student_entry = ttk.Entry(self.root, textvariable=self.student_var, width=40)

        ttk.Label(self.root, text="Репозиторий:").grid(row=3, column=0, sticky="w")
        self.repo_entry = ttk.Entry(self.root, textvariable=self.repo_var, width=40)

        ttk.Label(self.root, text="Базовая папка:").grid(row=4, column=0, sticky="w")
        self.base_entry = ttk.Entry(self.root, textvariable=self.base, width=40)

        self.log_text = tk.Text(height=10, state='disabled')
        self.progress = ttk.Progressbar(self.root, mode="indeterminate")

    def grid_layout(self):
        logging.info("Setting up grid layout.")
        # Размещение виджетов
        self.token_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=2, sticky="we")
        self.path_entry.grid(row=1, column=1, padx=5, pady=2, sticky="we")
        self.browse_btn.grid(row=1, column=2, padx=5, pady=2)
        self.student_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=2, sticky="we")
        self.repo_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=2, sticky="we")
        self.base_entry.grid(row=4, column=1, columnspan=2, padx=5, pady=2, sticky="we")

        self.buttons["create_info"].grid(row=5, column=1, columnspan=2, padx=5, pady=2, sticky="we")
        self.buttons["create_btn"].grid(row=5, column=0, padx=5, pady=5)

        self.buttons["sync_btn"].grid(row=6, column=0, padx=5, pady=5)
        self.log_text.grid(row=7, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        self.buttons["log_scroll"].grid(row=7, column=3, sticky="ns")

        self.buttons["uploaded_info"].grid(row=6, column=2)
        self.buttons["uploaded_show"].grid(row=6, column=3)

        self.buttons["progress"].grid(row=8, column=0, columnspan=3, sticky="we", padx=5, pady=5)
        self.buttons["example_label"].grid(row=9, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        self.buttons["save_btn"].grid(row=3, column=3, padx=5, pady=2)
        self.buttons["all_logs_entry"].grid(row=10, column=1, padx=5, pady=2)
        self.buttons["add_files_btn"].grid(row=10, column=0, padx=5, pady=5)

    # Глупая проверка валидности токена
    def check_token(self, *args):
        """Check if the token is valid and show/hide the button accordingly."""
        logging.info(f"Checking token validity. Token length: {len(self.token_var.get())}")
        if len(self.token_var.get()) == 93:
            self.set_buttons_visibility(True)
            self.root.update()  # Force the window to update its layout
            self.root.geometry("")  # Resize the window to fit its contents
        else:
            self.set_buttons_visibility(False)
            self.root.update()  # Force the window to update its layout
            self.root.geometry("")  # Resize the window to fit its contents

    # Функциональная часть
    
    def create_folder_structure(self):
        """Create local folder structure from GitHub repo"""
        logging.info("Starting folder structure creation.")
        self.toggle_progress(True) # Включаем прогрессбар
        self.buttons['add_files_btn'].grid_remove()
        if not self.token_var.get() or not self.repo_var.get():
            self.toggle_progress(False)
            return

        try:
            g = Github(self.token_var.get())
            repo = g.get_repo(self.repo_var.get())

            def get_dirs(repo_path='', local_path=self.path_var.get()): # Рекурсивная функция для обхода папок
                if self.cancel_flag:
                    self.log_message("[INFO] Создание структуры прервано.")
                    return {} # Выходим из метода, если установлен флаг отмены
                contents = repo.get_contents(repo_path)
                dct = {}
                for item in contents:
                    if self.cancel_flag:
                        self.log_message("[INFO] Создание структуры прервано.")
                        return {} # Выходим из метода, если установлен флаг отмены
                    if item.type == "dir":
                        dct[item.name] = get_dirs(item.path, local_path)
                        dir_path = os.path.join(local_path, item.path)
                        os.makedirs(dir_path, exist_ok=True)

                self.log_message(f"[OK] {repo_path} : folders uploaded {len(dct)}")
                return dct

            self.folder_structure = get_dirs()
            self.save_settings()
            self.log_message("[OK] Структура папок создана")
            logging.info("Folder structure created successfully.")

        except Exception as e:
            self.log_message(f"[ОШИБКА] {type(e).__name__} : {str(e)}")
            logging.error(f"Error creating folder structure: {e}")

        logging.info("Finished folder structure creation.")
        self.buttons['add_files_btn'].grid()
        self.toggle_progress(False)

    def load_settings(self):
        """Loads settings from a JSON file."""
        logging.info("Loading settings from file.")
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    logging.info("Settings loaded successfully.")
                    return settings
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding settings file: {e}")
                messagebox.showerror("Ошибка загрузки настроек", f"Не удалось прочитать файл настроек: {e}")
                return {}
            except Exception as e:
                logging.error(f"An unexpected error occurred while loading settings: {e}")
                messagebox.showerror("Ошибка загрузки настроек", f"Произошла непредвиденная ошибка при загрузке настроек: {e}")
                return {}
        else:
            logging.info("Settings file not found.")
            return {}


    def save_settings(self, *args):
        """Saves current settings to a JSON file."""
        logging.info("Saving settings.")
        settings = {
            "token": self.token_var.get(),
            "student": self.student_var.get(),
            "path": str(self.path_var.get()),
            "theme": sv_ttk.get_theme(), # Добавим тему
            "structure": self.folder_structure
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
            self.log_message(f"[OK] Настройки сохранены в файл: {SETTINGS_FILE}")
            logging.info("Settings saved successfully.")
        except IOError as e:
            logging.error(f"Error saving settings file: {e}")
            messagebox.showerror("Ошибка сохранения настроек", f"Не удалось записать файл настроек: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while saving settings: {e}")
            messagebox.showerror("Ошибка сохранения настроек", f"Произошла непредвиденная ошибка при сохранении настроек: {e}")




    def read_file_in_chunks(self, file_path, chunk_size=1024 * 1024):
        """Reads a file in chunks to handle large files."""
        logging.info(f"Reading file in chunks: {file_path}")
        with open(file_path, 'rb') as file:
            while True:
                chunk = file.read(chunk_size)
                if not chunk:
                    break
                logging.info(f"Chunk size: {len(chunk)}")
                logging.debug(f"Chunk content (hex): {binascii.hexlify(chunk[:100])}")
                yield chunk

    def cancel_operation(self):
        self.cancel_flag = True
        self.log_message("[INFO] Операция отменена пользователем.")
        self.buttons["cancel_btn"].grid_remove() # Скрываем кнопку после отмены

    def open_add_files_window(self):
        """Open window for adding files to structure"""
        logging.info("open_add_files_window: Starting")
        logging.info("Opening add files window.")
        if hasattr(self, 'add_window') and self.add_window.winfo_exists():
            self.add_window.lift()
            logging.info("open_add_files_window: Window already exists, lifting it")
        else:
            self.add_window = AddFilesWindow(self, self.path_var.get(), self.token_var, self.repo_var, DND_FILES)
            logging.info("open_add_files_window: New window created")       

    def open_load_window(self):
            """Opens the LoadWindow to browse and download from GitHub."""
            logging.info("Attempting to open LoadWindow.")
            token = self.token_var.get()
            repo_name = self.repo_var.get()
            local_path = self.path_var.get()

            if not token or not repo_name or not local_path:
                logging.warning("LoadWindow not opened: Missing token, repo, or local path.")
                return

            try:
                # Create and show the LoadWindow
                load_window = LoadWindow(self.root, token, repo_name, local_path, self)
                load_window.transient(self.root) # Make it a child of the main window
                load_window.grab_set() # Make it modal (optional, but can be useful)
                self.root.wait_window(load_window) # Wait until the LoadWindow is closed
                logging.info("LoadWindow closed.")

            except Exception as e:
                logging.error(f"Error opening LoadWindow: {e}")

    def save_profile(self, *args):
        # Сохранение профиля
        token = self.token_var.get()
        student = self.student_var.get()
        if token.strip() and student.strip():
            logging.info("Saving profile.")
            self.save_settings()
            logging.info("Profile saved successfully.")
        else:
            self.log_message("[ОШИБКА] Поля не должны быть пустыми")
            logging.warning("Failed to save profile: Fields are empty.")
          
    def select_path(self):
        # Выбор пути
        path = filedialog.askdirectory()
        if path:
            # Установка пути
            self.path_var.set(path)

    def log_message(self, msg):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', msg + '\n')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')
        logging.info(msg)

    def toggle_progress(self, start=True):
        logging.info(f"Toggling progress bar: {'Start' if start else 'Stop'}")
        # Включение/выключение прогрессбара
        if start:
            self.progress.start()
            self.progress_running = True
            logging.info("Progress bar started.")
        else:
            self.progress.stop()
            self.progress_running = False
            logging.info("Progress bar stopped.")

    # Работа с файлами
    def download_part_file(self, base_url, repo_path, part_name, destination_dir, attempt=1):
        """Downloads a part file from a GitHub repository.

        Args:
            base_url (str): The base URL of the GitHub API.
            repo_path (str): The path to the repository (e.g., "user/repo").
            part_name (str): The name of the part file.
            destination_dir (str): The local directory to save the part file.
            attempt (int): The current attempt number.
        """
        full_url = f"{base_url}/repos/{repo_path}/contents/{part_name}"
        headers = {
            "Authorization": f"token {self.token_var.get()}"  # Assuming you have a token
        }
        try:
            response = requests.get(full_url, headers=headers)
            response.raise_for_status()  # Raise an exception for bad status codes

            # Check if the response is JSON and contains the content
            if response.headers['Content-Type'] == 'application/json':
                content = response.json().get('content')
                if content:
                    # Decode the base64 content
                    decoded_content = base64.b64decode(content).decode('utf-8')
                    # Save the decoded content to a file
                    local_file_path = os.path.join(destination_dir, part_name.split('/')[-1])
                    logging.info(f"Saving part file to: {local_file_path}")
                    with open(local_file_path, 'w', encoding='utf-8') as f:
                        f.write(decoded_content)
                    logging.info(f"[OK] Successfully downloaded part file: {part_name}")
                else:
                    logging.error(f"Error: Content not found in response for {part_name}")
            else:
                logging.error(f"Error: Unexpected response type for {part_name}")
                # Save the content to a file
                local_file_path = os.path.join(destination_dir, part_name.split('/')[-1])
                logging.info(f"Saving part file to: {local_file_path}")
                with open(local_file_path, 'wb') as f:
                    f.write(response.content)
                logging.info(f"[OK] Successfully downloaded part file: {part_name}")

        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP error downloading part file {part_name} (Original: {os.path.splitext(os.path.basename(part_name))[0]}), attempt {attempt}/3: {e}")
            if attempt < 3:
                logging.info(f"LoadWindow: [FAILED] HTTP error while downloading part file {part_name} (Original: {os.path.splitext(os.path.basename(part_name))[0]}), attempt {attempt}/3: {e}")
                self.download_part_file(base_url, repo_path, part_name, destination_dir, attempt + 1)
            else:
                logging.info(f"LoadWindow: [FAILED] Failed to download part file {part_name}: [FAILED] Failed to download part file {part_name} (Original: {os.path.splitext(os.path.basename(part_name))[0]}) after 3 attempts: {e}")
                raise
        except requests.exceptions.RequestException as e:
            logging.error(f"Error downloading {part_name}: {e}")
            raise

    def run_create_structure(self):
        # Запуск создания структуры
        logging.info("Starting create structure process.")
        self.toggle_progress(True)
        threading.Thread(target=self.threaded_create_structure, daemon=True).start()

    def threaded_create_structure(self):
        # Потоковое создание структуры
        self.cancel_flag = False # Сбрасываем флаг отмены
        self.buttons["cancel_btn"].grid() # Показываем кнопку отмены
        self.create_folder_structure()
        self.buttons["cancel_btn"].grid_remove() # Скрываем кнопку после завершения
        self.toggle_progress(False)

    def run_sync(self):
        # Запуск синхронизации
        logging.info("Starting synchronization process.")
        self.toggle_progress(True)
        threading.Thread(target=self.threaded_sync, daemon=True).start()

    async def get_blob_async(self, repo, sha, session):
        """Asynchronously fetches and decodes a Git blob."""
        if sha in self.blob_cache:
            logging.info(f"Blob {sha} found in cache.")
            return self.blob_cache[sha]

        try:
            logging.info(f"Fetching blob {sha} from GitHub.")
            # Increased timeout for get_git_blob to 180 seconds (3 minutes)
            blob = repo.get_git_blob(sha, timeout=self.timeout)
            if blob.encoding == 'base64':
                remote_content = b64decode(blob.content)
            else:
                remote_content = blob.content
            self.blob_cache[sha] = remote_content  # Cache the blob
            return remote_content
        except GithubException as e:
            logging.error(f"Error fetching blob {sha}: {e}")
            return None

    def create_database(self):
        """Creates the database and table if they don't exist."""
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_metadata (
                    file_path TEXT PRIMARY KEY,
                    file_hash TEXT,
                    last_modified REAL,
                    file_size INTEGER
                )
            """)
            conn.commit()
            conn.close()
            logging.info(f"Database created/connected successfully at: {DATABASE_FILE}")
        except sqlite3.Error as e:
            logging.error(f"Error creating or connecting to database: {e}")
            # Handle the error appropriately (e.g., display a message to the user, exit the application)

    def close_database(self):
        """Closes the database connection."""
        pass

    def get_file_metadata(self, file_path, conn, cursor):
        """Retrieves file metadata from the database."""
        cursor.execute("SELECT file_hash, last_modified, file_size FROM file_metadata WHERE file_path=?", (file_path,))
        result = cursor.fetchone()
        if result:
            return {"file_hash": result[0], "last_modified": result[1], "file_size": result[2]}
        return None

    def save_file_metadata(self, file_path, file_hash, last_modified, file_size, conn, cursor):
        """Saves file metadata to the database."""
        cursor.execute("""
            INSERT OR REPLACE INTO file_metadata (file_path, file_hash, last_modified, file_size)
            VALUES (?, ?, ?, ?)
        """, (file_path, file_hash, last_modified, file_size))
        conn.commit()

    async def calculate_file_hash_async(self, file_path):
        """Calculates the SHA-256 hash of a file asynchronously."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.calculate_file_hash, file_path)

    def calculate_file_hash(self, file_path):
        """Calculates the SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as file:
                while True:
                    chunk = file.read(4096)  # Read in 4KB chunks
                    if not chunk:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()
        except FileNotFoundError:
            logging.error(f"File not found: {file_path}")
            return None

    async def sync_files_async(self, repo, conn, cursor):
        """
        Asynchronously iterates through local files and synchronizes them with GitHub.
        """
        logging.info("Starting asynchronous file iteration for sync.")
        self.uploaded.set(0) # Reset counters at the start of a sync run
        self.processed.set(0)

        # Шаблон регулярного выражения: subj_abbrev_type_num_name.ext (e.g. nm_hw_4_Kidysyuk.ipynb)
        pattern = re.compile(r"^([a-z]+)_(sem|hw|lec)_(\d+([_.]\d+)*)_(.+)\.(\w+)$")

        student = self.student_var.get()

        async with aiohttp.ClientSession() as session:
            tasks = []
            logging.info(f"Scanning local directory: {self.path_var.get()}")
            for root, _, files in os.walk(self.path_var.get()):
                
                
                if self.cancel_flag:
                    logging.info("File scanning cancelled.")
                    self.log_message("[INFO] Синхронизация прервана.")
                    return # Выходим из метода, если установлен флаг отмены

                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.path_var.get())
                    github_path = rel_path.replace(os.path.sep, "/")

                    # Check if the file matches the pattern and contains the student's name
                    match = pattern.match(file)
                    if not match or student.lower() not in file.lower():
                         if self.all_logs.get():
                             logging.warning(f"{file} does not match the synchronization pattern or student name. Skipping.")
                             self.log_message(f"[ОШИБКА] {file} не подходит для синхронизации (шаблон/имя студента). Не понимаю. Пропускаю.")
                         continue # Skip this file if it doesn't match

                    # If the file matches, create a task to sync it
                    task = asyncio.create_task(self.sync_file_async(repo, file, full_path, github_path, student, pattern, session, conn, cursor))
                    tasks.append(task)

            logging.info(f"Found {len(tasks)} files matching the pattern and student name to potentially sync.")

            await asyncio.gather(*tasks)

        logging.info("Finished asynchronous file iteration for sync.")
    
    async def sync_file_async(self, repo, file, full_path, github_path, student, pattern, session, conn, cursor):
        """
        Asynchronously synchronizes a single file with the GitHub repository.
        Checks file size. Files > 40MB are split, encoded, and uploaded as parts.
        Files <= 40MB are uploaded directly via Contents API.
        """
        # Check for cancellation flag
        if self.cancel_flag:
            self.log_message("[INFO] Синхронизация прервана.")
            return

        logging.info(f"Processing file: {file}")

        # File name validation based on path and pattern
        match = pattern.match(file)
        if not match or student.lower() not in file.lower():
             if self.all_logs.get():
                 logging.warning(f"{file} does not match the synchronization pattern or student name. Skipping.")
                 self.log_message(f"[ОШИБКА] {file} не подходит для синхронизации (шаблон/имя студента). Пропускаю.")
             self.processed.set(self.processed.get() + 1) # Still count as processed even if skipped by name
             return
        logging.info(f"File: {file} passed name check")

        # --- File Size Check ---
        try:
            file_size = os.path.getsize(full_path)
            # Define the size limit for direct API upload in bytes (40 MB)
            DIRECT_UPLOAD_SIZE_LIMIT_BYTES = 40 * 1024 * 1024

            if file_size > DIRECT_UPLOAD_SIZE_LIMIT_BYTES:
                 
                 logging.warning(f"File {file} ({file_size / (1024*1024):.2f} MB) exceeds the {DIRECT_UPLOAD_SIZE_LIMIT_BYTES / (1024*1024):.0f} MB limit for direct API upload.")
                 self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Файл {file} ({file_size / (1024*1024):.2f} МБ) превышает лимит ({DIRECT_UPLOAD_SIZE_LIMIT_BYTES / (1024*1024):.0f} МБ) для прямой загрузки через API. ")
                 if False:
                     # Depriciated
                    # Call the new function to handle splitting and uploading parts
                    await self.split_and_upload_parts(repo, full_path, github_path, student, conn, cursor)

                    self.processed.set(self.processed.get() + 1) # Count the original file as processed after handling parts
                    return # Exit the function after handling parts

        except FileNotFoundError:
            logging.error(f"Local file not found during size check: {full_path}. Skipping.")
            self.log_message(f"[ОШИБКА] Локальный файл не найден при проверке размера: {file}. Пропускаю.")
            self.processed.set(self.processed.get() + 1) # Count as processed
            return
        except Exception as e:
            logging.error(f"Error during file size check for {file}: {e}. Skipping.")
            self.log_message(f"[ОШИБКА] Ошибка при проверке размера файла {file}: {e}. Пропускаю.")
            self.processed.set(self.processed.get() + 1) # Count as processed
            return


        # --- Metadata and Hash Check (for files <= 40MB) ---
        # This part is only reached if the file is NOT larger than DIRECT_UPLOAD_SIZE_LIMIT_BYTES
        try:
            last_modified = os.path.getmtime(full_path)
            # file_size is already obtained above
        except FileNotFoundError:
             logging.error(f"Local file not found during metadata check: {full_path}. Skipping.")
             self.log_message(f"[ОШИБКА] Локальный файл не найден при проверке метаданных: {file}. Пропускаю.")
             self.processed.set(self.processed.get() + 1) # Count as processed
             return
        except Exception as e:
            logging.error(f"Error getting local file metadata for {file}: {e}. Skipping.")
            self.log_message(f"[ОШИБКА] Ошибка при получении метаданных локального файла {file}: {e}. Пропускаю.")
            self.processed.set(self.processed.get() + 1) # Count as processed
            return


        # Retrieve cached metadata from the database
        cached_metadata = self.get_file_metadata(full_path, conn, cursor)

        # Calculate local file hash
        local_file_hash = await self.calculate_file_hash_async(full_path)
        if local_file_hash is None:
            logging.error(f"Failed to calculate hash for {file}. Skipping.")
            self.log_message(f"[ОШИБКА] Не удалось вычислить хеш для {file}. Пропускаю.")
            self.processed.set(self.processed.get() + 1) # Count as processed
            return

        # Check if metadata is unchanged and hash is cached
        if cached_metadata:
            if cached_metadata["last_modified"] == last_modified and cached_metadata["file_size"] == file_size and cached_metadata["file_hash"] == local_file_hash:
                logging.info(f"{file} is unchanged based on metadata and hash. Skipping.")
                self.log_message(f"[OK] {file} без изменений. Пропускаю.")
                self.processed.set(self.processed.get() + 1) # Increment processed counter
                return
            else:
                 logging.info(f"File {file} metadata or hash has changed. Proceeding with sync.")
        else:
            logging.info(f"File {file} metadata not found in database. Proceeding with sync.")


        # --- File Upload/Update using Contents API (PUT) for files <= 40MB ---
        max_retries = 5
        retry_delay = 1

        repo_owner, repo_name = self.repo_var.get().split('/')
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{github_path}"
        headers = {
            "Authorization": f"token {self.token_var.get()}",
            "Accept": "application/vnd.github.v3+json"
        }

        # Determine if we are creating or updating the file on GitHub
        remote_file_sha = None
        remote_file_exists = False
        try:
            contents = repo.get_contents(github_path)
            if contents.type == "file":
                remote_file_exists = True
                remote_file_sha = contents.sha
                logging.info(f"Remote file {file} exists with SHA: {remote_file_sha}")
            else:
                 logging.error(f"Error: Path {github_path} on GitHub is not a file.")
                 self.log_message(f"[ОШИБКА] Путь {github_path} на GitHub не является файлом.")
                 self.processed.set(self.processed.get() + 1) # Count as processed
                 return # Skip if path is not a file
        except GithubException as e:
            if e.status == 404:
                logging.info(f"Remote file {file} not found on GitHub. Proceeding with creation.")
                self.log_message(f"[INFO] Удаленный файл {file} не найден на GitHub. Создаю его.")
                remote_file_exists = False
            else:
                logging.warning(f"GithubException during initial get_contents for {file}: {e}. Proceeding assuming creation/update.")
                self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Ошибка GitHub при получении содержимого {file}: {e}. Продолжаю, предполагая создание/обновление.")
                logging.error(f"Failed to get remote file SHA for {file} due to GithubException: {e}. Cannot proceed with update.")
                self.log_message(f"[ОШИБКА] Не удалось получить SHA удаленного файла {file} из-за ошибки GitHub: {e}. Не могу обновить.")
                self.processed.set(self.processed.get() + 1) # Count as processed
                return # Cannot proceed if we can't get SHA for potential update
        except Exception as e:
             logging.error(f"Unexpected error during initial get_contents for {file}: {type(e).__name__} - {e}. Cannot proceed.")
             self.log_message(f"[ОШИБКА] Неожиданная ошибка при получении содержимого {file}: {type(e).__name__} - {e}. Не могу продолжить.")
             self.processed.set(self.processed.get() + 1) # Count as processed
             return # Cannot proceed due to unexpected error


        # Read the content of the file to be uploaded and Base64 encode it
        logging.info(f'Reading and encoding content for {file}')
        try:
            local_content_chunks = self.read_file_in_chunks(full_path)
            local_content = b''.join(local_content_chunks) # Join chunks to get full content
            encoded_content = b64encode(local_content).decode('ascii')
        except MemoryError:
            logging.error(f"MemoryError while reading or encoding content for {file}. Skipping.")
            self.log_message(f"[ОШИБКА] Ошибка памяти при чтении или кодировании содержимого для {file}. Пропускаю.")
            self.processed.set(self.processed.get() + 1) # Count as processed
            return
        except Exception as e:
            logging.error(f"Error reading or encoding content for {file}: {e}. Skipping.")
            self.log_message(f"[ОШИБКА] Ошибка при чтении или кодировании содержимого для {file}: {e}. Пропускаю.")
            self.processed.set(self.processed.get() + 1) # Count as processed
            return

        if not encoded_content:
            logging.warning(f"Encoded content is empty for {file}. Skipping.")
            self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Кодированное содержимое для {file} пустое. Пропускаю.")
            self.processed.set(self.processed.get() + 1) # Count as processed
            return # Skip if file is empty

        # Prepare the request body for the Contents API
        commit_message = f"{'Update' if remote_file_exists else 'Add'} {file}"
        data = {
            "message": commit_message,
            "content": encoded_content,
            "branch": repo.default_branch # Specify the target branch
        }
        # Add SHA if updating an existing file
        if remote_file_exists and remote_file_sha:
             data["sha"] = remote_file_sha
        elif remote_file_exists and not remote_file_sha:
             logging.error(f"Remote file {file} exists but SHA could not be retrieved. Cannot update.")
             self.log_message(f"[ОШИБКА] Удаленный файл {file} существует, но не удалось получить его SHA. Не могу обновить.")
             self.processed.set(self.processed.get() + 1) # Count as processed
             return


        logging.info(f"Attempting to {'update' if remote_file_exists else 'create'} file {file} via Contents API ({url})")

        for attempt in range(max_retries):
            try:
                logging.info(f"Contents API sync attempt {attempt + 1}/{max_retries} for {file}.")
                response = requests.put(url, headers=headers, json=data, verify=certifi.where())
                logging.info(f"Contents API response status code: {response.status_code}")

                if response.status_code in [200, 201]: # 200 for update, 201 for create
                    logging.info(f"File {file} {'updated' if remote_file_exists else 'created'} successfully via Contents API.")
                    self.log_message(f"[OK] Файл {file} успешно {'обновлен' if remote_file_exists else 'создан'} через Contents API")
                    self.uploaded.set(self.uploaded.get() + 1)
                    # Save metadata for the successfully synced file
                    self.save_file_metadata(full_path, local_file_hash, last_modified, file_size, conn, cursor)
                    self.processed.set(self.processed.get() + 1) # Increment processed counter
                    return # Exit the function after successful sync
                else:
                    logging.error(f"Failed to {'update' if remote_file_exists else 'create'} file {file} via Contents API. Status Code: {response.status_code}")
                    logging.error(f"Response body: {response.text}")
                    if response.status_code == 409:
                         self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Конфликт при синхронизации {file}. Попытка повтора.")
                         logging.warning(f"Conflict (409) during Contents API sync for {file}. Retrying.")
                         pass
                    elif response.status_code == 422:
                         if "too large to be processed" in response.text:
                              logging.error(f"File {file} is too large for Contents API (>100MB limit). Response: {response.text}")
                              self.log_message(f"[ОШИБКА] Файл {file} слишком большой для загрузки через Contents API (>100MB). Используйте локальный Git.")
                              self.processed.set(self.processed.get() + 1) # Count as processed
                              return # Cannot upload files > 100MB this way, exit the retry loop
                         else:
                              self.log_message(f"[ОШИБКА] Ошибка валидации при синхронизации {file}. Тело ответа: {response.text}")
                              logging.error(f"Validation error (422) during Contents API sync for {file}. Response: {response.text}")
                              self.log_message(f"[ОШИБКА] Необрабатываемая сущность (422) при синхронизации {file}. Тело ответа: {response.text}")
                              logging.error(f"Unprocessable Entity (422) during Contents API sync for {file}. Response: {response.text}")
                              pass
                    elif response.status_code >= 400 and response.status_code < 500:
                         self.log_message(f"[ОШИБКА] Ошибка клиента ({response.status_code}) при синхронизации {file}. Тело ответа: {response.text}")
                         logging.error(f"Client error ({response.status_code}) during Contents API sync for {file}. Response: {response.text}")
                         self.processed.set(self.processed.get() + 1) # Count as processed
                         break
                    elif response.status_code >= 500:
                         self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Ошибка сервера ({response.status_code}) при синхронизации {file}. Попытка повтора.")
                         logging.warning(f"Server error ({response.status_code}) during Contents API sync for {file}. Retrying.")
                         pass
                    else:
                         self.log_message(f"[ОШИБКА] Неожиданный статус код ({response.status_code}) при синхронизации {file}. Тело ответа: {response.text}")
                         logging.error(f"Unexpected status code ({response.status_code}) during Contents API sync for {file}. Response: {response.text}")
                         self.processed.set(self.processed.get() + 1) # Count as processed
                         break

            except requests.exceptions.SSLError as e:
                 logging.error(f"SSLError during Contents API sync for {file}, attempt {attempt + 1}/{max_retries}: {e}")
                 self.log_message(f"[ОШИБКА] Ошибка SSL при синхронизации {file}, попытка {attempt + 1}/{max_retries}: {e}. Пожалуйста, проверьте настройки сети и сертификаты.")
                 if attempt == max_retries - 1:
                      self.log_message(f"[ОШИБКА] Не удалось синхронизировать {file} после {max_retries} попыток из-за ошибки SSL.")
                      logging.error(f"Failed to sync {file} after {max_retries} attempts due to SSLError.")
                      self.processed.set(self.processed.get() + 1) # Count as processed
                 time.sleep(retry_delay)
                 retry_delay *= 2
            except requests.exceptions.ConnectionError as e:
                 logging.error(f"ConnectionError during Contents API sync for {file}, attempt {attempt + 1}/{max_retries}: {e}")
                 if isinstance(e.__cause__, urllib3.exceptions.NameResolutionError):
                      logging.error(f"Underlying NameResolutionError: {e.__cause__}")
                      self.log_message(f"[ОШИБКА] Ошибка разрешения имени хоста при синхронизации {file}, попытка {attempt + 1}/{max_retries}: Не удалось разрешить 'api.github.com'. Проверьте ваше интернет-соединение и настройки DNS.")
                      self.processed.set(self.processed.get() + 1) # Count as processed
                      break
                 else:
                      self.log_message(f"[ОШИБКА] Ошибка соединения при синхронизации {file}, попытка {attempt + 1}/{max_retries}: {e}. Повторная попытка через {retry_delay} секунд...")
                      time.sleep(retry_delay)
                      retry_delay *= 2
                      if attempt == max_retries - 1:
                           self.log_message(f"[ОШИБКА] Не удалось синхронизировать {file} после {max_retries} попыток из-за ошибок соединения.")
                           logging.error(f"Failed to sync {file} after {max_retries} attempts due to connection errors: {e}")
                           self.processed.set(self.processed.get() + 1) # Count as processed
            except (ReadTimeout, IncompleteRead, requests.exceptions.ChunkedEncodingError, urllib3.exceptions.ProtocolError) as e:
                logging.warning(f"Network error during Contents API sync for {file}, attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay} seconds...")
                self.log_message(f"[ОШИБКА] Сетевая ошибка при синхронизации {file}, попытка {attempt + 1}/{max_retries}. Повторная попытка через {retry_delay} секунд...")
                time.sleep(retry_delay)
                retry_delay *= 2
                if attempt == max_retries - 1:
                    self.log_message(f"[ОШИБКА] Не удалось синхронизировать {file} после {max_retries} попыток из-за сетевых проблем.")
                    logging.error(f"Failed to sync {file} after {max_retries} attempts due to network errors: {e}")
                    self.processed.set(self.processed.get() + 1) # Count as processed
            except Exception as e:
                logging.error(f"Unexpected error during Contents API sync for {file}, attempt {attempt + 1}/{max_retries}: {type(e).__name__} - {e}")
                traceback.print_exc()
                self.log_message(f"[ОШИБКА] Неожиданная ошибка при синхронизации {file}, попытка {attempt + 1}/{max_retries}: {type(e).__name__} - {e}")
                self.processed.set(self.processed.get() + 1) # Count as processed
                break

    async def split_and_upload_parts(self, repo, original_full_path, original_github_path, student, conn, cursor):
        """
        Splits a large file into smaller binary chunks, encodes them in Base64,
        writes them to temporary .txt files with metadata, and uploads these parts
        to GitHub via the Contents API.
        """
        logging.info(f"Splitting and uploading parts for: {original_full_path}")

        part_size_bytes = 4 * 1024 * 1024 # 4 MB part size
        original_file_name = os.path.basename(original_full_path)
        temp_dir = os.path.dirname(original_full_path) # Use the same directory as the original file

        try:
            with open(original_full_path, 'rb') as f:
                part_index = 0
                parts = []
                while True:
                    chunk = f.read(part_size_bytes)
                    if not chunk:
                        break

                    # Encode the binary chunk in Base64
                    encoded_chunk = b64encode(chunk).decode('ascii')

                    # Create metadata for the part
                    # We don't know the total number of parts yet, will add in a second pass or handle during assembly
                    # For now, just store original filename and part index
                    metadata = {
                        "original_filename": original_file_name,
                        "part_index": part_index,
                        # We will add "total_parts" in a second pass or during assembly
                    }
                    metadata_string = json.dumps(metadata)

                    # Create temporary part file name (e.g., my_notebook.ipynb.part0.txt)
                    part_file_name = f"{original_file_name}.part{part_index}.txt"
                    temp_part_path = os.path.join(temp_dir, part_file_name)
                    part_github_path = f"{original_github_path}.parts/{part_file_name}" # Store parts in a subfolder on GitHub

                    # Write metadata and encoded content to the temporary part file
                    with open(temp_part_path, 'w', encoding='utf-8') as part_f:
                        part_f.write(f"METADATA:{metadata_string}\n")
                        part_f.write("CONTENT:\n")
                        part_f.write(encoded_chunk)

                    parts.append(temp_part_path)
                    part_index += 1

                total_parts = part_index
                logging.info(f"File split into {total_parts} parts.")
                self.log_message(f"[ИНФО] Файл {original_file_name} разбит на {total_parts} частей.")

                # Now, upload each part file
                upload_tasks = []
                for i, part_path in enumerate(parts):
                     # Update metadata in the part file with total_parts before uploading
                     with open(part_path, 'r+', encoding='utf-8') as part_f:
                          content = part_f.read()
                          # Find the metadata line and update it
                          metadata_line_match = re.match(r"METADATA:(.*)\n", content)
                          if metadata_line_match:
                               metadata = json.loads(metadata_line_match.group(1))
                               metadata["total_parts"] = total_parts
                               updated_metadata_string = json.dumps(metadata)
                               # Replace the old metadata line with the updated one
                               content = content.replace(metadata_line_match.group(0), f"METADATA:{updated_metadata_string}\n")
                               part_f.seek(0)
                               part_f.write(content)
                               part_f.truncate() # Trim any remaining old content if the new line is shorter

                     part_file_name = os.path.basename(part_path)
                     part_github_path = f"{original_github_path}.parts/{part_file_name}" # Store parts in a subfolder

                     # Create a task to upload this part
                     # We pass None for 'file' and 'pattern' as this is a part file, not an original file
                     # We also pass the original_full_path for database tracking
                     task = asyncio.create_task(self.upload_part_file(repo, part_path, part_github_path, original_full_path, conn, cursor))
                     upload_tasks.append(task)

                # Wait for all part upload tasks to complete
                await asyncio.gather(*upload_tasks)

                logging.info(f"Finished uploading all parts for {original_file_name}.")
                self.log_message(f"[ОК] Все части файла {original_file_name} загружены.")

                # Clean up temporary part files after successful upload
                for part_path in parts:
                    try:
                        os.remove(part_path)
                        logging.info(f"Cleaned up temporary part file: {part_path}")
                    except OSError as e:
                        logging.error(f"Error cleaning up temporary part file {part_path}: {e}")

                # Update metadata for the original file in the database to mark it as synced (via parts)
                # We store a special hash or flag to indicate it was split and uploaded as parts
                # For simplicity, let's store the hash of the *original* file and its size/modified time
                # This assumes if the original file hasn't changed, the parts on GitHub are still valid.
                original_file_hash = await self.calculate_file_hash_async(original_full_path)
                original_last_modified = os.path.getmtime(original_full_path)
                original_file_size = os.path.getsize(original_full_path)
                self.save_file_metadata(original_full_path, original_file_hash, original_last_modified, original_file_size, conn, cursor)


        except FileNotFoundError:
            logging.error(f"Original file not found during splitting: {original_full_path}. Skipping.")
            self.log_message(f"[ОШИБКА] Исходный файл не найден при разбиении: {original_file_name}. Пропускаю.")
        except Exception as e:
            logging.error(f"An error occurred during splitting or uploading parts for {original_file_name}: {e}")
            traceback.print_exc()
            self.log_message(f"[ОШИБКА] Произошла ошибка при разбиении или загрузке частей для {original_file_name}: {e}")
            # Attempt to clean up any partial files created
            for part_path in parts:
                 if os.path.exists(part_path):
                      try:
                           os.remove(part_path)
                           logging.info(f"Cleaned up partial temporary part file: {part_path}")
                      except OSError as clean_e:
                           logging.error(f"Error cleaning up partial temporary part file {part_path}: {clean_e}")

    async def upload_part_file(self, repo, part_full_path, part_github_path, original_full_path, conn, cursor):
        """
        Asynchronously uploads a single part file (.txt with Base64 encoded content)
        to GitHub via the Contents API.
        """
        if self.cancel_flag:
            self.log_message("[INFO] Загрузка частей прервана.")
            return

        part_file_name = os.path.basename(part_full_path)
        logging.info(f"Uploading part file: {part_file_name}")

        # --- Metadata and Hash Check for the part file ---
        # Check if the part file itself has changed since the last upload attempt of the original file
        # We'll use the hash of the part file and store it associated with the original file path
        try:
            part_last_modified = os.path.getmtime(part_full_path)
            part_file_size = os.path.getsize(part_full_path)
        except FileNotFoundError:
             logging.error(f"Part file not found for upload: {part_full_path}. Skipping.")
             self.log_message(f"[ОШИБКА] Файл части не найден для загрузки: {part_file_name}. Пропускаю.")
             return
        except Exception as e:
             logging.error(f"Error getting metadata for part file {part_file_name}: {e}. Skipping.")
             self.log_message(f"[ОШИБКА] Ошибка при получении метаданных для файла части {part_file_name}: {e}. Пропускаю.")
             return

        # Calculate hash of the part file
        part_file_hash = await self.calculate_file_hash_async(part_full_path)
        if part_file_hash is None:
             logging.error(f"Failed to calculate hash for part file {part_file_name}. Skipping.")
             self.log_message(f"[ОШИБКА] Не удалось вычислить хеш для файла части {part_file_name}. Пропускаю.")
             return

        # Retrieve cached metadata for the original file
        cached_metadata = self.get_file_metadata(original_full_path, conn, cursor)

        # Check if the original file's metadata and hash match the cached ones.
        # If they match, we assume the parts on GitHub are still valid and skip uploading this part.
        # This is a simplification; a more robust approach might track part hashes individually.
        # For this implementation, we rely on the original file's state.
        if cached_metadata:
             try:
                  original_last_modified = os.path.getmtime(original_full_path)
                  original_file_size = os.path.getsize(original_full_path)
                  original_file_hash = await self.calculate_file_hash_async(original_full_path) # Recalculate original hash
                  if cached_metadata["last_modified"] == original_last_modified and cached_metadata["file_size"] == original_file_size and cached_metadata["file_hash"] == original_file_hash:
                       logging.info(f"Original file {os.path.basename(original_full_path)} is unchanged. Skipping upload of part {part_file_name}.")
                       self.log_message(f"[OK] Исходный файл {os.path.basename(original_full_path)} без изменений. Пропускаю загрузку части {part_file_name}.")
                       # We don't increment processed here, as the main function counts the original file
                       return # Skip upload of this part

                  else:
                       logging.info(f"Original file {os.path.basename(original_full_path)} has changed. Proceeding with uploading part {part_file_name}.")
             except FileNotFoundError:
                  logging.warning(f"Original file {os.path.basename(original_full_path)} not found during part upload check. Proceeding with uploading part {part_file_name}.")
                  self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Исходный файл {os.path.basename(original_full_path)} не найден при проверке части. Продолжаю загрузку части {part_file_name}.")
             except Exception as e:
                  logging.error(f"Error checking original file metadata during part upload for {part_file_name}: {e}. Proceeding with upload.")
                  self.log_message(f"[ОШИБКА] Ошибка при проверке метаданных исходного файла для части {part_file_name}: {e}. Продолжаю загрузку.")


        # --- Upload Part File using Contents API (PUT) ---
        max_retries = 5
        retry_delay = 1

        repo_owner, repo_name = self.repo_var.get().split('/')
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{part_github_path}"
        headers = {
            "Authorization": f"token {self.token_var.get()}",
            "Accept": "application/vnd.github.v3+json"
        }

        # Read the content of the part file
        try:
            with open(part_full_path, 'r', encoding='utf-8') as f:
                part_content = f.read()
            encoded_content = b64encode(part_content.encode('utf-8')).decode('ascii') # Encode the text content of the part file
        except FileNotFoundError:
            logging.error(f"Part file not found during content reading for upload: {part_full_path}. Skipping.")
            self.log_message(f"[ОШИБКА] Файл части не найден при чтении содержимого для загрузки: {part_file_name}. Пропускаю.")
            return
        except Exception as e:
            logging.error(f"Error reading content for part file {part_file_name}: {e}. Skipping.")
            self.log_message(f"[ОШИБКА] Ошибка при чтении содержимого для файла части {part_file_name}: {e}. Пропускаю.")
            return


        # Determine if we are creating or updating the part file on GitHub
        remote_file_sha = None
        remote_file_exists = False
        try:
            contents = repo.get_contents(part_github_path)
            if contents.type == "file":
                remote_file_exists = True
                remote_file_sha = contents.sha
                logging.info(f"Remote part file {part_file_name} exists with SHA: {remote_file_sha}")
            else:
                 logging.error(f"Error: Path {part_github_path} on GitHub is not a file.")
                 self.log_message(f"[ОШИБКА] Путь {part_github_path} на GitHub не является файлом.")
                 return # Skip if path is not a file
        except GithubException as e:
            if e.status == 404:
                logging.info(f"Remote part file {part_file_name} not found on GitHub. Proceeding with creation.")
                self.log_message(f"[INFO] Удаленный файл части {part_file_name} не найден на GitHub. Создаю его.")
                remote_file_exists = False
            else:
                logging.warning(f"GithubException during initial get_contents for part file {part_file_name}: {e}. Proceeding assuming creation/update.")
                self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Ошибка GitHub при получении содержимого файла части {part_file_name}: {e}. Продолжаю, предполагая создание/обновление.")
                logging.error(f"Failed to get remote file SHA for part file {part_file_name} due to GithubException: {e}. Cannot proceed with update.")
                self.log_message(f"[ОШИБКА] Не удалось получить SHA удаленного файла части {part_file_name} из-за ошибки GitHub: {e}. Не могу обновить.")
                return # Cannot proceed if we can't get SHA for potential update
        except Exception as e:
             logging.error(f"Unexpected error during initial get_contents for part file {part_file_name}: {type(e).__name__} - {e}. Cannot proceed.")
             self.log_message(f"[ОШИБКА] Неожиданная ошибка при получении содержимого файла части {part_file_name}: {type(e).__name__} - {e}. Не могу продолжить.")
             return # Cannot proceed due to unexpected error


        # Prepare the request body for the Contents API
        commit_message = f"{'Update' if remote_file_exists else 'Add'} part {part_file_name}"
        data = {
            "message": commit_message,
            "content": encoded_content,
            "branch": repo.default_branch # Specify the target branch
        }
        # Add SHA if updating an existing file
        if remote_file_exists and remote_file_sha:
             data["sha"] = remote_file_sha
        elif remote_file_exists and not remote_file_sha:
             logging.error(f"Remote part file {part_file_name} exists but SHA could not be retrieved. Cannot update.")
             self.log_message(f"[ОШИБКА] Удаленный файл части {part_file_name} существует, но не удалось получить его SHA. Не могу обновить.")
             return


        logging.info(f"Attempting to {'update' if remote_file_exists else 'create'} part file {part_file_name} via Contents API ({url})")

        for attempt in range(max_retries):
            try:
                logging.info(f"Contents API sync attempt {attempt + 1}/{max_retries} for part file {part_file_name}.")
                response = requests.put(url, headers=headers, json=data, verify=certifi.where())
                logging.info(f"Contents API response status code: {response.status_code}")

                if response.status_code in [200, 201]: # 200 for update, 201 for create
                    logging.info(f"Part file {part_file_name} {'updated' if remote_file_exists else 'created'} successfully via Contents API.")
                    self.log_message(f"[OK] Файл части {part_file_name} успешно {'обновлен' if remote_file_exists else 'создан'} через Contents API")
                    # We don't increment uploaded here, as the main function counts the original file
                    return # Exit the function after successful sync
                else:
                    logging.error(f"Failed to {'update' if remote_file_exists else 'create'} part file {part_file_name} via Contents API. Status Code: {response.status_code}")
                    logging.error(f"Response body: {response.text}")
                    if response.status_code == 409:
                         self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Конфликт при синхронизации файла части {part_file_name}. Попытка повтора.")
                         logging.warning(f"Conflict (409) during Contents API sync for part file {part_file_name}. Retrying.")
                         pass
                    elif response.status_code == 422:
                         if "too large to be processed" in response.text:
                              # This should ideally not happen for parts if part size is < 40MB, but as a safeguard
                              logging.error(f"Part file {part_file_name} is too large for Contents API (>100MB limit). Response: {response.text}")
                              self.log_message(f"[ОШИБКА] Файл части {part_file_name} слишком большой для загрузки через Contents API (>100MB).")
                              return # Cannot upload this part
                         else:
                              self.log_message(f"[ОШИБКА] Ошибка валидации при синхронизации файла части {part_file_name}. Тело ответа: {response.text}")
                              logging.error(f"Validation error (422) during Contents API sync for part file {part_file_name}. Response: {response.text}")
                              self.log_message(f"[ОШИБКА] Необрабатываемая сущность (422) при синхронизации файла части {part_file_name}. Тело ответа: {response.text}")
                              logging.error(f"Unprocessable Entity (422) during Contents API sync for part file {part_file_name}. Response: {response.text}")
                              pass
                    elif response.status_code >= 400 and response.status_code < 500:
                         self.log_message(f"[ОШИБКА] Ошибка клиента ({response.status_code}) при синхронизации файла части {part_file_name}. Тело ответа: {response.text}")
                         logging.error(f"Client error ({response.status_code}) during Contents API sync for part file {part_file_name}. Response: {response.text}")
                         break
                    elif response.status_code >= 500:
                         self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Ошибка сервера ({response.status_code}) при синхронизации файла части {part_file_name}. Попытка повтора.")
                         logging.warning(f"Server error ({response.status_code}) during Contents API sync for part file {part_file_name}. Retrying.")
                         pass
                    else:
                         self.log_message(f"[ОШИБКА] Неожиданный статус код ({response.status_code}) при синхронизации файла части {part_file_name}. Тело ответа: {response.text}")
                         logging.error(f"Unexpected status code ({response.status_code}) during Contents API sync for part file {part_file_name}. Response: {response.text}")
                         break

            except requests.exceptions.SSLError as e:
                 logging.error(f"SSLError during Contents API sync for part file {part_file_name}, attempt {attempt + 1}/{max_retries}: {e}")
                 self.log_message(f"[ОШИБКА] Ошибка SSL при синхронизации файла части {part_file_name}, попытка {attempt + 1}/{max_retries}: {e}. Пожалуйста, проверьте настройки сети и сертификаты.")
                 if attempt == max_retries - 1:
                      self.log_message(f"[ОШИБКА] Не удалось синхронизировать файл части {part_file_name} после {max_retries} попыток из-за ошибки SSL.")
                      logging.error(f"Failed to sync part file {part_file_name} after {max_retries} attempts due to SSLError.")
                 time.sleep(retry_delay)
                 retry_delay *= 2
            except requests.exceptions.ConnectionError as e:
                 logging.error(f"ConnectionError during Contents API sync for part file {part_file_name}, attempt {attempt + 1}/{max_retries}: {e}")
                 if isinstance(e.__cause__, urllib3.exceptions.NameResolutionError):
                      logging.error(f"Underlying NameResolutionError: {e.__cause__}")
                      self.log_message(f"[ОШИБКА] Ошибка разрешения имени хоста при синхронизации файла части {part_file_name}, попытка {attempt + 1}/{max_retries}: Не удалось разрешить 'api.github.com'. Проверьте ваше интернет-соединение и настройки DNS.")
                      break
                 else:
                      self.log_message(f"[ОШИБКА] Ошибка соединения при синхронизации файла части {part_file_name}, попытка {attempt + 1}/{max_retries}: {e}. Повторная попытка через {retry_delay} секунд...")
                      time.sleep(retry_delay)
                      retry_delay *= 2
                      if attempt == max_retries - 1:
                           self.log_message(f"[ОШИБКА] Не удалось синхронизировать файл части {part_file_name} после {max_retries} попыток из-за ошибок соединения.")
                           logging.error(f"Failed to sync part file {part_file_name} after {max_retries} attempts due to connection errors: {e}")
            except (ReadTimeout, IncompleteRead, requests.exceptions.ChunkedEncodingError, urllib3.exceptions.ProtocolError) as e:
                logging.warning(f"Network error during Contents API sync for part file {part_file_name}, attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay} seconds...")
                self.log_message(f"[ОШИБКА] Сетевая ошибка при синхронизации файла части {part_file_name}, попытка {attempt + 1}/{max_retries}. Повторная попытка через {retry_delay} секунд...")
                time.sleep(retry_delay)
                retry_delay *= 2
                if attempt == max_retries - 1:
                    self.log_message(f"[ОШИБКА] Не удалось синхронизировать файл части {part_file_name} после {max_retries} попыток из-за сетевых проблем.")
                    logging.error(f"Failed to sync part file {part_file_name} after {max_retries} attempts due to network errors: {e}")
            except Exception as e:
                logging.error(f"Unexpected error during Contents API sync for part file {part_file_name}, attempt {attempt + 1}/{max_retries}: {type(e).__name__} - {e}")
                traceback.print_exc()
                self.log_message(f"[ОШИБКА] Неожиданная ошибка при синхронизации файла части {part_file_name}, попытка {attempt + 1}/{max_retries}: {type(e).__name__} - {e}")
                break

    def threaded_sync(self):
        """
        Starts the asynchronous file synchronization process in a separate thread.
        Includes initial internet connection check and overall error handling.
        """
        logging.info("Starting threaded synchronization.")
        try:
            # Check for internet connection before starting sync
            logging.info("Checking internet connection.")
            # Increased timeout to 180 seconds (3 minutes)
            requests.get("https://api.github.com", timeout=180, verify=certifi.where()) # Added verify here as well
            logging.info("Internet connection successful.")
        except requests.exceptions.ConnectionError:
            self.log_message(f"[ОШИБКА] Отсутствует интернет-соединение. Пожалуйста, проверьте ваше подключение к сети.")
            logging.error("No internet connection.")
            self.toggle_progress(False)
            return
        except requests.exceptions.ReadTimeout:
            self.log_message(f"[ОШИБКА] Время ожидания ответа от GitHub истекло при проверке интернет-соединения. Пожалуйста, проверьте ваше интернет-соединение и попробуйте позже.")
            logging.error("Read timed out error during internet connection check.")
            self.toggle_progress(False)
            return
        except requests.exceptions.SSLError as e: # Explicitly catch SSLError during connection check
             self.log_message(f"[ОШИБКА] Ошибка SSL при проверке интернет-соединения: {e}. Пожалуйста, проверьте настройки сети и сертификаты.")
             logging.error(f"SSLError during internet connection check: {e}")
             self.toggle_progress(False)
             return
        except Exception as e:
            # Catch any other errors during connection check
            self.log_message(f"[ОШИБКА] Неожиданная ошибка при проверке интернет-соединения: {e}")
            logging.error(f"Unexpected error during internet connection check: {e}")
            self.toggle_progress(False)
            return

        # Reset cancellation flag and show cancel button
        self.cancel_flag = False
        self.buttons["cancel_btn"].grid()

        # Connect to the database
        conn = None
        cursor = None
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            logging.info("Database connection established for sync.")
        except sqlite3.Error as e:
            self.log_message(f"[ОШИБКА] Ошибка подключения к базе данных: {e}")
            logging.error(f"Database connection error during sync: {e}")
            self.buttons["cancel_btn"].grid_remove()
            self.toggle_progress(False)
            return

        try:
            # Initialize PyGithub here as it's still used for get_contents and get_branch
            # Increased timeout for Github object
            g = Github(self.token_var.get(), timeout = self.timeout)
            repo = g.get_repo(self.repo_var.get())
            # Run the asynchronous sync process
            asyncio.run(self.sync_files_async(repo, conn, cursor)) # Pass repo to async function
        except GithubException as e:
             self.log_message(f"[ОШИБКА] Ошибка GitHub API при запуске синхронизации: {e}")
             logging.error(f"GithubException during threaded sync start: {e}")
        except requests.exceptions.ReadTimeout as e:
            self.log_message(f"[ОШИБКА] Время ожидания ответа от GitHub истекло во время синхронизации. Пожалуйста, проверьте ваше интернет-соединение и попробуйте позже.")
            logging.error(f"Read timed out error during sync: {e}")
        except Exception as e:
            # Catch any other exceptions from the async sync process
            self.log_message(f"[ОШИБКА] Произошла ошибка при синхронизации: {str(e)}")
            logging.error(f"Error during synchronization: {e}")
            traceback.print_exc() # Print traceback for debugging

        finally:
            # Close the database connection
            if conn:
                conn.close()
                logging.info("Database connection closed after sync.")
            # Log completion message and hide cancel button
            self.log_message(f"[INFO] Синхронизация завершена. Загружено: {self.uploaded.get()}. Обработано: {self.processed.get()}")
            logging.info(f"Synchronization completed. Uploaded: {self.uploaded.get()}. Processed: {self.processed.get()}")
            self.buttons["cancel_btn"].grid_remove()
            self.toggle_progress(False)
     
    # Создание повернутой кнопки
    def create_rotated_button(self):
        # Create a temporary image with text
        text = "Сохранить профиль"
        font_size = 17
        try:
            font = ImageFont.truetype("arial.ttf", font_size)  # Replace with your desired font
            logging.info("Loaded font arial.ttf.")
        except IOError:
            logging.info("Error: arial.ttf not found. Using default font.")
            font = ImageFont.load_default()

        # Create a dummy image to use for measuring text size
        dummy_image = Image.new("RGBA", (1, 1), (255, 255, 255, 0))
        draw = ImageDraw.Draw(dummy_image)
        # Use textbbox instead of textsize
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        image = Image.new("RGBA", (text_width + 20, text_height + 20), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        draw.text((10, 10), text, font=font, fill=(0, 0, 0))

        # Rotate the image
        rotated_image = image.rotate(90, expand=True)

        # Convert to PhotoImage
        self.rotated_photo = ImageTk.PhotoImage(rotated_image)

        # Create a Canvas to display the rotated image
        self.rotated_canvas = tk.Canvas(self.root, width=rotated_image.width, height=rotated_image.height, bd=0, highlightthickness=0, cursor="hand2", bg="SystemButtonFace")
        self.rotated_canvas.grid(rowspan=5, column=3, row=0, pady=5, padx=5)

        # Add the image to the Canvas with a tag
        self.rotated_image_id = self.rotated_canvas.create_image(0, 0, anchor="nw", image=self.rotated_photo)

        # Add a border to the Canvas
        self.rotated_canvas.config(bd=2, relief="groove")

        # Bind the click event to the image tag
        self.rotated_canvas.tag_bind(self.rotated_image_id, "<Button-1>", self.save_settings)

        # Remove old button
        if "save_btn" in self.buttons: # Удаление старой кнопки
            self.buttons["save_btn"].grid_remove()
            self.buttons["save_btn"].destroy()
            del self.buttons["save_btn"]

        # Add hover effect
        self.rotated_canvas.tag_bind(self.rotated_image_id, "<Enter>", self.on_enter)
        logging.info("Added hover effect to rotated button.")
        self.rotated_canvas.tag_bind(self.rotated_image_id, "<Leave>", self.on_leave) # Добавление эффекта наведения
    
        
        
        # Tooltip variables
        self.tooltip_window = None
        self.tooltip_text = "Сохраняет текущие настройки профиля (токен, имя студента)."


        
        # Bind the tooltip events directly to the canvas
        self.rotated_canvas.tag_bind(self.rotated_image_id, "<Enter>", self.show_tooltip)
        self.rotated_canvas.tag_bind(self.rotated_image_id, "<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        """Show the tooltip."""
        if self.tooltip_window is not None:
            return  # Tooltip already exists

        # Get the mouse position relative to the root window
        x, y = self.rotated_canvas.winfo_pointerxy()

        # Create the tooltip window
        self.tooltip_window = tk.Toplevel(self.root)
        self.tooltip_window.wm_overrideredirect(True)  # Remove window decorations
        self.tooltip_window.wm_geometry(f"+{x + 10}+{y + 10}")  # Position near the mouse

        # Create the tooltip label
        self.tooltip_label = tk.Label(
            self.tooltip_window,
            text=self.tooltip_text,
            justify="left",
            background=self.get_tooltip_bg_color(),
            foreground=self.get_tooltip_fg_color(),
            relief="solid",
            borderwidth=1,
            font=("tahoma", "8", "normal")
        )
        self.tooltip_label.pack(ipadx=1)

    def hide_tooltip(self, event):
        """Hide the tooltip."""
        if self.tooltip_window is not None:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def on_enter(self, event):
        logging.info("Mouse entered rotated button.")
        self.rotated_canvas.config(bg="#e0e0e0")  # Change background color on hover

    def on_leave(self, event): # Восстановление цвета
        logging.info("Mouse left rotated button.")
        self.rotated_canvas.config(bg="SystemButtonFace")  # Restore default background color
    
    def update_rotated_button_colors(self):
        """Updates the colors of the rotated button based on the current theme."""
        theme = sv_ttk.get_theme()
        if theme == "dark":
            text_color = "#ffffff"  # White text for dark theme
            bg_color = "#333333"
        else:
            text_color = "#000000"  # Black text for light theme
            bg_color = "#ffffff"
        self.update_rotated_button_text_color(text_color) # Добавим вызов метода
        # Update the tooltip colors
        if self.tooltip_window:
            self.tooltip_label.config(background=self.get_tooltip_bg_color(), foreground=self.get_tooltip_fg_color())

    def update_rotated_button_text_color(self, color):
        """Updates the text color of the rotated button."""
        # Create a temporary image with text
        text = "Сохранить профиль"
        font_size = 17
        try:
            font = ImageFont.truetype("arial.ttf", font_size)  # Replace with your desired font
        except IOError:
            font = ImageFont.load_default()

        # Create a dummy image to use for measuring text size
        dummy_image = Image.new("RGBA", (1, 1), (255, 255, 255, 0))
        draw = ImageDraw.Draw(dummy_image)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        image = Image.new("RGBA", (text_width + 20, text_height + 20), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        draw.text((10, 10), text, font=font, fill=color)
        rotated_image = image.rotate(90, expand=True)
        self.rotated_photo = ImageTk.PhotoImage(rotated_image)
        self.rotated_canvas.itemconfig(self.rotated_image_id, image=self.rotated_photo)

    def get_tooltip_bg_color(self):
        """Returns the appropriate background color for the tooltip based on the current theme."""
        theme = sv_ttk.get_theme()
        return "#333333" if theme == "dark" else "#ffffff"

    def get_tooltip_fg_color(self):
        """Returns the appropriate foreground color for the tooltip based on the current theme."""
        theme = sv_ttk.get_theme()
        return "#ffffff" if theme == "dark" else "#000000"


if __name__ == "__main__":
    print(urlopen('https://www.howsmyssl.com/a/check').read())
    logging.info("Starting application.")
    root = TkinterDnD.Tk() # Создание окна
    app = SyncApp(root)
    root.mainloop()