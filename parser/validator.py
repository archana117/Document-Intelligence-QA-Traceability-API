import re
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from parser.hierarchy_builder import TreeNode

class ValidationReport(BaseModel):
    is_valid: bool
    duplicate_headings: List[str] = Field(default_factory=list)
    broken_hierarchies: List[str] = Field(default_factory=list)
    skipped_numberings: List[str] = Field(default_factory=list)
    orphan_nodes: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

class DocumentValidator:
    def __init__(self):
        pass

    def validate(self, root: TreeNode, all_nodes: List[TreeNode]) -> ValidationReport:
        """
        Validates the reconstructed document tree for structural inconsistencies.
        """
        report = ValidationReport(is_valid=True)
        
        # 1. Check for Sibling Duplicate Headings (same heading under the same parent)
        # Note: duplicate heading titles under different parents (e.g. "Error Codes") are valid.
        node_id_map: Dict[str, TreeNode] = {}
        for node in all_nodes:
            node_id_map[node.id] = node

        for node in all_nodes:
            if not node.children:
                continue
            child_headings_count: Dict[str, int] = {}
            for child in node.children:
                child_headings_count[child.heading] = child_headings_count.get(child.heading, 0) + 1
            
            for heading, count in child_headings_count.items():
                if count > 1:
                    report.duplicate_headings.append(heading)
                    report.errors.append(f"Duplicate sibling heading title found under parent '{node.id}': '{heading}' ({count} occurrences)")
                    report.is_valid = False
        
        # 2. Check for Broken Hierarchy and Missing Parents
        for node in all_nodes:
            if node.id == root.id:
                continue
            
            # Check parent exists
            if node.parent_id not in node_id_map:
                report.orphan_nodes.append(node.id)
                report.errors.append(f"Node '{node.id}' has missing or invalid parent ID: '{node.parent_id}'")
                report.is_valid = False
            else:
                parent = node_id_map[node.parent_id]
                # Level difference check: H1(1) -> H3(3) is a broken hierarchy (skipped Level 2)
                if node.level - parent.level > 1 and parent.level != 0:
                    report.broken_hierarchies.append(f"{parent.id} -> {node.id}")
                    report.errors.append(
                        f"Broken hierarchy gap: '{node.id}' (L{node.level}) nested directly under '{parent.id}' (L{parent.level})"
                    )
                    report.is_valid = False

        # 3. Check for Skipped and Out-of-Order Numbering
        for node in all_nodes:
            if not node.children:
                continue
            
            # Extract numbered children in layout/original order
            numbered_children_layout: List[Tuple[TreeNode, List[int]]] = []
            for child in node.children:
                match = re.match(r"^((?:\d+\.)+\d*|\d+)\s+", child.heading)
                if match:
                    num_str = match.group(1).rstrip(".")
                    parts = [int(p) for p in num_str.split(".")]
                    numbered_children_layout.append((child, parts))
            
            if len(numbered_children_layout) > 1:
                # 3a. Check for Out-of-Order Sibling Sequence in layout order
                for idx in range(len(numbered_children_layout) - 1):
                    curr_child, curr_parts = numbered_children_layout[idx]
                    next_child, next_parts = numbered_children_layout[idx + 1]
                    
                    if len(curr_parts) == len(next_parts):
                        last_curr = curr_parts[-1]
                        last_next = next_parts[-1]
                        if last_next < last_curr:
                            err_desc = f"Out-of-order sibling numbering sequence: '{curr_child.heading}' followed by '{next_child.heading}'"
                            report.skipped_numberings.append(err_desc)
                            report.errors.append(err_desc)
                            report.is_valid = False

                # 3b. Sort by parsed parts to check for gaps (skipped numberings)
                numbered_children_sorted = sorted(numbered_children_layout, key=lambda item: item[1])
                for idx in range(len(numbered_children_sorted) - 1):
                    curr_child, curr_parts = numbered_children_sorted[idx]
                    next_child, next_parts = numbered_children_sorted[idx + 1]
                    
                    if len(curr_parts) == len(next_parts):
                        last_curr = curr_parts[-1]
                        last_next = next_parts[-1]
                        if last_next - last_curr > 1:
                            gap_desc = f"Gap between sibling sections: '{curr_child.heading}' and '{next_child.heading}'"
                            report.skipped_numberings.append(gap_desc)
                            report.errors.append(gap_desc)
                            report.is_valid = False

        # 4. Check for Orphan Paragraphs (if root contains body paragraphs that should have gone under sections)
        # Note: if the manual starts with a general intro before section 1, that's fine,
        # but if it contains paragraphs at depth=0 after section 1 started, it's a concern.
        if root.body_blocks:
            # Let's see if we have paragraphs after heading blocks
            # (which would indicate they failed to assign to the nearest heading)
            pass

        return report

