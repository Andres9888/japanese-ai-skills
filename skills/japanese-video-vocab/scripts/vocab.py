#!/usr/bin/env python3
"""Conservative vocabulary-status coverage, not a listening comprehension test.

Import-safe; all local file access occurs in explicit loaders/main. Caption timestamps
are segment-granular. Useful-word and section rankings are reviewable heuristics.
"""
import argparse
import collections
import csv
import json
import math
import re
import unicodedata
from pathlib import Path

STATUSES = {'KNOWN', 'IGNORED', 'LEARNING', 'TRACKED'}
KNOWN = {'KNOWN', 'IGNORED'}
FAMILIAR = KNOWN | {'LEARNING', 'TRACKED'}
KANA = re.compile(r'^[ぁ-ゖァ-ヺー]+$')
ARTIFACTS = {'実', '不', '痛', '何々', '鼻息', '咳払い', 'めっちゃ', 'まあまあ', 'そうそう', 'えー', 'ええ', 'あー', 'ああ', 'えっと', 'あの', 'まあ', 'うん'}
UNCLEAR_FRAGMENTS = {'たん', 'しょう'}  # context-dependent kana ASR/morphology fragments, not automatically known
DEFAULT_STATE = Path(__file__).resolve().parent.parent / 'references/user-state.json'


def norm(text):
    return unicodedata.normalize('NFKC', text or '').strip()


def hira(text):
    return ''.join(chr(ord(c) - 0x60) if 'ァ' <= c <= 'ヶ' else c for c in norm(text))


def band(rank):
    return '2k' if rank <= 2000 else '6k' if rank <= 6000 else '10k' if rank <= 10000 else 'rare'


def stars(rank):
    return 5 if rank <= 1500 else 4 if rank <= 5000 else 3 if rank <= 15000 else 2 if rank <= 30000 else 1


