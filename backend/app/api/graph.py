"""
图谱相关API路由
采用项目上下文机制，服务端持久化状态
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

# 获取日志器
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
    """检查文件扩展名是否允许"""
    if not filename or '.' not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext in Config.ALLOWED_EXTENSIONS


# ============== 项目管理接口 ==============

@graph_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id: str):
    """
    获取项目详情
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
    列出所有项目
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
    删除项目
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
    重置项目状态（用于重新构建图谱）
    """
    project = ProjectManager.get_project(project_id)
    
    if not project:
        return jsonify({
            "success": False,
            "error": f"프로젝트가 없습니다: {project_id}"
        }), 404
    
    # 重置到本体已生成状态
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


# ============== 接口1：上传文件并生成本体 ==============

@graph_bp.route('/ontology/generate', methods=['POST'])
def generate_ontology():
    """
    接口1：上传文件，分析生成本体定义
    
    请求方式：multipart/form-data
    
    参数：
        files: 上传的文件（PDF/MD/TXT），可多个
        simulation_requirement: 模拟需求描述（必填）
        project_name: 项目名称（可选）
        additional_context: 额外说明（可选）
        
    返回：
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
        
        # 获取参数
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
        
        # 获取上传的文件
        uploaded_files = request.files.getlist('files')
        if not uploaded_files or all(not f.filename for f in uploaded_files):
            return jsonify({
                "success": False,
                "error": "문서 파일을 하나 이상 업로드해 주세요"
            }), 400
        
        # 创建项目
        project = ProjectManager.create_project(name=project_name)
        project.simulation_requirement = simulation_requirement
        logger.info(f"프로젝트 생성: {project.project_id}")
        
        # 保存文件并提取文本
        document_texts = []
        all_text = ""
        
        for file in uploaded_files:
            if file and file.filename and allowed_file(file.filename):
                # 保存文件到项目目录
                file_info = ProjectManager.save_file_to_project(
                    project.project_id, 
                    file, 
                    file.filename
                )
                project.files.append({
                    "filename": file_info["original_filename"],
                    "size": file_info["size"]
                })
                
                # 提取文本
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
        
        # 保存提取的文本
        project.total_text_length = len(all_text)
        ProjectManager.save_extracted_text(project.project_id, all_text)
        logger.info(f"텍스트 추출 완료: 총 {len(all_text)}자")
        
        # 生成本体
        logger.info("LLM으로 온톨로지 정의 생성 중...")
        generator = OntologyGenerator()
        ontology = generator.generate(
            document_texts=document_texts,
            simulation_requirement=simulation_requirement,
            additional_context=additional_context if additional_context else None
        )
        
        # 保存本体到项目
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


# ============== 接口2：构建图谱 ==============

@graph_bp.route('/build', methods=['POST'])
def build_graph():
    """
    接口2：根据project_id构建图谱
    
    请求（JSON）：
        {
            "project_id": "proj_xxxx",  // 必填，来自接口1
            "graph_name": "图谱名称",    // 可选
            "chunk_size": 500,          // 可选，默认500
            "chunk_overlap": 50         // 可选，默认50
        }
        
    返回：
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
        
        # 检查配置
        errors = []
        if not Config.ZEP_API_KEY:
            errors.append("ZEP_API_KEY가 설정되지 않았습니다")
        if errors:
            logger.error(f"설정 오류: {errors}")
            return jsonify({
                "success": False,
                "error": "설정 오류: " + "; ".join(errors)
            }), 500
        
        # 解析请求
        data = request.get_json() or {}
        project_id = data.get('project_id')
        logger.debug(f"요청 파라미터: project_id={project_id}")
        
        if not project_id:
            return jsonify({
                "success": False,
                "error": "project_id를 입력해 주세요"
            }), 400
        
        # 获取项目
        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"프로젝트가 없습니다: {project_id}"
            }), 404
        
        # 检查项目状态
        force = data.get('force', False)  # 强制重新构建
        
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
        
        # 如果强制重建，重置状态
        if force and project.status in [ProjectStatus.GRAPH_BUILDING, ProjectStatus.FAILED, ProjectStatus.GRAPH_COMPLETED]:
            project.status = ProjectStatus.ONTOLOGY_GENERATED
            project.graph_id = None
            project.graph_build_task_id = None
            project.error = None
        
        # 获取配置
        graph_name = data.get('graph_name', project.name or 'MiroFish Graph')
        chunk_size = data.get('chunk_size', project.chunk_size or Config.DEFAULT_CHUNK_SIZE)
        chunk_overlap = data.get('chunk_overlap', project.chunk_overlap or Config.DEFAULT_CHUNK_OVERLAP)
        
        # 更新项目配置
        project.chunk_size = chunk_size
        project.chunk_overlap = chunk_overlap
        
        # 获取提取的文本
        text = ProjectManager.get_extracted_text(project_id)
        if not text:
            return jsonify({
                "success": False,
                "error": "추출된 텍스트를 찾을 수 없습니다"
            }), 400
        
        # 获取本体
        ontology = project.ontology
        if not ontology:
            return jsonify({
                "success": False,
                "error": "온톨로지 정의를 찾을 수 없습니다"
            }), 400
        
        # 创建异步任务
        task_manager = TaskManager()
        task_id = task_manager.create_task(f"그래프 구축: {graph_name}")
        logger.info(f"그래프 구축 작업 생성: task_id={task_id}, project_id={project_id}")
        
        # 更新项目状态
        project.status = ProjectStatus.GRAPH_BUILDING
        project.graph_build_task_id = task_id
        ProjectManager.save_project(project)
        
        # 启动后台任务
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
                
                # 创建图谱构建服务
                builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
                
                # 分块
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
                
                # 创建图谱
                task_manager.update_task(
                    task_id,
                    message="Zep 그래프를 생성하는 중...",
                    progress=10
                )
                graph_id = builder.create_graph(name=graph_name)
                
                # 更新项目的graph_id
                project.graph_id = graph_id
                ProjectManager.save_project(project)
                
                # 设置本体
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
                
                # 添加文本（progress_callback 签名是 (msg, progress_ratio)）
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
                
                # 等待Zep处理完成（查询每个episode的processed状态）
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
                
                # 获取图谱数据
                task_manager.update_task(
                    task_id,
                    message="그래프 데이터를 가져오는 중...",
                    progress=95
                )
                graph_data = builder.get_graph_data(graph_id)
                
                # 更新项目状态
                project.status = ProjectStatus.GRAPH_COMPLETED
                ProjectManager.save_project(project)
                
                node_count = graph_data.get("node_count", 0)
                edge_count = graph_data.get("edge_count", 0)
                build_logger.info(f"[{task_id}] 그래프 구축 완료: graph_id={graph_id}, 노드={node_count}, 엣지={edge_count}")
                
                # 完成
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
                # 更新项目状态为失败
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
        
        # 启动后台线程
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


# ============== 任务查询接口 ==============

@graph_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """
    查询任务状态
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
    列出所有任务
    """
    tasks = TaskManager().list_tasks()
    
    return jsonify({
        "success": True,
        "data": [t.to_dict() for t in tasks],
        "count": len(tasks)
    })


# ============== 图谱数据接口 ==============

@graph_bp.route('/data/<graph_id>', methods=['GET'])
def get_graph_data(graph_id: str):
    """
    获取图谱数据（节点和边）
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
    删除Zep图谱
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
