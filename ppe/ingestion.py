"""Local, model-free reconstruction of the supplied KID layout."""

import hashlib
import io
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from pypdf import PdfReader

from ppe.evidence import Catalogue, Document, Evidence


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


@dataclass(frozen=True)
class Line:
    page: int
    text: str


def extract_lines(pdf: bytes) -> list[Line]:
    """Join consecutive fragments sharing a text origin, not arbitrary newlines.

    The supplied PDFs emit artificial newlines inside words for separate Tj
    operations. Their unchanged text origin identifies the actual line. Keep
    content-stream order: it preserves cost row descriptions beside their values.
    """
    reader = PdfReader(io.BytesIO(pdf), strict=False)
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("Encrypted PDF.")
    lines = []
    for number, page in enumerate(reader.pages, 1):
        groups: list[list] = []

        def visit(text, cm, tm, font, size):
            if not text.strip():
                return
            origin = tuple(round(v, 3) for v in (tm[4], tm[5], *cm))
            # Only the synthetic trailing newline is removed. Internal line
            # breaks are retained, including on unsupported/new layouts.
            fragment = text.removesuffix("\n")
            if groups and groups[-1][0] == origin:
                groups[-1][1] += fragment
            else:
                groups.append([origin, fragment])

        page.extract_text(visitor_text=visit)
        for _, text in groups:
            for part in text.splitlines():
                cleaned = normalize(part)
                if cleaned and not re.fullmatch(r"Strona \d+ z \d+", cleaned):
                    lines.append(Line(number, cleaned))
    if not lines:
        raise ValueError("No readable text; OCR is outside this POC.")
    return lines


def _position(lines: list[Line], prefix: str) -> int:
    matches = [
        i
        for i, line in enumerate(lines)
        if line.text == prefix or line.text.startswith(prefix + " ")
    ]
    if len(matches) != 1:
        raise ValueError(f"Missing or ambiguous heading: {prefix}")
    return matches[0]


def _value(lines: list[Line], heading: str) -> str | None:
    try:
        i = _position(lines, heading)
        return lines[i + 1].text
    except (ValueError, IndexError):
        return None


def parse_document(filename: str, pdf: bytes) -> Document:
    digest = hashlib.sha256(pdf).hexdigest()
    fallback = "file-" + hashlib.sha256(filename.encode()).hexdigest()[:12]
    name = Path(filename).stem.removeprefix("KID_").replace("_", " ").strip()
    try:
        lines = extract_lines(pdf)
    except Exception:
        return Document(
            filename=filename,
            document_hash=digest,
            fund_id=fallback,
            name=name,
            gaps=("PDF could not be read reliably; no evidence is available.",),
        )
    identifier = _value(lines, "Identyfikator krajowy")
    fund_id = (
        identifier
        if identifier and re.fullmatch(r"PL[A-Z0-9]{7,20}", identifier)
        else fallback
    )
    product = _value(lines, "PRODUKT:")
    gaps = []
    if product:
        name = product.split(" (SUBFUNDUSZ", 1)[0]
    else:
        gaps.append("Product name unavailable; using the filename.")
    date = _value(lines, "Data dokumentu")
    unit_class = _value(lines, "Klasa jednostki")
    if not date:
        gaps.append("Document date is unavailable.")
    if not unit_class:
        gaps.append("Representative unit class is unavailable.")

    objectives = "Cele"
    investor = "Docelowy inwestor"
    redemption = "Możliwość dokonywania wypłat"
    risk = "JAKIE SĄ RYZYKA I MOŻLIWE KORZYŚCI?"
    scenarios = "Scenariusze dotyczące wyników"
    guarantee = "CO SIĘ STANIE, JEŚLI FUNDUSZ NIE MA MOŻLIWOŚCI WYPŁATY?"
    costs = "JAKIE SĄ KOSZTY?"
    holding = "ILE CZASU POWINIENEM POSIADAĆ PRODUKT"
    dissolution = "Możliwość rozwiązania Subfunduszu"
    complaints = "JAK MOGĘ ZŁOŻYĆ REKLAMACJĘ?"
    boundaries = [
        ("strategy", objectives, investor),
        ("risks", investor, redemption),
        ("risks", risk, scenarios),
        ("risks", guarantee, costs),
        ("costs", costs, holding),
        ("holding_terms", redemption, dissolution),
        ("holding_terms", holding, complaints),
        ("scenarios", scenarios, guarantee),
    ]
    document = Document(
        filename=filename,
        document_hash=digest,
        fund_id=fund_id,
        name=name,
        date=date,
        unit_class=unit_class,
    )
    metadata = document.model_dump(exclude={"name", "date", "records", "gaps"})
    records = []
    for section, start, end in boundaries:
        try:
            first, last = _position(lines, start), _position(lines, end)
            if last <= first + 1:
                raise ValueError("Empty or out-of-order section.")
            retained = lines[first:last]
            identity = f"{digest}:{filename}:{section}:{start}:0"
            records.append(
                Evidence(
                    id=hashlib.sha256(identity.encode()).hexdigest()[:24],
                    **metadata,
                    fund_name=name,
                    document_date=date,
                    section=section,
                    heading=retained[0].text,
                    pages=tuple(dict.fromkeys(line.page for line in retained)),
                    text="\n".join(line.text for line in retained),
                )
            )
        except ValueError:
            gaps.append(f"{section}: missing, empty, or ambiguous section ({start}).")
    return document.model_copy(update={"records": tuple(records), "gaps": tuple(gaps)})


def load_catalogue(pdf_dir: Path) -> Catalogue:
    documents, pdfs, startup_gaps = [], {}, []
    try:
        paths = sorted(
            p for p in pdf_dir.iterdir() if p.suffix.lower() == ".pdf" and p.is_file()
        )
    except OSError:
        paths = []
    if not paths:
        startup_gaps.append(
            "No readable PDF directory or PDF files were found at startup."
        )
    for path in paths:
        # Symlinks outside the configured directory must not widen the catalogue.
        if not path.resolve().is_relative_to(pdf_dir.resolve()):
            startup_gaps.append(
                f"Skipped PDF outside configured directory: {path.name}"
            )
            continue
        try:
            pdf = path.read_bytes()
        except OSError:
            fallback = "file-" + hashlib.sha256(path.name.encode()).hexdigest()[:12]
            documents.append(
                Document(
                    filename=path.name,
                    document_hash="unreadable",
                    fund_id=fallback,
                    name=path.stem,
                    gaps=("PDF is unreadable; no evidence is available.",),
                )
            )
            continue
        document = parse_document(path.name, pdf)
        documents.append(document)
        pdfs[document.fund_id] = pdf

    counts = Counter(d.fund_id for d in documents)
    for index, doc in enumerate(documents):
        if counts[doc.fund_id] > 1:
            suffix = hashlib.sha256(doc.filename.encode()).hexdigest()[:8]
            documents[index] = doc.model_copy(
                update={
                    "fund_id": f"{doc.fund_id}-{suffix}",
                    "records": (),
                    "gaps": (
                        *doc.gaps,
                        "Duplicate product identifier; evidence withheld.",
                    ),
                }
            )
    return Catalogue(tuple(documents), MappingProxyType(pdfs), tuple(startup_gaps))
