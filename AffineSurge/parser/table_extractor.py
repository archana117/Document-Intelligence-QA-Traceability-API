import json
from typing import List, Dict, Any, Tuple, Optional
import pdfplumber

class TableExtractor:
    def __init__(self, filepath: str):
        self.filepath = filepath

    def extract_tables_metadata(self) -> Dict[int, List[Dict[str, Any]]]:
        """
        Extracts table bounds (bboxes) and structured JSON content per page.
        Returns:
          Dict[page_number, List[TableMetadata]]
          where TableMetadata contains:
            bbox: (x0, y0, x1, y1)
            content: {headers: [...], rows: [[...], [...]]}
        """
        tables_by_page: Dict[int, List[Dict[str, Any]]] = {}

        with pdfplumber.open(self.filepath) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                page_num = page_idx + 1
                tables_by_page[page_num] = []

                # Find table objects
                plumber_tables = page.find_tables()
                if not plumber_tables:
                    continue

                # Sometimes pdfplumber returns nested or overlapping tables
                # We filter to keep only unique/outer tables
                outer_tables = self._filter_outer_tables(plumber_tables)

                for table_obj in outer_tables:
                    # extract table cells as text
                    table_data = table_obj.extract()
                    if not table_data or len(table_data) < 2:
                        continue

                    # Filter rows and clean up None values
                    cleaned_rows = []
                    for row in table_data:
                        cleaned_row = []
                        for cell in row:
                            if cell is None:
                                cleaned_row.append("")
                            else:
                                cleaned_row.append(cell.strip())
                        cleaned_rows.append(cleaned_row)

                    # Extract headers and body rows
                    headers = cleaned_rows[0]
                    rows = cleaned_rows[1:]

                    tables_by_page[page_num].append({
                        "bbox": table_obj.bbox,  # (x0, y0, x1, y1)
                        "content": {
                            "headers": headers,
                            "rows": rows
                        }
                    })

        return tables_by_page

    def _filter_outer_tables(self, tables) -> List[Any]:
        """Filters out tables that are completely inside other tables."""
        sorted_tables = sorted(tables, key=lambda t: self._bbox_area(t.bbox), reverse=True)
        outer = []
        for t in sorted_tables:
            is_inside = False
            tx0, ty0, tx1, ty1 = t.bbox
            for o in outer:
                ox0, oy0, ox1, oy1 = o.bbox
                if tx0 >= ox0 and ty0 >= oy0 and tx1 <= ox1 and ty1 <= oy1:
                    is_inside = True
                    break
            if not is_inside:
                outer.append(t)
        return outer

    def _bbox_area(self, bbox: Tuple[float, float, float, float]) -> float:
        return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
