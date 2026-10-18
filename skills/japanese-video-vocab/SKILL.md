---
name: "japanese-video-vocab"
description: "Use when the learner wants vocab from a Japanese YouTube video or podcast: which words to learn, Core 2k/6k/10k or Migaku-star words, top 3 / top 10 words, Japanese (monolingual) definitions, Migaku-prompt English explanations, or timestamps where a word is spoken. Also use to pick Japanese videos or articles that fit the learner's level (about 95-98% known words) and break down their words."
---

# Japanese Video Vocab

Turn one Japanese video into a ranked word list built for Migaku study: Japanese definition first, then a separated Migaku-prompt English explanation, plus clickable timestamps.

## 1. Get the transcript

Get timestamped Japanese captions. In Aside, use the REPL `youtube` global. Elsewhere, `yt-dlp --write-subs --sub-langs ja --skip-download` also works. The scorer expects one caption per line as `[start - end] text`, for example `[0:05.2 - 0:08.9] 今日はコーヒーを淹れます`.

```js
const id = 'VIDEO_ID';
const langs = await youtube.listTranscriptLanguages(id);   // inspect original Japanese track, prefer human captions; caption evidence is not an audio decode
const ts = await youtube.getTranscript(id, { lang: 'ja', includeTimestamp: true });
await fs.writeFile(`<tmp>/${id}.ts.txt`, ts);
```

Do not navigate away from a video the learner is watching. Verify original Japanese captions and natural Japanese transcript content; never imply translated captions establish Japanese audio. State when no independent audio-language check was possible.

## 2. Score it

```bash
python3 <this-skill-dir>/scripts/vocab.py <tmp>/<id>.ts.txt --export <migaku_words_YYYY-MM-DD.tsv> --rank-file <JPDB term_meta_bank_1.json> --json <tmp>/<id>.vocab.json
```

Inspect scorer diagnostics and its JSON before using results. It needs a Migaku word-status export (`word<TAB>reading<TAB>status`, statuses KNOWN/IGNORED/LEARNING/TRACKED) and the JPDB frequency dictionary `term_meta_bank_1.json`. Without `--export`, it looks for the newest `migaku_words_YYYY-MM-DD.tsv` in `iCloud Drive/Japanese/`. A mismatched schema, empty export, or unreadable input must fail visibly, not silently turn every word New.

Report `known_pct` from KNOWN/IGNORED status matches or confirmed user-known overrides separately from `familiar_pct`, which also includes LEARNING/TRACKED. Report reading-match assumptions when present; a matched status is not proof of contextual understanding. Unrecognized proper names stay uncertain, not assumed known, and are not mining targets. Unknown katakana and short kana are not automatically known. Both percentages are transcript-token proxies, not measured listening comprehension. Compare new scorer results only with the same scoring version/basis.

The scorer normalizes rolling/overlapping captions and provides word rows, candidate priorities, and bounded listening sections. Inspect each suggested word and example for caption errors, names, fillers, reading ambiguity, and real practical usefulness. A computed shortlist is a heuristic candidate list, not a substitute for this judgment.

Optional CLI inputs: `--export` and `--rank-file` select data; `--cards` supplies a read-only TSV inventory; `--state` supplies explicit known/relearning overrides; `--top` caps the shortlist; `--section-minutes` controls section windows. The default state is `references/user-state.json`. `New in export`, `present in supplied cards`, `not found in supplied cards`, and `card presence unverified` are distinct evidence labels. A supplied inventory's absence does not prove absence from every deck.

Honor explicit user-known confirmations and deliberate retries through `references/user-state.json`, without editing Migaku. Do not mark unspecified learning words as deliberate retries. If a word later moves to deliberate relearning, remove its known override first. Prefer orthographic/lemma evidence; do not use an ambiguous kana reading to assert that a different kanji word is known.

- Bands: Core 2k = rank 1-2,000, Core 6k = 2,001-6,000, Core 10k = 6,001-10,000.
- Migaku stars: 1-1,500 ★5, 1,501-5,000 ★4, 5,001-15,000 ★3. These are JPDB-based, so state that they can differ by a star from Migaku's default list.
- Prefer human Japanese captions; automatic captions need extra cleanup. Drop obvious ASR artifacts, filler-only candidates, and names from the shortlist without falsely counting them as known. Do not count overlapping rolling-caption duplicates as genuine repetitions.
- 95-98% known is the comfortable zone; below ~92% call it hard.

