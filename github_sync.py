import logging
import tkinter as tk
from tkinter import ttk, filedialog
import threading
import os
import re
from base64 import b64decode
from github import Github
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
            print("Unknown theme")

            
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

    def cancel_operation(self):
        self.cancel_flag = True
        self.log_message("[INFO] Операция отменена пользователем.")
        self.buttons["cancel_btn"].grid_remove() # Скрываем кнопку после отмены

    def open_add_files_window(self):
        """Open window for adding files to structure"""
        print("open_add_files_window: Starting")
        logging.info("Opening add files window.")
        if hasattr(self, 'add_window') and self.add_window.winfo_exists():
            self.add_window.lift()
            print("open_add_files_window: Window already exists, lifting it")
        else:
            self.add_window = AddFilesWindow(self, self.path_var.get(), self.token_var, self.repo_var, DND_FILES)
            print("open_add_files_window: New window created")

    def remove_buttons(self):
        # Удаление кнопок
        for key in self.buttons.keys():
            try:
                self.buttons[key].grid_remove()
            except:
                pass
        try:
            self.progress.grid_remove()
            self.log_text.grid_remove()
        except:
            pass           

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

    def sync_files(self):
        """Synchronize files with GitHub repo"""
        self.uploaded.set(0)  # Reset the counter at the start of each sync

        # Шаблон регулярного выражения: subj_abbrev_type_num_name.ext (e.g. nm_hw_4_Kidysyuk.ipynb)
        pattern = re.compile(r"^([a-z]+)_(sem|hw|lec)_(\d+([_.]\d+)*)_(.+)\.(\w+)$")

        g = Github(self.token_var.get(), timeout=180)
        repo = g.get_repo(self.repo_var.get())
        student = self.student_var.get()

        logging.info("Starting file synchronization.")
        for root, _, files in os.walk(self.path_var.get()):
            if self.cancel_flag:
                self.log_message("[INFO] Синхронизация прервана.")
                return  # Выходим из метода, если установлен флаг отмены
            for file in files:
                if self.cancel_flag:
                    self.log_message("[INFO] Синхронизация прервана.")
                    return  # Выходим из метода, если установлен флаг отмены
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.path_var.get())
                github_path = rel_path.replace("\\", "/")

                # Проверка имени файла
                if "data" in rel_path.split(os.sep):
                    if student not in file:
                        continue
                else:
                    match = pattern.match(file)
                    if not match or student not in file:
                        if self.all_logs.get():
                            logging.warning(f"{file} does not match the synchronization pattern.")
                            self.log_message(f"[ОШИБКА] {file} не подходит для синхронизации!")
                        continue

                # Проверка, является ли файл бинарным
                is_binary = False
                if not file.endswith(".ipynb"):
                    try:
                        with open(full_path, "r") as f:
                            chunk = f.read(1024)  # Read a small chunk to check for text encoding
                            if '\0' in chunk:  # Check for null bytes, a strong indicator of binary
                                is_binary = True
                    except UnicodeDecodeError:
                        is_binary = True

                # Загрузка/обновление файла
                if file.endswith(".ipynb"):
                    with open(full_path, "rb") as f:
                        local_content = f.read()
                else:
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            local_content = f.read().encode("utf-8")
                    except UnicodeDecodeError:
                        logging.error(f"Error: {file} has unsupported encoding.")
                        self.log_message(f"[ОШИБКА] {file} has unsupported encoding")
                        continue

                if not local_content:
                    self.log_message(f"[ОШИБКА] {file} is empty")
                    logging.error(f"Error: {file} is empty.")
                    continue


                max_retries = 3
                retry_delay = 1  # Initial delay in seconds

                for attempt in range(max_retries):
                    try:
                        contents = repo.get_contents(github_path)
                        if contents.type == "file":
                            if file.endswith(".ipynb"):
                                blob = repo.get_git_blob(contents.sha)
                                remote_content = b64decode(blob.content) if blob.encoding == 'base64' else blob.content
                                try:
                                    if remote_content != local_content:
                                        repo.update_file(contents.path, f"Update {file}", local_content, contents.sha)
                                        self.log_message(f"[OK] {file} успешно обновлен")
                                        logging.info(f"{file} updated successfully.")
                                        self.uploaded.set(self.uploaded.get() + 1)
                                    else:
                                        self.log_message(f"[OK] {file} без изменений")
                                        logging.info(f"{file} no changes.")
                                except ReadTimeout as e:
                                    logging.warning(f"Read timed out during update_file for {file}, attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay} seconds...")
                                    self.log_message(f"[ОШИБКА] Время ожидания ответа от GitHub истекло при обновлении {file}, попытка {attempt + 1}/{max_retries}. Повторная попытка через {retry_delay} секунд...")
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
                                try:
                                    github_content = contents.decoded_content
                                except UnicodeDecodeError:
                                    github_content = b''
                                    self.log_message(f"[ОШИБКА] {file} has unsupported encoding")
                                    logging.error(f"Error: {file} has unsupported encoding.")
                                    continue
                                if github_content.encode('utf-8') != local_content:
                                    repo.update_file(contents.path, f"Update {file}", local_content.decode('utf-8'), contents.sha)
                                    self.log_message(f"[OK] {file} успешно обновлен")
                                    logging.info(f"{file} updated successfully.")
                                    self.uploaded.set(self.uploaded.get() + 1)
                                else:
                                    self.log_message(f"[OK] {file} без изменений")
                                    logging.info(f"{file} no changes.")
                        else:
                            logging.error(f"Error: {file} is not a file.")
                            self.log_message(f"[ОШИБКА] {file} is not a file")
                        break  # Exit the retry loop if successful

                    except ReadTimeout as e:
                        logging.warning(f"Read timed out for {file}, attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay} seconds...")
                        self.log_message(f"[ОШИБКА] Время ожидания ответа от GitHub истекло для {file}, попытка {attempt + 1}/{max_retries}. Повторная попытка через {retry_delay} секунд...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        if attempt == max_retries - 1:
                            self.log_message(f"[ОШИБКА] Не удалось синхронизировать {file} после {max_retries} попыток.")
                            logging.error(f"Failed to sync {file} after {max_retries} attempts: {e}")
                    except Exception as e:
                        if "Not Found" in str(e):
                            try:
                                try:
                                    repo.create_file(github_path, f"Add {file}", local_content.decode('utf-8') if not file.endswith(".ipynb") else local_content)
                                    logging.info(f"{file} uploaded successfully.")
                                    self.log_message(f"[OK] {file} успешно загружен")
                                    self.uploaded.set(self.uploaded.get() + 1)
                                except ReadTimeout as e:
                                    logging.warning(f"Read timed out during create_file for {file}, attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay} seconds...")
                                    self.log_message(f"[ОШИБКА] Время ожидания ответа от GitHub истекло при создании {file}, попытка {attempt + 1}/{max_retries}. Повторная попытка через {retry_delay} секунд...")
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

                            except ReadTimeout as e:
                                logging.warning(f"Read timed out for {file}, attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay} seconds...")
                                self.log_message(f"[ОШИБКА] Время ожидания ответа от GitHub истекло для {file}, попытка {attempt + 1}/{max_retries}. Повторная попытка через {retry_delay} секунд...")
                                time.sleep(retry_delay)
                                retry_delay *= 2  # Exponential backoff
                                if attempt == max_retries - 1:
                                    self.log_message(f"[ОШИБКА] Не удалось синхронизировать {file} после {max_retries} попыток.")
                                    logging.error(f"Failed to sync {file} after {max_retries} attempts: {e}")
                            except Exception as e:
                                self.log_message(f"[ОШИБКА] {file}: {str(e)}")
                        else:
                            self.log_message(f"[ОШИБКА] {file}: {str(e)}")
                        break

    def convert_path(self, rel_path):
        # Конвертация пути
        parts = rel_path.split(os.sep)
        if "data" in parts:
            i = parts.index("data")
            parts = parts[:i + 1] + [self.student_var.get()] + parts[i + 1:]
        if parts[0] == "FU":
            parts = parts[1:]
        return parts

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
        try:
            self.sync_files()
        except requests.exceptions.ReadTimeout as e:
            self.log_message(f"[ОШИБКА] Время ожидания ответа от GitHub истекло. Пожалуйста, проверьте ваше интернет-соединение и попробуйте позже.")
            logging.error(f"Read timed out error: {e}")
        except Exception as e:
            self.log_message(f"[ОШИБКА] Произошла ошибка при синхронизации: {str(e)}")
            logging.error(f"Error during synchronization: {e}")

        finally:
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
            print("Error: arial.ttf not found. Using default font.")
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