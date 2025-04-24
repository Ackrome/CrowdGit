import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from github import Github
from collections import defaultdict
from tkinter import simpledialog
import shutil
import traceback
from ToolTip import ToolTip


class AddFilesWindow(tk.Toplevel):
    def __init__(self, parent, base_path, token_var, repo_var, DND_FILES):
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
        self.helper = ttk.Label(self,text = "Сначала заполните информацию о дисциплине, а затем загружайте файлы")
        self.helper.grid(row=0, column=0, sticky="e")
        

        
        # Use Treeview instead of Listbox
        self.file_list = ttk.Treeview(self, columns=("Number", "File", "Size"), show="headings")
        self.file_list.heading("Size", text="Размер")
        self.file_list.column("Size", width=100, anchor="center")

        self.file_list.heading("Number", text="Номер")
        self.file_list.heading("File", text="Файл")
        self.file_list.column("Number", width=50, anchor="center")
        self.file_list.column("File", width=300, anchor="w")
        self.file_list.bind("<Button-3>", self.show_context_menu)
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.drop_inside)
        
        # Entry for editing numbers
        # self.entry = None
        self.file_list.bind("<Double-1>", self.on_double_click)

        
        self.unfolder_dict = {value: key for key, value in self.parent.folder_dict.items()}
        # Dropdowns
        self.course_var = tk.StringVar()
        self.semester_var = tk.StringVar()
        self.subject_var = tk.StringVar()
        self.type_var = tk.StringVar(value="Домашнее задание")

        ttk.Label(self, text="Курс").grid(row=3, column=1, sticky="w")
        self.course_dd = ttk.Combobox(self, textvariable=self.course_var)
        self.course_dd.grid(row=3, column=0, sticky="we")

        ttk.Label(self, text="Семестр").grid(row=4, column=1, sticky="w")
        self.semester_dd = ttk.Combobox(self, textvariable=self.semester_var)
        self.semester_dd.grid(row=4, column=0, sticky="we")

        ttk.Label(self, text="Предмет").grid(row=5, column=1, sticky="w")
        self.subject_dd = ttk.Combobox(self, textvariable=self.subject_var)
        self.subject_dd.grid(row=5, column=0, sticky="we")
        
        
        self.perevodict = {
            "Семинар": "sem",
            "Лекция": "lec",
            "Домашнее задание": "hw",
            "Данные": "data",
            "Другое": "other"
        }

        ttk.Label(self, text="Тип").grid(row=6, column=1, sticky="w")
        self.type_dd = ttk.Combobox(self, textvariable=self.type_var, values=list(self.perevodict.keys()))
        self.type_dd.grid(row=6, column=0, sticky="we")

        # Convert button
        self.convert_btn = ttk.Button(self, text="Добавить в локальную структуру", command=self.convert_files)

        # Layout
        self.add_btn.grid(row=0, column=0, pady=5, sticky="w")
        self.add_btn.grid_remove() # Add this line
        self.paths_text.grid(row=1, column=0, sticky="nsew", padx=5)
        self.paths_text.grid_remove() # Add this line
        self.scroll.grid(row=1, column=1, sticky="ns")
        self.scroll.grid_remove() # Add this line
        self.file_list.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.file_list.grid_remove() # Add this line
        self.convert_btn.grid(row=7, column=0, pady=10)
        self.clear_btn = ttk.Button(self, text="Очистить список", command=self.clear_list)
        self.clear_btn.grid(row=7, column=0, sticky="w")
        
        self.scan_local_structure()

        # Добавляем привязки для автоматического обновления
        self.course_var.trace_add('write', self.update_semesters)
        self.semester_var.trace_add('write', self.update_subjects)
        self.course_var.trace_add('write', self.check_fields) # Add this line
        self.semester_var.trace_add('write', self.check_fields) # Add this line
        self.subject_var.trace_add('write', self.check_fields) # Add this line
        self.type_var.trace_add('write', self.check_fields) # Add this line
        
        for i in range(2): self.grid_columnconfigure(i, weight=1)
        for i in range(8): self.grid_rowconfigure(i, weight=1)
        
        
        # Add tooltips
        ToolTip(self.add_btn, "Нажмите, чтобы выбрать файлы для добавления в структуру.")
        ToolTip(self.helper, "Заполните информацию о курсе, семестре, предмете и типе работы, чтобы начать добавлять файлы.")
        ToolTip(self.file_list, "Список добавленных файлов. Двойной клик на номере для редактирования. Правый клик для удаления или просмотра местоположения.")
        ToolTip(self.course_dd, "Выберите курс из списка.")
        ToolTip(self.semester_dd, "Выберите семестр из списка.")
        ToolTip(self.subject_dd, "Выберите предмет из списка.")
        ToolTip(self.type_dd, "Выберите тип работы (Домашнее задание, Лекция, Семинар и т.д.).")
        ToolTip(self.convert_btn, "Нажмите, чтобы скопировать выбранные файлы в локальную структуру с правильными именами.")
        ToolTip(self.clear_btn, "Очистить список файлов.")
        ToolTip(self.paths_text, "Здесь отображаются пути к файлам, которые будут скопированы, и их новые имена.")

        self.update()  # Force the window to update its layout
        self.geometry("")  # Resize the window to fit its contents
        
        self.check_duplicates()
        
    def clear_list(self):
        """Очистка списка файлов."""
        self.files.clear()
        for item in self.file_list.get_children():
            self.file_list.delete(item)
        self.update_paths_text()
        self.check_duplicates()

        
    def check_fields(self, *args):
        """Check if all fields are filled and show/hide widgets accordingly."""
        if all([self.course_var.get(), self.semester_var.get(), self.subject_var.get(), self.type_var.get()]):
            self.file_list.grid()
            self.add_btn.grid()
            self.paths_text.grid()
            self.scroll.grid()
            self.update()  # Force the window to update its layout
            self.geometry("")  # Resize the window to fit its contents
        else:
            self.file_list.grid_remove()
            self.add_btn.grid_remove()
            self.paths_text.grid_remove()
            self.scroll.grid_remove()
            self.update()  # Force the window to update its layout
            self.geometry("")  # Resize the window to fit its contents
        self.check_duplicates()
        
    

    def add_file(self):
        """Add file to processing list"""
        paths = filedialog.askopenfilenames()
        if paths:
            for path in paths:
                file_size = os.path.getsize(path)
                self.files.append({"path": path, "num": tk.StringVar(value=""), "size": file_size})
                self.file_list.insert("", "end", values=("", os.path.basename(path), self.format_size(file_size)))

            
            self.update_paths_text()
            self.check_duplicates()
            
    def remove_file(self, event):
        """Remove selected file from list"""
        selection = self.file_list.selection()
        if selection:
            item = selection[0]
            index = self.file_list.index(item)
            del self.files[index]
            self.file_list.delete(item)
            self.update_paths_text()
            self.check_duplicates()
            # Re-index the files
            for i, file_data in enumerate(self.files):
                self.file_list.item(self.file_list.get_children()[i], values=(file_data["num"].get(), os.path.basename(file_data["path"]), self.format_size(file_data["size"])))
                
    def show_context_menu(self, event):
        """Show right-click menu for file operations"""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Удалить", command=lambda: self.remove_file(event))
        menu.add_command(label="Местоположение", command=lambda: self.show_file_location(event))
        menu.tk_popup(event.x_root, event.y_root)

    def show_file_location(self, event):
        """Open file location in explorer"""
        
        import platform
        import subprocess
        

        selection = self.file_list.selection()
        if selection:
            item = selection[0]
            index = self.file_list.index(item)
            path = self.files[index]["path"]
            system = platform.system()
            if system == "Windows":
                os.startfile(os.path.dirname(path))
            elif system.lower() in ["darwin","macos"]:  # macOS
                subprocess.run(["open", os.path.dirname(path)])
            elif system == "Linux":
                subprocess.run(["xdg-open", os.path.dirname(path)])
            else:
                os.startfile(os.path.dirname(path))

    def get_abbrev(self, course, semester, subject_name):
        """Получаем аббревиатуру из существующих папок"""
        target_dir = os.path.join(self.base_path, course, semester)
        for folder in os.listdir(target_dir):
            if folder.endswith(f"_{subject_name}"):
                return folder.split("_")[0]
        return "unknown"

    # Обновляем дропдауны
    def update_subjects(self, *args):
        """Обновляем список предметов при выборе семестра"""
        course = self.course_var.get()
        semester = self.semester_var.get()
        if not self.subjects_dict:
            return
        self.subject_dd['values'] = sorted(self.subjects_dict.get(course, {}).get(semester, []))
        self.subject_var.set('')
    
    def update_semesters(self, *args):
        """Обновляем список семестров при выборе курса"""
        course = self.course_var.get()
        if not self.semesters_dict:
            return
        self.semester_dd['values'] = sorted(self.semesters_dict.get(course, []))
        self.semester_var.set('')
        self.update_subjects()  # Call update_subjects here
    

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
        try:
            traverse_structure(self.parent.folder_structure)
        except AttributeError:
                messagebox.showwarning("Подождите", "Структура файлов создается. Подождите...")
                self.parent.create_folder_structure()
                self.parent.save_settings(self.parent.token_var.get(), self.parent.student_var.get(), self.parent.folder_structure)
                traverse_structure(self.parent.folder_structure)
            

        self.course_dd['values'] = sorted(self.courses)

    def update_paths_text(self):
        """Update displayed paths with target structure"""
        self.paths_text.configure(state='normal')
        self.paths_text.delete(1.0, "end")

        course = self.course_var.get()
        semester = self.semester_var.get()
        subject_name = self.subject_var.get()
        work_type = self.perevodict[self.type_var.get()]

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
        self.check_duplicates()

    def convert_files(self):
        """Rename and move files according to structure"""
        success = True
        for f in self.files:
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
                    self.unfolder_dict[self.perevodict[self.type_var.get()]]  # hw and others
                )
                os.makedirs(target_dir, exist_ok=True)

                # Generate new filename
                base = os.path.basename(src)
                abbrev = subject_folder.split("_")[0]
                new_name = f"{abbrev}_{self.perevodict[self.type_var.get()]}_{f['num'].get()}_{self.parent.student_var.get()}.{base.split('.')[-1]}"

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
        index = self.file_list.index(item)
        file_data = self.files[index]
        x, y, width, height = self.file_list.bbox(item, "#1")

        entry = ttk.Entry(self.file_list)  # Local variable
        entry.place(x=x, y=y, width=width, height=height, anchor='nw')
        entry.insert(0, file_data["num"].get())
        entry.focus_set()

        def save_and_destroy(event=None, entry=entry):  # Pass entry as an argument
            file_data["num"].set(entry.get())
            self.file_list.set(item, column="#1", value=entry.get()) # Display the number
            entry.destroy()
            self.update_paths_text()
            self.check_duplicates()

        entry.bind("<Return>", save_and_destroy)
        entry.bind("<FocusOut>", save_and_destroy)
    
    def check_duplicates(self):
        """Check for duplicate file numbers and highlight them."""
        duplicates = []
        numbers = {}
        for item_id in self.file_list.get_children():
            index = self.file_list.index(item_id)
            file_data = self.files[index]
            num = file_data["num"].get()
            if num:
                if num in numbers:
                    duplicates.append(item_id)
                    duplicates.append(numbers[num])
                else:
                    numbers[num] = item_id

        # Reset background color for all items
        for item_id in self.file_list.get_children():
            self.file_list.item(item_id, tags=())

        # Highlight duplicates
        for item_id in set(duplicates):
            self.file_list.item(item_id, tags=("duplicate",))

        # Configure tag for duplicate items
        self.file_list.tag_configure("duplicate", background="red")

        # Enable/disable convert button
        if duplicates:
            self.convert_btn.config(state="disabled")
        else:
            self.convert_btn.config(state="normal")

    def drop_inside(self, event):
        """Handle file drop event."""
        try:
            # Получаем список путей к файлам
            paths = self.tk.splitlist(event.data)
            
            # Обрабатываем каждый путь
            for path in paths:
                path = path.strip()
                if os.path.isfile(path):
                    file_size = os.path.getsize(path)
                    self.files.append({"path": path, "num": tk.StringVar(value=""), "size": file_size})
                    self.file_list.insert("", "end", values=("", os.path.basename(path), self.format_size(file_size)))

                elif os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        for file in files:
                            path = os.path.join(root, file)
                            self.files.append({"path": path, "num": tk.StringVar(value=""), "size": os.path.getsize(path)})
                            self.file_list.insert("", "end", values=("", os.path.basename(path), self.format_size(os.path.getsize(path))))

            self.update_paths_text()
            self.check_duplicates()
        except tk.TclError:
            pass
        except Exception as e:
            print(traceback.format_exc())
    
    def format_size(self, size):
        """Formats the file size into a human-readable string."""
        power = 2**10
        n = 0
        power_labels = {0 : 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
        while size >= power:
            size /= power
            n += 1
        return f"{size:.2f} {power_labels[n]}"
