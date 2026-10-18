"""Focused local tests for the article-only adapter."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('article', Path(__file__).with_name('article.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class ArticleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def file(self, name, contents):
        path = self.root / name
        path.write_text(contents, encoding='utf-8')
        return path

    def inventory(self, contents=None):
        return a.vocab.load_export(self.file('export.tsv', contents or (
            '私\tわたし\tKNOWN\nは\tは\tKNOWN\nが\tが\tKNOWN\n'
            '好き\tすき\tKNOWN\nです\tです\tKNOWN\n')))

    def score(self, text, export=None, ranks=None, **kwargs):
        return a.analyze_article(text, export or self.inventory(), ranks or {'猫': 500, '犬': 600},
                                 state=kwargs.pop('state', {'known_words': [], 'relearning_words': []}), **kwargs)

    def test_no_media_or_timestamp_fields_anywhere(self):
        result = self.score('私は猫が好きです。')
        forbidden = {'start', 'end', 'duration', 'times', 'time', 'caption', 'sections', 'recommended_sections', 'audio'}

        def walk(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    self.assertNotIn(key.lower(), forbidden)
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
        walk(result)
        self.assertEqual(result['article_japanese_character_count'], 8)
        self.assertEqual(result['rows'][0]['examples'][0]['reference'],
                         {'paragraph': 1, 'internal_paragraph_position': 1, 'sentence': 1})

    def test_repeated_article_text_is_retained_with_paragraph_references(self):
        result = self.score('猫。\n\n猫。')
        row = next(row for row in result['rows'] if row['word'] == '猫')
        self.assertEqual(row['count'], 2)
        self.assertEqual([ref['paragraph'] for ref in row['paragraph_references']], [1, 2])
        self.assertEqual([paragraph['text'] for paragraph in result['paragraphs']], ['猫。', '猫。'])

    def test_explicit_known_override_affects_coverage(self):
        export = self.inventory('猫\tねこ\tLEARNING\n')
        result = self.score('猫。', export, state={'known_words': ['猫'], 'relearning_words': []})
        self.assertEqual(result['coverage']['known_pct'], 100)
        self.assertEqual(result['coverage']['familiar_pct'], 100)
        self.assertEqual(result['rows'], [])

    def test_empty_article_fails_visibly(self):
        for text in ('', ' \n\n '):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'empty'):
                self.score(text)

    def test_incomplete_paragraph_never_becomes_a_full_sentence_example(self):
        result = self.score('私は猫が好きです')
        row = next(row for row in result['rows'] if row['word'] == '猫')
        self.assertEqual(row['one_unknown_sentence_example_count'], 0)
        self.assertTrue(row['examples'])
        self.assertEqual(row['examples'][0]['basis'], 'paragraph_fragment_proxy_not_complete_sentence')
        self.assertNotIn('sentence', row['examples'][0]['reference'])

    def test_card_presence_labels_are_distinct(self):
        cards = a.vocab.load_cards(self.file('cards.tsv', 'word\treading\n猫\tねこ\n'))
        result = self.score('猫。犬。', cards=cards)
        by_word = {row['word']: row for row in result['rows']}
        self.assertEqual(by_word['猫']['card_evidence']['label'], 'present in supplied cards')
        self.assertEqual(by_word['犬']['card_evidence']['label'], 'not found in supplied cards')
        self.assertFalse(by_word['犬']['card_evidence']['inventory_completeness_assumed'])



if __name__ == '__main__':
    unittest.main()
