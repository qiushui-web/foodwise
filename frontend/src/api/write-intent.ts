/** Keeps a retry's key until the payload changes or the write succeeds. */
export function createWriteIntent() {
  let signature = "";
  let key = "";
  return {
    key(payload: unknown) {
      const next = JSON.stringify(payload);
      if (!key || signature !== next) { signature = next; key = crypto.randomUUID(); }
      return key;
    },
    complete() { signature = ""; key = ""; },
  };
}
