"""
File chunking strategies.

This module owns the question "given a file's language/extension and its
content, how should it be split into chunks?" It exposes a single entry
point, `FileChunker.chunk`, which:

  1. Determines the content category for the file (engineering doc, code,
     or general-purpose text/data).
  2. Dispatches to the splitter best suited to that category:
       - Engineering docs (Markdown/RST/AsciiDoc) -> structure-aware split
         on headings/code fences before falling back to size.
       - Source code                              -> language-aware split
         via langchain_community's LanguageParser when available, else a
         generic recursive splitter tuned for code.
       - Everything else (JSON, YAML, CSS, plain text, unknown types...)
         -> a general-purpose recursive character splitter.

Callers (e.g. an indexer) don't need to know which splitter ran; they just
get back the resolved ChunkType and a list of (text, start_line, end_line)
tuples with 1-based, inclusive-ish line numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Tuple


class ChunkType(str, Enum):
    CODE = "code"
    DOC = "doc"
    GENERAL = "general"


@dataclass
class CodeChunk:
    language: str
    start_line: int
    end_line: int
    content: str
    type: str = "code"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language": self.language,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
            "type": self.type,
        }


# Languages we can chunk with langchain's language-aware splitters.
# Two tiers of support, both handled transparently by _split_code:
#   - AST-aware (langchain_community's tree-sitter LanguageParser): python,
#     js, ts, java, c, cpp, csharp, ruby, rust, scala, go, kotlin, lua, perl,
#     elixir, sql, cobol. Best quality: keeps whole functions/classes together.
#   - Character-splitter only (langchain_text_splitters.Language, no AST):
#     swift, html, r, markdown, latex, sol, haskell, powershell,
#     visualbasic6, proto, rst. Still splits on that language's natural
#     syntax boundaries (e.g. "\nfunc ", "\nclass "), just without parsing.
# language (from CODE_EXTENSIONS) -> (Language value, chunk_size, chunk_overlap)
_LANGUAGE_PARSER_MAP: Dict[str, Tuple[str, int, int]] = {
    "Python": ("python", 900, 120),
    "JavaScript": ("js", 800, 120),
    "TypeScript": ("ts", 800, 120),
    "Java": ("java", 1000, 120),
    "Go": ("go", 900, 120),
    "Rust": ("rust", 950, 120),
    "C": ("c", 900, 120),
    "C++": ("cpp", 1200, 120),
    "C/C++ Header": ("cpp", 900, 120),
    "C++ Header": ("cpp", 900, 120),
    "C#": ("csharp", 1000, 120),
    "PHP": ("php", 900, 120),
    "Ruby": ("ruby", 900, 120),
    "Swift": ("swift", 900, 120),
    "Kotlin": ("kotlin", 900, 120),
    "Scala": ("scala", 900, 120),
    "Lua": ("lua", 800, 120),
    "Perl": ("perl", 800, 120),
    "HTML": ("html", 900, 120),
    "SQL": ("sql", 900, 120),
    "R": ("r", 900, 120),
    # Deliberately NOT here (no langchain support at all, neither AST nor
    # character-splitter, so they fall through to ChunkType.GENERAL):
    # Objective-C, Objective-C++, Shell, Terraform, CSS/SCSS/SASS/Less,
    # JSON, XML, YAML, Text, VimL.
    
    # Adding support for additional languages that may be in CODE_EXTENSIONS
    "Objective-C": ("objc", 900, 120),
    "Objective-C++": ("objcpp", 900, 120),
    "Shell": ("bash", 900, 120),
    "Terraform": ("terraform", 900, 120),
    "CSS": ("css", 900, 120),
    "SCSS": ("scss", 900, 120),
    "SASS": ("sass", 900, 120),
    "Less": ("less", 900, 120),
    "JSON": ("json", 900, 120),
    "XML": ("xml", 900, 120),
    "YAML": ("yaml", 900, 120),
    "VimL": ("vim", 900, 120),
}

# Extensions/languages treated as "engineering docs" -> markdown-aware split
_DOC_EXTENSIONS = {".md", ".mdx", ".rst", ".adoc"}
_DOC_LANGUAGES = {"Markdown"}


class FileChunker:
    """Determines the right chunking strategy for a file and applies it."""

    # ─── strategy selection ────────────────────────────────────────────

    def determine_type(self, file_path: str, language: str) -> ChunkType:
        """Classify a file as DOC, CODE, or GENERAL based on its language/extension."""
        suffix = Path(file_path).suffix.lower()

        if language in _DOC_LANGUAGES or suffix in _DOC_EXTENSIONS:
            return ChunkType.DOC

        if language in _LANGUAGE_PARSER_MAP:
            return ChunkType.CODE

        return ChunkType.GENERAL

    def chunk_text(self, content: str, language: str) -> Tuple[ChunkType, List[Tuple[str, int, int]]]:
        """
        Split text content using the strategy appropriate for the given language.
        
        Returns (chunk_type, [(chunk_text, start_line, end_line), ...]).
        """
        # Determine the chunk type based on language
        chunk_type = self.determine_type("temp_file", language)
        
        if chunk_type == ChunkType.DOC:
            chunks = self._split_engineering_doc(content)
        elif chunk_type == ChunkType.CODE:
            chunks = self._split_code(content, language)
        else:
            chunks = self._split_general(content)

        return chunk_type, chunks

    def chunk_file(
        self, file_path: str, content: str, language: str
    ) -> Tuple[ChunkType, List[Tuple[str, int, int]]]:
        """
        Split `content` using the strategy appropriate for `file_path`/`language`.

        Returns (chunk_type, [(chunk_text, start_line, end_line), ...]).
        """
        chunk_type = self.determine_type(file_path, language)

        if chunk_type == ChunkType.DOC:
            chunks = self._split_engineering_doc(content)
        elif chunk_type == ChunkType.CODE:
            chunks = self._split_code(content, language)
        else:
            chunks = self._split_general(content)

        return chunk_type, chunks

    # ─── shared helper ──────────────────────────────────────────────────

    def _chunk_with_line_numbers(
        self,
        content: str,
        splitter,
    ) -> List[Tuple[str, int, int]]:
        """Split content and calculate 1-based start/end lines for each chunk."""
        chunks = []
        search_from = 0

        for chunk_text in splitter.split_text(content):
            if not chunk_text.strip():
                continue

            chunk_start = content.find(chunk_text, search_from)
            if chunk_start == -1:
                chunk_start = content.find(chunk_text)

            if chunk_start == -1:
                start_line = 1
                end_line = max(1, content.count("\n") + 1)
            else:
                chunk_end = chunk_start + len(chunk_text)
                start_line = content.count("\n", 0, chunk_start) + 1
                end_line = content.count("\n", 0, chunk_end) + 1
                search_from = chunk_end

            chunks.append((chunk_text, start_line, end_line))

        return chunks

    # ─── strategy: source code ──────────────────────────────────────────

    def _split_code(self, content: str, language: str) -> List[Tuple[str, int, int]]:
        """Split source code using code-oriented boundaries."""
        parser_info = _LANGUAGE_PARSER_MAP.get(language)

        if parser_info is None:
            # Shouldn't normally happen (determine_type already filtered),
            # but fall back safely if it does.
            return self._split_general(content)

        parser_lang, chunk_size, chunk_overlap = parser_info

        # 1) Try AST-aware splitting via tree-sitter (best quality: whole
        #    functions/classes stay together). Only a subset of languages
        #    have a tree-sitter segmenter; others raise and we fall through.
        ast_chunks = self._try_ast_split(content, parser_lang)
        if ast_chunks:
            final: List[Tuple[str, int, int]] = []
            for text, start, end in ast_chunks:
                if len(text) <= chunk_size * 1.5:
                    final.append((text, start, end))
                else:
                    # A single function/class was still too big -> re-split
                    # it internally rather than embedding one giant chunk.
                    final.extend(
                        self._resplit_oversized(text, start, parser_lang, chunk_size, chunk_overlap)
                    )
            return final

        # 2) No AST segmenter for this language -> character-level split
        #    using that language's natural syntax boundaries (e.g. "\nclass ",
        #    "\ndef " for Python; "\nfunc " for Go) rather than blind size.
        return self._character_split_for_language(content, parser_lang, chunk_size, chunk_overlap)

    def _try_ast_split(self, content: str, parser_lang: str) -> List[Tuple[str, int, int]]:
        """Attempt tree-sitter AST-aware splitting; return [] if unsupported/failed."""
        try:
            from langchain_community.document_loaders.parsers.language.language_parser import (
                LanguageParser,
            )
            from langchain_core.document_loaders import Blob
        except Exception as e:
            return []

        try:
            parser = LanguageParser(language=parser_lang, parser_threshold=0)
            blob = Blob.from_data(content, path=f"file.{parser_lang}")
            docs = parser.parse(blob)
        except Exception:
            return []

        # Keep only the per-function/class chunks; skip the extra
        # "simplified_code" summary doc LanguageParser also emits (a
        # skeleton with function bodies replaced by comments), which is
        # redundant with the real chunks above for indexing purposes.
        texts = [
            doc.page_content
            for doc in docs
            if doc.metadata.get("content_type") == "functions_classes" and doc.page_content.strip()
        ]
        if not texts:
            return []

        return self._locate_texts(content, texts)

    def _locate_texts(self, content: str, texts: List[str]) -> List[Tuple[str, int, int]]:
        """Find each text's line span within content, in order."""
        chunks = []
        search_from = 0
        for text in texts:
            start_idx = content.find(text, search_from)
            if start_idx == -1:
                start_idx = content.find(text)

            if start_idx == -1:
                start_line = 1
                end_line = max(1, text.count("\n") + 1)
            else:
                end_idx = start_idx + len(text)
                start_line = content.count("\n", 0, start_idx) + 1
                end_line = content.count("\n", 0, end_idx) + 1
                search_from = end_idx

            chunks.append((text, start_line, end_line))
        return chunks

    def _resplit_oversized(
        self, text: str, base_start_line: int, parser_lang: str, chunk_size: int, chunk_overlap: int
    ) -> List[Tuple[str, int, int]]:
        """Further split one oversized AST chunk, offsetting line numbers relative to the file."""
        splitter = self._get_language_splitter(parser_lang, chunk_size, chunk_overlap)

        sub_chunks = []
        search_from = 0
        for sub_text in splitter.split_text(text):
            if not sub_text.strip():
                continue
            sub_start = text.find(sub_text, search_from)
            if sub_start == -1:
                sub_start = text.find(sub_text)

            if sub_start == -1:
                start_line = base_start_line
                end_line = base_start_line + sub_text.count("\n")
            else:
                sub_end = sub_start + len(sub_text)
                start_line = base_start_line + text.count("\n", 0, sub_start)
                end_line = base_start_line + text.count("\n", 0, sub_end)
                search_from = sub_end

            sub_chunks.append((sub_text, start_line, end_line))
        return sub_chunks

    def _character_split_for_language(
        self, content: str, parser_lang: str, chunk_size: int, chunk_overlap: int
    ) -> List[Tuple[str, int, int]]:
        splitter = self._get_language_splitter(parser_lang, chunk_size, chunk_overlap)
        return self._chunk_with_line_numbers(content, splitter)

    def _get_language_splitter(self, parser_lang: str, chunk_size: int, chunk_overlap: int):
        """RecursiveCharacterTextSplitter using this language's syntax-aware separators,
        falling back to generic separators if langchain doesn't know this language value."""
        from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

        try:
            return RecursiveCharacterTextSplitter.from_language(
                language=Language(parser_lang),
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        except ValueError:
            return RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=["\n\n", "\n", ". ", " ", ""],
            )

    # ─── strategy: engineering docs (Markdown/RST/AsciiDoc) ─────────────

    def _split_engineering_doc(self, content: str) -> List[Tuple[str, int, int]]:
        """Split engineering docs by Markdown structure before falling back to size."""
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200,
            chunk_overlap=160,
            separators=[
                "\n# ",
                "\n## ",
                "\n### ",
                "\n#### ",
                "\n```",
                "\n\n",
                "\n",
                ". ",
                " ",
                "",
            ],
        )
        return self._chunk_with_line_numbers(content, splitter)

    # ─── strategy: general purpose (JSON, YAML, CSS, text, etc.) ────────

    def _split_general(self, content: str) -> List[Tuple[str, int, int]]:
        """Generic size-based split for anything that isn't code or a doc."""
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=900,
            chunk_overlap=120,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        return self._chunk_with_line_numbers(content, splitter)
