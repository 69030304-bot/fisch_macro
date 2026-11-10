"""
service.py - ตรรกะของระบบ (business logic) ทั้งหมดอยู่ที่นี่

main.py (FastAPI) แค่รับคำขอ HTTP แล้วเรียกฟังก์ชันในไฟล์นี้
แยกแบบนี้เพื่อให้ทดสอบ (test_service.py) ได้โดยไม่ต้องเปิดเซิร์ฟเวอร์

Refactored in Phase 5 to use Repository Pattern via data layer.
Maintains 100% backward compatibility for all API routes and return contracts.
"""
import re
import secrets
import sqlite3
import string
import time
from datetime import date, datetime, timedelta, timezone

import database
import security
from data.repositories import LogRepository, SessionRepository, UserRepository
from database import db

TZ = timezone(timedelta(hours=7))          # เวลาไทย (UTC+7)

USER_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,20}$")
MIN_PW, MAX_PW = 6, 128
SESSION_TTL = 12 * 3600                    # token ใช้ได้ 12 ชั่วโมง
MAX_FAILS, LOCK_SECS = 5, 60               # ล็อกอินผิดครบ 5 ครั้ง ล็อก 60 วินาที
RESET_MAX_FAILS, RESET_LOCK_SECS = 5, 300  # ยืนยันตัวตนตอนลืมรหัสผิดครบ 5 ครั้ง ล็อก 5 นาที

# หัวตาราง Google Sheet (ไม่มีรหัสผ่าน/แฮช เพราะไม่ควรส่งออกไปไหน)
SHEET_HEADERS = ["ID", "ชื่อผู้ใช้", "ชื่อเล่น", "วันเกิด", "สิทธิ์", "สถานะ", "สมัครเมื่อ", "ล็อกอินล่าสุด"]
SHEET_TEXT_COLUMNS = [3, 4, 7, 8]          # คอลัมน์ (เริ่มนับที่ 1) ที่ให้เก็บเป็นข้อความ ไม่ให้ Sheets แปลงเอง

# Repositories
user_repo = UserRepository()
session_repo = SessionRepository()
log_repo = LogRepository()


class ApiError(Exception):
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status
        self.detail = detail


# ---- hook: บอกว่า "ข้อมูลผู้ใช้เปลี่ยนแล้ว" (main.py จะเอาไปต่อกับการซิงค์ Google Sheet)
_change_hook = None


def set_change_hook(fn):
    global _change_hook
    _change_hook = fn


def _changed():
    if _change_hook:
        try:
            _change_hook()
        except Exception:
            pass


# ---- ตัวตรวจข้อมูลขาเข้า (validate) ไม่เชื่อข้อมูลที่ส่งมาจากผู้ใช้
def _clean_username(username):
    username = (username or "").strip()
    if not USER_RE.match(username):
        raise ApiError(400, "ชื่อผู้ใช้ต้องเป็น a-z 0-9 _ . - ยาว 3-20 ตัว")
    return username


def _check_password(password):
    if not isinstance(password, str) or len(password) < MIN_PW:
        raise ApiError(400, f"รหัสผ่านต้องยาวอย่างน้อย {MIN_PW} ตัวอักษร")
    if len(password) > MAX_PW:
        raise ApiError(400, "รหัสผ่านยาวเกินไป")


def _clean_nickname(nickname):
    nickname = (nickname or "").strip()
    if not 1 <= len(nickname) <= 30:
        raise ApiError(400, "ชื่อเล่น/ชื่อ ต้องยาว 1-30 ตัวอักษร")
    return nickname


