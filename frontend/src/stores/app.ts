import { defineStore } from "pinia";
import { ref } from "vue";

export const useAppStore = defineStore("app", () => {
  const pendingAlertCount = ref(0);
  const operatorName = ref("食堂运营中心");
  const lastError = ref("");

  function setPendingAlertCount(value: number) {
    pendingAlertCount.value = Math.max(0, Number(value) || 0);
  }

  function reportError(message: string) {
    lastError.value = message;
  }

  function clearError() {
    lastError.value = "";
  }

  return { pendingAlertCount, operatorName, lastError, setPendingAlertCount, reportError, clearError };
});
