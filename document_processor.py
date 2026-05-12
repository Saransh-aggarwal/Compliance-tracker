import io
import re
from typing import List

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageEnhance, ImageOps
import docx

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()

def preprocess_image_for_ocr(img: Image.Image) -> Image.Image:
    # 1. Convert to grayscale to remove color noise
    img = img.convert('L')
    
    # 2. Mildly boost contrast (1.5 instead of 2.0) to make text stand out 
    img = ImageEnhance.Contrast(img).enhance(1.5)
    return img

def extract_text_from_image(uploaded_file) -> str:
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)
    img.thumbnail((3000, 4000), Image.Resampling.LANCZOS) 
    img = preprocess_image_for_ocr(img)
    
    tesseract_cfg = r'--oem 3 --psm 3'
    return pytesseract.image_to_string(img, config=tesseract_cfg)
    
def extract_text_from_pdf(uploaded_file) -> str:
    pdf_bytes = uploaded_file.read()
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    parts: List[str] = []
    tesseract_cfg = r'--oem 3 --psm 6'

    for page in doc:
        text = (page.get_text("text") or "").strip()
        if text:
            parts.append(text)

        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        img = preprocess_image_for_ocr(img)
        
        ocr_text = (pytesseract.image_to_string(img, config=tesseract_cfg) or "").strip()
        if ocr_text:
            parts.append(ocr_text)

    doc.close()
    return "\n\n".join(parts)

def extract_text_from_docx(uploaded_file) -> str:
    doc = docx.Document(uploaded_file)
    return "\n".join([para.text for para in doc.paragraphs])
