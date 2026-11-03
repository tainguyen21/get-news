"""Gemini calls: embeddings, importance scoring, and Vietnamese summaries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

import numpy as np
from google import genai
from google.genai import types

from get_news.models import Cluster

_EMBED_BATCH = 100

_SCORE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"},
                    "importance": {"type": "INTEGER"},
                    "category": {"type": "STRING", "enum": ["tech", "world", "skip"]},
                },
                "required": ["id", "importance", "category"],
            },
        }
    },
    "required": ["items"],
}

_SUMMARY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title_vi": {"type": "STRING"},
        "lead_vi": {"type": "STRING"},
        "points_vi": {"type": "ARRAY", "items": {"type": "STRING"}},
        "discrepancy_vi": {"type": "STRING"},
    },
    "required": ["title_vi", "lead_vi", "points_vi", "discrepancy_vi"],
}

_MATCH_SCHEMA = {"type": "OBJECT", "properties": {"match": {"type": "INTEGER"}}, "required": ["match"]}

_MATCH_INSTRUCTION = """Xác định bản tin cần xét có nói về CÙNG MỘT sự kiện cụ thể với ứng viên nào không.
Cùng một sự kiện là cùng một sự việc cụ thể: cùng hành động, cùng thông báo, cùng vụ việc, có thể do
các báo khác nhau đưa tin bằng ngôn ngữ khác nhau, hoặc là diễn biến, phản ứng trực tiếp của chính
sự việc đó. Chỉ cùng chủ đề, cùng công ty, cùng quốc gia hay cùng cuộc xung đột nhưng là sự việc khác
thì KHÔNG phải cùng sự kiện. Trả về match là số thứ tự của ứng viên trùng sự kiện, hoặc 0 nếu không có."""

_SUMMARY_INSTRUCTION = """Bạn là biên tập viên tin tức viết cho một người đọc Việt Nam.
Viết bản tóm tắt tiếng Việt cho MỘT sự kiện, chỉ dựa trên các văn bản nguồn được cung cấp.

- title_vi: tiêu đề tiếng Việt rõ ràng, trung lập, tối đa 110 ký tự.
- lead_vi: một câu nêu điều quan trọng nhất của sự kiện (ai, làm gì, khi nào, tác động).
- points_vi: liệt kê ĐẦY ĐỦ các ý chính của sự kiện, không bỏ sót ý quan trọng nào trong nguồn.
  Mỗi ý là một hoặc hai câu ngắn, không lặp lại câu dẫn. Giữ số liệu, tên riêng, thời điểm,
  phát biểu quan trọng, bối cảnh và hệ quả. Số ý tuỳ lượng thông tin, thường từ 4 đến 10.
- discrepancy_vi: nếu các nguồn mâu thuẫn nhau về số liệu hoặc diễn biến, nêu ngắn gọn điểm
  khác nhau; nếu không có mâu thuẫn, để chuỗi rỗng.

Quy tắc: không thêm thông tin không có trong nguồn, không suy đoán, không bình luận.
Chỉ ghi ngày cụ thể khi nguồn nêu rõ hoặc suy ra chắc chắn từ thời điểm hiện tại được cung cấp.
Giữ nguyên tên riêng nước ngoài; thuật ngữ công nghệ phổ biến có thể giữ tiếng Anh.
Tổng độ dài lead_vi, points_vi và discrepancy_vi không quá 2.800 ký tự."""


def _score_instruction(settings: SimpleNamespace) -> str:
    priorities = "\n".join(f"  {i}. {topic}" for i, topic in enumerate(settings.topic_priorities, 1))
    return f"""Bạn là biên tập viên chọn tin cho một bản tin cá nhân về công nghệ và thế giới.
Với mỗi sự kiện, chấm mức quan trọng (importance) từ 1 đến 10 với người đọc này và xếp mục:

Chủ đề ưu tiên, theo thứ tự:
{priorities}
Ưu tiên thấp: {settings.topic_low_priority}
Bỏ qua (category = "skip"): {settings.topic_skip}

Thang điểm:
- 9-10: sự kiện lớn tầm thế giới hoặc tầm cả ngành, ai theo dõi tin cũng cần biết ngay.
- 7-8: tin quan trọng trong các chủ đề ưu tiên.
- 4-6: đáng đọc nhưng không cấp bách.
- 1-3: tin nhỏ, quảng cáo, tin cũ hoặc ít giá trị.
Nhiều nguồn độc lập cùng đưa tin là dấu hiệu quan trọng, nhưng không phải điều kiện bắt buộc.

