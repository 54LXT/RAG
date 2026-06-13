import config_data as config  # 必须在最前：设置 HF_HUB_OFFLINE
import json
import logging
import asyncio
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from rag import RagService
from knowledge_base import ingest_file
from file_history_store import get_history, save_history

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_service = RagService()


class ChatRequest(BaseModel):
    query: str
    session_id: str


@app.on_event("startup")
async def startup():
    logger.info("RAG 服务已启动 model=%s", config.chat_model_name)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    allowed = (".txt", ".pdf", ".docx", ".png", ".jpg", ".jpeg", ".bmp")
    if not file.filename.lower().endswith(allowed):
        return {"success": False, "error": f"仅支持: {', '.join(allowed)} 文件"}

    import os
    os.makedirs("data", exist_ok=True)
    file_path = os.path.join("data", file.filename)
    content = await file.read()

    max_size = config.max_upload_mb * 1024 * 1024
    if len(content) > max_size:
        return {"success": False, "error": f"文件大小超过上限 ({config.max_upload_mb}MB)"}

    try:
        # 复用 RagService 的 embedding 实例，避免重复初始化 API 客户端
        ingest_file(file_path, embedding=rag_service.embedding)
        # 刷新检索器，重建 BM25 索引以覆盖新入库的文档
        rag_service.refresh_retriever()
        return {"success": True, "filename": file.filename}
    except Exception as e:
        logger.exception("上传入库失败")
        return {"success": False, "error": str(e)}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    stream, docs = rag_service.stream_ask(req.query, req.session_id)

    async def event_generator():
        for token in stream:
            yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0)

        # 在发送 sources/done 之前保存历史——防止客户端中途断开导致本轮对话丢失
        save_history(req.session_id)

        sources = [
            {"source": d.metadata.get("source", "未知"), "content": d.page_content}
            for d in docs
        ]
        yield f"data: {json.dumps({'type': 'sources', 'docs': sources}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@app.get("/api/history/{session_id}")
async def chat_history(session_id: str):
    history = get_history(session_id)
    messages = []
    for msg in history.messages:
        messages.append({
            "type": type(msg).__name__,
            "content": msg.content,
        })
    return {"messages": messages}
