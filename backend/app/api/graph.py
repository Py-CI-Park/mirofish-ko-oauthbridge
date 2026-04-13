"""
그래프 관련 API 라우트
프로젝트 컨텍스트를 사용하며, 서버 측에서 상태를 영속화한다.
"""

import os
import traceback
import threading
from datetime import datetime
from flask import request, jsonify

from . import graph_bp
from ..config import Config
from ..services.ontology_generator import OntologyGenerator
from ..services.graph_builder import GraphBuilderService, OntologyApplyError
from ..services.text_processor import TextProcessor
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger
from ..models.task import TaskManager, TaskStatus
from ..models.project import ProjectManager, ProjectStatus

# 로거 준비
logger = get_logger('mirofish.api')


def try_recover_graph_building_project(project):
    """
    Recover stale graph_building projects when the in-memory task was lost
    (for example after a backend restart / debug reloader issue) but the graph
    already exists in Zep and has data.
    """
    try:
        if project.status != ProjectStatus.GRAPH_BUILDING:
            return project

        if not project.graph_id:
            return project

        task_id = project.graph_build_task_id
        task_exists = bool(task_id and TaskManager().get_task(task_id))
        if task_exists:
            return project

        try:
            updated_at = datetime.fromisoformat(project.updated_at)
        except Exception:
            return project

        recovery_after_seconds = int(os.environ.get('GRAPH_STUCK_RECOVERY_SECONDS', '600'))
        age_seconds = (datetime.now() - updated_at).total_seconds()
        if age_seconds < recovery_after_seconds:
            return project

        if not Config.ZEP_API_KEY:
            return project

        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        graph_data = builder.get_graph_data(project.graph_id)
        node_count = graph_data.get("node_count", 0) or len(graph_data.get("nodes", []) or [])
        edge_count = graph_data.get("edge_count", 0) or len(graph_data.get("edges", []) or [])

        if node_count > 0 or edge_count > 0:
            logger.warning(
                f"Recovering stale graph_building project {project.project_id}: "
                f"task_id={task_id} missing, age={age_seconds:.0f}s, "
                f"nodes={node_count}, edges={edge_count}"
            )
            project.status = ProjectStatus.GRAPH_COMPLETED
            project.graph_build_task_id = None
            project.error = None
            ProjectManager.save_project(project)

    except Exception as e:
        logger.warning(f"Failed to recover stale project {project.project_id}: {e}")

    return project


def allowed_file(filename: str) -> bool:
    """허용된 파일 확장자인지 확인한다."""
    if not filename or '.' not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext in Config.ALLOWED_EXTENSIONS


# ============== 프로젝트 관리 인터페이스 ==============

@graph_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id: str):
    """
    프로젝트 상세 정보를 조회한다.
    """
    project = ProjectManager.get_project(project_id)
    
    if not project:
        return jsonify({
            "success": False,
            "error": f"프로젝트가 없습니다: {project_id}"
        }), 404
    
    project = try_recover_graph_building_project(project)

    return jsonify({
        "success": True,
        "data": project.to_dict()
    })


@graph_bp.route('/project/<project_id>/inputs', methods=['GET'])
def get_project_inputs(project_id: str):
    """
    Return the original simulation prompt and uploaded source-file contents
    so publishing pipelines can expose the original cues on the public dashboard.
    """
    project = ProjectManager.get_project(project_id)

    if not project:
        return jsonify({
            "success": False,
            "error": f"프로젝트가 없습니다: {project_id}"
        }), 404

    saved_paths = sorted(ProjectManager.get_project_files(project_id), key=os.path.getmtime)
    files = []

    for index, meta in enumerate(project.files or []):
        path = saved_paths[index] if index < len(saved_paths) else None
        saved_filename = os.path.basename(path) if path else None
        content = ""

        if path and os.path.exists(path):
            try:
                content = FileParser.extract_text(path) or ""
            except Exception as exc:
                logger.warning(f"Failed to extract project input text: project={project_id}, file={path}, error={exc}")

        files.append({
            "filename": meta.get("filename") or saved_filename or f"file-{index + 1}",
            "saved_filename": saved_filename,
            "size": meta.get("size", 0),
            "content": content,
        })

    return jsonify({
        "success": True,
        "data": {
            "project_id": project.project_id,
            "simulation_requirement": project.simulation_requirement or "",
            "combined_extracted_text": ProjectManager.get_extracted_text(project_id) or "",
            "files": files,
        }
    })


