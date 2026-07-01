"""
Persistance locale (SQLite) pour ESPACE VIRTUELLE MINIÈRE DE SMC.

Chaque prospect a son état complet (DataFrames, dicts, listes) sérialisé en pickle et stocké
dans une table clé/valeur. Cela permet de retrouver les données après un redémarrage de
l'application, tant que le fichier .db reste sur le même disque.

⚠️ Limite importante : sur un hébergement éphémère (ex. Streamlit Community Cloud sans volume
persistant), le système de fichiers est réinitialisé à chaque redéploiement — la base sera alors
vidée. Pour une persistance garantie en production, héberger ce fichier sur un volume durable
(serveur dédié, VM, ou un vrai service de base de données externe).
"""
import sqlite3
import pickle
import os
import threading

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smc_dashboard.db")
_lock = threading.Lock()


def db_stats(path=DB_PATH):
    """Retourne, pour chaque prospect stocké, sa date de dernière sauvegarde et la taille
    (en octets) de son état sérialisé — pour affichage dans l'onglet Base de données centrale."""
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            "SELECT project, updated_at, LENGTH(state) FROM project_state ORDER BY project"
        ).fetchall()
    return [{"Prospect": r[0], "Derniere_sauvegarde": r[1], "Taille_octets": r[2]} for r in rows]


def get_db_file_bytes(path=DB_PATH):
    if not os.path.exists(path):
        return b""
    with open(path, "rb") as f:
        return f.read()


def restore_db_file(file_bytes, path=DB_PATH):
    with _lock:
        with open(path, "wb") as f:
            f.write(file_bytes)


def collar_count(project, path=DB_PATH):
    """Compte rapide du nombre de trous (RC/AC/DD) pour un prospect, sans tout recharger côté app."""
    state = load_project_state(project, path)
    if not state:
        return 0
    total = 0
    for k in ["RC", "AC", "DD"]:
        df = state.get("data", {}).get(k)
        if df is not None and not df.empty and "Sondage" in df.columns:
            total += df["Sondage"].nunique()
    return total


import hashlib
import secrets
import string


def init_users_table(path=DB_PATH):
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                role TEXT,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                must_change_password INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()


def generate_password(length=10):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _slugify_username(full_name):
    import unicodedata
    norm = unicodedata.normalize("NFKD", full_name).encode("ascii", "ignore").decode("ascii")
    parts = [p for p in norm.lower().replace("-", " ").split() if p]
    if not parts:
        return "user"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0][0]}{parts[-1]}"


def create_user(full_name, role, username=None, password=None, path=DB_PATH):
    """Crée un compte. Si username/password ne sont pas fournis, ils sont générés
    automatiquement (username dérivé du nom, mot de passe aléatoire). Retourne
    (username, password_en_clair) — le mot de passe en clair n'est JAMAIS stocké,
    seul son hash l'est ; il faut donc le communiquer à la personne concernée
    immédiatement après création."""
    init_users_table(path)
    base_username = username or _slugify_username(full_name)
    final_username = base_username
    with sqlite3.connect(path) as conn:
        i = 1
        while conn.execute("SELECT 1 FROM users WHERE username = ?", (final_username,)).fetchone():
            i += 1
            final_username = f"{base_username}{i}"
        plain_password = password or generate_password()
        salt = secrets.token_hex(16)
        pwd_hash = _hash_password(plain_password, salt)
        conn.execute(
            "INSERT INTO users (username, full_name, role, password_hash, salt) VALUES (?, ?, ?, ?, ?)",
            (final_username, full_name, role, pwd_hash, salt),
        )
        conn.commit()
    return final_username, plain_password


def verify_user(username, password, path=DB_PATH):
    init_users_table(path)
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "SELECT password_hash, salt, full_name, role FROM users WHERE username = ?", (username,)
        ).fetchone()
    if row is None:
        return None
    pwd_hash, salt, full_name, role = row
    if _hash_password(password, salt) == pwd_hash:
        return {"username": username, "full_name": full_name, "role": role}
    return None


def list_users(path=DB_PATH):
    init_users_table(path)
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            "SELECT username, full_name, role, must_change_password, created_at FROM users ORDER BY role, full_name"
        ).fetchall()
    return [{"username": r[0], "full_name": r[1], "role": r[2], "must_change_password": bool(r[3]), "created_at": r[4]} for r in rows]


def reset_password(username, new_password=None, path=DB_PATH):
    plain_password = new_password or generate_password()
    salt = secrets.token_hex(16)
    pwd_hash = _hash_password(plain_password, salt)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE users SET password_hash=?, salt=?, must_change_password=1 WHERE username=?",
                     (pwd_hash, salt, username))
        conn.commit()
    return plain_password


def change_password(username, new_password, path=DB_PATH):
    salt = secrets.token_hex(16)
    pwd_hash = _hash_password(new_password, salt)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE users SET password_hash=?, salt=?, must_change_password=0 WHERE username=?",
                     (pwd_hash, salt, username))
        conn.commit()


def delete_user(username, path=DB_PATH):
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()


def user_count(path=DB_PATH):
    init_users_table(path)
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def init_db(path=DB_PATH):
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_state (
                project TEXT NOT NULL,
                state BLOB NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (project)
            )
        """)
        conn.commit()
    return path


def list_projects(path=DB_PATH):
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT project FROM project_state ORDER BY project").fetchall()
    return [r[0] for r in rows]


def save_project_state(project, state_dict, path=DB_PATH):
    """Sauvegarde l'état complet d'un prospect (dict de DataFrames/listes/dicts)."""
    blob = pickle.dumps(state_dict)
    with _lock:
        with sqlite3.connect(path) as conn:
            conn.execute(
                "INSERT INTO project_state (project, state, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(project) DO UPDATE SET state=excluded.state, updated_at=CURRENT_TIMESTAMP",
                (project, blob),
            )
            conn.commit()


def load_project_state(project, path=DB_PATH):
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT state FROM project_state WHERE project = ?", (project,)).fetchone()
    if row is None:
        return None
    return pickle.loads(row[0])


def delete_project(project, path=DB_PATH):
    with _lock:
        with sqlite3.connect(path) as conn:
            conn.execute("DELETE FROM project_state WHERE project = ?", (project,))
            conn.commit()


def last_saved(project, path=DB_PATH):
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT updated_at FROM project_state WHERE project = ?", (project,)).fetchone()
    return row[0] if row else None