def read_tsv(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return [(i, [norm(x) for x in row]) for i, row in enumerate(csv.reader(f, delimiter='\t'), 1) if any(norm(x) for x in row)]


class Inventory:
    def __init__(self, entries, source=None):
        self.entries = entries
        self.source = str(source) if source else None
        self.exact = collections.defaultdict(list)
        self.readings = collections.defaultdict(list)
        for entry in entries:
            self.exact[entry['word']].append(entry)
            if entry['reading']:
                self.readings[hira(entry['reading'])].append(entry)

    def match(self, variants, reading, allow_kana=True):
        # Prefer spelling/lemma/orthBase. Never use a kanji token's reading to
        # promote a different homophone's status (橋 != 箸).
        for variant in dict.fromkeys(norm(x) for x in variants if x):
            entries = self.exact.get(variant, [])
            if entries:
                aligned = [e for e in entries if not reading or not e['reading'] or hira(e['reading']) == hira(reading)]
                if not aligned:
                    # One explicit spelling entry can have a legitimate alternate
                    # reading (私: わたし / わたくし). This is not homophone lookup.
                    if len(entries) == 1:
                        return entries[0], 'exact_spelling_reading_variant_assumption'
                    continue
                return max(aligned, key=lambda e: e.get('status') in KNOWN), 'spelling_or_lemma'
        surface = norm(variants[0]) if variants else ''
        if allow_kana and surface and KANA.fullmatch(surface):
            entries = self.readings.get(hira(reading or surface), [])
            if len({e['word'] for e in entries}) == 1 and entries:
                return max(entries, key=lambda e: e.get('status') in KNOWN), 'unambiguous_kana_reading_assumption'
        return None, None


def load_export(path):
    rows = read_tsv(path)
    if not rows:
        raise ValueError(f'{path}: empty vocabulary export')
    header = [x.lower().replace(' ', '_') for x in rows[0][1]]
    headed = 'word' in header
    if headed:
        if not {'word', 'reading', 'status'}.issubset(header):
            raise ValueError(f'{path}: expected word/reading/status; sweep jpdb_rank/know_it? schema is not a status export')
        indexes = [header.index(x) for x in ('word', 'reading', 'status')]
        rows = rows[1:]
    else:
        indexes = [0, 1, 2]
    entries = []
    for line, row in rows:
        if (not headed and len(row) != 3) or max(indexes) >= len(row):
            raise ValueError(f'{path}:{line}: expected word/reading/status columns')
        word, reading, status = [row[i] for i in indexes]
        status = status.upper()
        if not word and not reading and status in STATUSES:
            # Some real Migaku exports contain an empty KNOWN record. It must
            # never enter indexes or match any token. An all-empty export fails.
            continue
        if not word or status not in STATUSES:
            raise ValueError(f'{path}:{line}: nonempty word and status in {sorted(STATUSES)} required')
        entries.append({'word': word, 'reading': reading, 'status': status})
    if not entries:
        raise ValueError(f'{path}: no vocabulary entries')
    return Inventory(entries, path)


def load_cards(path):
    if path is None:
        return None
    rows = read_tsv(path)
    if not rows:
        raise ValueError(f'{path}: empty card inventory')
    header = [x.lower() for x in rows[0][1]]
    headed = 'word' in header
    if headed and not {'word', 'reading'}.issubset(header):
        raise ValueError(f'{path}: expected word/reading card columns')
    indexes = [header.index(x) for x in ('word', 'reading')] if headed else [0, 1]
    entries = []
    for line, row in rows[1:] if headed else rows:
        if (not headed and len(row) != 2) or max(indexes) >= len(row) or not row[indexes[0]]:
            raise ValueError(f'{path}:{line}: invalid word/reading card row')
        entries.append({'word': row[indexes[0]], 'reading': row[indexes[1]]})
    return Inventory(entries, path)


def load_state(path=DEFAULT_STATE):
    if path is None or not Path(path).exists():
        return {'known_words': [], 'relearning_words': []}
    with open(path, encoding='utf-8') as f:
        state = json.load(f)
    if not isinstance(state, dict):
        raise ValueError('state must be a JSON object')
    for key in ('known_words', 'relearning_words'):
        values = state.get(key, [])
        if not isinstance(values, list) or any(not isinstance(x, str) or not norm(x) for x in values):
            raise ValueError(f'state {key} must contain nonempty strings')
        state[key] = [norm(x) for x in values]
    if set(state['known_words']) & set(state['relearning_words']):
        raise ValueError('state known_words and relearning_words must not overlap')
    return state


def load_ranks(path):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, dict):
        return {norm(w): int(r) for w, r in data.items() if int(r) > 0}
    ranks = {}
    for entry in data:
        word, _, d = entry
        frequency = d.get('frequency') or {}
        if isinstance(frequency, (int, float)):
            frequency = {'value': frequency}
        kana_rank = '㋕' in str(d.get('displayValue', '')) + str(frequency.get('displayValue', ''))
        if kana_rank and not KANA.fullmatch(word):
            continue
        rank = d.get('value') or frequency.get('value')
        if rank is not None and int(rank) > 0:
            ranks[norm(word)] = min(ranks.get(norm(word), math.inf), int(rank))
    return ranks


def timestamp(text):
    parts = text.split(':')
    if len(parts) not in (2, 3):
        raise ValueError('invalid timestamp')
    vals = [float(x) for x in parts]
    if any(x < 0 for x in vals) or any(x >= 60 for x in vals[1:]):
        raise ValueError('invalid timestamp')
    return sum(v * 60 ** i for i, v in enumerate(reversed(vals)))


def parse_segments(text):
    segments, invalid = [], 0
    pattern = re.compile(r'^\[([\d:.]+)\s*-\s*([\d:.]+)\]\s*(.*)$')
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        match = pattern.match(line.strip())
        if not match:
            invalid += 1
            continue
        start, end = timestamp(match[1]), timestamp(match[2])
        if end <= start:
            raise ValueError(f'transcript line {line_no}: end must exceed start')
        caption = re.sub(r'\[[^\]]*\]', '', match[3]).strip()
        if caption:
            if segments and start < segments[-1]['start']:
                raise ValueError('caption start times must be nondecreasing')
            segments.append({'start': start, 'end': end, 'text': caption, 'source_line': line_no, 'original_text': caption})
    if not segments:
        raise ValueError('no nonempty timestamped captions')
    return segments, invalid


