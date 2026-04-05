import os
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

class FileHandler:
    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text

    @staticmethod
    def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 100):
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        return splitter.split_text(text)
    