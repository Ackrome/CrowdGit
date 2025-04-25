import threading
import sv_ttk
from concurrent.futures import ThreadPoolExecutor
import os
import logging
from urllib.parse import quote
import asyncio
import aiohttp
from aiohttp import ClientSession
import base64
import re
import json
import traceback
from github import Github, GithubException
from tkinter import ttk, messagebox
import tkinter as tk
import time
import random

class LoadWindow(tk.Toplevel):
    """
    A Toplevel window for browsing and downloading content from a GitHub repository.
    Handles both regular files and files split into parts.
    Optimized for faster network operations using aiohttp and lazy loading for Treeview.
    """
    def __init__(self, master, token, repo_name, local_base_path, parent):
        """
        Initializes the LoadWindow for browsing and downloading GitHub repository content.

        Args:
            master: The parent Tkinter window (usually the main application window).
            token (str): The GitHub personal access token.
            repo_name (str): The name of the repository (e.g., 'username/repo').
            local_base_path (str): The local directory to save downloaded files.
            parent: The parent application instance (used for logging).
        """
        super().__init__(master)
        self.title("Просмотр репозитория и загрузка")
        self.geometry("800x600")
        # Ensure timeout is an integer or float suitable for aiohttp
        self.timeout = aiohttp.ClientTimeout(total=int(getattr(parent, 'timeout', 180))) # Default to 180 seconds if parent.timeout is not available or invalid

        self.master = master
        self.repo_name = repo_name
        self.token = token
        self.parent = parent # Reference to the main application for logging
        self.local_base_path = local_base_path
        self.github_repo = None # Keep for initial connection and potentially tree structure fetching
        self.cancel_flag = False  # Flag to cancel download operations

        # Use a set to keep track of original files for which parts are being downloaded
        # This prevents trying to download/reconstruct the same file multiple times
        # if multiple parts of it are selected or encountered during recursion.
        self.reconstruction_queued = set()
        # Executor for running synchronous tasks (file I/O, decoding, JSON parsing)
        self.executor = ThreadPoolExecutor(max_workers=os.cpu_count() or 1) # Use number of CPU cores for CPU-bound tasks
        self.reconstruction_lock = asyncio.Lock() # Lock to prevent multiple simultaneous reconstructions of the same file

        # Dictionary to keep track of directories that have been loaded
        self.loaded_directories = set()

        self.create_widgets()
        self.grid_layout()

        # Apply current theme
        self.apply_theme()

        # Start fetching repo tree in a separate thread to avoid blocking the GUI
        threading.Thread(target=self.fetch_and_display_repo_tree, daemon=True).start()

    def create_widgets(self):
        """Creates the widgets for the LoadWindow."""
        self.tree_frame = ttk.Frame(self)
        self.tree_scroll_y = ttk.Scrollbar(self.tree_frame, orient="vertical")
        self.tree_scroll_x = ttk.Scrollbar(self.tree_frame, orient="horizontal")

        self.repo_tree = ttk.Treeview(self.tree_frame,
                                      yscrollcommand=self.tree_scroll_y.set,
                                      xscrollcommand=self.tree_scroll_x.set)
        self.tree_scroll_y.config(command=self.repo_tree.yview)
        self.tree_scroll_x.config(command=self.repo_tree.xview)

        # Define columns (optional, but good practice)
        self.repo_tree['columns'] = ('type',)
        self.repo_tree.column('#0', width=300, minwidth=150, stretch=tk.YES)  # Main tree column for names
        self.repo_tree.column('type', width=100, minwidth=50, stretch=tk.NO)

        self.repo_tree.heading('#0', text='Имя')
        self.repo_tree.heading('type', text='Тип')

        # Bind selection event
        self.repo_tree.bind('<<TreeviewSelect>>', self.on_item_select)
        # Bind the Treeview open event for lazy loading
        self.repo_tree.bind('<<TreeviewOpen>>', self.on_tree_expand)


        self.download_button = ttk.Button(self, text="Скачать выбранное", command=self.start_download_selected,
                                          state=tk.DISABLED)
        self.status_label = ttk.Label(self, text="Подключение к GitHub...")
        self.progress_bar = ttk.Progressbar(self, mode="indeterminate") # Start with indeterminate mode
        self.cancel_button = ttk.Button(self, text="Отмена", command=self.cancel_download, state=tk.DISABLED)
        self.reconstruct_button = ttk.Button(self, text="Реконструировать файлы", command=self.start_reconstruct_files)

        # New: Overwrite checkbox
        self.overwrite_existing_var = tk.BooleanVar(value=False)
        self.overwrite_checkbox = ttk.Checkbutton(self, text="Перезаписать существующие", variable=self.overwrite_existing_var)


    def grid_layout(self):
        """Arranges the widgets using the grid layout manager."""
        self.tree_frame.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
        self.repo_tree.grid(row=0, column=0, sticky="nsew")
        self.tree_scroll_y.grid(row=0, column=1, sticky="ns")
        self.tree_scroll_x.grid(row=1, column=0, sticky="ew")

        self.tree_frame.grid_columnconfigure(0, weight=1)
        self.tree_frame.grid_rowconfigure(0, weight=1)

        self.status_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=2)
        self.progress_bar.grid(row=2, column=0, columnspan=3, sticky="we", padx=5, pady=5)
        self.download_button.grid(row=3, column=0, padx=5, pady=5)
        self.cancel_button.grid(row=3, column=1, padx=5, pady=5)
        self.reconstruct_button.grid(row=3, column=2, padx=5, pady=5)
        # New: Place the overwrite checkbox
        self.overwrite_checkbox.grid(row=1, column=2, sticky="e", padx=5, pady=2)


        # Configure grid weights for resizing
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

    def apply_theme(self):
        """Applies the current sv_ttk theme to this window."""
        # sv_ttk handles Toplevel windows automatically if they are created after setting the theme.
        # However, explicitly setting the theme can ensure consistency if the theme changes
        # while this window is open.
        current_theme = sv_ttk.get_theme()
        sv_ttk.set_theme(current_theme)  # Re-apply the theme to this window

    # Modified to fetch only the root level initially
    async def async_fetch_repo_tree(self, session, repo_path=''):
        """Fetches the repository structure asynchronously for a given path using aiohttp."""
        if self.cancel_flag:
            return []

        url = f"https://api.github.com/repos/{self.repo_name}/contents/{quote(repo_path)}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

        try:
            async with session.get(url, headers=headers, timeout=self.timeout) as response:
                response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
                contents = await response.json()

            items = []
            for content in contents:
                if self.cancel_flag:
                    return []
                item = {
                    'name': content.get('name'),
                    'path': content.get('path'),
                    'type': content.get('type'), # 'dir' or 'file'
                    'sha': content.get('sha') if content.get('type') == 'file' else None,
                    # No recursive fetching here for lazy loading
                }
                items.append(item)
            return items
        except aiohttp.ClientResponseError as e:
            logging.error(f"HTTP error fetching repo tree at {repo_path}: {e.status} - {e.message}")
            self.parent.log_message(f"[ОШИБКА] Ошибка HTTP при получении структуры репозитория: {e.status} - {e.message}")
            return []
        except aiohttp.ClientError as e:
            logging.error(f"Network error fetching repo tree at {repo_path}: {e}")
            self.parent.log_message(f"[ОШИБКА] Сетевая ошибка при получении структуры репозитория: {e}")
            return []
        except Exception as e:
            logging.error(f"Unexpected error fetching repo tree at {repo_path}: {e}")
            self.parent.log_message(f"[ОШИБКА] Неожиданная ошибка при получении структуры репозитория: {e}")
            return []


    def fetch_and_display_repo_tree(self):
        """Fetches the root level of the repo tree asynchronously and populates the treeview."""
        self.parent.log_message("Подключение к GitHub...")
        self.toggle_progress(True, mode="indeterminate") # Start with indeterminate mode
        self.cancel_flag = False
        self.master.after(0, lambda: self.cancel_button.config(state=tk.NORMAL))

        async def run_fetch():
            try:
                # Initial check with synchronous GitHub library
                g = Github(self.token)
                self.github_repo = g.get_repo(self.repo_name)
                self.parent.log_message(f"Подключено к репозиторию: {self.repo_name}")

                # Use aiohttp session for asynchronous fetching
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    # Fetch only the root level
                    repo_tree_data = await self.async_fetch_repo_tree(session, '')

                if not self.cancel_flag:
                    self.master.after(0, self.populate_treeview, repo_tree_data) # Update GUI in main thread
                    self.parent.log_message("Структура репозитория загружена.")

            except GithubException as e:
                logging.error(f"GithubException during repo connection or initial fetch: {e}")
                self.parent.log_message(f"[ОШИБКА] Ошибка GitHub: {e}")
                self.master.after(0, messagebox.showerror, "Ошибка GitHub", f"Не удалось подключиться к репозиторию или получить структуру: {e}")
            except Exception as e:
                logging.error(f"Unexpected error during repo connection or initial fetch: {e}")
                self.parent.log_message(f"[ОШИБКА] Неожиданная ошибка: {e}")
                self.master.after(0, messagebox.showerror, "Неизвестная ошибка", f"Произошла ошибка: {e}")
            finally:
                self.master.after(0, self.toggle_progress, False)
                self.master.after(0, lambda: self.cancel_button.config(state=tk.DISABLED))

        # Run the async fetch in a separate thread
        threading.Thread(target=lambda: asyncio.run(run_fetch()), daemon=True).start()


    # Modified to populate only the current level and add placeholders for directories
    def populate_treeview(self, data, parent_iid=''):
        """Populates the Treeview with repository data for a given level."""
        if self.cancel_flag:
            return

        # Clear existing items if populating the root
        if parent_iid == '':
            for item in self.repo_tree.get_children():
                self.repo_tree.delete(item)

        for item in data:
            # Use item['name'] as text, item['type'] as value for the 'type' column
            iid = self.repo_tree.insert(parent_iid, 'end', text=item['name'], values=(item['type'],), open=False)
            self.repo_tree.set(iid, 'type', item['type'])  # Ensure 'type' is set

            # Store item data (path, sha, etc.) in the item's tags
            # Using tags for easier retrieval: (path, type, sha)
            self.repo_tree.item(iid, tags=(item['path'], item['type'], item.get('sha')))

            # If it's a directory, add a dummy child item to make it expandable
            if item['type'] == 'dir':
                # Add a placeholder child. We can use a special tag or text to identify it later.
                self.repo_tree.insert(iid, 'end', text="Загрузка...", tags=('loading_placeholder',))
                # Mark the directory as not yet loaded
                self.loaded_directories.discard(item['path'])
            else:
                 # Mark files as loaded since their info is complete
                 self.loaded_directories.add(item['path'])


    # New method to handle directory expansion
    def on_tree_expand(self, event):
        """Handles the TreeviewOpen event to load directory contents lazily."""
        item_iid = self.repo_tree.focus() # Get the item that was expanded
        if not item_iid:
            return

        item_tags = self.repo_tree.item(item_iid, 'tags')
        item_path = item_tags[0] if item_tags else None
        item_type = item_tags[1] if len(item_tags) > 1 else None

        # Check if the expanded item is a directory and hasn't been loaded yet
        if item_type == 'dir' and item_path not in self.loaded_directories:
            # Remove the loading placeholder
            for child_iid in self.repo_tree.get_children(item_iid):
                if 'loading_placeholder' in self.repo_tree.item(child_iid, 'tags'):
                    self.repo_tree.delete(child_iid)
                    break # Assuming only one placeholder per directory

            self.parent.log_message(f"Загрузка содержимого папки: {item_path}...")
            self.toggle_progress(True, mode="indeterminate")

            # Fetch directory contents asynchronously in a separate thread
            async def fetch_and_populate():
                try:
                    async with aiohttp.ClientSession(timeout=self.timeout) as session:
                        contents = await self.async_fetch_repo_tree(session, item_path) # Fetch contents of the expanded directory

                    if not self.cancel_flag:
                        self.master.after(0, self.populate_treeview, contents, item_iid) # Populate the expanded node
                        self.loaded_directories.add(item_path) # Mark as loaded
                        self.parent.log_message(f"Содержимое папки загружено: {item_path}")

                except Exception as e:
                    logging.error(f"Error fetching contents for directory {item_path}: {e}")
                    self.parent.log_message(f"[ОШИБКА] Ошибка при загрузке содержимого папки {item_path}: {e}")
                    # Re-add a placeholder or indicate error if fetching failed
                    self.master.after(0, lambda: self.repo_tree.insert(item_iid, 'end', text="Ошибка загрузки", tags=('loading_error',)))
                finally:
                    self.master.after(0, self.toggle_progress, False)

            threading.Thread(target=lambda: asyncio.run(fetch_and_populate()), daemon=True).start()


    def on_item_select(self, event):
        """Handles item selection in the Treeview."""
        selected_items = self.repo_tree.selection()
        if selected_items:
            # Enable download button if any item is selected
            self.download_button.config(state=tk.NORMAL)
        else:
            self.download_button.config(state=tk.DISABLED)

    def start_download_selected(self):
        """Starts the download process for the selected item(s) in a new thread."""
        selected_items = self.repo_tree.selection()
        if not selected_items:
            messagebox.showwarning("Нет выбора", "Пожалуйста, выберите файл или папку для скачивания.")
            return

        # Get the local destination folder
        download_dir = self.local_base_path
        if not download_dir:
            return  # User cancelled

        self.parent.log_message("Начало загрузки...")
        self.toggle_progress(True, mode="indeterminate") # Start with indeterminate mode
        self.cancel_flag = False
        self.reconstruction_queued.clear()  # Clear the set before a new download process
        self.master.after(0, lambda: self.cancel_button.config(state=tk.NORMAL))
        self.master.after(0, lambda: self.download_button.config(state=tk.DISABLED))

        # Run download in a separate thread using asyncio event loop
        def run_async_download():
            asyncio.run(self.threaded_download(selected_items, download_dir))

        threading.Thread(target=run_async_download, daemon=True).start()

    async def threaded_download(self, selected_items, download_dir):
        """Handles the asynchronous download process in a thread."""
        download_tasks = []
        # Use a single aiohttp session for all downloads in this process
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            for item_iid in selected_items:
                if self.cancel_flag:
                    break  # Stop processing new items if cancelled

                item_tags = self.repo_tree.item(item_iid, 'tags')
                item_path = item_tags[0] if item_tags else None
                item_type = item_tags[1] if len(item_tags) > 1 else None
                item_sha = item_tags[2] if len(item_tags) > 2 else None

                if not item_path or not item_type:
                    logging.warning(f"Skipping item with missing info: {item_iid}")
                    continue

                if item_type == 'file':
                    # Check if it's a part file
                    if ".part" in item_path and item_path.endswith(".txt"):
                        # If a part file is selected, find all parts for the original file
                        original_file_path_base = item_path.rsplit('.parts/', 1)[0] if '.parts/' in item_path else None
                        if original_file_path_base and original_file_path_base not in self.reconstruction_queued:
                            # Mark this original file for reconstruction to avoid duplicates
                            self.reconstruction_queued.add(original_file_path_base)

                            # Find all parts for this original file in the treeview
                            # This part assumes the treeview is already populated for the parts directory.
                            # With lazy loading, this might not be the case.
                            # A more robust approach would be to fetch the contents of the .parts directory
                            # if it's not already loaded.
                            parts_dir_iid = self.repo_tree.parent(item_iid)
                            if parts_dir_iid:
                                # Ensure the parts directory is loaded if not already
                                parts_dir_path = self.repo_tree.item(parts_dir_iid, 'tags')[0]
                                if parts_dir_path not in self.loaded_directories:
                                     self.parent.log_message(f"[ИНФО] Загрузка содержимого папки частей: {parts_dir_path}...")
                                     # Fetch contents of the parts directory
                                     parts_dir_contents = await self.async_fetch_repo_tree(session, parts_dir_path)
                                     # Populate the treeview for the parts directory (optional, but keeps treeview consistent)
                                     self.master.after(0, self.populate_treeview, parts_dir_contents, parts_dir_iid)
                                     self.loaded_directories.add(parts_dir_path) # Mark as loaded


                                part_iids = self.repo_tree.get_children(parts_dir_iid)
                                part_files_info = []
                                for part_iid in part_iids:
                                    part_tags = self.repo_tree.item(part_iid, 'tags')
                                    # Check if it's a file and not a loading placeholder or error indicator
                                    if part_tags and len(part_tags) > 1 and part_tags[1] == 'file' and 'loading_placeholder' not in part_tags and 'loading_error' not in part_tags:
                                        part_file_path = part_tags[0]
                                        part_sha = part_tags[2] if len(part_tags) > 2 else None
                                        # Ensure the part file belongs to the current original file
                                        if part_file_path.startswith(
                                                original_file_path_base + ".parts/") and part_file_path.endswith(".txt"):
                                            part_files_info.append({'path': part_file_path, 'sha': part_sha})

                                if part_files_info:
                                    task = asyncio.create_task(
                                        self.download_and_reconstruct_parts(session, part_files_info, download_dir,
                                                                            original_file_path_base))
                                    download_tasks.append(task)
                                else:
                                    self.parent.log_message(
                                        f"[ПРЕДУПРЕЖДЕНИЕ] Не найдено файлов частей для {original_file_path_base}. Пропускаю.")
                                    logging.warning(
                                        f"No part files found in treeview for {original_file_path_base}. Skipping reconstruction.")
                            else:
                                self.parent.log_message(
                                    f"[ПРЕДУПРЕЖДЕНИЕ] Не найдена папка частей для {item_path}. Пропускаю.")
                                logging.warning(f"Could not find parts directory for {item_path}. Skipping.")
                        elif original_file_path_base in self.reconstruction_queued:
                            logging.info(
                                f"Reconstruction for {original_file_path_base} already queued. Skipping part {item_path}.")
                            self.parent.log_message(
                                f"[ИНФО] Сборка для {original_file_path_base} уже запланирована. Пропускаю часть {os.path.basename(item_path)}.")
                        else:
                            self.parent.log_message(
                                f"[ПРЕДУПРЕЖДЕНИЕ] Не удалось определить исходный файл для части {item_path}. Пропускаю.")
                            logging.warning(f"Could not determine original file path for part {item_path}. Skipping.")
                    else:
                        # It's a regular file, download it directly
                        task = asyncio.create_task(self.download_single_file(session, item_path, item_sha, download_dir))
                        download_tasks.append(task)

                elif item_type == 'dir':
                    # If a directory is selected, download all its contents recursively
                    # We need to fetch the directory contents again to get all files/subdirs
                    self.parent.log_message(f"Скачивание содержимого папки: {item_path}")
                    logging.info(f"Downloading contents of directory: {item_path}")
                    # Recursive download is asynchronous within the thread
                    await self.download_directory_contents(session, item_path, download_dir)

            # Wait for all initial tasks to complete
            await asyncio.gather(*download_tasks)


        if not self.cancel_flag:
            self.parent.log_message("Загрузка завершена.")
            logging.info("Download process finished.")
            # Use self.master.after to show messagebox in the main GUI thread
            self.master.after(0, messagebox.showinfo, "Загрузка завершена", "Все выбранные файлы и папки скачаны.")
        else:
            self.parent.log_message("Загрузка отменена.")
            logging.info("Download process cancelled.")
            # Use self.master.after to show messagebox in the main GUI thread
            self.master.after(0, messagebox.showinfo, "Загрузка отменена", "Загрузка была отменена пользователем.")

        # Update GUI elements in the main thread
        self.master.after(0, self.toggle_progress, False)
        self.master.after(0, lambda: self.cancel_button.config(state=tk.DISABLED))
        self.master.after(0, lambda: self.download_button.config(state=tk.NORMAL))

    async def download_single_file(self, session, repo_file_path, file_sha, local_base_dir, is_part=False):
        """Asynchronously downloads a single file from GitHub using aiohttp."""
        if self.cancel_flag:
            self.log_message(f"[ИНФО] Загрузка файла {os.path.basename(repo_file_path)} отменена.")
            logging.info(f"Download of {repo_file_path} cancelled.")
            return

        local_file_path = os.path.join(local_base_dir, repo_file_path)
        local_dir = os.path.dirname(local_file_path)

        # Offload directory creation check and creation to executor
        if not await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.path.exists(local_dir)):
             await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.makedirs(local_dir, exist_ok=True)) # Ensure local directory exists

        # Check if file already exists locally and if overwrite is disabled - offload to executor
        if await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.path.exists(local_file_path)) and not self.overwrite_existing_var.get():
            self.log_message(f"[ИНФО] Файл уже существует локально: {os.path.basename(repo_file_path)}. Пропускаю.")
            logging.info(f"File already exists locally: {local_file_path}. Skipping download.")
            return # Skip download if file exists and overwrite is disabled

        self.log_message(f"[ИНФО] Скачивание файла: {os.path.basename(repo_file_path)}")
        logging.info(f"Downloading file: {repo_file_path}")

        try:
            # Using the Git Blob API with raw content accept header for efficiency
            repo_owner, repo_name = self.repo_name.split('/')
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/blobs/{file_sha}"
            headers = {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3.raw"  # Request raw content
            }

            async with session.get(url, headers=headers) as response: # Use the passed session
                response.raise_for_status()  # Raise an exception for bad status codes

                # Read content asynchronously and write to file in executor
                content = await response.read()
                await asyncio.get_event_loop().run_in_executor(self.executor, lambda: self._write_file_content(local_file_path, content))


            if is_part:
                self.parent.log_message(f"[OK] Скачана часть файла: {os.path.basename(repo_file_path)}")
                logging.info(f"Successfully downloaded part file: {repo_file_path}")
            else:
                self.parent.log_message(f"[OK] Скачан файл: {os.path.basename(repo_file_path)}")
                logging.info(f"Successfully downloaded file: {repo_file_path}")

        except aiohttp.ClientResponseError as e:
            logging.error(f"HTTP error downloading file {repo_file_path}: {e.status} - {e.message}")
            self.parent.log_message(f"[ОШИБКА] Ошибка HTTP при скачивании файла {os.path.basename(repo_file_path)}: {e.status} - {e.message}")
        except aiohttp.ClientError as e:
            logging.error(f"Network error downloading file {repo_file_path}: {e}")
            self.parent.log_message(f"[ОШИБКА] Сетевая ошибка при скачивании файла {os.path.basename(repo_file_path)}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error downloading file {repo_file_path}: {e}")
            self.parent.log_message(
                f"[ОШИБКА] Неожиданная ошибка при скачивании файла {os.path.basename(repo_file_path)}: {e}")

    # Helper function to write file content in executor
    def _write_file_content(self, file_path, content):
        """Writes content to a file synchronously."""
        with open(file_path, 'wb') as f:
            f.write(content)

    # Refactored to use aiohttp for asynchronous directory content fetching
    async def download_directory_contents(self, session, repo_dir_path, local_base_dir):
        """Recursively downloads contents of a directory from GitHub using aiohttp."""
        if self.cancel_flag:
            self.log_message(f"[ИНФО] Скачивание содержимого папки {repo_dir_path} отменено.")
            logging.info(f"Download of directory {repo_dir_path} cancelled.")
            return

        url = f"https://api.github.com/repos/{self.repo_name}/contents/{quote(repo_dir_path)}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

        try:
            async with session.get(url, headers=headers, timeout=self.timeout) as response:
                response.raise_for_status() # Raise an exception for bad status codes
                contents = await response.json()

            part_files_to_reconstruct = {}  # Dictionary to collect part files for reconstruction

            for content in contents:
                if self.cancel_flag:
                    self.log_message(f"[ИНФО] Скачивание содержимого папки {repo_dir_path} отменено.")
                    logging.info(f"Download of directory {repo_dir_path} cancelled.")
                    return

                local_path = os.path.join(local_base_dir, content.get('path'))

                if content.get('type') == 'dir':
                    # Check if it's a .parts directory
                    if content.get('name', '').endswith(".parts"):
                        logging.info(f"Scanning contents of .parts directory: {content.get('path')}")
                        # Recursively scan the .parts directory to collect part file info
                        # We still need to traverse the tree to find all parts, but don't download content here
                        await self.download_directory_contents(session, content.get('path'), local_base_dir)
                        continue  # Skip recursing into the .parts directory again for regular files
                    # Create local directory and recurse for regular directories
                    # Offload directory creation to executor
                    if not await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.path.exists(local_path)):
                         await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.makedirs(local_path, exist_ok=True))
                    await self.download_directory_contents(session, content.get('path'), local_base_dir)
                elif content.get('type') == 'file':
                    # Check if it's a part file within a .parts directory
                    if ".parts/" in content.get('path', '') and content.get('path', '').endswith(".txt"):
                        # Collect part files for potential reconstruction
                        original_file_path_base = content.get('path').rsplit('.parts/', 1)[0]
                        if original_file_path_base not in part_files_to_reconstruct:
                            part_files_to_reconstruct[original_file_path_base] = []
                        part_files_to_reconstruct[original_file_path_base].append(
                            {'path': content.get('path'), 'sha': content.get('sha')})
                        # IMPORTANT: DO NOT download the part file content here.
                        # It will be downloaded asynchronously by download_and_reconstruct_parts.
                        self.parent.log_message(f"[ИНФО] Найден файл части: {content.get('name')}")
                        logging.info(f"Found part file during recursive scan: {content.get('path')}")
                    else:
                        # It's a regular file, download it
                        await self.download_single_file(session, content.get('path'), content.get('sha'), local_base_dir)

            # After processing all contents in this directory level, queue reconstruction for collected part files
            for original_file_path_base, part_files_info in part_files_to_reconstruct.items():
                if self.cancel_flag:
                    self.log_message(f"[ИНФО] Очередь сборки для папки {repo_dir_path} отменена.")
                    logging.info(f"Reconstruction queue for directory {repo_dir_path} cancelled.")
                    return
                if original_file_path_base not in self.reconstruction_queued:
                    self.reconstruction_queued.add(original_file_path_base)
                    # Create a task to download and reconstruct the original file
                    asyncio.create_task(
                        self.download_and_reconstruct_parts(session, part_files_info, local_base_dir,
                                                            original_file_path_base))

        except aiohttp.ClientResponseError as e:
            logging.error(f"HTTP error downloading directory {repo_dir_path}: {e.status} - {e.message}")
            self.parent.log_message(f"[ОШИБКА] Ошибка HTTP при скачивании папки {repo_dir_path}: {e.status} - {e.message}")
        except aiohttp.ClientError as e:
            logging.error(f"Network error downloading directory {repo_dir_path}: {e}")
            self.parent.log_message(f"[ОШИБКА] Сетевая ошибка при скачивании папки {repo_dir_path}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error downloading directory {repo_dir_path}: {e}")
            self.parent.log_message(f"[ОШИБКА] Неожиданная ошибка при скачивании папки {repo_dir_path}: {e}")

    def log_message(self, msg):
        """Logs a message to the status label and main app's log."""
        # Update status label in the GUI thread
        self.master.after(0, lambda: self.status_label.config(text=msg))
        # Also log to the main application's log text widget
        if hasattr(self.master, 'log_message'):
             self.master.after(0, self.master.log_message, msg)
        else:
             logging.info(f"LoadWindow: {msg}")

    def toggle_progress(self, start=True, mode="indeterminate", maximum=0):
        """Toggles the progress bar and sets its mode/maximum."""
        # Ensure GUI updates happen in the main thread
        if start:
            self.master.after(0, lambda: self.progress_bar.config(mode=mode, maximum=maximum))
            self.master.after(0, self.progress_bar.start)
            logging.info(f"LoadWindow: Progress bar started in {mode} mode.")
        else:
            self.master.after(0, self.progress_bar.stop)
            self.master.after(0, lambda: self.progress_bar.config(mode="indeterminate", value=0)) # Reset after stopping
            logging.info("LoadWindow: Progress bar stopped.")

    def update_progress_value(self, value):
        """Updates the value of the determinate progress bar."""
        # Ensure GUI updates happen in the main thread
        self.master.after(0, lambda: self.progress_bar.config(value=value))


    def cancel_download(self):
        """Sets the cancel flag to stop the download process."""
        self.cancel_flag = True
        self.parent.log_message("[ИНФО] Запрос на отмену загрузки...")
        logging.info("LoadWindow: Cancel requested.")
        self.master.after(0, lambda: self.cancel_button.config(state=tk.DISABLED))

    def start_reconstruct_files(self):
        """Starts the file reconstruction process in a new thread."""
        self.parent.log_message("Начало реконструкции файлов...")
        self.toggle_progress(True, mode="indeterminate") # Start with indeterminate mode
        self.cancel_flag = False
        self.reconstruction_queued.clear()  # Clear the set before a new reconstruction process
        self.master.after(0, lambda: self.cancel_button.config(state=tk.NORMAL))
        self.master.after(0, lambda: self.reconstruct_button.config(state=tk.DISABLED))

        # Run reconstruction in a separate thread using asyncio event loop
        def run_async_reconstruction():
             asyncio.run(self.threaded_reconstruct_files(self.local_base_path))

        threading.Thread(target=run_async_reconstruction, daemon=True).start()


    async def threaded_reconstruct_files(self, download_dir):
        """Handles the asynchronous file reconstruction process in a thread."""
        try:
            # Use a single aiohttp session for potential part downloads during reconstruction scan
             async with aiohttp.ClientSession(timeout=self.timeout) as session:
                await self.reconstruct_files_in_directory(session, download_dir)
        except Exception as e:
            logging.error(f"An unexpected error occurred during file reconstruction: {e}")
            self.parent.log_message(f"[ОШИБКА] Неожиданная ошибка во время реконструкции файлов: {e}")
            # Show error messagebox in the main GUI thread
            self.master.after(0, messagebox.showerror, "Ошибка", f"Произошла непредвиденная ошибка: {e}")
        finally:
            if not self.cancel_flag:
                self.parent.log_message("Реконструкция файлов завершена.")
                logging.info("File reconstruction process finished.")
                # Show info messagebox in the main GUI thread
                self.master.after(0, messagebox.showinfo, "Реконструкция завершена", "Все найденные файлы были реконструированы.")
            else:
                self.parent.log_message("Реконструкция файлов отменена.")
                logging.info("File reconstruction process cancelled.")
                # Show info messagebox in the main GUI thread
                self.master.after(0, messagebox.showinfo, "Реконструкция отменена", "Реконструкция файлов была отменена пользователем.")

            # Update GUI elements in the main thread
            self.master.after(0, self.toggle_progress, False)
            self.master.after(0, lambda: self.cancel_button.config(state=tk.DISABLED))
            self.master.after(0, lambda: self.reconstruct_button.config(state=tk.NORMAL))

    async def reconstruct_files_in_directory(self, session, directory):
        """
        Scans a directory for .parts directories, checks for complete part sets,
        and reconstructs the original files. Uses aiohttp session for potential part downloads.
        """
        if self.cancel_flag:
            self.log_message("[ИНФО] Сканирование директорий для реконструкции отменено.")
            logging.info("Directory scanning for reconstruction cancelled.")
            return

        tasks = []
        # Use os.walk in an executor as it's a synchronous I/O operation
        self.log_message(f"[ИНФО] Сканирование локальной директории для файлов частей: {directory}")
        for root, dirs, _ in await asyncio.get_event_loop().run_in_executor(self.executor, lambda: list(os.walk(directory))):
            for dir_name in dirs:
                if self.cancel_flag:
                    self.log_message("[ИНФО] Сканирование директорий для реконструкции отменено.")
                    logging.info(f"Directory scanning for reconstruction cancelled in {directory}.")
                    return
                if dir_name.endswith(".parts"):
                    parts_dir_path = os.path.join(root, dir_name)
                    original_file_path_base = parts_dir_path.rsplit('.parts', 1)[0]

                    if original_file_path_base not in self.reconstruction_queued:
                        self.reconstruction_queued.add(original_file_path_base)
                        # Pass the aiohttp session to process_parts_directory
                        tasks.append(self.process_parts_directory(session, parts_dir_path, directory, original_file_path_base))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def process_parts_directory(self, session, parts_dir_path, directory, original_file_path_base):
        """Processes a single .parts directory."""
        async with self.reconstruction_lock:
            if self.cancel_flag:
                self.log_message(f"[ИНФО] Обработка директории частей {parts_dir_path} отменена.")
                logging.info(f"Processing of parts directory {parts_dir_path} cancelled.")
                return

            original_filename = os.path.basename(original_file_path_base)
            part_files_info = []
            # List files in the parts directory to get their names and paths - offload to executor
            try:
                part_filenames_in_dir = await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.listdir(parts_dir_path))
            except FileNotFoundError:
                 logging.warning(f"Parts directory not found during processing: {parts_dir_path}. Skipping.")
                 self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Директория частей не найдена при обработке: {parts_dir_path}. Пропускаю.")
                 return
            except Exception as e:
                 logging.error(f"Error listing files in parts directory {parts_dir_path}: {e}. Skipping.")
                 self.log_message(f"[ОШИБКА] Ошибка при получении списка файлов в директории частей {parts_dir_path}: {e}. Пропускаю.")
                 return


            for part_file_name in part_filenames_in_dir:
                if self.cancel_flag:
                    self.log_message(f"[ИНФО] Обработка директории частей {parts_dir_path} отменена.")
                    logging.info(f"Processing of parts directory {parts_dir_path} cancelled.")
                    return
                # We need the full path relative to the repo root for download_single_part_content
                # Assuming the parts directory structure on disk mirrors the repo structure relative to local_base_path
                # Construct the relative path from local_base_path to the part file
                local_part_file_path = os.path.join(parts_dir_path, part_file_name)
                part_repo_path_relative = os.path.relpath(local_part_file_path, self.local_base_path)


                if part_file_name.endswith(".txt") and part_file_name.startswith(os.path.basename(original_file_path_base) + ".part"):
                     part_files_info.append(
                         {'path': part_repo_path_relative,
                          'sha': None})  # sha is not needed for local reconstruction, but path is repo-relative

            if part_files_info:
                # Now call download_and_reconstruct_parts with the list of part file info
                # This will initiate the asynchronous download of parts from GitHub and reconstruction
                # Pass the aiohttp session
                await self.download_and_reconstruct_parts(session, part_files_info, directory,
                                                          original_file_path_base)
            else:
                self.parent.log_message(
                    f"[ПРЕДУПРЕЖДЕНИЕ] Не найдено файлов частей для {original_filename} в директории {parts_dir_path}. Пропускаю.")
                logging.warning(f"No part files found for {original_filename} in directory {parts_dir_path}. Skipping reconstruction.")


    async def download_and_reconstruct_parts(self, session, part_files_info, download_dir, original_file_path_base):
        """
        Downloads all part files for a given original file using aiohttp,
        validates metadata, reconstructs the original file in memory,
        writes it to disk, and cleans up the part files and directory.
        Uses the passed aiohttp session.
        """
        if self.cancel_flag:
            self.log_message(f"[ИНФО] Скачивание и сборка файла {os.path.basename(original_file_path_base)} отменены.")
            logging.info(f"Download and reconstruction of {os.path.basename(original_file_path_base)} cancelled.")
            return

        original_filename = os.path.basename(original_file_path_base)
        reconstructed_file_path = os.path.join(download_dir, original_file_path_base)

        # Check if the final reconstructed file already exists locally and if overwrite is disabled - offload to executor
        if await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.path.exists(reconstructed_file_path)) and not self.overwrite_existing_var.get():
            self.log_message(f"[ИНФО] Собранный файл уже существует локально: {original_filename}. Пропускаю сборку.")
            logging.info(f"Reconstructed file already exists locally: {reconstructed_file_path}. Skipping reconstruction.")
            # Clean up part files if the reconstructed file exists and overwrite is disabled - offload to executor
            asyncio.create_task(self.cleanup_parts_directory(download_dir, original_file_path_base, force_cleanup=True)) # Force cleanup if skipping
            return # Skip reconstruction if the final file exists

        self.log_message(f"[ИНФО] Скачивание частей для сборки файла: {original_filename}")
        logging.info(f"Downloading parts for reconstruction: {original_filename}")

        download_errors = []
        total_parts_expected = None
        downloaded_part_count = 0 # Counter for downloaded parts
        part_download_failures = [] # Collect specific part download/processing errors
        part_data_by_index = {} # Initialize the dictionary before use


        # --- Download all part files asynchronously ---
        download_tasks = []
        for part_file_info in part_files_info:
            if self.cancel_flag:
                self.log_message(f"[ИНФО] Скачивание частей для сборки файла {original_filename} отменено.")
                logging.info(f"Download of parts for {original_filename} cancelled.")
                break
            part_repo_path = part_file_info['path']
            # Pass original_file_path_base for better logging context in download_single_part_content
            # Pass the aiohttp session
            task = asyncio.create_task(self.download_single_part_content(session, part_repo_path, original_file_path_base))
            download_tasks.append(task)

        # Set progress bar to determinate mode and set maximum
        total_parts_in_list = len(part_files_info)
        self.master.after(0, lambda: self.progress_bar.config(mode="determinate", maximum=total_parts_in_list))
        self.master.after(0, lambda: self.progress_bar.config(value=0)) # Reset progress value

        # Wait for all download tasks to complete
        # Use asyncio.as_completed to process results as they finish and update progress
        for future in asyncio.as_completed(download_tasks):
             if self.cancel_flag:
                  self.log_message(f"[ИНФО] Скачивание частей для сборки файла {original_filename} отменено.")
                  logging.info(f"Download of parts for {original_filename} cancelled.")
                  # Cancel remaining tasks
                  for task in download_tasks:
                       if not task.done():
                            task.cancel()
                  # Ensure progress bar is stopped and reset on cancellation
                  self.master.after(0, self.toggle_progress, False)
                  return # Exit if cancelled

             try:
                  result = await future
                  if isinstance(result, Exception):
                       # This case should ideally be handled within download_single_part_content's retries,
                       # but including here as a safeguard for unexpected exceptions.
                       logging.error(f"An unexpected error occurred during part download: {result}")
                       download_errors.append(f"Неожиданная ошибка при скачивании части: {result}")
                       # Assume inconsistency if any download failed, but don't set metadata_consistent here
                       # as it's checked later based on downloaded_part_count and total_parts_expected.
                  elif result and 'error' in result:
                       logging.error(f"Error downloading or processing part: {result['error']}")
                       download_errors.append(result['error'])
                       part_download_failures.append(result['error']) # Add to specific failures list
                       # Assume inconsistency if any part failed, but don't set metadata_consistent here
                  elif result:
                       # Successful download and processing
                       part_index = result.get('part_index')
                       total_parts = result.get('total_parts')
                       content = result.get('content')
                       part_filename = result.get('part_filename') # Get filename for logging

                       if part_index is None or total_parts is None or content is None:
                            logging.warning(f"Missing essential data in downloaded part result for {part_filename} (Original: {original_filename}).")
                            self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Отсутствуют необходимые данные в результате скачивания части {part_filename} (Оригинал: {original_filename}).")
                            download_errors.append(f"Отсутствуют необходимые данные в части {part_filename}")
                            continue # Skip this part, but don't necessarily fail the whole reconstruction yet

                       if total_parts_expected is None:
                           total_parts_expected = total_parts
                       elif total_parts != total_parts_expected:
                           logging.warning(f"Inconsistent total_parts in metadata for {part_filename} (Original: {original_filename}). Expected {total_parts_expected}, got {total_parts}.")
                           self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Несогласованное общее количество частей в метаданных для {part_filename} (Оригинал: {original_filename}). Ожидалось {total_parts_expected}, получено {total_parts}.")
                           # This is a significant inconsistency, should probably fail reconstruction
                           download_errors.append(f"Несогласованное общее количество частей в метаданных для {part_filename}")
                           continue # Skip this part

                       if part_index in part_data_by_index:
                           logging.warning(f"Duplicate part index found: {part_index} for {part_filename} (Original: {original_filename}).")
                           self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Обнаружен дублирующийся индекс части: {part_index} для {part_filename} (Оригинал: {original_filename}).")
                           # Treat duplicate as an error
                           download_errors.append(f"Обнаружен дублирующийся индекс части: {part_index} для {part_filename}")
                           continue # Skip this part
                       else:
                           part_data_by_index[part_index] = result
                           downloaded_part_count += 1
                           # Update status label and progress bar with progress
                           self.log_message(f"[ИНФО] Скачано частей для {original_filename}: {downloaded_part_count}/{total_parts_expected if total_parts_expected is not None else '?'}")
                           self.update_progress_value(downloaded_part_count)


             except asyncio.CancelledError:
                  logging.info(f"Task for part download cancelled for {original_filename}.")
                  # Ensure progress bar is stopped and reset on cancellation
                  self.master.after(0, self.toggle_progress, False)
                  return # Exit if cancelled
             except Exception as e:
                  logging.error(f"An unexpected error occurred while processing completed part task: {e}")
                  download_errors.append(f"Неожиданная ошибка при обработке завершенной задачи части: {e}")
                  # Don't necessarily fail the whole reconstruction yet, just log the error

        # After all downloads are attempted, check for failures before proceeding to reconstruction
        if part_download_failures:
             self.log_message(f"[ОШИБКА] Не удалось скачать или обработать следующие части для {original_filename}: {', '.join(part_download_failures)}. Сборка невозможна.")
             logging.error(f"Failed to download or process parts for {original_filename}: {part_download_failures}. Reconstruction impossible.")
             # Do NOT clean up parts directory on failure
             self.master.after(0, self.toggle_progress, False) # Stop progress bar
             return # Stop if there were specific part failures

        if download_errors:
            # This might catch more general errors not tied to a specific part file's content
            self.log_message(f"[ОШИБКА] Произошли ошибки при скачивании или обработке частей для {original_filename}. Сборка невозможна.")
            logging.error(f"General errors occurred during part download or processing for {original_filename}. Reconstruction impossible. Errors: {download_errors}")
            # Do NOT clean up parts directory on failure
            self.master.after(0, self.toggle_progress, False) # Stop progress bar
            return


        if total_parts_expected is None or len(part_data_by_index) != total_parts_expected:
            logging.error(f"Missing parts or inconsistent total_parts for {original_filename}. Expected {total_parts_expected}, found {len(part_data_by_index)}.")
            self.log_message(f"[ОШИБКА] Отсутствуют части или несогласованное общее количество частей для файла {original_filename}. Ожидалось {total_parts_expected}, найдено {len(part_data_by_index)}. Сборка невозможна.")
            # Do NOT clean up parts directory on failure
            self.master.after(0, self.toggle_progress, False) # Stop progress bar
            return

        # Check for consecutive part indices from 0 to total_parts_expected - 1
        if not all(i in part_data_by_index for i in range(total_parts_expected)):
            missing_indices = [i for i in range(total_parts_expected) if i not in part_data_by_index]
            logging.error(f"Missing part indices for {original_filename}: {missing_indices}. Reconstruction impossible.")
            self.log_message(f"[ОШИБКА] Отсутствуют индексы частей для файла {original_filename}: {missing_indices}. Сборка невозможна.")
            # Do NOT clean up parts directory on failure
            self.master.after(0, self.toggle_progress, False) # Stop progress bar
            return


        # --- Reconstruct the original file in memory ---
        self.log_message(f"[ИНФО] Сборка файла: {original_filename}")
        logging.info(f"Reconstructing file: {original_filename}")
        reconstructed_content = b''
        # Ensure parts are processed in the correct order
        sorted_part_indices = sorted(part_data_by_index.keys())
        for index in sorted_part_indices:
            if self.cancel_flag:
                 self.log_message(f"[ИНФО] Сборка файла {original_filename} отменена во время конкатенации.")
                 logging.info(f"Reconstruction of {original_filename} cancelled during concatenation.")
                 # Ensure progress bar is stopped and reset on cancellation
                 self.master.after(0, self.toggle_progress, False)
                 return
            reconstructed_content += part_data_by_index[index]['content']

        # --- Write the reconstructed content to disk ---
        reconstructed_dir = os.path.dirname(reconstructed_file_path)

        # Offload directory creation to executor
        if not await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.path.exists(reconstructed_dir)):
             await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.makedirs(reconstructed_dir, exist_ok=True))

        try:
            # Write the reconstructed content to the file - offload to executor
            await asyncio.get_event_loop().run_in_executor(self.executor, lambda: self._write_file_content(reconstructed_file_path, reconstructed_content))

            self.log_message(f"[OK] Файл успешно собран: {original_filename}")
            logging.info(f"Successfully reconstructed file: {original_file_path_base}")

            # --- Cleanup Part Files and Directory after successful reconstruction ---
            asyncio.create_task(self.cleanup_parts_directory(download_dir, original_file_path_base, force_cleanup=True)) # Force cleanup on success
            self.master.after(0, self.toggle_progress, False) # Stop progress bar on success

        except IOError as e:
            logging.error(f"IOError writing reconstructed file {original_filename}: {e}")
            self.log_message(f"[ОШИБКА] Ошибка ввода/вывода при записи собранного файла {original_filename}: {e}")
            # Clean up potentially created partial file - offload to executor
            if await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.path.exists(reconstructed_file_path)):
                await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.remove(reconstructed_file_path))
                logging.info(f"Cleaned up partial reconstructed file: {reconstructed_file_path}")
            # Do NOT clean up parts directory on write failure
            self.master.after(0, self.toggle_progress, False) # Stop progress bar
            return
        except Exception as e:
            logging.error(f"Unexpected error writing reconstructed file {original_filename}: {e}")
            self.log_message(f"[ОШИБКА] Неожиданная ошибка при записи собранного файла {original_filename}: {e}")
            # Clean up potentially created partial file - offload to executor
            if await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.path.exists(reconstructed_file_path)):
                 await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.remove(reconstructed_file_path))
                 logging.info(f"Cleaned up partial reconstructed file: {reconstructed_file_path}")
            # Do NOT clean up parts directory on write failure
            self.master.after(0, self.toggle_progress, False) # Stop progress bar
            return


    async def cleanup_parts_directory(self, download_dir, original_file_path_base, force_cleanup=False):
        """
        Cleans up part files and the .parts directory.
        Offloaded to executor as it involves synchronous file operations.
        Only cleans up if force_cleanup is True or if reconstruction was successful.
        """
        # Only proceed with cleanup if explicitly forced (e.g., after successful reconstruction
        # or skipping due to existing file with overwrite disabled) or if reconstruction was successful.
        # The check for successful reconstruction is implicitly handled by where this function is called.
        if not force_cleanup and not self.cancel_flag: # Add check for cancel flag
             logging.info(f"Cleanup of parts directory for {original_file_path_base} skipped (not forced and not cancelled).")
             return

        try:
            # Find the .parts directory relative to the download_dir and original file base path
            parts_dir_relative = original_file_path_base + ".parts"
            parts_dir_full_path = os.path.join(download_dir, parts_dir_relative)

            # Check if the parts directory exists before attempting to list/remove files - offload to executor
            if await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.path.exists(parts_dir_full_path)):
                 # List files in the parts directory - offload to executor
                 part_filenames_in_dir = await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.listdir(parts_dir_full_path))
                 for part_filename in part_filenames_in_dir:
                      if self.cancel_flag:
                          self.log_message(f"[ИНФО] Очистка директории частей {parts_dir_full_path} отменена.")
                          logging.info(f"Cleanup of parts directory {parts_dir_full_path} cancelled.")
                          return # Exit cleanup if cancelled
                      # Only remove files that look like parts of the original file
                      if part_filename.endswith(".txt") and part_filename.startswith(os.path.basename(original_file_path_base) + ".part"):
                           part_path = os.path.join(parts_dir_full_path, part_filename)
                           try:
                               # Remove the part file - offload to executor
                               await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.remove(part_path))
                               logging.info(f"Cleaned up part file: {part_path}")
                           except OSError as e:
                               logging.error(f"Error cleaning up part file {part_path}: {e}")
                               self.log_message(f"[ОШИБКА] Ошибка при очистке файла части {part_path}: {e}")
            else:
                logging.warning(f"Parts directory not found during cleanup: {parts_dir_full_path}")
                self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Директория частей не найдена при очистке: {parts_dir_full_path}")


            # Remove the .parts directory if it's empty after removing part files - offload checks and removal to executor
            if await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.path.exists(parts_dir_full_path) and not os.listdir(parts_dir_full_path)):
                try:
                    await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.rmdir(parts_dir_full_path))
                    logging.info(f"Cleaned up empty parts directory: {parts_dir_full_path}")
                except OSError as e:
                    logging.error(f"Error cleaning up empty parts directory {parts_dir_full_path}: {e}")
                    self.log_message(f"[ОШИБКА] Ошибка при очистке пустой директории частей {parts_dir_full_path}: {e}")
            # Check if directory still exists and is not empty - offload to executor
            elif await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.path.exists(parts_dir_full_path)):
                logging.warning(f"Parts directory not empty, skipping directory cleanup: {parts_dir_full_path}")
                self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Директория частей не пуста, пропуск очистки директории: {parts_dir_full_path}")

        except Exception as e:
            logging.error(f"Error during cleanup of part files or directory for {original_file_path_base}: {e}")
            self.log_message(f"[ОШИБКА] Ошибка при очистке файлов частей или директории для {original_file_path_base}: {e}")


    async def download_single_part_content(self, session, part_repo_path, original_file_path_base):
        """
        Asynchronously downloads the content of a single part file using aiohttp.
        Returns a dict with metadata and decoded content, or a dict with an 'error' key on failure.
        Includes original_filename for better logging context.
        Implements retry logic and content validation.
        Uses the passed aiohttp session.
        """
        if self.cancel_flag:
            logging.info(f"Download of part {os.path.basename(part_repo_path)} cancelled.")
            return None

        repo_owner, repo_name = self.repo_name.split('/')  # Get repo info from main app
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{quote(part_repo_path)}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        # Use the session's timeout, which is set during session creation

        part_file_name = os.path.basename(part_repo_path)
        original_filename = os.path.basename(original_file_path_base)

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            if self.cancel_flag:
                logging.info(f"Download of part {part_file_name} cancelled during retry loop.")
                return None
            try:
                logging.info(f"Downloading content for part file: {part_file_name} (Original: {original_filename}), attempt {attempt + 1}/{max_retries}")
                async with session.get(url, headers=headers) as response: # Use session's timeout
                    response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
                    content_data = await response.json()

                    if content_data.get('type') == 'file':
                        encoded_content_text = content_data.get('content')

                        # --- Added check for missing or empty content ---
                        if not encoded_content_text:
                             logging.warning(f"Part file {part_file_name} (Original: {original_filename}) has no encoded content or content is empty.")
                             self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Файл части {part_file_name} (Оригинал: {original_filename}) пуст или не содержит закодированного содержимого.")
                             # Return an error dictionary for empty content
                             return {'error': f"[ПРЕДУПРЕЖДЕНИЕ] Файл части {part_file_name} (Оригинал: {original_filename}) пуст или не содержит закодированного содержимого."}
                        # --- End of added check ---

                        # Decode the Base64 content of the .txt part file - offload to executor
                        try:
                            decoded_part_text = await asyncio.get_event_loop().run_in_executor(
                                 self.executor,
                                 lambda: base64.b64decode(encoded_content_text).decode('utf-8', errors='replace') # Use 'replace' for potentially invalid bytes
                            )
                        except Exception as e:
                            logging.error(f"Error decoding Base64 content in part file {part_file_name} (Original: {original_filename}): {e}")
                            self.log_message(f"[ОШИБКА] Ошибка декодирования Base64 в файле части {part_file_name} (Оригинал: {original_filename}): {e}")
                            continue # Retry download if decoding fails

                        # Parse metadata and extract binary content
                        metadata = {}
                        binary_content = b''
                        metadata_match = re.match(r"METADATA:(.*)\n", decoded_part_text)
                        if metadata_match:
                            try:
                                metadata_string = metadata_match.group(1)
                                # JSON decoding is CPU-bound, offload to executor
                                metadata = await asyncio.get_event_loop().run_in_executor(
                                     self.executor,
                                     lambda: json.loads(metadata_string)
                                )

                                # Find the start of the CONTENT: section
                                content_start_match = re.search(r"CONTENT:\n", decoded_part_text)
                                if content_start_match:
                                    base64_data = decoded_part_text[content_start_match.end():]
                                    try:
                                        # Base64 decoding binary content is CPU-bound, offload to executor
                                        binary_content = await asyncio.get_event_loop().run_in_executor(
                                             self.executor,
                                             lambda: base64.b64decode(base64_data)
                                        )
                                    except Exception as e:
                                        logging.error(f"Error decoding Base64 binary content in part file {part_file_name} (Original: {original_filename}): {e}")
                                        self.log_message(f"[ОШИБКА] Ошибка декодирования бинарного Base64 в файле части {part_file_name} (Оригинал: {original_filename}): {e}")
                                        continue # Retry download if decoding fails

                                else:
                                    logging.warning(f"CONTENT: section not found in part file {part_file_name} (Original: {original_filename})")
                                    self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Секция CONTENT: не найдена в файле части {part_file_name} (Оригинал: {original_filename}).")
                                    continue # Treat as a potentially recoverable issue, retry

                            except json.JSONDecodeError:
                                logging.warning(f"Failed to decode JSON metadata in part file {part_file_name} (Original: {original_filename}). Content: {metadata_string[:200]}...")
                                self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Не удалось декодировать метаданные JSON в файле части {part_file_name} (Оригинал: {original_filename}).")
                                continue # Retry download if metadata is corrupted
                            except Exception as e:
                                logging.error(f"Error processing metadata or content in part file {part_file_name} (Original: {original_filename}): {e}")
                                self.log_message(f"[ОШИБКА] Ошибка обработки метаданных/содержимого в файле части {part_file_name} (Оригинал: {original_filename}): {e}.")
                                continue # Retry download for other processing errors
                        else:
                            logging.warning(f"METADATA: section not found in part file {part_file_name} (Original: {original_filename}).")
                            self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Секция METADATA: не найдена в файле части {part_file_name} (Оригинал: {original_filename}).")
                            continue # Treat as a potentially recoverable issue, retry

                        # Extract part_index from metadata or filename if not in metadata
                        part_index = metadata.get("part_index")
                        if part_index is None:
                             # Attempt to extract from filename if not in metadata
                            match = re.search(r"\.part(\d+)\.txt$", part_file_name)
                            if match:
                                try:
                                    part_index = int(match.group(1))
                                    metadata['part_index'] = part_index # Add to metadata for consistency
                                except ValueError:
                                    logging.warning(f"Could not parse part index from filename {part_file_name} (Original: {original_filename}).")
                                    self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Не удалось разобрать индекс части из имени файла {part_file_name} (Оригинал: {original_filename}).")
                                    continue # Treat as a potentially recoverable issue, retry
                            else:
                                logging.warning(f"Part index not found in metadata or filename for {part_file_name} (Original: {original_filename}).")
                                self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Индекс части не найден в метаданных или имени файла для {part_file_name} (Оригинал: {original_filename}).")
                                continue # Treat as a potentially recoverable issue, retry

                        total_parts = metadata.get("total_parts")
                        if total_parts is None:
                            logging.warning(f"Total parts not found in metadata for {part_file_name} (Original: {original_filename}).")
                            self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Общее количество частей не найдено в метаданных для {part_file_name} (Оригинал: {original_filename}).")
                            # Decide if this should be a fatal error or attempt reconstruction without this info (risky)
                            # For now, let's treat it as a recoverable issue, retry
                            continue

                        # Check if decoded binary content is unexpectedly empty for a part that should have content
                        if not binary_content and (total_parts is None or total_parts > 0):
                             logging.warning(f"Decoded binary content is empty for part file {part_file_name} (Original: {original_filename}).")
                             self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Декодированное бинарное содержимое пустое для файла части {part_file_name} (Оригинал: {original_filename}).")
                             # Consider retrying or marking as a failed part
                             continue # Retry download

                        # Successful download and processing
                        return {
                            'part_filename': part_file_name,
                            'part_repo_path': part_repo_path, # Keep repo path for easier handling
                            'part_index': part_index,
                            'total_parts': total_parts,
                            'metadata': metadata, # Keep full metadata just in case
                            'content': binary_content
                        }
                    else:
                        logging.warning(f"Item {part_file_name} is not a file on GitHub.")
                        self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Элемент {part_file_name} на GitHub не является файлом.")
                        return {'error': f"[ПРЕДУПРЕЖДЕНИЕ] Элемент {part_file_name} на GitHub не является файлом."}

            except aiohttp.ClientResponseError as e:
                logging.error(f"HTTP error downloading part file {part_file_name} (Original: {original_filename}), attempt {attempt + 1}/{max_retries}: {e.status} - {e.message}")
                self.log_message(f"[ОШИБКА] Ошибка HTTP при скачивании части {part_file_name} (Оригинал: {original_filename}), попытка {attempt + 1}/{max_retries}: {e.status} - {e.message}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    # Return an error dictionary after retries are exhausted
                    return {'error': f"[ОШИБКА] Не удалось скачать часть {part_file_name} (Оригинал: {original_filename}) после {max_retries} попыток: {e.status} - {e.message}"}
            except aiohttp.ClientError as e:
                logging.error(f"Network error downloading part file {part_file_name} (Original: {original_filename}), attempt {attempt + 1}/{max_retries}: {e}")
                self.log_message(f"[ОШИБКА] Сетевая ошибка при скачивании части {part_file_name} (Оригинал: {original_filename}), попытка {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    # Return an error dictionary after retries are exhausted
                    return {'error': f"[ОШИБКА] Не удалось скачать часть {part_file_name} (Оригинал: {original_filename}) после {max_retries} попыток: {e}"}
            except Exception as e:
                logging.error(f"Unexpected error downloading part file {part_file_name} (Original: {original_filename}), attempt {attempt + 1}/{max_retries}: {e}")
                self.log_message(f"[ОШИБКА] Неожиданная ошибка при скачивании части {part_file_name} (Оригинал: {original_filename}), попытка {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    # Return an error dictionary after retries are exhausted
                    return {'error': f"[ОШИБКА] Не удалось скачать часть {part_file_name} (Оригинал: {original_filename}) после всех попыток."}

        # This part should ideally not be reached if retries are handled, but as a safeguard
        logging.error(f"Download of part file {part_file_name} (Original: {original_filename}) failed after all retries.")
        return {'error': f"[ОШИБКА] Скачивание части {part_file_name} (Оригинал: {original_filename}) не удалось после всех попыток."}