"""Local, deterministic fixtures. No iCloud or network required."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('vocab', Path(__file__).with_name('vocab.py'))
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class VocabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def file(self, name, contents):
        path = self.root / name
        path.write_text(contents, encoding='utf-8')
        return path

    def inventory(self, contents='私\tわたし\tKNOWN\nは\tは\tKNOWN\nが\tが\tKNOWN\n好き\tすき\tKNOWN\nです\tです\tKNOWN\n'):
        return v.load_export(self.file('export.tsv', contents))

    def score(self, text, export=None, ranks=None, **kwargs):
        return v.analyze(text, export or self.inventory(), ranks or {'猫': 500, '犬': 600, 'コーヒー': 700, 'わし': 800, '鈴木': 1000, '橋': 1200, '箸': 1400, '実': 900, 'コミュニケーション': 1500}, state=kwargs.pop('state', {'known_words': [], 'relearning_words': []}), **kwargs)

    def test_import_safe(self):
        self.assertTrue(callable(v.main))

    def test_headerless_export(self):
        self.assertEqual(self.inventory().exact['私'][0]['status'], 'KNOWN')

    def test_headed_export(self):
        inv = self.inventory('reading\tstatus\tword\nねこ\tlearning\t猫\n')
        self.assertEqual(inv.exact['猫'][0]['status'], 'LEARNING')

    def test_sweep_schema_rejected(self):
        with self.assertRaisesRegex(ValueError, 'schema'):
            self.inventory('word\treading\tjpdb_rank\tknow_it?\n猫\tねこ\t500\ttrue\n')

    def test_empty_invalid_exports(self):
        for contents in ('', '\t\t\n', 'word\treading\tstatus\n', '\t\tKNOWN\n', '猫\tねこ\tYES\n'):
            with self.subTest(contents=contents), self.assertRaises(ValueError):
                self.inventory(contents)

    def test_no_katakana_or_short_kana_magic(self):
        result = self.score('[00:00 - 00:05] コーヒー わし。')
        self.assertEqual(result['known_pct'], 0)
        self.assertEqual({r['word']: r['status'] for r in result['rows']}, {'コーヒー': 'NEW', 'わし': 'NEW'})

    def test_known_override_stale_learning(self):
        inv = self.inventory('コミュニケーション\tこみゅにけーしょん\tLEARNING\n')
        result = self.score('[00:00 - 00:05] コミュニケーション。', inv, state={'known_words': ['コミュニケーション'], 'relearning_words': []})
        self.assertEqual(result['known_pct'], 100)
        self.assertEqual(result['rows'], [])

    def test_learning_not_known(self):
        result = self.score('[00:00 - 00:05] 猫。', self.inventory('猫\tねこ\tLEARNING\n'))
        self.assertEqual(result['known_pct'], 0)
        self.assertEqual(result['familiar_pct'], 100)
        self.assertEqual(result['rows'][0]['status'], 'LEARNING')

    def test_homophones_no_reading_collision(self):
        result = self.score('[00:00 - 00:05] 橋。', self.inventory('箸\tはし\tKNOWN\n'))
        self.assertEqual(result['known_pct'], 0)
        self.assertEqual(result['rows'][0]['word'], '橋')
        self.assertEqual(result['rows'][0]['reading'], 'はし')

    def test_reading_fallback_ambiguous(self):
        inv = self.inventory('箸\tはし\tKNOWN\n橋\tはし\tLEARNING\n')
        self.assertIsNone(inv.match(['はし'], 'はし')[0])
        one = self.inventory('箸\tはし\tKNOWN\n')
        self.assertEqual(one.match(['はし'], 'はし')[1], 'unambiguous_kana_reading_assumption')
        self.assertIsNone(one.match(['橋'], 'はし')[0])
        self.assertIsNone(one.match([''], '')[0])

    def test_overlap_dedup_whitespace(self):
        segs, _ = v.parse_segments('[00:00 - 00:08] 私は コーヒー\n[00:04 - 00:12] コー ヒーが好きです。')
        clean, removed = v.deduplicate_segments(segs)
        self.assertEqual(clean[1]['text'], 'が好きです。')
        self.assertEqual(removed, 4)
        result = self.score('[00:00 - 00:08] 私は コーヒー\n[00:04 - 00:12] コー ヒーが好きです。')
        self.assertEqual(next(r for r in result['rows'] if r['word'] == 'コーヒー')['count'], 1)

    def test_nonoverlap_repetition_retained(self):
        result = self.score('[00:00 - 00:03] コーヒー。\n[00:03 - 00:06] コーヒー。')
        row = next(r for r in result['rows'] if r['word'] == 'コーヒー')
        self.assertEqual(row['count'], 2)
        self.assertEqual(row['times'], [0, 3])

    def test_unknown_names_uncertain(self):
        result = self.score('[00:00 - 00:05] 鈴木。')
        self.assertGreater(result['uncertain_token_count'], 0)
        self.assertEqual(result['known_pct'], 0)
        self.assertEqual(result['top_candidates'], [])

    def test_no_punctuation_no_sentence_ip1(self):
        result = self.score('[00:00 - 00:05] 私は猫が好きです')
        cat = next(r for r in result['rows'] if r['word'] == '猫')
        self.assertEqual(cat['ip1_times'], [])
        self.assertEqual(cat['ip1_clause_times'], [])
        self.assertTrue(cat['ip1_caption_times'])
        self.assertFalse(cat['example_is_ip1'])

    def test_punctuated_sentence_ip1(self):
        result = self.score('[00:00 - 00:05] 私は猫が好きです。')
        cat = next(r for r in result['rows'] if r['word'] == '猫')
        self.assertEqual(cat['ip1_times'], [0])
        self.assertTrue(cat['example_is_ip1'])

    def test_cards_learning_lower_not_excluded(self):
        inv = self.inventory('猫\tねこ\tLEARNING\n私\tわたし\tKNOWN\n')
        cards = v.load_cards(self.file('cards.tsv', 'word\treading\n猫\tねこ\n'))
        result = self.score('[00:00 - 00:05] 猫。犬。', inv, cards=cards)
        self.assertEqual([r['word'] for r in result['top_candidates']], ['犬', '猫'])
        by_word = {r['word']: r for r in result['rows']}
        self.assertEqual(by_word['猫']['card_presence'], 'present')
        self.assertEqual(by_word['犬']['card_presence'], 'not_found_in_supplied_inventory')
        self.assertFalse(by_word['犬']['card_evidence']['inventory_completeness_assumed'])

    def test_explicit_retries_only(self):
        inv = self.inventory('猫\tねこ\tKNOWN\n犬\tいぬ\tLEARNING\n')
        result = self.score('[00:00 - 00:05] 犬。猫。', inv, state={'known_words': [], 'relearning_words': ['猫']})
        self.assertEqual(result['top_candidates'][0]['word'], '猫')
        self.assertTrue(result['top_candidates'][0]['relearning'])
        self.assertEqual(result['top_candidates'][0]['status'], 'LEARNING')
        self.assertEqual(result['top_candidates'][0]['export_status'], 'KNOWN')
        self.assertEqual(result['known_pct'], 0)
        self.assertEqual(result['familiar_pct'], 100)
        self.assertFalse(next(r for r in result['rows'] if r['word'] == '犬')['relearning'])

    def test_short_sections_duration(self):
        result = self.score('[00:10 - 00:25] 猫。')
        self.assertEqual(len(result['sections']), 1)
        section = result['sections'][0]
        self.assertEqual((section['start'], section['end'], section['duration_seconds']), (10, 25, 15))
        self.assertEqual(section['target_words'], ['猫'])
        self.assertEqual(section['opportunities_per_minute_proxy'], 4)

    def test_long_sections_bounds_membership(self):
        text = '\n'.join(f'[{i//60:02d}:{i%60:02d} - {(i+8)//60:02d}:{(i+8)%60:02d}] 猫。' for i in range(0, 420, 30))
        result = self.score(text)
        for section in result['sections']:
            self.assertGreater(section['end'], section['start'])
            self.assertLessEqual(section['end'], result['end'])
            self.assertEqual(section['duration_seconds'], 180)
            self.assertEqual(section['target_words'], ['猫'])
        recommended = result['recommended_sections']
        for left, right in zip(recommended, recommended[1:]):
            self.assertLessEqual(left['end'], right['start'])

    def test_artifact_unknown_not_candidate(self):
        result = self.score('[00:00 - 00:05] 実。')
        self.assertEqual(result['known_pct'], 0)
        self.assertEqual(result['top_candidates'], [])
        self.assertTrue(result['rows'][0]['artifact_or_filler'])

    def test_empty_input_error(self):
        for text in ('', '字幕なし', '[00:00 - 00:05] [音楽]', '[00:00 - 00:05] ...'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.score(text)

    def test_compound_exact_and_card_variants(self):
        inv = self.inventory('経済学\tけいざいがく\tKNOWN\n')
        result = self.score('[00:00 - 00:05] 経済学。', inv, ranks={'経済学': 500})
        self.assertEqual(result['known_pct'], 100)
        cards = v.load_cards(self.file('cards.tsv', '食べる\tたべる\n'))
        result = self.score('[00:00 - 00:05] 食べた。', ranks={'食べる': 500}, cards=cards)
        self.assertEqual(result['rows'][0]['card_presence'], 'present')

    def test_proper_name_not_kana_homophone_known(self):
        for spelling, known, reading in [('ハナ', '花', 'はな'), ('リカ', '理科', 'りか')]:
            result = self.score(f'[00:00 - 00:05] {spelling}。', self.inventory(f'{known}\t{reading}\tKNOWN\n'), ranks={spelling: 500})
            self.assertEqual(result['known_pct'], 0)
            self.assertEqual(result['uncertain_token_count'], 1)
            self.assertEqual(result['top_candidates'], [])

    def test_three_growing_rolling_captions(self):
        result = self.score('[00:00 - 00:08] 私はコーヒー\n[00:02 - 00:10] 私はコーヒーが\n[00:04 - 00:12] 私はコーヒーが好きです。')
        self.assertEqual(''.join(s['text'] for s in result['caption_segments']), '私はコーヒーが好きです。')
        self.assertEqual(result['token_count'], 6)

    def test_existing_card_new_lower_than_learning_without_card(self):
        inv = self.inventory('犬\tいぬ\tLEARNING\n')
        cards = v.load_cards(self.file('cards.tsv', '猫\tねこ\n'))
        result = self.score('[00:00 - 00:05] 猫。犬。', inv, cards=cards)
        self.assertEqual([r['word'] for r in result['top_candidates']], ['犬', '猫'])

    def test_real_comma_clause_separate_from_caption(self):
        result = self.score('[00:00 - 00:05] 私は猫が好きです、犬。')
        cat = next(r for r in result['rows'] if r['word'] == '猫')
        self.assertTrue(cat['ip1_clause_times'])
        self.assertFalse(cat['ip1_caption_times'])

    def test_repeated_overlap_phrase_preserved(self):
        segments, _ = v.parse_segments('[00:00 - 00:08] はいはい\n[00:04 - 00:12] はいはい')
        clean, removed = v.deduplicate_segments(segments)
        self.assertEqual(removed, 0)
        self.assertEqual(len(clean), 2)

    def test_state_overlap_error(self):
        path = self.file('state.json', json.dumps({'known_words': ['猫'], 'relearning_words': ['猫']}))
        with self.assertRaisesRegex(ValueError, 'overlap'):
            v.load_state(path)

    def test_functional_unknown_stays_in_coverage(self):
        result = self.score('[00:00 - 00:05] てる。', ranks={'てる': 500})
        self.assertEqual(result['known_pct'], 0)
        self.assertEqual(result['token_count'], 1)
        self.assertEqual(result['top_candidates'], [])
        self.assertTrue(result['rows'][0]['functional_fragment'])

    def test_dropped_caption_still_provides_dedup_provenance(self):
        result = self.score('[00:00 - 00:08] 私はコーヒー\n[00:04 - 00:12] 私はコーヒー\n[00:09 - 00:14] 私はコーヒーが好きです。')
        self.assertEqual(''.join(s['text'] for s in result['caption_segments']), '私はコーヒーが好きです。')
        self.assertEqual(next(r for r in result['rows'] if r['word'] == 'コーヒー')['count'], 1)

    def test_reviewer_rolling_chain(self):
        result = self.score('[00:00 - 00:08] 私はコーヒー\n[00:04 - 00:12] 私はコーヒーと犬\n[00:09 - 00:14] 私はコーヒーと犬が好きです。')
        self.assertEqual(next(r for r in result['rows'] if r['word'] == 'コーヒー')['count'], 1)
        self.assertEqual(next(r for r in result['rows'] if r['word'] == '犬')['count'], 1)

    def test_meaningful_short_word_retained(self):
        result = self.score('[00:00 - 00:05] 列。', ranks={'列': 500})
        self.assertEqual(result['known_pct'], 0)
        self.assertEqual(result['top_candidates'][0]['word'], '列')

    def test_main_explicit_paths(self):
        transcript = self.file('transcript.txt', '[00:00 - 00:05] 猫。')
        export = self.file('status.tsv', '私\tわたし\tKNOWN\n')
        ranks = self.file('rank.json', json.dumps({'猫': 500}))
        state = self.file('state.json', json.dumps({'known_words': [], 'relearning_words': []}))
        out = self.root / 'out.json'
        self.assertEqual(v.main([str(transcript), '--export', str(export), '--rank-file', str(ranks), '--state', str(state), '--json', str(out), '--top', '10']), 0)
        self.assertEqual(json.loads(out.read_text())['rows'][0]['word'], '猫')


if __name__ == '__main__':
    unittest.main()
