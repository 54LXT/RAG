<template>
  <div class="chat-panel">
    <div class="messages" ref="msgList">
      <div v-if="messages.length === 0" class="empty-hint">输入问题开始对话</div>

      <div v-for="(msg, i) in messages" :key="i" :class="['message', msg.role]">
        <div class="avatar">{{ msg.role === 'user' ? 'U' : 'AI' }}</div>
        <div class="bubble">
          <div class="text">{{ msg.content }}</div>
          <SourceViewer v-if="msg.sources" :sources="msg.sources" />
        </div>
      </div>

      <div v-if="streaming" class="message assistant">
        <div class="avatar">AI</div>
        <div class="bubble">
          <div class="text">{{ streamingText }}<span class="cursor">|</span></div>
        </div>
      </div>
    </div>

    <div class="input-row">
      <textarea
        v-model="input"
        @keydown.enter.exact.prevent="send"
        placeholder="输入问题，按 Enter 发送"
        rows="2"
        :disabled="streaming"
      ></textarea>
      <button @click="send" :disabled="streaming || !input.trim()">发送</button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from "vue";
import { streamChat, getHistory } from "../api/index.js";
import SourceViewer from "./SourceViewer.vue";

const props = defineProps({ sessionId: String });

const messages = ref([]);
const input = ref("");
const streaming = ref(false);
const streamingText = ref("");
const msgList = ref(null);

onMounted(async () => {
  try {
    const data = await getHistory(props.sessionId);
    messages.value = data.messages.map((m) => ({
      role: m.type === "HumanMessage" ? "user" : "assistant",
      content: m.content,
    }));
    scrollBottom();
  } catch (e) {
    // 历史加载失败不影响使用
  }
});

function scrollBottom() {
  nextTick(() => {
    const el = msgList.value;
    if (el) el.scrollTop = el.scrollHeight;
  });
}

async function send() {
  const q = input.value.trim();
  if (!q || streaming.value) return;
  input.value = "";

  messages.value.push({ role: "user", content: q });
  scrollBottom();

  streaming.value = true;
  streamingText.value = "";

  try {
    let sources = null;
    for await (const ev of streamChat(q, props.sessionId)) {
      if (ev.type === "token") {
        streamingText.value += ev.content;
        scrollBottom();
      } else if (ev.type === "sources") {
        sources = ev.docs;
      } else if (ev.type === "done") {
        messages.value.push({
          role: "assistant",
          content: streamingText.value,
          sources,
        });
        streamingText.value = "";
      }
    }
  } catch (e) {
    messages.value.push({
      role: "assistant",
      content: "抱歉，请求失败：" + e.message,
    });
    streamingText.value = "";
  } finally {
    streaming.value = false;
    scrollBottom();
  }
}
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 100px);
  max-width: 800px;
  margin: 0 auto;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
}
.empty-hint {
  text-align: center;
  color: #999;
  margin-top: 80px;
}
.message {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}
.message.user { flex-direction: row-reverse; }
.avatar {
  width: 32px; height: 32px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: bold; flex-shrink: 0;
}
.message.user .avatar { background: #4f46e5; color: #fff; }
.message.assistant .avatar { background: #e5e7eb; color: #374151; }
.bubble {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
}
.message.user .bubble { background: #4f46e5; color: #fff; }
.message.assistant .bubble { background: #f3f4f6; color: #1f2937; }
.cursor {
  display: inline-block;
  animation: blink 1s step-end infinite;
  color: #4f46e5;
}
@keyframes blink {
  50% { opacity: 0; }
}
.input-row {
  display: flex; gap: 8px;
  padding: 10px 0; border-top: 1px solid #e5e7eb;
}
.input-row textarea {
  flex: 1; resize: none;
  padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px;
  font-size: 14px; outline: none; font-family: inherit;
}
.input-row textarea:focus { border-color: #4f46e5; }
.input-row button {
  padding: 0 20px; background: #4f46e5; color: #fff;
  border: none; border-radius: 8px; cursor: pointer; font-size: 14px;
}
.input-row button:disabled { opacity: 0.5; cursor: default; }
</style>
