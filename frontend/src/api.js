const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // response wasn't JSON; fall back to statusText
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return null;
  return res.json();
}

function withIds(params, ids) {
  for (const id of ids || []) params.append("ids", id);
  return params;
}

export function listDocuments() {
  return request("/documents");
}

export function getDocument(docId) {
  return request(`/documents/${docId}`);
}

export function createDocument({ title, content }) {
  return request("/documents", {
    method: "POST",
    body: JSON.stringify({ title, content }),
  });
}

export function patchDocument(docId, { changes, preview }) {
  return request(`/documents/${docId}`, {
    method: "PATCH",
    body: JSON.stringify({ changes, preview: !!preview }),
  });
}

export function searchDocuments({ q, ids, limit = 20, offset = 0 }) {
  const params = withIds(new URLSearchParams({ q, limit, offset }), ids);
  return request(`/documents/search?${params.toString()}`);
}

export function bulkChangeDocuments({ filter, changes, preview }) {
  return request("/documents/bulk-changes", {
    method: "POST",
    body: JSON.stringify({ filter, changes, preview: !!preview }),
  });
}
