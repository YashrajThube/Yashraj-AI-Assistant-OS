import { motion } from "framer-motion";

export default function Navbar({ title }) {
  return (
    <motion.header
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="sticky top-0 z-20 mb-6 flex items-center justify-between rounded-2xl border border-white/20 bg-white/10 px-5 py-4 backdrop-blur-xl"
    >
      <h2 className="text-lg font-semibold text-white md:text-xl">{title}</h2>
      <div className="flex items-center gap-3">
        <div className="text-right">
          <p className="text-sm text-slate-200">Product Admin</p>
          <p className="text-xs text-slate-400">Demo User</p>
        </div>
        <div className="h-10 w-10 rounded-full bg-gradient-to-br from-indigo-400 to-fuchsia-500 ring-2 ring-white/30" />
      </div>
    </motion.header>
  );
}
