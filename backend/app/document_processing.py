import re
from pathlib import Path

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown"}


def extract_text(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Upload a PDF, DOCX, TXT, or Markdown document.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("File exceeds the 10 MB upload limit.")
    if not content:
        raise ValueError("The uploaded file is empty.")
    if extension in {".txt", ".md", ".markdown"}:
        text = content.decode("utf-8-sig", errors="replace")
    elif extension == ".pdf":
        import fitz
        with fitz.open(stream=content, filetype="pdf") as document:
            text = "\n".join(page.get_text() for page in document)
    else:
        from docx import Document
        from io import BytesIO
        document = Document(BytesIO(content))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    text = text.strip()
    if not text:
        raise ValueError("No readable text was found in the document.")
    return text[:200_000]


def extract_stories(text: str) -> list[dict]:
    lines = [re.sub(r"^\s*(?:[-*#]+\s*|\d+[.)]\s*)", "", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    stories: list[dict] = []
    current: list[str] = []

    def save():
        if not current:
            return
        body = " ".join(current).strip()
        if len(body) < 12:
            return
        match = re.search(r"\b(?:as a|as an)\s+([^,]+),\s*i want\s+(.+?)(?:,\s*so that\s+(.+))?$", body, re.I)
        title = (match.group(2) if match else body.split(".")[0]).strip().rstrip(".")
        stories.append({
            "id": f"ST-{len(stories) + 1:03d}",
            "title": title[:180] or "Requirement",
            "description": body,
            "acceptance_criteria": [],
            "priority": "Medium",
            "dependencies": [],
        })

    for line in lines:
        looks_like_story = bool(re.search(r"\b(as a|as an)\s+.+\bi want\b", line, re.I))
        is_heading = bool(re.match(r"(?:story\s*\d+|user story|requirement\s*\d+)\b", line, re.I))
        if current and (looks_like_story or is_heading):
            save()
            current = []
        current.append(line)
    save()
    if not stories and lines:
        for sentence in re.split(r"(?<=[.!?])\s+", " ".join(lines)):
            sentence = sentence.strip()
            if len(sentence) >= 20:
                stories.append({"id": f"ST-{len(stories) + 1:03d}", "title": sentence[:100], "description": sentence, "acceptance_criteria": [], "priority": "Medium", "dependencies": []})
    return stories[:100]
