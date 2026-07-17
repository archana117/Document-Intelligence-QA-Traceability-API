import re
from typing import List, Tuple, Optional
from pydantic import BaseModel, Field
from parser.pdf_loader import RawBlock

class LayoutBlock(BaseModel):
    block_id: int
    page_number: int
    bbox: Tuple[float, float, float, float]
    font_name: str
    font_size: float
    is_bold: bool
    text: str
    block_type: str  # Title, Heading, Paragraph, List, Table, Image, Caption, Footer, Header, Unknown
    confidence: float

class LayoutDetector:
    def __init__(self):
        # Heading regex patterns
        self.heading_number_pattern = re.compile(r"^(\d+\.)+\d*\s+")
        self.bullet_pattern = re.compile(r"^([●•\-\*\s]+|\d+\.\s+)")

    def detect_block_type(
        self,
        block: RawBlock,
        table_bboxes: List[Tuple[float, float, float, float]] = None
    ) -> Tuple[str, float]:
        """
        Classify a block based on text, font size, bold flag, and table boundaries.
        Returns (block_type, confidence).
        """
        text = block.text.strip()
        if not text:
            return "Unknown", 0.0

        # 1. Table Detection
        # Check if block falls inside any table bbox on this page.
        # table_bboxes: list of (x0, y0, x1, y1)
        if table_bboxes:
            bx0, by0, bx1, by1 = block.bbox
            for tx0, ty0, tx1, ty1 in table_bboxes:
                # Calculate intersection ratio
                ix0 = max(bx0, tx0)
                iy0 = max(by0, ty0)
                ix1 = min(bx1, tx1)
                iy1 = min(by1, ty1)
                
                if ix0 < ix1 and iy0 < iy1:
                    area_intersection = (ix1 - ix0) * (iy1 - iy0)
                    area_block = (bx1 - bx0) * (by1 - by0)
                    if area_intersection / area_block > 0.6:  # 60% overlap
                        return "Table", 0.95

        # 2. Title Detection
        # The title is usually very large (e.g. 22pt) and bold.
        if block.font_size >= 20.0 and block.is_bold:
            return "Title", 0.99

        # 3. Heading Detection
        # Level 1 Headings: e.g. "1. Device Overview" (16.5pt, bold)
        if block.font_size >= 15.0 and block.is_bold:
            return "Heading", 0.95

        # Level 2+ Headings: e.g. "1.1 Intended Use" (12.87pt, bold)
        # We also check if it starts with section numbers
        is_numbered = bool(self.heading_number_pattern.match(text))
        if block.font_size >= 12.0 and block.is_bold:
            return "Heading", 0.90
        
        if is_numbered and block.is_bold:
            return "Heading", 0.85

        # 4. List Detection
        # Bullet list: starts with ●, •, -, *
        # Ordered list: starts with "1. ", "2. ", etc. (but not bold headings)
        is_bullet = text.startswith(('●', '•', '-', '*'))
        is_ordered_list = bool(re.match(r"^\d+\.\s+", text))
        if is_bullet or (is_ordered_list and not block.is_bold):
            return "List", 0.90

        # 5. Caption Detection
        # Captions are typically smaller fonts (e.g. < 10pt) or start with "Figure", "Table"
        is_caption_text = text.lower().startswith(("figure", "fig.", "caption", "table "))
        if block.font_size < 10.0 or (is_caption_text and block.font_size <= 11.0):
            return "Caption", 0.80

        # 6. Default to Paragraph
        return "Paragraph", 0.80

    def process_page(
        self,
        page_blocks: List[RawBlock],
        table_bboxes: List[Tuple[float, float, float, float]] = None
    ) -> List[LayoutBlock]:
        layout_blocks = []
        for block in page_blocks:
            block_type, conf = self.detect_type_advanced(block, table_bboxes)
            layout_blocks.append(
                LayoutBlock(
                    block_id=block.block_id,
                    page_number=block.page_number,
                    bbox=block.bbox,
                    font_name=block.font_name,
                    font_size=block.font_size,
                    is_bold=block.is_bold,
                    text=block.text,
                    block_type=block_type,
                    confidence=conf
                )
            )
        return layout_blocks

    def detect_type_advanced(
        self,
        block: RawBlock,
        table_bboxes: List[Tuple[float, float, float, float]] = None
    ) -> Tuple[str, float]:
        # Helper to do the classification
        return self.detect_block_type(block, table_bboxes)
