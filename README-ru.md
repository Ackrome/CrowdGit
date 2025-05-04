Спасибо за уточнение! Вот обновлённый README с якорями на английском языке для корректной работы оглавления:

# 🧠 CrowdGit: Инструмент для Синхронизации и Управления Учебными Материалами

[![GitHub stars](https://img.shields.io/github/stars/Ackrome/CrowdGit?style=for-the-badge)](https://github.com/Ackrome/CrowdGit/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/Ackrome/CrowdGit?style=for-the-badge)](https://github.com/Ackrome/CrowdGit/issues)
[![MIT License](https://img.shields.io/github/license/Ackrome/CrowdGit?style=for-the-badge)](https://github.com/Ackrome/CrowdGit/blob/main/LICENSE)

---

## 📚 Оглавление

1. [Описание проекта](#project-description)
2. [Основные возможности](#features)
3. [Технологии](#technologies)
4. [Как начать использовать](#usage)
5. [Авторы](#authors)
6. [Полезные ссылки](#links)

---

`<a id="project-description"></a>`

## 📌 Описание Проекта

CrowdGit — это **интуитивно понятное приложение** для студентов и преподавателей, которое автоматизирует:

- 🔄 Синхронизацию учебных материалов с GitHub
- 🗂️ Управление локальной структурой файлов
- 💾 Работу с большими файлами (до 15 ГБ)

> Поддерживает автоматическое разбиение файлов, сборку частей и кэширование для ускорения работы (https://docs.github.com/en/collaboration/sharing-projects-on-github/about-readmes)

`<a id="features"></a>`

## ⚙️ Основные Возможности

### 🔁 Синхронизация с GitHub

- ✅ Автоматическая загрузка изменений в репозиторий
- 🔽 Скачивание обновлений с отслеживанием прогресса
- 📦 Поддержка файлов >40 МБ через chunked upload

### 🗂️ Управление Структурой

- 📁 Автоматическое создание папок по шаблону
- 📄 Классификация файлов: лекции, семинары, ДЗ
- 🔁 Перемещение и переименование по правилам

### 📁 Работа с Файлами-Частями

- 📤 Разбиение больших файлов на части
- 📥 Сборка оригинального файла при скачивании
- 📡 Возможность загрузки отдельных частей

### 🖥️ Интерфейс

- 🌗 Темная/светлая тема
- 📊 Прогресс-бары операций
- 🧾 Детальное логирование
- ❓ Всплывающие подсказки

### 🛡️ Дополнительно

- 🧠 Сохранение профиля (токен, пути)
- 🔄 Проверка валидности токена
- 🔁 Отмена операций
- 📶 Проверка интернет-соединения

`<a id="technologies"></a>`

## 🛠️ Технологии

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&style=flat-square)
![Tkinter](https://img.shields.io/badge/Tkinter-UI-yellow?logo=python&style=flat-square)
![GitHub API](https://img.shields.io/badge/GitHub_API-REST-orange?logo=github&style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-DB-green?logo=sqlite&style=flat-square)

- **Основной язык:** Python 3.9+
- **API:** PyGithub для работы с GitHub
- **UI:** Tkinter + [sv-ttk](https://github.com/rdbende/Sun-Valley-ttk-theme)
- **Сетевые запросы:** aiohttp (асинхронные)
- **Медиа:** Pillow для обработки изображений
- **База данных:** sqlite3 для хранения метаданных

`<a id="usage"></a>`

## 🚀 Как Начать Использовать

👉 [Документация по настройке](https://github.com/Ackrome/CrowdGit/wiki)

`<a id="authors"></a>`

## 👥 Авторы

- [**ackrome**](https://github.com/ackrome) — UI/UX и документация
- [**kvdep**](https://github.com/kvdep) — ядро приложения и тестирование

`<a id="links"></a>`

## 📎 Полезные Ссылки

- 📂 [Репозиторий проекта](https://github.com/Ackrome/CrowdGit)
- 📬 [Создать issue](https://github.com/Ackrome/CrowdGit/issues/new)
- 🧪 [Планы по развитию](https://github.com/Ackrome/CrowdGit/projects)

---

## 📜 Лицензия

MIT License © 2025 Ackrome

Полная лицензия: [LICENSE](https://github.com/Ackrome/CrowdGit/blob/main/LICENSE)

---

> 💡 *"CrowdGit помогает сосредоточиться на обучении, а не на рутине управления файлами."*
