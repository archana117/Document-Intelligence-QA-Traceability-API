from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class NodeBase(BaseModel):
    node_id: str
    level: int
    heading: str
    body: str
    title: Optional[str] = None
    section_number: Optional[str] = None
    body_text: Optional[str] = None
    page_number: int
    bbox: List[float] = Field(default_factory=list)
    content_hash: str
    depth: int
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    lists: List[Dict[str, Any]] = Field(default_factory=list)
    figures: List[Dict[str, Any]] = Field(default_factory=list)

class NodeBrief(BaseModel):
    id: int
    node_id: str
    level: int
    heading: str
    page_number: int

    class Config:
        from_attributes = True

class NodeTreeResponse(BaseModel):
    id: int
    node_id: str
    level: int
    heading: str
    body: str
    title: Optional[str] = None
    section_number: Optional[str] = None
    body_text: Optional[str] = None
    page_number: int
    bbox: List[float]
    content_hash: str
    depth: int
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    lists: List[Dict[str, Any]] = Field(default_factory=list)
    figures: List[Dict[str, Any]] = Field(default_factory=list)
    children: List["NodeTreeResponse"] = Field(default_factory=list)

    class Config:
        from_attributes = True

class DocumentResponse(BaseModel):
    id: int
    name: str
    version: int
    created_at: datetime

    class Config:
        from_attributes = True

class DocumentTreeResponse(BaseModel):
    document_id: int
    name: str
    version: int
    title: str
    sections: List[NodeTreeResponse]

class SelectionCreate(BaseModel):
    name: str
    document_id: int
    version: int
    node_ids: List[str]  # Stable node IDs (e.g. ['sec_1_1', 'sec_2_1'])

class SelectionResponse(BaseModel):
    id: str
    name: str
    document_id: int
    version: int
    node_ids: List[str]
    created_at: datetime

    class Config:
        from_attributes = True

class TestCase(BaseModel):
    test_case_id: str = Field(description="Stable ID for the test case, e.g. tc_001")
    title: str = Field(description="Short descriptive title of the test case")
    steps: List[str] = Field(description="Step-by-step instructions to execute the check")
    expected_result: str = Field(description="The expected outcome of the test case")

class GenerationCreate(BaseModel):
    test_cases: List[TestCase]

class TestCaseGenerationResponse(BaseModel):
    node_id: str
    node_heading: str
    content_hash: str
    is_stale: bool
    test_cases: List[TestCase]

class SelectionQAResponse(BaseModel):
    selection_id: str
    selection_name: str
    document_version: int
    is_stale: bool  # True if any selected node content has changed in the latest version
    generations: List[TestCaseGenerationResponse]

class DiffItem(BaseModel):
    field: str  # 'heading' or 'body'
    v1_value: str
    v2_value: str
    diff: str  # Simple comparison diff

class NodeDiffResponse(BaseModel):
    node_id: str
    changed: bool
    v1_version: int
    v2_version: int
    diff_details: List[DiffItem] = Field(default_factory=list)
