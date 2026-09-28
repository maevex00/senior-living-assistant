let advisorToken = "";
export function setAdvisorToken(value: string) {
  advisorToken = value;
}
const base = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const isForm = body instanceof FormData;
  const response = await fetch(`${base}/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      ...(!isForm && body !== undefined
        ? { "Content-Type": "application/json" }
        : {}),
      ...(advisorToken ? { Authorization: `Bearer ${advisorToken}` } : {}),
    },
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    signal: AbortSignal.timeout(75000),
  });
  const result = await response
    .json()
    .catch(() => ({
      error: { message: "Service returned an invalid response." },
    }));
  if (!response.ok) throw new Error(result.error?.message || "Request failed.");
  return result;
}
