import config_data as config  # 必须在最前：设置 HF_HUB_OFFLINE 等环境变量

import logging
import tiktoken

from langchain_core.messages import BaseMessage
from langchain_core.runnables import (
    RunnableLambda,
    RunnableWithMessageHistory
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings

from vector_stores import VectorStoreService
from file_history_store import get_history, save_history

logger = logging.getLogger(__name__)

# 全局 tokenizer（cl100k_base 与 tiktoken 在 knowledge_base 中保持一致）
_tokenizer = tiktoken.get_encoding("cl100k_base")


def _estimate_tokens(messages: list[BaseMessage]) -> int:
    """估算消息列表的总 token 数"""
    total = 0
    for msg in messages:
        # 每条消息额外 +4 tokens 用于角色标记（approximate）
        total += len(_tokenizer.encode(msg.content)) + 4
    return total


def _trim_history(messages: list[BaseMessage], max_tokens: int) -> list[BaseMessage]:
    """从消息列表头部丢弃旧消息，直到总 token 数不超过 max_tokens"""
    if not messages:
        return messages

    current_tokens = _estimate_tokens(messages)
    if current_tokens <= max_tokens:
        return messages

    # 从最旧的消息开始丢弃，确保至少保留最后一条消息
    trimmed = list(messages)
    while len(trimmed) > 1:
        removed = trimmed.pop(0)
        current_tokens -= (len(_tokenizer.encode(removed.content)) + 4)
        if current_tokens <= max_tokens:
            break

    if len(trimmed) >= 2:
        logger.info(
            "历史截断: %d → %d 条消息 (tokens: %d, 阈值: %d)",
            len(messages), len(trimmed), current_tokens, max_tokens
        )

    return trimmed


class RagService:
    def __init__(self):
        self.embedding = DashScopeEmbeddings(
            model=config.embedding_model_name,
            dashscope_api_key=config.DASHSCOPE_API_KEY,
        )
        self.vector_service = VectorStoreService(self.embedding)
        self.retriever = self.vector_service.get_retriever()

        self.prompt = ChatPromptTemplate.from_messages([
 {context}
            """),
            MessagesPlaceholder("history"),
            ("user", "{input}")
        ])

        # 开启流式输出
        self.llm = ChatTongyi(
            model=config.chat_model_name,
            temperature=0.1,
            streaming=True,
            dashscope_api_key=config.DASHSCOPE_API_KEY,
        )

        self.chain = self._build_chain()

    def _build_chain(self):
        def retrieve_with_docs(input_dict):
            query = input_dict["input"]
            docs = input_dict.get("docs") or self.retriever.invoke(query)
            context = "\n\n".join([d.page_content for d in docs])

            # 对历史消息做滑动窗口截断，避免超出上下文窗口
            history = input_dict.get("history", [])
            history = _trim_history(list(history), config.max_history_tokens)

            return {
                "input": query,
                "context": context,
                "history": history
            }

        chain = (
            RunnableLambda(retrieve_with_docs)
            | self.prompt
            | self.llm
            | StrOutputParser()
        )

        return RunnableWithMessageHistory(
            chain,
            get_history,
            input_messages_key="input",
            history_messages_key="history",
        )

    # 公开方法：流式问答
    def stream_ask(self, query: str, session_id: str):
        config = {
            "configurable": {"session_id": session_id}
        }
        try:
            docs = self.retriever.invoke(query)
            logger.info("检索完成 session=%s query=%s docs=%d", session_id, query[:30], len(docs))
        except Exception:
            logger.exception("检索失败 session=%s", session_id)
            raise

        try:
            stream = self.chain.stream(
                {"input": query, "docs": docs},
                config=config
            )
            return stream, docs
        except Exception:
            logger.exception("LLM 调用失败 session=%s", session_id)
            raise

    def refresh_retriever(self):
        """入库后刷新检索器，确保新文档可被 BM25 和向量检索覆盖"""
        self.retriever = self.vector_service.refresh_retriever()
        logger.info("检索器已刷新（BM25 缓存已清除）")

    def save_history(self, session_id: str):
        save_history(session_id)