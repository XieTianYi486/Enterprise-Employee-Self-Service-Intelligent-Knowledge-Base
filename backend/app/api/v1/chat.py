# ============================================================
# 问答交互接口
# POST /api/v1/chat/ask     - 同步提问
# POST /api/v1/chat/stream  - 流式提问 (SSE)
# 会话管理 CRUD
# ============================================================

import json
import logging
import traceback as tb_module
import uuid as uuid_lib
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.db.sqlite import get_db, SessionLocal
from app.api.deps import get_current_active_user, get_security_level, require_permission
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage, ChatLog
from app.schemas.common import APIResponse, PaginatedData
from app.schemas.chat import (
    AskRequest, FeedbackRequest,
    CitationSource, SessionCreate, SessionUpdate,
    SessionResponse, MessageResponse,
)
from app.services.chat_service import ChatService, get_chat_service
from app.services.sensitive_service import SensitiveService
from app.services.audit_service import add_audit_log

router = APIRouter(prefix="/chat", tags=["问答交互"])
logger = logging.getLogger(__name__)


# ==================== 问题侧敏感词拦截 ====================

BLOCKED_QUESTION_RESPONSE = (
    "您的问题包含敏感内容，系统已拦截并记录。请调整提问内容后重试。"
)


def _check_question_sensitive(db: Session, question: str, user: User) -> bool:
    """问题侧高危敏感词检测：命中则写审计留痕并返回 True（由调用方拒答）"""
    words = SensitiveService.get_enabled_words(db)
    if not SensitiveService.contains_block_word(question, words):
        return False
    add_audit_log(
        db=db, module="sensitive", action="sensitive_block", status="blocked",
        user_id=user.id, username=user.username,
        target_type="chat", detail={"question": question[:200]},
    )
    return True


# ==================== 问答 ====================

@router.post("/ask", response_model=APIResponse, summary="同步提问")
def ask_question(
    request: AskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("chat:ask")),
):
    """
    同步问答接口
    提交问题后等待完整答案返回（适用于批量调用和测试）
    """
    chat_service = get_chat_service()

    # ── 关键：提前将 detached SQLAlchemy 对象的数据提取为纯 Python 变量，
    #    避免后续代码访问 detached User 触发 "not bound to a Session" 错误 ──
    user_id: int = current_user.id
    role_code: str = current_user.role.code if current_user.role else ""

    # ── 问题侧敏感词拦截：高危词直接拒答并审计留痕 ──
    if _check_question_sensitive(db, request.question, current_user):
        return APIResponse(
            code=0, message="success",
            data={
                "answer_id": None,
                "answer": BLOCKED_QUESTION_RESPONSE,
                "sources": [],
                "session_id": request.session_id,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "latency": {"retrieval_ms": 0, "rerank_ms": 0, "llm_ms": 0, "total_ms": 0},
            },
        )

    # ── 会话归属校验：不允许携带他人会话ID（可读取其历史/向其写入消息）──
    if request.session_id:
        owned_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.id == request.session_id,
                ChatSession.user_id == user_id,
            )
            .first()
        )
        if not owned_session:
            return APIResponse(code=3001, message="会话不存在或无权访问")

    # 获取会话历史
    chat_history = None
    if request.session_id:
        history_msgs = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == request.session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(20).all()
        )
        chat_history = [
            {"role": msg.role, "content": msg.content}
            for msg in history_msgs
        ]

    # 确定可访问密级（基于用户角色）
    security_level = get_security_level(role_code)

    # 执行 RAG 问答
    result = chat_service.ask(
        question=request.question,
        security_level=security_level,
        chat_history=chat_history,
    )

    # ── 敏感词脱敏：对 AI 回答做合规过滤并留痕 ──
    masked_answer, sensitive_hits = SensitiveService.mask_answer(
        result["answer"], db,
        user_id=user_id, username=current_user.username,
    )
    result["answer"] = masked_answer

    # 创建/获取会话
    session_id = request.session_id or _generate_session_id()
    if not request.session_id:
        session = ChatSession(
            id=session_id,
            user_id=user_id,
            title=request.question[:50],
        )
        db.add(session)

    # 保存用户消息
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=request.question,
    )
    db.add(user_msg)

    # 保存助手消息
    answer_id = uuid_lib.uuid4().hex[:12]
    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=result["answer"],
        sources=json.dumps(result.get("sources", [])),
        token_count=result.get("usage", {}).get("total_tokens", 0),
    )
    db.add(assistant_msg)
    # 先提交释放 SQLite 写锁，避免 save_chat_log 的独立会话因抢锁失败丢日志
    db.commit()

    # 异步写入日志
    chat_service.save_chat_log(
        question=request.question,
        answer=result["answer"],
        session_id=session_id,
        user_id=user_id,
        sources=result.get("sources", []),
        latency=result.get("latency", {}),
        usage=result.get("usage", {}),
    )

    return APIResponse(
        code=0,
        message="success",
        data={
            "answer_id": answer_id,
            "answer": result["answer"],
            "sources": result.get("sources", []),
            "similarity": result.get("similarity"),
            "session_id": session_id,
            "usage": result.get("usage", {}),
            "latency": result.get("latency", {}),
        }
    )


