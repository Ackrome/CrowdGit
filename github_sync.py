import tkinter as tk
from tkinter import ttk, filedialog
import threading
import os
import re
from base64 import b64decode
from github import Github
import json

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "saved_settings.json")

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_settings(token, student):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"token": token, "student": student}, f)

class SyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub Sync Tool")

        #Смотрим, юзер уже работал с приложением или нет
        settings = load_settings()
        GITHUB_TOKEN = settings.get("token", "")
        STUDENT_NAME = settings.get("student", "")

        self.token_var = tk.StringVar(value=GITHUB_TOKEN if GITHUB_TOKEN else "")
        self.path_var = tk.StringVar(value=os.getcwd())
        self.student_var = tk.StringVar(value=STUDENT_NAME if STUDENT_NAME else "")
        self.repo_var = tk.StringVar(value="kvdep/CoolSekeleton")
        self.log_text = tk.Text(height=10, state='disabled')
        self.progress_running = False

        self.folder_dict = {"seminar":'sem', "lecture":'lec', "hw":'hw', "data":'data', "other":'other'}

        self.create_widgets()
        self.grid_layout()

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

        self.create_btn = ttk.Button(self.root, text="Создать структуру", command=self.run_create_structure)
        ttk.Label(self.root, text="Скачает сюда всю структуру папок с Git. Подпапку не создаст.").grid(row=4, column=1, sticky="w")

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
        self.create_btn.grid(row=4, column=0, padx=5, pady=5)
        self.sync_btn.grid(row=5, column=0, padx=5, pady=5)
        self.log_text.grid(row=6, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        self.log_scroll.grid(row=6, column=3, sticky="ns")
        self.progress.grid(row=7, column=0, columnspan=3, sticky="we", padx=5, pady=5)
        self.example_label.grid(row=8, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        self.save_btn.grid(row=3, column=3, padx=5, pady=2)

    def save_profile(self):
        token = self.token_var.get()
        student = self.student_var.get()
        if token.strip() and student.strip():
            save_settings(token, student)
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
        try:
            #pattern = re.compile(r"^(?P<subj>[a-z_]+)_(?P<type>sem|hw|lec)_(?P<num>\\d{1,3})_(?P<name>.+)\\.(?P<ext>\\w+)$")
            pattern  = re.compile(r"^(?P<subj>[a-z_]+)_(?P<type>sem|hw|lec)_(?P<num>\d{1,3})_(?P<name>.+)\.(?P<ext>\w+)$")

            g = Github(self.token_var.get())
            repo = g.get_repo(self.repo_var.get())
            student = self.student_var.get()
            base_path = self.path_var.get()

            for root, _, files in os.walk(base_path):
                if any(part in root for part in ["seminar", "lecture", "hw", "data", "other"]):
                    rel_root = os.path.relpath(root, base_path)
                    parts = rel_root.split(os.sep)

                    subj_abbr = parts[3].split("_")[0] if len(parts) >= 4 and "_" in parts[3] else ""
                    print(subj_abbr)
                    folder_type = parts[4] if len(parts) >= 5 else ""
                    folder_type = self.folder_dict[folder_type]
                    
                    for file in files:
                        print(file,student,subj_abbr,folder_type)
                        valid = (
                            folder_type == "data"
                            or (pattern.match(file) and student in file and pattern.match(file).group("subj") == subj_abbr)
                        )
                        if not valid:
                            self.log_message(f"Skipped (bad name): {file}")
                            continue

                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, base_path)
                        repo_path = os.path.join("FU", *self.convert_path(rel_path)).replace("\\", "/")

                        with open(full_path, "rb") as f:
                            content = f.read()

                        try:
                            contents = repo.get_contents(repo_path)
                            decoded = b""
                            if contents.encoding == "base64":
                                decoded = b64decode(contents.content)
                            if decoded != content:
                                repo.update_file(contents.path, f"Update {file}", content, contents.sha)
                                self.log_message(f"Updated: {repo_path}")
                            else:
                                self.log_message(f"Unchanged: {repo_path}")
                        except Exception:
                            repo.create_file(repo_path, f"Add {file}", content)
                            self.log_message(f"Created: {repo_path}")
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