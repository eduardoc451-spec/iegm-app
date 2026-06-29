"""
Módulo de geração de relatório PDF
Cria relatórios com análise de pontuação, pontos fortes e críticos
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
    Image,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
from typing import List, Dict
import io

from constants import ICIDADE_QUESTIONS
from scoring import analyze_responses, get_band_color


def generate_report_pdf(
    dimension: str, year: int, responses: List[Dict]
) -> bytes:
    """Gera um relatório PDF com análise de pontuação."""

    # Análise das respostas
    analysis = analyze_responses(responses)

    # Criar documento PDF em memória
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5 * inch)

    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#001A4D"),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )

    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#001A4D"),
        spaceAfter=12,
        spaceBefore=12,
        fontName="Helvetica-Bold",
    )

    normal_style = ParagraphStyle(
        "CustomNormal",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#333333"),
        spaceAfter=6,
    )

    # Elementos do documento
    elements = []

    # Cabeçalho
    elements.append(
        Paragraph("IEG-M Francisco Morato", title_style)
    )
    elements.append(
        Paragraph(f"Relatório de Auditoria - {dimension.upper()}", heading_style)
    )
    elements.append(Spacer(1, 0.2 * inch))

    # Informações gerais
    info_data = [
        ["Dimensão:", dimension.upper()],
        ["Ano de Referência:", str(year)],
        ["Pontuação Total:", f"{analysis['total_points']} pontos"],
        ["Faixa de Desempenho:", analysis["band"]],
        ["Data do Relatório:", datetime.now().strftime("%d/%m/%Y %H:%M")],
    ]

    info_table = Table(info_data, colWidths=[2 * inch, 4 * inch])
    info_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8E8E8")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 1, colors.grey),
            ]
        )
    )
    elements.append(info_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Pontos Fortes
    if analysis["strong_points"]:
        elements.append(Paragraph("✓ Pontos Fortes", heading_style))

        strong_data = [["Quesito", "Resposta", "Pontos", "Evidência"]]
        for point in analysis["strong_points"]:
            strong_data.append(
                [
                    point.get("question_id", ""),
                    point.get("answer", ""),
                    str(point.get("points", "")),
                    point.get("evidence", "")[:50],  # Truncar evidência
                ]
            )

        strong_table = Table(strong_data, colWidths=[1 * inch, 2 * inch, 1 * inch, 2 * inch])
        strong_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#22C55E")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                ]
            )
        )
        elements.append(strong_table)
        elements.append(Spacer(1, 0.2 * inch))

    # Pontos Críticos por Relevância
    if any(analysis["critical_points"].values()):
        elements.append(Paragraph("✗ Pontos Críticos", heading_style))

        relevance_colors = {
            "Alta": colors.HexColor("#DC2626"),
            "Média": colors.HexColor("#EA580C"),
            "Baixa": colors.HexColor("#EAB308"),
        }

        for relevance in ["Alta", "Média", "Baixa"]:
            if analysis["critical_points"][relevance]:
                elements.append(
                    Paragraph(
                        f"Relevância {relevance} (Perda de Pontuação)",
                        ParagraphStyle(
                            "SubHeading",
                            parent=styles["Heading3"],
                            fontSize=11,
                            textColor=relevance_colors[relevance],
                            spaceBefore=6,
                            spaceAfter=6,
                        ),
                    )
                )

                critical_data = [["Quesito", "Resposta", "Pontos", "Perda"]]
                for point in analysis["critical_points"][relevance]:
                    critical_data.append(
                        [
                            point.get("question_id", ""),
                            point.get("answer", ""),
                            str(point.get("points", "")),
                            str(point.get("points_lost", "")),
                        ]
                    )

                critical_table = Table(
                    critical_data, colWidths=[1 * inch, 2 * inch, 1 * inch, 1 * inch]
                )
                critical_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), relevance_colors[relevance]),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                        ]
                    )
                )
                elements.append(critical_table)
                elements.append(Spacer(1, 0.15 * inch))

    # Nova página para histórico completo
    elements.append(PageBreak())

    # Histórico Geral de Respostas
    elements.append(Paragraph("Histórico Geral de Respostas", heading_style))

    all_data = [["Quesito", "Resposta", "Pontos", "Máximo", "Evidência"]]
    for response in responses:
        all_data.append(
            [
                response.get("question_id", ""),
                response.get("answer", "")[:30],
                str(response.get("points", "")),
                str(response.get("max_points", "")),
                response.get("evidence", "")[:40],
            ]
        )

    all_table = Table(
        all_data, colWidths=[1 * inch, 1.5 * inch, 0.8 * inch, 0.8 * inch, 1.9 * inch]
    )
    all_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#001A4D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 1, colors.grey),
            ]
        )
    )
    elements.append(all_table)

    # Rodapé
    elements.append(Spacer(1, 0.3 * inch))
    footer_text = f"Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | IEG-M Francisco Morato v1.0"
    elements.append(
        Paragraph(
            footer_text,
            ParagraphStyle(
                "Footer",
                parent=styles["Normal"],
                fontSize=8,
                textColor=colors.grey,
                alignment=TA_CENTER,
            ),
        )
    )

    # Construir PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
