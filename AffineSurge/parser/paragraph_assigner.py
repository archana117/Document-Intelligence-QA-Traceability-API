import re
from typing import List, Dict, Tuple, Optional, Any
from parser.layout_detector import LayoutBlock
from parser.hierarchy_builder import TreeNode

class ParagraphAssigner:
    def __init__(self):
        pass

    def assign(
        self,
        ordered_blocks: List[LayoutBlock],
        root_node: TreeNode,
        heading_node_map: Dict[int, TreeNode]
    ) -> List[LayoutBlock]:
        """
        Attaches body paragraphs, lists, and table blocks to the nearest preceding heading node.
        Returns a list of orphan blocks that were not assigned to any heading.
        """
        orphans: List[LayoutBlock] = []
        current_heading_node: Optional[TreeNode] = None

        # First, clear any existing body_blocks on all nodes in the tree
        self._clear_body_blocks(root_node)

        for block in ordered_blocks:
            if block.block_type in ("Title", "Heading"):
                # Update current heading node
                current_heading_node = heading_node_map.get(block.block_id)
            elif block.block_type in ("Paragraph", "List", "Table", "Image", "Caption", "Unknown"):
                if current_heading_node is not None:
                    current_heading_node.body_blocks.append(block)
                else:
                    # No heading has been encountered yet
                    orphans.append(block)
                    # Fallback: assign to root node
                    root_node.body_blocks.append(block)
            else:
                # E.g. Footer, Header (we can skip or treat as orphans/metadata)
                pass

        return orphans

    def _clear_body_blocks(self, node: TreeNode):
        node.body_blocks = []
        for child in node.children:
            self._clear_body_blocks(child)

    def extract_structured_lists(self, body_blocks: List[LayoutBlock]) -> List[Dict[str, Any]]:
        """
        Processes body blocks of a node, groups contiguous list items,
        and returns them as structured list objects.
        """
        structured_lists = []
        current_list_items = []
        current_list_type = None
        current_page = None

        for block in body_blocks:
            if block.block_type == "List":
                text = block.text.strip()
                if not text:
                    continue
                # Detect list type
                if text.startswith(('●', '•', '-', '*')):
                    list_type = "bullet"
                    clean_text = re.sub(r'^[●•\-\*\s]+', '', text).strip()
                else:
                    # Check if it starts with numbering like "1. ", "1) "
                    list_type = "ordered"
                    clean_text = re.sub(r'^\d+[\.\)]\s*', '', text).strip()

                if current_list_type is None:
                    current_list_type = list_type
                    current_page = block.page_number
                    current_list_items.append(clean_text)
                elif current_list_type == list_type:
                    current_list_items.append(clean_text)
                else:
                    # Type changed, save previous list
                    structured_lists.append({
                        "type": current_list_type,
                        "items": current_list_items,
                        "page_number": current_page
                    })
                    current_list_type = list_type
                    current_page = block.page_number
                    current_list_items = [clean_text]
            else:
                if current_list_items:
                    # Save current list when encountering non-list block
                    structured_lists.append({
                        "type": current_list_type,
                        "items": current_list_items,
                        "page_number": current_page
                    })
                    current_list_items = []
                    current_list_type = None
                    current_page = None

        # Add any remaining list
        if current_list_items:
            structured_lists.append({
                "type": current_list_type,
                "items": current_list_items,
                "page_number": current_page
            })

        return structured_lists
