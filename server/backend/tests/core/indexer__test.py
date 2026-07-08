
import datetime
import os
import shutil
from unittest.mock import patch

import pytest
from ollama import Client
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import PointStruct

from config import QDRANT_URL, SPARSE_VECTOR_NAME
from core.directory_file_manager import DirectoryFileManager
from core.indexer_ import CodeIndexer
from core.reranker import Reranker
from core.wayne_ignorer import WayneIgnorer


class TestIndexer:
    @pytest.fixture(scope='function', autouse=True)
    def setup_teardown(self):
        self._repo_path = '/test_code_indexer'
        os.makedirs(self._repo_path)
        yield
        shutil.rmtree(self._repo_path)

    def _mock_ollama_embeddings(self, ollama_client):
        instance = ollama_client.return_value
        mock_embedding = []
        for i in range(0, 768):
            mock_embedding.append(float(i))
        instance.embeddings.return_value = {'embedding': mock_embedding}
        return instance

    def test_init_no_cache(self) -> None:
        collection_name = 'test_collection'
        indexer = CodeIndexer(collection_name)

        assert indexer.collection == collection_name
        assert isinstance(indexer.ollama, Client)
        assert isinstance(indexer.reranker, Reranker)
        assert len(indexer._files_cache) == 0

        qd_client = QdrantClient(url=QDRANT_URL)

        assert qd_client.collection_exists(collection_name)

    def test_init_cache_files(self) -> None:
        collection_name = 'test_collection_cache'
        modified = int(datetime.datetime.now().timestamp())
        dense1 = []
        for i in range(0, 768):
            dense1.append(float(i))

        dense2 = []
        for i in range(0, 768):
            dense2.append(float(i+768))

        points = [
            PointStruct(
                id=1,
                vector={
                    "dense": dense1,
                    SPARSE_VECTOR_NAME:models.Document(text='test', model='Qdrant/bm25')
                },
                payload={
                    "file_path": 'test.txt',
                    "language": 'Python',
                    "start_line": 1,
                    "end_line": 10,
                    "content": 'test',
                    "type": 'code',
                    "modified": modified,
                }
            ),
            PointStruct(
                id=2,
                vector={
                    "dense": dense2,
                    SPARSE_VECTOR_NAME: models.Document(text='test 2', model='Qdrant/bm25')
                },
                payload={
                    "file_path": 'test2.txt',
                    "language": 'Python',
                    "start_line": 1,
                    "end_line": 10,
                    "content": 'test 2',
                    "type": 'code',
                    "modified": modified,
                }
            )
        ]

        # we use the CodeIndexer itself to create the collection for us
        indexer = CodeIndexer(collection_name)
        qd_client = QdrantClient(url=QDRANT_URL)
        qd_client.upsert(collection_name=collection_name, points=points)

        indexer = CodeIndexer(collection_name)

        assert len(indexer._files_cache) == 2

        assert indexer._files_cache == {
            'test.txt':{
                'path':'test.txt',
                'language':'Python',
                'modified':modified,
            },
            'test2.txt':{
                'path': 'test2.txt',
                'language': 'Python',
                'modified': modified,
            }
        }

    def test_build_index_cache(self) -> None:
        with patch('core.indexer_.ollama_lib.Client') as ollama_client:
            self._mock_ollama_embeddings(ollama_client)

            collection_name = 'test_collection_index_cache'

            base_dir_path = '/app/tests/test_data/indexer_build_test'
            dir_scanner = DirectoryFileManager(base_dir_path, ignorers=[
                WayneIgnorer(base_dir_path),
            ])
            dir_scanner.scan_directory()
            file_list = dir_scanner.file_list

            indexer = CodeIndexer(collection_name)
            # a file that doesn't exist
            file_list['/i_dont_exist.txt'] = 10

            cpp_file_path = f'{base_dir_path}/test_cpp.cpp'
            python_file_path = f'{base_dir_path}/test_python.py'
            engineering_doc_path = f'{base_dir_path}/engineering_documentation_indexer.md'
            large_engineering_doc_path = f'{base_dir_path}/engineering_documentation_chunking_strategy.md'
            # we set up a condition from one of the file to be in cache but wil an
            # older modified time so it's updated but not in the db so we can see it
            # added as well
            indexer._files_cache[python_file_path] = {
                'path':python_file_path,
                'language':'Python',
                'modified':0
            }

            indexer.build_index(file_list)

            assert len(indexer._files_cache) == 4
            assert indexer._files_cache == {
                python_file_path:{
                    'path': python_file_path,
                    'language': 'Python',
                    'modified': int(os.path.getmtime(python_file_path)),
                },
                cpp_file_path:{
                    'path': cpp_file_path,
                    'language': 'C++',
                    'modified': int(os.path.getmtime(cpp_file_path)),
                },
                engineering_doc_path:{
                    'path': engineering_doc_path,
                    'language': 'Markdown',
                    'modified': int(os.path.getmtime(engineering_doc_path)),
                },
                large_engineering_doc_path:{
                    'path': large_engineering_doc_path,
                    'language': 'Markdown',
                    'modified': int(os.path.getmtime(large_engineering_doc_path)),
                }
            }

            assert indexer._files_cache[python_file_path]['modified'] == int(os.path.getmtime(python_file_path))

            qd_client = QdrantClient(url=QDRANT_URL)

            records, _ = qd_client.scroll(collection_name=collection_name, with_payload=True)
            print(records)

    def test_build_index_sets_code_and_doc_chunk_types(self) -> None:
        with patch('core.indexer_.ollama_lib.Client') as ollama_client:
            self._mock_ollama_embeddings(ollama_client)

            collection_name = 'test_collection_code_and_doc_chunk_types'
            base_dir_path = '/app/tests/test_data/indexer_build_test'

            python_file_path = f'{base_dir_path}/test_python.py'
            engineering_doc_path = f'{base_dir_path}/engineering_documentation_indexer.md'
            file_list = {
                python_file_path: int(os.path.getmtime(python_file_path)),
                engineering_doc_path: int(os.path.getmtime(engineering_doc_path)),
            }

            indexer = CodeIndexer(collection_name)
            indexer.build_index(file_list)

            qd_client = QdrantClient(url=QDRANT_URL)
            records, _ = qd_client.scroll(
                collection_name=collection_name,
                limit=100,
                with_payload=True,
            )

            python_records = [
                record for record in records
                if record.payload['file_path'] == python_file_path
            ]
            doc_records = [
                record for record in records
                if record.payload['file_path'] == engineering_doc_path
            ]

            assert len(python_records) > 0
            assert len(doc_records) > 0

            assert {record.payload['type'] for record in python_records} == {'code'}
            assert {record.payload['type'] for record in doc_records} == {'doc'}

            assert {record.payload['language'] for record in python_records} == {'Python'}
            assert {record.payload['language'] for record in doc_records} == {'Markdown'}

    def test_engineering_markdown_chunks_preserve_heading_content_and_line_numbers(self) -> None:
        with patch('core.indexer_.ollama_lib.Client') as ollama_client:
            self._mock_ollama_embeddings(ollama_client)

            collection_name = 'test_collection_engineering_markdown_chunks'
            base_dir_path = '/app/tests/test_data/indexer_build_test'
            engineering_doc_path = f'{base_dir_path}/engineering_documentation_indexer.md'
            file_list = {
                engineering_doc_path: int(os.path.getmtime(engineering_doc_path)),
            }

            indexer = CodeIndexer(collection_name)
            indexer.build_index(file_list)

            qd_client = QdrantClient(url=QDRANT_URL)
            records, _ = qd_client.scroll(
                collection_name=collection_name,
                limit=100,
                with_payload=True,
            )

            doc_records = [
                record for record in records
                if record.payload['file_path'] == engineering_doc_path
            ]

            assert len(doc_records) > 0

            contents = '\n'.join(record.payload['content'] for record in doc_records)
            assert 'Simple Document Test' in contents
            assert '## Section 1' in contents
            assert '### Subsection 1.1' in contents
            assert 'type `doc`' not in contents  # This is from the original documentation, but not in this test file

            for record in doc_records:
                assert record.payload['type'] == 'doc'
                assert record.payload['start_line'] >= 1
                assert record.payload['end_line'] >= record.payload['start_line']

    def test_engineering_markdown_chunks_complex_structure(self) -> None:
        with patch('core.indexer_.ollama_lib.Client') as ollama_client:
            self._mock_ollama_embeddings(ollama_client)

            collection_name = 'test_collection_engineering_markdown_chunks_complex'
            base_dir_path = '/app/tests/test_data/indexer_build_test'
            engineering_doc_path = f'{base_dir_path}/engineering_documentation_chunking_strategy.md'
            file_list = {
                engineering_doc_path: int(os.path.getmtime(engineering_doc_path)),
            }

            indexer = CodeIndexer(collection_name)
            indexer.build_index(file_list)

            qd_client = QdrantClient(url=QDRANT_URL)
            records, _ = qd_client.scroll(
                collection_name=collection_name,
                limit=100,
                with_payload=True,
            )

            doc_records = [
                record for record in records
                if record.payload['file_path'] == engineering_doc_path
            ]

            assert len(doc_records) > 0

            contents = '\n'.join(record.payload['content'] for record in doc_records)
            assert 'Large Engineering Design' in contents
            assert '## Overview' in contents
            assert '## Requirements' in contents
            assert '## Architecture' in contents
            assert '## Chunking Strategy' in contents

            for record in doc_records:
                assert record.payload['type'] == 'doc'
                assert record.payload['start_line'] >= 1
                assert record.payload['end_line'] >= record.payload['start_line']

    def test_code_chunks_use_code_type_and_code_language(self) -> None:
        with patch('core.indexer_.ollama_lib.Client') as ollama_client:
            self._mock_ollama_embeddings(ollama_client)

            collection_name = 'test_collection_code_chunks'
            base_dir_path = '/app/tests/test_data/indexer_build_test'
            python_file_path = f'{base_dir_path}/test_python.py'
            file_list = {
                python_file_path: int(os.path.getmtime(python_file_path)),
            }

            indexer = CodeIndexer(collection_name)
            indexer.build_index(file_list)

            qd_client = QdrantClient(url=QDRANT_URL)
            records, _ = qd_client.scroll(
                collection_name=collection_name,
                limit=100,
                with_payload=True,
            )

            code_records = [
                record for record in records
                if record.payload['file_path'] == python_file_path
            ]

            assert len(code_records) > 0

            for record in code_records:
                assert record.payload['type'] == 'code'
                assert record.payload['language'] == 'Python'
                assert record.payload['start_line'] >= 1
                assert record.payload['end_line'] >= record.payload['start_line']
                assert record.payload['content'].strip() != ''