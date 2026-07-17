import difflib
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from models.db_models import Document, Node, Selection, Generation, selection_node_association
from parser.hierarchy_builder import TreeNode

class DocumentRepository:
    def __init__(self):
        pass

    def save_parsed_document(
        self,
        db: Session,
        name: str,
        version: int,
        root_node: TreeNode,
        flat_nodes: List[TreeNode]
    ) -> Document:
        """
        Saves a parsed document tree to the database.
        Resolves parent-child keys dynamically after database insertion.
        """
        # Create Document record
        doc = Document(name=name, version=version)
        db.add(doc)
        db.flush()  # Generates doc.id

        # Insert Node records in flat form (temporary parent_id link)
        db_nodes: Dict[str, Node] = {}
        for tn in flat_nodes:
            # We store bbox as JSON string
            bbox_str = json.dumps(tn.bbox)
            
            db_node = Node(
                node_id=tn.id,
                document_id=doc.id,
                level=tn.level,
                heading=tn.heading,
                body=tn.get_body_text(),
                title=tn.title,
                section_number=tn.section_number,
                body_text=tn.body_text,
                page_number=tn.page_number,
                bbox=bbox_str,
                content_hash=tn.content_hash,
                depth=tn.depth,
                tables=json.dumps(tn.tables),
                lists=json.dumps(tn.lists),
                figures=json.dumps(tn.figures)
            )
            db.add(db_node)
            db_nodes[tn.id] = db_node

        db.flush()  # Generates auto-increment IDs for all nodes

        # Update parent relationships using inserted db IDs
        for tn in flat_nodes:
            if tn.parent_id and tn.parent_id in db_nodes:
                db_nodes[tn.id].parent_id = db_nodes[tn.parent_id].id

        db.commit()
        db.refresh(doc)
        return doc

    def get_latest_document_version(self, db: Session, name: str) -> Optional[int]:
        """Returns the highest version number for a document by name."""
        result = db.query(Document).filter(Document.name == name).order_by(Document.version.desc()).first()
        return result.version if result else None

    def get_document_tree(self, db: Session, doc_id: int) -> Optional[Document]:
        """Retrieves document metadata by id."""
        return db.query(Document).filter(Document.id == doc_id).first()

    def get_document_by_version(self, db: Session, name: str, version: int) -> Optional[Document]:
        """Retrieves document metadata by name and version."""
        return db.query(Document).filter(and_(Document.name == name, Document.version == version)).first()

    def assemble_tree(self, db: Session, doc_id: int) -> List[Dict[str, Any]]:
        """
        Queries all nodes for a document and reconstructs the nested tree.
        """
        nodes = db.query(Node).filter(Node.document_id == doc_id).all()
        if not nodes:
            return []

        # Map auto-increment ID to serialized node dictionaries
        node_map: Dict[int, Dict[str, Any]] = {}
        for n in nodes:
            node_map[n.id] = {
                "id": n.id,
                "node_id": n.node_id,
                "level": n.level,
                "heading": n.heading,
                "body": n.body,
                "title": n.title if n.title else n.heading,
                "section_number": n.section_number if n.section_number else "",
                "body_text": n.body_text if n.body_text else n.body,
                "page_number": n.page_number,
                "bbox": json.loads(n.bbox) if n.bbox else [],
                "content_hash": n.content_hash,
                "depth": n.depth,
                "tables": json.loads(n.tables) if n.tables else [],
                "lists": json.loads(n.lists) if n.lists else [],
                "figures": json.loads(n.figures) if n.figures else [],
                "children": []
            }

        # Build tree by nesting children under parents
        root_nodes = []
        for n in nodes:
            serialized = node_map[n.id]
            if n.parent_id is None:
                root_nodes.append(serialized)
            else:
                parent_serialized = node_map.get(n.parent_id)
                if parent_serialized:
                    parent_serialized["children"].append(serialized)
                else:
                    root_nodes.append(serialized)

        return root_nodes

    def search_nodes(self, db: Session, query: str, doc_id: int) -> List[Node]:
        """Filters nodes in a specific document containing query in heading or body."""
        return db.query(Node).filter(
            and_(
                Node.document_id == doc_id,
                or_(
                    Node.heading.ilike(f"%{query}%"),
                    Node.body.ilike(f"%{query}%")
                )
            )
        ).all()

    def save_selection(
        self,
        db: Session,
        name: str,
        document_id: int,
        version: int,
        node_ids: List[str]
    ) -> Selection:
        """
        Creates a version-pinned selection of nodes.
        Locates the SQLite primary keys of the given stable node IDs.
        """
        selection_id = str(uuid.uuid4())
        
        # Query the nodes in the database that match these stable node_ids
        db_nodes = db.query(Node).filter(
            and_(
                Node.document_id == document_id,
                Node.node_id.in_(node_ids)
            )
        ).all()

        selection = Selection(
            id=selection_id,
            name=name,
            document_id=document_id,
            version=version
        )
        # Link relationships
        selection.nodes.extend(db_nodes)

        db.add(selection)
        db.commit()
        db.refresh(selection)
        return selection

    def get_selection(self, db: Session, selection_id: str) -> Optional[Selection]:
        return db.query(Selection).filter(Selection.id == selection_id).first()

    def save_generation(
        self,
        db: Session,
        selection_id: str,
        node_id: str,
        content_hash: str,
        test_cases: List[Dict[str, Any]]
    ) -> Generation:
        """
        Saves generated test cases linked to selection and node state.
        If an entry already exists for this selection and node, we overwrite it.
        """
        gen_id = f"gen_{selection_id}_{node_id}"
        
        # Check if exists
        existing = db.query(Generation).filter(Generation.id == gen_id).first()
        if existing:
            existing.content_hash = content_hash
            existing.test_cases = json.dumps(test_cases)
            existing.created_at = datetime.utcnow()
            existing.is_stale = False
            db.commit()
            db.refresh(existing)
            return existing

        gen = Generation(
            id=gen_id,
            selection_id=selection_id,
            node_id=node_id,
            content_hash=content_hash,
            test_cases=json.dumps(test_cases),
            is_stale=False
        )
        db.add(gen)
        db.commit()
        db.refresh(gen)
        return gen

    def check_selection_staleness(self, db: Session, selection_id: str) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Validates LLM-generated test cases against the latest document version.
        Checks if the content has changed since the test cases were created.
        """
        selection = self.get_selection(db, selection_id)
        if not selection:
            return False, []

        # Find the latest version of this document
        doc_metadata = db.query(Document).filter(Document.id == selection.document_id).first()
        if not doc_metadata:
            return False, []
            
        latest_doc = db.query(Document).filter(
            Document.name == doc_metadata.name
        ).order_by(Document.version.desc()).first()

        is_selection_stale = False
        generations_status = []

        # Get all generations for this selection
        generations = db.query(Generation).filter(Generation.selection_id == selection_id).all()
        
        for gen in generations:
            # Query the corresponding node in the latest document version
            latest_node = db.query(Node).filter(
                and_(
                    Node.document_id == latest_doc.id,
                    Node.node_id == gen.node_id
                )
            ).first()

            is_node_stale = False
            if not latest_node:
                # The section was deleted in the newer version
                is_node_stale = True
                is_selection_stale = True
            elif latest_node.content_hash != gen.content_hash:
                # The content hash has changed
                is_node_stale = True
                is_selection_stale = True
                
                # Update the generation database flag as well
                gen.is_stale = True
                db.commit()

            generations_status.append({
                "node_id": gen.node_id,
                "node_heading": latest_node.heading if latest_node else "Deleted Section",
                "content_hash": gen.content_hash,
                "is_stale": is_node_stale,
                "test_cases": json.loads(gen.test_cases)
            })

        return is_selection_stale, generations_status

    def diff_node_versions(
        self,
        db: Session,
        doc_name: str,
        node_id: str,
        v1_ver: int,
        v2_ver: int
    ) -> Dict[str, Any]:
        """
        Creates a side-by-side diff comparison for a section node across two versions.
        """
        # Fetch document metadata
        doc1 = self.get_document_by_version(db, doc_name, v1_ver)
        doc2 = self.get_document_by_version(db, doc_name, v2_ver)

        if not doc1 or not doc2:
            return {"node_id": node_id, "changed": False, "error": "One or both document versions not found"}

        node1 = db.query(Node).filter(and_(Node.document_id == doc1.id, Node.node_id == node_id)).first()
        node2 = db.query(Node).filter(and_(Node.document_id == doc2.id, Node.node_id == node_id)).first()

        if not node1 and not node2:
            return {"node_id": node_id, "changed": False, "error": "Section not found in either version"}
        
        diff_details = []
        changed = False

        if not node1:
            diff_details.append({
                "field": "section",
                "v1_value": "",
                "v2_value": node2.heading,
                "diff": "Section Added"
            })
            changed = True
        elif not node2:
            diff_details.append({
                "field": "section",
                "v1_value": node1.heading,
                "v2_value": "",
                "diff": "Section Deleted"
            })
            changed = True
        else:
            # Both exist, compare heading and body
            if node1.heading != node2.heading:
                changed = True
                diff_details.append({
                    "field": "heading",
                    "v1_value": node1.heading,
                    "v2_value": node2.heading,
                    "diff": f"- {node1.heading}\n+ {node2.heading}"
                })
            
            if node1.body != node2.body:
                changed = True
                # Compute line diff
                lines1 = node1.body.splitlines()
                lines2 = node2.body.splitlines()
                line_diff = difflib.unified_diff(lines1, lines2, lineterm="")
                diff_str = "\n".join(line_diff)
                diff_details.append({
                    "field": "body",
                    "v1_value": node1.body,
                    "v2_value": node2.body,
                    "diff": diff_str
                })

        return {
            "node_id": node_id,
            "changed": changed,
            "v1_version": v1_ver,
            "v2_version": v2_ver,
            "diff_details": diff_details
        }
