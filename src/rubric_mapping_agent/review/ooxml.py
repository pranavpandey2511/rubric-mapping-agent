"""Preserve source worksheet formulas and cached values after style edits."""

from __future__ import annotations

import posixpath
import re
import xml.etree.ElementTree as ET
from contextlib import suppress
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile


SPREADSHEET_NAMESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOCUMENT_RELATIONSHIP_NAMESPACE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
PACKAGE_RELATIONSHIP_NAMESPACE = (
    "http://schemas.openxmlformats.org/package/2006/relationships"
)
CELL_ELEMENT_RE = re.compile(
    rb"<c\b(?![^>]*?/>)" rb"(?P<attributes>[^>]*)>(?P<body>.*?)</c>",
    re.DOTALL,
)
CELL_ADDRESS_RE = re.compile(rb'\br="([A-Z]{1,3}[1-9][0-9]*)"')
VALUE_ELEMENT_RE = re.compile(
    rb"<v(?:\s[^>]*)?>.*?</v\s*>|<v(?:\s[^>]*)?/>", re.DOTALL
)
FORMULA_ELEMENT_RE = re.compile(
    rb"<f(?:\s[^>]*)?>.*?</f\s*>|<f(?:\s[^>]*)?/>", re.DOTALL
)
CELL_TYPE_RE = re.compile(rb'\s+t="([^"]+)"')


def _worksheet_parts(archive: ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships.findall(
            f"{{{PACKAGE_RELATIONSHIP_NAMESPACE}}}Relationship"
        )
    }
    parts: dict[str, str] = {}
    for sheet in workbook.findall(f".//{{{SPREADSHEET_NAMESPACE}}}sheet"):
        relationship_id = sheet.attrib[
            f"{{{DOCUMENT_RELATIONSHIP_NAMESPACE}}}id"
        ]
        target = targets[relationship_id]
        if target.startswith("/"):
            part = target.lstrip("/")
        else:
            part = posixpath.normpath(posixpath.join("xl", target))
        parts[sheet.attrib["name"]] = part
    return parts


def _source_cell_payloads(
    worksheet_xml: bytes,
) -> dict[bytes, tuple[bytes | None, bytes | None, bytes | None]]:
    payloads: dict[bytes, tuple[bytes | None, bytes | None, bytes | None]] = {}
    for match in CELL_ELEMENT_RE.finditer(worksheet_xml):
        address_match = CELL_ADDRESS_RE.search(match.group("attributes"))
        body = match.group("body")
        if address_match is None:
            continue
        formula_match = FORMULA_ELEMENT_RE.search(body)
        value_match = VALUE_ELEMENT_RE.search(body)
        if formula_match is not None or value_match is not None:
            type_match = CELL_TYPE_RE.search(match.group("attributes"))
            payloads[address_match.group(1)] = (
                formula_match.group(0) if formula_match is not None else None,
                value_match.group(0) if value_match is not None else None,
                type_match.group(1) if type_match is not None else None,
            )
    return payloads


def _restore_worksheet_cell_payloads(
    worksheet_xml: bytes,
    payloads: dict[bytes, tuple[bytes | None, bytes | None, bytes | None]],
) -> bytes:
    def restore(match: re.Match[bytes]) -> bytes:
        attributes = match.group("attributes")
        body = match.group("body")
        address_match = CELL_ADDRESS_RE.search(attributes)
        if address_match is None:
            return match.group(0)
        payload = payloads.get(address_match.group(1))
        if payload is None:
            return match.group(0)
        source_formula, source_value, source_type = payload

        formula_match = FORMULA_ELEMENT_RE.search(body)
        if source_formula is not None:
            if formula_match is not None:
                body = (
                    body[: formula_match.start()]
                    + source_formula
                    + body[formula_match.end() :]
                )
            else:
                body = source_formula + body

        value_match = VALUE_ELEMENT_RE.search(body)
        if source_value is not None:
            if value_match is not None:
                body = (
                    body[: value_match.start()]
                    + source_value
                    + body[value_match.end() :]
                )
            elif source_formula is not None:
                formula_match = FORMULA_ELEMENT_RE.search(body)
                if formula_match is not None:
                    body = (
                        body[: formula_match.end()]
                        + source_value
                        + body[formula_match.end() :]
                    )
        elif source_formula is not None and value_match is not None:
            body = body[: value_match.start()] + body[value_match.end() :]

        # Shared strings become inline strings when OpenPyXL serializes them and
        # therefore cannot safely reuse the source shared-string index.
        if source_formula is not None or source_type != b"s":
            attributes = CELL_TYPE_RE.sub(b"", attributes)
            if source_type is not None:
                attributes += b' t="' + source_type + b'"'
        return b"<c" + attributes + b">" + body + b"</c>"

    return CELL_ELEMENT_RE.sub(restore, worksheet_xml)


def restore_cell_payloads(source: Path, annotated: Path) -> None:
    """Restore source formulas, scalar values, and caches after a style edit."""

    restored = annotated.with_suffix(annotated.suffix + f".{uuid4().hex}.cache.tmp")
    try:
        with ZipFile(source, "r") as source_archive, ZipFile(
            annotated, "r"
        ) as annotated_archive:
            source_parts = _worksheet_parts(source_archive)
            annotated_parts = _worksheet_parts(annotated_archive)
            modified: dict[str, bytes] = {}
            for sheet_name, source_part in source_parts.items():
                annotated_part = annotated_parts.get(sheet_name)
                if annotated_part is None:
                    continue
                payloads = _source_cell_payloads(source_archive.read(source_part))
                modified[annotated_part] = _restore_worksheet_cell_payloads(
                    annotated_archive.read(annotated_part), payloads
                )

            with ZipFile(restored, "w", compression=ZIP_DEFLATED) as restored_archive:
                for member in annotated_archive.infolist():
                    restored_archive.writestr(
                        member,
                        modified.get(member.filename, annotated_archive.read(member)),
                    )
        restored.replace(annotated)
    finally:
        with suppress(FileNotFoundError):
            restored.unlink()
