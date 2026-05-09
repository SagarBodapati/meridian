"""Financial-aware document chunker.

Narrative text → sentence-boundary chunks (≤512 tokens).
Tables → whole-table chunk + a prose summary chunk.
MD&A / Risk Factors → section-level parent + paragraph-level children.
Footnotes → linked to parent paragraph via parent_chunk_id.
"""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

import tiktoken

from backend.models.documents import (
    ChunkMetadata,
    ChunkType,
    DocumentChunk,
    FilingSection,
    IngestedDocument,
)

_enc = tiktoken.get_encoding("cl100k_base")

# Approximate section headings found in SEC filings
SECTION_PATTERNS: list[tuple[re.Pattern, FilingSection]] = [
    (re.compile(r"management.{0,10}discussion.{0,10}analysis", re.I), FilingSection.MDA),
    (re.compile(r"risk\s+factors", re.I), FilingSection.RISK_FACTORS),
    (re.compile(r"(consolidated\s+)?(financial\s+statements|balance\s+sheet|income\s+statement|cash\s+flow)", re.I), FilingSection.FINANCIAL_STATEMENTS),
    (re.compile(r"notes?\s+to\s+(the\s+)?(consolidated\s+)?financial\s+statements", re.I), FilingSection.NOTES),
    (re.compile(r"item\s+1\b.*business", re.I), FilingSection.BUSINESS),
    (re.compile(r"executive\s+compensation", re.I), FilingSection.EXECUTIVE_COMP),
    (re.compile(r"legal\s+proceedings", re.I), FilingSection.LEGAL),
]

TABLE_PATTERN = re.compile(
    r"(<table[\s\S]*?</table>|\|.+\|[\s\S]*?\n(?:\|[-:]+\|[\s\S]*?\n)?(?:\|.+\|[\s\S]*?\n)+)",
    re.I,
)
FOOTNOTE_PATTERN = re.compile(r"^\s*\(\d+\)\s+.{20,}", re.MULTILINE)


@dataclass
class ChunkConfig:
    max_tokens: int = 512
    overlap_tokens: int = 64
    min_tokens: int = 50
    include_section_context: bool = True  # prepend section name to each chunk


def _count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def _chunk_id(ticker: str, doc_id: str, index: int) -> str:
    raw = f"{ticker}:{doc_id}:{index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _detect_section(text: str) -> FilingSection:
    for pattern, section in SECTION_PATTERNS:
        if pattern.search(text[:200]):
            return section
    return FilingSection.OTHER


def _split_into_sentences(text: str) -> list[str]:
    """Rough sentence splitter that respects common financial abbreviations."""
    # Protect common abbreviations that shouldn't end sentences
    text = re.sub(r"\b(Mr|Mrs|Dr|Inc|Corp|Ltd|Co|vs|approx|est|avg|fig|No|Vol)\.", r"\1<DOT>", text)
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [s.replace("<DOT>", ".") for s in sentences if s.strip()]


def _build_token_chunks(sentences: list[str], config: ChunkConfig) -> list[str]:
    """Group sentences into token-bounded chunks with overlap."""
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sent in sentences:
        sent_tokens = _count_tokens(sent)
        if current_tokens + sent_tokens > config.max_tokens and current:
            chunk_text = " ".join(current)
            if _count_tokens(chunk_text) >= config.min_tokens:
                chunks.append(chunk_text)
            # Keep overlap: last N tokens worth of sentences
            overlap_sents: list[str] = []
            ot = 0
            for s in reversed(current):
                t = _count_tokens(s)
                if ot + t > config.overlap_tokens:
                    break
                overlap_sents.insert(0, s)
                ot += t
            current = overlap_sents
            current_tokens = ot
        current.append(sent)
        current_tokens += sent_tokens

    if current:
        remainder = " ".join(current)
        if _count_tokens(remainder) >= config.min_tokens:
            chunks.append(remainder)

    return chunks


def _table_to_prose(table_data: dict[str, Any]) -> str:
    """Convert a parsed table dict to a readable prose description."""
    headers = table_data.get("headers", [])
    rows = table_data.get("rows", [])
    title = table_data.get("title", "Financial Table")

    if not rows:
        return title

    lines = [f"{title}:"]
    for row in rows[:20]:  # cap at 20 rows for the prose summary
        if len(row) == len(headers) and headers:
            pairs = ", ".join(f"{h}: {v}" for h, v in zip(headers, row) if v)
            lines.append(f"  {pairs}")
        else:
            lines.append("  " + " | ".join(str(c) for c in row if c))

    return "\n".join(lines)


