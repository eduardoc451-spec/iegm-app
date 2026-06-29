"""
Módulo de banco de dados SQLite para IEG-M Francisco Morato
Gerencia usuários, respostas e histórico de pontuação
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

DB_PATH = "ieg_m_database.db"


def init_database():
    """Inicializa o banco de dados com as tabelas necessárias."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tabela de usuários
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Tabela de respostas
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dimension TEXT NOT NULL,
            year INTEGER NOT NULL,
            question_id TEXT NOT NULL,
            answer TEXT,
            points INTEGER,
            max_points INTEGER,
            evidence TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(dimension, year, question_id)
        )
    """
    )

    # Tabela de histórico de pontuação
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scoring_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dimension TEXT NOT NULL,
            year INTEGER NOT NULL,
            total_points INTEGER,
            max_points INTEGER,
            band TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(dimension, year)
        )
    """
    )

    conn.commit()
    conn.close()


def add_user(username: str, password: str, role: str = "user") -> bool:
    """Adiciona um novo usuário ao banco de dados."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, password, role),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def verify_user(username: str, password: str) -> Tuple[bool, Optional[str]]:
    """Verifica credenciais do usuário. Retorna (sucesso, role)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password, role FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()

    if result and result[0] == password:
        return True, result[1]
    return False, None


def save_response(
    dimension: str,
    year: int,
    question_id: str,
    answer: str,
    points: int,
    max_points: int,
    evidence: str = "",
    notes: str = "",
) -> bool:
    """Salva uma resposta de quesito."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO responses 
            (dimension, year, question_id, answer, points, max_points, evidence, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (dimension, year, question_id, answer, points, max_points, evidence, notes),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Erro ao salvar resposta: {e}")
        return False


def get_responses(dimension: str, year: int) -> List[Dict]:
    """Obtém todas as respostas de uma dimensão e ano."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT question_id, answer, points, max_points, evidence, notes
        FROM responses
        WHERE dimension = ? AND year = ?
        ORDER BY question_id
    """,
        (dimension, year),
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "question_id": row[0],
            "answer": row[1],
            "points": row[2],
            "max_points": row[3],
            "evidence": row[4],
            "notes": row[5],
        }
        for row in rows
    ]


def save_scoring_history(
    dimension: str, year: int, total_points: int, max_points: int, band: str
) -> bool:
    """Salva o histórico de pontuação."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO scoring_history
            (dimension, year, total_points, max_points, band)
            VALUES (?, ?, ?, ?, ?)
        """,
            (dimension, year, total_points, max_points, band),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Erro ao salvar histórico de pontuação: {e}")
        return False


def get_scoring_history(dimension: str) -> List[Dict]:
    """Obtém o histórico de pontuação de uma dimensão."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT year, total_points, band
        FROM scoring_history
        WHERE dimension = ?
        ORDER BY year
    """,
        (dimension,),
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {"year": row[0], "total_points": row[1], "band": row[2]} for row in rows
    ]


# Inicializar banco de dados ao importar o módulo
if not os.path.exists(DB_PATH):
    init_database()
    # Adicionar usuário admin padrão
    from constants import ADMIN_USER, ADMIN_PASSWORD

    add_user(ADMIN_USER, ADMIN_PASSWORD, "admin")
