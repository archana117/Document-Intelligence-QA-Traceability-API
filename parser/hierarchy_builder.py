import re
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from parser.layout_detector import LayoutBlock
from parser.heading_detector import HeadingDetector

class TreeNode(BaseModel):
    id: str                         # Stable ID e.g., sec_1, sec_1_1
    level: int                      # Heading level (0=Title, 1=H1, 2=H2, etc.)
    heading: str                    # Section heading text
    title: Optional[str] = None     # Clean section title without numbers
    section_number: Optional[str] = None # Parsed section number prefix
    body_text: str = ""             # Clean concatenated body text paragraphs
    body_blocks: List[LayoutBlock] = Field(default_factory=list)  # Associated text paragraphs, lists
    page_number: int
    bbox: List[float]               # Bounding box of the heading block
    children: List["TreeNode"] = Field(default_factory=list)
    parent_id: Optional[str] = None
    depth: int = 0
    content_hash: str = ""
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    lists: List[Dict[str, Any]] = Field(default_factory=list)
    figures: List[Dict[str, Any]] = Field(default_factory=list)

    def get_body_text(self) -> str:
        """Concatenates all body blocks into a single string."""
        texts = []
        for b in self.body_blocks:
            texts.append(b.text)
        return "\n\n".join(texts)

# Required for Pydantic self-referential model resolution
TreeNode.model_rebuild()

class HierarchyBuilder:
    def __init__(self):
        self.heading_detector = HeadingDetector()
        self.heading_node_map: Dict[int, TreeNode] = {}

    def build_tree(self, ordered_blocks: List[LayoutBlock]) -> TreeNode:
        """
        Processes heading blocks, establishes nesting hierarchy, and returns
        a root TreeNode (representing the document/title).
        """
        self.heading_node_map = {}
        heading_blocks = [b for b in ordered_blocks if b.block_type in ("Title", "Heading")]
        
        if not heading_blocks:
            # Fallback if no headings found, create a dummy root
            return TreeNode(
                id="doc_root",
                level=0,
                heading="Document Root",
                title="Document Root",
                section_number="",
                page_number=1,
                bbox=[0.0, 0.0, 0.0, 0.0],
                depth=0
            )

        first_block = heading_blocks[0]
        level, num_pref, text = self.heading_detector.parse_heading(first_block)
        
        if level == 0:
            # First block is the Title
            root_node = TreeNode(
                id=self._generate_stable_id(level, num_pref, text, "root"),
                level=0,
                heading=text,
                title=text,
                section_number="",
                page_number=first_block.page_number,
                bbox=list(first_block.bbox),
                depth=0
            )
            stack: List[TreeNode] = [root_node]
            self.heading_node_map[first_block.block_id] = root_node
            blocks_to_process = heading_blocks[1:]
        else:
            # First block is a standard heading. Create a dummy document root.
            root_node = TreeNode(
                id="doc_root",
                level=0,
                heading="Document Root",
                title="Document Root",
                section_number="",
                page_number=first_block.page_number,
                bbox=[0.0, 0.0, 0.0, 0.0],
                depth=0
            )
            stack: List[TreeNode] = [root_node]
            blocks_to_process = heading_blocks

        for block in blocks_to_process:
            lvl, num_pref, text = self.heading_detector.parse_heading(block)
            
            # Find parent by popping from stack until we find a node with a smaller level
            while stack and stack[-1].level >= lvl:
                stack.pop()

            parent = stack[-1] if stack else root_node
            
            # Generate a stable ID based on hierarchy path
            parent_suffix = parent.id.replace("sec_", "")
            node_id = self._generate_stable_id(lvl, num_pref, text, parent_suffix)
            
            node = TreeNode(
                id=node_id,
                level=lvl,
                heading=block.text,
                title=text,
                section_number=num_pref if num_pref else None,
                page_number=block.page_number,
                bbox=list(block.bbox),
                parent_id=parent.id,
                depth=parent.depth + 1
            )
            
            parent.children.append(node)
            stack.append(node)
            self.heading_node_map[block.block_id] = node

        return root_node

    def _generate_stable_id(self, level: int, num_pref: str, text: str, parent_suffix: str) -> str:
        """
        Generates a stable node ID like 'sec_1_1' or 'sec_overview'.
        If numbering is present, we use the numbering e.g. 'sec_1_1'.
        Otherwise we generate a clean slug from the text.
        """
        if num_pref:
            # Replace dots with underscores
            clean_num = num_pref.replace(".", "_")
            return f"sec_{clean_num}"
        
        # Slugify text
        slug = re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')
        if not slug:
            slug = f"lvl{level}"
        
        # Make it unique by prefixing parent suffix
        if parent_suffix and parent_suffix != "root" and parent_suffix != "doc_root":
            return f"sec_{parent_suffix}_{slug}"
        return f"sec_{slug}"