def deduplicate_segments(segments):
    retained, removed, source_history = [], 0, []
    for source in segments:
        segment = dict(source)
        compact = re.sub(r'\s+', '', segment['text'])
        overlap = 0
        # Only compare genuinely overlapping source intervals. The longest suffix
        # prefix requires >=4 characters and lexical content, avoiding はい/そう
        # repetitions. Nonoverlapping repetitions are never deduplicated.
        previous = [s for s in source_history if s['start'] < segment['end'] and s['end'] > segment['start']]
        for prev in previous:
            old = re.sub(r'\s+', '', prev['original_text'])
            for size in range(min(len(old), len(compact)), 3, -1):
                prefix = compact[:size]
                if (old.endswith(prefix) and len(re.sub(r'[^\wぁ-ヺ一-龯]', '', prefix)) >= 4
                        and not re.fullmatch(r'(.{1,4})\1+', prefix)):
                    overlap = max(overlap, size)
                    break
        if overlap:
            chars, cut = 0, 0
            for cut, char in enumerate(segment['text'], 1):
                chars += not char.isspace()
                if chars == overlap:
                    break
            segment['text'] = segment['text'][cut:].lstrip()
            segment['dedup_removed_prefix'] = source['text'][:cut]
            removed += overlap
        if segment['text']:
            retained.append(segment)
        source_history.append(source)
    if not retained:
        raise ValueError('no captions after cleanup')
    return retained, removed


def build_units(segments):
    # Carry text only across nearby captions, bounded to 30 seconds / 180 chars.
    # A discarded fragment boundary remains untrusted until real punctuation.
    units, buffer, spans = [], '', []
    trusted_start = True
    def flush(complete=False):
        nonlocal buffer, spans, trusted_start
        if buffer.strip():
            units.append({'text': buffer, 'spans': spans, 'complete': complete and trusted_start})
        buffer, spans = '', []
        trusted_start = complete
    for segment in segments:
        if buffer and (segment['start'] - spans[-1][2]['end'] > 2 or segment['end'] - spans[0][2]['start'] > 30 or len(buffer) + len(segment['text']) > 180):
            flush()
        for piece in re.findall(r'[^。？！?!]+[。？！?!]*|[。？！?!]+', segment['text']):
            offset = len(buffer)
            buffer += piece
            spans.append((offset, len(buffer), segment))
            if re.search(r'[。？！?!]$', piece):
                flush(complete=True)
    flush()
    return units


def tokenize_unit(unit, tagger, compound_words):
    text, raw, pos = unit['text'], [], 0
    for node in tagger(text):
        start = text.find(node.surface, pos)
        if start < 0:
            start = pos
        pos = start + len(node.surface)
        ft = node.feature
        feature = lambda key: getattr(ft, key, '') or ''
        raw.append({'surface': node.surface, 'word': norm(feature('orthBase') or feature('lemma').split('-')[0] or node.surface),
                    'lemma': norm(feature('lemma').split('-')[0]), 'reading': hira(feature('kanaBase') or feature('pron') or node.surface),
                    'pos1': feature('pos1'), 'pos2': feature('pos2'), 'offset': start, 'stop': pos})
    merged, i = [], 0
    while i < len(raw):
        chosen = None
        for j in range(min(i + 6, len(raw)), i + 1, -1):
            chunk = raw[i:j]
            spellings = (''.join(t['surface'] for t in chunk), ''.join(t['word'] for t in chunk))
            word = next((w for w in spellings if w in compound_words), None)
            if word and all(t['pos1'] not in {'補助記号', '記号', '空白'} for t in chunk):
                chosen = {**raw[i], 'surface': ''.join(t['surface'] for t in chunk), 'word': word, 'lemma': word,
                          'reading': ''.join(t['reading'] for t in chunk), 'stop': chunk[-1]['stop'],
                          'pos2': '固有名詞' if any(t['pos2'] == '固有名詞' for t in chunk) else raw[i]['pos2']}
                i = j
                break
        if chosen is None:
            chosen = raw[i]
            i += 1
        if chosen['pos1'] in {'補助記号', '記号', '空白'} or chosen['pos2'] == '数詞' or re.fullmatch(r'[\W\dA-Za-z_]+', chosen['surface']):
            continue
        sources = [s for a, b, s in unit['spans'] if a < chosen['stop'] and b > chosen['offset']]
        chosen.update(start=sources[0]['start'], end=max(s['end'] for s in sources), source_lines=[s['source_line'] for s in sources], unit_text=text)
        merged.append(chosen)
    return merged