## 3. Pick and rank for return on study time

Optimize for the next common, useful words the learner does not already know and does not already have cards for. Do not prioritize LEARNING words over New candidates by default.

1. Normally skip confirmed-known words, honoring explicit recent user confirmations that postdate the export. Words with existing cards remain eligible but lower priority than equally useful missing-card words. If the learner explicitly marked a word to retry learning, treat it as intentional relearning, not a duplicate to discard; label it `Relearning` only with evidence of that intent. Do not infer that all LEARNING statuses mean deliberate retries. A clean, frequent, useful relearning opportunity can outrank a weak New candidate.
2. Check card/deck inventory read-only when available. Vocabulary status is not card inventory: NEW means absent from the inspected vocabulary export, not proven absent from every deck. LEARNING/TRACKED likewise do not establish card presence. Check spelling/reading variants and compounds before claiming a missing card. If card inventory is unavailable, label card absence unverified; prefer export-New candidates while retaining useful LEARNING/TRACKED candidates at lower priority. Do not stall or claim deduplication succeeded.
3. **Ranking rule: commonness first, combined.** Never skip a word just because it is LEARNING, TRACKED, Relearning, or already has a card; include it, labeled, but rank it below NEW/no-card words of similar usefulness. Only confirmed-known words, names, ASR artifacts, and fragments are dropped. Within each priority tier, sort by JPDB frequency rank (more common first). A less common word may move ahead of a more common one only within the same band and only with a clearly better example (sentence vs fragment) or a clearly easier section. If a common word has no usable example, drop it down rather than forcing it. A practically useful word above 10k (banking, housing, cooking, work) gets a separate "impact" slot instead of displacing common words. JPDB frequency comes from media (anime, drama, novels), so practical usefulness is a judgment call used only for tiebreaks and the impact slot. Use 2k -> 6k -> 10k as a progression guide, not equal quotas.
4. Favor clear one-unknown sentence examples, clean Japanese audio/context, repetition after caption deduplication, and examples that are quick to turn into a good card. Rank videos/sections by distinct useful missing-card candidates per recommended listening minute, balanced with comprehensibility and enjoyment, not raw unknown counts.
5. Default to Top 3, expanding to 5-10 only when the remaining words earn their place. Give 15+ only when requested. Include band, rank, vocabulary status, and card-presence evidence separately. Never invent exact ROI scores or force five words per band.

Optional: list current target words in `references/targets.tsv` (for example the useful NEW words left in the 2k band). When choosing videos, favor ones where these words appear with usable examples, and flag them as targets. Remove words only when the learner says they are learned or carded.

Flag current explicit target words and deliberate retries when they appear. Keep existing-card/LEARNING/TRACKED/Relearning candidates in the list, labeled and deprioritized below comparable NEW words; promote intentional relearning when its usefulness and context justify it.

## 4. Write each entry

Default layout: one word at a time, everything for that word lined up together: header, ⭐ timestamp links, the best i+1 sentence, the Japanese definition, then a small blank + rule + small blank, then the English definition (so the learner can stop before the English). Do not put an extra `---` between words; the `###` header separates them. No English glosses or dictionary equivalents anywhere.

```markdown
### 1. 程度【ていど】 ★★★★★ #597 ・ 10回
▶ ⭐[5:47](https://www.youtube.com/watch?v=ID&t=347s) [9:08](https://www.youtube.com/watch?v=ID&t=548s) [14:16](https://www.youtube.com/watch?v=ID&t=856s)
> ある程度は分かるようになった。

ものごとの量や大きさが、どのくらいかという度合い。この文では「ある程度」で、全部ではないけど少しは、という意味。

&nbsp;

---

&nbsp;

How much or how far something goes, as a level or amount. Here, to a certain extent: not fully, but noticeably.
```

The `▶` line has no "i+1" label (the ⭐ marks the best i+1 spot; all links are i+1 unless labeled `(not i+1)`). The `>` line is the ⭐ sentence. No JP/EN labels.

Header: number, word, 【reading】 (omit for kana words), stars, #rank, `・ N回` when N ≥ 2 and caption cleanup supports the count. Label `New in export` separately from `Present in supplied cards`, `Not found in supplied cards`, or `Card presence unverified`. Absence from a partial inventory is not proof of absence from all decks. Do not equate vocabulary status with card presence.

