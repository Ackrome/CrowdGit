import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from github import Github
from collections import defaultdict
from tkinter import simpledialog
from setup import save_settings, load_settings


class AddFilesWindow(tk.Toplevel):
    def __init__(self, parent, base_path, token_var, repo_var):
        super().__init__(parent.root)
        self.parent = parent
        self.base_path = base_path
        self.token_var = token_var
        self.repo_var = repo_var
        
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
        
        ttk.Label(self, text="Курс").grid(row=3, column=1, sticky="w")
        self.course_dd = ttk.Combobox(self, textvariable=self.course_var)
        self.course_dd.grid(row=3, column=0,ipadx=300)
        ttk.Label(self, text="Семестр").grid(row=4, column=1, sticky="w")
        self.semester_dd = ttk.Combobox(self, textvariable=self.semester_var)
        self.semester_dd.grid(row=4, column=0,ipadx=300)
        ttk.Label(self, text="Предмет").grid(row=5, column=1, sticky="w")
        self.subject_dd = ttk.Combobox(self, textvariable=self.subject_var)
        self.subject_dd.grid(row=5, column=0,ipadx=300)
        ttk.Label(self, text="Тип").grid(row=6, column=1, sticky="w")
        self.type_dd = ttk.Combobox(self, textvariable=self.type_var, values=["sem", "hw", "lec", "data", "other"])
        self.type_dd.grid(row=6, column=0,ipadx=300)
        
        # Convert button
        self.convert_btn = ttk.Button(self, text="Добавить в локальную структуру", command=self.convert_files)
        
        # Layout
        self.add_btn.grid(row=0, column=0, pady=5, sticky="w")
        self.paths_text.grid(row=1, column=0, sticky="nsew", padx=5)
        self.scroll.grid(row=1, column=1, sticky="ns")
        self.file_list.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.convert_btn.grid(row=7, column=0, pady=10)
        
        
        try:
            self.folder_structure = load_settings().get("structure")
            if not len(list(self.folder_structure.keys())):
                self.create_folder_structure()
                save_settings(self.token_var.get(), self.parent.student_var.get(), self.folder_structure)
        except:
            self.create_folder_structure()
            save_settings(self.token_var.get(), self.parent.student_var.get(), self.folder_structure)
    
        print("AddFilesWindow: folder_structure created")
        self.scan_local_structure()
        print("AddFilesWindow: local structure scanned")
        print(f"AddFilesWindow: folder_structure = {self.folder_structure}")
        print(f"AddFilesWindow: courses = {self.courses}")
        print(f"AddFilesWindow: semesters_dict = {self.semesters_dict}")
        print(f"AddFilesWindow: subjects_dict = {self.subjects_dict}")

        # Добавляем привязки для автоматического обновления
        self.course_var.trace_add('write', self.update_semesters)
        self.semester_var.trace_add('write', self.update_subjects)
        print("AddFilesWindow: Initialization complete")
    
    def create_folder_structure(self):
        """Create local folder structure from GitHub repo"""
        self.parent.toggle_progress(True)
        print("create_folder_structure: Starting")
        if not self.token_var.get() or not self.repo_var.get():
            self.parent.log_message("[ОШИБКА] Token or repository is empty.")
            print("[ОШИБКА] create_folder_structure: Token or repository is empty.")
            return

        try:
            print("create_folder_structure: Trying to connect to GitHub")
            g = Github(self.token_var.get())
            repo = g.get_repo(self.repo_var.get())

            def get_dirs(repo_path=""):
                contents = repo.get_contents(repo_path)
                print(f"create_folder_structure: Contents of {repo_path}: {contents}")
                dct = {}
                for item in contents:
                    if item.type == "dir":
                        dct[item.name] = get_dirs(item.path)
                return dct

            self.folder_structure = get_dirs()
            self.parent.log_message("[OK] Структура папок создана")
            print("create_folder_structure: Folder structure created successfully")
            self.parent.toggle_progress(False)
        except Exception as e:
            self.parent.log_message(f"[ОШИБКА] {type(e).__name__}: {str(e)}")  # Log exception type and message
            print(f"create_folder_structure: Error: {type(e).__name__}: {str(e)}")

    
        
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

    def update_semesters(self, *args):
        """Обновляем список семестров при выборе курса"""
        print("update_semesters: Starting")
        course = self.course_var.get()
        if not self.semesters_dict:
            print("update_semesters: semesters_dict is empty")
            return
        self.semester_dd['values'] = sorted(self.semesters_dict.get(course, []))
        self.semester_var.set('')
        self.update_subjects() # Call update_subjects here
        print("update_semesters: Finished")

    def update_subjects(self, *args):
        """Обновляем список предметов при выборе семестра"""
        print("update_subjects: Starting")
        course = self.course_var.get()
        semester = self.semester_var.get()
        if not self.subjects_dict:
            print("update_subjects: subjects_dict is empty")
            return
        self.subject_dd['values'] = sorted(self.subjects_dict.get(course, {}).get(semester, []))
        self.subject_var.set('')
        print("update_subjects: Finished")


    def scan_local_structure(self):
        """
        Gets the structure from folders in the format course_X/semester_Y/subject_abbrev_Name
        using the self.folder_structure dictionary.
        """
        print("scan_local_structure: Starting")
        if not os.path.isdir(self.base_path):
            self.parent.log_message(f"[ОШИБКА] Invalid base path: {self.base_path}")
            print(f"scan_local_structure: Invalid base path: {self.base_path}")
            return

        self.courses = set()
        self.semesters_dict = defaultdict(set)
        self.subjects_dict = defaultdict(lambda: defaultdict(set))

        def traverse_structure(structure, current_path=""):
            for key, value in structure.items():
                if current_path == "":
                    if key.startswith("course_"):
                        self.courses.add(key)
                        traverse_structure(value, key)
                elif current_path.startswith("course_") and key.startswith("semester_"):
                    self.semesters_dict[current_path].add(key)
                    traverse_structure(value, os.path.join(current_path, key))
                elif "_" in key:
                    subject_name = key.split("_", 1)[1]
                    course, semester = current_path.split(os.sep)
                    self.subjects_dict[course][semester].add(subject_name)

        traverse_structure(self.folder_structure)

        self.course_dd['values'] = sorted(self.courses)
        print("scan_local_structure: Finished")


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
            if f["num"] and course and semester and subject_name:
                # Get subject abbreviation from folder structure
                subject_folder = next((d for d in os.listdir(os.path.join(self.base_path, course, semester)) 
                                     if d.endswith(f"_{subject_name}")), "")
                if subject_folder:
                    abbrev = subject_folder.split("_")[0]
                else:
                    abbrev = ""
                
                new_name = f"{abbrev}_{work_type}_{f['num']}_{self.parent.student_var.get()}.{orig_path.split('.')[-1]}"
                target_path = os.path.join(course, semester, subject_folder, work_type, new_name)
                display_text = f"{orig_path} -> {target_path}\n"
            else:
                display_text = f"{orig_path} -> [Недостаточно параметров]\n"
            
            self.paths_text.insert("end", display_text)
        
        self.paths_text.configure(state='disabled')

    def convert_files(self):
        """Rename and move files according to structure"""
        success = True
        for f in self.files:
            try:
                if not all([f["num"], self.course_var.get(), self.semester_var.get(), self.subject_var.get()]):
                    raise ValueError("Missing parameters")
                
                src = f["path"]
                try:
                    subject_folder = next(d for d in os.listdir(os.path.join(self.base_path, self.course_var.get(), self.semester_var.get())) 
                                         if d.endswith(f"_{self.subject_var.get()}"))
                except StopIteration:
                    raise ValueError(f"No folder found for subject: {self.subject_var.get()}")
                target_dir = os.path.join(
                    self.base_path,
                    self.course_var.get(),
                    self.semester_var.get(),
                    subject_folder,
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