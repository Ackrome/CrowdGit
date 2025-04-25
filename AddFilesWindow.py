import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from github import Github # Keep for potential future use, though not used in current file logic
from collections import defaultdict
from tkinter import simpledialog
import shutil
import traceback
from ToolTip import ToolTip
from concurrent.futures import ThreadPoolExecutor # Import ThreadPoolExecutor
import asyncio # Import asyncio for running async tasks in executor (if needed, though not strictly required for sync file ops)
import logging # Import logging

class AddFilesWindow(tk.Toplevel):
    def __init__(self, parent, base_path, token_var, repo_var, DND_FILES):
        super().__init__(parent.root)
        self.parent = parent
        self.base_path = base_path
        self.token_var = token_var # Keep for potential future use
        self.repo_var = repo_var # Keep for potential future use
        self.base = self.parent.base.get()

        self.files = []
        self.title("Добавить файлы в структуру")
        self.geometry("800x600")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Initialize ThreadPoolExecutor for file operations
        self.executor = ThreadPoolExecutor(max_workers=os.cpu_count() or 1) # Use number of CPU cores for I/O-bound tasks

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

        # Start scanning local structure in a thread
        self.executor.submit(self.scan_local_structure)


        # Добавляем привязки для автоматического обновления
        self.course_var.trace_add('write', self.update_semesters)
        self.semester_var.trace_add('write', self.update_subjects)
        self.course_var.trace_add('write', self.check_fields) # Add this line
        self.semester_var.trace_add('write', self.check_fields) # Add this line
        self.subject_var.trace_add('write', self.check_fields) # Add this line
        self.type_var.trace_add('write', self.check_fields) # Add this line
        # Update paths text when relevant fields change - submit to executor
        self.course_var.trace_add('write', lambda *args: self.executor.submit(self.update_paths_text))
        self.semester_var.trace_add('write', lambda *args: self.executor.submit(self.update_paths_text))
        self.subject_var.trace_add('write', lambda *args: self.executor.submit(self.update_paths_text))
        self.type_var.trace_add('write', lambda *args: self.executor.submit(self.update_paths_text))


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

        self.check_duplicates() # Initial check

    def clear_list(self):
        """Очистка списка файлов."""
        self.files.clear()
        # Clear Treeview in the main thread
        self.master.after(0, lambda: [self.file_list.delete(item) for item in self.file_list.get_children()])
        self.executor.submit(self.update_paths_text) # Update paths text in executor
        self.master.after(0, self.check_duplicates)


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
            # Process file paths and get sizes in the executor
            self.executor.submit(self._process_added_files, paths)

    def _process_added_files(self, paths):
        """Process added file paths and update GUI in the main thread."""
        new_files_data = []
        for path in paths:
            try:
                file_size = os.path.getsize(path)
                new_files_data.append({"path": path, "num": tk.StringVar(value=""), "size": file_size})
            except Exception as e:
                logging.error(f"Error getting file size for {path}: {e}")
                self.parent.log_message(f"[ОШИБКА] Не удалось получить размер файла {os.path.basename(path)}: {e}")

        # Update self.files and Treeview in the main thread
        self.master.after(0, self._update_file_list_gui, new_files_data)


    def _update_file_list_gui(self, new_files_data):
        """Update the self.files list and Treeview in the main thread."""
        for file_data in new_files_data:
             self.files.append(file_data)
             self.file_list.insert("", "end", values=("", os.path.basename(file_data["path"]), self.format_size(file_data["size"])))

        self.executor.submit(self.update_paths_text) # Update paths text in executor
        self.check_duplicates() # Check for duplicates in the main thread


    def remove_file(self, event):
        """Remove selected file from list"""
        selection = self.file_list.selection()
        if selection:
            item = selection[0]
            index = self.file_list.index(item)
            del self.files[index]
            self.file_list.delete(item)
            self.executor.submit(self.update_paths_text) # Update paths text in executor
            self.check_duplicates()
            # Re-index the files - Update Treeview values in the main thread
            self.master.after(0, self._reindex_file_list_gui)

    def _reindex_file_list_gui(self):
        """Re-index the file list in the Treeview in the main thread."""
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
            try:
                if system == "Windows":
                    os.startfile(os.path.dirname(path))
                elif system.lower() in ["darwin","macos"]:  # macOS
                    subprocess.run(["open", os.path.dirname(path)])
                elif system == "Linux":
                    subprocess.run(["xdg-open", os.path.dirname(path)])
                else:
                    os.startfile(os.path.dirname(path)) # Fallback
            except Exception as e:
                logging.error(f"Error opening file location for {path}: {e}")
                self.parent.log_message(f"[ОШИБКА] Не удалось открыть местоположение файла {os.path.basename(path)}: {e}")


    def get_abbrev(self, course, semester, subject_name):
        """Получаем аббревиатуру из существующих папок"""
        target_dir = os.path.join(self.base_path, self.base, course, semester)
        try:
            # Offload os.listdir to executor
            folders = self.executor.submit(os.listdir, target_dir).result()
            for folder in folders:
                if folder.endswith(f"_{subject_name}"):
                    return folder.split("_")[0]
        except FileNotFoundError:
            logging.warning(f"Directory not found for abbreviation lookup: {target_dir}")
            return "unknown"
        except Exception as e:
            logging.error(f"Error getting abbreviation for {course}/{semester}/{subject_name}: {e}")
            return "unknown"
        return "unknown"


    # Обновляем дропдауны - these are quick GUI updates, keep in main thread
    def update_subjects(self, *args):
        """Обновляем список предметов при выборе семестра"""
        course = self.course_var.get()
        semester = self.semester_var.get()
        if not hasattr(self, 'subjects_dict') or not self.subjects_dict: # Added check for self.subjects_dict existence
            self.subject_dd['values'] = []
            return
        self.subject_dd['values'] = sorted(self.subjects_dict.get(course, {}).get(semester, []))
        self.subject_var.set('')

    def update_semesters(self, *args):
        """Обновляем список семестров при выборе курса"""
        course = self.course_var.get()
        if not hasattr(self, 'semesters_dict') or not self.semesters_dict: # Added check for self.semesters_dict existence
            self.semester_dd['values'] = []
            return
        self.semester_dd['values'] = sorted(self.semesters_dict.get(course, []))
        self.semester_var.set('')
        self.update_subjects()  # Call update_subjects here


    def scan_local_structure(self):
        """
        Gets the structure from folders in the format base/course_X/semester_Y/subject_abbrev_Name
        using the self.folder_structure dictionary. Runs in executor.
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
                # If folder_structure is not ready, try creating it
                self.master.after(0, messagebox.showwarning, "Подождите", "Структура файлов создается. Подождите...")
                # These calls might still be synchronous and block the executor,
                # but they are necessary to get the structure.
                self.parent.create_folder_structure()
                self.parent.save_settings()
                # After creating, traverse the structure again
                if hasattr(self.parent, 'folder_structure') and self.parent.folder_structure:
                    traverse_structure(self.parent.folder_structure)
                else:
                     logging.error("Failed to create or find folder_structure after attempt.")
                     self.parent.log_message("[ОШИБКА] Не удалось создать или найти структуру папок.")
                     # Optionally, disable conversion or show an error state in GUI
                     self.master.after(0, lambda: self.convert_btn.config(state="disabled"))


        # Update GUI elements in the main thread after scanning
        self.master.after(0, lambda: self._update_structure_dropdowns_gui(sorted(list(self.courses)))) # Ensure courses is a list for sorted


    def _update_structure_dropdowns_gui(self, sorted_courses):
        """Update course dropdown in the main thread."""
        self.course_dd['values'] = sorted_courses


    def update_paths_text(self):
        """Update displayed paths with target structure. Runs in executor."""
        display_texts = []

        course = self.course_var.get()
        semester = self.semester_var.get()
        subject_name = self.subject_var.get()
        work_type = self.perevodict.get(self.type_var.get(), "other") # Use .get with default

        for f in self.files:
            orig_path = f["path"]
            num = f["num"].get()
            if num and course and semester and subject_name:
                # Get subject abbreviation from folder structure - Offload os.listdir
                try:
                    target_subject_dir = os.path.join(self.base_path, self.base, course, semester)
                    # Submit os.listdir to the executor and get the result
                    folders = self.executor.submit(os.listdir, target_subject_dir).result()

                    # Find the subject folder
                    subject_folder = next((d for d in folders if d.endswith(f"_{subject_name}")), None) # Use None as default if not found

                    if subject_folder:
                        abbrev = subject_folder.split("_")[0]
                    else:
                         abbrev = "unknown_abbrev" # Handle case where folder isn't found
                         subject_folder = f"unknown_abbrev_{subject_name}" # Use a placeholder folder name
                         logging.warning(f"Subject folder not found for {subject_name} in {target_subject_dir}. Using placeholder.")

                except (FileNotFoundError, StopIteration):
                    abbrev = "unknown_abbrev"
                    subject_folder = f"unknown_abbrev_{subject_name}" # Create a placeholder folder name
                    logging.warning(f"Subject folder not found for {subject_name} in {os.path.join(self.base_path, self.base, course, semester)}. Using placeholder.")
                except Exception as e:
                     abbrev = "error_abbrev"
                     subject_folder = f"error_abbrev_{subject_name}"
                     logging.error(f"Error finding subject folder for {subject_name}: {e}")


                # Ensure work_type folder exists in unfolder_dict
                work_type_folder_name = self.unfolder_dict.get(work_type, "other")

                new_name = f"{abbrev}_{work_type}_{num}_{self.parent.student_var.get()}.{orig_path.split('.')[-1]}"
                target_path = os.path.join(course, semester, subject_folder, work_type_folder_name, new_name)
                display_texts.append(f"{orig_path} -> {target_path}\n")
            else:
                display_texts.append(f"{orig_path} -> [Недостаточно параметров]\n")

        # Update paths_text in the main thread
        self.master.after(0, lambda: self._update_paths_text_gui("".join(display_texts)))


    def _update_paths_text_gui(self, text_content):
        """Update the paths_text widget in the main thread."""
        self.paths_text.configure(state='normal')
        self.paths_text.delete(1.0, "end")
        self.paths_text.insert("end", text_content)
        self.paths_text.configure(state='disabled')
        self.check_duplicates() # Check for duplicates after updating paths


    def convert_files(self):
        """Rename and move files according to structure. Runs in executor."""
        # Disable button in main thread
        self.master.after(0, lambda: self.convert_btn.config(state="disabled"))

        self.executor.submit(self._perform_file_conversion)


    def _perform_file_conversion(self):
        """Perform the actual file conversion (copying) in the executor."""
        success_count = 0
        fail_count = 0
        results = [] # To store results for feedback

        course = self.course_var.get()
        semester = self.semester_var.get()
        subject_name = self.subject_var.get()
        work_type = self.perevodict.get(self.type_var.get(), "other")

        for f in self.files:
            try:
                if not all([f["num"].get(), course, semester, subject_name]):
                    raise ValueError("Missing parameters")

                src = f["path"]
                try:
                    target_subject_dir = os.path.join(self.base_path, self.base, course, semester)
                     # Submit os.listdir to the executor and get the result
                    folders = self.executor.submit(os.listdir, target_subject_dir).result()

                    # Find the subject folder
                    subject_folder = next((d for d in folders if d.endswith(f"_{subject_name}")), None) # Use None as default if not found

                    if not subject_folder:
                         raise ValueError(f"No folder found for subject: {subject_name} in {target_subject_dir}")

                except (FileNotFoundError, StopIteration):
                     raise ValueError(f"No folder found for subject: {subject_name} in {os.path.join(self.base_path, self.base, course, semester)}")


                target_dir = os.path.join(
                    self.base_path,  # absolute path to directory
                    self.base,  # uni name
                    course,  # course name
                    semester,  # semester name
                    subject_folder,  # subject name from dropdown
                    self.unfolder_dict.get(work_type, "other") # hw and others
                )
                # Offload os.makedirs to executor
                # Use result() to wait for directory creation before copying
                self.executor.submit(os.makedirs, target_dir, exist_ok=True).result()

                # Generate new filename
                base = os.path.basename(src)
                abbrev = subject_folder.split("_")[0]
                new_name = f"{abbrev}_{work_type}_{f['num'].get()}_{self.parent.student_var.get()}.{base.split('.')[-1]}"
                target_path = os.path.join(target_dir, new_name)

                # Check for existing file and overwrite preference - Offload os.path.exists
                # Use result() to wait for the check
                file_exists = self.executor.submit(os.path.exists, target_path).result()

                if file_exists and not self.overwrite_existing_var.get():
                    logging.info(f"File already exists and overwrite disabled: {target_path}. Skipping.")
                    results.append(f"[ИНФО] Файл уже существует, пропущен: {new_name}")
                    continue # Skip copying this file

                # Copy file - Offload shutil.copy
                # Use result() to wait for the copy operation
                self.executor.submit(shutil.copy, src, target_path).result()
                results.append(f"[OK] {new_name} добавлен в структуру")
                success_count += 1

            except Exception as e:
                logging.error(f"Error converting file {os.path.basename(f['path'])}: {e}")
                results.append(f"[ОШИБКА] Не удалось добавить файл {os.path.basename(f['path'])}: {e}")
                fail_count += 1

        # Show results in the main thread
        self.master.after(0, lambda: self._show_conversion_results_gui(success_count, fail_count, results))


    def _show_conversion_results_gui(self, success_count, fail_count, results):
        """Show conversion results in a messagebox and update log in the main thread."""
        for result_msg in results:
            self.parent.log_message(result_msg)

        if fail_count == 0:
            messagebox.showinfo("Успех", f"Файлы успешно добавлены: {success_count}")
        else:
            messagebox.showerror("Ошибка", f"Добавление файлов завершено с ошибками. Успешно: {success_count}, Ошибок: {fail_count}")

        # Re-enable button in main thread
        self.master.after(0, lambda: self.convert_btn.config(state="normal"))


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
            self.executor.submit(self.update_paths_text) # Update paths text in executor
            self.check_duplicates()

        entry.bind("<Return>", save_and_destroy)
        entry.bind("<FocusOut>", save_and_destroy)

    def check_duplicates(self):
        """Check for duplicate file numbers and highlight them. Runs in main thread."""
        duplicates = set()
        numbers = {}
        for item_id in self.file_list.get_children():
            index = self.file_list.index(item_id)
            file_data = self.files[index]
            num = file_data["num"].get().strip() # Strip whitespace
            if num:
                if num in numbers:
                    duplicates.add(item_id)
                    duplicates.add(numbers[num])
                else:
                    numbers[num] = item_id

        # Reset background color for all items in the main thread
        for item_id in self.file_list.get_children():
             current_tags = list(self.file_list.item(item_id, 'tags'))
             if 'duplicate' in current_tags:
                  current_tags.remove('duplicate')
             self.file_list.item(item_id, tags=tuple(current_tags))


        # Highlight duplicates in the main thread
        for item_id in duplicates:
            current_tags = list(self.file_list.item(item_id, 'tags'))
            if 'duplicate' not in current_tags:
                 current_tags.append('duplicate')
            self.file_list.item(item_id, tags=tuple(current_tags))


        # Configure tag for duplicate items (should be done once, but safe to repeat)
        self.file_list.tag_configure("duplicate", background="red")

        # Enable/disable convert button in the main thread
        if duplicates:
            self.convert_btn.config(state="disabled")
        else:
            # Also check if there are files to convert
            if self.files:
                 self.convert_btn.config(state="normal")
            else:
                 self.convert_btn.config(state="disabled")


    def drop_inside(self, event):
        """Handle file drop event. Process paths in executor."""
        try:
            # Get list of paths
            paths = self.tk.splitlist(event.data)

            # Process dropped paths in the executor
            self.executor.submit(self._process_dropped_paths, paths)

        except tk.TclError:
            pass
        except Exception as e:
            logging.error(f"Error handling drop event: {e}")
            self.parent.log_message(f"[ОШИБКА] Ошибка при обработке перетаскивания: {e}")


    def _process_dropped_paths(self, paths):
        """Process dropped paths (files and directories) and update GUI in main thread."""
        new_files_data = []
        for path in paths:
            path = path.strip()
            try:
                if os.path.isfile(path):
                    file_size = os.path.getsize(path)
                    new_files_data.append({"path": path, "num": tk.StringVar(value=""), "size": file_size})
                elif os.path.isdir(path):
                    # Walk through directory and collect files - Offload os.walk and os.path.getsize
                    # Use result() to wait for the walk to complete in the executor
                    for root, _, files in self.executor.submit(os.walk, path).result():
                        for file in files:
                            file_path = os.path.join(root, file)
                            # Offload os.path.getsize for each file
                            file_size = self.executor.submit(os.path.getsize, file_path).result()
                            new_files_data.append({"path": file_path, "num": tk.StringVar(value=""), "size": file_size})
            except Exception as e:
                 logging.error(f"Error processing dropped path {path}: {e}")
                 self.parent.log_message(f"[ОШИБКА] Не удалось обработать перетащенный путь {os.path.basename(path)}: {e}")


        # Update self.files and Treeview in the main thread
        self.master.after(0, self._update_file_list_gui, new_files_data) # Reuse the GUI update method


    def format_size(self, size):
        """Formats the file size into a human-readable string."""
        power = 2**10
        n = 0
        power_labels = {0 : 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
        while size >= power and n < len(power_labels) - 1: # Added check to prevent index error
            size /= power
            n += 1
        return f"{size:.2f} {power_labels[n]}"