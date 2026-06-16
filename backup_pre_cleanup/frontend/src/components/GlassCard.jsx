import { motion } from "framer-motion";

export default function GlassCard({ children, className = "", hover = true }) {
  return (
    <motion.div
      whileHover={hover ? { scale: 1.015, y: -3 } : undefined}
      transition={{ duration: 0.22, ease: "easeOut" }}
      className={`glass-card rounded-2xl p-5 shadow-xl shadow-indigo-950/30 ${className}`}
    >
      {children}
    </motion.div>
  );
}
