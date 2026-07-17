import re
from typing import Optional, Tuple
from parser.layout_detector import LayoutBlock

class HeadingDetector:
    def __init__(self):
        # Regex to match numbered sections like "1.", "1.1", "2.1.1.1"
        self.number_pattern = re.compile(r"^((?:\d+\.)+\d*|\d+)\s+(.*)$")

    def parse_heading(self, block: LayoutBlock) -> Tuple[int, str, str]:
        """
        Infers the heading level and extracts the raw number and clean heading text.
        Returns: (inferred_level, number_prefix, clean_text)
        
        Levels:
          0: Document Title
          1: Main Section (e.g. 1, 2)
          2: Subsection (e.g. 1.1, 1.2)
          3: Sub-subsection (e.g. 1.1.1)
          4: L4 Subsection (e.g. 2.1.1.1)
        """
        text = block.text.strip()
        
        # Default fallback values
        number_prefix = ""
        clean_text = text
        
        # Title block overrides other rules
        if block.block_type == "Title" or (block.font_size >= 20.0 and block.is_bold):
            return 0, "", text

        # Check for numbering pattern
        match = self.number_pattern.match(text)
        number_level = None
        if match:
            number_prefix = match.group(1).rstrip(".")
            clean_text = match.group(2).strip()
            
            # Level is determined by number of dots in prefix
            # "1" -> no dots -> parts=1 -> level 1
            # "1.1" -> 1 dot -> parts=2 -> level 2
            # "2.1.1.1" -> 3 dots -> parts=4 -> level 4
            parts = number_prefix.split(".")
            number_level = len(parts)

        # Infer based on font size if no numbering is present
        font_level = 3  # default fallback for bold text
        if block.font_size >= 15.0:
            font_level = 1
        elif block.font_size >= 12.0:
            font_level = 2
        elif block.font_size >= 10.5:
            font_level = 3
        else:
            font_level = 4

        # Intelligent resolution of inconsistencies:
        # If we have a numbering prefix, we favor the numbering level because it's the explicit
        # logical structure. E.g. "3.2 Cuff Inflation Sequence" (numbered 3.2, but size is 11.00).
        # Numbering indicates Level 2, but Font Size indicates Level 3. We choose Level 2!
        if number_level is not None:
            inferred_level = number_level
        else:
            # If no number, use font size heuristic
            inferred_level = font_level

        return inferred_level, number_prefix, clean_text
