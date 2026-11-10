"""
database.py - เชื่อมต่อและสร้างตารางฐานข้อมูล (SQLite)

SQLite = ฐานข้อมูลที่เก็บเป็นไฟล์เดียว (app.db) ไม่ต้องติดตั้งเซิร์ฟเวอร์ฐานข้อมูลเพิ่ม
เหมาะกับโปรเจกต์เรียนรู้ ภาษา SQL ที่ใช้ตรงนี้ใช้ได้เกือบเหมือนกันกับ MySQL / PostgreSQL
เปิดดูข้อมูลในไฟล์ app.db ได้ด้วยโปรแกรมฟรี "DB Browser for SQLite"

Modular refactored implementation delegates to data.database package.
Preserves 100% backward compatibility for all existing scripts and tests.
"""
import os
import sqlite3
from contextlib import contextmanager

from data.database import (
    DatabaseManager,
    SCHEMA,
    db as _data_db,
    default_manager,
    get_default_db_path,
    init_db as _data_init_db,
)

DB_PATH = get_default_db_path()


@contextmanager
def db():
    """ใช้แบบ  with db() as c:  -> ถ้าจบปกติ commit ให้เอง ถ้า error จะ rollback"""
    with _data_db() as conn:
        yield conn


def init_db():
    _data_init_db()
