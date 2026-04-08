"""Shared Jira API, ADF conversion, and content processing utilities.

Used by both submit.py (standard) and split_submit.py (split submissions).

Environment variables:
    JIRA_SERVER  Jira server URL (e.g. https://mysite.atlassian.net)
    JIRA_USER    Jira username/email
    JIRA_TOKEN   Jira API token
"""

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request


# ─── HTTP Layer ───────────────────────────────────────────────────────────────

def make_request(url, user, token, body=None, method=None):
    """HTTP request with Basic Auth. Returns parsed JSON or None for 204."""
    credentials = base64.b64encode(f"{user}:{token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Accept": "application/json",
    }
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        if resp.status == 204:
            return None
        resp_body = resp.read()
        if not resp_body:
            return None
        return json.loads(resp_body)


def api_call(server, path, user, token, body=None, method=None):
    """Build full URL and call make_request."""
    url = f"{server.rstrip('/')}/rest/api/3{path}"
    return make_request(url, user, token, body, method)


def api_call_with_retry(server, path, user, token, body=None, method=None,
                        max_retries=3):
    """Wrap api_call with retry on transient errors."""
    last_error = None
    for attempt in range(max_retries):
        try:
            return api_call(server, path, user, token, body, method)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry_after = int(e.headers.get("Retry-After", 1))
                wait = max(retry_after, 1)
                print(f"  Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                last_error = e
                continue
            if e.code in (502, 503, 504):
                wait = 4 ** attempt  # 1, 4, 16
                print(f"  HTTP {e.code}, retrying in {wait}s...",
                      file=sys.stderr)
                time.sleep(wait)
                last_error = e
                continue
            error_body = e.read().decode("utf-8", errors="replace")
            print(f"HTTP {e.code}: {error_body}", file=sys.stderr)
            raise
        except urllib.error.URLError as e:
            wait = 4 ** attempt
            print(f"  Network error: {e.reason}, retrying in {wait}s...",
                  file=sys.stderr)
            time.sleep(wait)
            last_error = e
    raise last_error


def require_env():
    """Read and validate Jira env vars. Returns (server, user, token)."""
    server = os.environ.get("JIRA_SERVER")
    user = os.environ.get("JIRA_USER")
    token = os.environ.get("JIRA_TOKEN")
    return server, user, token


# ─── Jira Operations ─────────────────────────────────────────────────────────

def get_issue(server, user, token, key, fields=None):
    """GET /rest/api/3/issue/{key}"""
    path = f"/issue/{key}"
    if fields:
        path += f"?fields={','.join(fields)}"
    return api_call_with_retry(server, path, user, token)


def get_comments(server, user, token, issue_key):
    """GET all comments for an issue, handling pagination."""
    comments = []
    start_at = 0
    while True:
        path = f"/issue/{issue_key}/comment?startAt={start_at}&maxResults=100"
        data = api_call_with_retry(server, path, user, token)
        batch = data.get("comments", [])
        comments.extend(batch)
        if start_at + len(batch) >= data.get("total", 0):
            break
        start_at += len(batch)
    return comments


def add_comment(server, user, token, issue_key, body_adf):
    """POST a comment with ADF body."""
    path = f"/issue/{issue_key}/comment"
    return api_call_with_retry(server, path, user, token,
                               body={"body": body_adf})


def create_issue(server, user, token, project, issue_type, summary,
                 description_adf, priority, labels=None):
    """POST /rest/api/3/issue — returns the created issue key."""
    body = {
        "fields": {
            "project": {"key": project},
            "issuetype": {"name": issue_type},
            "summary": summary,
            "description": description_adf,
            "priority": {"name": priority},
        }
    }
    if labels:
        body["fields"]["labels"] = labels
    result = api_call_with_retry(server, "/issue", user, token, body=body)
    return result["key"]


def update_issue(server, user, token, issue_key, summary, description_adf):
    """PUT to update an existing issue's summary and description."""
    body = {
        "fields": {
            "summary": summary,
            "description": description_adf,
        }
    }
    path = f"/issue/{issue_key}"
    api_call_with_retry(server, path, user, token, body=body, method="PUT")


def add_labels(server, user, token, issue_key, labels):
    """Add labels to an existing issue without removing existing ones."""
    body = {
        "update": {
            "labels": [{"add": label} for label in labels]
        }
    }
    path = f"/issue/{issue_key}"
    api_call_with_retry(server, path, user, token, body=body, method="PUT")


def remove_labels(server, user, token, issue_key, labels):
    """Remove labels from an existing issue."""
    body = {
        "update": {
            "labels": [{"remove": label} for label in labels]
        }
    }
    path = f"/issue/{issue_key}"
    api_call_with_retry(server, path, user, token, body=body, method="PUT")


# ─── ADF Helpers ──────────────────────────────────────────────────────────────

def _adf_doc(content):
    """Wrap content nodes in an ADF document."""
    return {"type": "doc", "version": 1, "content": content}


def _adf_paragraph(text_nodes):
    """Create an ADF paragraph from text nodes."""
    return {"type": "paragraph", "content": text_nodes}


def _adf_text(text, marks=None):
    """Create an ADF text node, optionally with marks."""
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return node


def _adf_heading(level, text_nodes):
    """Create an ADF heading node."""
    return {"type": "heading", "attrs": {"level": level},
            "content": text_nodes}


def _adf_code_block(text, language=""):
    """Create an ADF codeBlock node."""
    node = {"type": "codeBlock", "content": [_adf_text(text)]}
    if language:
        node["attrs"] = {"language": language}
    return node


def _adf_bullet_list(items):
    """Create an ADF bulletList from a list of content node lists."""
    return {
        "type": "bulletList",
        "content": [
            {"type": "listItem", "content": [_adf_paragraph(nodes)]}
            for nodes in items
        ],
    }


def _adf_ordered_list(items):
    """Create an ADF orderedList from a list of content node lists."""
    return {
        "type": "orderedList",
        "content": [
            {"type": "listItem", "content": [_adf_paragraph(nodes)]}
            for nodes in items
        ],
    }


def _adf_rule():
    """Create an ADF horizontal rule."""
    return {"type": "rule"}


def _adf_table(rows, has_header=True):
    """Create an ADF table from rows of cell text lists.

    Each row is a list of cell strings. If has_header, the first row
    uses tableHeader cells; remaining rows use tableCell.
    """
    adf_rows = []
    for row_idx, cells in enumerate(rows):
        is_header = has_header and row_idx == 0
        cell_type = "tableHeader" if is_header else "tableCell"
        adf_cells = []
        for cell_text in cells:
            adf_cells.append({
                "type": cell_type,
                "content": [_adf_paragraph(_parse_inline(cell_text.strip()))],
            })
        adf_rows.append({"type": "tableRow", "content": adf_cells})
    return {"type": "table", "content": adf_rows}


def _parse_inline(text):
    """Parse inline markdown formatting into ADF text nodes with marks.

    Handles: **bold**, *italic*, ~~strike~~, `code`, [text](url)
    """
    nodes = []
    pattern = re.compile(
        r'(\*\*(?P<bold>.+?)\*\*)'
        r'|(\*(?P<italic>.+?)\*)'
        r'|(~~(?P<strike>.+?)~~)'
        r'|(`(?P<code>[^`]+)`)'
        r'|(\[(?P<link_text>[^\]]*)\]\((?P<link_url>[^)]+)\))'
    )
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            nodes.append(_adf_text(text[pos:m.start()]))

        if m.group("bold") is not None:
            nodes.append(_adf_text(m.group("bold"), [{"type": "strong"}]))
        elif m.group("italic") is not None:
            nodes.append(_adf_text(m.group("italic"), [{"type": "em"}]))
        elif m.group("strike") is not None:
            nodes.append(_adf_text(m.group("strike"), [{"type": "strike"}]))
        elif m.group("code") is not None:
            nodes.append(_adf_text(m.group("code"), [{"type": "code"}]))
        elif m.group("link_text") is not None:
            nodes.append(_adf_text(
                m.group("link_text"),
                [{"type": "link",
                  "attrs": {"href": m.group("link_url")}}]
            ))
        pos = m.end()

    if pos < len(text):
        nodes.append(_adf_text(text[pos:]))

    return nodes if nodes else [_adf_text(text)]


def markdown_to_adf(markdown):
    """Convert markdown to Atlassian Document Format.

    Handles: headings, paragraphs, bullet/ordered lists, bold, italic,
    strikethrough, code spans, code blocks, blockquotes, tables,
    horizontal rules, links, and checkboxes (as text).
    """
    lines = markdown.split("\n")
    content = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Code block
        if line.startswith("```"):
            lang = line[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            content.append(_adf_code_block("\n".join(code_lines), lang))
            continue

        # Heading
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            content.append(_adf_heading(level, _parse_inline(text)))
            i += 1
            continue

        # Horizontal rule
        if re.match(r'^---+\s*$', line):
            content.append(_adf_rule())
            i += 1
            continue

        # Bullet list
        if re.match(r'^[-*]\s', line) or re.match(r'^- \[[ x]\]\s', line):
            items = []
            while i < len(lines) and (re.match(r'^[-*]\s', lines[i]) or
                                       re.match(r'^- \[[ x]\]\s', lines[i])):
                item_text = re.sub(r'^[-*]\s+', '', lines[i])
                items.append(_parse_inline(item_text))
                i += 1
            content.append(_adf_bullet_list(items))
            continue

        # Ordered list
        if re.match(r'^\d+\.\s', line):
            items = []
            while i < len(lines) and re.match(r'^\d+\.\s', lines[i]):
                item_text = re.sub(r'^\d+\.\s+', '', lines[i])
                items.append(_parse_inline(item_text))
                i += 1
            content.append(_adf_ordered_list(items))
            continue

        # Blockquote
        if line.startswith("> ") or line == ">":
            quote_lines = []
            while i < len(lines) and (lines[i].startswith("> ") or
                                       lines[i] == ">"):
                quote_lines.append(re.sub(r'^>\s?', '', lines[i]))
                i += 1
            quote_md = "\n".join(quote_lines)
            inner = markdown_to_adf(quote_md)
            content.append({
                "type": "blockquote",
                "content": inner.get("content", []),
            })
            continue

        # Table
        if re.match(r'^\|.+\|', line):
            table_rows = []
            while i < len(lines) and re.match(r'^\|.+\|', lines[i]):
                row_text = lines[i].strip()
                # Skip separator rows (| --- | --- |)
                if re.match(r'^\|[\s\-:|]+\|$', row_text):
                    i += 1
                    continue
                # Split cells, dropping empty first/last from leading/trailing |
                cells = row_text.split("|")
                cells = [c for c in cells[1:-1]]  # drop empty first/last
                table_rows.append(cells)
                i += 1
            if table_rows:
                content.append(_adf_table(table_rows, has_header=True))
            continue

        # Empty line — skip
        if not line.strip():
            i += 1
            continue

        # Paragraph — accumulate consecutive non-empty, non-special lines
        para_lines = []
        while i < len(lines) and lines[i].strip() and \
                not lines[i].startswith("#") and \
                not lines[i].startswith("```") and \
                not re.match(r'^[-*]\s', lines[i]) and \
                not re.match(r'^\d+\.\s', lines[i]) and \
                not re.match(r'^---+\s*$', lines[i]) and \
                not re.match(r'^\|.+\|', lines[i]):
            para_lines.append(lines[i])
            i += 1
        if para_lines:
            text = " ".join(para_lines)
            content.append(_adf_paragraph(_parse_inline(text)))

    return _adf_doc(content) if content else \
        _adf_doc([_adf_paragraph([_adf_text("")])])


def text_to_adf_paragraph(text):
    """Wrap text in a simple ADF paragraph — for short status comments."""
    return _adf_doc([_adf_paragraph([_adf_text(text)])])



