from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import os
import json
import time

class DrPetClinicalAudit:
    """PDF Export utility for professional veterinary audits."""
    def __init__(self, output_dir="data/results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_pdf(self, file_id, analysis_data):
        """
        [Improvement #4: Professional Clinical Export]
        Generates a PDF audit report grounded in sensory evidence.
        """
        pdf_filename = f"DR_PET_Audit_{file_id}.pdf"
        output_path = os.path.join(self.output_dir, pdf_filename)
        
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # --- Header Section ---
        title_style = ParagraphStyle(
            'TitleStyle', parent=styles['Heading1'],
            fontSize=22, textColor=colors.HexColor("#2C3E50"),
            spaceAfter=15
        )
        elements.append(Paragraph("Clinical Behavioral Audit Report", title_style))
        elements.append(Paragraph(f"Reference ID: {file_id}", styles['Normal']))
        elements.append(Paragraph(f"Timestamp: {time.ctime(analysis_data.get('timestamp', time.time()))}", styles['Normal']))
        elements.append(Spacer(1, 15))

        # --- Summary Section ---
        elements.append(Paragraph("Behavioral Summary", styles['Heading2']))
        metrics = analysis_data.get("metrics", {})
        summary_text = (
            f"<b>Primary Sentiment:</b> {metrics.get('acoustic_sentiment', 'Unknown')}<br/>"
            f"<b>Happiness Score:</b> {metrics.get('happiness_score', 0)}%<br/>"
            f"<b>Data Fidelity:</b> {analysis_data.get('data_fidelity', 'Standard')}"
        )
        elements.append(Paragraph(summary_text, styles['Normal']))
        elements.append(Spacer(1, 15))

        # --- AI Insights & Key Points ---
        elements.append(Paragraph("Direct AI Observations (Vision)", styles['Heading2']))
        ai_insights = analysis_data.get("ai_insights", {})
        key_points = ai_insights.get("key_points", [])
        
        if key_points:
            for point in key_points:
                elements.append(Paragraph(f"• {point}", styles['Normal']))
        else:
            elements.append(Paragraph("No specific morphological points extracted.", styles['Normal']))
        elements.append(Spacer(1, 15))

        # --- Clinical Reasoning ---
        elements.append(Paragraph("Professional Interpretation (Groq/Gemini Synthesis)", styles['Heading2']))
        coaching = analysis_data.get("coaching_plan", {})
        if not coaching:
            # Fallback for orchestrator.py format
            coaching = {
                "message": analysis_data.get("analysis", "N/A"),
                "care_methods": analysis_data.get("recommendations", [])
            }
        elements.append(Paragraph(coaching.get("message", "N/A"), styles['Normal']))
        elements.append(Spacer(1, 15))

        # --- Recommended Action ---
        elements.append(Paragraph("Recommended Care Methods", styles['Heading2']))
        care_methods = coaching.get("care_methods", [])
        if care_methods:
            for method in care_methods:
                elements.append(Paragraph(f"• {method}", styles['Normal']))
        else:
            elements.append(Paragraph("No specific recommendations provided.", styles['Normal']))
        elements.append(Spacer(1, 15))

        # --- RAG Grounding ---
        rag_context = analysis_data.get("rag_context", "")
        if not rag_context and "individual_pets" in analysis_data and analysis_data["individual_pets"]:
             rag_context = analysis_data["individual_pets"][0].get("pet_data", {}).get("rag_insight", "")
             
        if rag_context and rag_context != "N/A":
            elements.append(Paragraph("Veterinary Context (RAG)", styles['Heading2']))
            elements.append(Paragraph(rag_context, styles['Italic']))
            elements.append(Spacer(1, 15))

        # --- Table Section: Sensory Data ---
        elements.append(Paragraph("Sensory Calibration Data", styles['Heading2']))
        data = [
            ["Metric", "Value", "Confidence"],
            ["Motion Vigor", metrics.get("motion_vigor", 0), "High"],
            ["Tail Wag Freq", metrics.get("tail_wag_frequency", "0 Hz"), "High"],
            ["Acoustic Sent.", metrics.get("acoustic_sentiment", "N/A"), "Medium"],
            ["Total Score", f"{metrics.get('happiness_score', 0)}%", "AI-Enhanced"]
        ]
        t = Table(data, colWidths=[150, 150, 150])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#34495E")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        elements.append(t)

        # --- Build PDF ---
        doc.build(elements)
        print(f"CLINICAL AUDIT: PDF report generated for {file_id} at {output_path}")
        return pdf_filename
