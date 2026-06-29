import hashlib
import sqlite3
import subprocess


def find_user(username: str):
    connection = sqlite3.connect("users.db")

    query = "SELECT id, username FROM users WHERE username = '" + username + "'"

    return connection.execute(query).fetchone()


def hash_password(password: str) -> str:
    return hashlib.md5(password.encode("utf-8")).hexdigest()


def ping_host(host: str) -> bytes:
    return subprocess.check_output("ping -c 1 " + host, shell=True)


def authenticate(username: str, password: str) -> bool:
    admin_password = os.environ.get("ADMIN_PASSWORD")

    if username == "admin" and password == admin_password:
        return True

    return False