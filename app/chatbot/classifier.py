"""Compatibility wrapper for the production classifier implementation."""

from app.chatbot.new_classifier import (
    TYPE_NAMES,
    classify_complaint_type,
    extract_complaint_schema,
    extract_local_complaint_schema,
    has_physical_lookup_signal,
    extract_unknown_equipment,
    keyword_match,
    preprocess,
    extract_keywords,
    normalize,
    generate_phrases,
    process_complaint,
)

__all__ = [
    "TYPE_NAMES",
    "classify_complaint_type",
    "extract_complaint_schema",
    "extract_local_complaint_schema",
    "has_physical_lookup_signal",
    "extract_unknown_equipment",
    "keyword_match",
    "preprocess",
    "extract_keywords",
    "normalize",
    "generate_phrases",
    "process_complaint",
]
