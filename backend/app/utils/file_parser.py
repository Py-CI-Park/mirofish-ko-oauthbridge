"""
파일 파서 유틸리티
PDF, Markdown, TXT 파일에서 텍스트를 추출한다.
"""

import os
from pathlib import Path
from typing import List, Optional


def _read_text_with_fallback(file_path: str) -> str:
    """
    텍스트 파일을 읽고, UTF-8 실패 시 인코딩을 자동 추정한다.
    
    다단계 fallback 전략:
    1. 먼저 UTF-8 디코딩 시도
    2. charset_normalizer로 인코딩 탐지
    3. chardet으로 재시도
    4. 마지막으로 UTF-8 + errors='replace' 사용
    
    Args:
        file_path: 파일 경로
        
    Returns:
        디코딩된 텍스트 내용
    """
    data = Path(file_path).read_bytes()
    
    # 먼저 UTF-8 시도
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        pass
    
    # charset_normalizer로 인코딩 탐지 시도
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass
    
    # chardet으로 fallback
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass
    
    # 최종 fallback: UTF-8 + replace
    if not encoding:
        encoding = 'utf-8'
    
    return data.decode(encoding, errors='replace')


class FileParser:
    """파일 파서"""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt'}
    
    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
        파일에서 텍스트를 추출한다.
        
        Args:
            file_path: 파일 경로
            
        Returns:
            추출된 텍스트 내용
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"파일이 없습니다: {file_path}")
        
        suffix = path.suffix.lower()
        
        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"지원하지 않는 파일 형식입니다: {suffix}")
        
        if suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        elif suffix == '.txt':
            return cls._extract_from_txt(file_path)
        
        raise ValueError(f"처리할 수 없는 파일 형식입니다: {suffix}")
    
    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """PDF에서 텍스트를 추출한다."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("PyMuPDF가 필요합니다: pip install PyMuPDF")
        
        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
        
        return "\n\n".join(text_parts)
    
    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        """Markdown에서 텍스트를 추출한다. 자동 인코딩 탐지 지원."""
        return _read_text_with_fallback(file_path)
    
    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        """TXT에서 텍스트를 추출한다. 자동 인코딩 탐지 지원."""
        return _read_text_with_fallback(file_path)
    
    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        """
        여러 파일에서 텍스트를 추출해 합친다.
        
        Args:
            file_paths: 파일 경로 목록
            
        Returns:
            합쳐진 텍스트
        """
        all_texts = []
        
        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"=== 문서 {i}: {filename} ===\n{text}")
            except Exception as e:
                all_texts.append(f"=== 문서 {i}: {file_path} (추출 실패: {str(e)}) ===")
        
        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str, 
    chunk_size: int = 500, 
    overlap: int = 50
) -> List[str]:
    """
    텍스트를 작은 청크로 분할한다.
    
    Args:
        text: 원본 텍스트
        chunk_size: 각 청크의 문자 수
        overlap: 중첩 문자 수
        
    Returns:
        텍스트 청크 목록
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # 가능한 경우 문장 경계에서 분할 시도
        if end < len(text):
            # 가장 가까운 문장 종료 기호 탐색
            for sep in ['。', '！', '？', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # 다음 청크는 overlap 위치부터 시작
        start = end - overlap if end < len(text) else len(text)
    
    return chunks

