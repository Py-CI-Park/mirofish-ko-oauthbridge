"""
설정 관리
프로젝트 루트의 .env / .env.local 값을 우선해서 불러온다.
"""

import os
from dotenv import dotenv_values, load_dotenv

# 프로젝트 루트의 환경변수 파일을 불러온다.
# 경로: repo/.env, repo/.env.local (backend/app/config.py 기준 상대 경로)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
project_root_env = os.path.join(project_root, '.env')
project_root_env_local = os.path.join(project_root, '.env.local')
runtime_env_keys = set(os.environ.keys())

if os.path.exists(project_root_env):
    for key, value in dotenv_values(project_root_env).items():
        if value is not None and key not in runtime_env_keys:
            os.environ[key] = value

if os.path.exists(project_root_env_local):
    for key, value in dotenv_values(project_root_env_local).items():
        if value is not None and key not in runtime_env_keys:
            os.environ[key] = value

if not os.path.exists(project_root_env) and not os.path.exists(project_root_env_local):
    # 루트에 .env / .env.local 이 없으면 환경변수만 로드한다. (운영 환경용)
    load_dotenv(override=True)


class Config:
    """Flask 설정 클래스"""
    
    # Flask 설정
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON 설정 - ASCII 이스케이프를 끄고 유니코드를 그대로 출력한다.
    JSON_AS_ASCII = False
    
    # LLM 설정 (OpenAI 호환 형식 통일)
    LLM_API_KEY = os.environ.get('LLM_API_KEY', 'local-oauth-bridge')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'http://127.0.0.1:8787/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-5.4-mini')
    LLM_PROMPT_LANGUAGE = os.environ.get('LLM_PROMPT_LANGUAGE', 'legacy')
    LLM_OUTPUT_LANGUAGE = os.environ.get('LLM_OUTPUT_LANGUAGE', 'ko')
    
    # Zep 설정
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')
    
    # 파일 업로드 설정
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # 텍스트 처리 설정
    DEFAULT_CHUNK_SIZE = 500  # 기본 청크 크기
    DEFAULT_CHUNK_OVERLAP = 50  # 기본 중첩 크기
    
    # OASIS 시뮬레이션 설정
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS 플랫폼별 사용 가능 액션 설정
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent 설정
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls):
        """필수 설정값을 검증한다."""
        errors = []
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY가 설정되지 않았습니다")
        return errors
