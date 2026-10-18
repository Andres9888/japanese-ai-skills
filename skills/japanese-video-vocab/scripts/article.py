#!/usr/bin/env python3
"""Score clean Japanese article-body text with vocab.py's tested status logic.

The adapter uses private, non-overlapping paragraph positions only to reuse the
existing tokenizer/status scorer. Published data never exposes those positions
as media timing and never estimates reading time.
"""
import argparse
import importlib.util
import json
import re
from pathlib import Path

try:  # Normal invocation: python scripts/article.py ...
    import vocab
except ModuleNotFoundError:  # Import-safe support for file-based test imports.
    _spec = importlib.util.spec_from_file_location('vocab', Path(__file__).with_name('vocab.py'))
    vocab = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(vocab)

DEFAULT_STATE = vocab.DEFAULT_STATE
JAPANESE_CHARACTERS = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]')
PUNCTUATED_SENTENCE = re.compile(r'[^。？！?!]+[。？！?!]')


def split_paragraphs(text):
    """Keep blank-line paragraph boundaries without inventing punctuation."""
    normalized = text.replace('\r\n', '\n').replace('\r', '\n').strip()
    if not normalized:
        raise ValueError('article body is empty')
    paragraphs = [block.strip() for block in re.split(r'\n\s*\n+', normalized) if block.strip()]
    if not paragraphs:
        raise ValueError('article body is empty')
    return paragraphs


