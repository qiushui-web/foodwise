export function formatNumber(value: unknown, digits = 1): string {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  return Number.isFinite(number) ? new Intl.NumberFormat("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(number) : "—";
}

/** 站点统一用北京时间展示日期，避免把 UTC 的 `Z` 时间当成当地日期。 */
export function formatDate(value: unknown): string {
  if (!value) return "日期未知";
  const text = String(value);
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text.slice(0, 10);
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Shanghai" }).format(date);
}

export function formatDateTime(value: unknown): string {
  if (!value) return "时间未知";
  const text = String(value);
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text;
  return `${new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", hour12: false,
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  }).format(date)}（北京时间）`;
}
