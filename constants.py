"""
Constantes do sistema IEG-M Francisco Morato
Definições de quesitos, pontuação máxima/mínima e faixas de desempenho
"""

# Quesitos do i-Cidade com pontuação máxima e mínima
ICIDADE_QUESTIONS = {
    "1.0": {"title": "Quesito 1.0", "max": 40, "min": 0},
    "1.3": {"title": "Quesito 1.3", "max": 5, "min": 0},
    "1.4": {"title": "Quesito 1.4", "max": 50, "min": 0},
    "2.0": {"title": "Quesito 2.0", "max": 20, "min": 0},
    "2.1": {"title": "Quesito 2.1", "max": 30, "min": 0},
    "2.2": {"title": "Quesito 2.2", "max": 5, "min": 0},
    "3.0": {"title": "Quesito 3.0", "max": 10, "min": 0},
    "3.1.1": {"title": "Quesito 3.1.1", "max": 10, "min": 0},
    "4.2": {"title": "Quesito 4.2", "max": 0, "min": -50},
    "5.0": {"title": "Quesito 5.0", "max": 200, "min": 0},
    "5.1.1": {"title": "Quesito 5.1.1", "max": 0, "min": -100},
    "5.2": {"title": "Quesito 5.2", "max": 0, "min": -50},
    "6.0": {"title": "Quesito 6.0", "max": 0, "min": -50},
    "7.0": {"title": "Quesito 7.0", "max": 50, "min": 0},
    "7.1": {"title": "Quesito 7.1", "max": 5, "min": 0},
    "7.2": {"title": "Quesito 7.2", "max": 80, "min": 0},
    "7.3": {"title": "Quesito 7.3", "max": 50, "min": 0},
    "7.4": {"title": "Quesito 7.4", "max": 50, "min": 0},
    "7.5": {"title": "Quesito 7.5", "max": 10, "min": 0},
    "7.6": {"title": "Quesito 7.6", "max": 10, "min": 0},
    "8.0": {"title": "Quesito 8.0", "max": 50, "min": 0},
    "8.1.1.1": {"title": "Quesito 8.1.1.1", "max": 20, "min": 0},
    "8.2": {"title": "Quesito 8.2", "max": 50, "min": 0},
    "9.0": {"title": "Quesito 9.0", "max": 100, "min": 0},
    "10.0": {"title": "Quesito 10.0", "max": 0, "min": -100},
    "11.1": {"title": "Quesito 11.1", "max": 0, "min": -20},
    "11.1.1": {"title": "Quesito 11.1.1", "max": 0, "min": -20},
    "11.2": {"title": "Quesito 11.2", "max": 0, "min": -20},
    "11.2.1": {"title": "Quesito 11.2.1", "max": 0, "min": -20},
    "12.1": {"title": "Quesito 12.1", "max": 0, "min": -50},
    "12.1.3": {"title": "Quesito 12.1.3", "max": 0, "min": -50},
    "14.0": {"title": "Quesito 14.0", "max": 0, "min": -50},
    "15.0": {"title": "Quesito 15.0", "max": 50, "min": 0},
    "16.0": {"title": "Quesito 16.0", "max": 50, "min": 0},
    "C1.1": {"title": "Quesito C1.1", "max": 50, "min": 10},
}

# Faixas de desempenho
PERFORMANCE_BANDS = [
    {"band": "C", "min": 0, "max": 500, "color": "#DC2626"},
    {"band": "C+", "min": 500, "max": 600, "color": "#EA580C"},
    {"band": "B", "min": 600, "max": 750, "color": "#EAB308"},
    {"band": "B+", "min": 750, "max": 900, "color": "#84CC16"},
    {"band": "A", "min": 900, "max": 1500, "color": "#22C55E"},
]

# Classificação de relevância de perda de pontuação
RELEVANCE_LEVELS = {
    "Baixa": {"min": 1, "max": 5},
    "Média": {"min": 6, "max": 15},
    "Alta": {"min": 16, "max": 250},
}

# Anos disponíveis
AVAILABLE_YEARS = list(range(2024, 2031))

# Dimensões disponíveis
DIMENSIONS = [
    "i-Cidade",
    "i-Gov TI",
    "i-Amb",
    "i-Plan",
    "i-Fiscal",
    "i-Educ",
    "i-Saúde",
]

# Usuário administrador padrão
ADMIN_USER = "jefferson.espanha"
ADMIN_PASSWORD = "fodase"
