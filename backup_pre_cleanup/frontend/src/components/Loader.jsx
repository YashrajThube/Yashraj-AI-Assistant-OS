import { motion } from "framer-motion";

export default function Loader({ label = "Loading..." }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-300">
      <div className="flex gap-1">
        {[0, 1, 2].map((dot) => (
          <motion.span
            key={dot}
            animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 0.8, repeat: Infinity, delay: dot * 0.12 }}
            className="h-1.5 w-1.5 rounded-full bg-cyan-300"
          />
        ))}
      </div>
      <span>{label}</span>
    </div>
  );
}
