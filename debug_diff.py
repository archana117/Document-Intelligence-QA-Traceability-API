import sys
import os
import json
import fitz

# Setup path
sys.path.insert(0, "C:/Users/vyshn/Downloads/AffineSurge")

from app.database import SessionLocal, init_db
from models.db_models import Document, Node
from parser.pdf_loader import PDFLoader
from parser.layout_detector import LayoutDetector
from parser.reading_order import ReadingOrderReconstructor
from parser.hierarchy_builder import HierarchyBuilder, TreeNode
from parser.paragraph_assigner import ParagraphAssigner
from parser.table_extractor import TableExtractor
from parser.image_extractor import ImageExtractor
from parser.hashing import ContentHasher
from app.repository import DocumentRepository

def ingest_pdf_direct(filepath: str, version: int, doc_name: str):
    db = SessionLocal()
    # Loader
    loader = PDFLoader(filepath)
    doc_data = loader.load()
    
    # Table Extraction
    table_extractor = TableExtractor(filepath)
    tables_by_page = table_extractor.extract_tables_metadata()
    table_bboxes_by_page = {page_num: [t["bbox"] for t in page_tables] for page_num, page_tables in tables_by_page.items()}
    
    # Layout Detector
    detector = LayoutDetector()
    layout_blocks = []
    for page in doc_data.pages:
        tb_bboxes = table_bboxes_by_page.get(page.page_number, [])
        page_layout = detector.process_page(page.blocks, tb_bboxes)
        layout_blocks.extend(page_layout)
        
    # Reading Order
    order_reconstructor = ReadingOrderReconstructor()
    ordered_blocks = order_reconstructor.reconstruct(layout_blocks)
    
    # Hierarchy
    builder = HierarchyBuilder()
    root_node = builder.build_tree(ordered_blocks)
    
    # Paragraph Assignment
    assigner = ParagraphAssigner()
    assigner.assign(ordered_blocks, root_node, builder.heading_node_map)
    
    # Flatten and hash
    flat_nodes = []
    def traverse(node):
        flat_nodes.append(node)
        for child in node.children:
            traverse(child)
    traverse(root_node)
    
    for node in flat_nodes:
        # Resolve table cells
        new_blocks = []
        for b in node.body_blocks:
            if b.block_type == "Table":
                matched_table = None
                p_tables = tables_by_page.get(b.page_number, [])
                for pt in p_tables:
                    bx0, by0, bx1, by1 = b.bbox
                    tx0, ty0, tx1, ty1 = pt["bbox"]
                    if max(bx0, tx0) < min(bx1, tx1) and max(by0, ty0) < min(by1, ty1):
                        matched_table = pt["content"]
                        break
                if matched_table:
                    b.text = f"[Structured Table Data: {json.dumps(matched_table)}]"
            new_blocks.append(b)
        node.body_blocks = new_blocks
        node.content_hash = ContentHasher.compute_hash(node.heading, node.get_body_text())
        
    # Clear existing
    repo = DocumentRepository()
    existing = repo.get_document_by_version(db, doc_name, version)
    if existing:
        db.delete(existing)
        db.commit()
        
    repo.save_parsed_document(db, doc_name, version, root_node, flat_nodes)
    db.close()
    print(f"Successfully ingested {filepath} version {version}")

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    init_db()
    # Ingest v1 and v2
    ingest_pdf_direct("ct200_manual.pdf", 1, "Debug-Monitor")
    ingest_pdf_direct("ct200_manual_v2.pdf", 2, "Debug-Monitor")
    
    # Inspect
    db = SessionLocal()
    nodes_v1 = db.query(Node).join(Document).filter(Document.name == "Debug-Monitor", Document.version == 1).all()
    nodes_v2 = db.query(Node).join(Document).filter(Document.name == "Debug-Monitor", Document.version == 2).all()
    
    print("\n--- VERSION 1 NODES ---")
    for n in nodes_v1:
        print(f"Node ID: {n.node_id} | Heading: '{n.heading}'")
        
    print("\n--- VERSION 2 NODES ---")
    for n in nodes_v2:
        print(f"Node ID: {n.node_id} | Heading: '{n.heading}'")
        
    # Run a test diff on sec_2_1_1_1
    repo = DocumentRepository()
    diff = repo.diff_node_versions(db, "Debug-Monitor", "sec_2_1_1_1", 1, 2)
    print("\n--- DIFF FOR sec_2_1_1_1 ---")
    print(json.dumps(diff, indent=2))
    db.close()

if __name__ == "__main__":
    main()
