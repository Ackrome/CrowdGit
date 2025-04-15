import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from github import Github
from collections import defaultdict
from tkinter import simpledialog

class AddFilesWindow(tk.Toplevel):
    def __init__(self, parent, base_path, token_var, repo_var):
        super().__init__(parent.root)  # Исправлено: передаем parent.root вместо parent
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
        self.course_dd = ttk.Combobox(self, textvariable=self.course_var).grid(row=3, column=0,ipadx=300)
        ttk.Label(self, text="Семестр").grid(row=4, column=1, sticky="w")
        self.semester_dd = ttk.Combobox(self, textvariable=self.semester_var).grid(row=4, column=0,ipadx=300)
        ttk.Label(self, text="Предмет").grid(row=5, column=1, sticky="w")
        self.subject_dd = ttk.Combobox(self, textvariable=self.subject_var).grid(row=5, column=0,ipadx=300)
        ttk.Label(self, text="Тип").grid(row=6, column=1, sticky="w")
        self.type_dd = ttk.Combobox(self, textvariable=self.type_var, values=["sem", "hw", "lec", "data", "other"]).grid(row=6, column=0,ipadx=300)
        
        # Convert button
        self.convert_btn = ttk.Button(self, text="Добавить в локальную структуру", command=self.convert_files)
        
        # Layout
        self.add_btn.grid(row=0, column=0, pady=5, sticky="w")
        self.paths_text.grid(row=1, column=0, sticky="nsew", padx=5)
        self.scroll.grid(row=1, column=1, sticky="ns")
        self.file_list.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        '''self.course_dd.grid(row=3, column=0, sticky="we", padx=5)
        self.semester_dd.grid(row=4, column=0, sticky="we", padx=5)
        self.subject_dd.grid(row=5, column=0, sticky="we", padx=5)
        self.type_dd.grid(row=6, column=0, sticky="we", padx=5)'''
        self.convert_btn.grid(row=7, column=0, pady=10)
        
        self.create_folder_structure()
        
        
        # Init structure
        self.scan_local_structure()

        # Добавляем привязки для автоматического обновления
        self.course_var.trace_add('write', self.update_semesters)
        self.semester_var.trace_add('write', self.update_subjects)    

    
    def create_folder_structure(self):
        """Create local folder structure from GitHub repo"""
        try:
            g = Github(self.token_var.get())
            repo = g.get_repo(self.repo_var.get())
            
            def create_dirs(repo_path="", local_path=self.path_var.get()):
                contents = repo.get_contents(repo_path)
                dct = {}
                for item in contents:
                    if item.type == "dir":
                        dct[item.name] = create_dirs(item.path, local_path)
                        #dir_path = os.path.join(local_path, item.path)
                        #os.makedirs(dir_path, exist_ok=True)
                return dct
                        
            
            dcts = create_dirs()
            print(dcts)
            self.parent.log_message("[OK] Структура папок создана")
        except Exception as e:
            self.parent.log_message(f"[ОШИБКА] {str(e)}")
    
    def scan_local_structure(self):
        """Получаем структуру из папок формата course_X/semester_Y/subject_abbrev_Name"""
        self.courses = set()
        self.semesters_dict = defaultdict(set)
        self.subjects_dict = defaultdict(lambda: defaultdict(set))

        # Сканируем только первый уровень (курсы)
        for course in os.listdir(self.base_path):
            print(course)
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