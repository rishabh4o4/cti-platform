import os
import hashlib
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    Flowable,
)
from reportlab.pdfgen import canvas


class ReportGenerationError(Exception):
    """Exception raised for errors in the PDF generation process."""
    pass

class BookmarkFlowable(Flowable):
    """A flowable that inserts a PDF bookmark (Outline entry)."""
    def __init__(self, title: str, key: str):
        Flowable.__init__(self)
        self.title = title
        self.key = key
        
    def draw(self):
        self.canv.bookmarkPage(self.key)
        self.canv.addOutlineEntry(self.title, self.key, 0, 0)

class PageNumCanvas(canvas.Canvas):
    """
    Custom canvas to allow drawing 'Page X of Y'.
    """
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            if hasattr(self, '_draw_page_number'):
                self._draw_page_number(page_count)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)


class EvidenceReportGenerator:
    """
    Generates investigation-ready PDF reports with a law enforcement style layout.
    """

    def __init__(self):
        """
        Initialize the report generator.
        """
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles for the report."""
        self.styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=self.styles["Heading1"],
                fontSize=18,
                spaceAfter=10,
                alignment=1,  # Center
                fontName="Helvetica-Bold",
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Classification",
                parent=self.styles["Normal"],
                fontSize=12,
                spaceAfter=20,
                alignment=1,  # Center
                textColor=colors.red,
                fontName="Helvetica-Bold",
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading2"],
                fontSize=14,
                spaceBefore=15,
                spaceAfter=5,
                fontName="Helvetica-Bold",
                textColor=colors.darkblue,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="FieldLabel",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=10,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="FieldValue",
                parent=self.styles["Normal"],
                fontName="Helvetica",
                fontSize=10,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="MessageBody",
                parent=self.styles["Normal"],
                fontName="Courier",
                fontSize=10,
                leftIndent=20,
                rightIndent=20,
                spaceBefore=10,
                spaceAfter=10,
            )
        )

    def _create_header(self, case_id: str) -> List[Any]:
        """Creates the header section of the report."""
        elements = []
        elements.append(Paragraph("LAW ENFORCEMENT SENSITIVE", self.styles["Classification"]))
        elements.append(Paragraph("CYBER INTELLIGENCE UNIT", self.styles["ReportTitle"]))
        elements.append(Paragraph("INTELLIGENCE EVIDENCE REPORT", self.styles["ReportTitle"]))
        
        # Divider
        elements.append(HRFlowable(width="100%", thickness=2, color=colors.black, spaceBefore=5, spaceAfter=15))
        return elements

    def _create_metadata_table(self, report_data: Dict[str, Any]) -> Table:
        """Creates a tabular layout for key metadata."""
        # Risk score formatting
        risk_score_raw = report_data.get("risk_score", 0.0)
        try:
            risk_score = float(risk_score_raw)
        except (ValueError, TypeError):
            risk_score = 0.0
            
        risk_text = f"{risk_score} / 100"
        
        # Color coding for severity
        severity = str(report_data.get("severity", "UNKNOWN")).upper()
        
        data = [
            [
                Paragraph("<b>Case ID:</b>", self.styles["FieldLabel"]),
                Paragraph(str(report_data.get("case_id", "N/A")), self.styles["FieldValue"]),
                Paragraph("<b>Generated:</b>", self.styles["FieldLabel"]),
                Paragraph(report_data.get("generated_timestamp", datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")), self.styles["FieldValue"])
            ],
            [
                Paragraph("<b>Source:</b>", self.styles["FieldLabel"]),
                Paragraph(str(report_data.get("source", "N/A")), self.styles["FieldValue"]),
                Paragraph("<b>Source Status:</b>", self.styles["FieldLabel"]),
                Paragraph(str(report_data.get("source_status", "N/A")), self.styles["FieldValue"])
            ],
            [
                Paragraph("<b>Source Reliability:</b>", self.styles["FieldLabel"]),
                Paragraph(str(report_data.get("source_reliability_rating", "C / 2")), self.styles["FieldValue"]),
                Paragraph("<b>Model Version:</b>", self.styles["FieldLabel"]),
                Paragraph(str(report_data.get("model_version", "N/A")), self.styles["FieldValue"])
            ],
            [
                Paragraph("<b>Risk Score:</b>", self.styles["FieldLabel"]),
                Paragraph(risk_text, self.styles["FieldValue"]),
                Paragraph("<b>Data Confidence:</b>", self.styles["FieldLabel"]),
                Paragraph(str(report_data.get("data_confidence", "N/A")), self.styles["FieldValue"])
            ],
            [
                Paragraph("<b>Severity:</b>", self.styles["FieldLabel"]),
                Paragraph(severity, self.styles["FieldValue"]),
                Paragraph("<b>Threat Category:</b>", self.styles["FieldLabel"]),
                Paragraph(str(report_data.get("threat_category", "N/A")), self.styles["FieldValue"])
            ],
            [
                Paragraph("<b>Report Version:</b>", self.styles["FieldLabel"]),
                Paragraph(str(report_data.get("report_version", "v1.0")), self.styles["FieldValue"]),
                "", ""
            ]
        ]
        
        table = Table(data, colWidths=[1.2*inch, 2.3*inch, 1.2*inch, 2.3*inch])
        
        # Determine severity cell color
        sev_color = colors.whitesmoke
        if severity == "CRITICAL":
            sev_color = colors.lightpink
        elif severity == "HIGH":
            sev_color = colors.moccasin
        elif severity == "MEDIUM":
            sev_color = colors.lightyellow
        elif severity == "LOW":
            sev_color = colors.lightgreen

        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (1, 4), (1, 4), sev_color),  # Severity cell background
        ]))
        return table
        
    def _create_evidence_block(self, report_data: Dict[str, Any]) -> List[Any]:
        """Creates the original message / evidence block."""
        elements = []
        msg = report_data.get("original_message", "No message provided.")
        elements.append(Paragraph(msg, self.styles["MessageBody"]))
        
        meta_data = [
            [
                Paragraph("<b>Collection Timestamp:</b>", self.styles["FieldLabel"]),
                Paragraph(report_data.get("collected_at", "Unknown"), self.styles["FieldValue"])
            ],
            [
                Paragraph("<b>Author/Handle:</b>", self.styles["FieldLabel"]),
                Paragraph(str(report_data.get("author_handle", "Unknown")), self.styles["FieldValue"])
            ],
            [
                Paragraph("<b>Source URL:</b>", self.styles["FieldLabel"]),
                Paragraph(str(report_data.get("source_url", "Unknown")), self.styles["FieldValue"])
            ],
            [
                Paragraph("<b>SHA-256 Hash:</b>", self.styles["FieldLabel"]),
                Paragraph(str(report_data.get("content_hash", "Unknown")), self.styles["MessageBody"])
            ]
        ]
        
        table = Table(meta_data, colWidths=[1.5*inch, 5.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)
        
        return elements

    def _create_entities_section(self, entities: List[Dict[str, str]]) -> Any:
        """Creates a table for extracted entities."""
        if not entities:
            return Paragraph("No entities extracted.", self.styles["FieldValue"])
            
        data = [["Entity Type", "Value", "Confidence"]]
        for entity in entities:
            data.append([
                entity.get("type", "N/A"),
                entity.get("value", "N/A"),
                str(entity.get("confidence", "N/A"))
            ])
            
        table = Table(data, colWidths=[2*inch, 3.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        return table

    def _create_timeline_section(self, timeline_events: List[Dict[str, str]]) -> Any:
        """Creates a timeline representation."""
        if not timeline_events:
            return Paragraph("No timeline events recorded.", self.styles["FieldValue"])
            
        data = [["Timestamp", "Event Description"]]
        for event in timeline_events:
            data.append([
                event.get("timestamp", "N/A"),
                Paragraph(event.get("description", "N/A"), self.styles["FieldValue"])
            ])
            
        table = Table(data, colWidths=[2*inch, 5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        return table

    def _create_mitre_section(self, tactics: List[str], techniques: List[str]) -> Any:
        """Creates a section for MITRE ATT&CK tactics and techniques."""
        elements = []
        
        t_data = [["Tactics", "Techniques"]]
        
        tactics_text = "\n".join([f"• {t}" for t in tactics]) if tactics else "None identified"
        tech_text = "\n".join([f"• {t}" for t in techniques]) if techniques else "None identified"
        
        t_data.append([
            Paragraph(tactics_text.replace("\n", "<br/>"), self.styles["FieldValue"]),
            Paragraph(tech_text.replace("\n", "<br/>"), self.styles["FieldValue"])
        ])
        
        table = Table(t_data, colWidths=[3.5*inch, 3.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)
        return elements

    def _create_list_section(self, items: List[str]) -> Any:
        """Creates a bulleted list for related channels or similar fields."""
        if not items:
            return Paragraph("None identified.", self.styles["FieldValue"])
            
        bullet_list = []
        for item in items:
            bullet_list.append(Paragraph(f"• {item}", self.styles["FieldValue"]))
        return bullet_list
        
    def _create_analyst_notes_section(self, notes_data: List[Dict[str, str]] | str) -> List[Any]:
        """Creates analyst notes block."""
        elements = []
        if isinstance(notes_data, str):
            elements.append(Paragraph(notes_data, self.styles["FieldValue"]))
            return elements
            
        if not notes_data:
            elements.append(Paragraph("No notes provided.", self.styles["FieldValue"]))
            return elements
            
        for note in notes_data:
            author = note.get("author", "Unknown Analyst")
            timestamp = note.get("timestamp", "Unknown Time")
            text = note.get("text", "")
            
            header = Paragraph(f"<b>{author}</b> - {timestamp}", self.styles["FieldLabel"])
            body = Paragraph(text, self.styles["FieldValue"])
            elements.extend([header, body, Spacer(1, 0.1*inch)])
            
        return elements

    def _create_recommended_actions_section(self, actions: List[str]) -> Any:
        """Creates a section for recommended actions."""
        if not actions:
            return Paragraph("No recommended actions provided.", self.styles["FieldValue"])
            
        elements = []
        for action in actions:
            elements.append(Paragraph(f"• {action}", self.styles["FieldValue"]))
        return elements
        
    def _create_attachments_section(self, media_urls: List[str]) -> Any:
        """Creates a section for media URLs/attachments."""
        if not media_urls:
            return Paragraph("No attachments or media identified.", self.styles["FieldValue"])
            
        elements = []
        for url in media_urls:
            elements.append(Paragraph(f"• {url}", self.styles["FieldValue"]))
        return elements

    def generate_bytes(self, report_data: Dict[str, Any]) -> bytes:
        """
        Generate the PDF report as bytes based on the provided dictionary of data.
        """
        output_buffer = BytesIO()
        doc = BaseDocTemplate(
            output_buffer,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        # Define the frame and template
        frame = Frame(
            doc.leftMargin, 
            doc.bottomMargin, 
            doc.width, 
            doc.height, 
            id='normal'
        )
        
        case_id = report_data.get("case_id", "UNKNOWN")
        report_ref = report_data.get("report_ref", "REF-NONE")

        def footer_canvas(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 9)
            canvas.setFillColor(colors.grey)
            # Draw a line above footer
            canvas.line(doc.leftMargin, doc.bottomMargin - 0.2*inch, doc.leftMargin + doc.width, doc.bottomMargin - 0.2*inch)
            
            def _draw_page_number(page_count):
                footer_text = f"PROPERTY OF LAW ENFORCEMENT - DO NOT DISTRIBUTE UNLESS AUTHORIZED | Case ID: {case_id} | Ref: {report_ref} | Page {doc.page} of {page_count}"
                canvas.drawString(doc.leftMargin, doc.bottomMargin - 0.4*inch, footer_text)
                
            canvas._draw_page_number = _draw_page_number
            canvas.restoreState()

        template = PageTemplate(id='ReportTemplate', frames=[frame], onPage=footer_canvas)
        doc.addPageTemplates([template])

        elements = []

        # 1. Header
        elements.extend(self._create_header(case_id))

        # 2. Metadata Block
        elements.append(BookmarkFlowable("Case Metadata", "bm_metadata"))
        elements.append(Paragraph("CASE METADATA", self.styles["SectionHeader"]))
        elements.append(self._create_metadata_table(report_data))
        elements.append(Spacer(1, 0.2*inch))

        # 3. Original Message
        elements.append(BookmarkFlowable("Original Evidence", "bm_evidence"))
        elements.append(Paragraph("ORIGINAL MESSAGE / EVIDENCE", self.styles["SectionHeader"]))
        elements.extend(self._create_evidence_block(report_data))
        elements.append(Spacer(1, 0.2*inch))

        # 4. Extracted Entities
        elements.append(BookmarkFlowable("Extracted Entities", "bm_entities"))
        elements.append(Paragraph("EXTRACTED ENTITIES", self.styles["SectionHeader"]))
        entities = report_data.get("extracted_entities", [])
        elements.append(self._create_entities_section(entities))
        elements.append(Spacer(1, 0.2*inch))

        # 4.5 MITRE ATT&CK
        tactics = report_data.get("tactics", [])
        techniques = report_data.get("techniques", [])
        if tactics or techniques:
            elements.append(BookmarkFlowable("MITRE ATT&CK", "bm_mitre"))
            elements.append(Paragraph("MITRE ATT&CK MAPPING", self.styles["SectionHeader"]))
            elements.extend(self._create_mitre_section(tactics, techniques))
            elements.append(Spacer(1, 0.2*inch))

        # 5. Related Channels
        elements.append(BookmarkFlowable("Related Channels", "bm_channels"))
        elements.append(Paragraph("RELATED CHANNELS", self.styles["SectionHeader"]))
        channels = report_data.get("related_channels", [])
        channels_elements = self._create_list_section(channels)
        if isinstance(channels_elements, list):
            elements.extend(channels_elements)
        else:
            elements.append(channels_elements)
        elements.append(Spacer(1, 0.2*inch))

        # 5.5 Recommended Actions
        actions = report_data.get("recommended_actions", [])
        if actions:
            elements.append(BookmarkFlowable("Recommended Actions", "bm_actions"))
            elements.append(Paragraph("RECOMMENDED ACTIONS", self.styles["SectionHeader"]))
            elements.extend(self._create_recommended_actions_section(actions))
            elements.append(Spacer(1, 0.2*inch))
            
        # 5.6 Attachments
        media_urls = report_data.get("media_urls", [])
        if media_urls:
            elements.append(BookmarkFlowable("Attachments", "bm_attachments"))
            elements.append(Paragraph("ATTACHMENTS & MEDIA", self.styles["SectionHeader"]))
            elements.extend(self._create_attachments_section(media_urls))
            elements.append(Spacer(1, 0.2*inch))

        # 6. Timeline
        elements.append(BookmarkFlowable("Investigation Timeline", "bm_timeline"))
        elements.append(Paragraph("INVESTIGATION TIMELINE", self.styles["SectionHeader"]))
        timeline = report_data.get("timeline", [])
        elements.append(self._create_timeline_section(timeline))
        elements.append(Spacer(1, 0.2*inch))

        # 7. Analyst Notes
        elements.append(BookmarkFlowable("Analyst Notes", "bm_notes"))
        elements.append(Paragraph("ANALYST NOTES", self.styles["SectionHeader"]))
        notes = report_data.get("analyst_notes", [])
        elements.extend(self._create_analyst_notes_section(notes))
        
        # 8. Signature Block
        elements.append(Spacer(1, 0.4*inch))
        elements.append(Paragraph("<b>Primary Analyst:</b> ___________________________   <b>Date:</b> ___________________________", self.styles["FieldValue"]))
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph("<b>Reviewing Officer:</b> ___________________________   <b>Date:</b> ___________________________", self.styles["FieldValue"]))
        
        # 9. Document Integrity Seal (on last page)
        elements.append(Spacer(1, 0.4*inch))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.black))
        elements.append(Spacer(1, 0.1*inch))
        elements.append(BookmarkFlowable("Document Integrity Seal", "bm_seal"))
        elements.append(Paragraph("DOCUMENT INTEGRITY SEAL", self.styles["SectionHeader"]))
        
        seal_data = [
            [Paragraph("<b>Original SHA-256 Hash:</b>", self.styles["FieldLabel"]),
             Paragraph(str(report_data.get("content_hash", "Unknown")), self.styles["MessageBody"])]
        ]
        seal_table = Table(seal_data, colWidths=[2*inch, 5*inch])
        seal_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(seal_table)

        # Build PDF
        try:
            doc.build(elements, canvasmaker=PageNumCanvas)
        except Exception as e:
            raise ReportGenerationError(f"Failed to generate PDF: {e}")

        return output_buffer.getvalue()

    def save_to_file(self, report_data: Dict[str, Any], output_path: str) -> None:
        """
        Generate the PDF report and save it to the specified path.
        """
        pdf_bytes = self.generate_bytes(report_data)
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

    def generate(self, report_data: Dict[str, Any]) -> bytes:
        """
        Deprecated: use generate_bytes() instead. Returns bytes.
        """
        return self.generate_bytes(report_data)
