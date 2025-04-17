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
from PIL import Image, ImageDraw, ImageFont, ImageTk

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

class ToolTip:
    """
    Creates a tooltip for a given widget.
    """

    def __init__(self, widget, text="widget info"):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(100, self.showtip)

    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)

    def showtip(self, event=None):
        if self.widget.winfo_exists():
            x = y = 0
            bbox = self.widget.bbox()  # Get the bounding box of the entire widget
            if bbox is not None:
                x, y, cx, cy = bbox
                x += self.widget.winfo_rootx() + 25
                y += self.widget.winfo_rooty() + 20
                # creates a toplevel window
                self.tw = tk.Toplevel(self.widget)
                # Leaves only the label and removes the app window
                self.tw.wm_overrideredirect(True)
                self.tw.wm_geometry("+%d+%d" % (x, y))
                label = tk.Label(
                    self.tw,
                    text=self.text,
                    justify="left",
                    background="#ffffff",
                    relief="solid",
                    borderwidth=1,
                    font=("tahoma", "8", "normal"),
                )
                label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()

class SyncApp:
    def __init__(self, root):  # Инициализация приложения
        self.root = root
        self.root.title("GitHub Sync Tool")

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
        
        
        
        # Add tooltips
        ToolTip(
            self.buttons["add_files_btn"],
            "Открывает окно для добавления файлов в локальную структуру.",
        )
        ToolTip(
            self.buttons["create_btn"],
            "Скачивает структуру папок из репозитория GitHub в указанную локальную директорию.",
        )
        ToolTip(
            self.buttons["sync_btn"],
            "Синхронизирует локальные файлы с репозиторием GitHub.",
        )
        ToolTip(
            self.buttons["all_logs_entry"],
            "Включает отображение всех логов, включая информацию о пропущенных файлах.",
        )
        ToolTip(
            self.buttons["save_btn"],
            "Сохраняет текущие настройки профиля (токен, имя студента).",
        )
        ToolTip(
            self.buttons["create_info"],
            "Информация о том, как работает создание структуры.",
        )
        ToolTip(
            self.buttons["uploaded_info"],
            "Показывает количество файлов, загруженных на GitHub.",
        )
        ToolTip(
            self.buttons["example_label"],
            "Показывает пример правильного пути к файлу.",
        )


    def set_buttons_visibility(self, visible):
        # Set button visibility
        for button in self.buttons.values():
            if visible:
                button.grid()
            else:
                button.grid_remove()

    

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
                contents = repo.get_contents(repo_path)
                dct = {}
                for item in contents:
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
                return json.load(f)
        return {}

    @staticmethod
    # Сохранение настроек в файл
    def save_settings(token, student, structure={}):
        logging.info("Saving settings to file.")
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"token": token, "student": student, "structure": structure}, f)

    def open_add_files_window(self):
        """Open window for adding files to structure"""
        print("open_add_files_window: Starting")
        logging.info("Opening add files window.")
        if hasattr(self, 'add_window') and self.add_window.winfo_exists():
            self.add_window.lift()
            print("open_add_files_window: Window already exists, lifting it")
        else:
            self.add_window = AddFilesWindow(self, self.path_var.get(), self.token_var, self.repo_var)
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

    def save_profile(self, *args):
        # Сохранение профиля
        token = self.token_var.get()
        student = self.student_var.get()
        if token.strip() and student.strip():
            logging.info("Saving profile.")
            self.save_settings(token, student, self.folder_structure)
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
        try:
            self.uploaded.set(0)  # Reset the counter at the start of each sync

            # Шаблон регулярного выражения: subj_abbrev_type_num_name.ext (e.g. nm_hw_4_Kidysyuk.ipynb)
            pattern = re.compile(r"^([a-z]+)_(sem|hw|lec)_(\d+)_(.+)\.(\w+)$")

            g = Github(self.token_var.get())
            repo = g.get_repo(self.repo_var.get())
            student = self.student_var.get()

            logging.info("Starting file synchronization.")
            for root, _, files in os.walk(self.path_var.get()):
                for file in files:
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
                                self.log_message(f"{file} не подходит для синхронизации!")
                            continue

                    # Проверка, является ли файл бинарным
                    is_binary = False
                    if file.endswith(".ipynb"):
                        is_binary = False
                    else:
                        try:
                            with open(full_path, "r") as f:
                                chunk = f.read(1024)  # Read a small chunk to check for text encoding
                                if '\0' in chunk:  # Check for null bytes, a strong indicator of binary
                                    is_binary = True
                        except UnicodeDecodeError:
                            is_binary = True


                    # Загрузка/обновление файла
                    if is_binary:
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
                        continue

                    try:
                        contents = repo.get_contents(github_path)
                        if contents.type == "file":
                            try:
                                github_content = contents.decoded_content
                            except UnicodeDecodeError:
                                github_content = b''
                                self.log_message(f"[ОШИБКА] {file} has unsupported encoding")
                                logging.error(f"Error: {file} has unsupported encoding.")
                            if github_content != local_content:
                                repo.update_file(contents.path, f"Update {file}", local_content, contents.sha)
                                self.log_message(f"{file} успешно обновлен")
                                logging.info(f"{file} updated successfully.")
                                self.uploaded.set(self.uploaded.get() + 1)  # Increment counter
                            else:
                                self.log_message(f"{file} без изменений")
                                logging.info(f"{file} no changes.")
                        else:
                            logging.error(f"Error: {file} is not a file.")
                            self.log_message(f"[ОШИБКА] {file} is not a file")

                    except Exception as e:
                        if "Not Found" in str(e):
                            repo.create_file(github_path, f"Add {file}", local_content)
                            logging.info(f"{file} uploaded successfully.")
                            self.log_message(f"{file} успешно загружен")
                            self.uploaded.set(self.uploaded.get() + 1)  # Increment counter
                        else:
                            self.log_message(f"[ОШИБКА] {file}: {str(e)}")

        except Exception as e:
            self.log_message(f"[ОШИБКА] {str(e)}")
            logging.error(f"Error during file synchronization: {e}")

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
        logging.info("Starting threaded create structure.")
        self.create_folder_structure()
        self.toggle_progress(False)

    def run_sync(self):
        # Запуск синхронизации
        logging.info("Starting synchronization process.")
        self.toggle_progress(True)
        threading.Thread(target=self.threaded_sync, daemon=True).start()

    def threaded_sync(self):
        # Потоковая синхронизация
        logging.info("Starting threaded synchronization.")
        self.sync_files()
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
        label = tk.Label(
            self.tooltip_window,
            text=self.tooltip_text,
            justify="left",
            background="#ffffff",
            relief="solid",
            borderwidth=1,
            font=("tahoma", "8", "normal"),
        )
        label.pack(ipadx=1)

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


if __name__ == "__main__":
    logging.info("Starting application.")
    root = tk.Tk() # Создание окна
    app = SyncApp(root)
    root.mainloop()