# -*- coding: utf-8 -*-
"""
LUMA — OCR (Optical Character Recognition)
===========================================
LAYERED EXTRACTION STRATEGY:

Layer 1 — AWS Textract (preferred for known form types)
    - Death certificates (standardized by state)
    - SSA-721 (federal form, fixed layout)
    - VA Form 21P-530EZ (fixed layout)
    - Insurance assignment forms
    Textract has been trained on millions of these exact forms.
    It understands form field labels and their associated values natively.

Layer 2 — Unstructured.io (fallback for unknown/messy documents)
    - Old scanned intake forms with inconsistent layouts
    - Handwritten notes
    - Proprietary CRM exports
    - Mixed-format documents from the 1980s-90s

This is Step 2 of the pipeline:
Upload → Ingest → [OCR] → Extract → Normalize → Store
"""

import os
from pathlib import Path

# Known form types where Textract excels
TEXTRACT_PREFERRED_FORMS = {
    "death_certificate",
    "ssa_721",
    "va_burial",
    "burial_permit",
    "insurance_assignment",
    "cremation_authorization",
}


def extract_text_from_document(file_path: str, form_type: str = "unknown") -> dict:
    """
    Extract all text and key-value pairs from a document.
    Uses Textract for known forms, Unstructured for everything else.

    Args:
        file_path: Path to uploaded document
        form_type: Hint about what kind of form this is

    Returns:
        dict with raw_text, key_value_pairs, elements, page_count, extractor_used
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    # Choose extraction strategy
    use_textract = (
        form_type in TEXTRACT_PREFERRED_FORMS
        and os.getenv("AWS_ACCESS_KEY_ID")  # Only if AWS configured
    )

    if use_textract:
        return _extract_with_textract(path)
    else:
        return _extract_with_unstructured(path)


def _extract_with_textract(path: Path) -> dict:
    """
    Layer 1: AWS Textract Forms API
    Best for standardized government and insurance forms.
    Returns structured key-value pairs directly from form fields.
    """
    try:
        import boto3

        textract = boto3.client(
            "textract",
            region_name=os.getenv("AWS_REGION", "us-west-2"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )

        with open(path, "rb") as f:
            doc_bytes = f.read()

        # Use FORMS feature for key-value extraction
        response = textract.analyze_document(
            Document={"Bytes": doc_bytes},
            FeatureTypes=["FORMS", "TABLES"],
        )

        # Parse Textract response into clean key-value pairs
        key_value_pairs = _parse_textract_kv(response)
        raw_text = _parse_textract_text(response)

        print(f"[OCR/Textract] Extracted {len(key_value_pairs)} KV pairs from {path.name}")

        return {
            "raw_text": raw_text,
            "elements": [],
            "key_value_pairs": key_value_pairs,
            "page_count": _count_textract_pages(response),
            "extractor_used": "textract",
            "status": "success",
        }

    except ImportError:
        print("[OCR] boto3 not installed. Falling back to Unstructured.")
        return _extract_with_unstructured(path)
    except Exception as e:
        print(f"[OCR/Textract] Error: {e}. Falling back to Unstructured.")
        return _extract_with_unstructured(path)


def _extract_with_unstructured(path: Path) -> dict:
    """
    Layer 2: Unstructured.io
    Fallback for documents without standardized layouts.
    Handles mixed content: scans, Word docs, handwritten forms.
    """
    try:
        from unstructured.partition.auto import partition

        elements = partition(filename=str(path))
        raw_text = "\n".join([str(el) for el in elements])
        key_value_pairs = _parse_kv_from_text(raw_text)

        print(f"[OCR/Unstructured] Extracted {len(elements)} elements from {path.name}")

        return {
            "raw_text": raw_text,
            "elements": [{"type": type(el).__name__, "text": str(el)} for el in elements],
            "key_value_pairs": key_value_pairs,
            "page_count": max(1, sum(1 for el in elements if "PageBreak" in type(el).__name__) + 1),
            "extractor_used": "unstructured",
            "status": "success",
        }

    except ImportError:
        print("[OCR] Unstructured not installed. Using basic text extraction.")
        return _basic_extraction(path)
    except Exception as e:
        print(f"[OCR/Unstructured] Error: {e}")
        return _basic_extraction(path)


def _basic_extraction(path: Path) -> dict:
    """Last resort: read raw text from file."""
    try:
        raw_text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        raw_text = f"[Could not read {path.name}]"

    return {
        "raw_text": raw_text,
        "elements": [],
        "key_value_pairs": _parse_kv_from_text(raw_text),
        "page_count": 1,
        "extractor_used": "basic",
        "status": "basic_extraction",
    }


def _parse_textract_kv(response: dict) -> dict:
    """Parse AWS Textract AnalyzeDocument response into key-value pairs."""
    blocks = response.get("Blocks", [])
    block_map = {b["Id"]: b for b in blocks}

    pairs = {}

    for block in blocks:
        if block["BlockType"] == "KEY_VALUE_SET" and "KEY" in block.get("EntityTypes", []):
            key_text = _get_text_from_block(block, block_map)
            value_block = _get_value_block(block, block_map)
            if value_block:
                value_text = _get_text_from_block(value_block, block_map)
                if key_text and value_text:
                    clean_key = key_text.strip().lower().replace(" ", "_").replace(":", "")
                    pairs[clean_key] = value_text.strip()

    return pairs


def _get_text_from_block(block: dict, block_map: dict) -> str:
    """Extract text from a Textract block and its children."""
    text = ""
    for rel in block.get("Relationships", []):
        if rel["Type"] == "CHILD":
            for child_id in rel["Ids"]:
                child = block_map.get(child_id, {})
                if child.get("BlockType") == "WORD":
                    text += child.get("Text", "") + " "
    return text.strip()


def _get_value_block(key_block: dict, block_map: dict):
    """Find the VALUE block associated with a KEY block."""
    for rel in key_block.get("Relationships", []):
        if rel["Type"] == "VALUE":
            for value_id in rel["Ids"]:
                return block_map.get(value_id)
    return None


def _parse_textract_text(response: dict) -> str:
    """Extract all raw text from Textract response."""
    blocks = response.get("Blocks", [])
    lines = [b["Text"] for b in blocks if b["BlockType"] == "LINE" and "Text" in b]
    return "\n".join(lines)


def _count_textract_pages(response: dict) -> int:
    pages = set()
    for block in response.get("Blocks", []):
        if "Page" in block:
            pages.add(block["Page"])
    return max(1, len(pages))


def _parse_kv_from_text(text: str) -> dict:
    """Fallback: parse key: value pairs from raw text."""
    pairs = {}
    for line in text.split("\n"):
        if ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip().lower().replace(" ", "_")
                value = parts[1].strip()
                if 2 < len(key) < 50 and 0 < len(value) < 200:
                    pairs[key] = value
    return pairs
