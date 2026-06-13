import logging
import streamlit as st
from rag import RagService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

st.title("RAG 问答系统")

if "rag" not in st.session_state:
    st.session_state.rag = RagService()

if "session_id" not in st.session_state:
    st.session_state.session_id = "user_001"

query = st.chat_input("请输入你的问题")

if query:
    st.chat_message("user").write(query)

    try:
        response_stream, docs = st.session_state.rag.stream_ask(
            query=query,
            session_id=st.session_state.session_id
        )

        with st.chat_message("assistant"):
            answer = st.write_stream(response_stream)

        st.session_state.rag.save_history(st.session_state.session_id)

        with st.expander("参考来源"):
            for i, doc in enumerate(docs):
                source = doc.metadata.get("source", "未知文件")
                st.write(f"**来源 {i+1}：{source}**")
                st.write(doc.page_content)
                st.divider()
    except Exception:
        logging.getLogger(__name__).exception("问答失败")
        st.error("抱歉，处理请求时出现错误，请稍后重试。")