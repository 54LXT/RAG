<template>
  <div class="app">
    <header>
      <h1>RAG 知识库问答</h1>
      <nav>
        <button :class="{ active: tab === 'chat' }" @click="tab = 'chat'">问答</button>
        <button :class="{ active: tab === 'upload' }" @click="tab = 'upload'">上传</button>
      </nav>
    </header>

    <main>
      <ChatPanel v-if="tab === 'chat'" :session-id="sessionId" />
      <UploadPanel v-else />
    </main>
  </div>
</template>

<script setup>
import { ref } from "vue";
import ChatPanel from "./components/ChatPanel.vue";
import UploadPanel from "./components/UploadPanel.vue";

function getSessionId() {
  const key = "rag_session_id";
  let id = localStorage.getItem(key);
  if (!id) {
    id = "user_" + Date.now();
    localStorage.setItem(key, id);
  }
  return id;
}

const tab = ref("chat");
const sessionId = ref(getSessionId());
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }

.app { min-height: 100vh; display: flex; flex-direction: column; }

header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 24px; border-bottom: 1px solid #e5e7eb;
}
header h1 { font-size: 18px; color: #1f2937; }
nav { display: flex; gap: 4px; }
nav button {
  padding: 6px 16px; border: 1px solid #d1d5db; background: #fff;
  border-radius: 6px; cursor: pointer; font-size: 13px;
}
nav button.active { background: #4f46e5; color: #fff; border-color: #4f46e5; }

main { flex: 1; padding: 0 24px; }
</style>
