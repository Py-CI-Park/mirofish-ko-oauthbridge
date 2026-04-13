"""
텍스트 처리 서비스
"""

from typing import List, Optional
from ..utils.file_parser import FileParser, split_text_into_chunks


class TextProcessor:
    """텍스트 처리기"""
    
    @staticmethod
    def extract_from_files(file_paths: List[str]) -> str:
        """여러 파일에서 텍스트를 추출한다."""
        return FileParser.extract_from_multiple(file_paths)
    
    @staticmethod
    def split_text(
        text: str,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> List[str]:
        """
        텍스트를 분할한다.
        
        Args:
            text: 원본 텍스트
            chunk_size: 청크 크기
            overlap: 중첩 크기
            
        Returns:
            텍스트 청크 목록
        """
        return split_text_into_chunks(text, chunk_size, overlap)
    
    @staticmethod
    def preprocess_text(text: str) -> str:
        """
        텍스트를 전처리한다.
        - 불필요한 공백 제거
        - 줄바꿈 정규화
        
        Args:
            text: 원본 텍스트
            
        Returns:
            전처리된 텍스트
        """
        import re
        
        # 줄바꿈 정규화
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # 연속된 빈 줄 제거 (최대 두 줄까지만 유지)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 각 줄의 앞뒤 공백 제거
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        return text.strip()
    
    @staticmethod
    def get_text_stats(text: str) -> dict:
        """텍스트 통계 정보를 반환한다."""
        return {
            "total_chars": len(text),
            "total_lines": text.count('\n') + 1,
            "total_words": len(text.split()),
        }

