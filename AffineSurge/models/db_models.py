from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table, Text
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

# Many-to-many relationship for Selection and Node
selection_node_association = Table(
    "selection_node",
    Base.metadata,
    Column("selection_id", String, ForeignKey("selections.id", ondelete="CASCADE"), primary_key=True),
    Column("node_id", Integer, ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True)
)

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    version = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    nodes = relationship("Node", back_populates="document", cascade="all, delete-orphan")

class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(String, nullable=False)  # Stable string ID (e.g. 'sec_1', 'sec_1_1')
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    level = Column(Integer, nullable=False)   # 1 for H1, 2 for H2, etc.
    heading = Column(String, nullable=False)
    body = Column(Text, nullable=False)       # Aggregated body text
    title = Column(String, nullable=True)     # Reconstructs assignment-compliant title
    section_number = Column(String, nullable=True)  # Section number e.g. "2.1.1.1"
    body_text = Column(Text, nullable=True)   # Reconstructs assignment-compliant body text
    page_number = Column(Integer, nullable=False)
    bbox = Column(String, nullable=False)      # JSON representation of bounding box coordinates
    content_hash = Column(String, nullable=False)  # SHA256 of heading + body
    parent_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=True)
    depth = Column(Integer, default=0)

    # Structured fields stored as serialized JSON strings
    tables = Column(Text, nullable=True)
    lists = Column(Text, nullable=True)
    figures = Column(Text, nullable=True)

    # Relationships
    document = relationship("Document", back_populates="nodes")
    parent = relationship("Node", remote_side=[id], back_populates="children")
    children = relationship("Node", back_populates="parent", cascade="all, delete-orphan")
    selections = relationship("Selection", secondary=selection_node_association, back_populates="nodes")

class Selection(Base):
    __tablename__ = "selections"

    id = Column(String, primary_key=True)  # Unique selection ID (UUID or stable hash)
    name = Column(String, nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)  # Pin to a specific document version
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    nodes = relationship("Node", secondary=selection_node_association, back_populates="selections")
    generations = relationship("Generation", back_populates="selection", cascade="all, delete-orphan")

class Generation(Base):
    __tablename__ = "generations"

    id = Column(String, primary_key=True)  # Generation ID
    selection_id = Column(String, ForeignKey("selections.id", ondelete="CASCADE"), nullable=False)
    node_id = Column(String, nullable=False)  # Stable node ID this generation belongs to
    content_hash = Column(String, nullable=False)  # Hash of the node's content at generation time
    test_cases = Column(Text, nullable=False)      # JSON string representing the generated test cases
    created_at = Column(DateTime, default=datetime.utcnow)
    is_stale = Column(Boolean, default=False)

    # Relationships
    selection = relationship("Selection", back_populates="generations")