category: "tech" cho công nghệ, khoa học, AI, phần mềm, thiết bị, doanh nghiệp công nghệ;
"world" cho thế giới, chính trị, xung đột, thiên tai, kinh tế vĩ mô và thời sự lớn của Việt Nam;
"skip" cho tin thuộc nhóm bỏ qua. Trả về đúng mọi id được đưa vào."""


@dataclass
class Summary:
    title: str
    lead: str
    points: list[str]
    discrepancy: str


@dataclass
class Material:
    """Source text gathered for one event before summarising."""

    texts: list[tuple[str, str, str, str]]  # (source name, url, title, text)
    headlines: list[str]
    image: str | None

    @property
    def fulltext_chars(self) -> int:
        return sum(len(text) for *_, text in self.texts)


class Gemini:
    def __init__(self, client: genai.Client, settings: SimpleNamespace):
        self.client = client
        self.settings = settings
        self.models = settings.models

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = []
        for start in range(0, len(texts), _EMBED_BATCH):
            response = self.client.models.embed_content(
                model=self.models.embedding,
                contents=texts[start : start + _EMBED_BATCH],
                # No task type: measured on real pairs, it separates events better than
                # CLUSTERING or SEMANTIC_SIMILARITY.
                config=types.EmbedContentConfig(output_dimensionality=self.models.embedding_dims),
            )
            vectors.extend(e.values for e in response.embeddings)
        matrix = np.asarray(vectors, dtype=np.float32)
        return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)

    def score(self, clusters: list[Cluster], now: datetime) -> dict[str, tuple[int, str]]:
        """One batch call; returns cluster id -> (importance, category)."""
        if not clusters:
            return {}
        briefs = [
            {
                "id": c.id,
                "headlines": list(dict.fromkeys(a.title for a in c.articles))[:6],
                "snippets": [a.snippet[:200] for a in c.articles if a.snippet][:3],
                "independent_publishers": len(c.publishers()),
                "hacker_news_points": c.hn_points or None,
                "hours_since_first_report": round((now - min(a.published_at for a in c.articles)).total_seconds() / 3600, 1),
            }
            for c in clusters
        ]
        response = self.client.models.generate_content(
            model=self.models.scoring,
            contents=json.dumps(briefs, ensure_ascii=False),
            config=types.GenerateContentConfig(
                system_instruction=_score_instruction(self.settings),
                response_mime_type="application/json",
                response_schema=_SCORE_SCHEMA,
                temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
            ),
        )
        known = {c.id for c in clusters}
        result = {}
        for item in json.loads(response.text)["items"]:
            if item["id"] in known:
                result[item["id"]] = (max(1, min(10, int(item["importance"]))), item["category"])
        return result

    def same_event(self, subject: list[str], candidates: list[list[str]]) -> int | None:
        """Index of the candidate describing the same specific event as `subject`, or None."""
        lines = ["Bản tin cần xét:", *(f"- {s}" for s in subject), "", "Ứng viên:"]
        for number, headlines in enumerate(candidates, 1):
            lines.append(f"{number}.")
            lines.extend(f"   - {h}" for h in headlines)
        response = self.client.models.generate_content(
            model=self.models.scoring,
            contents="\n".join(lines),
            config=types.GenerateContentConfig(
                system_instruction=_MATCH_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=_MATCH_SCHEMA,
                temperature=0,
                thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
            ),
        )
        match = int(json.loads(response.text)["match"])
        return match - 1 if 1 <= match <= len(candidates) else None

    def summarize(self, material: Material, local_now: datetime) -> Summary:
        # The current date lets the model resolve "today" or "Tuesday" in sources correctly.
        parts = [f"Thời điểm hiện tại: {local_now:%H:%M ngày %d/%m/%Y} (giờ Việt Nam)."]
        for index, (name, url, title, text) in enumerate(material.texts, 1):
            parts.append(f"### Nguồn {index}: {name} ({url})\nTiêu đề: {title}\n\n{text}")
        if material.headlines:
            parts.append("### Tiêu đề và mô tả từ các nguồn khác\n" + "\n".join(f"- {h}" for h in material.headlines))
        response = self.client.models.generate_content(
            model=self.models.summary,
            contents="\n\n".join(parts),
            config=types.GenerateContentConfig(
                system_instruction=_SUMMARY_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=_SUMMARY_SCHEMA,
                temperature=0.3,
                thinking_config=types.ThinkingConfig(thinking_level="LOW"),
            ),
        )
        data = json.loads(response.text)
        return Summary(
            title=data["title_vi"].strip(),
            lead=data["lead_vi"].strip(),
            points=[p.strip() for p in data["points_vi"] if p.strip()],
            discrepancy=data["discrepancy_vi"].strip(),
        )