def _clock(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f'{hours:02d}:{minutes:02d}:{secs:02d}'


def _internal_transcript(paragraphs):
    """Give each paragraph a private position with a >2-unit gap.

    vocab.build_units flushes on that gap, so an incomplete paragraph cannot be
    completed by the next paragraph. The positions are implementation-only.
    """
    lines, positions = [], {}
    for index, paragraph in enumerate(paragraphs, 1):
        position = (index - 1) * 10
        positions[position] = index
        scoring_text = re.sub(r'\s+', ' ', paragraph).strip()
        lines.append(f'[{_clock(position)} - {_clock(position + 1)}] {scoring_text}')
    return '\n'.join(lines), positions


def _sentence_numbers(paragraphs):
    # A sentence reference exists only when punctuation appears in the original
    # paragraph. Incomplete text deliberately has no sentence reference.
    numbers = {}
    for paragraph_number, paragraph in enumerate(paragraphs, 1):
        for ordinal, match in enumerate(PUNCTUATED_SENTENCE.finditer(re.sub(r'\s+', ' ', paragraph)), 1):
            text = match.group().strip()
            numbers.setdefault((paragraph_number, text), []).append(ordinal)
    return numbers


def _paragraph_for_position(position, positions):
    return positions.get(position)


def _reference(paragraph_number, sentence_number=None):
    ref = {'paragraph': paragraph_number, 'internal_paragraph_position': paragraph_number}
    if sentence_number is not None:
        ref['sentence'] = sentence_number
    return ref


def _example_entries(row, positions, sentence_numbers):
    entries, seen = [], set()

    def add(hit, basis):
        paragraph_number = _paragraph_for_position(hit['t'], positions)
        if paragraph_number is None:
            return
        text = hit.get('sentence', hit.get('clause', '')).strip()
        sentence_options = sentence_numbers.get((paragraph_number, text), [])
        sentence_number = sentence_options[0] if basis == 'punctuation_bounded_sentence' and sentence_options else None
        key = (paragraph_number, text, basis, sentence_number)
        if not text or key in seen:
            return
        seen.add(key)
        entries.append({'text': text, 'basis': basis,
                        'reference': _reference(paragraph_number, sentence_number)})

    for hit in row['ip1_hits']:
        add(hit, 'punctuation_bounded_sentence')
    for hit in row['ip1_clause_hits']:
        add(hit, 'clause_proxy_not_complete_sentence')
    for hit in row['ip1_caption_hits']:
        # This is article text: retain the weaker evidence without calling it a
        # caption or a sentence.
        add(hit, 'paragraph_fragment_proxy_not_complete_sentence')
    return entries


def _card_evidence(row):
    presence = row['card_presence']
    labels = {
        'present': 'present in supplied cards',
        'not_found_in_supplied_inventory': 'not found in supplied cards',
        'unverified': 'card presence unverified',
    }
    evidence = row['card_evidence']
    return {
        'label': labels[presence],
        'source': evidence['source'],
        'matched_word': evidence['matched_word'],
        'match_method': evidence['match_method'],
        'inventory_completeness_assumed': False,
    }


def _clean_row(row, positions, sentence_numbers):
    paragraph_numbers = sorted({_paragraph_for_position(position, positions) for position in row['times']})
    paragraph_numbers = [number for number in paragraph_numbers if number is not None]
    examples = _example_entries(row, positions, sentence_numbers)
    return {
        'word': row['word'],
        'reading': row['reading'],
        'count': row['count'],
        'status': row['status'],
        'export_status': row['export_status'],
        'relearning': row['relearning'],
        'rank': row['rank'],
        'band': row['band'],
        'stars': row['stars'],
        'paragraph_references': [_reference(number) for number in paragraph_numbers],
        'examples': examples,
        'one_unknown_sentence_example_count': sum(example['basis'] == 'punctuation_bounded_sentence' for example in examples),
        'uncertain': row['uncertain'],
        'artifact_or_filler': row['artifact_or_filler'],
        'functional_fragment': row['functional_fragment'],
        'eligible_candidate': row['eligible_candidate'],
        'shortlist_exclusion_reason': row['shortlist_exclusion_reason'],
        'card_evidence': _card_evidence(row),
        'match_methods': row['match_methods'],
    }


def analyze_article(article_text, inventory, ranks, cards=None, state=None, max_rank=10000, top=3, tagger=None):
    """Return article-only coverage and mining data, with no media metadata."""
    paragraphs = split_paragraphs(article_text)
    internal, positions = _internal_transcript(paragraphs)
    scored = vocab.analyze(internal, inventory, ranks, cards=cards, state=state,
                           max_rank=max_rank, top=top, tagger=tagger)
    sentence_numbers = _sentence_numbers(paragraphs)
    rows = [_clean_row(row, positions, sentence_numbers) for row in scored['rows']]
    rows_by_word = {row['word']: row for row in rows}
    top_candidates = [rows_by_word[row['word']] for row in scored['top_candidates'] if row['word'] in rows_by_word]
    return {
        'article_japanese_character_count': sum(1 for character in article_text if JAPANESE_CHARACTERS.fullmatch(character)),
        'paragraph_count': len(paragraphs),
        'paragraph_coordinate_basis': 'Paragraph references are 1-based internal paragraph positions used only to preserve article boundaries during scoring.',
        'coverage': {
            'known_pct': scored['known_pct'],
            'familiar_pct': scored['familiar_pct'],
            'token_count': scored['token_count'],
            'known_token_count': scored['known_token_count'],
            'familiar_token_count': scored['familiar_token_count'],
            'basis': scored['coverage_basis'] + '; LEARNING/TRACKED also count as familiar. Article reading comprehension is not measured.',
            'status_counts': scored['status_token_counts'],
        },
        'uncertainty': {
            'token_count': scored['uncertain_token_count'],
            'tokens': scored['uncertain_tokens'],
            'basis': 'Unknown proper names and ambiguous kana fragments remain uncertain rather than assumed known.',
        },
        'rows': rows,
        'top_candidates': top_candidates,
        'paragraphs': [
            {'paragraph': number, 'internal_paragraph_position': number, 'text': paragraph,
             'japanese_character_count': sum(1 for character in paragraph if JAPANESE_CHARACTERS.fullmatch(character))}
            for number, paragraph in enumerate(paragraphs, 1)
        ],
        'shortlist_basis': 'Candidate preference follows the vocab scorer: useful rank bands, explicit relearning or export-New status, card evidence, clean one-unknown examples, and repetition. Review practical meaning and context before mining.',
        'warnings': [
            'Reading time was not measured; no reading-time estimate is included.',
            'Vocabulary-status scoring is not a measure of article comprehension.',
            'Only punctuation-bounded examples are sentence candidates. Clause and paragraph-fragment proxies are labeled separately.',
            'Repeated article text is retained; it is not deduplicated.',
        ],
        'diagnostics': {
            'export': scored['diagnostics']['export'],
            'export_entries': scored['diagnostics']['export_entries'],
            'ranked_candidate_count': scored['diagnostics']['ranked_candidate_count'],
            'kana_fallback_token_count': scored['diagnostics']['kana_fallback_token_count'],
            'unknown_grammar_fragment_token_count': scored['diagnostics']['unknown_grammar_fragment_token_count'],
        },
    }


def _default_export_and_ranks(args):
    root = Path.home() / 'Library/Mobile Documents/com~apple~CloudDocs'
    export = args.export
    if not export:
        exports = sorted((root / 'Japanese').glob('migaku_words_????-??-??.tsv'))
        if not exports:
            raise ValueError('no dated Migaku export found; supply --export')
        export = exports[-1]
    return export, args.rank_file or root / '[Freq] JPDB (Recommended)/term_meta_bank_1.json'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('article', help='UTF-8 clean Japanese article-body text')
    parser.add_argument('--export', help='Migaku word/reading/status TSV (latest dated export by default)')
    parser.add_argument('--rank-file', help='JPDB term metadata JSON or test word-to-rank JSON')
    parser.add_argument('--cards', help='Optional word/reading TSV, not assumed complete')
    parser.add_argument('--state', default=str(DEFAULT_STATE), help='Explicit known/relearning JSON; defaults to references/user-state.json')
    parser.add_argument('--max-rank', type=int, default=10000)
    parser.add_argument('--top', type=int, default=3)
    parser.add_argument('--json', required=True, help='Output JSON path')
    args = parser.parse_args(argv)
    try:
        export, rank_file = _default_export_and_ranks(args)
        result = analyze_article(Path(args.article).read_text(encoding='utf-8-sig'), vocab.load_export(export),
                                 vocab.load_ranks(rank_file), cards=vocab.load_cards(args.cards),
                                 state=vocab.load_state(args.state), max_rank=args.max_rank, top=args.top)
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        coverage = result['coverage']
        print(f"article characters {result['article_japanese_character_count']} | paragraphs {result['paragraph_count']} | known {coverage['known_pct']}% | familiar {coverage['familiar_pct']}% | tokens {coverage['token_count']} | uncertain {result['uncertainty']['token_count']} | candidates {result['diagnostics']['ranked_candidate_count']}")
        print('Vocabulary-status scoring only, not article comprehension. Reading time was not measured.')
        for row in result['top_candidates']:
            refs = ','.join(f"P{ref['paragraph']}" for ref in row['paragraph_references'])
            print(f"{row['rank']}\t{row['word']}【{row['reading']}】\t{row['band']}\t{row['status']}\tx{row['count']}\t{refs}\t{row['card_evidence']['label']}")
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
