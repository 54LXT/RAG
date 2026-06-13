"""批量入库脚本"""
import sys, os, shutil, glob, time
sys.path.insert(0, os.path.dirname(__file__))
import config_data as config
from knowledge_base import ingest_file
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("batch_ingest")

# 清空旧向量库
if os.path.exists(config.persist_directory):
    shutil.rmtree(config.persist_directory)
    logger.info("已清空旧向量库: %s", config.persist_directory)

# 入库所有生成文档（含原始核心文档 + 相似变体 + 干扰文档）
files = glob.glob("data_gen/*.txt")
logger.info("开始批量入库 %d 个文件...", len(files))

success, fail = 0, 0
start = time.time()
for i, f in enumerate(files):
    try:
        ingest_file(f)
        success += 1
    except Exception as e:
        fail += 1
        if fail <= 3:
            logger.warning("入库失败 %s: %s", os.path.basename(f), e)
    if (i + 1) % 100 == 0:
        elapsed = time.time() - start
        logger.info("进度: %d/%d (%.1f docs/s)", i + 1, len(files), (i + 1) / elapsed)

elapsed = time.time() - start
logger.info("完成: %d 成功, %d 失败, 耗时 %.1fs (%.1f docs/s)", success, fail, elapsed, success / elapsed if elapsed > 0 else 0)
