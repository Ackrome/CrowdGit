import logging
import tkinter as tk
from tkinter import ttk, filedialog
import threading
import os
import re
from base64 import b64decode
from github import Github, InputGitBlob 
import json
import traceback
from AddFilesWindow import AddFilesWindow
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
from github import Github, GithubException
from http.client import IncompleteRead
import urllib3
import hashlib
import sqlite3
import atexit


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),  # Log to a file
        logging.StreamHandler()  # Log to console
    ]
)

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "saved_settings.json")
# Define the application data directory
APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".crowdgit")
os.makedirs(APP_DATA_DIR, exist_ok=True)

# Define the database file path
DATABASE_FILE = os.path.join(APP_DATA_DIR, "file_metadata.db")

class SyncApp:
    def __init__(self, root):  # Инициализация приложения
        self.root = root
        self.root.title("CrowdGit")
        
        # Set the icon
        try:
            self.root.iconphoto(True, tk.PhotoImage(file="skull-icon-5253.png"))
        except tk.TclError:
            logging.error("Icon file 'skull-icon-5253.png' not found.")
        
        
        logging.info("Application started.")
        # Смотрим, юзер уже работал с приложением или нет
        settings = self.load_settings()
        GITHUB_TOKEN = settings.get("token", "")
        STUDENT_NAME = settings.get("student", "")
        self.folder_structure = settings.get("structure")
        

        self.token_var = tk.StringVar(value=GITHUB_TOKEN if GITHUB_TOKEN else "")
        self.path_var = tk.StringVar(value=os.getcwd())
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
                
        self.set_theme(settings.get("theme", get_system_theme())) # Применим тему
        
        self.token_var.trace_add(
            "write", lambda *args: self.check_token()
        )  # Добавляем отслеживание изменений токена
        self.token_var.set(GITHUB_TOKEN + " ")
        self.token_var.set(GITHUB_TOKEN)

        # Move the logic that depends on buttons here
        if not self.folder_structure:
            self.create_folder_structure()
            self.save_settings(
                self.token_var.get(),
                self.student_var.get(),
                self.folder_structure,
            )
        
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
        
        self.cancel_flag = False
        
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
        self.buttons["save_btn"] = ttk.Button(self.root, text="Сохранить профиль", command=self.save_profile)
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
            self.save_profile() # Сохраним тему
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
        self.token_entry = ttk.Entry(self.root, textvariable=self.token_var, width=40, show="*")

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
            self.save_settings(self.token_var.get(), self.student_var.get(), self.folder_structure)
            self.log_message("[OK] Структура папок создана")
            logging.info("Folder structure created successfully.")

        except Exception as e:
            self.log_message(f"[ОШИБКА] {type(e).__name__} : {str(e)}")
            logging.error(f"Error creating folder structure: {e}")

        logging.info("Finished folder structure creation.")
        self.buttons['add_files_btn'].grid()
        self.toggle_progress(False)

    @staticmethod
    def load_settings():
        # Загрузка настроек из файла
        if os.path.exists(SETTINGS_FILE):
            logging.info("Loading settings from file.")
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
                settings["theme"] = settings.get("theme", "light") # Добавим получение темы, если ее нет, то light
                return settings
        return {}
    
    @staticmethod
    def save_settings(token, student, structure={}, theme="light"): # Добавим параметр theme
        logging.info("Saving settings to file.")
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"token": token, "student": student, "structure": structure, "theme": theme}, f) # Добавим theme в словарь

    @staticmethod
    def read_file_in_chunks(file_path, chunk_size=1024 * 1024):  # 1MB chunks
        """Reads a file in chunks."""
        logging.info(f'Chunking file {file_path}')
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        logging.info(f'Finished chunking file {file_path}')
                        break
                    yield chunk
        except UnicodeDecodeError:
            with open(file_path, 'rb') as file:
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        logging.info(f'Finished chunking file {file_path}')
                        break
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

    def save_profile(self, *args):
        # Сохранение профиля
        token = self.token_var.get()
        student = self.student_var.get()
        theme = sv_ttk.get_theme() # Получим текущую тему
        if token.strip() and student.strip():
            logging.info("Saving profile.")
            self.save_settings(token, student, self.folder_structure, theme) # Передадим тему
            self.log_message("[OK] Профиль сохранён") # Вывод сообщения в лог
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
            blob = repo.get_git_blob(sha)
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

    async def sync_file_async(self, repo, file, full_path, github_path, student, pattern, session, conn, cursor):
        """Asynchronously synchronizes a single file."""
        if self.cancel_flag:
            self.log_message("[INFO] Синхронизация прервана.")
            return

        logging.info(f"Processing file: {file}")

        # Проверка имени файла
        if "data" in github_path.split("/"):
            if student not in file:
                return
        else:
            match = pattern.match(file)
            if not match or student not in file:
                if self.all_logs.get():
                    logging.warning(f"{file} does not match the synchronization pattern.")
                    self.log_message(f"[ОШИБКА] {file} не подходит для синхронизации!")
                return
        logging.info(f" file: {file} passed name check")

        # Metadata check
        last_modified = os.path.getmtime(full_path)
        file_size = os.path.getsize(full_path)
        cached_metadata = self.get_file_metadata(full_path, conn, cursor)

        if cached_metadata:
            if cached_metadata["last_modified"] == last_modified and cached_metadata["file_size"] == file_size:
                logging.info(f"{file} metadata is unchanged. Checking hash cache.")
                if cached_metadata["file_hash"] in self.file_hash_cache.values():
                    logging.info(f"{file} hash is unchanged. Skipping.")
                    self.log_message(f"[OK] {file} без изменений. Пропускаю.")
                    self.processed.set(self.processed.get() + 1) # Increment processed counter
                    return
                else:
                    logging.info(f"{file} hash is not in cache. Proceeding with hash calculation.")
            else:
                logging.info(f"{file} metadata has changed. Proceeding with hash calculation.")
        else:
            logging.info(f"{file} metadata not found in database. Proceeding with hash calculation.")

        # Calculate local file hash
        local_file_hash = await self.calculate_file_hash_async(full_path)
        if local_file_hash is None:
            logging.error(f"Failed to calculate hash for {file}. Skipping.")
            self.log_message(f"[ОШИБКА] Не удалось вычислить хеш для {file}. Пропускаю.")
            return

        # Check if the file exists remotely
        try:
            contents = repo.get_contents(github_path)
            if contents.type == "file":
                # Get remote file hash
                remote_content = await self.get_blob_async(repo, contents.sha, session)
                if remote_content is None:
                    logging.error(f"Failed to get remote content for {file}. Skipping.")
                    self.log_message(f"[ОШИБКА] Не удалось получить удаленное содержимое для {file}. Пропускаю.")
                    return
                remote_file_hash = hashlib.sha256(remote_content).hexdigest()

                # Compare hashes
                if local_file_hash == remote_file_hash:
                    logging.info(f"{file} is unchanged. Skipping.")
                    self.log_message(f"[OK] {file} без изменений. Пропускаю.")
                    self.file_hash_cache[full_path] = local_file_hash
                    self.save_file_metadata(full_path, local_file_hash, last_modified, file_size, conn, cursor)
                    self.processed.set(self.processed.get() + 1) # Increment processed counter
                    return  # Skip the file if it's unchanged
                else:
                    logging.info(f"{file} has changed. Proceeding with update.")
                    self.log_message(f"[INFO] {file} изменился. Обновляю.")
            else:
                logging.error(f"Error: {file} is not a file.")
                self.log_message(f"[ОШИБКА] {file} is not a file")
                return
        except (GithubException, requests.exceptions.ChunkedEncodingError, IncompleteRead, urllib3.exceptions.ProtocolError) as e:
            if isinstance(e, GithubException) and e.status == 404:
                logging.info(f"File {file} not found on GitHub. Creating it.")
                self.log_message(f"[INFO] Файл {file} не найден на GitHub. Создаю его.")
            else:
                logging.warning(f"Error during get_contents for {file}. Proceeding with update.")
                self.log_message(f"[ОШИБКА] Произошла ошибка при получении содержимого {file}. Обновляю.")

        # Загрузка/обновление файла
        max_retries = 5  # Increased retries
        retry_delay = 1  # Initial delay in seconds

        for attempt in range(max_retries):
            try:
                logging.info(f"Syncing file: {file}. Attempt {attempt + 1}/{max_retries}.")
                self.log_message(f"[INFO] Синхронизация файла {file}. Попытка {attempt + 1}/{max_retries}.")
                try:
                    contents = repo.get_contents(github_path)
                except (GithubException, requests.exceptions.ChunkedEncodingError, IncompleteRead, urllib3.exceptions.ProtocolError) as e:
                    if isinstance(e, GithubException) and e.status == 404:
                        logging.info(f"File {file} not found on GitHub. Creating it.")
                        self.log_message(f"[INFO] Файл {file} не найден на GitHub. Создаю его.")
                        try:
                            logging.info(f"Creating {file}")
                            #full_path = os.path.join(root, file) # this is wrong

                            logging.info(f'Getting chunks of {file}')
                            local_content_chunks = self.read_file_in_chunks(full_path)
                            local_content = b''

                            logging.info(f'Concatinatig chunks of {file}')
                            for chunk in local_content_chunks:
                                if isinstance(chunk, str):
                                    local_content += chunk.encode('utf-8')
                                else:
                                    local_content += chunk

                            logging.info(f'Uploading {file}')
                            logging.info(f"full_path: {full_path}")
                            logging.info(f"github_path: {github_path}")

                            if not isinstance(github_path, str):
                                raise TypeError(f"github_path is not a string: {type(github_path)}")
                            repo.create_file(github_path, f"Add {file}", local_content.decode('utf-8') if not file.endswith(".ipynb") else local_content)
                            logging.info(f"{file} uploaded successfully.")
                            self.log_message(f"[OK] {file} успешно загружен")
                            self.uploaded.set(self.uploaded.get() + 1)
                            self.file_hash_cache[full_path] = local_file_hash
                            self.save_file_metadata(full_path, local_file_hash, last_modified, file_size, conn, cursor)
                            self.processed.set(self.processed.get() + 1) # Increment processed counter
                            break
                        except (ReadTimeout, IncompleteRead, requests.exceptions.ChunkedEncodingError, urllib3.exceptions.ProtocolError) as e:  # Catch IncompleteRead
                            logging.warning(f"Read timed out or IncompleteRead during create_file for {file}, attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay} seconds...")
                            self.log_message(f"[ОШИБКА] Время ожидания ответа от GitHub истекло или не все данные были получены при создании {file}, попытка {attempt + 1}/{max_retries}. Повторная попытка через {retry_delay} секунд...")
                            time.sleep(retry_delay)
                            retry_delay *= 2
                            if attempt == max_retries - 1:
                                self.log_message(f"[ОШИБКА] Не удалось создать {file} после {max_retries} попыток.")
                                logging.error(f"Failed to create {file} after {max_retries} attempts: {e}")
                            continue  # Continue to the next attempt
                        except Exception as e:
                            self.log_message(f"[ОШИБКА] {file}: {str(e)}")
                            logging.error(f"Error creating file {file}: {e}")
                            break
                    else:
                        logging.warning(f"Error during get_contents for {file}, attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay} seconds...")
                        self.log_message(f"[ОШИБКА] Произошла ошибка при получении содержимого {file}, попытка {attempt + 1}/{max_retries}. Повторная попытка через {retry_delay} секунд...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        if attempt == max_retries - 1:
                            self.log_message(f"[ОШИБКА] Не удалось получить содержимое {file} после {max_retries} попыток.")
                            logging.error(f"Failed to get contents {file} after {max_retries} attempts: {e}")
                        continue
                if contents.type == "file":
                    if file.endswith(".ipynb"):
                        logging.info('.ipynb detected')
                        with open(full_path, "rb") as f:
                            local_content = f.read()
                            logging.info('.ipynb contend read')

                        logging.info('getting blob')
                        remote_content = await self.get_blob_async(repo, contents.sha, session)
                        logging.info('.ipynb content decoded')

                        try:
                            if remote_content != local_content:
                                logging.info(f"{file} started updating")
                                repo.update_file(contents.path, f"Update {file}", local_content, contents.sha)
                                self.log_message(f"[OK] {file} успешно обновлен")
                                logging.info(f"{file} updated successfully.")
                                self.uploaded.set(self.uploaded.get() + 1)
                                self.file_hash_cache[full_path] = local_file_hash
                                self.save_file_metadata(full_path, local_file_hash, last_modified, file_size, conn, cursor)
                                self.processed.set(self.processed.get() + 1) # Increment processed counter
                            else:
                                self.log_message(f"[OK] {file} без изменений")
                                logging.info(f"{file} no changes.")
                                self.file_hash_cache[full_path] = local_file_hash
                                self.save_file_metadata(full_path, local_file_hash, last_modified, file_size, conn, cursor)
                                self.processed.set(self.processed.get() + 1) # Increment processed counter
                        except (ReadTimeout, IncompleteRead, requests.exceptions.ChunkedEncodingError, urllib3.exceptions.ProtocolError) as e:  # Catch IncompleteRead
                            logging.warning(f"Read timed out or IncompleteRead during update_file for {file}, attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay} seconds...")
                            self.log_message(f"[ОШИБКА] Время ожидания ответа от GitHub истекло или не все данные были получены при обновлении {file}, попытка {attempt + 1}/{max_retries}. Повторная попытка через {retry_delay} секунд...")
                            time.sleep(retry_delay)
                            retry_delay *= 2
                            if attempt == max_retries - 1:
                                self.log_message(f"[ОШИБКА] Не удалось обновить {file} после {max_retries} попыток.")
                                logging.error(f"Failed to update {file} after {max_retries} attempts: {e}")
                            continue  # Continue to the next attempt
                        except Exception as e:
                            self.log_message(f"[ОШИБКА] {file}: {str(e)}")
                            logging.error(f"Error updating file {file}: {e}")
                            break
                    else:
                        logging.info(f'started loading chunks of {file}')
                        local_content_chunks = self.read_file_in_chunks(full_path)
                        remote_content = b''
                        try:
                            logging.info(f'started decoding {file}')
                            github_content = contents.decoded_content
                            remote_content = github_content.encode('utf-8')
                            logging.info(f'decoded {file}')
                        except UnicodeDecodeError:
                            self.log_message(f"[ОШИБКА] {file} has unsupported encoding")
                            logging.error(f"Error: {file} has unsupported encoding.")
                            continue

                        local_content = b''

                        logging.info(f'Concatinatig chunks of {file}')
                        for chunk in local_content_chunks:
                            if isinstance(chunk, str):
                                local_content += chunk.encode('utf-8')
                            else:
                                local_content += chunk

                        logging.info(f'Loading {file} to remote')
                        if remote_content != local_content:
                            repo.update_file(contents.path, f"Update {file}", local_content.decode('utf-8') if not file.endswith(".ipynb") else local_content, contents.sha)
                            self.log_message(f"[OK] {file} успешно обновлен")
                            logging.info(f"{file} updated successfully.")
                            self.uploaded.set(self.uploaded.get() + 1)
                            self.file_hash_cache[full_path] = local_file_hash
                            self.save_file_metadata(full_path, local_file_hash, last_modified, file_size, conn, cursor)
                            self.processed.set(self.processed.get() + 1) # Increment processed counter
                        else:
                            self.log_message(f"[OK] {file} без изменений")
                            logging.info(f"{file} no changes.")
                            self.file_hash_cache[full_path] = local_file_hash
                            self.save_file_metadata(full_path, local_file_hash, last_modified, file_size, conn, cursor)
                            self.processed.set(self.processed.get() + 1) # Increment processed counter
                else:
                    logging.error(f"Error: {file} is not a file.")
                    self.log_message(f"[ОШИБКА] {file} is not a file")
                logging.info('successfull sync')
                break  # Exit the retry loop if successful

            except (ReadTimeout, IncompleteRead, requests.exceptions.ChunkedEncodingError, urllib3.exceptions.ProtocolError) as e:  # Catch IncompleteRead
                logging.warning(f"Read timed out or IncompleteRead for {file}, attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay} seconds...")
                self.log_message(f"[ОШИБКА] Время ожидания ответа от GitHub истекло или не все данные были получены для {file}, попытка {attempt + 1}/{max_retries}. Повторная попытка через {retry_delay} секунд...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                if attempt == max_retries - 1:
                    self.log_message(f"[ОШИБКА] Не удалось синхронизировать {file} после {max_retries} попыток.")
                    logging.error(f"Failed to sync {file} after {max_retries} attempts: {e}")
            except Exception as e:
                logging.error(f"Error during sync for {file}: {e}")
                traceback.print_exc()
                self.log_message(f"[ОШИБКА] {file}: {str(e)}")
                break
                       
    async def sync_files_async(self, conn, cursor):
        """Asynchronously synchronizes files with GitHub repo."""
        self.uploaded.set(0)  # Reset the counter at the start of each sync
        self.processed.set(0) # Reset the counter at the start of each sync

        # Шаблон регулярного выражения: subj_abbrev_type_num_name.ext (e.g. nm_hw_4_Kidysyuk.ipynb)
        pattern = re.compile(r"^([a-z]+)_(sem|hw|lec)_(\d+([_.]\d+)*)_(.+)\.(\w+)$")

        g = Github(self.token_var.get(), timeout=180)
        repo = g.get_repo(self.repo_var.get())
        student = self.student_var.get()
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for root, _, files in os.walk(self.path_var.get()):
                if self.cancel_flag:
                    self.log_message("[INFO] Синхронизация прервана.")
                    return  # Выходим из метода, если установлен флаг отмены
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.path_var.get())
                    github_path = rel_path.replace(os.path.sep, "/")
                    task = asyncio.create_task(self.sync_file_async(repo, file, full_path, github_path, student, pattern, session, conn, cursor))
                    tasks.append(task)
            await asyncio.gather(*tasks)

    def threaded_sync(self):
        # Потоковая синхронизация
        logging.info("Starting threaded synchronization.")
        try:
            # Проверка интернет-соединения
            requests.get("https://api.github.com", timeout=5)  # Проверяем доступность GitHub
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
        self.cancel_flag = False # Сбрасываем флаг отмены
        self.buttons["cancel_btn"].grid() # Показываем кнопку отмены
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        try:
            asyncio.run(self.sync_files_async(conn, cursor))
        except requests.exceptions.ReadTimeout as e:
            self.log_message(f"[ОШИБКА] Время ожидания ответа от GitHub истекло. Пожалуйста, проверьте ваше интернет-соединение и попробуйте позже.")
            logging.error(f"Read timed out error: {e}")
        except Exception as e:
            self.log_message(f"[ОШИБКА] Произошла ошибка при синхронизации: {str(e)}")
            logging.error(f"Error during synchronization: {e}")

        finally:
            conn.close()
            self.log_message(f"[INFO] Синхронизация завершена. Загружено: {self.uploaded.get()}. Обработано: {self.processed.get()}")
            logging.info(f"Synchronization completed. Uploaded: {self.uploaded.get()}. Processed: {self.processed.get()}")
            self.buttons["cancel_btn"].grid_remove() # Скрываем кнопку после завершения
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
        self.rotated_canvas.tag_bind(self.rotated_image_id, "<Button-1>", self.save_profile)

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
    logging.info("Starting application.")
    root = TkinterDnD.Tk() # Создание окна
    app = SyncApp(root)
    root.mainloop()