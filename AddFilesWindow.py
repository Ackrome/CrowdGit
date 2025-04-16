import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from github import Github
from collections import defaultdict
from tkinter import simpledialog
import shutil
import traceback

class AddFilesWindow(tk.Toplevel):
    def __init__(self, parent, base_path, token_var, repo_var):
        super().__init__(parent.root)
        self.parent = parent
        self.base_path = base_path
        self.token_var = token_var
        self.repo_var = repo_var
        self.base = self.parent.base.get()

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
        self.force_reload = ttk.Button(self, text="Перезагрузить структуру", command=self.force_reload_structure)
        
        # Use Treeview instead of Listbox
        self.file_list = ttk.Treeview(self, columns=("Number", "File"), show="headings")
        self.file_list.heading("Number", text="Номер")
        self.file_list.heading("File", text="Файл")
        self.file_list.column("Number", width=50, anchor="center")
        self.file_list.column("File", width=300, anchor="w")
        self.file_list.bind("<Button-3>", self.show_context_menu)
        
        # Entry for editing numbers
        self.entry = None
        self.file_list.bind("<Double-1>", self.on_double_click)

        # Dropdowns
        self.course_var = tk.StringVar()
        self.semester_var = tk.StringVar()
        self.subject_var = tk.StringVar()
        self.type_var = tk.StringVar(value="hw")

        ttk.Label(self, text="Курс").grid(row=3, column=1, sticky="w")
        self.course_dd = ttk.Combobox(self, textvariable=self.course_var)
        self.course_dd.grid(row=3, column=0, ipadx=300)

        ttk.Label(self, text="Семестр").grid(row=4, column=1, sticky="w")
        self.semester_dd = ttk.Combobox(self, textvariable=self.semester_var)
        self.semester_dd.grid(row=4, column=0, ipadx=300)

        ttk.Label(self, text="Предмет").grid(row=5, column=1, sticky="w")
        self.subject_dd = ttk.Combobox(self, textvariable=self.subject_var)
        self.subject_dd.grid(row=5, column=0, ipadx=300)

        ttk.Label(self, text="Тип").grid(row=6, column=1, sticky="w")
        self.type_dd = ttk.Combobox(self, textvariable=self.type_var, values=["sem", "hw", "lec", "data", "other"])
        self.type_dd.grid(row=6, column=0, ipadx=300)

        # Convert button
        self.convert_btn = ttk.Button(self, text="Добавить в локальную структуру", command=self.convert_files)

        # Layout
        self.add_btn.grid(row=0, column=0, pady=5, sticky="w")
        self.force_reload.grid(row=0, column=1, pady=5, sticky="e")
        ttk.Label(self, text="Не нашли нужную папку? Попробуйте перезагрузить структуру ->").grid(row=0, column=0, sticky="e")
        self.paths_text.grid(row=1, column=0, sticky="nsew", padx=5)
        self.scroll.grid(row=1, column=1, sticky="ns")
        self.file_list.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.convert_btn.grid(row=7, column=0, pady=10)

        try:
            self.folder_structure = self.parent.load_settings().get("structure")
            if not len(list(self.folder_structure.keys())):
                self.create_folder_structure()
                self.parent.save_settings(self.token_var.get(), self.parent.student_var.get(), self.folder_structure)
        except:
            self.create_folder_structure()
            self.parent.save_settings(self.token_var.get(), self.parent.student_var.get(), self.folder_structure)

        self.scan_local_structure()

        # Добавляем привязки для автоматического обновления
        self.course_var.trace_add('write', self.update_semesters)
        self.semester_var.trace_add('write', self.update_subjects)

    def force_reload_structure(self):
        self.create_folder_structure()
        self.parent.save_settings(self.token_var.get(), self.parent.student_var.get(), self.folder_structure)
        self.parent.log_message("[OK] Структура папок создана")

    def create_folder_structure(self):
        """Create local folder structure from GitHub repo"""
        self.parent.toggle_progress(True)
        if not self.token_var.get() or not self.repo_var.get():
            self.parent.log_message("[ОШИБКА] Token or repository is empty.")
            return

        try:
            g = Github(self.token_var.get())
            repo = g.get_repo(self.repo_var.get())

            def get_dirs(repo_path=""):
                contents = repo.get_contents(repo_path)
                dct = {}
                for item in contents:
                    if item.type == "dir":
                        dct[item.name] = get_dirs(item.path)
                return dct

            self.folder_structure = get_dirs()
            self.parent.log_message("[OK] Структура папок создана")
            self.parent.toggle_progress(False)
        except Exception as e:
            self.parent.log_message(f"[ОШИБКА] {type(e).__name__}: {str(e)}")

    def update_subjects(self, event=None):
        """Update subject dropdown based on selected course"""
        course = self.course_var.get()
        self.subject_dd["values"] = sorted(self.subjects.get(course, []))

    def add_file(self):
        """Add file to processing list"""
        paths = filedialog.askopenfilenames()
        if paths:
            for path in paths:
                self.files.append({"path": path, "num": tk.StringVar(value="")})
                self.file_list.insert("", "end", values=("", os.path.basename(path)))
            self.update_paths_text()

    def show_context_menu(self, event):
        """Show right-click menu for file operations"""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Удалить", command=lambda: self.remove_file(event))
        menu.add_command(label="Местоположение", command=lambda: self.show_file_location(event))
        menu.tk_popup(event.x_root, event.y_root)

    def remove_file(self, event):
        """Remove selected file from list"""
        selection = self.file_list.selection()
        if selection:
            item = selection[0]
            index = self.file_list.index(item)
            del self.files[index]
            self.file_list.delete(item)
            self.update_paths_text()

    def show_file_location(self, event):
        """Open file location in explorer"""
        selection = self.file_list.selection()
        if selection:
            item = selection[0]
            index = self.file_list.index(item)
            path = self.files[index]["path"]
            os.startfile(os.path.dirname(path))

    def get_abbrev(self, course, semester, subject_name):
        """Получаем аббревиатуру из существующих папок"""
        target_dir = os.path.join(self.base_path, course, semester)
        for folder in os.listdir(target_dir):
            if folder.endswith(f"_{subject_name}"):
                return folder.split("_")[0]
        return "unknown"

    def update_semesters(self, *args):
        """Обновляем список семестров при выборе курса"""
        course = self.course_var.get()
        if not self.semesters_dict:
            return
        self.semester_dd['values'] = sorted(self.semesters_dict.get(course, []))
        self.semester_var.set('')
        self.update_subjects()  # Call update_subjects here

    def update_subjects(self, *args):
        """Обновляем список предметов при выборе семестра"""
        course = self.course_var.get()
        semester = self.semester_var.get()
        if not self.subjects_dict:
            return
        self.subject_dd['values'] = sorted(self.subjects_dict.get(course, {}).get(semester, []))
        self.subject_var.set('')

    def scan_local_structure(self):
        """
        Gets the structure from folders in the format base/course_X/semester_Y/subject_abbrev_Name
        using the self.folder_structure dictionary.
        """
        if not os.path.isdir(self.base_path):
            self.parent.log_message(f"[ОШИБКА] Invalid base path: {self.base_path}")
            return

        self.courses = set()
        self.semesters_dict = defaultdict(set)
        self.subjects_dict = defaultdict(lambda: defaultdict(set))

        def traverse_structure(structure, current_path_parts=None):
            if current_path_parts is None:
                current_path_parts = []

            for key, value in structure.items():
                new_path_parts = current_path_parts + [key]

                if key.startswith("course_"):
                    self.courses.add(key)
                    traverse_structure(value, new_path_parts)
                elif key.startswith("semester_"):
                    course = new_path_parts[-2]
                    self.semesters_dict[course].add(key)
                    traverse_structure(value, new_path_parts)
                elif "_" in key:
                    subject_name = key.split("_", 1)[1]
                    course = new_path_parts[-3]
                    semester = new_path_parts[-2]
                    self.subjects_dict[course][semester].add(subject_name)
                else:
                    traverse_structure(value, new_path_parts)

        traverse_structure(self.folder_structure)

        self.course_dd['values'] = sorted(self.courses)

    def update_paths_text(self):
        """Update displayed paths with target structure"""
        self.paths_text.configure(state='normal')
        self.paths_text.delete(1.0, "end")

        course = self.course_var.get()
        semester = self.semester_var.get()
        subject_name = self.subject_var.get()
        work_type = self.type_var.get()

        for item_id in self.file_list.get_children():
            index = self.file_list.index(item_id)
            f = self.files[index]
            orig_path = f["path"]
            num = f["num"].get()
            if num and course and semester and subject_name:
                # Get subject abbreviation from folder structure
                subject_folder = next((d for d in os.listdir(os.path.join(self.base_path, self.base, course, semester))
                                       if d.endswith(f"_{subject_name}")), "")
                if subject_folder:
                    abbrev = subject_folder.split("_")[0]
                else:
                    abbrev = ""

                new_name = f"{abbrev}_{work_type}_{num}_{self.parent.student_var.get()}.{orig_path.split('.')[-1]}"
                target_path = os.path.join(course, semester, subject_folder, work_type, new_name)
                display_text = f"{orig_path} -> {target_path}\n"
            else:
                display_text = f"{orig_path} -> [Недостаточно параметров]\n"

            self.paths_text.insert("end", display_text)

        self.paths_text.configure(state='disabled')

    def convert_files(self):
        """Rename and move files according to structure"""
        success = True
        for item_id in self.file_list.get_children():
            index = self.file_list.index(item_id)
            f = self.files[index]
            try:
                if not all([f["num"].get(), self.course_var.get(), self.semester_var.get(), self.subject_var.get()]):
                    raise ValueError("Missing parameters")

                src = f["path"]
                try:
                    subject_folder = next(d for d in os.listdir(
                        os.path.join(self.base_path, self.base, self.course_var.get(), self.semester_var.get()))
                                          if d.endswith(f"_{self.subject_var.get()}"))
                except StopIteration:
                    raise ValueError(f"No folder found for subject: {self.subject_var.get()}")
                target_dir = os.path.join(
                    self.base_path,  # absolute path to directory
                    self.base,  # uni name
                    self.course_var.get(),  # course name
                    self.semester_var.get(),  # semester name
                    subject_folder,  # subject name from dropdown
                    self.type_var.get()  # hw and others
                )
                os.makedirs(target_dir, exist_ok=True)

                # Generate new filename
                base = os.path.basename(src)
                abbrev = subject_folder.split("_")[0]
                new_name = f"{abbrev}_{self.type_var.get()}_{f['num'].get()}_{self.parent.student_var.get()}.{base.split('.')[-1]}"

                # Copy file
                shutil.copy(src, os.path.join(target_dir, new_name))
                self.parent.log_message(f"[OK] {new_name} добавлен в структуру")
            except Exception as e:
                print(traceback.format_exc())
                success = False
                self.parent.log_message(f"[ОШИБКА] {str(e)}")

        if success:
            messagebox.showinfo("Успех", "Файлы успешно конвертированы")
        else:
            messagebox.showerror("Ошибка", "Ошибка конвертации файлов")
            
    def on_double_click(self, event):
        """Handle double-click on a Treeview item."""
        region = self.file_list.identify_region(event.x, event.y)
        if region == "cell":
            column = self.file_list.identify_column(event.x)
            item = self.file_list.identify_row(event.y)
            if column == "#1":  # "Number" column
                self.edit_number(item)

    def edit_number(self, item):
        """Create an Entry widget to edit the number."""
        if self.entry is not None:
            return

        index = self.file_list.index(item)
        file_data = self.files[index]
        x, y, width, height = self.file_list.bbox(item, "#1")
        
        self.entry = ttk.Entry(self.file_list)
        self.entry.place(x=x, y=y, width=width, height=height, anchor='nw')
        self.entry.insert(0, file_data["num"].get())
        self.entry.focus_set()
        
        def save_and_destroy(event=None):
            file_data["num"].set(self.entry.get())
            # self.entry.destroy()
            # self.entry = None
            self.update_paths_text()

        self.entry.bind("<Return>", save_and_destroy)
        self.entry.bind("<FocusOut>", save_and_destroy)