from contextlib import contextmanager
import logging

logging.basicConfig(level=logging.INFO)


class Database:
    _instances = {}

    def __new__(cls, *args, **kwargs):
        key = (cls, tuple(sorted(kwargs.items())))
        if key not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[key] = instance
        return cls._instances[key]

    def __init__(self, **config):
        if hasattr(self, "_initialized"):
            return
        self.config = config
        self.conn = None
        self._initialized = True

    def connect(self):
        raise NotImplementedError

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    @contextmanager
    def cursor(self):
        cur = None
        try:
            if self.conn is None:
                self.connect()
            cur = self.conn.cursor()
            yield cur
            self.conn.commit()
        except Exception as e:
            logging.error(f"Database error: {e}")
            if self.conn:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                self.conn = None
            raise
        finally:
            if cur:
                cur.close()

    def query(self, sql: str, params=None):
        with self.cursor() as cur:
            cur.execute(sql, params or ())
            if sql.strip().lower().startswith("select"):
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
            return cur.rowcount


class SQLiteDB(Database):
    def connect(self):
        import sqlite3
        self.conn = sqlite3.connect(
            self.config.get("database", "test.db")
        )


class MySQLDB(Database):
    def connect(self):
        import pymysql  # uv add pymysql / uv pip install pymysql
        self.conn = pymysql.connect(
            host=self.config.get("host", "localhost"),
            user=self.config.get("user"),
            password=self.config.get("password"),
            database=self.config.get("database"),
            port=self.config.get("port", 3306)
        )


# class PostgresDB(Database):
#     def connect(self):
#         import psycopg  # uv add "psycopg[binary]" / uv pip install "psycopg[binary]"
#         self.conn = psycopg.connect(
#             host=self.config.get("host", "localhost"),
#             dbname=self.config.get("database"),
#             user=self.config.get("user"),
#             password=self.config.get("password"),
#             port=self.config.get("port", 5432)
#         )


# import json


# db = SQLiteDB(database="test.db")
# db.query("""
# CREATE TABLE IF NOT EXISTS users (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     name TEXT,
#     age INTEGER
# )
# """)
# db.query(
#     "INSERT INTO users (name, age) VALUES (?, ?)",
#     ("Albina", 4)
# )
# users = db.query("SELECT * FROM users")
# print(json.dumps(users, indent=4))
# print(Database._instances)  # -> {(<class '__main__.SQLiteDB'>, (('database', 'test.db'),)): <__main__.SQLiteDB object at 0x...>}
# db.close()


# db = MySQLDB(
#     host="localhost",
#     user="root",
#     password="password",
#     database="testdb"
# )
# db.query("""
# CREATE TABLE IF NOT EXISTS users (
#     id INT AUTO_INCREMENT PRIMARY KEY,
#     name VARCHAR(100),
#     age INT
# )
# """)
# db.query(
#     "INSERT INTO users (name, age) VALUES (%s, %s)",
#     ("Serhii", 42)
# )
# users = db.query("SELECT * FROM users")
# print(json.dumps(users, indent=4))
# db.close()


# db = PostgresDB(
#     host="localhost",
#     database="testdb",
#     user="postgres",
#     password="password"
# )
# db.query("""
# CREATE TABLE IF NOT EXISTS users (
#     id SERIAL PRIMARY KEY,
#     name TEXT,
#     age INT
# )
# """)
# db.query(
#     "INSERT INTO users (name, age) VALUES (%s, %s)",
#     ("Serhii", 42)
# )
# users = db.query("SELECT * FROM users")
# print(json.dumps(users, indent=4))
# db.close()


# Проверка Singleton
# db1 = SQLiteDB(database="test.db")
# db2 = SQLiteDB(database="test.db")
# print(db1 is db2)  # -> True
