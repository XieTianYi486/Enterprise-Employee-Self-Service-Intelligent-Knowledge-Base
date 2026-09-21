# ============================================================
# 语义分块器（结构感知）
# 不采用简单固定长度切分，而是基于文档结构进行智能分块
# 与旧项目的 RecursiveCharacterTextSplitter 方式区分开
# ============================================================

import re
from typing import List, Dict, Optional

from app.core.config import settings


class SemanticChunker:
    """
    结构感知的语义分块器

    策略：
    1. 优先按标题层级（一级标题 > 二级标题 > 三级标题）切分
    2. 在标题内部，按段落边界切分
    3. 过长的段落按句子边界进一步切分
    4. 每个 chunk 附加章节、页码等元数据
    5. chunk 之间保留 overlap（重叠上下文）
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        # 中文/英文句子分隔正则
        self.sentence_sep = re.compile(
            r'(?<=[。！？.!?\n])\s*'
        )

    def chunk_text(
        self,
        text: str,
        title: str = "",
        page_start: int = 1,
        page_end: Optional[int] = None,
    ) -> List[Dict]:
        """
        对文档文本进行分块

        参数:
            text: 文档全文
            title: 文档标题
            page_start: 起始页码
            page_end: 结束页码（可选，单页文档不需要）

        返回:
            chunk 列表，每个 chunk 包含：
            - content: 文本内容
            - chapter: 所属章节
            - page: 页码
            - token_count: 估算 token 数
        """
        if not text or not text.strip():
            return []

        # 第一步：提取文档结构（标题层级）
        sections = self._extract_sections(text)

        chunks = []
        chunk_index = 0

        for section in sections:
            section_title = section["title"]
            section_text = section["content"]
            section_page = section.get("page", page_start)

            # 第二步：按段落切分
            paragraphs = self._split_paragraphs(section_text)

            current_chunk = ""
            current_token_count = 0

            for para in paragraphs:
                para_tokens = self._estimate_tokens(para)

                # 如果当前 chunk + 新段落超出限制，则保存当前 chunk
                if current_chunk and (
                    current_token_count + para_tokens > self.chunk_size
                ):
                    chunks.append({
                        "content": current_chunk.strip(),
                        "chapter": self._clean_title(section_title, title),
                        "page": section_page,
                        "token_count": current_token_count,
                    })
                    chunk_index += 1

                    # 保留 overlap：取最后一段作为下个 chunk 的上下文
                    overlap_text = self._get_overlap(current_chunk)
                    current_chunk = overlap_text
                    current_token_count = self._estimate_tokens(overlap_text)

                # 过长的单个段落按句子切分
                if para_tokens > self.chunk_size:
                    sub_chunks = self._split_long_paragraph(
                        para, current_chunk, current_token_count,
                        section_title, title, section_page
                    )
                    chunks.extend(sub_chunks)
                    chunk_index += len(sub_chunks)
                    current_chunk = ""
                    current_token_count = 0
                else:
                    current_chunk += para + "\n"
                    current_token_count += para_tokens

            # 保存最后一个 chunk
            if current_chunk.strip():
                chunks.append({
                    "content": current_chunk.strip(),
                    "chapter": self._clean_title(section_title, title),
                    "page": section_page,
                    "token_count": current_token_count,
                })

        # 小文档处理：如果最终只有一个 chunk 且小于 chunk_size/2，直接返回
        return chunks

    def _extract_sections(self, text: str) -> List[Dict]:
        """
        提取文档的章节结构
        识别 Markdown 标题（# ## ###）和纯文本标题模式
        """
        sections = []
        # 匹配 Markdown 标题和中文章节标题（不匹配"第X条"防止过度切分）
        heading_pattern = re.compile(
            r'^(#{1,3})\s+(.+)$|'
            r'^(第[一二三四五六七八九十\d]+[章节])\s*(.*)$',
            re.MULTILINE
        )

        # 找到所有标题的位置
        headings = list(heading_pattern.finditer(text))

        if not headings:
            # 没有识别到标题，整篇作为一个 section
            sections.append({"title": "", "content": text, "page": 1})
            return sections

        # 第一个标题之前的内容（如有）
        if headings[0].start() > 0:
            preamble = text[:headings[0].start()].strip()
            if preamble:
                sections.append({"title": "", "content": preamble, "page": 1})

        # 按标题切分
        for i, match in enumerate(headings):
            # 提取标题文本
            title = match.group(2) or match.group(4) or match.group(6) or ""
            title = title.strip()

            # 提取内容（当前标题到下一个标题之间）
            content_start = match.end()
            content_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            content = text[content_start:content_end].strip()

            # 估算页码（按每页约 1500 字符估算）
            char_position = match.start()
            estimated_page = max(1, char_position // 1500 + 1)

            sections.append({
                "title": title,
                "content": content,
                "page": estimated_page,
            })

        return sections

    def _split_paragraphs(self, text: str) -> List[str]:
        """按段落切分（双换行）"""
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]

    def _split_long_paragraph(
        self, paragraph: str, prefix: str, prefix_tokens: int,
        section_title: str, doc_title: str, page: int,
    ) -> List[Dict]:
        """对过长的段落按句子切分"""
        sentences = self.sentence_sep.split(paragraph)
        chunks = []
        current = prefix
        current_tokens = prefix_tokens

        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            sent_tokens = self._estimate_tokens(sent)

            if current_tokens + sent_tokens > self.chunk_size and current.strip():
                chunks.append({
                    "content": current.strip(),
                    "chapter": self._clean_title(section_title, doc_title),
                    "page": page,
                    "token_count": current_tokens,
                })
                current = sent + " "
                current_tokens = sent_tokens
            else:
                current += sent + " "
                current_tokens += sent_tokens

        if current.strip():
            chunks.append({
                "content": current.strip(),
                "chapter": self._clean_title(section_title, doc_title),
                "page": page,
                "token_count": current_tokens,
            })

        return chunks

    def _get_overlap(self, text: str) -> str:
        """取文本末尾部分作为 overlap 上下文"""
        # 取最后约 chunk_overlap 个 token（简单估算：4 字符 ≈ 1 token）
        overlap_chars = self.chunk_overlap * 4
        if len(text) <= overlap_chars:
            return text + "\n"
        return text[-overlap_chars:] + "\n"

    def _estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数量
        简单估算：中文约 2 字符/token，英文约 4 字符/token
        """
        if not text:
            return 0
        # 混合估算：取折中 3 字符/token
        return max(1, len(text) // 3)

    def _clean_title(self, section_title: str, doc_title: str) -> str:
        """生成干净的章节标识"""
        if section_title:
            return section_title
        return doc_title


# --- 默认分块器实例 ---
_default_chunker = SemanticChunker(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,
)


def get_chunker() -> SemanticChunker:
    """获取默认分块器"""
    return _default_chunker
