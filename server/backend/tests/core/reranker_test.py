import datetime

import pytest
from flashrank import Ranker

from core.reranker import Reranker


class TestReranker:
    @pytest.fixture(scope='function', autouse=True)
    def setup_teardown(self):
        yield

    def test_init(self):
        ranker = Reranker('test')
        assert ranker.name == 'test'
        assert ranker.model == "ms-marco-MiniLM-L-12-v2"
        assert ranker.cache_dir == '/opt'
        assert isinstance(ranker.ranker, Ranker)

    def test_rerank(self):
        ranker = Reranker('test')
        modified = datetime.datetime.now().timestamp()

        # pass no candidates
        assert ranker.rerank('test', [], 10) == []

        # test with some candidates we're not testing flashrank
        # just that it handle the input format and returns the expected output
        candidates = [
            {
                'score': 1.0,
                "file_path": 'test.cpp',
                "language": 'cpp',
                "start_line": 1,
                "end_line": 10,
                "content": 'test text',
                "type": 'code',
                "modified": modified,
            },
            {
                'score': 1.1,
                "file_path": 'test.cpp',
                "language": 'cpp',
                "start_line": 1,
                "end_line": 10,
                "content": 'next text',
                "type": 'code',
                "modified": modified,
            }
        ]

        rankings = ranker.rerank('test', candidates, 10)
        assert len(rankings) == 2
        assert rankings == [
            {
                'score': 1.0,
                "file_path": 'test.cpp',
                "language": 'cpp',
                "start_line": 1,
                "end_line": 10,
                "content": 'test text',
                "type": 'code',
                "modified": modified,
                'rerank_score':0.6766034,
            },
            {
                'score': 1.1,
                "file_path": 'test.cpp',
                "language": 'cpp',
                "start_line": 1,
                "end_line": 10,
                "content": 'next text',
                "type": 'code',
                "modified": modified,
                'rerank_score': 2.6028349e-05,
            }
        ]

    def test_get_create_ranker(self):
        with pytest.raises(RuntimeError, match="Failed to find reranker with name: no_name"):
            Reranker.get_ranker('no_name')

        ranker = Reranker.get_or_create_reranker('test')
        assert ranker is not None
        assert 'test' in Reranker._rankers

        ranker = None
        ranker = Reranker.get_or_create_reranker('test')
        assert ranker is not None

        ranker = None
        ranker = Reranker.get_ranker('test')
        assert ranker is not None

        with pytest.raises(RuntimeError, match="A reranker exists with name 'test' but it has a different model or cache directory than requested"):
            Reranker.get_or_create_reranker('test', cache_dir='test')