"""
MiroFish Backend - Flask app factory
"""

import os
import warnings
import urllib.request
from urllib.parse import urlparse

# multiprocessing resource_tracker 경고를 숨긴다
# (예: transformers 같은 서드파티 라이브러리에서 발생)
# 다른 import보다 먼저 설정해야 한다.
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flask 앱 팩토리 함수."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # JSON 인코딩 설정:
    # 한글/유니코드가 \uXXXX 형태로 이스케이프되지 않도록 한다.
    # Flask >= 2.3 은 app.json.ensure_ascii, 구버전은 JSON_AS_ASCII를 사용한다.
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # 로거 설정
    logger = setup_logger('mirofish')
    
    # debug reloader 환경에서 시작 로그가 두 번 찍히지 않도록
    # 실제 하위 프로세스에서만 시작 메시지를 남긴다.
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend 시작 중...")
        logger.info("=" * 50)
    
    # CORS 활성화
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # 서버 종료 시 시뮬레이션 프로세스를 정리하도록 훅을 등록한다.
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("시뮬레이션 프로세스 정리 훅을 등록했습니다")
    
    # 요청/응답 로그 미들웨어
    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"요청: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"요청 본문: {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"응답: {response.status_code}")
        return response
    
    # 블루프린트 등록
    from .api import graph_bp, simulation_bp, report_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    
    # 헬스체크
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend'}

    @app.route('/api/system/bridge-health')
    def bridge_health():
        base_url = app.config.get('LLM_BASE_URL') or ''
        if not base_url:
            return {'ok': False, 'error': 'LLM_BASE_URL is not configured'}, 500

        parsed = urlparse(base_url)
        if parsed.scheme not in {'http', 'https'}:
            return {'ok': False, 'error': f'Unsupported LLM_BASE_URL: {base_url}'}, 400

        bridge_base = base_url[:-3] if base_url.endswith('/v1') else base_url.rstrip('/')
        health_url = f'{bridge_base}/health'

        try:
            with urllib.request.urlopen(health_url, timeout=3) as response:
                import json
                payload = json.loads(response.read().decode('utf-8'))
                return payload
        except Exception as e:
            return {
                'ok': False,
                'busy': None,
                'queueDepth': None,
                'error': f'Failed to reach bridge health endpoint: {e}',
                'healthUrl': health_url,
            }, 502
    
    if should_log_startup:
        logger.info("MiroFish Backend 시작 완료")
    
    return app
