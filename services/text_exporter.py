import os
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

class TextExporter:
    """
    Exports post bodies, descriptions, and comments to clean TXT or PDF files.
    """

    @staticmethod
    def _strip_html(html_str: str) -> str:
        if not html_str:
            return ""
        # Replace line breaks and paragraphs
        text = re.sub(r'<br\s*/?>', '\n', html_str, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        # Unescape HTML entities
        import html
        return html.unescape(text).strip()

    @classmethod
    def export_post_to_txt(
        cls,
        post_data: Dict[str, Any],
        comments: Optional[List[Dict[str, Any]]] = None,
        target_path: str = ""
    ) -> bool:
        """
        Writes post metadata, formatted content, and comments into a TXT file.
        """
        title = post_data.get("title") or "Untitled Post"
        service = post_data.get("service", "")
        user_id = post_data.get("user", "")
        published = post_data.get("published", "") or post_data.get("added", "")
        content = cls._strip_html(post_data.get("content", ""))

        lines = [
            f"Title:     {title}",
            f"Service:   {service}",
            f"Creator:   {user_id}",
            f"Published: {published}",
            "=" * 60,
            "",
            "CONTENT:",
            content if content else "(No text content)",
            "",
        ]

        if comments:
            lines.append("=" * 60)
            lines.append(f"COMMENTS ({len(comments)}):")
            lines.append("")
            for idx, c in enumerate(comments, 1):
                c_user = c.get("commenter_name") or c.get("user") or f"User #{idx}"
                c_date = c.get("published") or c.get("added") or ""
                c_body = cls._strip_html(c.get("content", ""))
                lines.append(f"[{idx}] {c_user} ({c_date}):")
                lines.append(f"    {c_body}")
                lines.append("-" * 40)

        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return True
        except Exception:
            return False

    @classmethod
    def export_post_to_pdf(
        cls,
        post_data: Dict[str, Any],
        comments: Optional[List[Dict[str, Any]]] = None,
        target_path: str = ""
    ) -> bool:
        """
        Attempts to write post content to PDF if fpdf/fpdf2 is installed.
        Falls back to TXT if PDF libraries are not present.
        """
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font("Helvetica", size=12)

            title = post_data.get("title") or "Untitled Post"
            pdf.set_font("Helvetica", style="B", size=16)
            pdf.cell(0, 10, title.encode("latin-1", "replace").decode("latin-1"), ln=True)
            pdf.ln(4)

            pdf.set_font("Helvetica", size=10)
            published = post_data.get("published", "") or ""
            service = post_data.get("service", "")
            pdf.cell(0, 6, f"Service: {service} | Published: {published}".encode("latin-1", "replace").decode("latin-1"), ln=True)
            pdf.ln(6)

            pdf.set_font("Helvetica", size=11)
            content = cls._strip_html(post_data.get("content", ""))
            if content:
                pdf.multi_cell(0, 6, content.encode("latin-1", "replace").decode("latin-1"))

            if comments:
                pdf.ln(8)
                pdf.set_font("Helvetica", style="B", size=13)
                pdf.cell(0, 8, f"Comments ({len(comments)}):", ln=True)
                pdf.set_font("Helvetica", size=10)
                for idx, c in enumerate(comments, 1):
                    c_body = cls._strip_html(c.get("content", ""))
                    pdf.multi_cell(0, 5, f"[{idx}] {c_body}".encode("latin-1", "replace").decode("latin-1"))
                    pdf.ln(2)

            os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
            pdf.output(target_path)
            return True
        except Exception:
            # Fallback to TXT with .txt extension
            txt_path = os.path.splitext(target_path)[0] + ".txt"
            return cls.export_post_to_txt(post_data, comments, txt_path)
