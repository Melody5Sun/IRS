from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams

from app.resume.llm_resume_parser import LLMResumeParser
from app.schemas.resume import ParsedResume


def pdf_text(pdf) -> str:
    """PDF 转纯文本。boxes_flow=None 按版面从上到下逐行读：默认参数会把两栏简历右栏的日期整列挪到后面，
    硕士的起止日期被抽到项目标题下（见 lessons 2026-10-02）。pdf 可以是路径或二进制文件对象。"""
    return extract_text(pdf, laparams=LAParams(boxes_flow=None)).strip()


class ResumeParser:
    def __init__(self, llm_parser: LLMResumeParser | None = None) -> None:
        self.llm_parser = llm_parser or LLMResumeParser()

    def parse(self, text: str) -> ParsedResume:
        return self.llm_parser.parse(text)