def parse_birthday(text):
    """รับ 'YYYY-MM-DD' คืนสตริงรูปแบบเดิมที่ตรวจแล้ว"""
    try:
        d = datetime.strptime((text or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ApiError(400, "วันเกิดไม่ถูกต้อง (ต้องเป็นรูปแบบ YYYY-MM-DD)") from None
    if d > date.today() or d.year < 1900:
        raise ApiError(400, "วันเกิดไม่ถูกต้อง")
    return d.isoformat()


def _fmt(ts):
    return "" if not ts else datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d %H:%M:%S")


def _log(c, username, ok, ip, now):
    log_repo.log(username, ok, ip, now, conn=c)


# ================================================================ สมัคร / ล็อกอิน
def register(username, password, nickname, birthday):
    username = _clean_username(username)
    _check_password(password)
    nickname = _clean_nickname(nickname)
    birthday = parse_birthday(birthday)
    pw_hash = security.hash_password(password)       # เก็บแฮช ไม่เก็บรหัสจริง
    taken, new_id = False, None
    with db() as c:
        first = user_repo.count(conn=c) == 0
        role = "admin" if first else "user"          # คนแรกที่สมัครเป็นผู้ดูแล
        try:
            new_id = user_repo.create(username, pw_hash, nickname, birthday, role, time.time(), conn=c)
        except sqlite3.IntegrityError:               # ชนกับ UNIQUE ของ username
            taken = True
    if taken:
        raise ApiError(409, "มีชื่อผู้ใช้นี้อยู่แล้ว")
    _changed()
    return {"id": new_id, "username": username, "role": role}


def login(username, password, ip=""):
    username = (username or "").strip()
    password = password or ""
    now = time.time()
    outcome, result = None, None
    with db() as c:
        u = user_repo.get_by_username(username, conn=c)
        if u is None:
            security.verify_password(password, security.DUMMY_HASH)
            _log(c, username, False, ip, now)
            outcome = (401, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
        elif u.locked_until > now:
            outcome = (429, f"ลองผิดหลายครั้ง กรุณารออีก {int(u.locked_until - now) + 1} วินาที")
        elif not security.verify_password(password, u.password_hash):
            fails = u.failed_count + 1
            if fails >= MAX_FAILS:
                user_repo.lock_user(u.id, now + LOCK_SECS, conn=c)
                outcome = (429, f"ผิดครบ {MAX_FAILS} ครั้ง ล็อก {LOCK_SECS} วินาที")
            else:
                user_repo.set_failed_count(u.id, fails, conn=c)
                outcome = (401, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
            _log(c, username, False, ip, now)
        elif not u.active:
            _log(c, username, False, ip, now)
            outcome = (403, "บัญชีนี้ถูกระงับการใช้งาน")
        else:
            token = security.new_token()
            user_repo.record_login_success(u.id, now, conn=c)
            session_repo.delete_expired(now, conn=c)      # ล้าง token ที่หมดอายุ
            session_repo.create(security.hash_token(token), u.id, now + SESSION_TTL, now, conn=c)
            _log(c, username, True, ip, now)
            result = {"token": token, "id": u.id, "username": u.username,
                      "nickname": u.nickname, "role": u.role, "expires_in": SESSION_TTL}
    if outcome:                      # raise หลังออกจาก with เพื่อให้ commit (นับครั้งที่ผิด) ไปก่อน
        raise ApiError(*outcome)
    _changed()
    return result


def current_user(token):
    """ตรวจ token -> คืนข้อมูลผู้ใช้ ถ้าไม่ผ่านจะ raise 401/403"""
    now = time.time()
    with db() as c:
        row = session_repo.get_session_with_user(security.hash_token(token), conn=c)
    if row is None or row["expires_at"] < now:
        raise ApiError(401, "เซสชันหมดอายุหรือบัญชีถูกลบ กรุณาล็อกอินใหม่")
    if not row["active"]:
        raise ApiError(403, "บัญชีนี้ถูกระงับการใช้งาน")
    return {"id": row["id"], "username": row["username"], "nickname": row["nickname"],
            "birthday": row["birthday"], "role": row["role"]}


def logout(token):
    with db() as c:
        session_repo.delete(security.hash_token(token), conn=c)


# ================================================================ เปลี่ยน / ลืม / รีเซ็ตรหัสผ่าน
def change_password(user_id, token, old_password, new_password):
    _check_password(new_password)
    wrong = False
    with db() as c:
        u = user_repo.get_by_id(user_id, conn=c)
        if u is None or not security.verify_password(old_password or "", u.password_hash):
            wrong = True
        else:
            user_repo.update_password(user_id, security.hash_password(new_password), conn=c)
            # ออกจากระบบทุกเครื่องอื่น เหลือเฉพาะเครื่องที่กำลังใช้
            session_repo.delete_other_user_sessions(user_id, security.hash_token(token), conn=c)
    if wrong:
        raise ApiError(400, "รหัสผ่านเดิมไม่ถูกต้อง")
    return {"ok": True}


def reset_password(username, birthday, nickname, new_password):
    """ลืมรหัสผ่าน: ยืนยันตัวตนด้วย ชื่อเล่น + วันเกิด (และชื่อผู้ใช้ถ้าจำได้) ผิดครบ 5 ครั้งล็อก 5 นาที"""
    username = (username or "").strip()
    _check_password(new_password)
    birthday = parse_birthday(birthday)
    clean_nick = (nickname or "").strip().lower()
    if not clean_nick:
        raise ApiError(400, "กรุณากรอกชื่อเล่น")
    new_hash = security.hash_password(new_password)
    now = time.time()
    outcome = None
    generic = (400, "ข้อมูลไม่ตรงกับที่ลงทะเบียนไว้")      # ข้อความเดียวกันทุกกรณี ไม่บอกว่าผิดช่องไหน
    with db() as c:
        if username:
            u = user_repo.get_by_username(username, conn=c)
        else:
            matches = user_repo.find_by_nickname_and_birthday(clean_nick, birthday, conn=c)
            if len(matches) > 1:
                outcome = (400, "พบผู้ใช้ที่มีชื่อเล่นและวันเกิดซ้ำกันหลายคน กรุณาระบุชื่อผู้ใช้ด้วย")
                u = None
            elif len(matches) == 1:
                u = matches[0]
            else:
                u = None

        if outcome:
            pass
        elif u is None:
            outcome = generic
        elif u.reset_locked_until > now:
            outcome = (429, f"ลองผิดหลายครั้ง กรุณารออีก {int(u.reset_locked_until - now) + 1} วินาที")
        elif u.birthday != birthday or u.nickname.strip().lower() != clean_nick:
            fails = u.reset_failed_count + 1
            if fails >= RESET_MAX_FAILS:
                user_repo.lock_reset(u.id, now + RESET_LOCK_SECS, conn=c)
                outcome = (429, f"ผิดครบ {RESET_MAX_FAILS} ครั้ง ล็อก {RESET_LOCK_SECS // 60} นาที")
            else:
                user_repo.set_reset_failed_count(u.id, fails, conn=c)
                outcome = (400, f"ข้อมูลไม่ตรงกับที่ลงทะเบียนไว้ ({fails}/{RESET_MAX_FAILS})")
        else:
            user_repo.reset_password_success(u.id, new_hash, conn=c)
            session_repo.delete_all_for_user(u.id, conn=c)     # ออกจากระบบทุกเครื่อง
    if outcome:
        raise ApiError(*outcome)
    return {"ok": True}


def _random_password(n=8):
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"      # ตัดตัวที่สับสน (l, 1, O, 0)
    return "".join(secrets.choice(alphabet) for _ in range(n))


# ================================================================ ฝั่งผู้ดูแล (admin)
def list_users():
    with db() as c:
        users = user_repo.list_all(conn=c)
    return [{"id": u.id, "username": u.username, "nickname": u.nickname,
             "birthday": u.birthday, "role": u.role, "active": bool(u.active),
             "created_at": _fmt(u.created_at), "last_login": _fmt(u.last_login)} for u in users]


def set_active(admin_id, user_id, active):
    if user_id == admin_id and not active:
        raise ApiError(400, "ระงับบัญชีตัวเองไม่ได้")
    with db() as c:
        found = user_repo.set_active(user_id, active, conn=c)
    if not found:
        raise ApiError(404, "ไม่พบผู้ใช้")
    _changed()
    return {"ok": True}


def delete_user(admin_id, user_id):
    if user_id == admin_id:
        raise ApiError(400, "ลบบัญชีตัวเองไม่ได้")
    with db() as c:
        found = user_repo.delete(user_id, conn=c)   # sessions ถูกลบตามด้วย CASCADE
    if not found:
        raise ApiError(404, "ไม่พบผู้ใช้")
    _changed()
    return {"ok": True}


def admin_reset_password(user_id, new_password=""):
    """ผู้ดูแลรีเซ็ตรหัสให้ผู้ใช้ ถ้าไม่ระบุรหัสใหม่ จะสุ่มให้ แล้วคืนรหัสใหม่กลับไปให้ผู้ดูแลแจ้งผู้ใช้"""
    new_password = (new_password or "").strip()
    if new_password:
        _check_password(new_password)
    else:
        new_password = _random_password()
    new_hash = security.hash_password(new_password)
    with db() as c:
        found = user_repo.admin_reset_password(user_id, new_hash, conn=c)
        if found:
            session_repo.delete_all_for_user(user_id, conn=c)
    if not found:
        raise ApiError(404, "ไม่พบผู้ใช้")
    return {"new_password": new_password}


def export_users_rows():
    """ข้อมูลสำหรับ Google Sheet: ไม่รวมรหัสผ่าน/แฮช/token"""
    rows = []
    for u in list_users():
        rows.append([u["id"], u["username"], u["nickname"], u["birthday"], u["role"],
                     "ใช้งาน" if u["active"] else "ระงับ", u["created_at"], u["last_login"]])
    return SHEET_HEADERS, rows
