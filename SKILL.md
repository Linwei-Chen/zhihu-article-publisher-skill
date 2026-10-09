---
name: zhihu-article-publisher
description: Publish a local Markdown article to Zhihu with local images uploaded in place and LaTeX formulas converted to native Zhihu equations; supports publishing into a specified column or as a standalone article.
---

# Zhihu article publisher

Use this skill when the user wants to publish a Markdown article to Zhihu and the article may contain local images, LaTeX formulas, tables, lists, quotes, or code blocks. It can publish either into a Zhihu column or as a standalone article.

## Core rule

Do not publish user content to Zhihu unless the user explicitly asked for publication. If the request is ambiguous about the destination, ask whether it should go into a column or be published standalone.

## Workflow

1. Read the Markdown file and identify:
   - the first `#` heading as the default title;
   - local image paths;
   - `$...$` and `$$...$$` formulas;
   - any user-specified Zhihu topics.
2. Determine the destination:
   - `--column c_xxxxxxxx` publishes into that column;
   - omitting `--column` publishes as a standalone article.
   - If the user refers to their usual “人工智能与计算机视觉笔记” column without giving an ID, use `c_1027873866512740352`.
3. When the format is uncertain, run a dry run first:

   ```bash
   /Users/chenlinwei/.local/share/uv/tools/pyzhihu-cli/bin/python \
     /Users/chenlinwei/.codex/skills/zhihu-article-publisher/scripts/zhihu_publish.py \
     /absolute/path/to/article.md --dry-run
   ```

4. Publish with:

   ```bash
   /Users/chenlinwei/.local/share/uv/tools/pyzhihu-cli/bin/python \
     /Users/chenlinwei/.codex/skills/zhihu-article-publisher/scripts/zhihu_publish.py \
     /absolute/path/to/article.md \
     --column c_xxxxxxxx \
     -t 19590195 \
     --json
   ```

   For a standalone article, remove `--column`. Repeat `-t` for each topic ID.

5. Verify the returned URL. If you need to confirm the article belongs to a column, query the user's latest article with:

   ```bash
   zhihu user-articles <url_token> --limit 1 --json
   ```

If you do not know the `url_token`, get it with `zhihu whoami --json`.

## Notes and constraints

- The script uses the local `zhihu` CLI login state. It does not read, print, store, or transmit cookies beyond calling the Zhihu API through `pyzhihu-cli`.
- Local image paths are resolved relative to the Markdown file. Images are uploaded to Zhihu and inserted at their original positions.
- Images are converted to JPEG before upload because this avoids Zhihu's image-processing queue getting stuck.
- The tool converts Markdown to HTML with `pandoc`, then converts formulas to native Zhihu equation tags.
- A dry run does not upload images or publish anything; it only writes a `.zhihu.html` preview next to the source Markdown.
- If a temporary test article was created only to validate the workflow, delete it immediately after verification with `zhihu delete-article <article_id> -y`.
