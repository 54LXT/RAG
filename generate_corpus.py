"""
生成大规模测试语料库
用法: python generate_corpus.py --count 1000
"""
import os
import random
import argparse

# 原始核心文档（作为"正确答案"来源）
CORE_DOCS = {
    "docker-vitis.txt": """xczu9eg-ffvb1156
KV260密码 Kria@2025!
进入容器: cd ~/Vitis-AI
运行: ./docker_run.sh xilinx/vitis-ai-pytorch-cpu:latest
容器ID: f0fa4ddfaeb3
启动容器: docker start -ai f0fa4ddfaeb3
运行脚本: python vart_image_multi_thread.py
拷贝文件: docker cp /mnt/d/study/FPGA/xilinx/nets f0fa4ddfaeb3:/workspace/bushu/
Vitis-AI是Xilinx推出的AI推理部署平台，支持FPGA加速深度学习模型。
Docker环境提供了PyTorch、TensorFlow等框架的预编译版本。""",

    "python.txt": """房价预测（线性回归 / 随机森林）
鸢尾花分类 / 手写数字识别（MNIST）
电影推荐系统（协同过滤）
图片分类（CNN卷积神经网络）
文本分类 / 情感分析（NLP自然语言处理）
上述项目涵盖了机器学习的主要应用场景：回归预测、分类任务、推荐系统和计算机视觉。""",

    "vivasdo启动.txt": """source /tools/Xilinx/Vivado/2020.2/settings64.sh
vivado &
Vivado是Xilinx的FPGA开发环境，用于Verilog/VHDL代码编写、综合、布局布线和比特流生成。
settings64.sh脚本配置了Vivado所需的所有环境变量，包括PATH、LD_LIBRARY_PATH等。""",

    "改抢.txt": """改枪码配置：
丐版性价比: MK4冲锋枪-烽火地带-6JDKN3O0DL7ME0D5D5SUT
稳定高改版: MK4冲锋枪-烽火地带-6JDKN8K0DL7ME0D5D5SUT
轻语满改版: MK4冲锋枪-烽火地带-6JDKND00DL7ME0D5D5SUT
以上为游戏中的武器改装方案代码，适用于烽火地带地图。""",
}

# 干扰文档模板（不同主题，用于增加检索难度）
DISTRACTOR_TOPICS = [
    ["深度学习", "Transformer模型", "BERT预训练", "GPT生成", "注意力机制", "神经网络", "反向传播", "梯度下降", "损失函数", "激活函数", "卷积层", "池化层", "全连接层", "Dropout正则化", "Batch Normalization", "ResNet残差网络", "LSTM长短期记忆", "RNN循环神经网络", "GAN生成对抗网络", "强化学习"],
    ["数据库", "MySQL", "PostgreSQL", "MongoDB", "Redis缓存", "索引优化", "SQL查询", "事务ACID", "分库分表", "读写分离", "主从复制", "连接池", "ORM映射", "NoSQL", "Elasticsearch"],
    ["前端开发", "React", "Vue.js", "Angular", "CSS布局", "Flexbox", "Grid", "TypeScript", "Webpack", "Vite", "npm包管理", "组件化", "状态管理", "路由", "SSR服务端渲染"],
    ["Linux运维", "Shell脚本", "systemd服务", "cron定时任务", "Nginx配置", "防火墙iptables", "SSH远程", "文件权限chmod", "进程管理ps", "磁盘挂载mount", "日志查看journalctl"],
    ["云原生", "Kubernetes", "Docker容器", "微服务", "Service Mesh", "CI/CD流水线", "Helm Chart", "Prometheus监控", "Grafana可视化", "Istio服务网格", "容器编排"],
    ["编程语言", "Python", "Java", "Go", "Rust", "C++", "JavaScript", "TypeScript", "内存管理", "垃圾回收", "并发编程", "异步IO", "协程", "多线程"],
    ["计算机网络", "TCP/IP", "HTTP协议", "DNS解析", "负载均衡", "CDN加速", "WebSocket", "gRPC", "RESTful API", "GraphQL", "OSI七层模型"],
    ["安全", "SQL注入", "XSS跨站脚本", "CSRF攻击", "JWT认证", "OAuth2.0", "HTTPS加密", "防火墙", "WAF", "漏洞扫描", "渗透测试"],
    ["大数据", "Hadoop", "Spark", "Flink流处理", "Kafka消息队列", "Hive数据仓库", "HBase", "数据湖", "ETL管道", "实时计算"],
    ["移动开发", "Android", "iOS", "Flutter", "React Native", "Swift", "Kotlin", "APK打包", "App Store审核", "推送通知"],
]


def generate_distractor_docs(count):
    """生成干扰文档"""
    docs = {}
    for i in range(count):
        # 随机选1-3个主题混搭
        num_topics = random.randint(1, 3)
        topics = random.sample(DISTRACTOR_TOPICS, num_topics)
        lines = []
        for topic in topics:
            keywords = random.sample(topic, min(5, len(topic)))
            lines.append(f"关于{keywords[0]}的相关内容：")
            for kw in keywords[1:]:
                lines.append(f"- {kw}的详细介绍和实际应用案例")
                lines.append(f"  在实际项目中，{kw}常用于解决各种技术挑战。")
            lines.append("")
        doc_name = f"tech_doc_{i:04d}.txt"
        docs[doc_name] = "\n".join(lines)
    return docs


def generate_similar_docs(core_docs, variations_per_doc=10):
    """为核心文档生成相似但不同的变体（增加检索混淆）"""
    similar = {}
    for name, content in core_docs.items():
        base_name = name.replace(".txt", "")
        for v in range(variations_per_doc):
            lines = content.split("\n")
            # 随机打乱非空行的顺序，模拟不同排版
            non_empty = [l for l in lines if l.strip()]
            if len(non_empty) > 3:
                # 保留前2行（包含关键信息），打乱其余行
                head = non_empty[:2]
                tail = non_empty[2:]
                random.shuffle(tail)
                # 随机替换一些词
                new_lines = head + tail
                new_content = "\n".join(new_lines)
            else:
                new_content = content
            similar[f"{base_name}_variant_{v:02d}.txt"] = new_content
    return similar


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1000, help="目标文档总数")
    parser.add_argument("--output-dir", default="data_gen", help="生成文档输出目录")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # 核心文档
    core_count = len(CORE_DOCS)
    similar_count = core_count * 8  # 每篇核心文档8个变体
    distractor_count = args.count - core_count - similar_count

    print(f"目标文档总数: {args.count}")
    print(f"  核心文档: {core_count}")
    print(f"  相似变体: {similar_count}")
    print(f"  干扰文档: {distractor_count}")

    all_docs = {}

    # 1. 核心文档
    all_docs.update(CORE_DOCS)

    # 2. 相似变体
    similar = generate_similar_docs(CORE_DOCS, variations_per_doc=8)
    all_docs.update(similar)

    # 3. 干扰文档
    distractors = generate_distractor_docs(distractor_count)
    all_docs.update(distractors)

    # 写入文件
    for name, content in all_docs.items():
        path = os.path.join(args.output_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"\n已生成 {len(all_docs)} 个文档到 {args.output_dir}/")
    print(f"  核心文档（正确答案来源）: {core_count}")
    print(f"  相似变体（增加检索难度）: {similar_count}")
    print(f"  干扰文档（噪声）: {distractor_count}")


if __name__ == "__main__":
    main()
