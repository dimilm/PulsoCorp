/**
 * Pull a human-readable error message out of an Axios/Fetch error.
 *
 * The backend returns FastAPI-style payloads (`{detail: "..."}` or
 * `{detail: [{loc, msg, type}, ...]}`) plus the occasional plain string. This
 * helper normalises all of them so call sites do not need their own
 * `error?.response?.data?.detail || ...` chains.
 */
export function extractApiError(error: unknown, fallback: string): string {
  if (!error) return fallback;
  if (typeof error === "string") return error;

  const anyErr = error as {
    response?: { data?: unknown; status?: number };
    message?: string;
  };
  const data = anyErr.response?.data;

  if (typeof data === "string" && data.trim()) return data;
  if (data && typeof data === "object") {
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((entry: unknown) => {
          if (entry && typeof entry === "object") {
            const obj = entry as { msg?: unknown; message?: unknown };
            if (typeof obj.msg === "string") return obj.msg;
            if (typeof obj.message === "string") return obj.message;
          }
          return null;
        })
        .filter((s): s is string => Boolean(s));
      if (messages.length) return messages.join(" | ");
    }
    const message = (data as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  if (anyErr.message) return anyErr.message;
  return fallback;
}
