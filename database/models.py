
from dataclasses import dataclass
from typing import Optional


@dataclass
class Project:
    name: str
    website_url: str
    domain: str
    description: Optional[str] = None


@dataclass
class AnalysisRun:
    project_id: int
    max_pages: int = 50
    status: str = "pending"


@dataclass
class Keyword:
    project_id: int
    keyword: str
    normalized_keyword: str


@dataclass
class Competitor:
    project_id: int
    domain: str
    website_url: Optional[str] = None
    discovered_by_keyword: Optional[str] = None


@dataclass
class TechnicalIssue:
    analysis_run_id: int
    issue_code: str
    category: str
    severity: str
    title: str
    description: Optional[str] = None
    recommendation: Optional[str] = None
