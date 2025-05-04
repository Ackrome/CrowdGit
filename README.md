# 🧠 CrowdGit: Tool for Synchronizing and Managing Educational Materials

[![GitHub stars](https://img.shields.io/github/stars/Ackrome/CrowdGit?style=for-the-badge)](https://github.com/Ackrome/CrowdGit/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/Ackrome/CrowdGit?style=for-the-badge)](https://github.com/Ackrome/CrowdGit/issues)
[![MIT License](https://img.shields.io/github/license/Ackrome/CrowdGit?style=for-the-badge)](https://github.com/Ackrome/CrowdGit/blob/main/LICENSE)

## 🌍 Choose language:

- [English README](README.md) 🇬🇧
- [Русский README](README-ru.md) 🇷🇺

---

## 📚 Table of Contents

1. Project Description
2. Main Features
3. Technologies
4. How to Use
5. Authors

---


## 📌 Project Description

CrowdGit is an intuitive **application for students and educators** designed to automate:

- 🔁 Synchronization of educational materials with GitHub
- 🗂️ Management of local file structures
- 💾 Handling large files (up to 15 GB)

> Supports automatic file splitting, reassembly of parts, and caching for faster workflows (https://devman.org/qna/git/chto-takoe-readme/).

---


## ⚙️ Main Features

### 🔁 GitHub Synchronization

- ✅ Automatic upload of changes to GitHub repositories
- 🔽 Download updates with progress tracking
- 📦 Support for files >40 MB via chunked uploads

### 🗂️ Local Structure Management

- 📁 Automated folder creation based on templates
- 📄 File classification: lectures, seminars, homework
- 🔁 Rule-based file renaming and relocation

### 📁 Partial File Handling

- 📤 Split large files into smaller chunks
- 📥 Reassemble original files during download
- 📡 Download individual chunks or full files

### 🖥️ User Interface

- 🌗 Light/dark theme toggle
- 📊 Progress bars for operations
- 🧾 Detailed logging
- ❓ Interactive tooltips

### 🛡️ Additional Features

- 🧠 Profile saving (token, paths)
- 🔄 Token validity checks
- 🔁 Cancelable operations
- 📶 Internet connection verification
- 🧠 Caching for performance optimization
- 🗄️ SQLite database for metadata storage

---


## 🛠️ Technologies Used

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&style=flat-square)
![Tkinter](https://img.shields.io/badge/Tkinter-UI-yellow?logo=python&style=flat-square)
![GitHub API](https://img.shields.io/badge/GitHub_API-REST-orange?logo=github&style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-DB-green?logo=sqlite&style=flat-square)

- **Core Language:** Python 3.9+
- **API:** [PyGithub](https://pygithub.readthedocs.io/en/latest/)
- **UI:** Tkinter + [sv-ttk](https://github.com/rdbende/Sun-Valley-ttk-theme)
- **Networking:** `aiohttp` (async requests)
- **Media:** Pillow for image processing
- **Database:** SQLite for metadata

---


## 🚀 How to Use

### 1. Profile Setup

```python
token = "your_github_token"
local_path = "/path/to/folder"
username = "your_name"
repo_name = "username/repo"
```

### 2. Create Folder Structure

```bash
Click "Create Structure" in the interface
```

### 3. Add Files

- Select files via file explorer
- Specify type: lecture/seminar/homework
- Assign task number

### 4. Synchronize

- Click "Synchronize" for two-way sync with GitHub

---

`<a id="authors"></a>`

## 👥 Authors

- [**ackrome**](https://github.com/ackrome) — UI/UX & Documentation
- [**kvdep**](https://github.com/kvdep) — Core Development & Testing

---

## 📎 Useful Links

- 📂 [Project Repository](https://github.com/Ackrome/CrowdGit)
- 📬 [Report Issues](https://github.com/Ackrome/CrowdGit/issues/new)

---

> 💡 *"CrowdGit helps you focus on learning, not file management."*
> — Inspired by [Markdown best practices](https://ru.stackoverflow.com/questions/609631/%D0%9A%D0%B0%D0%BA-%D0%BD%D0%B0%D0%BF%D0%B8%D1%81%D0%B0%D1%82%D1%8C-%D1%85%D0%BE%D1%80%D0%BE%D1%88%D0%B8%D0%B9-readme)