**Timestamp links must have accurate evidence labels.** Sentence-level i+1 means the target is the only unknown lexical item in a punctuation-bounded sentence, with no unresolved uncertain tokens. A clause-level hit and a caption-fragment proxy are not the same as a complete sentence. The scorer's timings are caption-granularity estimates, not word-accurate audio cuts. Review the context before endorsing a mining example.

- Use `ip1_times` / `ip1_hits` for sentence candidates; review sentence completeness and caption accuracy.
- Use `ip1_clause_times` / `ip1_clause_hits` only as labeled clause contexts, not unqualified sentence i+1.
- Use `ip1_caption_times` / `ip1_caption_hits` only as caption proxies. They must say `(caption fragment; review)` and must not receive the best-sentence marker. Unpunctuated transcripts can yield no reliable sentence hits; do not repair that by inventing punctuation or a numerical sentence count.
- Inspect `sections` and choose a comfortably understandable, useful section rather than requiring the entire video. Show its start/end and 2-3 useful words. Candidate density is a measured proxy, not a claim of learning gain.

For reliable examples:

1. Sentence-level i+1 (`ip1_times`) first, then reviewed actual clause hits (`ip1_clause_times`), explicitly labeled `(clause)`. Show up to 3 links. Caption proxies (`ip1_caption_times`) must be labeled `(caption fragment; review)` rather than i+1 sentences.
2. If a word has no reviewed sentence or clause hit, link a caption proxy with its evidence label or its first occurrence as `(not verified i+1)`. Prefer dropping weak examples from Top 3 unless the target's practical/relearning value justifies them.
3. The example sentence should be the **best i+1 hit** (JSON `ip1_hits` / `ip1_clause_hits` give time + text). Choose by: short and self-contained > full sentence over a clause > shows the core meaning clearly > avoids long caption run-ons. Put that hit's timestamp first in the ▶ links and mark it with ⭐ right before the link (`⭐[11:34](…)`), so the learner can see at a glance which timestamp is the best i+1 sentence. Only one ⭐ per word. Never put ⭐ on a `(not i+1)` link. Use ⭐ (not ★) so it isn't confused with the Migaku star rating. Trim run-ons to the clause plus just enough context.

If the learner asks for every timestamp, list all occurrences, with the i+1 ones marked.

**Japanese definition**: plain, easy Japanese like a native monolingual dictionary, core meaning in one sentence, then 「この文では…」 for the nuance in this video. Never use the word itself in its own definition.

**English (Migaku-prompt style)**: explain what the word means, not the sentence. Write it like a Japanese-to-Japanese dictionary would, but in English. Avoid direct English equivalents. Use 100% English with no Japanese at all. Give only the core meaning, in one plain, intuitive sentence of about 15 words max. Don't repeat the word and don't add any intro. End with the specific nuance in this context, starting with "Here, ...".

Example sentences must come from the inspected video context, lightly cleaned only when the correction is supported. If captions are too garbled, choose a different occurrence or drop the candidate. If the user asks for an invented practice sentence, label it generated and never attach a video timestamp or an i+1 verification claim to it.

## 5. Delivery

- For daily recommendations, use a compact pick: bare URL, title/channel/date, full duration and best listening section, coverage basis, practical benefit, and 2-3 target words with band/rank/status/card evidence. Do not dump a full dictionary breakdown before the learner chooses a video.
- For a requested vocabulary breakdown, default to Top 3, adding 4-10 only when useful. Use the lined-up word blocks above. No extra words to satisfy quotas. The chat cannot hide text; the gap before English is the substitute. Use a card page only when requested.
- If the learner wants a card page: an HTML artifact with front = sentence (target word bold/orange), back = word, reading, star/rank/Learning-New tag, timestamp buttons (the best i+1 button labeled with ⭐ and visually highlighted), Japanese definition, and English in a black bar (`background:#111;color:#111`, readable on `::selection`). Give the `file://` link on its own line.
- Deck placement (example setup): put mined words into band decks such as **Core 2k Mining** (rank 1-2,000), **Core 6k Mining** (2,001-6,000), and **Core 10k Mining** (6,001-10,000). Ask before creating a new deck. Tag each Top 3 / Top 10 word with its deck when asked.
- Making a Migaku card: the study.migaku.com web app has no card creator ("Create cards using the Migaku Browser Extension"). On the YouTube tab, seek to the i+1 timestamp, click the word in the Migaku subtitle browser, then use the popup's create button (`ID:UiDictEntry.create.0`). Cards land in a queue in the separate "Migaku | Dictionary" extension window, where the learner finishes them. Click only once: each click queues another copy. Suggested card settings: deck = the band deck; the sentence trimmed to the i+1 part; the Japanese definition from this skill; **as much audio as possible for both the word and the sentence** (every native/word recording and TTS voice Migaku offers, plus the video clip audio for the sentence).
- After the list, at most one line of guidance (e.g. which stretch of the video packs the top words, or add New target words to Mining). No follow-up menus.


