import logging
import streamlit as st
from knowledge_base import ingest_file
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

st.write("当前运行目录:", os.getcwd())
st.title("知识库上传")


uploaded_file = st.file_uploader("上传txt文件", type=["txt"])
if uploaded_file:
    try:
        os.makedirs("data", exist_ok=True)
        file_path = os.path.join("data", uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.read())
        logger.info("开始入库: %s", uploaded_file.name)
        ingest_file(file_path)
        logger.info("入库成功: %s", uploaded_file.name)
        st.success("上传并入库成功！")
    except Exception as e:
        logger.exception("入库失败: %s", uploaded_file.name)
        st.error(f"处理失败：{e}")