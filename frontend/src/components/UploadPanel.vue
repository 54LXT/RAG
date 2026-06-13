<template>
  <div class="upload-panel">
    <div
      class="drop-zone"
      :class="{ over: dragging }"
      @dragover.prevent="dragging = true"
      @dragleave="dragging = false"
      @drop.prevent="onDrop"
    >
      <p>拖拽 txt/pdf/docx/图片文件到此处，或点击选择</p>
      <input
        type="file"
        accept=".txt,.pdf,.docx,.png,.jpg,.jpeg,.bmp"
        @change="onFileChange"
        :disabled="uploading"
      />
    </div>

    <div v-if="uploading" class="status">上传中...</div>
    <div v-else-if="result" :class="['status', result.success ? 'ok' : 'fail']">
      {{ result.success ? `已入库：${result.filename}` : result.error }}
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { uploadFile } from "../api/index.js";

const dragging = ref(false);
const uploading = ref(false);
const result = ref(null);

async function upload(file) {
  uploading.value = true;
  result.value = null;
  try {
    result.value = await uploadFile(file);
  } catch (e) {
    result.value = { success: false, error: e.message };
  } finally {
    uploading.value = false;
  }
}

function onDrop(e) {
  dragging.value = false;
  const file = e.dataTransfer.files[0];
  if (file) upload(file);
}

function onFileChange(e) {
  const file = e.target.files[0];
  if (file) upload(file);
}
</script>

<style scoped>
.upload-panel {
  max-width: 500px;
  margin: 60px auto 0;
}
.drop-zone {
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  transition: border-color 0.2s;
}
.drop-zone.over { border-color: #4f46e5; background: #eef2ff; }
.drop-zone p { color: #6b7280; margin-bottom: 12px; }
.status { margin-top: 12px; padding: 8px 12px; border-radius: 6px; font-size: 14px; }
.status.ok { background: #ecfdf5; color: #065f46; }
.status.fail { background: #fef2f2; color: #991b1b; }
</style>
