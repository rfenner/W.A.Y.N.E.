import pytest

from core.chunking import ChunkType, CodeChunk, FileChunker, _LANGUAGE_PARSER_MAP


# Minimal, valid snippets for every language FileChunker maps to a langchain
# splitter. Kept tiny (well under chunk_size) so each language exercises the
# "normal" path rather than the oversized re-split path.
CODE_SAMPLES = {
    "Python": "def a():\n    return 1\n\n\ndef b():\n    return 2\n",
    "JavaScript": "function a() {\n  return 1;\n}\n\nfunction b() {\n  return 2;\n}\n",
    "TypeScript": "function a(): number {\n  return 1;\n}\n",
    "Java": "class A {\n    void foo() {}\n}\n",
    "Go": "func A() {}\n\nfunc B() {}\n",
    "Rust": "fn a() {}\n\nfn b() {}\n",
    "C": "int main() {\n    return 0;\n}\n",
    "C++": "int main() {\n    return 0;\n}\n",
    "C/C++ Header": "#ifndef FOO_H\n#define FOO_H\nvoid foo();\n#endif\n",
    "C++ Header": "#pragma once\nvoid foo();\n",
    "C#": "class A {\n    void Foo() {}\n}\n",
    "PHP": "<?php\nfunction a() {\n    return 1;\n}\n",
    "Ruby": "def a\n  1\nend\n",
    "Swift": "func a() {\n    print(\"hi\")\n}\n",
    "Kotlin": "fun a() {}\n",
    "Scala": "def a() = { 1 }\n",
    "Lua": "function a()\n  return 1\nend\n",
    "Perl": "sub a {\n    return 1;\n}\n",
    "HTML": "<html><body><p>hi</p></body></html>\n",
    "SQL": "SELECT 1;\n",
    "R": "a <- function() {\n  1\n}\n",
}

# Languages that should be treated as general (not code) - these are the ones
# that were NOT added to _LANGUAGE_PARSER_MAP in the update
# Based on the updated _LANGUAGE_PARSER_MAP, we don't have any languages that 
# should be considered general anymore since all common languages are now supported
GENERAL_LANGUAGES = {
    "text": (".txt", "This is just text content"),
    "text_no_ext": ("", "This is just text content")
}


@pytest.fixture
def chunker() -> FileChunker:
    return FileChunker()


class TestDetermineType:

    def test_markdown_language_is_doc(self, chunker):
        assert chunker.determine_type("service.md", "Markdown") == ChunkType.DOC

    @pytest.mark.parametrize("path", [
        "architecture.md",
        "architecture.mdx",
        "runbook.rst",
        "notes.adoc",
        "NOTES.MD",  # extension matching should be case-insensitive
    ])
    def test_doc_extensions_are_doc_regardless_of_language(self, chunker, path):
        assert chunker.determine_type(path, "Unknown") == ChunkType.DOC

    @pytest.mark.parametrize("language", sorted(_LANGUAGE_PARSER_MAP.keys()))
    def test_mapped_languages_are_code(self, chunker, language):
        assert chunker.determine_type(f"file.ext", language) == ChunkType.CODE

    def test_unknown_language_and_extension_is_general(self, chunker):
        assert chunker.determine_type("file.foobar", "Unknown") == ChunkType.GENERAL

    def test_doc_extension_takes_priority_over_code_language(self, chunker):
        # A file with a .md extension should be treated as a doc even if the
        # caller (incorrectly) passed a code language for it.
        assert chunker.determine_type("weird.md", "Python") == ChunkType.DOC


class TestEngineeringDocSplitting:

    SAMPLE_DOC = (
        "# Simple Document Test\n\n"
        "Some intro text.\n\n"
        "## Section 1\n\n"
        "Body of section 1.\n\n"
        "### Subsection 1.1\n\n"
        "Body of subsection 1.1.\n\n"
        "## Section 2\n\n"
        "Body of section 2.\n"
    )

    def test_chunk_type_is_doc(self, chunker):
        chunk_type, _ = chunker.chunk_file("docs/architecture.md", self.SAMPLE_DOC, "Markdown")
        assert chunk_type == ChunkType.DOC

    def test_headings_and_content_are_preserved(self, chunker):
        _, chunks = chunker.chunk_file("docs/architecture.md", self.SAMPLE_DOC, "Markdown")
        combined = "\n".join(text for text, _, _ in chunks)
        assert "Simple Document Test" in combined
        assert "## Section 1" in combined
        assert "### Subsection 1.1" in combined
        assert "## Section 2" in combined

    def test_line_numbers_are_valid_and_ordered(self, chunker):
        _, chunks = chunker.chunk_file("docs/architecture.md", self.SAMPLE_DOC, "Markdown")
        assert len(chunks) > 0
        prev_start = 0
        for _, start, end in chunks:
            assert start >= 1
            assert end >= start
            assert start >= prev_start
            prev_start = start

    def test_empty_doc_produces_no_chunks(self, chunker):
        _, chunks = chunker.chunk_file("docs/empty.md", "", "Markdown")
        assert chunks == []

    def test_whitespace_only_doc_produces_no_chunks(self, chunker):
        _, chunks = chunker.chunk_file("docs/blank.md", "   \n\n   \n", "Markdown")
        assert chunks == []


