import { motion } from "framer-motion";
import Loader from "./Loader";

export default function ChatBubble({ role, content, pending = false }) {
  const isUser = role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-lg ${
          isUser
            ? "bg-gradient-to-r from-indigo-500 to-purple-500 text-white"
            : "glass-card border border-white/20 text-slate-100"
        }`}
      >
        {pending ? <Loader label="AI is typing" /> : <p className="whitespace-pre-wrap">{content}</p>}
      </div>
    </motion.div>
  );
}