def pct(num, denominator):
    return round(100 * num / denominator, 1) if denominator else None


def candidate_sort(row):
    # Frequency first in broad bands, then comparable opportunities prefer explicit
    # retries / export-New, with ordinary existing-card learning lower. No ROI score.
    priority = 0 if row['relearning'] else 1
    export_priority = 0 if row['status'] == 'NEW' else 1
    card_penalty = 1 if row['card_presence'] == 'present' and not row['relearning'] else 0
    return (['2k', '6k', '10k', 'rare'].index(row['band']), priority, card_penalty, export_priority,
            not bool(row['ip1_times']), not bool(row['ip1_clause_times']), not bool(row['ip1_caption_times']), -min(row['count'], 5), row['rank'], row['word'])


def make_sections(tokens, candidates, start, end, window_minutes):
    window = window_minutes * 60
    starts = [start] if end - start <= window else [start + 60 * i for i in range(int((end - start - window) // 60) + 1)]
    if end - start > window:
        if not starts or starts[-1] + window < end:
            starts.append(end - window)
    sections = []
    ordering = {r['word']: i for i, r in enumerate(candidates)}
    by_word = {r['word']: r for r in candidates}
    for left in sorted(set(starts)):
        right = min(end, left + window)
        # Assign each token by its caption start, not an invented word timestamp.
        selected = [t for t in tokens if left <= t['start'] < right]
        if not selected:
            continue
        words = sorted({t['word'] for t in selected if t['word'] in ordering}, key=ordering.get)
        sections.append({'start': left, 'end': right, 'duration_seconds': right - left, 'token_count': len(selected),
                         'known_pct': pct(sum(t['status'] in KNOWN for t in selected), len(selected)),
                         'familiar_pct': pct(sum(t['status'] in FAMILIAR for t in selected), len(selected)),
                         'unique_candidate_opportunities': len(words), 'opportunities_per_minute_proxy': round(len(words) * 60 / (right - left), 2),
                         'target_words': words, 'top_target_words': words[:3], 'recommended': False,
                         'opportunity_evidence': {
                             'new_in_export_words': [w for w in words if by_word[w]['export_status'] == 'NEW'],
                             'new_in_export_count': sum(by_word[w]['export_status'] == 'NEW' for w in words),
                             'present_card_reinforcement_words': [w for w in words if by_word[w]['card_presence'] == 'present' and not by_word[w]['relearning']],
                             'present_card_reinforcement_count': sum(by_word[w]['card_presence'] == 'present' and not by_word[w]['relearning'] for w in words),
                             'explicit_relearning_words': [w for w in words if by_word[w]['relearning']],
                             'explicit_relearning_count': sum(by_word[w]['relearning'] for w in words),
                             'card_absence_globally_verified': False}})
    def section_sort(s):
        comfort = 0 if s['known_pct'] >= 95 else 1 if s['known_pct'] >= 92 else 2
        return (comfort, -s['familiar_pct'], -s['unique_candidate_opportunities'], s['start'])
    chosen = []
    for section in sorted(sections, key=section_sort):
        if section['target_words'] and all(section['end'] <= c['start'] or section['start'] >= c['end'] for c in chosen):
            section['recommended'] = True
            chosen.append(section)
            if len(chosen) == 3:
                break
    return sections, sorted(chosen, key=lambda s: s['start'])


def analyze(transcript, inventory, ranks, cards=None, state=None, max_rank=10000, top=3, section_minutes=3, tagger=None):
    if not 1 <= top <= 10 or section_minutes <= 0:
        raise ValueError('top must be 1..10 and section-minutes positive')
    if tagger is None:
        import fugashi
        tagger = fugashi.Tagger()
    state = state or {'known_words': [], 'relearning_words': []}
    user_known, retries = set(state.get('known_words', [])), set(state.get('relearning_words', []))
    if user_known & retries:
        raise ValueError('state known_words and relearning_words must not overlap')
    originals, invalid = parse_segments(transcript)
    segments, removed = deduplicate_segments(originals)
    units = build_units(segments)
    compounds = set(inventory.exact) | user_known | retries | (set(cards.exact) if cards else set())
    tokens, sentence_hits, proxy_hits = [], collections.defaultdict(list), collections.defaultdict(list)
    caption_hits = collections.defaultdict(list)
    fallback_count = 0
    for unit in units:
        unit_tokens = tokenize_unit(unit, tagger, compounds)
        for token in unit_tokens:
            # Canonical spelling before an inflected surface avoids treating なり
            # (a form of なる) as the separately exported particle なり.
            variants = [token['word'], token['lemma'], token['surface']]
            match, method = inventory.match(variants, token['reading'], allow_kana=token['pos2'] != '固有名詞')
            override = next((v for v in variants if v in user_known), None)
            token['export_status'] = match['status'] if match else 'NEW'
            token['status'] = 'KNOWN' if override else token['export_status']
            token['match_method'] = 'explicit_user_known' if override else method
            token['word'] = override or (match['word'] if match else token['word'])
            token['reading'] = hira(match['reading']) if match and match['reading'] else token['reading']
            token['relearning'] = bool(set(variants + [token['word']]) & retries)
            if token['relearning']:
                token['status'] = 'LEARNING'
            unknown_name = token['pos2'] == '固有名詞' and token['status'] not in FAMILIAR
            unclear_fragment = token['word'] in UNCLEAR_FRAGMENTS and token['status'] not in KNOWN and not token['relearning']
            token['uncertain'] = unknown_name or unclear_fragment
            token['uncertainty_reason'] = 'unknown_proper_name' if unknown_name else 'ambiguous_kana_fragment_heuristic' if unclear_fragment else None
            if method == 'unambiguous_kana_reading_assumption' and not override:
                fallback_count += 1
            tokens.append(token)
        def hit(group, text, destination, label):
            unknown = {t['word'] for t in group if t['status'] not in KNOWN or t['relearning']}
            if len(unknown) == 1 and not any(t['uncertain'] for t in group):
                word = next(iter(unknown))
                target = next(t for t in group if t['word'] == word)
                destination[word].append({'t': target['start'], 'end': max(t['end'] for t in group), 'sentence': text.strip(), 'boundary_basis': label, 'source_lines': sorted({i for t in group for i in t['source_lines']})})
        if unit['complete'] and unit_tokens:
            hit(unit_tokens, unit['text'], sentence_hits, 'observed_terminal_punctuation_bounded_unit_requires_review')
        # Proxy groups stay inside each actual caption and comma-delimited fragment.
        for a, b, source in unit['spans']:
            for fragment in re.finditer(r'[^。？！?!、，,]+', unit['text'][a:b]):
                left, right = a + fragment.start(), a + fragment.end()
                group = [t for t in unit_tokens if left <= t['offset'] < right]
                if group and len(fragment.group().strip()) >= 6:
                    is_clause = bool(re.search(r'[、，,]', unit['text'][a:b]))
                    hit(group, fragment.group(), proxy_hits if is_clause else caption_hits,
                        'comma_delimited_clause_proxy_not_sentence' if is_clause else 'caption_fragment_proxy_not_sentence')
    if not tokens:
        raise ValueError('no Japanese lexical tokens after cleanup')
    grouped = collections.defaultdict(list)
    for token in tokens:
        if token['status'] not in KNOWN or token['relearning']:
            grouped[token['word']].append(token)
    rows = []
    for word, group in grouped.items():
        first = group[0]
        rank = min([ranks.get(v, 10**9) for t in group for v in (t['surface'], t['word'], t['lemma'])])
        if rank > max_rank:
            continue
        card, card_method = cards.match([word, first['surface'], first['lemma']], first['reading']) if cards else (None, None)
        sh, ph, ch = sentence_hits[word], proxy_hits[word], caption_hits[word]
        sentence_times = sorted({h['t'] for h in sh})
        ph = [h for h in ph if h['t'] not in sentence_times]
        ch = [h for h in ch if h['t'] not in sentence_times]
        uncertain = any(t['uncertain'] for t in group)
        artifact = word in ARTIFACTS or any(t['surface'] in ARTIFACTS for t in group)
        # Coverage still includes all these unknown tokens. Mining favors lexical
        # content over function-word/inflection fragments, unless explicitly retried.
        functional = all(t['pos1'] in {'助詞', '助動詞', '接尾辞', '接頭辞', '代名詞', '感動詞'} for t in group)
        intentional = any(t['relearning'] for t in group)
        row = {'rank': rank, 'word': word, 'reading': first['reading'], 'band': band(rank), 'stars': stars(rank),
               'status': first['status'], 'export_status': first['export_status'], 'count': len(group),
               'times': sorted({t['start'] for t in group}), 'ip1_times': sentence_times,
               'ip1_clause_times': sorted({h['t'] for h in ph}), 'ip1_hits': sh,
               'ip1_clause_hits': [{**h, 'clause': h['sentence']} for h in ph],
               'ip1_caption_times': sorted({h['t'] for h in ch}), 'ip1_caption_hits': ch,
               'example': (sh or ph or ch or [{'sentence': first['unit_text']}])[0]['sentence'][:120], 'example_is_ip1': bool(sh),
               'example_boundary': 'punctuation_sentence_candidate' if sh else 'comma_clause_proxy' if ph else 'caption_fragment_proxy' if ch else 'fragment',
               'relearning': any(t['relearning'] for t in group), 'uncertain': uncertain, 'artifact_or_filler': artifact,
               'functional_fragment': functional,
               'eligible_candidate': not uncertain and not artifact and (not functional or intentional),
               'shortlist_exclusion_reason': next((t['uncertainty_reason'] for t in group if t['uncertain']), None) if uncertain else 'artifact_or_filler' if artifact else 'function_word_or_inflection_heuristic' if functional and not intentional else None,
               'card_presence': 'present' if card else 'not_found_in_supplied_inventory' if cards is not None else 'unverified',
               'card_evidence': {'source': cards.source if cards is not None else None, 'matched_word': card['word'] if card else None, 'match_method': card_method, 'inventory_completeness_assumed': False},
               'match_methods': sorted({t['match_method'] for t in group if t['match_method']})}
        row['reason'] = ('explicit user relearning; ' if row['relearning'] else 'new in inspected status export, not proven card-free; ' if row['status'] == 'NEW' else 'existing vocabulary status; ') + f"{row['band']} frequency band; {row['count']} retained occurrence(s); " + ('punctuation-bounded i+1 candidate requires review' if sh else 'comma clause i+1 proxy only' if ph else 'caption fragment i+1 proxy only' if ch else 'no one-unknown example')
        rows.append(row)
    rows.sort(key=lambda r: (r['rank'], r['word']))
    candidates = sorted((r for r in rows if r['eligible_candidate']), key=candidate_sort)
    start, end = min(s['start'] for s in originals), max(s['end'] for s in originals)
    sections, recommended = make_sections(tokens, candidates, start, end, section_minutes)
    uncertain_group = collections.Counter(t['word'] for t in tokens if t['uncertain'])
    status_counts = collections.Counter(t['status'] for t in tokens)
    return {'known_pct': pct(sum(t['status'] in KNOWN for t in tokens), len(tokens)),
            'familiar_pct': pct(sum(t['status'] in FAMILIAR for t in tokens), len(tokens)),
            'coverage_basis': 'retained lexical-token counts; explicit KNOWN/IGNORED or user known overrides, including annotated exact-spelling alternate-reading and unambiguous kana fallback assumptions; not verified listening comprehension',
            'token_count': len(tokens), 'known_token_count': sum(t['status'] in KNOWN for t in tokens),
            'familiar_token_count': sum(t['status'] in FAMILIAR for t in tokens), 'status_token_counts': dict(status_counts),
            'uncertain_token_count': sum(uncertain_group.values()), 'uncertain_tokens': [{'word': w, 'count': c, 'reasons': sorted({t['uncertainty_reason'] for t in tokens if t['word'] == w and t['uncertain']})} for w, c in uncertain_group.most_common()],
            'rows': rows, 'top_candidates': candidates[:top], 'sections': sections, 'recommended_sections': recommended,
            'duration_seconds': end - start, 'start': start, 'end': end,
            'shortlist_basis': 'useful-word heuristic: frequency bands, explicit retries/export-New, card evidence, examples and repetition; agent must judge context and practical utility',
            'section_basis': 'comfort-first heuristic; distinct eligible candidate types/minute is a proxy, not causal learning ROI; membership uses caption start timestamps',
            'diagnostics': {'export': inventory.source, 'export_entries': len(inventory.entries), 'original_caption_count': len(originals),
                            'retained_caption_count': len(segments), 'dedup_removed_characters': removed, 'unparsed_lines': invalid,
                            'sentence_candidate_units': sum(u['complete'] for u in units), 'fragment_units': sum(not u['complete'] for u in units),
                            'kana_fallback_token_count': fallback_count, 'ranked_candidate_count': len(candidates),
                            'unknown_grammar_fragment_token_count': sum(t['status'] not in KNOWN and t['pos1'] in {'助詞', '助動詞', '接尾辞', '接頭辞', '感動詞'} for t in tokens),
                            'unranked_or_over_limit_unknown_types': sum(min(ranks.get(t['word'], 10**9) for t in group) > max_rank for group in grouped.values()),
                            'boundary_warnings': ['Caption punctuation is evidence, not a semantic sentence guarantee; review every example.', 'Unpunctuated/gapped/long streams are fragments, never asserted sentence i+1.', 'Times retain caption provenance, not word-accurate alignment.', 'Overlap deduplication is a suffix-prefix heuristic; ambiguous repeated short phrases are retained.', 'Unambiguous kana-reading fallback and same-spelling alternate readings are annotated assumptions.', 'NEW means absent from inspected status export; supplied cards are not a complete deck inventory.']},
            'caption_segments': segments}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('transcript')
    parser.add_argument('--export', help='Migaku word/reading/status TSV (latest dated export by default)')
    parser.add_argument('--rank-file', help='JPDB term metadata JSON or test word-to-rank JSON')
    parser.add_argument('--cards', help='Optional word/reading TSV, not assumed complete')
    parser.add_argument('--state', default=str(DEFAULT_STATE))
    parser.add_argument('--max-rank', type=int, default=10000)
    parser.add_argument('--top', type=int, default=3)
    parser.add_argument('--section-minutes', type=float, default=3)
    parser.add_argument('--json')
    args = parser.parse_args(argv)
    try:
        root = Path.home() / 'Library/Mobile Documents/com~apple~CloudDocs'
        export = args.export
        if not export:
            exports = sorted((root / 'Japanese').glob('migaku_words_????-??-??.tsv'))
            if not exports:
                raise ValueError('no dated Migaku export found; supply --export')
            export = exports[-1]
        ranks = load_ranks(args.rank_file or root / '[Freq] JPDB (Recommended)/term_meta_bank_1.json')
        result = analyze(Path(args.transcript).read_text(encoding='utf-8-sig'), load_export(export), ranks,
                         cards=load_cards(args.cards), state=load_state(args.state), max_rank=args.max_rank,
                         top=args.top, section_minutes=args.section_minutes)
        print(f"export {Path(export).name} | known {result['known_pct']}% | familiar {result['familiar_pct']}% | tokens {result['token_count']} | uncertain {result['uncertain_token_count']} | candidates {result['diagnostics']['ranked_candidate_count']}")
        print('Vocabulary-status proxy only, not listening accuracy. Shortlist and punctuation boundaries require review.')
        for row in result['top_candidates']:
            print(f"{row['rank']}\t{row['word']}【{row['reading']}】\t{row['band']}\t{row['status']}\tx{row['count']}\t{row['card_presence']}\t{row['reason']}")
        for section in result['recommended_sections']:
            print(f"section {section['start']:g}-{section['end']:g}s | known {section['known_pct']}% | targets {', '.join(section['top_target_words'])} | {section['opportunities_per_minute_proxy']} types/min proxy")
        if args.json:
            Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