@router.post("/stream", summary="流式提问 (SSE)")
async def ask_stream(
    request: AskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("chat:ask")),
):
    """
    流式问答接口 (Server-Sent Events)

    事件类型:
    - event: token   → {"token": "文字片段"}
    - event: sources → [{"document_name": "...", ...}]
    - event: done    → {"full_answer": "...", "total_tokens": 123}
    - event: error   → {"message": "错误信息"}
    """
    chat_service = get_chat_service()

    # ── 将 detached SQLAlchemy 对象的数据提取为纯 Python 变量 ──
    user_id: int = current_user.id
    username: str = current_user.username
    role_code: str = current_user.role.code if current_user.role else ""
    security_level = get_security_level(role_code)
    question: str = request.question

    # ── 问题侧敏感词拦截：高危词直接拒答并审计留痕（以 SSE 协议返回）──
    if _check_question_sensitive(db, question, current_user):
        def blocked_stream():
            payload = {"token": BLOCKED_QUESTION_RESPONSE}
            yield f"event: token\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield f"event: sources\ndata: {json.dumps([], ensure_ascii=False)}\n\n"
            done_payload = {
                "full_answer": BLOCKED_QUESTION_RESPONSE,
                "status": "blocked",
                "latency": {"retrieval_ms": 0, "llm_ms": 0, "total_ms": 0},
            }
            yield f"event: done\ndata: {json.dumps(done_payload, ensure_ascii=False)}\n\n"
        return StreamingResponse(blocked_stream(), media_type="text/event-stream")

    # ── 会话归属校验：不允许携带他人会话ID（可读取其历史/向其写入消息）──
    if request.session_id:
        owned_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.id == request.session_id,
                ChatSession.user_id == user_id,
            )
            .first()
        )
        if not owned_session:
            def denied_stream():
                yield f"event: error\ndata: {json.dumps({'message': '会话不存在或无权访问'}, ensure_ascii=False)}\n\n"
            return StreamingResponse(denied_stream(), media_type="text/event-stream")

    # 获取会话历史（在 db Session 关闭前提取为纯 dict 列表）
    chat_history = None
    if request.session_id:
        history_msgs = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == request.session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(20).all()
        )
        chat_history = [
            {"role": msg.role, "content": msg.content}
            for msg in history_msgs
        ]

    # 创建/获取会话
    session_id = request.session_id or _generate_session_id()
    if not request.session_id:
        session = ChatSession(
            id=session_id,
            user_id=user_id,
            title=question[:50],
        )
        db.add(session)
        db.flush()

    # 保存用户消息
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=question,
    )
    db.add(user_msg)
    db.commit()
    db.close()

    # ── 流式数据收集器（在生成器和后台任务之间传递数据） ──
    stream_result = {"full_answer": "", "sources": [], "ok": False, "status": "", "latency": {}}

    async def event_stream():
        """纯 SSE 流式生成器 —— 不涉及任何数据库操作"""
        try:
            async for event in chat_service.ask_stream(
                question=question,
                security_level=security_level,
                chat_history=chat_history,
            ):
                if event["type"] == "token":
                    stream_result["full_answer"] += event["data"]
                    yield f"event: token\ndata: {json.dumps({'token': event['data']}, ensure_ascii=False)}\n\n"

                elif event["type"] == "sources":
                    stream_result["sources"] = event["data"]
                    yield f"event: sources\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"

                elif event["type"] == "done":
                    event_data = event["data"]
                    if event_data.get("status") == "not_found":
                        stream_result["full_answer"] = event_data["answer"]
                    stream_result["status"] = event_data.get("status", "")
                    stream_result["latency"] = event_data.get("latency", {})

                    # ── 敏感词脱敏（完成后对完整回答做合规过滤）──
                    masked = stream_result["full_answer"]
                    hits = []
                    if masked:
                        sdb = SessionLocal()
                        try:
                            masked, hits = SensitiveService.mask_answer(
                                masked, sdb,
                                user_id=user_id, username=username,
                            )
                            sdb.commit()
                        finally:
                            sdb.close()
                        stream_result["full_answer"] = masked
                        if hits:
                            yield f"event: sensitive\ndata: {json.dumps({'full_answer': masked, 'hits': hits}, ensure_ascii=False)}\n\n"

                    event_data["full_answer"] = masked
                    stream_result["ok"] = True
                    yield f"event: done\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"

                elif event["type"] == "error":
                    yield f"event: error\ndata: {json.dumps({'message': event['data']}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error("流式问答异常:\n%s", tb_module.format_exc())
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"

    def save_assistant_message():
        """后台任务：流式完成后保存助手消息和问答日志（使用独立 Session）"""
        if not stream_result["ok"]:
            return
        save_db = SessionLocal()
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)

            # 保存助手消息
            assistant_msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=stream_result["full_answer"],
                sources=json.dumps(stream_result["sources"]),
                token_count=len(stream_result["full_answer"]) // 3,
            )
            save_db.add(assistant_msg)

            # 更新会话计数
            sess = save_db.query(ChatSession).filter(
                ChatSession.id == session_id
            ).first()
            if sess:
                sess.message_count = sess.message_count + 2
                sess.last_message_at = now

            # 保存问答日志
            source_docs = stream_result.get("sources", [])
            is_not_found = stream_result.get("status") == "not_found"
            answer_text = stream_result.get("full_answer", "")
            # 检测 LLM 拒答：答案中包含以下任一模式即判定为未命中
            refusal_patterns = [
                "未找到相关信息", "未找到关于", "知识库中未找到", "无法回答",
                "建议您咨询", "无法获取", "参考资料中未涉及", "未涉及",
            ]
            is_refusal = any(p in answer_text for p in refusal_patterns)
            is_answered = 0 if (is_not_found or not source_docs or is_refusal) else 1
            latency = stream_result.get("latency", {})
            chat_log = ChatLog(
                session_id=session_id,
                user_id=user_id,
                question=question,
                answer=stream_result["full_answer"],
                source_doc_ids=[s.get("document_id") for s in source_docs],
                is_answered=is_answered,
                retrieval_ms=latency.get("retrieval_ms", 0),
                llm_ms=latency.get("llm_ms", 0),
                total_ms=latency.get("total_ms", 0),
                prompt_tokens=0,
                completion_tokens=0,
            )
            save_db.add(chat_log)

            save_db.commit()
        except Exception:
            save_db.rollback()
            logger.warning("保存助手消息失败:\n%s", tb_module.format_exc())
        finally:
            save_db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
        background=BackgroundTask(save_assistant_message),
    )


