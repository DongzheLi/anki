// Thin fetch wrappers around the JSON API. Every call returns parsed JSON; we
// keep this flat rather than building a client abstraction — it's just fetch.

const json = (r) => {
  if (!r.ok) return r.json().then((e) => Promise.reject(new Error(e.error || r.statusText)));
  return r.json();
};
const send = (method) => (url, body) =>
  fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then(json);

const post = send("POST");
const patch = send("PATCH");
const del = send("DELETE");

export const api = {
  tree: () => fetch("/api/tree").then(json),
  taxonomy: () => fetch("/api/taxonomy").then(json),
  stats: () => fetch("/api/stats").then(json),
  due: () => fetch("/api/due").then(json),
  items: () => fetch("/api/items").then(json),
  item: (id) => fetch(`/api/items/${id}`).then(json),

  addCategory: (name) => post("/api/categories", { name }),
  renameCategory: (id, name) => patch(`/api/categories/${id}`, { name }),
  deleteCategory: (id) => del(`/api/categories/${id}`),

  addTopic: (category_id, name) => post("/api/topics", { category_id, name }),
  renameTopic: (id, name) => patch(`/api/topics/${id}`, { name }),
  deleteTopic: (id) => del(`/api/topics/${id}`),

  addItem: (data) => post("/api/items", data),
  updateItem: (id, data) => patch(`/api/items/${id}`, data),
  deleteItem: (id) => del(`/api/items/${id}`),

  practice: (id, data) => post(`/api/items/${id}/practice`, data),
};
