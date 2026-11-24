import unittest

import test_memory as fixtures


class Similarity(unittest.TestCase):
    def test_score_uses_only_normalized_metadata(self):
        from similarity import score

        self.assertEqual(score({'name': 'Answer-Format'}, {'name': 'answer_format'}), 1)
        self.assertEqual(score({'index_hook': '검증, 조건'}, {'index_hook': '검증 조건'}), 1)
        self.assertEqual(score({'aliases': '[출력 형식]'}, {'aliases': ['출력 형식']}), 1)
        self.assertEqual(score({'body': 'same body'}, {'body': 'same body'}), 0)
        self.assertEqual(score({'name': 'x'}, {'name': 'x'}), 0)

    def test_score_detects_korean_inflection(self):
        from similarity import score

        self.assertAlmostEqual(score(
            {'description': '응답 형식은 요청한 형식을 그대로 따른다'},
            {'description': '응답의 형식을 사용자 요청대로 맞춘다'},
        ), 0.2)

    def test_candidates_include_other_types_and_do_not_block_inactive_notes(self):
        from memory import Note
        from similarity import candidates

        request = {'name': 'answer_format', 'description': '답변 형식 선호'}
        notes = [
            Note('user/answer_format.md', '', {**request, 'type': 'user'}, ''),
            Note('_archive/feedback/answer_format.md', '', {**request, 'status': 'archived'}, ''),
            Note('projects/demo/feedback/answer_format.md', '', request, ''),
        ]
        result = candidates(request, notes, '', warn=0.2, block=0.8)
        self.assertEqual([(n.rel, n.level, n.score) for n in result],
                         [('_archive/feedback/answer_format.md', 'warn', 1),
                          ('user/answer_format.md', 'block', 1)])