class FinancialChunker:
    def __init__(self, config: ChunkConfig | None = None) -> None:
        self._cfg = config or ChunkConfig()

    def chunk(self, doc: IngestedDocument) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        idx = 0

        # ── Split raw text into sections ──────────────────────────────
        sections = self._split_sections(doc.raw_text)

        for section_text, section_type in sections:
            # ── Extract and handle tables first ──────────────────────
            section_no_tables, table_chunks, idx = self._extract_tables(
                section_text, doc, section_type, idx
            )
            chunks.extend(table_chunks)

            # ── Handle footnotes ──────────────────────────────────────
            section_clean, footnote_chunks, idx = self._extract_footnotes(
                section_no_tables, doc, section_type, idx
            )
            chunks.extend(footnote_chunks)

            # ── Narrative chunks ──────────────────────────────────────
            if section_type == FilingSection.MDA:
                # Extra granularity for MD&A: paragraph-level chunks
                paragraphs = re.split(r"\n{2,}", section_clean)
                for para in paragraphs:
                    para = para.strip()
                    if _count_tokens(para) < self._cfg.min_tokens:
                        continue
                    sentences = _split_into_sentences(para)
                    for chunk_text in _build_token_chunks(sentences, self._cfg):
                        chunks.append(self._make_chunk(chunk_text, doc, section_type, idx, ChunkType.NARRATIVE))
                        idx += 1
            else:
                sentences = _split_into_sentences(section_clean)
                for chunk_text in _build_token_chunks(sentences, self._cfg):
                    chunks.append(self._make_chunk(chunk_text, doc, section_type, idx, ChunkType.NARRATIVE))
                    idx += 1

        # ── Document-level summary chunk ──────────────────────────────
        summary_text = self._generate_summary_context(doc)
        if summary_text:
            chunks.append(self._make_chunk(summary_text, doc, FilingSection.COVER, idx, ChunkType.SUMMARY))

        return chunks

    def _split_sections(self, text: str) -> list[tuple[str, FilingSection]]:
        """Split full filing text into (section_text, FilingSection) pairs."""
        # Remove HTML tags if present
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s{3,}", "\n\n", text)

        # Find section boundaries by heading patterns
        splits: list[tuple[int, FilingSection]] = []
        for pattern, section in SECTION_PATTERNS:
            for m in pattern.finditer(text):
                splits.append((m.start(), section))

        if not splits:
            return [(text, FilingSection.OTHER)]

        splits.sort(key=lambda x: x[0])
        result: list[tuple[str, FilingSection]] = []
        prev_pos = 0
        prev_section = FilingSection.OTHER

        for pos, section in splits:
            segment = text[prev_pos:pos].strip()
            if segment:
                result.append((segment, prev_section))
            prev_pos = pos
            prev_section = section

        result.append((text[prev_pos:].strip(), prev_section))
        return [(t, s) for t, s in result if t]

    def _extract_tables(
        self,
        text: str,
        doc: IngestedDocument,
        section: FilingSection,
        idx: int,
    ) -> tuple[str, list[DocumentChunk], int]:
        """Remove HTML/markdown tables, yield table chunks, return cleaned text."""
        table_chunks: list[DocumentChunk] = []
        remaining = text

        for i, match in enumerate(TABLE_PATTERN.finditer(text)):
            table_raw = match.group()
            parsed = _parse_html_table(table_raw) or {"headers": [], "rows": [], "title": f"Table {i+1}"}
            prose = _table_to_prose(parsed)

            chunk = self._make_chunk(prose, doc, section, idx, ChunkType.TABLE)
            chunk.structured_data = parsed
            table_chunks.append(chunk)
            idx += 1

        remaining = TABLE_PATTERN.sub(" ", remaining)
        return remaining, table_chunks, idx

    def _extract_footnotes(
        self,
        text: str,
        doc: IngestedDocument,
        section: FilingSection,
        idx: int,
    ) -> tuple[str, list[DocumentChunk], int]:
        footnote_chunks: list[DocumentChunk] = []
        remaining = text

        for match in FOOTNOTE_PATTERN.finditer(text):
            fn_text = match.group().strip()
            if _count_tokens(fn_text) < self._cfg.min_tokens:
                continue
            chunk = self._make_chunk(fn_text, doc, section, idx, ChunkType.FOOTNOTE)
            footnote_chunks.append(chunk)
            idx += 1

        remaining = FOOTNOTE_PATTERN.sub(" ", remaining)
        return remaining, footnote_chunks, idx

    def _make_chunk(
        self,
        text: str,
        doc: IngestedDocument,
        section: FilingSection,
        idx: int,
        chunk_type: ChunkType,
    ) -> DocumentChunk:
        cid = _chunk_id(doc.ticker, doc.document_id, idx)

        # Optionally prepend section context for better retrieval
        display_text = text
        if self._cfg.include_section_context and section != FilingSection.OTHER:
            display_text = f"[{doc.ticker} {doc.filing_type.value} {doc.fiscal_period} — {section.value}]\n{text}"

        meta = ChunkMetadata(
            chunk_id=cid,
            document_id=doc.document_id,
            source_url=doc.source_url,
            ticker=doc.ticker,
            company_name=doc.company_name,
            cik=doc.cik,
            filing_type=doc.filing_type,
            filing_section=section,
            fiscal_period=doc.fiscal_period,
            fiscal_year=doc.report_date.year,
            report_date=doc.report_date,
            filing_date=doc.filing_date,
            chunk_type=chunk_type,
            word_count=len(text.split()),
        )
        return DocumentChunk(chunk_id=cid, text=display_text, metadata=meta)

    def _generate_summary_context(self, doc: IngestedDocument) -> str:
        first_500 = doc.raw_text[:2000].strip()
        return (
            f"Filing: {doc.company_name} ({doc.ticker}) "
            f"{doc.filing_type.value} for {doc.fiscal_period}. "
            f"Filed: {doc.filing_date.strftime('%Y-%m-%d')}. "
            f"Period ending: {doc.report_date.strftime('%Y-%m-%d')}.\n\n"
            f"{first_500[:500]}"
        )


def _parse_html_table(raw: str) -> dict[str, Any] | None:
    """Very lightweight HTML table parser — no lxml dependency."""
    try:
        rows_raw = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", raw, re.I)
        if not rows_raw:
            return None

        parsed_rows: list[list[str]] = []
        for row_html in rows_raw:
            cells = re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", row_html, re.I)
            clean_cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
            if any(clean_cells):
                parsed_rows.append(clean_cells)

        if not parsed_rows:
            return None

        headers = parsed_rows[0] if parsed_rows else []
        data_rows = parsed_rows[1:] if len(parsed_rows) > 1 else []
        return {"headers": headers, "rows": data_rows, "title": "Financial Table"}
    except Exception:
        return None