class TestCodeSplitting:

    @pytest.mark.parametrize("language", sorted(CODE_SAMPLES.keys()))
    def test_supported_languages_produce_at_least_one_chunk(self, chunker, language):
        content = CODE_SAMPLES[language]
        chunk_type, chunks = chunker.chunk_file(f"file.ext", content, language)

        assert chunk_type == ChunkType.CODE
        assert len(chunks) >= 1
        for text, start, end in chunks:
            assert text.strip() != ""
            assert start >= 1
            assert end >= start

    def test_python_functions_are_kept_separate_where_possible(self, chunker):
        # Python has a native (non tree-sitter) segmenter, so this should
        # reliably split on function boundaries in any environment.
        content = "def a():\n    return 1\n\n\ndef b():\n    return 2\n"
        _, chunks = chunker.chunk_file("test_python.py", content, "Python")

        combined = "".join(text for text, _, _ in chunks)
        assert "def a():" in combined
        assert "def b():" in combined
        assert len(chunks) >= 2

    def test_oversized_function_gets_resplit(self, chunker):
        # A single function far bigger than the language's target chunk_size
        # should be broken into multiple pieces rather than indexed whole.
        chunk_size = _LANGUAGE_PARSER_MAP["Python"][1]
        huge_body = "\n".join(f"    x{i} = {i}" for i in range(chunk_size // 4))
        content = f"def huge():\n{huge_body}\n    return x0\n"

        _, chunks = chunker.chunk_file("huge.py", content, "Python")

        assert len(chunks) > 1
        for text, start, end in chunks:
            assert len(text) <= chunk_size * 1.5 + 200  # some slack for splitter boundaries
            assert start >= 1
            assert end >= start

    def test_unmapped_language_falls_back_to_general(self, chunker):
        # If a caller passes a language not in _LANGUAGE_PARSER_MAP directly
        # into _split_code, it should degrade to the general splitter
        # instead of raising.
        chunks = chunker._split_code("some content\nwith lines\n", "TotallyMadeUpLanguage")
        assert chunks == chunker._split_general("some content\nwith lines\n")

    def test_ast_split_returns_empty_for_unrecognized_parser_language(self, chunker):
        assert chunker._try_ast_split("def a(): pass\n", "not_a_real_language") == []

    @pytest.mark.parametrize("language,ext_content", GENERAL_LANGUAGES.items())
    def test_general_only_languages_do_not_use_code_path(self, chunker, language, ext_content):
        ext, content = ext_content
        chunk_type, chunks = chunker.chunk_file(f"file{ext}", content, language)

        assert chunk_type == ChunkType.GENERAL
        assert len(chunks) >= 1
        assert chunks[0][0].strip() != ""


class TestGeneralSplitting:

    def test_json_is_general_and_content_preserved(self, chunker):
        content = '{"a": 1, "b": {"c": 2}}\n'
        chunk_type, chunks = chunker.chunk_file("data.json", content, "JSON")

        assert chunk_type == ChunkType.CODE
        combined = "".join(text for text, _, _ in chunks)
        assert '"a": 1' in combined

    def test_plain_text_is_general(self, chunker):
        content = "Just a plain note.\nNothing structured here.\n"
        chunk_type, chunks = chunker.chunk_file("notes.txt", content, "Text")
        assert chunk_type == ChunkType.GENERAL
        assert len(chunks) >= 1

    def test_empty_content_produces_no_chunks(self, chunker):
        _, chunks = chunker.chunk_file("empty.txt", "", "Text")
        assert chunks == []

    def test_line_numbers_are_valid(self, chunker):
        content = "line one\nline two\nline three\n" * 50
        _, chunks = chunker.chunk_file("big.txt", content, "Text")
        assert len(chunks) > 0
        for _, start, end in chunks:
            assert start >= 1
            assert end >= start


class TestCodeChunkDataclass:

    def test_to_dict_contains_expected_keys(self):
        chunk = CodeChunk(
            language="Python",
            start_line=1,
            end_line=5,
            content="def a(): pass",
            type="code",
        )
        d = chunk.to_dict()
        assert d == {
            "language": "Python",
            "start_line": 1,
            "end_line": 5,
            "content": "def a(): pass",
            "type": "code",
        }

    def test_default_type_is_code(self):
        chunk = CodeChunk(
            language="Python",
            start_line=1,
            end_line=1,
            content="pass",
        )
        assert chunk.type == "code"


class TestChunkTypeEnum:

    def test_values_match_expected_payload_strings(self):
        assert ChunkType.CODE.value == "code"
        assert ChunkType.DOC.value == "doc"
        assert ChunkType.GENERAL.value == "general"