# ==================== 会话管理 ====================

@router.get("/sessions", response_model=APIResponse, summary="会话列表")
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.last_message_at.desc().nullslast())
        .all()
    )
    data = [
        SessionResponse(
            id=s.id, user_id=s.user_id, title=s.title,
            message_count=s.message_count,
            last_message_at=s.last_message_at, created_at=s.created_at,
        ).model_dump()
        for s in sessions
    ]
    return APIResponse(code=0, message="success", data=data)


@router.post("/sessions", response_model=APIResponse, summary="创建会话")
def create_session(
    request: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    session = ChatSession(
        id=_generate_session_id(),
        user_id=current_user.id,
        title=request.title,
    )
    db.add(session)
    db.flush()
    return APIResponse(
        code=0, message="会话创建成功",
        data={"session_id": session.id, "title": session.title}
    )


@router.patch("/sessions/{session_id}", response_model=APIResponse, summary="更新会话")
def update_session(
    session_id: str, request: SessionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()
    if not session:
        return APIResponse(code=3001, message="会话不存在")
    if request.title is not None:
        session.title = request.title
        db.flush()
    return APIResponse(code=0, message="更新成功")


@router.delete("/sessions/{session_id}", response_model=APIResponse, summary="删除会话")
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()
    if not session:
        return APIResponse(code=3001, message="会话不存在")
    db.delete(session)
    db.flush()
    return APIResponse(code=0, message="会话已删除")


@router.get("/sessions/{session_id}/messages", response_model=APIResponse, summary="会话消息")
def get_session_messages(
    session_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()
    if not session:
        return APIResponse(code=3001, message="会话不存在")

    query = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc())

    total = query.count()
    messages = query.offset((page - 1) * page_size).limit(page_size).all()

    msg_list = []
    for m in messages:
        sources = None
        if m.sources:
            try:
                parsed = json.loads(m.sources) if isinstance(m.sources, str) else m.sources
                sources = [CitationSource(**s) for s in parsed]
            except Exception:
                pass
        msg_list.append(MessageResponse(
            id=m.id, session_id=m.session_id, role=m.role,
            content=m.content, sources=sources,
            token_count=m.token_count, created_at=m.created_at,
        ).model_dump())

    return APIResponse(
        code=0, message="success",
        data=PaginatedData.from_query(msg_list, total, page, page_size).model_dump()
    )


# ==================== 反馈 ====================

@router.post("/feedback", response_model=APIResponse, summary="提交反馈")
def submit_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """提交答案反馈（通过 session_id 关联到最近的问答日志）"""
    # 优先查找该会话中最近的日志
    log = db.query(ChatLog).filter(
        ChatLog.user_id == current_user.id,
        ChatLog.session_id == request.session_id,
    ).order_by(ChatLog.created_at.desc()).first()

    # 如果找不到指定会话的日志，回退到用户最近的日志
    if not log:
        log = db.query(ChatLog).filter(
            ChatLog.user_id == current_user.id,
        ).order_by(ChatLog.created_at.desc()).first()

    if log:
        log.feedback = request.feedback
        log.feedback_reason = request.reason
        db.flush()
    return APIResponse(code=0, message="感谢您的反馈")


# ==================== 工具函数 ====================

def _generate_session_id() -> str:
    return f"sess_{uuid_lib.uuid4().hex[:16]}"
