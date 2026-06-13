<template>
  <div v-if="sources && sources.length > 0" class="source-viewer">
    <button class="toggle" @click="open = !open">
      参考来源 ({{ sources.length }})
      <span class="arrow">{{ open ? '▾' : '▸' }}</span>
    </button>
    <div v-if="open" class="list">
      <div v-for="(s, i) in sources" :key="i" class="item">
        <div class="source-name">{{ s.source }}</div>
        <div class="source-text">{{ s.content }}</div>
        <hr v-if="i < sources.length - 1" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
defineProps({ sources: Array });
const open = ref(false);
</script>

<style scoped>
.source-viewer { margin-top: 8px; }
.toggle {
  background: none; border: none; color: #6b7280;
  font-size: 12px; cursor: pointer; padding: 2px 0;
}
.toggle:hover { color: #4f46e5; }
.arrow { font-size: 10px; }
.list { margin-top: 6px; }
.item { font-size: 12px; color: #6b7280; }
.source-name { font-weight: 600; margin-bottom: 2px; }
.source-text { line-height: 1.5; word-break: break-all; }
hr { border: none; border-top: 1px dashed #e5e7eb; margin: 6px 0; }
</style>
