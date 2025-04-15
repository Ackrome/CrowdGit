import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import re
from github import Github
from collections import defaultdict
from tkinter import simpledialog

class AddFilesWindow(tk.Toplevel):
    def __init__(self, parent, base_path):
        super().__init__(parent.root)  # Исправлено: передаем parent.root вместо parent
        self.parent = parent
        self.base_path = base_path
        self.files = []
        self.title("Добавить файлы в структуру")
        self.geometry("800x600")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # File list with paths
        self.paths_text = tk.Text(self, height=10, state='disabled')
        self.scroll = ttk.Scrollbar(self, command=self.paths_text.yview)
        self.paths_text.configure(yscrollcommand=self.scroll.set)
        
        # File management
        self.add_btn = ttk.Button(self, text="Добавить файл", command=self.add_file)
        self.file_list = tk.Listbox(self)
        self.file_list.bind("<Button-3>", self.show_context_menu)
        
        # Dropdowns
        self.course_var = tk.StringVar()
        self.semester_var = tk.StringVar()
        self.subject_var = tk.StringVar()
        self.type_var = tk.StringVar(value="hw")
        
        ttk.Label(self, text="Курс:").grid(row=3, column=0, sticky="w")
        self.course_dd = ttk.Combobox(self, textvariable=self.course_var)
        ttk.Label(self, text="Семестр:").grid(row=4, column=0, sticky="w")
        self.semester_dd = ttk.Combobox(self, textvariable=self.semester_var)
        ttk.Label(self, text="Предмет:").grid(row=5, column=0, sticky="w")
        self.subject_dd = ttk.Combobox(self, textvariable=self.subject_var)
        ttk.Label(self, text="Тип:").grid(row=6, column=0, sticky="w")
        self.type_dd = ttk.Combobox(self, textvariable=self.type_var, values=["sem", "hw", "lec", "data", "other"])
        
        # Convert button
        self.convert_btn = ttk.Button(self, text="Добавить в локальную структуру", command=self.convert_files)
        
        # Layout
        self.add_btn.grid(row=0, column=0, pady=5, sticky="w")
        self.paths_text.grid(row=1, column=0, sticky="nsew", padx=5)
        self.scroll.grid(row=1, column=1, sticky="ns")
        self.file_list.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.course_dd.grid(row=3, column=0, sticky="we", padx=5)
        self.semester_dd.grid(row=4, column=0, sticky="we", padx=5)
        self.subject_dd.grid(row=5, column=0, sticky="we", padx=5)
        self.type_dd.grid(row=6, column=0, sticky="we", padx=5)
        self.convert_btn.grid(row=7, column=0, pady=10)
        
        # Init structure
        self.scan_local_structure()

        # Добавляем привязки для автоматического обновления
        self.course_var.trace_add('write', self.update_semesters)
        self.semester_var.trace_add('write', self.update_subjects)    

    def scan_local_structure(self):
        """Получаем структуру из папок формата course_X/semester_Y/subject_abbrev_Name"""
        self.courses = set()
        self.semesters_dict = defaultdict(set)
        self.subjects_dict = defaultdict(lambda: defaultdict(set))

        # Сканируем только первый уровень (курсы)
        for course in os.listdir(self.base_path):
            if course.startswith("course_"):
                self.courses.add(course)
                course_path = os.path.join(self.base_path, course)
                
                # Сканируем семестры внутри курса
                for semester in os.listdir(course_path):
                    if semester.startswith("semester_"):
                        self.semesters_dict[course].add(semester)
                        semester_path = os.path.join(course_path, semester)
                        
                        # Сканируем предметы внутри семестра
                        for subject in os.listdir(semester_path):
                            if "_" in subject:
                                subject_name = subject.split("_", 1)[1]
                                self.subjects_dict[course][semester].add(subject_name)
        
        self.course_dd['values'] = sorted(self.courses)

    def update_semesters(self, *args):
        """Обновляем список семестров при выборе курса"""
        course = self.course_var.get()
        self.semester_dd['values'] = sorted(self.semesters_dict.get(course, []))
        self.semester_var.set('')
        self.update_subjects()

    def update_subjects(self, *args):
        """Обновляем список предметов при выборе семестра"""
        course = self.course_var.get()
        semester = self.semester_var.get()
        self.subject_dd['values'] = sorted(self.subjects_dict.get(course, {}).get(semester, []))
        self.subject_var.set('')
        
    def scan_local_structure(self):
        """Scan local folder structure to populate dropdowns"""
        self.courses = set()
        self.semesters = set()
        self.subjects = defaultdict(set)
        
        for root, dirs, _ in os.walk(self.base_path):
            if "course_" in root:
                course = os.path.basename(root)
                self.courses.add(course)
                for d in dirs:
                    if "semester_" in d:
                        self.semesters.add(d)
                    elif "_" in d:
                        subject = d.split("_", 1)[1]
                        self.subjects[course].add(subject)
        
        self.course_dd["values"] = sorted(self.courses)
        self.semester_dd["values"] = sorted(self.semesters)
        
    def update_subjects(self, event=None):
        """Update subject dropdown based on selected course"""
        course = self.course_var.get()
        self.subject_dd["values"] = sorted(self.subjects.get(course, []))
        
    def add_file(self):
        """Add file to processing list"""
        path = filedialog.askopenfilename()
        if path:
            self.files.append({"path": path, "num": None})
            self.file_list.insert("end", os.path.basename(path))
            self.update_paths_text()
    
    def show_context_menu(self, event):
        """Show right-click menu for file operations"""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Удалить", command=lambda: self.remove_file(event))
        menu.add_command(label="Местоположение", command=lambda: self.show_file_location(event))
        menu.add_command(label="Номер", command=lambda: self.set_file_number(event))
        menu.tk_popup(event.x_root, event.y_root)
    
    def remove_file(self, event):
        """Remove selected file from list"""
        selection = self.file_list.curselection()
        if selection:
            index = selection[0]
            del self.files[index]
            self.file_list.delete(index)
            self.update_paths_text()
    
    def show_file_location(self, event):
        """Open file location in explorer"""
        selection = self.file_list.curselection()
        if selection:
            path = self.files[selection[0]]["path"]
            os.startfile(os.path.dirname(path))
    
    def set_file_number(self, event):
        """Set work number for selected file"""
        selection = self.file_list.curselection()
        if selection:
            index = selection[0]
            num = simpledialog.askinteger("Номер работы", "Введите номер:")
            if num:
                self.files[index]["num"] = num
                self.update_paths_text()
    
    def get_abbrev(self, course, semester, subject_name):
        """Получаем аббревиатуру из существующих папок"""
        target_dir = os.path.join(self.base_path, course, semester)
        for folder in os.listdir(target_dir):
            if folder.endswith(f"_{subject_name}"):
                return folder.split("_")[0]
        return "unknown"
    
    def update_paths_text(self):
        """Update displayed paths with target structure"""
        self.paths_text.configure(state='normal')
        self.paths_text.delete(1.0, "end")
        
        course = self.course_var.get()
        semester = self.semester_var.get()
        subject_name = self.subject_var.get()
        work_type = self.type_var.get()
        
        for f in self.files:
            orig_path = f["path"]
            if f["num"] and course and semester and subject:
                # Get subject abbreviation from folder structure
                subject_folder = next((d for d in os.listdir(os.path.join(self.base_path, course, semester)) 
                                     if d.endswith(f"_{subject}")), "")
                abbrev = subject_folder.split("_")[0] if subject_folder else ""
                
                new_name = f"{abbrev}_{work_type}_{f['num']}_{self.parent.student_var.get()}.{orig_path.split('.')[-1]}"
                target_path = os.path.join(course, semester, subject_folder, work_type, new_name)
                display_text = f"{orig_path} -> {target_path}\n"
            else:
                display_text = f"{orig_path} -> [Недостаточно параметров]\n"
            
            self.paths_text.insert("end", display_text)
        
        self.paths_text.configure(state='disabled')

        
        for f in self.files:
            if all([f["num"], course, semester, subject_name]):
                # Формируем путь с учетом структуры
                target_path = os.path.join(
                    course,
                    semester,
                    f"{self.get_abbrev(course, semester, subject_name)}_{subject_name}",
                    self.type_var.get(),
                    f"{abbrev}_{self.type_var.get()}_{f['num']}_{self.parent.student_var.get()}.{ext}"
                )
                
    
    def convert_files(self):
        """Rename and move files according to structure"""
        success = True
        for f in self.files:
            try:
                if not all([f["num"], self.course_var.get(), self.semester_var.get(), self.subject_var.get()]):
                    raise ValueError("Missing parameters")
                
                src = f["path"]
                target_dir = os.path.join(
                    self.base_path,
                    self.course_var.get(),
                    self.semester_var.get(),
                    next(d for d in os.listdir(os.path.join(self.base_path, self.course_var.get(), self.semester_var.get())) 
                         if d.endswith(f"_{self.subject_var.get()}")),
                    self.type_var.get()
                )
                os.makedirs(target_dir, exist_ok=True)
                
                # Generate new filename
                base = os.path.basename(src)
                abbrev = os.path.basename(target_dir).split("_")[0]
                new_name = f"{abbrev}_{self.type_var.get()}_{f['num']}_{self.parent.student_var.get()}.{base.split('.')[-1]}"
                
                # Copy file
                os.replace(src, os.path.join(target_dir, new_name))
                self.parent.log_message(f"[OK] {new_name} добавлен в структуру")
            except Exception as e:
                success = False
                self.parent.log_message(f"[ОШИБКА] {str(e)}")
        
        if success:
            messagebox.showinfo("Успех", "Файлы успешно конвертированы")
        else:
            messagebox.showerror("Ошибка", "Ошибка конвертации файлов")


class SyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub Sync Tool")
        
        # Variables
        self.token_var = tk.StringVar()
        self.path_var = tk.StringVar(value=os.getcwd())
        self.student_var = tk.StringVar()
        self.repo_var = tk.StringVar(value="kvdep/CoolSekeleton")
        self.log_text = tk.Text(height=10, state='disabled')
        self.progress_running = False

        # Widgets
        self.create_widgets()
        self.grid_layout()

        self.add_files_btn = ttk.Button(self.root, text="Добавить файлы", command=self.open_add_files_window)
        self.add_files_btn.grid(row=9, column=0, padx=5, pady=5)

    def open_add_files_window(self):
        """Open window for adding files to structure"""
        if hasattr(self, 'add_window') and self.add_window.winfo_exists():
            self.add_window.lift()
        else:
            self.add_window = AddFilesWindow(self, self.path_var.get())    

    def create_widgets(self):
        # Token input
        ttk.Label(self.root, text="GitHub Token:").grid(row=0, column=0, sticky="w")
        self.token_entry = ttk.Entry(self.root, textvariable=self.token_var, width=40)
        
        # Path selector
        ttk.Label(self.root, text="Локальный путь:").grid(row=1, column=0, sticky="w")
        self.path_entry = ttk.Entry(self.root, textvariable=self.path_var, width=35)
        self.browse_btn = ttk.Button(self.root, text="Обзор", command=self.select_path)
        
        # Student name
        ttk.Label(self.root, text="Фамилия студента:").grid(row=2, column=0, sticky="w")
        self.student_entry = ttk.Entry(self.root, textvariable=self.student_var, width=40)
        
        # Repo URL
        ttk.Label(self.root, text="Репозиторий:").grid(row=3, column=0, sticky="w")
        self.repo_entry = ttk.Entry(self.root, textvariable=self.repo_var, width=40)
        
        # Buttons
        self.create_btn = ttk.Button(self.root, text="Создать структуру", command=self.run_create_structure)
        ttk.Label(self.root, text="Скачает сюда всю структуру папок с Git. Подпапку не создаст.").grid(row=4, column=1, sticky="w")
        
        self.sync_btn = ttk.Button(self.root, text="Синхронизировать", command=self.run_sync)
        
        # Log area
        self.log_scroll = ttk.Scrollbar(self.root, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=self.log_scroll.set)
        
        # Progress indicator
        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        
        # Example label
        self.example_label = ttk.Label(
            self.root, 
            text="Пример верного path: 'FU\\course_2\\semester_4\\nm_Численные Методы\\hw\\nm_hw_4_Kidysyuk.ipynb'"
        )

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
        """Create local folder structure from GitHub repo"""
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
        self.toggle_progress(False)

if __name__ == "__main__":
    root = tk.Tk()
    app = SyncApp(root)
    root.mainloop()