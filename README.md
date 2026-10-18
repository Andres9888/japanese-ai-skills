# japanese-ai-skills

AI agent skill I use to learn Japanese with Migaku. Written as a `SKILL.md` for Claude-style agents (Claude Code, Aside, or anything that reads skill folders).

Goal: eventually 10k known words, with the most common 2k and 6k words down first, using AI as much as possible.

I'm already using this to learn, and I'm still modifying and improving it, so expect changes.

## Skill

### `japanese-video-vocab`
Scores a Japanese YouTube video (or article) against your Migaku known words and picks what to learn next.

- Known vs familiar coverage for the video, so you can pick content where you already know ~95-98%
- Ranks the words you don't know by frequency (JPDB), most common first, grouped into Core 2k / 6k / 10k bands
- Finds i+1 sentences (only one unknown word) with clickable timestamps, best one marked with ⭐
- Writes a Japanese monolingual definition plus a short English Migaku-prompt explanation for each word
- Suggests the best 3-minute section to listen to


## Setup (video vocab)

1. Python 3 with `fugashi` and a UniDic dictionary:
   ```bash
   pip install fugashi unidic-lite
   ```
2. Export your Migaku word statuses as a TSV: `word<TAB>reading<TAB>status` (KNOWN / IGNORED / LEARNING / TRACKED), named like `migaku_words_2026-10-18.tsv`.
3. Get the JPDB frequency dictionary (Yomitan format) and use its `term_meta_bank_1.json`.
4. Get timestamped Japanese captions, one per line as `[start - end] text`.
5. Run:
   ```bash
   python3 skills/japanese-video-vocab/scripts/vocab.py captions.txt \
     --export migaku_words_2026-10-18.tsv \
     --rank-file term_meta_bank_1.json \
     --json out.json --top 10
   ```
   On a Mac you can drop the export in `iCloud Drive/Japanese/` and the JPDB folder in iCloud Drive root, and skip `--export` / `--rank-file`.

Tests: `python3 -m unittest discover -s skills/japanese-video-vocab/scripts -p 'test_*.py'`

Coverage numbers are a vocabulary proxy from captions, not a measure of listening comprehension.

## Install as a skill

Copy `skills/japanese-video-vocab` into your agent's skills directory (for Claude Code: `~/.claude/skills/`).
