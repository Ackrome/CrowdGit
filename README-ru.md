🧠 CrowdGit: Инструмент для Синхронизации и Управления Учебными Материалами

[![GitHub stars](https://img.shields.io/github/stars/Ackrome/CrowdGit?style=for-the-badge)](https://github.com/Ackrome/CrowdGit/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/Ackrome/CrowdGit?style=for-the-badge)](https://github.com/Ackrome/CrowdGit/issues)
[![MIT License](https://img.shields.io/github/license/Ackrome/CrowdGit?style=for-the-badge)](https://github.com/Ackrome/CrowdGit/blob/main/LICENSE)

---

## 📚 Оглавление

1. Описание проекта
2. Основные возможности
3. Технологии
4. Как начать использовать
5. Авторы
6. Полезные ссылки

## 📌 Описание Проекта

---

CrowdGit — это **интуитивно понятное приложение** для студентов и преподавателей, которое автоматизирует:

- 🔄 Синхронизацию учебных материалов с GitHub
- 🗂️ Управление локальной структурой файлов
- 💾 Работу с большими файлами (до 15 ГБ)

> Поддерживает автоматическое разбиение файлов, сборку частей и кэширование для ускорения работы (https://docs.github.com/en/collaboration/sharing-projects-on-github/about-readmes)

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

## 🚀 Как Начать Использовать

👉 [Документация по настройке](https://github.com/Ackrome/CrowdGit/wiki)

## 👥 Авторы

- [**ackrome**](https://github.com/ackrome) — UI/UX и документация
- [**kvdep**](https://github.com/kvdep) — ядро приложения и тестирование

## 📎 Полезные Ссылки

- 📂 [Репозиторий проекта](https://github.com/Ackrome/CrowdGit)
- 📬 [Создать issue](https://github.com/Ackrome/CrowdGit/issues/new)
- 🧪 [Планы по развитию](https://github.com/Ackrome/CrowdGit/projects)

---

## 📜 Лицензия

MIT License © 2025 Ackrome

---

> 💡 *"CrowdGit помогает сосредоточиться на обучении, а не на рутине управления файлами."*
