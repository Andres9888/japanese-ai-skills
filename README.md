# japanese-ai-skills

AI agent skills I use to learn Japanese with Migaku. Written as `SKILL.md` files for Claude-style agents (Claude Code, Aside, or anything that reads skill folders).

Goal: get fluent in Japanese (around 10k known words), using AI as much as possible.

## Skills

### `japanese-video-vocab`
Scores a Japanese YouTube video (or article) against your Migaku known words and picks what to learn next.

- Known vs familiar coverage for the video, so you can pick content where you already know ~95-98%
- Ranks the words you don't know by frequency (JPDB), most common first, grouped into Core 2k / 6k / 10k bands
- Finds i+1 sentences (only one unknown word) with clickable timestamps, best one marked with ⭐
- Writes a Japanese monolingual definition plus a short English Migaku-prompt explanation for each word
- Suggests the best 3-minute section to listen to

### `japanese-progress-post`
Turns a Migaku stats screenshot into a 2-post X thread (Proof, Goal, Method, Invite + "how it works") and stages it in the composer for you to post.

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

## Install as skills

Copy a folder from `skills/` into your agent's skills directory (for Claude Code: `~/.claude/skills/`).