@graph_bp.route('/project/list', methods=['GET'])
def list_projects():
    """
    전체 프로젝트 목록을 조회한다.
    """
    limit = request.args.get('limit', 50, type=int)
    projects = [try_recover_graph_building_project(p) for p in ProjectManager.list_projects(limit=limit)]
    
    return jsonify({
        "success": True,
        "data": [p.to_dict() for p in projects],
        "count": len(projects)
    })


@graph_bp.route('/project/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    """
    프로젝트를 삭제한다.
    """
    success = ProjectManager.delete_project(project_id)
    
    if not success:
        return jsonify({
            "success": False,
            "error": f"프로젝트가 없거나 삭제에 실패했습니다: {project_id}"
        }), 404
    
    return jsonify({
        "success": True,
        "message": f"프로젝트를 삭제했습니다: {project_id}"
    })


@graph_bp.route('/project/<project_id>/reset', methods=['POST'])
def reset_project(project_id: str):
    """
    프로젝트 상태를 재설정한다. (그래프 재구축용)
    """
    project = ProjectManager.get_project(project_id)
    
    if not project:
        return jsonify({
            "success": False,
            "error": f"프로젝트가 없습니다: {project_id}"
        }), 404
    
    # 온톨로지 생성 완료 상태로 되돌린다.
    if project.ontology:
        project.status = ProjectStatus.ONTOLOGY_GENERATED
    else:
        project.status = ProjectStatus.CREATED
    
    project.graph_id = None
    project.graph_build_task_id = None
    project.error = None
    ProjectManager.save_project(project)
    
    return jsonify({
        "success": True,
        "message": f"프로젝트를 재설정했습니다: {project_id}",
        "data": project.to_dict()
    })


# ============== 인터페이스 1: 파일 업로드 및 온톨로지 생성 ==============

@graph_bp.route('/ontology/generate', methods=['POST'])
def generate_ontology():
    """
    인터페이스 1: 업로드된 파일을 분석해 온톨로지 정의를 생성한다.
    
    요청 형식: multipart/form-data
    
    파라미터:
        files: 업로드 파일(PDF/MD/TXT), 여러 개 가능
        simulation_requirement: 시뮬레이션 요구사항 설명(필수)
        project_name: 프로젝트 이름(선택)
        additional_context: 추가 설명(선택)
        
    반환:
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "ontology": {
                    "entity_types": [...],
                    "edge_types": [...],
                    "analysis_summary": "..."
                },
                "files": [...],
                "total_text_length": 12345
            }
        }
    """
    try:
        logger.info("=== 온톨로지 정의 생성 시작 ===")
        
        # 파라미터 수집
        simulation_requirement = request.form.get('simulation_requirement', '')
        project_name = request.form.get('project_name', 'Unnamed Project')
        additional_context = request.form.get('additional_context', '')
        
        logger.debug(f"프로젝트 이름: {project_name}")
        logger.debug(f"시뮬레이션 요구사항: {simulation_requirement[:100]}...")
        
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": "시뮬레이션 요구사항 설명(simulation_requirement)을 입력해 주세요"
            }), 400
        
        # 업로드 파일 조회
        uploaded_files = request.files.getlist('files')
        if not uploaded_files or all(not f.filename for f in uploaded_files):
            return jsonify({
                "success": False,
                "error": "문서 파일을 하나 이상 업로드해 주세요"
            }), 400
        
        # 프로젝트 생성
        project = ProjectManager.create_project(name=project_name)
        project.simulation_requirement = simulation_requirement
        logger.info(f"프로젝트 생성: {project.project_id}")
        
        # 파일 저장 및 텍스트 추출
        document_texts = []
        all_text = ""
        
        for file in uploaded_files:
            if file and file.filename and allowed_file(file.filename):
                # 파일을 프로젝트 디렉터리에 저장
                file_info = ProjectManager.save_file_to_project(
                    project.project_id, 
                    file, 
                    file.filename
                )
                project.files.append({
                    "filename": file_info["original_filename"],
                    "size": file_info["size"]
                })
                
                # 텍스트 추출
                text = FileParser.extract_text(file_info["path"])
                text = TextProcessor.preprocess_text(text)
                document_texts.append(text)
                all_text += f"\n\n=== {file_info['original_filename']} ===\n{text}"
        
        if not document_texts:
            ProjectManager.delete_project(project.project_id)
            return jsonify({
                "success": False,
                "error": "처리된 문서가 없습니다. 파일 형식을 확인해 주세요"
            }), 400
        
        # 추출한 텍스트 저장
        project.total_text_length = len(all_text)
        ProjectManager.save_extracted_text(project.project_id, all_text)
        logger.info(f"텍스트 추출 완료: 총 {len(all_text)}자")
        
        # 온톨로지 생성
        logger.info("LLM으로 온톨로지 정의 생성 중...")
        generator = OntologyGenerator()
        ontology = generator.generate(
            document_texts=document_texts,
            simulation_requirement=simulation_requirement,
            additional_context=additional_context if additional_context else None
        )
        
        # 생성한 온톨로지를 프로젝트에 저장
        entity_count = len(ontology.get("entity_types", []))
        edge_count = len(ontology.get("edge_types", []))
        logger.info(f"온톨로지 생성 완료: 엔티티 유형 {entity_count}개, 관계 유형 {edge_count}개")
        
        project.ontology = {
            "entity_types": ontology.get("entity_types", []),
            "edge_types": ontology.get("edge_types", [])
        }
        project.analysis_summary = ontology.get("analysis_summary", "")
        project.status = ProjectStatus.ONTOLOGY_GENERATED
        ProjectManager.save_project(project)
        logger.info(f"=== 온톨로지 정의 생성 완료 === 프로젝트 ID: {project.project_id}")
        
        return jsonify({
            "success": True,
            "data": {
                "project_id": project.project_id,
                "project_name": project.name,
                "ontology": project.ontology,
                "analysis_summary": project.analysis_summary,
                "files": project.files,
                "total_text_length": project.total_text_length
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 인터페이스 2: 그래프 구축 ==============

@graph_bp.route('/build', methods=['POST'])
def build_graph():
    """
    인터페이스 2: project_id 기준으로 그래프를 구축한다.
    
    요청(JSON):
        {
            "project_id": "proj_xxxx",  // 필수, 인터페이스 1에서 생성
            "graph_name": "그래프 이름", // 선택
            "chunk_size": 500,          // 선택, 기본값 500
            "chunk_overlap": 50         // 선택, 기본값 50
        }
        
    반환:
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "task_id": "task_xxxx",
                "message": "그래프 구축 작업을 시작했습니다"
            }
        }
    """
    try:
        logger.info("=== 그래프 구축 시작 ===")
        
        # 설정 확인
        errors = []
        if not Config.ZEP_API_KEY:
            errors.append("ZEP_API_KEY가 설정되지 않았습니다")
        if errors:
            logger.error(f"설정 오류: {errors}")
            return jsonify({
                "success": False,
                "error": "설정 오류: " + "; ".join(errors)
            }), 500
        
        # 요청 파싱
        data = request.get_json() or {}
        project_id = data.get('project_id')
        logger.debug(f"요청 파라미터: project_id={project_id}")
        
        if not project_id:
            return jsonify({
                "success": False,
                "error": "project_id를 입력해 주세요"
            }), 400
        
        # 프로젝트 조회
        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"프로젝트가 없습니다: {project_id}"
            }), 404
        
        # 프로젝트 상태 확인
        force = data.get('force', False)  # 강제 재구축
        
        if project.status == ProjectStatus.CREATED:
            return jsonify({
                "success": False,
                "error": "프로젝트 온톨로지가 아직 생성되지 않았습니다. 먼저 /ontology/generate를 호출해 주세요"
            }), 400
        
        if project.status == ProjectStatus.GRAPH_BUILDING and not force:
            return jsonify({
                "success": False,
                "error": "그래프를 구축 중입니다. 중복 요청하지 마세요. 강제 재구축이 필요하면 force: true를 추가하세요",
                "task_id": project.graph_build_task_id
            }), 400
        
        # 강제 재구축이면 상태를 되돌린다.
        if force and project.status in [ProjectStatus.GRAPH_BUILDING, ProjectStatus.FAILED, ProjectStatus.GRAPH_COMPLETED]:
            project.status = ProjectStatus.ONTOLOGY_GENERATED
            project.graph_id = None
            project.graph_build_task_id = None
            project.error = None
        
        # 설정값 조회
        graph_name = data.get('graph_name', project.name or 'MiroFish Graph')
        chunk_size = data.get('chunk_size', project.chunk_size or Config.DEFAULT_CHUNK_SIZE)
        chunk_overlap = data.get('chunk_overlap', project.chunk_overlap or Config.DEFAULT_CHUNK_OVERLAP)
        
        # 프로젝트 설정값 갱신
        project.chunk_size = chunk_size
        project.chunk_overlap = chunk_overlap
        
        # 추출 텍스트 조회
        text = ProjectManager.get_extracted_text(project_id)
        if not text:
            return jsonify({
                "success": False,
                "error": "추출된 텍스트를 찾을 수 없습니다"
            }), 400
        
        # 온톨로지 조회
        ontology = project.ontology
        if not ontology:
            return jsonify({
                "success": False,
                "error": "온톨로지 정의를 찾을 수 없습니다"
            }), 400
        
        # 비동기 작업 생성
        task_manager = TaskManager()
        task_id = task_manager.create_task(f"그래프 구축: {graph_name}")
        logger.info(f"그래프 구축 작업 생성: task_id={task_id}, project_id={project_id}")
        
        # 프로젝트 상태 갱신
        project.status = ProjectStatus.GRAPH_BUILDING
        project.graph_build_task_id = task_id
        ProjectManager.save_project(project)
        
        # 백그라운드 작업 시작
        def build_task():
            build_logger = get_logger('mirofish.build')
            graph_id = None
            try:
                build_logger.info(f"[{task_id}] 그래프 구축 시작...")
                task_manager.update_task(
                    task_id, 
                    status=TaskStatus.PROCESSING,
                    message="그래프 구축 서비스를 초기화하는 중..."
                )
                
                # 그래프 구축 서비스 생성
                builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
                
                # 텍스트 분할
                task_manager.update_task(
                    task_id,
                    message="텍스트를 분할하는 중...",
                    progress=5
                )
                chunks = TextProcessor.split_text(
                    text, 
                    chunk_size=chunk_size, 
                    overlap=chunk_overlap
                )
                total_chunks = len(chunks)
                
                # 그래프 생성
                task_manager.update_task(
                    task_id,
                    message="Zep 그래프를 생성하는 중...",
                    progress=10
                )
                graph_id = builder.create_graph(name=graph_name)
                
                # 프로젝트 graph_id 갱신
                project.graph_id = graph_id
                ProjectManager.save_project(project)
                
                # 온톨로지 적용
                task_manager.update_task(
                    task_id,
                    message="Validating and applying ontology...",
                    progress=15
                )
                try:
                    builder.apply_ontology_with_cleanup(graph_id, ontology)
                except OntologyApplyError as exc:
                    build_logger.error(
                        f"[{task_id}] Ontology validation/apply failed for graph_id={graph_id}: {exc}"
                    )
                    build_logger.debug(traceback.format_exc())

                    if exc.cleanup_succeeded:
                        build_logger.info(
                            f"[{task_id}] Graph cleanup after ontology failure succeeded: graph_id={graph_id}"
                        )
                        project.graph_id = None
                        ProjectManager.save_project(project)

                    raise
                
                # 텍스트 추가 (progress_callback 시그니처: (msg, progress_ratio))
                def add_progress_callback(msg, progress_ratio):
                    progress = 15 + int(progress_ratio * 40)  # 15% - 55%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )
                
                task_manager.update_task(
                    task_id,
                    message=f"텍스트 청크 {total_chunks}개를 추가하는 중...",
                    progress=15
                )
                
                episode_uuids = builder.add_text_batches(
                    graph_id, 
                    chunks,
                    batch_size=3,
                    progress_callback=add_progress_callback
                )
                
                # Zep 처리 완료까지 대기 (각 episode의 processed 상태 조회)
                task_manager.update_task(
                    task_id,
                    message="Zep 데이터 처리를 기다리는 중...",
                    progress=55
                )
                
                def wait_progress_callback(msg, progress_ratio):
                    progress = 55 + int(progress_ratio * 35)  # 55% - 90%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )
                
                builder._wait_for_episodes(episode_uuids, wait_progress_callback)
                
                # 그래프 데이터 조회
                task_manager.update_task(
                    task_id,
                    message="그래프 데이터를 가져오는 중...",
                    progress=95
                )
                graph_data = builder.get_graph_data(graph_id)
                
                # 프로젝트 상태 갱신
                project.status = ProjectStatus.GRAPH_COMPLETED
                ProjectManager.save_project(project)
                
                node_count = graph_data.get("node_count", 0)
                edge_count = graph_data.get("edge_count", 0)
                build_logger.info(f"[{task_id}] 그래프 구축 완료: graph_id={graph_id}, 노드={node_count}, 엣지={edge_count}")
                
                # 완료 처리
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.COMPLETED,
                    message="그래프 구축 완료",
                    progress=100,
                    result={
                        "project_id": project_id,
                        "graph_id": graph_id,
                        "node_count": node_count,
                        "edge_count": edge_count,
                        "chunk_count": total_chunks
                    }
                )
                
            except Exception as e:
                # 프로젝트 상태를 실패로 갱신
                build_logger.error(f"[{task_id}] 그래프 구축 실패: {str(e)}")
                build_logger.debug(traceback.format_exc())
                
                project.status = ProjectStatus.FAILED
                project.error = str(e)
                ProjectManager.save_project(project)
                
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    message=f"구축 실패: {str(e)}",
                    error=traceback.format_exc()
                )
        
        # 백그라운드 스레드 시작
        thread = threading.Thread(target=build_task, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "data": {
                "project_id": project_id,
                "task_id": task_id,
                "message": "그래프 구축 작업이 시작되었습니다. /task/{task_id}로 진행 상황을 확인해 주세요"
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 작업 조회 인터페이스 ==============

@graph_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """
    작업 상태를 조회한다.
    """
    task = TaskManager().get_task(task_id)
    
    if not task:
        return jsonify({
            "success": False,
            "error": f"작업이 없습니다: {task_id}"
        }), 404
    
    return jsonify({
        "success": True,
        "data": task.to_dict()
    })


@graph_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """
    전체 작업 목록을 조회한다.
    """
    tasks = TaskManager().list_tasks()
    
    return jsonify({
        "success": True,
        "data": [t.to_dict() for t in tasks],
        "count": len(tasks)
    })


# ============== 그래프 데이터 인터페이스 ==============

@graph_bp.route('/data/<graph_id>', methods=['GET'])
def get_graph_data(graph_id: str):
    """
    그래프 데이터(노드/엣지)를 조회한다.
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEY가 설정되지 않았습니다"
            }), 500
        
        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        graph_data = builder.get_graph_data(graph_id)
        
        return jsonify({
            "success": True,
            "data": graph_data
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@graph_bp.route('/delete/<graph_id>', methods=['DELETE'])
def delete_graph(graph_id: str):
    """
    Zep 그래프를 삭제한다.
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEY가 설정되지 않았습니다"
            }), 500
        
        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        builder.delete_graph(graph_id)
        
        return jsonify({
            "success": True,
            "message": f"그래프를 삭제했습니다: {graph_id}"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
