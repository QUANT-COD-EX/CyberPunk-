"""
SQLite storage manager for investigations, documents, extracted fields, and findings.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from backend.app.models.contracts import (
    DocumentRecord,
    DocumentStatus,
    DocumentType,
    ExtractedField,
    FieldSource,
    Finding,
    FindingCategory,
    FindingStatus,
    FindingStrength,
    FindingTier,
    Investigation,
    PriorityBreakdownItem,
    ReviewPriority,
    CaseDecision,
    ReviewerAction,
    EvidenceItem,
    CrossDocRelationshipGraph,
    AnomalyCorrelationCluster,
    ForensicAnalysisReport,
)


class StorageManager:
    def __init__(self, db_path: Path, data_dir: Path):
        self.db_path = db_path
        self.data_dir = data_dir
        self.originals_dir = data_dir / "originals"
        self.rendered_dir = data_dir / "rendered"
        self.originals_dir.mkdir(parents=True, exist_ok=True)
        self.rendered_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS investigations (
                    investigation_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    review_priority TEXT NOT NULL,
                    priority_score INTEGER NOT NULL DEFAULT 0,
                    priority_breakdown TEXT NOT NULL DEFAULT '[]',
                    case_decision TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    investigation_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    type TEXT NOT NULL,
                    type_confidence REAL NOT NULL,
                    pages INTEGER NOT NULL,
                    render_dpi INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    llm_type TEXT,
                    llm_accuracy REAL,
                    llm_reasoning TEXT,
                    llm_provider TEXT,
                    FOREIGN KEY (investigation_id) REFERENCES investigations(investigation_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fields (
                    field_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source TEXT NOT NULL,
                    page INTEGER NOT NULL,
                    bbox TEXT NOT NULL,
                    unable_to_assess INTEGER NOT NULL DEFAULT 0,
                    is_handwritten INTEGER NOT NULL DEFAULT 0,
                    language TEXT DEFAULT 'en',
                    script TEXT DEFAULT 'Latin',
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS findings (
                    finding_id TEXT PRIMARY KEY,
                    investigation_id TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    category TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    signals TEXT NOT NULL,
                    strength TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    FOREIGN KEY (investigation_id) REFERENCES investigations(investigation_id)
                )
            """)

            # Auto-migrate table columns if upgrading an existing database
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(documents)")
            existing_doc_cols = [c[1] for c in cursor.fetchall()]
            for col_name, col_type in [
                ("llm_type", "TEXT"),
                ("llm_accuracy", "REAL"),
                ("llm_reasoning", "TEXT"),
                ("llm_provider", "TEXT"),
                ("is_ai_generated", "INTEGER DEFAULT 0"),
                ("ai_generation_risk", "REAL DEFAULT 0.0"),
                ("ai_generation_reasoning", "TEXT"),
                ("ai_generation_indicators", "TEXT DEFAULT '[]'"),
                ("primary_language", "TEXT DEFAULT 'en'"),
                ("detected_languages", "TEXT DEFAULT '[\"en\"]'"),
                ("scripts", "TEXT DEFAULT '[\"Latin\"]'"),
                ("has_handwriting", "INTEGER DEFAULT 0"),
                ("handwriting_ratio", "REAL DEFAULT 0.0"),
                ("forensic_report", "TEXT"),
            ]:
                if col_name not in existing_doc_cols:
                    conn.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}")

            cursor.execute("PRAGMA table_info(investigations)")
            existing_inv_cols = [c[1] for c in cursor.fetchall()]
            for col_name, col_type in [
                ("relationship_graph", "TEXT"),
                ("correlation_clusters", "TEXT"),
                ("tampering_risk_score", "REAL DEFAULT 0.0"),
            ]:
                if col_name not in existing_inv_cols:
                    conn.execute(f"ALTER TABLE investigations ADD COLUMN {col_name} {col_type}")

            cursor.execute("PRAGMA table_info(fields)")
            existing_field_cols = [c[1] for c in cursor.fetchall()]
            for col_name, col_type in [
                ("is_handwritten", "INTEGER DEFAULT 0"),
                ("language", "TEXT DEFAULT 'en'"),
                ("script", "TEXT DEFAULT 'Latin'"),
            ]:
                if col_name not in existing_field_cols:
                    conn.execute(f"ALTER TABLE fields ADD COLUMN {col_name} {col_type}")
            conn.commit()

    def create_investigation(self, investigation: Investigation):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO investigations (investigation_id, created_at, review_priority, priority_score, priority_breakdown, case_decision)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    investigation.investigation_id,
                    investigation.created_at,
                    investigation.review_priority.value,
                    investigation.priority_score,
                    json.dumps([b.model_dump() for b in investigation.priority_breakdown]),
                    json.dumps(investigation.case_decision.model_dump()) if investigation.case_decision else None,
                ),
            )
            conn.commit()

    def get_investigation(self, investigation_id: str) -> Optional[Investigation]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT investigation_id, created_at, review_priority, priority_score, priority_breakdown, case_decision,
                       relationship_graph, correlation_clusters, tampering_risk_score
                FROM investigations WHERE investigation_id = ?
                """,
                (investigation_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            inv_id, created_at, priority, score, breakdown_json, decision_json = row[:6]
            graph_json = row[6] if len(row) > 6 else None
            clusters_json = row[7] if len(row) > 7 else None
            tamper_score = float(row[8]) if len(row) > 8 and row[8] is not None else 0.0

            docs = self.get_documents(investigation_id)

            breakdown_data = json.loads(breakdown_json)
            breakdown = [PriorityBreakdownItem.model_validate(item) for item in breakdown_data]
            decision = CaseDecision.model_validate(json.loads(decision_json)) if decision_json else None
            graph = CrossDocRelationshipGraph.model_validate(json.loads(graph_json)) if graph_json else None
            clusters = [AnomalyCorrelationCluster.model_validate(c) for c in json.loads(clusters_json)] if clusters_json else []

            return Investigation(
                investigation_id=inv_id,
                created_at=created_at,
                documents=docs,
                review_priority=ReviewPriority(priority),
                priority_score=score,
                priority_breakdown=breakdown,
                case_decision=decision,
                relationship_graph=graph,
                correlation_clusters=clusters,
                tampering_risk_score=tamper_score,
            )

    def save_investigation_analytics(
        self,
        investigation_id: str,
        relationship_graph: Optional[CrossDocRelationshipGraph] = None,
        correlation_clusters: Optional[List[AnomalyCorrelationCluster]] = None,
        tampering_risk_score: float = 0.0,
    ):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE investigations
                SET relationship_graph = ?, correlation_clusters = ?, tampering_risk_score = ?
                WHERE investigation_id = ?
                """,
                (
                    json.dumps(relationship_graph.model_dump()) if relationship_graph else None,
                    json.dumps([c.model_dump() for c in correlation_clusters]) if correlation_clusters else None,
                    tampering_risk_score,
                    investigation_id,
                ),
            )
            conn.commit()

    def list_investigations(self) -> List[Investigation]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT investigation_id FROM investigations ORDER BY created_at DESC")
            rows = cursor.fetchall()
            invs = []
            for r in rows:
                inv = self.get_investigation(r[0])
                if inv:
                    invs.append(inv)
            return invs

    def save_document(self, investigation_id: str, doc: DocumentRecord, file_path: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO documents (
                    doc_id, investigation_id, filename, file_path, sha256, type, type_confidence,
                    pages, render_dpi, status, error_message, llm_type, llm_accuracy, llm_reasoning, llm_provider,
                    is_ai_generated, ai_generation_risk, ai_generation_reasoning, ai_generation_indicators,
                    primary_language, detected_languages, scripts, has_handwriting, handwriting_ratio, forensic_report
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.doc_id,
                    investigation_id,
                    doc.filename,
                    str(file_path),
                    doc.sha256,
                    doc.type.value,
                    doc.type_confidence,
                    doc.pages,
                    doc.render_dpi,
                    doc.status.value,
                    doc.error_message,
                    doc.llm_type.value if doc.llm_type else None,
                    doc.llm_accuracy,
                    doc.llm_reasoning,
                    doc.llm_provider,
                    1 if doc.is_ai_generated else 0,
                    doc.ai_generation_risk,
                    doc.ai_generation_reasoning,
                    json.dumps(doc.ai_generation_indicators),
                    doc.primary_language,
                    json.dumps(doc.detected_languages),
                    json.dumps(doc.scripts),
                    1 if doc.has_handwriting else 0,
                    doc.handwriting_ratio,
                    json.dumps(doc.forensic_report.model_dump()) if doc.forensic_report else None,
                ),
            )
            conn.commit()

    def get_documents(self, investigation_id: str) -> List[DocumentRecord]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT doc_id, filename, sha256, type, type_confidence, pages, render_dpi,
                       status, error_message, llm_type, llm_accuracy, llm_reasoning, llm_provider,
                       is_ai_generated, ai_generation_risk, ai_generation_reasoning, ai_generation_indicators,
                       primary_language, detected_languages, scripts, has_handwriting, handwriting_ratio, forensic_report
                FROM documents WHERE investigation_id = ?
                """,
                (investigation_id,),
            )
            rows = cursor.fetchall()
            docs = []
            for r in rows:
                doc_id = r[0]
                fields = self.get_fields(doc_id)
                llm_t = None
                if r[9]:
                    try:
                        llm_t = DocumentType(r[9])
                    except ValueError:
                        llm_t = None

                is_ai = bool(r[13]) if len(r) > 13 and r[13] is not None else False
                ai_risk = float(r[14]) if len(r) > 14 and r[14] is not None else 0.0
                ai_reason = r[15] if len(r) > 15 and r[15] else None
                ai_inds = json.loads(r[16]) if len(r) > 16 and r[16] else []

                p_lang = r[17] if len(r) > 17 and r[17] else "en"
                det_langs = json.loads(r[18]) if len(r) > 18 and r[18] else ["en"]
                scripts = json.loads(r[19]) if len(r) > 19 and r[19] else ["Latin"]
                has_hw = bool(r[20]) if len(r) > 20 and r[20] is not None else False
                hw_ratio = float(r[21]) if len(r) > 21 and r[21] is not None else 0.0
                f_report = ForensicAnalysisReport.model_validate(json.loads(r[22])) if len(r) > 22 and r[22] else None

                docs.append(
                    DocumentRecord(
                        doc_id=doc_id,
                        filename=r[1],
                        sha256=r[2],
                        type=DocumentType(r[3]),
                        type_confidence=r[4],
                        pages=r[5],
                        render_dpi=r[6],
                        status=DocumentStatus(r[7]),
                        error_message=r[8],
                        llm_type=llm_t,
                        llm_accuracy=r[10],
                        llm_reasoning=r[11],
                        llm_provider=r[12],
                        is_ai_generated=is_ai,
                        ai_generation_risk=ai_risk,
                        ai_generation_reasoning=ai_reason,
                        ai_generation_indicators=ai_inds,
                        fields=fields,
                        primary_language=p_lang,
                        detected_languages=det_langs,
                        scripts=scripts,
                        has_handwriting=has_hw,
                        handwriting_ratio=hw_ratio,
                        forensic_report=f_report,
                    )
                )
            return docs

    def get_document(self, doc_id: str) -> Optional[DocumentRecord]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT doc_id, filename, sha256, type, type_confidence, pages, render_dpi,
                       status, error_message, llm_type, llm_accuracy, llm_reasoning, llm_provider,
                       is_ai_generated, ai_generation_risk, ai_generation_reasoning, ai_generation_indicators,
                       primary_language, detected_languages, scripts, has_handwriting, handwriting_ratio, forensic_report
                FROM documents WHERE doc_id = ?
                """,
                (doc_id,),
            )
            r = cursor.fetchone()
            if not r:
                return None
            fields = self.get_fields(doc_id)
            llm_t = None
            if r[9]:
                try:
                    llm_t = DocumentType(r[9])
                except ValueError:
                    llm_t = None

            is_ai = bool(r[13]) if len(r) > 13 and r[13] is not None else False
            ai_risk = float(r[14]) if len(r) > 14 and r[14] is not None else 0.0
            ai_reason = r[15] if len(r) > 15 and r[15] else None
            ai_inds = json.loads(r[16]) if len(r) > 16 and r[16] else []

            p_lang = r[17] if len(r) > 17 and r[17] else "en"
            det_langs = json.loads(r[18]) if len(r) > 18 and r[18] else ["en"]
            scripts = json.loads(r[19]) if len(r) > 19 and r[19] else ["Latin"]
            has_hw = bool(r[20]) if len(r) > 20 and r[20] is not None else False
            hw_ratio = float(r[21]) if len(r) > 21 and r[21] is not None else 0.0
            f_report = ForensicAnalysisReport.model_validate(json.loads(r[22])) if len(r) > 22 and r[22] else None

            return DocumentRecord(
                doc_id=r[0],
                filename=r[1],
                sha256=r[2],
                type=DocumentType(r[3]),
                type_confidence=r[4],
                pages=r[5],
                render_dpi=r[6],
                status=DocumentStatus(r[7]),
                error_message=r[8],
                llm_type=llm_t,
                llm_accuracy=r[10],
                llm_reasoning=r[11],
                llm_provider=r[12],
                is_ai_generated=is_ai,
                ai_generation_risk=ai_risk,
                ai_generation_reasoning=ai_reason,
                ai_generation_indicators=ai_inds,
                fields=fields,
                primary_language=p_lang,
                detected_languages=det_langs,
                scripts=scripts,
                has_handwriting=has_hw,
                handwriting_ratio=hw_ratio,
                forensic_report=f_report,
            )

    def get_document_file_path(self, doc_id: str) -> Optional[Path]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT file_path FROM documents WHERE doc_id = ?", (doc_id,))
            r = cursor.fetchone()
            return Path(r[0]) if r else None

    def get_investigation_id_for_document(self, doc_id: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT investigation_id FROM documents WHERE doc_id = ?", (doc_id,))
            r = cursor.fetchone()
            return r[0] if r else None

    def save_fields(self, fields: List[ExtractedField]):
        with sqlite3.connect(self.db_path) as conn:
            for f in fields:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO fields (
                        field_id, doc_id, name, value, raw_text, confidence, source, page, bbox, unable_to_assess,
                        is_handwritten, language, script
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f.field_id,
                        f.doc_id,
                        f.name,
                        json.dumps(f.value),
                        f.raw_text,
                        f.confidence,
                        f.source.value,
                        f.page,
                        json.dumps(f.bbox),
                        1 if f.unable_to_assess else 0,
                        1 if f.is_handwritten else 0,
                        f.language,
                        f.script,
                    ),
                )
            conn.commit()

    def get_fields(self, doc_id: str) -> List[ExtractedField]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT field_id, doc_id, name, value, raw_text, confidence, source, page, bbox, unable_to_assess,
                       is_handwritten, language, script
                FROM fields WHERE doc_id = ?
                """,
                (doc_id,),
            )
            rows = cursor.fetchall()
            return [
                ExtractedField(
                    field_id=r[0],
                    doc_id=r[1],
                    name=r[2],
                    value=json.loads(r[3]),
                    raw_text=r[4],
                    confidence=r[5],
                    source=FieldSource(r[6]),
                    page=r[7],
                    bbox=json.loads(r[8]),
                    unable_to_assess=bool(r[9]),
                    is_handwritten=bool(r[10]) if len(r) > 10 and r[10] is not None else False,
                    language=r[11] if len(r) > 11 and r[11] else "en",
                    script=r[12] if len(r) > 12 and r[12] else "Latin",
                )
                for r in rows
            ]

    def get_field_by_id(self, field_id: str) -> Optional[ExtractedField]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT field_id, doc_id, name, value, raw_text, confidence, source, page, bbox, unable_to_assess,
                       is_handwritten, language, script
                FROM fields WHERE field_id = ?
                """,
                (field_id,),
            )
            r = cursor.fetchone()
            if not r:
                return None
            return ExtractedField(
                field_id=r[0],
                doc_id=r[1],
                name=r[2],
                value=json.loads(r[3]),
                raw_text=r[4],
                confidence=r[5],
                source=FieldSource(r[6]),
                page=r[7],
                bbox=json.loads(r[8]),
                unable_to_assess=bool(r[9]),
                is_handwritten=bool(r[10]) if len(r) > 10 and r[10] is not None else False,
                language=r[11] if len(r) > 11 and r[11] else "en",
                script=r[12] if len(r) > 12 and r[12] else "Latin",
            )

    def save_findings(self, investigation_id: str, findings: List[Finding]):
        with sqlite3.connect(self.db_path) as conn:
            for f in findings:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO findings (finding_id, investigation_id, tier, category, rule_id, title, evidence, signals, strength, confidence, status, explanation, reviewer)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f.finding_id,
                        investigation_id,
                        f.tier.value,
                        f.category.value,
                        f.rule_id,
                        f.title,
                        json.dumps([e.model_dump() for e in f.evidence]),
                        json.dumps(f.signals),
                        f.strength.value,
                        f.confidence,
                        f.status.value,
                        f.explanation,
                        json.dumps(f.reviewer.model_dump()),
                    ),
                )
            conn.commit()

    def get_findings(self, investigation_id: str) -> List[Finding]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT finding_id, tier, category, rule_id, title, evidence, signals, strength, confidence, status, explanation, reviewer FROM findings WHERE investigation_id = ?",
                (investigation_id,),
            )
            rows = cursor.fetchall()
            findings = []
            for r in rows:
                ev_data = json.loads(r[5])
                evidence = [EvidenceItem.model_validate(e) for e in ev_data]
                signals = json.loads(r[6])
                reviewer_data = json.loads(r[11])
                reviewer = ReviewerAction.model_validate(reviewer_data)

                findings.append(
                    Finding(
                        finding_id=r[0],
                        tier=FindingTier(r[1]),
                        category=FindingCategory(r[2]),
                        rule_id=r[3],
                        title=r[4],
                        evidence=evidence,
                        signals=signals,
                        strength=FindingStrength(r[7]),
                        confidence=r[8],
                        status=FindingStatus(r[9]),
                        explanation=r[10],
                        reviewer=reviewer,
                    )
                )
            return findings

    def get_finding(self, finding_id: str) -> Optional[Finding]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT finding_id, tier, category, rule_id, title, evidence, signals, strength, confidence, status, explanation, reviewer FROM findings WHERE finding_id = ?",
                (finding_id,),
            )
            r = cursor.fetchone()
            if not r:
                return None
            evidence = [EvidenceItem.model_validate(e) for e in json.loads(r[5])]
            return Finding(
                finding_id=r[0],
                tier=FindingTier(r[1]),
                category=FindingCategory(r[2]),
                rule_id=r[3],
                title=r[4],
                evidence=evidence,
                signals=json.loads(r[6]),
                strength=FindingStrength(r[7]),
                confidence=r[8],
                status=FindingStatus(r[9]),
                explanation=r[10],
                reviewer=ReviewerAction.model_validate(json.loads(r[11])),
            )

    def update_investigation_priority(
        self,
        investigation_id: str,
        priority: ReviewPriority,
        score: int,
        breakdown: List[PriorityBreakdownItem],
    ):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE investigations
                SET review_priority = ?, priority_score = ?, priority_breakdown = ?
                WHERE investigation_id = ?
                """,
                (
                    priority.value,
                    score,
                    json.dumps([b.model_dump() for b in breakdown]),
                    investigation_id,
                ),
            )
            conn.commit()

    def update_case_decision(self, investigation_id: str, decision: CaseDecision):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE investigations SET case_decision = ? WHERE investigation_id = ?",
                (json.dumps(decision.model_dump()), investigation_id),
            )
            conn.commit()

    def update_finding_review(
        self,
        finding_id: str,
        status: FindingStatus,
        reviewer: ReviewerAction,
    ):
        """Updates the status and reviewer action for a finding."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE findings SET status = ?, reviewer = ? WHERE finding_id = ?",
                (
                    status.value,
                    json.dumps(reviewer.model_dump()),
                    finding_id,
                ),
            )
            conn.commit()

    def get_investigation_id_for_finding(self, finding_id: str) -> Optional[str]:
        """Returns the investigation_id for a given finding."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT investigation_id FROM findings WHERE finding_id = ?",
                (finding_id,),
            )
            r = cursor.fetchone()
            return r[0] if r else None
