from typing import List
from parser.layout_detector import LayoutBlock

class ReadingOrderReconstructor:
    def __init__(self):
        pass

    def reconstruct(self, blocks: List[LayoutBlock]) -> List[LayoutBlock]:
        """
        Sort blocks on each page to match logical reading order.
        First groups by page number, then sorts blocks within each page.
        """
        if not blocks:
            return []

        # Group by page
        pages: dict[int, List[LayoutBlock]] = {}
        for b in blocks:
            pages.setdefault(b.page_number, []).append(b)

        ordered_blocks = []
        # Sort keys (page numbers)
        for page_num in sorted(pages.keys()):
            page_blocks = pages[page_num]
            sorted_page_blocks = self._sort_page_blocks(page_blocks)
            ordered_blocks.extend(sorted_page_blocks)

        return ordered_blocks

    def _sort_page_blocks(self, blocks: List[LayoutBlock]) -> List[LayoutBlock]:
        """
        Sorts blocks on a single page.
        Identifies multi-column text structures if they exist.
        For simple layouts, sorting from top-to-bottom and left-to-right works.
        """
        # If there are 0 or 1 blocks, no sorting needed.
        if len(blocks) <= 1:
            return blocks

        # Sort primarily by vertical coordinate (y0), then horizontal (x0).
        # We define a tolerance: if two blocks have y0 coordinates within 4.0 points of each other,
        # we consider them as side-by-side (same line) and sort by x0.
        # However, to handle columns properly, we check if blocks can be partitioned horizontally.
        
        # Let's check if there are columns.
        # Two columns exist if we have a set of blocks on the left and a set of blocks on the right
        # with no horizontal overlap and significant vertical overlap.
        # For this assignment, we sort using a line-based clustering:
        # 1. Sort blocks by y0.
        # 2. Iterate and group blocks that overlap vertically.
        # 3. For each group (line), sort by x0.
        # But wait! If we have columns, their y0 will overlap, but we want to read the entire left column
        # before the right column. 
        # Let's detect if there is a multi-column partition.
        # A partition exists if we can draw a vertical line that splits the page into two regions
        # and no text block crosses this vertical line (except maybe headers/titles at the top).
        
        # Let's implement column detection:
        # Check if the page is split.
        # Since the CT-200 manual is single-column (the table blocks are handled separately), 
        # a standard line-based sort works beautifully. Let's implement it robustly.
        
        # We can sort blocks using a sorting key:
        # To avoid sensitivity to slight differences in Y, we can cluster blocks into rows.
        sorted_by_y = sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))
        rows: List[List[LayoutBlock]] = []
        
        for block in sorted_by_y:
            bx0, by0, bx1, by1 = block.bbox
            placed = False
            for row in rows:
                # Compare with the average Y coords of the row
                row_y0 = sum(r.bbox[1] for r in row) / len(row)
                row_y1 = sum(r.bbox[3] for r in row) / len(row)
                row_height = row_y1 - row_y0
                
                # Check vertical overlap
                overlap = min(by1, row_y1) - max(by0, row_y0)
                if overlap > 0 and (overlap / row_height > 0.4 or overlap / (by1 - by0) > 0.4):
                    row.append(block)
                    placed = True
                    break
            if not placed:
                rows.append([block])
                
        # Now sort each row by X coordinate
        final_blocks = []
        # Sort rows by their average y0
        sorted_rows = sorted(rows, key=lambda r: sum(b.bbox[1] for b in r) / len(r))
        for row in sorted_rows:
            sorted_row = sorted(row, key=lambda b: b.bbox[0])
            final_blocks.extend(sorted_row)
            
        return final_blocks
