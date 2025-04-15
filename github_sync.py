import tkinter as tk
from tkinter import ttk, filedialog
import threading
import os
import re
from base64 import b64decode
from github import Github
import json
from AddFilesWindow import AddFilesWindow

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "saved_settings.json")



class SyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub Sync Tool")
        

        #Смотрим, юзер уже работал с приложением или нет
        settings = self.load_settings()
        GITHUB_TOKEN = settings.get("token", "")
        STUDENT_NAME = settings.get("student", "")

        self.token_var = tk.StringVar(value=GITHUB_TOKEN if GITHUB_TOKEN else "")
        self.path_var = tk.StringVar(value=os.getcwd())
        self.student_var = tk.StringVar(value=STUDENT_NAME if STUDENT_NAME else "")
        self.repo_var = tk.StringVar(value="kvdep/CoolSekeleton")
        self.base = tk.StringVar(value="FU")
        self.log_text = tk.Text(height=10, state='disabled')
        self.progress_running = False

        self.folder_dict = {"seminar":'sem', "lecture":'lec', "hw":'hw', "data":'data', "other":'other'}

        self.create_widgets()
        self.grid_layout()
        
        self.add_files_btn = ttk.Button(self.root, text="Добавить файлы", command=self.open_add_files_window)
        self.add_files_btn.grid(row=10, column=0, padx=5, pady=5)
    
    @staticmethod
    def load_settings():
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        return {}
    
    @staticmethod
    def save_settings(token, student,structure = {}):
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"token": token, "student": student, "structure": structure}, f)
    
    def open_add_files_window(self):
        """Open window for adding files to structure"""
        print("open_add_files_window: Starting")
        if hasattr(self, 'add_window') and self.add_window.winfo_exists():
            self.add_window.lift()
            print("open_add_files_window: Window already exists, lifting it")
        else:
            self.add_window = AddFilesWindow(self, self.path_var.get(), self.token_var, self.repo_var)
            print("open_add_files_window: New window created")

   

    def create_widgets(self):
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

        self.create_btn = ttk.Button(self.root, text="Создать структуру", command=self.run_create_structure)
        ttk.Label(self.root, text="Скачает сюда всю структуру папок с Git. Подпапку не создаст.").grid(row=5, column=1, sticky="w")

        self.sync_btn = ttk.Button(self.root, text="Синхронизировать", command=self.run_sync)

        self.log_scroll = ttk.Scrollbar(self.root, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=self.log_scroll.set)

        self.progress = ttk.Progressbar(self.root, mode="indeterminate")

        self.example_label = ttk.Label(
            self.root,
            text="Пример верного path: 'FU\\course_2\\semester_4\\nm_Численные Методы\\hw\\nm_hw_4_Kidysyuk.ipynb'"
        )

        self.save_btn = ttk.Button(self.root, text="Сохранить профиль", command=self.save_profile)


    def grid_layout(self):
        self.token_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=2, sticky="we")
        self.path_entry.grid(row=1, column=1, padx=5, pady=2, sticky="we")
        self.browse_btn.grid(row=1, column=2, padx=5, pady=2)
        self.student_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=2, sticky="we")
        self.repo_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=2, sticky="we")
        self.base_entry.grid(row=4, column=1, columnspan=2, padx=5, pady=2, sticky="we")
        self.create_btn.grid(row=5, column=0, padx=5, pady=5)
        self.sync_btn.grid(row=6, column=0, padx=5, pady=5)
        self.log_text.grid(row=7, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        self.log_scroll.grid(row=7, column=3, sticky="ns")
        self.progress.grid(row=8, column=0, columnspan=3, sticky="we", padx=5, pady=5)
        self.example_label.grid(row=9, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        self.save_btn.grid(row=3, column=3, padx=5, pady=2)

    def save_profile(self):
        token = self.token_var.get()
        student = self.student_var.get()
        if token.strip() and student.strip():
            self.save_settings(token, student)
            self.log_message("[OK] Профиль сохранён")
        else:
            self.log_message("[ОШИБКА] Поля не должны быть пустыми")

    def select_path(self):
        path = filedialog.askdirectory()
        if path:
            self.path_var.set(path)

    def log_message(self, msg):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', msg + '\n')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def toggle_progress(self, start=True):
        if start:
            self.progress.start()
            self.progress_running = True
        else:
            self.progress.stop()
            self.progress_running = False

    def create_folder_structure(self):
        try:
            g = Github(self.token_var.get())
            repo = g.get_repo(self.repo_var.get())

            def create_dirs(repo_path="", local_path=self.path_var.get()):
                contents = repo.get_contents(repo_path)
                for item in contents:
                    if item.type == "dir":
                        dir_path = os.path.join(local_path, item.path)
                        os.makedirs(dir_path, exist_ok=True)
                        create_dirs(item.path, local_path)

            create_dirs()
            self.log_message("[OK] Структура папок создана")
        except Exception as e:
            self.log_message(f"[ОШИБКА] {str(e)}")

    def sync_files(self):
        """Synchronize files with GitHub repo"""
        try:
            # Regex pattern: subj_abbrev_type_num_name.ext (e.g. nm_hw_4_Kidysyuk.ipynb)
            pattern = re.compile(r"^([a-z]+)_(sem|hw|lec)_(\d+)_(.+)\.(\w+)$")
            
            g = Github(self.token_var.get())
            repo = g.get_repo(self.repo_var.get())
            student = self.student_var.get()

            for root, _, files in os.walk(self.path_var.get()):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.path_var.get())
                    github_path = rel_path.replace("\\", "/")

                    # Check filename validity
                    if "data" in rel_path.split(os.sep):
                        if student not in file:
                            continue
                    else:
                        match = pattern.match(file)
                        if not match or student not in file:
                            self.log_message(f"{file} не подходит для синхронизации!")
                            continue

                    # Upload/update file
                    with open(full_path, "rb") as f:
                        content = f.read()
                    
                    try:
                        contents = repo.get_contents(github_path)
                        if contents.decoded_content != content:
                            repo.update_file(contents.path, f"Update {file}", content, contents.sha)
                            self.log_message(f"{file} успешно обновлен")
                        else:
                            self.log_message(f"{file} без изменений")
                    except:
                        repo.create_file(github_path, f"Add {file}", content)
                        self.log_message(f"{file} успешно загружен")
                        
        except Exception as e:
            self.log_message(f"[ОШИБКА] {str(e)}")
            
    def convert_path(self, rel_path):
        parts = rel_path.split(os.sep)
        if "data" in parts:
            i = parts.index("data")
            parts = parts[:i+1] + [self.student_var.get()] + parts[i+1:]
        if parts[0] == "FU":
            parts = parts[1:]
        return parts

    def run_create_structure(self):
        self.toggle_progress(True)
        threading.Thread(target=self.threaded_create_structure, daemon=True).start()

    def threaded_create_structure(self):
        self.create_folder_structure()
        self.toggle_progress(False)

    def run_sync(self):
        self.toggle_progress(True)
        threading.Thread(target=self.threaded_sync, daemon=True).start()

    def threaded_sync(self):
        self.sync_files()
        #save_settings(self.token_var.get(), self.student_var.get())
        self.toggle_progress(False)

if __name__ == "__main__":
    root = tk.Tk()
    app = SyncApp(root)
    root.mainloop()