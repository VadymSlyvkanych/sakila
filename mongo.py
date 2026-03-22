"""
mongo.py — работа с MongoDB: сохранение и чтение статистики поиска.

Все операции с MongoDB сосредоточены здесь, чтобы логика работы
с базой данных была отделена от логики UI.
"""

from datetime import datetime, timezone
from config import searches_col
from models import Filters


def save_search(filters: Filters) -> None:
    """
    Сохраняет поисковый запрос в MongoDB.

    Вызывается при каждом поиске (даже если текстовый запрос пустой,
    но выбраны жанры или годы).

    Структура сохраняемого документа:
        {
            "query":      "godfather",           # текст из строки поиска
            "genres":     ["Action", "Drama"],   # отсортированный список жанров
            "years":      [1990, 1991],          # отсортированный список годов
            "created_at": datetime(...)          # время запроса в UTC
        }
    """
    searches_col.insert_one({
        "query":      filters.search.strip(),
        "genres":     sorted(filters.genres),
        "years":      sorted(filters.years),
        "created_at": datetime.now(timezone.utc),
    })


def get_stats() -> dict:
    """
    Возвращает всю статистику поисковых запросов одним вызовом.

    Выполняет четыре MongoDB aggregation pipeline параллельно
    (в рамках одного вызова функции, последовательно).

    Возвращаемый словарь:
        {
            "total":       int,         # общее кол-во запросов
            "top_queries": list[dict],  # топ-5 текстовых запросов по частоте
            "recent":      list[dict],  # 5 последних запросов
            "top_genres":  list[dict],  # топ-5 жанров по частоте использования
            "top_years":   list[dict],  # топ-5 годов по частоте использования
        }

    Каждый элемент top_* имеет вид: {"_id": значение, "count": количество}
    Каждый элемент recent имеет вид: {"query": str, "genres": list, "years": list}

    Агрегации:
        - top_queries: $match (исключаем пустые) → $group по query → $sort → $limit
        - top_genres:  $unwind genres (разворачиваем массив) → $group → $sort → $limit
        - top_years:   $unwind years → $group → $sort → $limit
    """
    # Топ-5 текстовых запросов (пустые строки не считаем)
    top_queries = list(searches_col.aggregate([
        {"$match":  {"query": {"$ne": ""}}},
        {"$group":  {"_id": "$query", "count": {"$sum": 1}}},
        {"$sort":   {"count": -1}},
        {"$limit":  5},
    ]))

    # 5 последних запросов по времени
    recent = list(
        searches_col
        .find({}, {"query": 1, "genres": 1, "years": 1, "created_at": 1})
        .sort("created_at", -1)
        .limit(5)
    )

    # Топ-5 жанров — $unwind разворачивает массив genres в отдельные документы
    # ["Action", "Drama"] → два документа с genre="Action" и genre="Drama"
    top_genres = list(searches_col.aggregate([
        {"$unwind": "$genres"},
        {"$group":  {"_id": "$genres", "count": {"$sum": 1}}},
        {"$sort":   {"count": -1}},
        {"$limit":  5},
    ]))

    # Топ-5 годов — аналогично жанрам
    top_years = list(searches_col.aggregate([
        {"$unwind": "$years"},
        {"$group":  {"_id": "$years", "count": {"$sum": 1}}},
        {"$sort":   {"count": -1}},
        {"$limit":  5},
    ]))

    total = searches_col.count_documents({})

    return {
        "total":       total,
        "top_queries": top_queries,
        "recent":      recent,
        "top_genres":  top_genres,
        "top_years":   top_years,
    }


def clear_all() -> None:
    """Удаляет все документы из коллекции статистики."""
    searches_col.delete_many({})
