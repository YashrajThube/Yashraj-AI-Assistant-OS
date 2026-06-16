import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useMutation } from "@tanstack/react-query";
import ChatBubble from "../components/ChatBubble";
import Button from "../components/Button";
import GlassCard from "../components/GlassCard";
import { ApiError, sendMessage } from "../services/api";

function streamText(target, onUpdate) {
  return new Promise((resolve) => {
    let index = 0;
    const speed = 12;
    const timer = setInterval(() => {
      index += 1;
      onUpdate(target.slice(0, index));
      if (index >= target.length) {
        clearInterval(timer);
        resolve();
      }
    }, speed);
  });
}

function describeError(error) {
  if (!error) return "Unknown error";

  const backendResponse = error?.payload?.data?.response;
  if (backendResponse) return backendResponse;

  const diagnostic = error?.payload?.data?.diagnostic;
  if (diagnostic?.detail) return diagnostic.detail;

  if (error?.message === "Network Error" || error?.code === "ERR_NETWORK") {
    return "Backend unreachable. Check whether the FastAPI server is running on the configured port.";
  }

  const status = error?.statusCode;
  if (status === 429) return "Rate limited. Please try again shortly.";
  if (status === 503) return "Backend service unavailable. Check API key, Gemini quota, and server logs.";
  if (status === 401 || status === 403) return "Authentication or API key rejected by the backend.";
  if (status === 404) return "API endpoint not found. Check the frontend API base URL or proxy configuration.";

  return error?.message || "Unexpected error";
}

export default function Chat() {
  const [messages, setMessages] = useState([
    { id: crypto.randomUUID(), role: "assistant", content: "Hello. I can schedule events, manage notes, and answer questions." },
  ]);
  const [actionFeed, setActionFeed] = useState([]);
  const [input, setInput] = useState("");
  const endRef = useRef(null);

  const chatMutation = useMutation({
    mutationFn: (message) => sendMessage(message),
    onSuccess: async (result) => {
      const fullText = result?.response || "I could not generate a response.";
      const tempId = crypto.randomUUID();

      localStorage.setItem("ai_usage_count", String(Number(localStorage.getItem("ai_usage_count") || "0") + 1));
      setActionFeed((prev) => [...(result?.actions || []), ...prev].slice(0, 8));
      setMessages((prev) => [...prev, { id: tempId, role: "assistant", content: "" }]);
      await streamText(fullText, (partial) => {
        setMessages((prev) => prev.map((m) => (m.id === tempId ? { ...m, content: partial } : m)));
      });
    },
    onError: async (error) => {
      console.debug("Chat request failed", {
        message: error?.message,
        statusCode: error?.statusCode,
        payload: error?.payload,
      });

      const fallbackText = describeError(error);
      let fallbackActions = [{ type: "chat", status: "failed" }];

      if (error instanceof ApiError && error.payload?.data) {
        if (Array.isArray(error.payload.data.actions) && error.payload.data.actions.length > 0) {
          fallbackActions = error.payload.data.actions;
        }
      }

      setActionFeed((prev) => [...fallbackActions, ...prev].slice(0, 8));

      const tempId = crypto.randomUUID();
      setMessages((prev) => [...prev, { id: tempId, role: "assistant", content: "" }]);
      await streamText(fallbackText, (partial) => {
        setMessages((prev) => prev.map((m) => (m.id === tempId ? { ...m, content: partial } : m)));
      });
    },
  });

  const sending = chatMutation.isPending;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  async function handleSend() {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    const userMessage = { id: crypto.randomUUID(), role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    chatMutation.mutate(trimmed);
  }

  function formatAction(action) {
    const type = action?.type || "action";
    const status = action?.status || "ok";
    if (type === "create_event" && status === "created") return "Event created";
    if (type === "create_note" && status === "saved") return "Note saved";
    if (type === "delete_event" && status === "deleted") return "Event deleted";
    if (status === "failed") return "Action failed";
    return `${type.replaceAll("_", " ")} (${status})`;
  }

  return (
    <GlassCard className="flex h-[72vh] flex-col p-0">
      <div className="border-b border-white/10 px-5 py-4">
        <h3 className="text-lg font-semibold text-white">AI Conversation</h3>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
        {actionFeed.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-2">
            {actionFeed.map((action, idx) => (
              <span
                key={`${action.type || "action"}-${idx}`}
                className={`rounded-full border px-3 py-1 text-xs ${
                  action.status === "failed"
                    ? "border-rose-300/40 bg-rose-400/10 text-rose-200"
                    : "border-emerald-300/40 bg-emerald-400/10 text-emerald-100"
                }`}
              >
                {formatAction(action)}
              </span>
            ))}
          </div>
        )}
        <AnimatePresence>
          {messages.map((msg) => (
            <ChatBubble key={msg.id} role={msg.role} content={msg.content} />
          ))}
        </AnimatePresence>
        {sending && <ChatBubble role="assistant" content="" pending />}
        <div ref={endRef} />
      </div>

      <div className="border-t border-white/10 p-4">
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3">
          <textarea
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask something..."
            className="flex-1 resize-none rounded-2xl border border-white/15 bg-slate-900/70 px-4 py-3 text-sm text-white outline-none ring-cyan-300/40 transition focus:ring"
          />
          <Button onClick={handleSend} disabled={sending || !input.trim()}>
            Send
          </Button>
        </motion.div>
      </div>
    </GlassCard>
  );
}
