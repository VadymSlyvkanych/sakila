"""
config.py — конфигурация проекта: подключения к БД и константы.

Все настройки собраны в одном месте, чтобы при смене сервера
или параметров не нужно было искать по всему коду.
"""

from pathlib import Path
from pymongo import MongoClient
from db import MySQLDB

# =============================================================================
# MySQL — основная база данных Sakila
# =============================================================================

# MySQLDB использует паттерн Singleton — повторный вызов с теми же параметрами
# вернёт тот же объект, а не создаст новое соединение.
sakila_db = MySQLDB(
    host="your-mysql-host",       # адрес сервера MySQL
    user="your-user",             # имя пользователя
    password="your-password",     # пароль
    database="sakila",            # имя базы данных
)

# =============================================================================
# MongoDB — хранение истории поисковых запросов
# =============================================================================

MONGO_URI = (
    "mongodb://your-user:your-password@your-mongo-host/"
    "?authSource=your-auth-db"
)
MONGO_COLLECTION = "your-collection-name"

mongo_client = MongoClient(MONGO_URI)

# Коллекция для хранения поисковых запросов.
# Структура документа:
#   {
#     "query":      str,        — текст запроса (может быть пустым)
#     "genres":     list[str],  — выбранные жанры
#     "years":      list[int],  — выбранные годы
#     "created_at": datetime    — UTC время создания
#   }
searches_col = mongo_client["ich_edit"][MONGO_COLLECTION]

# =============================================================================
# Прочие константы приложения
# =============================================================================

# Варианты сортировки результатов поиска (отображение, значение)
SORT_OPTIONS: list[tuple[str, str]] = [
    ("Relevance", "relevance"),
    ("Title",     "title"),
    ("Year",      "year"),
]

# Количество результатов загружаемых за один запрос
PAGE_SIZE = 10

# Ширина тега фильтра в символах:
# len(label) + padding(1+1) + " ✕"(2) + margin-right(1) + запас(1)
TAG_WIDTH_EXTRA = 6

# Путь к файлу README — ищем рядом с текущим файлом
README_PATH = Path(__file__).parent / "README.md"
