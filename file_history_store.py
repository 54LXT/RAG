import json
import logging
import os
from collections import OrderedDict

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

import config_data as config

logger = logging.getLogger(__name__)

HISTORY_FILE = "chat_history.json"

# OrderedDict 实现 LRU：最近访问的排在末尾，淘汰时从头部移除
store: OrderedDict[str, InMemoryChatMessageHistory] = OrderedDict()


def _load_from_disk():
    if not os.path.exists(HISTORY_FILE):
        return
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    for session_id, messages in data.items():
        history = InMemoryChatMessageHistory()
        for msg in messages:
            if msg["type"] == "HumanMessage":
                history.add_message(HumanMessage(content=msg["content"]))
            elif msg["type"] == "AIMessage":
                history.add_message(AIMessage(content=msg["content"]))
        store[session_id] = history


def _evict_one():
    """淘汰最早（最久未访问）的一个会话，淘汰前先持久化"""
    _save_all_to_disk()
    oldest_sid, _ = store.popitem(last=False)
    logger.info("LRU 淘汰会话: %s (当前内存会话数: %d)", oldest_sid, len(store))


def _save_all_to_disk():
    """将内存中的会话写入磁盘，同时保留已淘汰到磁盘的会话"""
    # 先读取磁盘上已有的数据（保留被 LRU 淘汰的会话）
    data = {}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    # 用内存中的最新状态覆盖对应会话
    for sid, history in store.items():
        data[sid] = []
        for msg in history.messages:
            data[sid].append({
                "type": type(msg).__name__,
                "content": msg.content,
            })

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_history(session_id: str):
    if not store:
        _load_from_disk()

    if session_id in store:
        # 移到末尾表示最近访问
        store.move_to_end(session_id)
        return store[session_id]

    # 新会话：超过上限则淘汰最旧的
    while len(store) >= config.max_sessions:
        _evict_one()

    store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]


def save_history(session_id: str):
    _save_all_to_disk()
