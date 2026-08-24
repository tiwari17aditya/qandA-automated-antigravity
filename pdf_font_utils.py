import os
import sys
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FONTS_REGISTERED = False

def register_unicode_fonts():
    """
    Registers NotoSansDevanagari TTF fonts with ReportLab so Hindi (Devanagari)
    and English characters render beautifully in generated PDF documents.
    """
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return "Devanagari", "Devanagari-Bold"

    base_dir = os.path.dirname(os.path.abspath(__file__))
    fonts_dir = os.path.join(base_dir, "fonts")
    
    reg_path = os.path.join(fonts_dir, "NotoSansDevanagari-Regular.ttf")
    bold_path = os.path.join(fonts_dir, "NotoSansDevanagari-Bold.ttf")

    if os.path.exists(reg_path) and os.path.exists(bold_path):
        try:
            pdfmetrics.registerFont(TTFont("Devanagari", reg_path))
            pdfmetrics.registerFont(TTFont("Devanagari-Bold", bold_path))
            _FONTS_REGISTERED = True
            return "Devanagari", "Devanagari-Bold"
        except Exception as e:
            print(f"[WARN] Failed to register Devanagari fonts: {e}")

    # Fallback to standard Helvetica if TTF fonts are missing
    return "Helvetica", "Helvetica-Bold"
