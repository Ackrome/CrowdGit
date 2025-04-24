import threading
import sv_ttk
from concurrent.futures import ThreadPoolExecutor
import os
import requests
import logging
from urllib.parse import quote
import asyncio
import aiohttp
from aiohttp import ClientSession
import base64
import re
import json
import traceback
import certifi
from github import Github, GithubException
from tkinter import ttk, messagebox
import tkinter as tk
import time
import random

class FileDownloader:
    """
    A utility class for downloading files.
    Note: This class seems to be partially redundant with LoadWindow's
    async download methods, consider consolidating or clarifying its purpose.
    """
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.logger = logging.getLogger(__name__)

    def download_part_file(self, part_url, part_filename):
        """
        Synchronously downloads a single part file.
        Note: This synchronous method is not used in the asynchronous
        part file downloading/reconstruction logic in LoadWindow.
        """
        try:
            response = requests.get(part_url, stream=True)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            # Check if the response is what we expect (e.g., text/plain)
            if 'text/plain' not in response.headers.get('Content-Type', ''):
                self.logger.error(f"Error: Unexpected response type for {part_url}")
                # Handle the unexpected type appropriately, e.g., save it as is or skip
                # For now, we'll save it as is
                with open(part_filename, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                return True
            
            with open(part_filename, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            self.logger.info(f"[OK] Successfully downloaded part file: {part_url}")
            return True
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error downloading {part_url}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"An unexpected error occurred: {e}")
            return False

    def download_and_save_part(self, part_url, part_filename, target_dir):
        """
        Synchronously downloads a part file and saves it to the specified directory.
        Note: This method is not used in the asynchronous part file
        downloading/reconstruction logic in LoadWindow.
        """
        full_path = os.path.join(target_dir, part_filename)
        if self.download_part_file(part_url, full_path):
            self.logger.info(f"Saving part file to: {full_path}")
            return True
        else:
            return False


    def download_and_reconstruct(self, filename, num_parts, github_token=None):
        """
        Synchronously downloads all part files and attempts to reconstruct the original file.
        Note: This synchronous method is not used in the asynchronous
        part file downloading/reconstruction logic in LoadWindow.
        """
        all_parts_content = []
        for part_index in range(num_parts):
            part_content = self._download_part_file(filename, part_index, github_token=github_token)
            if part_content is None:
                self.logger.error(
                    f"Failed to successfully download all parts for {filename}. Reconstruction impossible."
                )
                self.logger.warning(f"Redownloading all parts for {filename} due to errors.")
                self.logger.info(f"LoadWindow: [Перезагрузка] Повторная загрузка всех частей файла {filename} из-за ошибок.")
                return None # Stop if any part fails to download
            all_parts_content.append(part_content)

        self.logger.info(f"LoadWindow: [Успех] Все части файла {filename} успешно загружены.")
        return "".join(all_parts_content)

class LoadWindow(tk.Toplevel):
    """
    A Toplevel window for browsing and downloading content from a GitHub repository.
    Handles both regular files and files split into parts.
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
        # Ensure timeout is an integer or float suitable for requests/aiohttp
        self.timeout = int(getattr(parent, 'timeout', 180)) # Default to 180 seconds if parent.timeout is not available or invalid

        self.master = master
        self.base_url = "https://api.github.com"  # Ensure base_url is set correctly
        self.repo_name = repo_name
        self.token = token
        self.parent = parent # Reference to the main application for logging
        self.file_downloader = None # Seems unused in current async flow, consider removing
        self.local_base_path = local_base_path
        self.github_repo = None
        self.cancel_flag = False  # Flag to cancel download operations

        # Use a set to keep track of original files for which parts are being downloaded
        # This prevents trying to download/reconstruct the same file multiple times
        # if multiple parts of it are selected or encountered during recursion.
        self.reconstruction_queued = set()
        self.executor = ThreadPoolExecutor(max_workers=5) # Executor for running synchronous tasks
        self.reconstruction_lock = asyncio.Lock() # Lock to prevent multiple simultaneous reconstructions of the same file

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

    def fetch_repo_tree(self, repo_path=''):
        """Recursively fetches the repository structure."""
        if self.cancel_flag:
            return []

        try:
            # Use the GitHub library for tree fetching
            contents = self.github_repo.get_contents(repo_path)
            items = []
            for content in contents:
                if self.cancel_flag:
                    return []
                item = {
                    'name': content.name,
                    'path': content.path,
                    'type': content.type,  # 'dir' or 'file'
                    'sha': content.sha if content.type == 'file' else None,
                    'children': []
                }
                if content.type == 'dir':
                    item['children'] = self.fetch_repo_tree(content.path) # Recursive call
                items.append(item)
            return items
        except GithubException as e:
            logging.error(f"GithubException fetching repo tree at {repo_path}: {e}")
            self.parent.log_message(f"[ОШИБКА] Ошибка GitHub при получении структуры репозитория: {e}")
            return []
        except Exception as e:
            logging.error(f"Unexpected error fetching repo tree at {repo_path}: {e}")
            self.parent.log_message(f"[ОШИБКА] Неожиданная ошибка при получении структуры репозитория: {e}")
            return []

    def fetch_and_display_repo_tree(self):
        """Fetches the repo tree and populates the treeview."""
        self.parent.log_message("Подключение к GitHub...")
        self.toggle_progress(True, mode="indeterminate") # Start with indeterminate mode
        self.cancel_flag = False
        # Corrected: Use lambda to pass keyword argument
        self.master.after(0, lambda: self.cancel_button.config(state=tk.NORMAL))

        try:
            g = Github(self.token)
            self.github_repo = g.get_repo(self.repo_name)
            self.parent.log_message(f"Подключено к репозиторию: {self.repo_name}")

            repo_tree_data = self.fetch_repo_tree()

            if not self.cancel_flag:
                self.populate_treeview(repo_tree_data)
                self.parent.log_message("Структура репозитория загружена.")

        except GithubException as e:
            logging.error(f"GithubException during repo connection or initial fetch: {e}")
            self.parent.log_message(f"[ОШИБКА] Ошибка GitHub: {e}")
            messagebox.showerror("Ошибка GitHub", f"Не удалось подключиться к репозиторию или получить структуру: {e}")
        except Exception as e:
            logging.error(f"Unexpected error during repo connection or initial fetch: {e}")
            self.parent.log_message(f"[ОШИБКА] Неожиданная ошибка: {e}")
            messagebox.showerror("Неизвестная ошибка", f"Произошла ошибка: {e}")

        self.toggle_progress(False)
        # Corrected: Use lambda to pass keyword argument
        self.master.after(0, lambda: self.cancel_button.config(state=tk.DISABLED))

    def populate_treeview(self, data, parent_iid=''):
        """Populates the Treeview with repository data."""
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

            # Store item data (path, sha, etc.) in the item's values or tags
            # Using tags for easier retrieval: (path, type, sha)
            self.repo_tree.item(iid, tags=(item['path'], item['type'], item.get('sha')))

            if item['type'] == 'dir' and item['children']:
                self.populate_treeview(item['children'], iid) # Recursive call

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
        # Corrected: Use lambda to pass keyword argument
        self.master.after(0, lambda: self.cancel_button.config(state=tk.NORMAL))
        self.master.after(0, lambda: self.download_button.config(state=tk.DISABLED))  # Corrected # Disable download button during download

        # Run download in a separate thread using asyncio event loop
        def run_async_download():
            asyncio.run(self.threaded_download(selected_items, download_dir))

        threading.Thread(target=run_async_download, daemon=True).start()

    async def threaded_download(self, selected_items, download_dir):
        """Handles the asynchronous download process in a thread."""
        download_tasks = []
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
                        parts_dir_iid = self.repo_tree.parent(
                            item_iid)  # Get the parent directory (the .parts folder)
                        if parts_dir_iid:
                            part_iids = self.repo_tree.get_children(parts_dir_iid)
                            part_files_info = []
                            for part_iid in part_iids:
                                part_tags = self.repo_tree.item(part_iid, 'tags')
                                if part_tags and len(part_tags) > 1 and part_tags[1] == 'file':
                                    part_file_path = part_tags[0]
                                    part_sha = part_tags[2] if len(part_tags) > 2 else None
                                    # Ensure the part file belongs to the current original file
                                    if part_file_path.startswith(
                                            original_file_path_base + ".parts/") and part_file_path.endswith(".txt"):
                                        part_files_info.append({'path': part_file_path, 'sha': part_sha})

                            if part_files_info:
                                # Create a task to download and reconstruct the original file
                                task = asyncio.create_task(
                                    self.download_and_reconstruct_parts(part_files_info, download_dir,
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
                    task = asyncio.create_task(self.download_single_file(item_path, item_sha, download_dir))
                    download_tasks.append(task)

            elif item_type == 'dir':
                # If a directory is selected, download all its contents recursively
                # We need to fetch the directory contents again to get all files/subdirs
                self.parent.log_message(f"Скачивание содержимого папки: {item_path}")
                logging.info(f"Downloading contents of directory: {item_path}")
                # Recursive download is asynchronous within the thread
                await self.download_directory_contents(item_path, download_dir)

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
        # Corrected: Use lambda to pass keyword argument
        self.master.after(0, lambda: self.cancel_button.config(state=tk.DISABLED))
        self.master.after(0, lambda: self.download_button.config(state=tk.NORMAL))  # Corrected # Re-enable download button

    async def download_single_file(self, repo_file_path, file_sha, local_base_dir, is_part=False):
        """Asynchronously downloads a single file from GitHub, handling both text and binary files."""
        if self.cancel_flag:
            self.log_message(f"[ИНФО] Загрузка файла {os.path.basename(repo_file_path)} отменена.")
            logging.info(f"Download of {repo_file_path} cancelled.")
            return

        local_file_path = os.path.join(local_base_dir, repo_file_path)
        local_dir = os.path.dirname(local_file_path)
        os.makedirs(local_dir, exist_ok=True)  # Ensure local directory exists

        # Check if file already exists locally and if overwrite is disabled
        if os.path.exists(local_file_path) and not self.overwrite_existing_var.get():
            self.log_message(f"[ИНФО] Файл уже существует локально: {os.path.basename(repo_file_path)}. Пропускаю.")
            logging.info(f"File already exists locally: {local_file_path}. Skipping download.")
            return # Skip download if file exists and overwrite is disabled

        self.log_message(f"[ИНФО] Скачивание файла: {os.path.basename(repo_file_path)}")
        logging.info(f"Downloading file: {repo_file_path}")

        try:
            # Get the raw content URL from the GitHub API
            repo_owner, repo_name = self.repo_name.split('/')
            # Using the direct raw content URL is more efficient for large files
            # Construct the raw URL based on the repository, branch (assuming default branch), and file path
            # This requires knowing the default branch, which might not be readily available from get_contents
            # A more reliable way is to use the Git Blob API with Accept: application/vnd.github.v3.raw
            # url = f"https://raw.githubusercontent.com/{repo_owner}/{repo_name}/main/{repo_file_path}" # Assuming 'main' branch

            # Using the Git Blob API with raw content accept header
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/blobs/{file_sha}"
            headers = {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3.raw"  # Request raw content
            }

            # Use requests.get in a thread-safe manner or offload to executor if needed for sync calls in async context
            # Since this is an async function using aiohttp session is preferred for true async
            # However, the current implementation uses requests, let's offload it to the executor
            response = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: requests.get(url, headers=headers, timeout=self.timeout, verify=certifi.where())
            )
            response.raise_for_status()  # Raise an exception for bad status codes

            # Write the raw content to the local file in binary mode
            with open(local_file_path, 'wb') as f:
                f.write(response.content)

            if is_part:
                self.parent.log_message(f"[OK] Скачана часть файла: {os.path.basename(repo_file_path)}")
                logging.info(f"Successfully downloaded part file: {repo_file_path}")
            else:
                self.parent.log_message(f"[OK] Скачан файл: {os.path.basename(repo_file_path)}")
                logging.info(f"Successfully downloaded file: {repo_file_path}")

        except requests.exceptions.RequestException as e:
            logging.error(f"RequestException downloading file {repo_file_path}: {e}")
            self.parent.log_message(f"[ОШИБКА] Ошибка при скачивании файла {os.path.basename(repo_file_path)}: {e}")
        except GithubException as e:
            logging.error(f"GithubException downloading file {repo_file_path}: {e}")
            self.parent.log_message(f"[ОШИБКА] Ошибка GitHub при скачивании файла {os.path.basename(repo_file_path)}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error downloading file {repo_file_path}: {e}")
            self.parent.log_message(
                f"[ОШИБКА] Неожиданная ошибка при скачивании файла {os.path.basename(repo_file_path)}: {e}")

    async def download_directory_contents(self, repo_dir_path, local_base_dir):
        """Recursively downloads contents of a directory from GitHub."""
        if self.cancel_flag:
            self.log_message(f"[ИНФО] Скачивание содержимого папки {repo_dir_path} отменено.")
            logging.info(f"Download of directory {repo_dir_path} cancelled.")
            return

        try:
            # Use the GitHub library to get directory contents
            contents = await asyncio.get_event_loop().run_in_executor(
                 self.executor,
                 lambda: self.github_repo.get_contents(repo_dir_path)
            )
            part_files_to_reconstruct = {}  # Dictionary to collect part files for reconstruction

            for content in contents:
                if self.cancel_flag:
                    self.log_message(f"[ИНФО] Скачивание содержимого папки {repo_dir_path} отменено.")
                    logging.info(f"Download of directory {repo_dir_path} cancelled.")
                    return

                local_path = os.path.join(local_base_dir, content.path)

                if content.type == 'dir':
                    # Check if it's a .parts directory
                    if content.name.endswith(".parts"):
                        logging.info(f"Scanning contents of .parts directory: {content.path}")
                        # Recursively scan the .parts directory to collect part file info
                        # We still need to traverse the tree to find all parts, but don't download content here
                        await self.download_directory_contents(content.path, local_base_dir)
                        continue  # Skip recursing into the .parts directory again for regular files
                    # Create local directory and recurse for regular directories
                    os.makedirs(local_path, exist_ok=True)
                    await self.download_directory_contents(content.path, local_base_dir)
                elif content.type == 'file':
                    # Check if it's a part file within a .parts directory
                    if ".parts/" in content.path and content.path.endswith(".txt"):
                        # Collect part files for potential reconstruction
                        original_file_path_base = content.path.rsplit('.parts/', 1)[0]
                        if original_file_path_base not in part_files_to_reconstruct:
                            part_files_to_reconstruct[original_file_path_base] = []
                        part_files_to_reconstruct[original_file_path_base].append(
                            {'path': content.path, 'sha': content.sha})
                        # IMPORTANT: DO NOT download the part file content here.
                        # It will be downloaded asynchronously by download_and_reconstruct_parts.
                        self.parent.log_message(f"[ИНФО] Найден файл части: {content.name}")
                        logging.info(f"Found part file during recursive scan: {content.path}")
                    else:
                        # It's a regular file, download it
                        await self.download_single_file(content.path, content.sha, local_base_dir)

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
                        self.download_and_reconstruct_parts(part_files_info, local_base_dir,
                                                            original_file_path_base))

        except GithubException as e:
            logging.error(f"GithubException downloading directory {repo_dir_path}: {e}")
            self.parent.log_message(f"[ОШИБКА] Ошибка GitHub при скачивании папки {repo_dir_path}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error downloading directory {repo_dir_path}: {e}")
            self.parent.log_message(f"[ОШИБКА] Неожиданная ошибка при скачивании папки {repo_dir_path}: {e}")

    def log_message(self, msg):
        """Logs a message to the status label and main app's log."""
        # Update status label in the GUI thread
        # Corrected: Use lambda to pass keyword argument
        self.master.after(0, lambda: self.status_label.config(text=msg))
        # Also log to the main application's log text widget
        if hasattr(self.master, 'log_message'):
             # Use self.master.after to ensure GUI updates happen in the main thread
             self.master.after(0, self.master.log_message, msg)
        else:
             # Fallback if main app log_message is not available
             logging.info(f"LoadWindow: {msg}")

    def toggle_progress(self, start=True, mode="indeterminate", maximum=0):
        """Toggles the progress bar and sets its mode/maximum."""
        # Ensure GUI updates happen in the main thread
        if start:
            # Corrected: Use lambda to pass keyword arguments
            self.master.after(0, lambda: self.progress_bar.config(mode=mode, maximum=maximum))
            self.master.after(0, self.progress_bar.start)
            logging.info(f"LoadWindow: Progress bar started in {mode} mode.")
        else:
            self.master.after(0, self.progress_bar.stop)
            # Corrected: Use lambda to pass keyword arguments
            self.master.after(0, lambda: self.progress_bar.config(mode="indeterminate", value=0)) # Reset after stopping
            logging.info("LoadWindow: Progress bar stopped.")

    def update_progress_value(self, value):
        """Updates the value of the determinate progress bar."""
        # Ensure GUI updates happen in the main thread
        # Corrected: Use lambda to pass keyword argument
        self.master.after(0, lambda: self.progress_bar.config(value=value))


    def cancel_download(self):
        """Sets the cancel flag to stop the download process."""
        self.cancel_flag = True
        self.parent.log_message("[ИНФО] Запрос на отмену загрузки...")
        logging.info("LoadWindow: Cancel requested.")
        # Disable cancel button in the main thread
        # Corrected: Use lambda to pass keyword argument
        self.master.after(0, lambda: self.cancel_button.config(state=tk.DISABLED))

    def set_base_url(self, url):
        """
        Extracts and sets the base URL from a given file URL.
        Note: This method seems unused in the current async download flow.
        """
        if "raw.githubusercontent.com" in url:
            parts = url.split("/")
            self.base_url = "/".join(parts[:5])
        else:
            self.base_url = "/".join(url.split("/")[:3])
        self.file_downloader = FileDownloader(base_url=self.base_url) # file_downloader seems unused
        logging.info(f"Base URL set to: {self.base_url}")

    def start_reconstruct_files(self):
        """Starts the file reconstruction process in a new thread."""
        self.parent.log_message("Начало реконструкции файлов...")
        self.toggle_progress(True, mode="indeterminate") # Start with indeterminate mode
        self.cancel_flag = False
        self.reconstruction_queued.clear()  # Clear the set before a new reconstruction process
        # Corrected: Use lambda to pass keyword argument
        self.master.after(0, lambda: self.cancel_button.config(state=tk.NORMAL))
        self.master.after(0, lambda: self.reconstruct_button.config(state=tk.DISABLED))  # Corrected # Disable button during reconstruction

        # Run reconstruction in a separate thread using asyncio event loop
        def run_async_reconstruction():
             asyncio.run(self.threaded_reconstruct_files(self.local_base_path))

        threading.Thread(target=run_async_reconstruction, daemon=True).start()


    async def threaded_reconstruct_files(self, download_dir):
        """Handles the asynchronous file reconstruction process in a thread."""
        try:
            await self.reconstruct_files_in_directory(download_dir)
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
            # Corrected: Use lambda to pass keyword argument
            self.master.after(0, lambda: self.cancel_button.config(state=tk.DISABLED))
            self.master.after(0, lambda: self.reconstruct_button.config(state=tk.NORMAL))  # Corrected # Re-enable button

    async def reconstruct_files_in_directory(self, directory):
        """
        Scans a directory for .parts directories, checks for complete part sets,
        and reconstructs the original files.
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
                        tasks.append(self.process_parts_directory(parts_dir_path, directory, original_file_path_base))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def process_parts_directory(self, parts_dir_path, directory, original_file_path_base):
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
                await self.download_and_reconstruct_parts(part_files_info, directory,
                                                          original_file_path_base)
            else:
                self.parent.log_message(
                    f"[ПРЕДУПРЕЖДЕНИЕ] Не найдено файлов частей для {original_filename} в директории {parts_dir_path}. Пропускаю.")
                logging.warning(f"No part files found for {original_filename} in directory {parts_dir_path}. Skipping reconstruction.")


    async def download_and_reconstruct_parts(self, part_files_info, download_dir, original_file_path_base):
        """
        Downloads all part files for a given original file using aiohttp,
        validates metadata, reconstructs the original file in memory,
        writes it to disk, and cleans up the part files and directory.
        """
        if self.cancel_flag:
            self.log_message(f"[ИНФО] Скачивание и сборка файла {os.path.basename(original_file_path_base)} отменены.")
            logging.info(f"Download and reconstruction of {os.path.basename(original_file_path_base)} cancelled.")
            return

        original_filename = os.path.basename(original_file_path_base)
        reconstructed_file_path = os.path.join(download_dir, original_file_path_base)

        # Check if the final reconstructed file already exists locally and if overwrite is disabled
        if os.path.exists(reconstructed_file_path) and not self.overwrite_existing_var.get():
            self.log_message(f"[ИНФО] Собранный файл уже существует локально: {original_filename}. Пропускаю сборку.")
            logging.info(f"Reconstructed file already exists locally: {reconstructed_file_path}. Skipping reconstruction.")
            # Clean up part files if the reconstructed file exists and overwrite is disabled - offload to executor
            asyncio.create_task(self.cleanup_parts_directory(download_dir, original_file_path_base, force_cleanup=True)) # Force cleanup if skipping
            return # Skip reconstruction if the final file exists

        self.log_message(f"[ИНФО] Скачивание частей для сборки файла: {original_filename}")
        logging.info(f"Downloading parts for reconstruction: {original_filename}")

        downloaded_parts = []
        download_errors = []
        total_parts_expected = None
        downloaded_part_count = 0 # Counter for downloaded parts
        part_download_failures = [] # Collect specific part download/processing errors
        part_data_by_index = {} # Initialize the dictionary before use


        # --- Download all part files asynchronously ---
        # Use a single aiohttp session for potentially multiple part downloads
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            download_tasks = []
            for part_file_info in part_files_info:
                if self.cancel_flag:
                    self.log_message(f"[ИНФО] Скачивание частей для сборки файла {original_filename} отменено.")
                    logging.info(f"Download of parts for {original_filename} cancelled.")
                    break
                part_repo_path = part_file_info['path']
                # Pass original_file_path_base for better logging context in download_single_part_content
                task = asyncio.create_task(self.download_single_part_content(session, part_repo_path, original_file_path_base))
                download_tasks.append(task)

            # Set progress bar to determinate mode and set maximum
            total_parts_in_list = len(part_files_info)
            # Corrected: Use lambda to pass keyword arguments
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
        os.makedirs(reconstructed_dir, exist_ok=True)

        try:
            # Code starting at line 894 in the previous version
            with open(reconstructed_file_path, 'wb') as f:
                f.write(reconstructed_content)
            self.log_message(f"[OK] Файл успешно собран: {original_filename}")
            logging.info(f"Successfully reconstructed file: {original_file_path_base}")

            # --- Cleanup Part Files and Directory after successful reconstruction ---
            asyncio.create_task(self.cleanup_parts_directory(download_dir, original_file_path_base, force_cleanup=True)) # Force cleanup on success
            self.master.after(0, self.toggle_progress, False) # Stop progress bar on success

        except IOError as e:
            logging.error(f"IOError writing reconstructed file {original_filename}: {e}")
            self.log_message(f"[ОШИБКА] Ошибка ввода/вывода при записи собранного файла {original_filename}: {e}")
            # Clean up potentially created partial file - offload to executor
            if os.path.exists(reconstructed_file_path):
                asyncio.create_task(asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.remove(reconstructed_file_path)))
                logging.info(f"Cleaned up partial reconstructed file: {reconstructed_file_path}")
            # Do NOT clean up parts directory on write failure
            self.master.after(0, self.toggle_progress, False) # Stop progress bar
            return
        except Exception as e:
            logging.error(f"Unexpected error writing reconstructed file {original_filename}: {e}")
            self.log_message(f"[ОШИБКА] Неожиданная ошибка при записи собранного файла {original_filename}: {e}")
            # Clean up potentially created partial file - offload to executor
            if os.path.exists(reconstructed_file_path):
                 asyncio.create_task(asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.remove(reconstructed_file_path)))
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

            # Check if the parts directory exists before attempting to list/remove files
            if await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.path.exists(parts_dir_full_path)):
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
                               await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.remove(part_path))
                               logging.info(f"Cleaned up part file: {part_path}")
                           except OSError as e:
                               logging.error(f"Error cleaning up part file {part_path}: {e}")
                               self.log_message(f"[ОШИБКА] Ошибка при очистке файла части {part_path}: {e}")
            else:
                logging.warning(f"Parts directory not found during cleanup: {parts_dir_full_path}")
                self.log_message(f"[ПРЕДУПРЕЖДЕНИЕ] Директория частей не найдена при очистке: {parts_dir_full_path}")


            # Remove the .parts directory if it's empty after removing part files
            if await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.path.exists(parts_dir_full_path) and not os.listdir(parts_dir_full_path)):
                try:
                    await asyncio.get_event_loop().run_in_executor(self.executor, lambda: os.rmdir(parts_dir_full_path))
                    logging.info(f"Cleaned up empty parts directory: {parts_dir_full_path}")
                except OSError as e:
                    logging.error(f"Error cleaning up empty parts directory {parts_dir_full_path}: {e}")
                    self.log_message(f"[ОШИБКА] Ошибка при очистке пустой директории частей {parts_dir_full_path}: {e}")
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
        """
        if self.cancel_flag:
            logging.info(f"Download of part {os.path.basename(part_repo_path)} cancelled.")
            return None

        repo_owner, repo_name = self.repo_name.split('/')  # Get repo info from main app
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{part_repo_path}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        # Use the session's timeout
        timeout = aiohttp.ClientTimeout(total=self.timeout)

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

                        # Decode the Base64 content of the .txt part file
                        try:
                            # Decoding Base64 is CPU-bound, offload to executor
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
                        # self.log_message(f"[OK] Скачана часть {part_file_name} для {original_filename}") # Log successful part download - moved to download_and_reconstruct_parts for progress update
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
