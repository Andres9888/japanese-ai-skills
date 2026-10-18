---
name: "japanese-progress-post"
description: "Use when the learner shares a Migaku stats/share screenshot or asks for a Japanese progress post, Migaku post, known-words update, or 'make the post' for X. Drafts and stages a 2-post thread in the X composer using a Proof, Goal, Method, Invite format. Never posts without the learner's click."
---

# Japanese Progress Post (X)

## Framework: Proof, Goal, Method, Invite + "how it works" reply

Post 1 (with the Migaku screenshot attached):
1. **Proof**: current known-word count from the screenshot + `@MigakuOfficial`.
2. **Goal**: the learner's own goal in their own words (for example `goal is to get fluent, around 10k words, maybe by next year`). Never invent a deadline, JLPT level, or trip date.
3. **Method**: one line on what they are trying right now (for example using AI to find i+1 words).
4. **Invite**: `ask if you want the setup` (or a genuine question to peers).
5. `#日本語勉強中`

Post 2 (reply, no image): `how it works:` + 3 short dash bullets that make the method concrete.

Example:

```
5261 known words in @MigakuOfficial. goal is to get fluent, around 10k words, maybe by next year

using ai as much as possible. right now it finds me good i+1 words, most common first, then ones that help me, from content i'm into

ask if you want the setup

#日本語勉強中
---
how it works:

- scores youtube videos against my known words, only keeps ones where i already know ~95%
- pulls the most common words i don't know + the timestamp they're said
- turns the video into primed listening audio, english line right before each japanese line
```

## Steps

1. Read the attached screenshot. Use the total known words (not the "+N today" number).
2. Read the learner's last few posts so the new post does not repeat the previous method line word for word.
3. Pick the Method line. Rotate the angle so each post adds something new, using only things the learner actually did:
   - AI i+1 word finding
   - primed listening audio (English line before each Japanese line)
   - one specific word mined this week + where it was heard
   - a video/channel that hit ~95% known
   - shadowing/chorusing
   If unsure what they did this week, ask one short question instead of inventing it.
4. Match the learner's voice. Default: lowercase, flat, no emojis, no hype, no "day N", no manufactured punchline. Keep the method line to 1-2 sentences.
5. Count weighted length (each CJK character counts as 2). Both posts must be <= 280. Report the counts.
6. Stage in the X composer, screenshot it, and show both posts. Stop after one version unless asked for changes.

## Staging mechanics (browser automation)

- Open the composer from the sidebar `Post` link. Type with `keyboard.insertText` per line and `Shift+Enter` between lines.
- Attach the image with `setInputFiles` on `input[type="file"][data-testid="fileInput"]`.
- Add post 2 with the `Add post` button, then type.
- In a narrow window X shows only the focused post and earlier posts are not in the DOM. Verify the thread by reading every `[role="dialog"] [data-testid^="tweetTextarea_"][role="textbox"]` or switching to the modal view. Do not open a second composer (duplicate risk).
- To edit, click the textbox, select all, delete, retype.
- Never click outside the composer dialog while staged; it can discard the thread.
- Never click `Post` / `Post all`. The learner posts.
