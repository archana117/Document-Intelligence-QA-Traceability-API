import os
import io
import logging
from typing import List, Dict, Any, Tuple
import fitz
from pydantic import BaseModel, Field

class RawBlock(BaseModel):
    block_id: int
    page_number: int
    bbox: Tuple[float, float, float, float]
    text: str
    font_name: str
    font_size: float
    is_bold: bool
    color: int

class PageMetadata(BaseModel):
    page_number: int
    width: float
    height: float
    blocks: List[RawBlock]

class PDFDocumentData(BaseModel):
    filepath: str
    filename: str
    total_pages: int
    pages: List[PageMetadata]

class PDFLoader:
    def __init__(self, filepath: str):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"PDF file not found at {filepath}")
        self.filepath = filepath
        self.filename = os.path.basename(filepath)

    def load(self) -> PDFDocumentData:
        doc = fitz.open(self.filepath)
        total_pages = len(doc)
        pages_meta = []
        global_block_id = 1

        for page_idx in range(total_pages):
            page = doc[page_idx]
            width, height = page.rect.width, page.rect.height
            raw_blocks = page.get_text("dict")["blocks"]
            blocks_list = []

            # Check if page is empty or scanned
            text_blocks = [b for b in raw_blocks if b.get("type") == 0]
            total_chars = 0
            for b in text_blocks:
                for line in b.get("lines", []):
                    for span in line.get("spans", []):
                        total_chars += len(span.get("text", ""))

            # If page contains very little or no digital text, trigger OCR fallback
            if not text_blocks or total_chars < 50:
                ocr_blocks, next_id = self._extract_text_via_ocr(page, page_idx + 1, global_block_id)
                if ocr_blocks:
                    blocks_list.extend(ocr_blocks)
                    global_block_id = next_id

            # If no OCR was run or OCR yielded no blocks, do normal PyMuPDF text block extraction
            if not blocks_list:
                for b in raw_blocks:
                    # Type 0 is text block, Type 1 is image block
                    if b.get("type") == 0:
                        # Extract text and analyze fonts
                        text_parts = []
                        font_stats: Dict[Tuple[str, float, bool], int] = {}

                        for line in b.get("lines", []):
                          line_parts = []
                          for span in line.get("spans", []):
                              text = span["text"]
                              line_parts.append(text)
                              
                              font_name = span["font"]
                              font_size = span["size"]
                              color = span["color"]
                              flags = span["flags"]
                              is_bold = bool(flags & 16) or "bold" in font_name.lower()
                              
                              key = (font_name, font_size, is_bold)
                              font_stats[key] = font_stats.get(key, 0) + len(text)
                          
                          text_parts.append(" ".join(line_parts))

                        full_text = "\n".join(text_parts).strip()
                        if not full_text:
                            continue

                        # Determine dominant font by char count
                        if font_stats:
                            dominant_font = max(font_stats, key=font_stats.get)
                            font_name, font_size, is_bold = dominant_font
                        else:
                            font_name, font_size, is_bold = "Unknown", 10.0, False

                        blocks_list.append(
                            RawBlock(
                                block_id=global_block_id,
                                page_number=page_idx + 1,
                                bbox=b["bbox"],
                                text=full_text,
                                font_name=font_name,
                                font_size=font_size,
                                is_bold=is_bold,
                                color=b.get("color", 0)
                            )
                        )
                        global_block_id += 1
            
            pages_meta.append(
                PageMetadata(
                    page_number=page_idx + 1,
                    width=width,
                    height=height,
                    blocks=blocks_list
                )
            )

        doc.close()
        return PDFDocumentData(
            filepath=self.filepath,
            filename=self.filename,
            total_pages=total_pages,
            pages=pages_meta
        )

    def _extract_text_via_ocr(self, page, page_number: int, global_start_id: int) -> Tuple[List[RawBlock], int]:
        """
        Renders a page as an image and uses easyocr or pytesseract to perform OCR extraction.
        Returns a list of RawBlocks and the next global_block_id.
        """
        blocks = []
        global_block_id = global_start_id

        # Render page to high-res image (matrix scale 2.0 = 144 DPI)
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        png_bytes = pix.tobytes("png")
        
        # 1. Try EasyOCR first
        try:
            import easyocr
            import numpy as np
            from PIL import Image
            
            reader = easyocr.Reader(['en'], gpu=False)
            img = Image.open(io.BytesIO(png_bytes))
            img_np = np.array(img)
            
            results = reader.readtext(img_np)
            for bbox, text, confidence in results:
                text = text.strip()
                if not text:
                    continue
                # easyocr bbox: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                x0 = bbox[0][0] / 2.0
                y0 = bbox[0][1] / 2.0
                x1 = bbox[2][0] / 2.0
                y1 = bbox[2][1] / 2.0
                
                # Estimate font size from height
                font_size = max(6.0, (y1 - y0) * 0.8)
                
                blocks.append(
                    RawBlock(
                        block_id=global_block_id,
                        page_number=page_number,
                        bbox=(x0, y0, x1, y1),
                        text=text,
                        font_name="OCR-EasyOCR",
                        font_size=font_size,
                        is_bold=False,
                        color=0
                    )
                )
                global_block_id += 1
            if blocks:
                return blocks, global_block_id
        except ImportError:
            pass
        except Exception as e:
            logging.warning(f"EasyOCR fallback failed: {str(e)}")

        # 2. Try Pytesseract second
        try:
            import pytesseract
            from PIL import Image
            
            img = Image.open(io.BytesIO(png_bytes))
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            n_boxes = len(data['text'])
            
            # Pytesseract returns word-level boxes. Group words in same line.
            line_groups = {}
            for i in range(n_boxes):
                text = data['text'][i].strip()
                if not text:
                    continue
                
                if int(data['conf'][i]) < 40:
                    continue
                
                key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
                left = data['left'][i] / 2.0
                top = data['top'][i] / 2.0
                width = data['width'][i] / 2.0
                height = data['height'][i] / 2.0
                
                if key not in line_groups:
                    line_groups[key] = {
                        "text_parts": [text],
                        "bbox": [left, top, left + width, top + height]
                    }
                else:
                    g = line_groups[key]
                    g["text_parts"].append(text)
                    g["bbox"][0] = min(g["bbox"][0], left)
                    g["bbox"][1] = min(g["bbox"][1], top)
                    g["bbox"][2] = max(g["bbox"][2], left + width)
                    g["bbox"][3] = max(g["bbox"][3], top + height)

            for key, g in line_groups.items():
                full_text = " ".join(g["text_parts"]).strip()
                if not full_text:
                    continue
                
                x0, y0, x1, y1 = g["bbox"]
                font_size = max(6.0, (y1 - y0) * 0.8)
                blocks.append(
                    RawBlock(
                        block_id=global_block_id,
                        page_number=page_number,
                        bbox=(x0, y0, x1, y1),
                        text=full_text,
                        font_name="OCR-Tesseract",
                        font_size=font_size,
                        is_bold=False,
                        color=0
                    )
                )
                global_block_id += 1
            if blocks:
                return blocks, global_block_id
        except ImportError:
            pass
        except Exception as e:
            logging.warning(f"Pytesseract fallback failed: {str(e)}")

        logging.warning(f"OCR fallback requested for page {page_number} but neither easyocr nor pytesseract is available or functioning.")
        return [], global_block_id
