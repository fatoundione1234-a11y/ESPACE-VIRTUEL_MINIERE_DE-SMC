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
