"""Immutable evidence, catalogue access, and validated answer shapes."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

Section = Literal["strategy", "risks", "costs", "holding_terms", "scenarios"]
SECTIONS = get_args(Section)


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Evidence(Record):
    id: str
    document_hash: str
    filename: str
    fund_id: str
    fund_name: str
    document_date: str | None
    unit_class: str | None
    section: Section
    heading: str
    pages: tuple[int, ...]
    text: str = Field(min_length=1)


class Document(Record):
    filename: str
    document_hash: str
    fund_id: str
    name: str
    date: str | None = None
    unit_class: str | None = None
    records: tuple[Evidence, ...] = ()
    gaps: tuple[str, ...] = ()


@dataclass(frozen=True)
class Catalogue:
    documents: tuple[Document, ...]
    pdfs: Mapping[str, bytes]
    startup_gaps: tuple[str, ...] = ()

    @property
    def by_id(self) -> Mapping[str, Evidence]:
        return MappingProxyType({r.id: r for d in self.documents for r in d.records})

    def options(self) -> dict:
        return {
            "options": [
                {
                    **d.model_dump(mode="json", exclude={"records"}),
                    "sections": sorted({r.section for r in d.records}),
                }
                for d in self.documents
            ],
            "gaps": list(self.startup_gaps),
        }

    def retrieve(self, section: Section, fund_ids: list[str]) -> dict:
        if section not in SECTIONS:
            raise ValueError("Unknown section.")
        documents = {d.fund_id: d for d in self.documents}
        records, gaps = [], list(self.startup_gaps)
        for fund_id in dict.fromkeys(fund_ids):
            document = documents.get(fund_id)
            if document is None:
                gaps.append(f"Unknown fund ID: {fund_id}")
                continue
            selected = [r for r in document.records if r.section == section]
            records.extend(r.model_dump(mode="json") for r in selected)
            gaps.extend(f"{fund_id}: {gap}" for gap in document.gaps)
            if not selected:
                gaps.append(f"{fund_id}: {section} evidence is unavailable.")
        return {
            "section": section,
            "fund_ids": fund_ids,
            "records": records,
            "gaps": gaps,
        }


class Preferences(Record):
    horizon: str | None
    loss_tolerance: str | None
    liquidity: str | None
    cost_concerns: str | None
    exposure_currency: str | None
    experience: str | None

    @classmethod
    def unknown(cls) -> "Preferences":
        return cls(**{name: None for name in cls.model_fields})


class Citation(Record):
    evidence_id: str
    quote: str = Field(min_length=1, max_length=1800, pattern=r"\S")


class Finding(Record):
    label: Literal["Documented", "Interpreted", "Assumed", "Not supported"]
    statement: str = Field(min_length=1, max_length=2500)
    reasoning: str | None
    citations: list[Citation] = Field(max_length=12)

    @model_validator(mode="after")
    def grounded(self) -> "Finding":
        if self.label in {"Documented", "Interpreted"} and not self.citations:
            raise ValueError("Documented and Interpreted findings require citations.")
        if self.label == "Interpreted" and not self.reasoning:
            raise ValueError("Interpretations require reasoning from cited premises.")
        return self


class Answer(Record):
    status: Literal[
        "answered",
        "clarification",
        "unsupported",
        "incomplete",
        "error",
        "english_required",
    ]
    preferences: Preferences
    findings: list[Finding] = Field(max_length=24)
    assumptions: list[str] = Field(max_length=12)
    gaps: list[str] = Field(max_length=30)
    follow_up: str | None

    @classmethod
    def message(cls, status: str, message: str, preferences: Preferences | None = None):
        return cls(
            status=status,
            preferences=preferences or Preferences.unknown(),
            findings=[],
            assumptions=[],
            gaps=[message],
            follow_up=None,
        )