## 6. Calibrate using reported listening experience

Read `references/listening-feedback.tsv` when choosing new content. Record a row only when the learner explicitly reports the experience: video_id, channel, reported_at, rating (`easy`, `comfortable`, `needed-subtitles`, `too-fast`, or `too-hard`), captions used, and their notes. Never infer watched status from a recommendation, open tab, or playback, and do not modify the main listening log without the learner's actual listening report.

Use recent feedback qualitatively: favor channels and speech styles the learner actually understands; favor shorter/slower/visual sections after `too-fast` or `needed-subtitles`; offer more natural speech or useful higher-band words when content is consistently easy. One difficult report is not a blanket channel ban. Speech speed, accent, grammar, and enjoyment can override a vocabulary percentage. With no feedback yet, do not claim personal listening calibration; use the conservative baseline without repeating this caveat on every daily pick.

For stale vocabulary exports, honor `references/user-state.json` and disclose the export date. Do not claim live deck completeness or listening ability from old vocabulary data. Run regression tests after scorer edits: `python3 -m unittest discover -s <this-skill-dir>/scripts -p 'test_vocab.py'`.


## 7. Japanese article picks

Use the same interests, practical Japanese-life/culture focus, vocabulary-status priorities, known/familiar distinction, explicit known/relearning state, and conservative card evidence as for videos. Article reading fit is not listening fit. Preserve the 95-98% known target; label below-target readings as stretches and do not promise comprehension from familiar coverage alone.

Find specific readable articles, not merely site homepages. Inspect the full scored article body. Exclude menus, advertisements, comments, unrelated glossary/proverb sections, and ruby readings (`rt`/`rp`) so kanji and furigana are not counted twice. If scoring only a section, identify it explicitly. Do not bypass paywalls or required consent and do not score a search snippet as a full article. Verify dates on the publisher page; news is at most 14 days old. Older undated evergreen pieces remain eligible, but label publication date unknown and do not present old venue details or social rules as verified current guidance.

Save clean UTF-8 body text with blank lines between source paragraphs. Run:

```bash
python3 <this-skill-dir>/scripts/article.py <tmp>/article.txt --json <tmp>/article.json --top 10
```

Optional `--export`, `--rank-file`, `--cards`, `--state`, and `--max-rank` match the video scorer. Article JSON supplies paragraph references, evidence-labeled examples, character count, known/familiar coverage, uncertainty, and word/card status. It has no video timestamps or invented reading duration. Only punctuation-bounded examples are sentence candidates; clause/paragraph fragments require explicit proxy labels. Repeated article text is retained, not treated as rolling captions. Manually reject false words produced from names, compounds, or ambiguous tokenization, even when the script ranks them highly.

Videos are the priority: articles are secondary. Recommend at most 1 article per daily run, only when clearly worthwhile, ideally reinforcing a target from a recommended video; never let article work crowd out video quality. Prioritize genuinely useful New-in-export candidates; existing learning/relearning words remain eligible at lower priority. Identify reused targets across video and article contexts when that helps retention. Give bare URL, title/publisher/date, known/familiar coverage, scored scope, length in Japanese characters if useful, and 1-3 genuine target words with rank/band/status. State once when card absence remains unverified. Built-in audio may be mentioned only when inspected; don't claim it was listened to or language-decoded. Full definitions/paragraph analysis are for requested breakdowns, not every daily pick.

Track article recommendations by canonical URL to prevent repeats. Record reading feedback only from explicit user reports, separately from video watched status. Run both suites after edits: `python3 -B -m unittest discover -s <this-skill-dir>/scripts -p 'test_*.py'`.
