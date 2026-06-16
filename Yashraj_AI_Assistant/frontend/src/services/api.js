import axios from "axios";

export class ApiError extends Error {
  constructor(message, statusCode = 500, payload = null) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
    this.payload = payload;
  }
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 20000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const statusCode = error?.response?.status || 500;
    const payload = error?.response?.data || null;
    const message = payload?.error || error?.message || "Request failed";
    return Promise.reject(new ApiError(message, statusCode, payload));
  },
);

function normalizeChatResponse(data) {
  return {
    intent: data?.intent || "chat",
    response: data?.response || "I could not generate a response.",
    actions: Array.isArray(data?.actions) ? data.actions : [],
  };
}

export async function sendMessage(message, background = false) {
  const response = await api.post("/assistant/chat", { message }, {
    params: background ? { background_ai: true } : undefined,
  });
  return normalizeChatResponse(response.data?.data || {});
}

export async function getEvents() {
  const response = await api.get("/calendar/events");
  return response.data?.data?.events || [];
}

export async function createEvent(payload) {
  const response = await api.post("/calendar/create", payload);
  return response.data?.data?.event;
}

export async function getNotes() {
  const response = await api.get("/notes");
  return response.data?.data?.notes || [];
}

export async function getAnalytics() {
  const response = await api.get("/analytics/dashboard");
  return response.data?.data?.analytics || {};
}

export async function createNote(content) {
  const response = await api.post("/notes", { content });
  return response.data?.data?.note;
}

export default api;
