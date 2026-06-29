"""
Módulo de cálculo de pontuação e classificação
Funções para calcular pontos, faixas e relevância
"""

from constants import PERFORMANCE_BANDS, RELEVANCE_LEVELS, ICIDADE_QUESTIONS
from typing import List, Dict


def calculate_band(total_points: int) -> str:
    """Calcula a faixa de desempenho baseada na pontuação total."""
    for band_info in PERFORMANCE_BANDS:
        if band_info["min"] <= total_points < band_info["max"]:
            return band_info["band"]
    return "C"


def get_band_color(band: str) -> str:
    """Retorna a cor associada à faixa de desempenho."""
    for band_info in PERFORMANCE_BANDS:
        if band_info["band"] == band:
            return band_info["color"]
    return "#9CA3AF"


def classify_relevance(points_lost: int) -> str:
    """Classifica a relevância de perda de pontuação."""
    for relevance, range_info in RELEVANCE_LEVELS.items():
        if range_info["min"] <= points_lost <= range_info["max"]:
            return relevance
    return "Baixa"


def validate_points(question_id: str, points: int) -> bool:
    """Valida se os pontos estão dentro do intervalo permitido."""
    if question_id not in ICIDADE_QUESTIONS:
        return False

    question = ICIDADE_QUESTIONS[question_id]
    min_points = min(question["min"], question["max"])
    max_points = max(question["min"], question["max"])

    return min_points <= points <= max_points


def calculate_total_points(responses: List[Dict]) -> int:
    """Calcula a pontuação total a partir das respostas."""
    total = 0
    for response in responses:
        if response.get("points") is not None:
            total += response["points"]
    return total


def analyze_responses(responses: List[Dict]) -> Dict:
    """Analisa as respostas e retorna estatísticas."""
    total_points = calculate_total_points(responses)
    band = calculate_band(total_points)

    # Pontos fortes (quesitos na pontuação máxima)
    strong_points = []
    critical_points = {"Alta": [], "Média": [], "Baixa": []}

    for response in responses:
        question_id = response.get("question_id")
        if question_id not in ICIDADE_QUESTIONS:
            continue

        question = ICIDADE_QUESTIONS[question_id]
        points = response.get("points", 0)

        # Verificar se é ponto forte
        if points == question["max"] and question["max"] > 0:
            strong_points.append(response)
        # Verificar se é ponto crítico
        elif points < question["max"]:
            points_lost = question["max"] - points
            if points_lost > 0:
                relevance = classify_relevance(points_lost)
                critical_points[relevance].append(
                    {**response, "points_lost": points_lost}
                )

    return {
        "total_points": total_points,
        "band": band,
        "strong_points": strong_points,
        "critical_points": critical_points,
        "total_responses": len(responses),
    }


def get_band_info(band: str) -> Dict:
    """Retorna informações sobre uma faixa de desempenho."""
    for band_info in PERFORMANCE_BANDS:
        if band_info["band"] == band:
            return band_info
    return PERFORMANCE_BANDS[0]


def calculate_max_possible_points() -> int:
    """Calcula a pontuação máxima possível do i-Cidade."""
    total = 0
    for question in ICIDADE_QUESTIONS.values():
        if question["max"] > 0:
            total += question["max"]
    return total
