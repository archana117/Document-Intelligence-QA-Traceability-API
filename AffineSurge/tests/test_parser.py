import pytest
from parser.layout_detector import LayoutBlock, RawBlock, LayoutDetector
from parser.heading_detector import HeadingDetector
from parser.hierarchy_builder import HierarchyBuilder, TreeNode
from parser.paragraph_assigner import ParagraphAssigner
from parser.hashing import ContentHasher
from parser.validator import DocumentValidator

def test_heading_detection():
    detector = HeadingDetector()
    
    # Test Level 1 heading
    block_h1 = LayoutBlock(
        block_id=1, page_number=1, bbox=(10, 10, 100, 30),
        font_name="NimbusSans-Bold", font_size=16.50, is_bold=True,
        text="1. Device Overview", block_type="Heading", confidence=0.9
    )
    level, num_pref, clean_text = detector.parse_heading(block_h1)
    assert level == 1
    assert num_pref == "1"
    assert clean_text == "Device Overview"

    # Test Level 2 heading
    block_h2 = LayoutBlock(
        block_id=2, page_number=1, bbox=(10, 40, 100, 60),
        font_name="NimbusSans-Bold", font_size=12.87, is_bold=True,
        text="1.1 Intended Use", block_type="Heading", confidence=0.9
    )
    level, num_pref, clean_text = detector.parse_heading(block_h2)
    assert level == 2
    assert num_pref == "1.1"
    assert clean_text == "Intended Use"

    # Test Heading level formatting irregularity (numbered 3.2 but font size 11.0)
    block_irreg = LayoutBlock(
        block_id=3, page_number=3, bbox=(10, 80, 100, 100),
        font_name="NimbusSans-Bold", font_size=11.00, is_bold=True,
        text="3.2 Cuff Inflation Sequence", block_type="Heading", confidence=0.9
    )
    level, num_pref, clean_text = detector.parse_heading(block_irreg)
    assert level == 2  # Inferred level should be 2 because numbering is "3.2"
    assert num_pref == "3.2"

def test_hierarchy_tree_construction():
    builder = HierarchyBuilder()
    
    # Construct sequence of headings
    blocks = [
        LayoutBlock(block_id=0, page_number=1, bbox=(10, 10, 100, 20), font_name="NimbusSans-Bold", font_size=22.0, is_bold=True, text="CardioTrack Manual", block_type="Title", confidence=0.9),
        LayoutBlock(block_id=1, page_number=1, bbox=(10, 30, 100, 40), font_name="NimbusSans-Bold", font_size=16.5, is_bold=True, text="1. Overview", block_type="Heading", confidence=0.9),
        LayoutBlock(block_id=2, page_number=1, bbox=(10, 50, 100, 60), font_name="NimbusSans-Bold", font_size=12.87, is_bold=True, text="1.1 Intended Use", block_type="Heading", confidence=0.9),
        LayoutBlock(block_id=3, page_number=1, bbox=(10, 70, 100, 80), font_name="NimbusSans-Bold", font_size=12.87, is_bold=True, text="1.2 Contraindications", block_type="Heading", confidence=0.9),
        LayoutBlock(block_id=4, page_number=1, bbox=(10, 90, 100, 100), font_name="NimbusSans-Bold", font_size=16.5, is_bold=True, text="2. Specifications", block_type="Heading", confidence=0.9)
    ]
    
    root = builder.build_tree(blocks)
    assert root.id == "sec_cardiotrack_manual"
    assert root.level == 0
    assert len(root.children) == 2  # H1: sec_1 (Overview) and sec_2 (Specifications)
    
    sec_1 = root.children[0]
    assert sec_1.id == "sec_1"
    assert len(sec_1.children) == 2  # Subsections: 1.1 and 1.2
    
    sec_1_1 = sec_1.children[0]
    assert sec_1_1.id == "sec_1_1"
    assert sec_1_1.parent_id == "sec_1"

