import { motion } from "framer-motion";

export default function Button({ children, className = "", disabled = false, type = "button", onClick }) {
  return (
    <motion.button
      type={type}
      whileTap={{ scale: disabled ? 1 : 0.97 }}
      whileHover={disabled ? undefined : { scale: 1.02 }}
      disabled={disabled}
      onClick={onClick}
      className={`glow-button rounded-2xl bg-gradient-to-r from-indigo-500 via-purple-500 to-fuchsia-500 px-4 py-2 font-medium text-white disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {children}
    </motion.button>
  );
}
