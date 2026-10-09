#!/Users/chenlinwei/.local/share/uv/tools/pyzhihu-cli/bin/python
"""Publish a local Markdown article to Zhihu.

Usage:
    zhihu_publish.py article.md [--column c_xxx] [-t TOPIC_ID ...]
                                [--title TITLE] [--dry-run] [--json]
"""

from __future__ import annotations

import argparse
import html as H
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import quote

from PIL import Image

from zhihu_cli.auth import cookie_str_to_dict, get_cookie_string
from zhihu_cli.client import ZhihuClient
from zhihu_cli.config import ZHIHU_IMAGE_API, ZHIHU_ZHUANLAN_API
from zhihu_cli.exceptions import DataFetchError


EQUATION_BASE = "https://www.zhihu.com/equation?tex="
IMG_MD = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def die(message: str) -> None:
    print(f"✗ {message}", file=sys.stderr, flush=True)
    sys.exit(1)


def collect_local_images(markdown: str, base_dir: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for _alt, raw in IMG_MD.findall(markdown):
        raw = raw.strip()
        if raw.startswith(("http://", "https://", "data:")):
            continue
        path = Path(raw)
        if not path.is_absolute():
            path = (base_dir / path).resolve()
        if not path.is_file():
            die(f"找不到图片文件: {raw}（相对 {base_dir}）")
        found[raw] = path
    return found


def to_jpeg(path: Path) -> Path:
    temp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    temp_name = temp.name
    temp.close()
    with Image.open(path) as image:
        if image.mode in ("RGBA", "LA"):
            rgb_image = Image.new("RGB", image.size, "white")
            rgb_image.paste(image, mask=image.split()[-1])
        else:
            rgb_image = image.convert("RGB")
        rgb_image.save(temp_name, format="JPEG", quality=92, optimize=True)
    return Path(temp_name)


def upload_image_with_retry(client: ZhihuClient, path: Path) -> dict:
    jpeg_path = to_jpeg(path)
    try:
        return client.upload_image(str(jpeg_path), source="article")
    except DataFetchError as exc:
        if "Image processing timed out" not in str(exc):
            raise
        log("    ↻ 知乎图片处理卡住，重新编码后重试")
        retry_path = to_jpeg(path)
        try:
            return client.upload_image(str(retry_path), source="article")
        finally:
            retry_path.unlink(missing_ok=True)
    finally:
        jpeg_path.unlink(missing_ok=True)


def upload_images(mapping: dict[str, Path]) -> dict[str, dict]:
    uploaded: dict[str, dict] = {}
    for raw, path in mapping.items():
        log(f"  ↑ 上传图片: {path.name}")
        # A fresh session per image avoids Zhihu's image queue hanging after
        # several rapid uploads in the same session.
        cookie = get_cookie_string()
        if not cookie:
            die("未登录：先运行 zhihu login --qrcode")
        with PatientZhihuClient(cookie_str_to_dict(cookie)) as client:
            info = upload_image_with_retry(client, path)
        uploaded[raw] = {
            "src": info["src"],
            "original": info.get("original_src", info["src"]),
            "watermark": info.get("watermark", "watermark"),
            "watermark_src": info.get("watermark_src", ""),
            "w": info.get("width", 0),
            "h": info.get("height", 0),
        }
    return uploaded


class PatientZhihuClient(ZhihuClient):
    """Poll Zhihu image processing long enough for slow uploads."""

    def _poll_image(
        self, image_id: str, max_attempts: int = 20, interval: float = 2.0
    ) -> dict:
        for attempt in range(1, max_attempts + 1):
            response = self._session.get(
                f"{ZHIHU_IMAGE_API}/{image_id}", timeout=30
            )
            data = response.json()
            status = data.get("status")
            if attempt == 1 or attempt % 10 == 0 or status not in (None, "processing"):
                log(f"  ⏳ 图片处理中（第 {attempt} 次）：{status}")
            if status == "success":
                return {
                    "src": data["src"],
                    "original_src": data["original_src"],
                    "watermark": data.get("watermark", "watermark"),
                    "watermark_src": data.get("watermark_src", ""),
                }
            if attempt == 1 and status != "processing":
                log("    ↯ 图片接口返回：" + json.dumps(data, ensure_ascii=False)[:300])
            time.sleep(interval)
        raise DataFetchError("Image processing timed out")


def markdown_to_html(markdown_path: Path) -> str:
    pandoc = shutil.which("pandoc")
    if not pandoc:
        die("未找到 pandoc，请先安装（brew install pandoc）")
    output = tempfile.NamedTemporaryFile(suffix=".html", delete=False).name
    subprocess.run(
        [
            pandoc,
            "-f",
            "markdown+tex_math_single_backslash",
            "-t",
            "html",
            "--mathjax",
            "--wrap=none",
            str(markdown_path),
            "-o",
            output,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(output).read_text(encoding="utf-8")


def equation_tag(match: re.Match, display: bool) -> str:
    tex = match.group(1)[2:-2].strip()
    kind = "2" if display else "1"
    return (
        f'<img eeimg="{kind}" src="{EQUATION_BASE}{quote(tex)}" '
        f'alt="{H.escape(tex)}">'
    )


def zhihu_image(info: dict, caption: str = "") -> str:
    caption = H.escape(caption)
    return (
        f'<img src="{info["src"]}" data-caption="{caption}" '
        f'data-size="normal" data-rawwidth="{info["w"]}" '
        f'data-rawheight="{info["h"]}" '
        f'data-watermark="{info.get("watermark", "watermark")}" '
        f'data-original-src="{info["original"]}" '
        f'data-watermark-src="{info.get("watermark_src", "")}" '
        f'data-private-watermark-src="" />'
    )


def postprocess(html: str, uploaded: dict[str, dict]) -> str:
    html = re.sub(r"\s*<h1[^>]*>.*?</h1>", "", html, count=1, flags=re.S)

    html = re.sub(
        r'<span class="math inline">(.*?)</span>',
        lambda match: equation_tag(match, False),
        html,
        flags=re.S,
    )
    html = re.sub(
        r'<span class="math display">(.*?)</span>',
        lambda match: equation_tag(match, True),
        html,
        flags=re.S,
    )

    def replace_image(match: re.Match) -> str:
        block = match.group(0)
        image = re.search(r'<img[^>]*src="([^"]+)"[^>]*>', block)
        if not image:
            return block
        info = uploaded.get(image.group(1))
        if info is None:
            return block
        alt_match = re.search(r'alt="([^"]*)"', image.group(0))
        alt = H.unescape(alt_match.group(1)) if alt_match else ""
        return zhihu_image(info, alt)

    html = re.sub(
        r"<figure[^>]*>(?:(?!</figure>).)*?</figure>",
        replace_image,
        html,
        flags=re.S,
    )
    html = re.sub(r'<p><img[^>]*src="([^"]+)"[^>]*/?></p>', replace_image, html)

    def drop_duplicate_caption(match: re.Match) -> str:
        caption = H.escape(H.unescape(match.group(2)))
        return match.group(1) if caption == match.group(2) else match.group(0)

    html = re.sub(
        r'(<img [^>]*data-caption="([^"]+)"[^>]*/>)\s*<p><i>\2</i></p>',
        drop_duplicate_caption,
        html,
        flags=re.S,
    )

    def fix_table(match: re.Match) -> str:
        table = match.group(0)
        header_match = re.search(
            r"<thead[^>]*>\s*(<tr.*?</tr>)\s*</thead>", table, re.S
        )
        header = header_match.group(1) if header_match else ""
        table = re.sub(r"<thead[^>]*>.*?</thead>", "", table, flags=re.S)
        if header:
            table = re.sub(
                r"(<tbody[^>]*>)",
                lambda inner: inner.group(1) + header,
                table,
                count=1,
            )
        table = re.sub(r"<colgroup[^>]*>.*?</colgroup>", "", table, flags=re.S)
        table = re.sub(r'<tr class="[^"]*"', "<tr", table)
        return table

    html = re.sub(r"<table.*?</table>", fix_table, html, flags=re.S)
    html = html.replace(
        "<table>",
        '<table data-draft-node="block" data-draft-type="table" '
        'data-size="normal" data-row-style="normal">',
    )
    html = html.replace("<strong>", "<b>").replace("</strong>", "</b>")
    html = html.replace("<em>", "<i>").replace("</em>", "</i>")
    return html.strip()


def publish(
    client: ZhihuClient,
    title: str,
    content: str,
    topics: list[str],
    column: str | None,
) -> str:
    response = client._session.post(
        f"{ZHIHU_ZHUANLAN_API}/articles/drafts", json={}, timeout=30
    )
    if response.status_code != 200:
        die(f"创建草稿失败({response.status_code}): {response.text[:200]}")
    draft_id = response.json().get("id", "")
    if not draft_id:
        die("创建草稿成功但未返回 ID")

    draft = {"title": title, "content": content}
    if topics:
        draft["topics"] = topics
    if column:
        draft["column"] = [column]

    response = client._session.patch(
        f"{ZHIHU_ZHUANLAN_API}/articles/{draft_id}/draft",
        json=draft,
        timeout=30,
    )
    if response.status_code not in (200, 204):
        die(f"写入草稿失败({response.status_code}): {response.text[:200]}")

    business = {
        "disclaimer_type": "none",
        "disclaimer_status": "close",
        "table_of_contents_enabled": False,
        "content": content,
        "title": title,
        "commercial_report_info": {"commercial_types": []},
        "commercial_zhitask_bind_info": None,
        "canReward": False,
    }
    payload = {
        "action": "article",
        "data": {
            "publish": {
                "traceId": f"{int(time.time() * 1000)},{uuid.uuid4()}"
            },
            "extra_info": {
                "publisher": "pc",
                "pc_business_params": json.dumps(business, ensure_ascii=False),
            },
            "draft": {"disabled": 1, "id": draft_id, "isPublished": False},
            "commentsPermission": {"comment_permission": "anyone"},
            "creationStatement": {
                "disclaimer_type": "none",
                "disclaimer_status": "close",
            },
            "contentsTables": {"table_of_contents_enabled": False},
            "commercialReportInfo": {"isReport": 0},
            "appreciate": {"can_reward": False, "tagline": ""},
            "hybridInfo": {},
            "hybrid": {"html": content, "textLength": len(content)},
            "title": {"title": title},
        },
    }
    if column:
        payload["data"]["column"] = {"column": [column]}

    response = client._session.post(
        "https://www.zhihu.com/api/v4/content/publish",
        json=payload,
        timeout=30,
    )
    if response.status_code != 200:
        die(f"发布失败({response.status_code}): {response.text[:300]}")
    try:
        body = response.json()
        result = json.loads(body.get("data", {}).get("result", "{}"))
        return str(result.get("publish", {}).get("id", draft_id))
    except (ValueError, AttributeError, TypeError):
        return draft_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish local Markdown with images and formulas to Zhihu"
    )
    parser.add_argument("markdown", type=Path)
    parser.add_argument(
        "-t", "--topic", dest="topics", action="append", default=[]
    )
    parser.add_argument("--column", default=None)
    parser.add_argument("--title", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    markdown_path = args.markdown.resolve()
    if not markdown_path.is_file():
        die(f"文件不存在: {markdown_path}")
    markdown = markdown_path.read_text(encoding="utf-8")

    title_match = re.search(r"^#\s+(.+?)\s*$", markdown, flags=re.M)
    title = (
        args.title
        or (title_match.group(1) if title_match else None)
        or ""
    ).strip()
    if not title:
        die("未找到标题：请在 md 里写一级标题，或用 --title 指定")

    images = collect_local_images(markdown, markdown_path.parent)
    log(f"标题: {title}")
    log(f"本地图片: {len(images)} 张")

    if args.dry_run:
        html = postprocess(markdown_to_html(markdown_path), {})
        output = markdown_path.with_suffix(".zhihu.html")
        output.write_text(html, encoding="utf-8")
        log(f"[dry-run] 已生成 {output}")
        return

    cookie = get_cookie_string()
    if not cookie:
        die("未登录：先运行 zhihu login --qrcode")

    uploaded = upload_images(images) if images else {}
    log("转换知乎格式 HTML…")
    html = postprocess(markdown_to_html(markdown_path), uploaded)
    log(f"发布中（column={args.column or '无'}）…")
    with PatientZhihuClient(cookie_str_to_dict(cookie)) as client:
        article_id = publish(client, title, html, args.topics, args.column)

    result = {
        "id": article_id,
        "url": f"https://zhuanlan.zhihu.com/p/{article_id}",
        "title": title,
        "column": args.column,
        "topics": args.topics,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        log(f"✓ 发布成功: {result['url']}")


if __name__ == "__main__":
    main()
