import { motion } from "framer-motion";
import { Bot, CalendarDays, LayoutDashboard, NotebookTabs } from "lucide-react";

const navItems = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "chat", label: "Chat", icon: Bot },
  { key: "calendar", label: "Calendar", icon: CalendarDays },
  { key: "notes", label: "Notes", icon: NotebookTabs },
];

export default function Sidebar({ activePage, setActivePage }) {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 border-r border-white/15 bg-slate-950/65 p-4 backdrop-blur-2xl lg:block">
      <div className="mb-8 rounded-2xl border border-white/20 bg-white/10 p-4">
        <p className="text-xs uppercase tracking-[0.2em] text-slate-300">Yashraj AI</p>
        <h1 className="mt-1 text-xl font-semibold text-white">Assistant OS</h1>
      </div>

      <nav className="space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = item.key === activePage;
          return (
            <motion.button
              key={item.key}
              whileHover={{ x: 5 }}
              onClick={() => setActivePage(item.key)}
              className={`flex w-full items-center gap-3 rounded-2xl border px-4 py-3 text-left transition ${
                active
                  ? "border-cyan-300/70 bg-cyan-300/20 text-white"
                  : "border-transparent bg-white/5 text-slate-300 hover:border-white/20 hover:bg-white/10"
              }`}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </motion.button>
          );
        })}
      </nav>
    </aside>
  );
}