def test_paragraph_assignment_and_orphans():
    # Sequence containing headings and paragraphs
    blocks = [
        # Paragraph before first heading (Orphan)
        LayoutBlock(block_id=0, page_number=1, bbox=(10, 10, 100, 20), font_name="NimbusSans-Regular", font_size=11.0, is_bold=False, text="This is introduction text.", block_type="Paragraph", confidence=0.8),
        # Heading 1
        LayoutBlock(block_id=1, page_number=1, bbox=(10, 30, 100, 40), font_name="NimbusSans-Bold", font_size=16.5, is_bold=True, text="1. Section 1", block_type="Heading", confidence=0.9),
        # Paragraph inside Section 1
        LayoutBlock(block_id=2, page_number=1, bbox=(10, 50, 100, 60), font_name="NimbusSans-Regular", font_size=11.0, is_bold=False, text="Paragraph in section 1.", block_type="Paragraph", confidence=0.8),
        # List item inside Section 1
        LayoutBlock(block_id=3, page_number=1, bbox=(10, 70, 100, 80), font_name="NimbusSans-Regular", font_size=11.0, is_bold=False, text="● Bullet point.", block_type="List", confidence=0.8)
    ]
    
    builder = HierarchyBuilder()
    root = builder.build_tree(blocks)
    
    assigner = ParagraphAssigner()
    orphans = assigner.assign(blocks, root, builder.heading_node_map)
    
    # Assert orphan paragraphs detected correctly
    assert len(orphans) == 1
    assert orphans[0].text == "This is introduction text."
    
    # Assert section 1 contains assigned body paragraphs
    sec_1 = root.children[0]
    assert len(sec_1.body_blocks) == 2
    assert sec_1.body_blocks[0].text == "Paragraph in section 1."
    assert sec_1.body_blocks[1].block_type == "List"

def test_content_hashing():
    hash1 = ContentHasher.compute_hash("Section 1", "This is the body paragraph.")
    hash2 = ContentHasher.compute_hash("Section 1", "This is the body paragraph. ")
    hash3 = ContentHasher.compute_hash("Section 1", "Different paragraph.")
    
    # Assert whitespace normalization ignores padding differences
    assert hash1 == hash2
    # Assert content changes produce different hashes
    assert hash1 != hash3

def test_validator_diagnostics():
    validator = DocumentValidator()
    
    # 1. Test broken hierarchy (skipping Level 2, e.g. H1 directly nesting H3)
    root = TreeNode(id="doc_root", level=0, heading="Manual", page_number=1, bbox=[0,0,0,0], depth=0)
    parent = TreeNode(id="sec_1", level=1, heading="1. Section 1", page_number=1, bbox=[0,0,0,0], parent_id="doc_root", depth=1)
    child = TreeNode(id="sec_1_1_1", level=3, heading="1.1.1 Sub-sub", page_number=1, bbox=[0,0,0,0], parent_id="sec_1", depth=2)
    
    root.children.append(parent)
    parent.children.append(child)
    
    all_nodes = [root, parent, child]
    report = validator.validate(root, all_nodes)
    assert report.is_valid is False
    assert len(report.broken_hierarchies) == 1

    # 2. Test skipped numbering (e.g. 1.1 followed by 1.3)
    root2 = TreeNode(id="doc_root", level=0, heading="Manual", page_number=1, bbox=[0,0,0,0], depth=0)
    h1 = TreeNode(id="sec_1", level=1, heading="1. Section 1", page_number=1, bbox=[0,0,0,0], parent_id="doc_root", depth=1)
    h1_1 = TreeNode(id="sec_1_1", level=2, heading="1.1 Sub 1", page_number=1, bbox=[0,0,0,0], parent_id="sec_1", depth=2)
    h1_3 = TreeNode(id="sec_1_3", level=2, heading="1.3 Sub 3", page_number=1, bbox=[0,0,0,0], parent_id="sec_1", depth=2)
    
    root2.children.append(h1)
    h1.children.append(h1_1)
    h1.children.append(h1_3)
    
    all_nodes2 = [root2, h1, h1_1, h1_3]
    report2 = validator.validate(root2, all_nodes2)
    assert report2.is_valid is False
    assert len(report2.skipped_numberings) == 1

def test_list_and_table_layout_detection():
    detector = LayoutDetector()
    
    # 1. Test List item bullet detection
    block_bullet = RawBlock(
        block_id=1, page_number=1, bbox=(33.0, 100.0, 300.0, 115.0),
        text="● This is a bullet point", font_name="NimbusSans-Regular", font_size=11.0, is_bold=False, color=0
    )
    btype, conf = detector.detect_block_type(block_bullet)
    assert btype == "List"
    
    # 2. Test List item numbered list detection
    block_num_list = RawBlock(
        block_id=2, page_number=1, bbox=(33.0, 120.0, 300.0, 135.0),
        text="1. Normal operating pressure is high", font_name="NimbusSans-Regular", font_size=11.0, is_bold=False, color=0
    )
    btype, conf = detector.detect_block_type(block_num_list)
    assert btype == "List"
    
    # 3. Test Table block intersection classification
    block_cell = RawBlock(
        block_id=3, page_number=2, bbox=(40.0, 100.0, 150.0, 115.0),
        text="Measurement method", font_name="NimbusSans-Regular", font_size=11.0, is_bold=False, color=0
    )
    
    # Inside table bbox
    table_bboxes = [(35.0, 95.0, 350.0, 200.0)]
    btype, conf = detector.detect_block_type(block_cell, table_bboxes)
    assert btype == "Table"

