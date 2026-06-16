import { Suspense, lazy, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Bot, CalendarDays, LayoutDashboard, NotebookTabs } from "lucide-react";
import Loader from "./components/Loader";
import Navbar from "./components/Navbar";
import Sidebar from "./components/Sidebar";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Chat = lazy(() => import("./pages/Chat"));
const Calendar = lazy(() => import("./pages/Calendar"));
const Notes = lazy(() => import("./pages/Notes"));

const mobileNav = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "chat", label: "Chat", icon: Bot },
  { key: "calendar", label: "Calendar", icon: CalendarDays },
  { key: "notes", label: "Notes", icon: NotebookTabs },
];

function App() {
  const [activePage, setActivePage] = useState("dashboard");

  const pageMap = useMemo(
    () => ({
      dashboard: { title: "Command Dashboard", component: Dashboard },
      chat: { title: "AI Chat", component: Chat },
      calendar: { title: "Calendar", component: Calendar },
      notes: { title: "Notes", component: Notes },
    }),
    [],
  );

  const ActiveComponent = pageMap[activePage].component;

  return (
    <div className="relative min-h-screen overflow-hidden pb-20 lg:pb-0">
      <div className="pointer-events-none absolute -left-32 top-10 h-72 w-72 rounded-full bg-cyan-500/20 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 bottom-8 h-64 w-64 rounded-full bg-fuchsia-500/20 blur-3xl" />

      <Sidebar activePage={activePage} setActivePage={setActivePage} />

      <main className="relative z-10 px-4 py-5 lg:ml-72 lg:px-8">
        <Navbar title={pageMap[activePage].title} />
        <Suspense fallback={<Loader label="Loading page" />}>
          <AnimatePresence mode="wait">
            <motion.div
              key={activePage}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
            >
              <ActiveComponent />
            </motion.div>
          </AnimatePresence>
        </Suspense>
      </main>

      <nav className="fixed bottom-3 left-1/2 z-40 flex w-[94%] -translate-x-1/2 items-center justify-between rounded-2xl border border-white/15 bg-slate-950/80 p-2 backdrop-blur-xl lg:hidden">
        {mobileNav.map((item) => {
          const Icon = item.icon;
          const active = activePage === item.key;
          return (
            <button
              key={item.key}
              onClick={() => setActivePage(item.key)}
              className={`flex flex-1 flex-col items-center gap-1 rounded-xl px-2 py-2 text-[11px] ${
                active ? "bg-cyan-300/20 text-cyan-100" : "text-slate-300"
              }`}
            >
              <Icon size={16} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}

export default App;
