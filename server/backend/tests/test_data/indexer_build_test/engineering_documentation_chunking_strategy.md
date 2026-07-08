# Large Engineering Design

This engineering document is intentionally long enough to exercise Markdown-aware splitting.

## Overview

The indexing pipeline scans repository files, detects supported languages, reads content,
splits content into chunks, embeds each chunk, and stores the resulting points in Qdrant.

The system must preserve enough context in each chunk for retrieval to be useful. Engineering
documents often encode context through headings, sections, and subsections rather than classes
or functions.

## Requirements

The chunker should keep related engineering documentation together where possible. A section
about deployment should not be mixed with a section about API behavior unless the file is too
small or overlap makes that useful.

The indexer should mark engineering documentation chunks as doc chunks. This allows downstream
features to display documentation search results differently than source code search results.

## Architecture

The code path uses code-oriented separators. These separators include common declaration
boundaries such as classes, functions, interfaces, types, constants, and language-specific
constructs.

The documentation path uses Markdown-oriented separators. These separators include headings,
subheadings, fenced code blocks, paragraphs, lines, sentences, and words.

## Chunking Strategy

Markdown files should split on top-level headings first. If a section is still too large,
the splitter should continue with lower-level headings, fenced code blocks, paragraphs, and
sentences.

This strategy works better for engineering docs because a heading usually defines the semantic
scope of the following paragraphs.

## Search Behavior

Search results should include the file path, language, line range, content, and type. The type
field is especially important because a caller may want to bias toward source code or
engineering documentation depending on the user question.

## Operations

Operational runbooks, architecture decision records, deployment notes, and troubleshooting
guides should all be indexed as engineering documentation when they are Markdown files.

## Final Notes

This fixture verifies that Markdown files are not treated as normal code files and that their
payload type is stored as doc.
