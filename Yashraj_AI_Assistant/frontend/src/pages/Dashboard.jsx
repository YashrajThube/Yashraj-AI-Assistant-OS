import { memo, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BadgeCheck,
  BrainCircuit,
  CalendarCheck2,
  CalendarClock,
  CheckCircle2,
  Clock3,
  Gauge,
  Layers3,
  MessageSquareText,
  NotebookPen,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  TimerReset,
  ChevronRight,
} from "lucide-react";
import GlassCard from "../components/GlassCard";
import Loader from "../components/Loader";
import { getAnalytics, getEvents, getNotes } from "../services/api";

const IST_TIME_ZONE = "Asia/Kolkata";

const StatCard = memo(function StatCard({ title, value, icon: Icon, subtext, tone, accent, trend }) {
  return (
    <GlassCard className="relative h-full overflow-hidden border border-white/10 bg-slate-950/40">
      <div className={`absolute inset-0 bg-gradient-to-br ${accent}`} />
      <div className={`absolute -right-8 -top-8 h-24 w-24 rounded-full blur-2xl ${tone}`} />
      <div className="relative flex h-full flex-col justify-between gap-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm text-slate-300">{title}</p>
            <AnimatedValue value={value} />
            {subtext ? <p className="mt-2 text-xs uppercase tracking-[0.2em] text-slate-400">{subtext}</p> : null}
          </div>
          <Icon className="text-cyan-200" size={22} />
        </div>
        {trend ? (
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.22em] text-slate-200">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-300 shadow-[0_0_18px_rgba(34,211,238,0.8)]" />
            {trend}
          </div>
        ) : null}
      </div>
    </GlassCard>
  );
});

const AnimatedValue = memo(function AnimatedValue({ value }) {
  const [displayValue, setDisplayValue] = useState(value);

  useEffect(() => {
    const raw = typeof value === "number" ? String(value) : String(value ?? "");
    const match = raw.match(/^(\d+(?:\.\d+)?)(.*)$/);
    if (!match) {
      setDisplayValue(value);
      return undefined;
    }

    const target = Number(match[1]);
    const suffix = match[2] || "";
    const duration = 650;
    const startTime = window.performance.now();

    const tick = (currentTime) => {
      const progress = Math.min(1, (currentTime - startTime) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = target * eased;
      const rendered = `${Number.isInteger(target) ? Math.round(current) : current.toFixed(1)}${suffix}`;
      setDisplayValue(rendered);
      if (progress < 1) {
        window.requestAnimationFrame(tick);
      }
    };

    window.requestAnimationFrame(tick);
    return undefined;
  }, [value]);

  return <p className="mt-2 text-3xl font-semibold text-white">{displayValue}</p>;
});

const MiniStat = memo(function MiniStat({ label, value, icon: Icon, tone }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4 transition-all duration-200 hover:border-cyan-300/30 hover:bg-white/[0.07]">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">{label}</p>
          <p className="mt-2 text-xl font-semibold text-white">{value}</p>
        </div>
        <div className={`rounded-full p-2 ${tone}`}>
          <Icon size={16} />
        </div>
      </div>
    </div>
  );
});

const BarRow = memo(function BarRow({ label, value, total = 1, tone = "bg-cyan-400" }) {
  const percent = Math.max(0, Math.min(100, Math.round((value / total) * 100)));
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
        <span>{label}</span>
        <span>{value}</span>
      </div>
      <div className="h-2 rounded-full bg-white/10">
        <div className={`h-2 rounded-full ${tone}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
});

function parseDate(value) {
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatIstDateTime(value) {
  const date = parseDate(value);
  if (!date) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: IST_TIME_ZONE,
    day: "2-digit",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(date);
}

function formatIstDay(value) {
  const date = parseDate(value);
  if (!date) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: IST_TIME_ZONE,
    weekday: "long",
    month: "short",
    day: "numeric",
  }).format(date);
}

function getIstDateKey(value) {
  const date = parseDate(value);
  if (!date) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: IST_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const year = parts.find((part) => part.type === "year")?.value;
  const month = parts.find((part) => part.type === "month")?.value;
  const day = parts.find((part) => part.type === "day")?.value;
  return year && month && day ? `${year}-${month}-${day}` : null;
}

function formatDurationMinutes(startValue, endValue) {
  const start = parseDate(startValue);
  const end = parseDate(endValue);
  if (!start || !end) return 0;
  return Math.max(0, Math.round((end.getTime() - start.getTime()) / 60000));
}

function buildActivitySummary(event) {
  const syncStatus = String(event.sync_status || "pending");
  const duration = formatDurationMinutes(event.start_time || event.start, event.end_time || event.end);
  const attendees = getAttendees(event);
  if (syncStatus === "synced") {
    return duration > 0
      ? `Synced to Google Calendar. ${duration}-minute block with ${attendees.length ? attendees.join(", ") : "no captured attendees"}.`
      : `Synced to Google Calendar with ${attendees.length ? attendees.join(", ") : "no captured attendees"}.`;
  }
  return "Awaiting Google sync and final visibility confirmation.";
}

function getAttendees(event) {
  if (Array.isArray(event.attendees) && event.attendees.length > 0) {
    return event.attendees;
  }
  const title = String(event.title || "");
  const match = title.match(/\bwith\s+(.+)$/i);
  if (!match) return [];
  return [match[1].replace(/\b(?:for|on|at|to|tomorrow|today|next week|next month)\b.*$/i, "").trim()].filter(Boolean);
}

function normalizeCategory(value = "general") {
  return String(value).replace(/_/g, " ");
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "morning";
  if (hour < 18) return "afternoon";
  return "evening";
}

function buildGroupedEvents(events) {
  const now = new Date();
  const todayKey = getIstDateKey(now);
  const tomorrowDate = new Date(now);
  tomorrowDate.setDate(tomorrowDate.getDate() + 1);
  const tomorrowKey = getIstDateKey(tomorrowDate);

  const grouped = { Today: [], Tomorrow: [], "This Week": [], Completed: [] };
  const sorted = [...events].sort((left, right) => {
    const leftStart = parseDate(left.start_time || left.start || 0)?.getTime() || 0;
    const rightStart = parseDate(right.start_time || right.start || 0)?.getTime() || 0;
    return leftStart - rightStart;
  });

  const seenIds = new Set();
  sorted.forEach((event) => {
    const eventId = event.id || `${event.title}-${event.start_time || event.start}-${event.end_time || event.end}`;
    if (seenIds.has(eventId)) return;
    seenIds.add(eventId);

    const start = parseDate(event.start_time || event.start);
    const end = parseDate(event.end_time || event.end);
    const key = start ? getIstDateKey(start) : null;

    if (end && end < now) {
      grouped.Completed.push(event);
      return;
    }
    if (key && key === todayKey) {
      grouped.Today.push(event);
      return;
    }
    if (key && key === tomorrowKey) {
      grouped.Tomorrow.push(event);
      return;
    }
    grouped["This Week"].push(event);
  });

  return grouped;
}

const ActivityCard = memo(function ActivityCard({ event, idx }) {
  const title = String(event.title || "Untitled meeting");
  const start = event.start_time || event.start;
  const end = event.end_time || event.end;
  const duration = formatDurationMinutes(start, end);
  const attendees = getAttendees(event);
  const syncStatus = String(event.sync_status || "pending");
  const category = normalizeCategory(event.event_type_label || event.event_type || "general");
  const isSynced = syncStatus === "synced";
  const summary = buildActivitySummary(event);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: idx * 0.04 }}
      className="group relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.05] p-4 shadow-lg shadow-slate-950/20 backdrop-blur-xl transition-all duration-200 hover:-translate-y-0.5 hover:border-cyan-300/30 hover:bg-white/[0.08]"
    >
      <div className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset ring-white/5 transition-opacity group-hover:ring-cyan-300/30" />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-cyan-300/20 bg-cyan-400/10 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.22em] text-cyan-100">
              {category}
            </span>
            <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.22em] ${isSynced ? "border border-emerald-300/20 bg-emerald-400/10 text-emerald-100" : "border border-amber-300/20 bg-amber-400/10 text-amber-100"}`}>
              {isSynced ? "Synced" : syncStatus.replace(/_/g, " ")}
            </span>
          </div>
          <h4 className="truncate text-base font-semibold text-white sm:text-lg">{title}</h4>
          <p className="text-sm text-slate-300">{formatIstDateTime(start)} {end ? `- ${formatIstDateTime(end)}` : ""}</p>
          <div className="flex flex-wrap gap-3 text-xs text-slate-400">
            <span className="inline-flex items-center gap-1.5"><CalendarClock size={12} /> {duration ? `${duration} min` : "Duration n/a"}</span>
            <span className="inline-flex items-center gap-1.5"><BadgeCheck size={12} /> {attendees.length ? attendees.join(", ") : "No attendees captured"}</span>
          </div>
          <p className="max-w-3xl text-sm leading-6 text-slate-300">{summary}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2 self-start rounded-full border border-white/10 bg-slate-950/40 px-3 py-2 text-xs text-slate-200 shadow-inner shadow-black/20">
          <ShieldCheck size={14} className={isSynced ? "text-emerald-300" : "text-amber-300"} />
          <span>{isSynced ? "Google sync completed" : "Awaiting Google sync"}</span>
        </div>
      </div>
    </motion.div>
  );
});

const Toast = memo(function Toast({ toast }) {
  if (!toast) return null;
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 12 }}
      className="fixed right-4 top-4 z-50 max-w-sm rounded-2xl border border-white/10 bg-slate-950/95 px-4 py-3 text-sm text-slate-100 shadow-2xl shadow-black/40 backdrop-blur-xl"
    >
      <div className="flex items-start gap-3">
        <CheckCircle2 className="mt-0.5 text-emerald-300" size={18} />
        <div>
          <p className="font-medium text-white">{toast.title}</p>
          <p className="mt-1 text-slate-300">{toast.message}</p>
        </div>
      </div>
    </motion.div>
  );
});

const Dashboard = () => {
  const [toast, setToast] = useState(null);
  const [now, setNow] = useState(() => new Date());
  const eventsQuery = useQuery({ queryKey: ["events"], queryFn: getEvents });
  const notesQuery = useQuery({ queryKey: ["notes"], queryFn: getNotes });
  const analyticsQuery = useQuery({ queryKey: ["analytics"], queryFn: getAnalytics });

  const events = eventsQuery.data || [];
  const notes = notesQuery.data || [];
  const analytics = analyticsQuery.data || {};
  const loading = eventsQuery.isLoading || notesQuery.isLoading || analyticsQuery.isLoading;

  const meetingCategories = analytics.meeting_categories || {};
  const priorityDistribution = analytics.priority_distribution || {};
  const syncHealth = analytics.sync_health || {};
  const freeTime = analytics.free_time_analysis || {};
  const retryStats = analytics.retry_statistics || {};
  const insights = analytics.executive_insights || {};

  const groupedEvents = useMemo(() => buildGroupedEvents(events), [events]);
  const latestNotes = useMemo(() => [...notes].sort((left, right) => (right.id || 0) - (left.id || 0)).slice(0, 3), [notes]);
  const aiUsageCount = useMemo(() => Number(localStorage.getItem("ai_usage_count") || "0"), []);
  const nowIstLabel = useMemo(
    () =>
      new Intl.DateTimeFormat("en-IN", {
        timeZone: IST_TIME_ZONE,
        weekday: "long",
        day: "2-digit",
        month: "short",
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      }).format(now),
    [now],
  );

  useEffect(() => {
    const interval = window.setInterval(() => setNow(new Date()), 60000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!loading && eventsQuery.isSuccess && analyticsQuery.isSuccess && notesQuery.isSuccess) {
      setToast({ title: "Dashboard ready", message: "Analytics, calendar, and AI signals are loaded." });
      const timer = window.setTimeout(() => setToast(null), 2800);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [loading, eventsQuery.isSuccess, analyticsQuery.isSuccess, notesQuery.isSuccess]);

  const upcomingEvents = [...groupedEvents.Today, ...groupedEvents.Tomorrow, ...groupedEvents["This Week"]];
  const nextMeeting = upcomingEvents.find((event) => {
    const end = parseDate(event.end_time || event.end);
    return !end || end >= new Date();
  }) || null;
  const todayCount = groupedEvents.Today.length;
  const upcomingCount = events.filter((event) => {
    const end = parseDate(event.end_time || event.end);
    return !end || end >= new Date();
  }).length;
  const googleConnected = Boolean(syncHealth.synced || 0) && (syncHealth.score || 0) >= 75;
  const topMetrics = [
    { title: "Total Meetings", value: analytics.total_meetings || events.length, icon: CalendarCheck2, tone: "bg-cyan-500/40", accent: "from-cyan-400/20 via-cyan-400/10 to-transparent", trend: "Live total" },
    { title: "Upcoming Meetings", value: upcomingCount, icon: CalendarClock, tone: "bg-emerald-500/40", accent: "from-emerald-400/20 via-emerald-400/10 to-transparent", trend: upcomingCount > 0 ? "Active schedule" : "No upcoming events" },
    { title: "Productivity Score", value: `${analytics.productivity_score || 0}%`, icon: Gauge, tone: "bg-indigo-500/40", accent: "from-indigo-400/20 via-indigo-400/10 to-transparent", trend: (analytics.productivity_score || 0) >= 70 ? "Healthy cadence" : "Needs attention" },
    { title: "AI Suggestions", value: (insights.smart_recommendations || []).length, icon: BrainCircuit, tone: "bg-fuchsia-500/40", accent: "from-fuchsia-400/20 via-fuchsia-400/10 to-transparent", trend: "Actionable guidance" },
    { title: "Calendar Sync Health", value: `${syncHealth.score || 0}%`, icon: Activity, tone: "bg-emerald-500/40", accent: "from-emerald-400/20 via-emerald-400/10 to-transparent", trend: googleConnected ? "Google connected" : "Monitoring sync" },
  ];

  const quickActions = [
    { label: "Create meeting", icon: Plus, tone: "bg-cyan-400/15 text-cyan-100" },
    { label: "Refresh sync", icon: RefreshCw, tone: "bg-emerald-400/15 text-emerald-100" },
    { label: "AI assistant", icon: BrainCircuit, tone: "bg-fuchsia-400/15 text-fuchsia-100" },
  ];

  return (
    <div className="relative space-y-6 overflow-hidden">
      <Toast toast={toast} />

      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-slate-950/60 p-6 shadow-2xl shadow-black/20 backdrop-blur-xl"
      >
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(45,212,191,0.18),transparent_35%),radial-gradient(circle_at_bottom_left,rgba(168,85,247,0.15),transparent_28%)]" />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.22em] text-cyan-100">
              <Sparkles size={14} /> Executive Command Center
            </div>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                Good {getGreeting()}, Demo User.
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-slate-300 sm:text-base">
                A focused view of meetings, sync health, AI guidance, and productivity performance in one enterprise dashboard.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-sm text-slate-200">
              <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-2">
                <Clock3 size={14} className="text-cyan-200" /> {nowIstLabel}
              </span>
              <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-400/10 px-3 py-2 text-emerald-100">
                <BadgeCheck size={14} /> AI Status: {loading ? "Analyzing" : "Ready"}
              </span>
              <span className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/10 px-3 py-2 text-cyan-100">
                <ShieldCheck size={14} /> Google Sync: {googleConnected ? "Connected" : "Checking"}
              </span>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:min-w-[28rem] xl:grid-cols-1">
            <MiniStat label="Today Meetings" value={todayCount ? `${todayCount} scheduled` : "No meetings today"} icon={CalendarClock} tone="bg-cyan-400/20 text-cyan-100" />
            <MiniStat label="Next Meeting" value={nextMeeting ? formatIstDateTime(nextMeeting.start_time || nextMeeting.start) : "No upcoming meeting"} icon={TimerReset} tone="bg-emerald-400/20 text-emerald-100" />
          </div>
        </div>

        <div className="relative mt-6 flex flex-wrap items-center gap-3">
          {quickActions.map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.label}
                type="button"
                onClick={() => setToast({ title: action.label, message: "Quick actions are ready in the current build." })}
                className={`inline-flex items-center gap-2 rounded-full border border-white/10 px-4 py-2 text-sm font-medium transition-all duration-200 hover:-translate-y-0.5 hover:border-cyan-300/30 ${action.tone}`}
              >
                <Icon size={14} />
                {action.label}
              </button>
            );
          })}
        </div>
      </motion.section>

      {loading ? (
        <GlassCard className="min-h-[12rem] border border-white/10 bg-slate-950/40">
          <div className="space-y-4">
            <Loader label="Loading premium dashboard" />
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              {[0, 1, 2, 3, 4].map((item) => (
                <div key={item} className="h-28 animate-pulse rounded-2xl border border-white/8 bg-white/5" />
              ))}
            </div>
          </div>
        </GlassCard>
      ) : (
        <div className="space-y-6">
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {topMetrics.map((metric) => (
              <StatCard
                key={metric.title}
                {...metric}
                subtext={metric.title === "AI Suggestions" ? "Generated recommendations" : metric.title === "Calendar Sync Health" ? "Google Calendar status" : undefined}
              />
            ))}
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.45fr_0.95fr]">
            <GlassCard className="min-h-full border border-white/10 bg-slate-950/40 p-0">
              <div className="border-b border-white/10 px-5 py-4 sm:px-6">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Calendar Insights</p>
                    <h3 className="mt-2 text-xl font-semibold text-white">Production scheduling intelligence</h3>
                    <p className="mt-1 text-sm text-slate-300">High-signal view of the day, next meeting, busiest patterns, and AI recommendations.</p>
                  </div>
                  <div className="flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/10 px-3 py-2 text-xs font-medium text-cyan-100">
                    <Layers3 size={14} /> {analytics.total_meetings || events.length} total meetings
                  </div>
                </div>
              </div>

              <div className="grid gap-4 px-5 py-5 sm:px-6 lg:grid-cols-2">
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Today Meetings</p>
                  <p className="mt-2 text-3xl font-semibold text-white">{todayCount}</p>
                  <p className="mt-2 text-sm text-slate-300">{todayCount ? "Meetings scheduled for today in IST." : "No meetings scheduled today."}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Next Meeting</p>
                  <p className="mt-2 text-lg font-semibold text-white">{nextMeeting ? nextMeeting.title || "Untitled meeting" : "No upcoming meeting"}</p>
                  <p className="mt-2 text-sm text-slate-300">{nextMeeting ? formatIstDateTime(nextMeeting.start_time || nextMeeting.start) : "Add a meeting to see the next slot."}</p>
                </div>
              </div>

              <div className="grid gap-4 px-5 pb-5 sm:px-6 md:grid-cols-2">
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Busiest Day</p>
                  <p className="mt-2 text-lg font-semibold text-white">{analytics.busiest_day ? formatIstDay(analytics.busiest_day) : "N/A"}</p>
                  <p className="mt-2 text-sm text-slate-300">Peak collaboration day based on current event load.</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Sync Indicators</p>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <MiniStat label="Synced" value={syncHealth.synced || 0} icon={CheckCircle2} tone="bg-emerald-400/20 text-emerald-100" />
                    <MiniStat label="Retry Queue" value={retryStats.pending || 0} icon={RefreshCw} tone="bg-amber-400/20 text-amber-100" />
                  </div>
                </div>
              </div>

              <div className="grid gap-4 px-5 pb-5 sm:px-6 lg:grid-cols-2">
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-400">AI Recommendations</p>
                  <div className="mt-3 space-y-2 text-sm text-slate-200">
                    {(insights.smart_recommendations || ["No AI recommendations yet."]).map((item, idx) => (
                      <div key={idx} className="rounded-xl border border-white/5 bg-slate-950/30 px-3 py-2 transition-colors hover:border-cyan-300/20">
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Meetings by Category</p>
                  <div className="mt-4 space-y-3">
                    {Object.keys(meetingCategories).length === 0 ? <p className="text-sm text-slate-400">No meetings yet.</p> : null}
                    {Object.entries(meetingCategories).map(([key, value]) => (
                      <BarRow key={key} label={key.replace(/_/g, " ")} value={value} total={analytics.total_meetings || 1} tone="bg-cyan-400" />
                    ))}
                  </div>
                </div>
              </div>
            </GlassCard>

            <div className="space-y-6">
              <GlassCard className="border border-white/10 bg-slate-950/40">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Productivity Summary</p>
                    <h3 className="mt-2 text-xl font-semibold text-white">Daily performance snapshot</h3>
                  </div>
                  <Gauge className="text-cyan-200" size={20} />
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                  <MiniStat label="Productivity Score" value={`${analytics.productivity_score || 0}%`} icon={Gauge} tone="bg-indigo-400/20 text-indigo-100" />
                  <MiniStat label="Focus Time Score" value={`${insights.focus_time_score || 0}/100`} icon={BrainCircuit} tone="bg-fuchsia-400/20 text-fuchsia-100" />
                  <MiniStat label="AI Requests" value={aiUsageCount} icon={MessageSquareText} tone="bg-cyan-400/20 text-cyan-100" />
                  <MiniStat label="Free Minutes" value={`${freeTime.estimated_free_minutes || 0}`} icon={TimerReset} tone="bg-emerald-400/20 text-emerald-100" />
                </div>
              </GlassCard>

              <GlassCard className="border border-white/10 bg-slate-950/40">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-400">AI Signals</p>
                    <h3 className="mt-2 text-lg font-semibold text-white">Recommendations and alerts</h3>
                  </div>
                  <NotebookPen className="text-fuchsia-200" size={18} />
                </div>
                <div className="mt-4 space-y-3">
                  <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                    <p className="text-sm text-slate-400">Burnout Risk</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{(insights.burnout_risk || "low").toUpperCase()}</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                    <p className="text-sm text-slate-400">Priority Distribution</p>
                    <div className="mt-3 space-y-3">
                      <BarRow label="High Priority" value={priorityDistribution.high || 0} total={analytics.total_meetings || 1} tone="bg-rose-400" />
                      <BarRow label="Normal" value={priorityDistribution.normal || 0} total={analytics.total_meetings || 1} tone="bg-emerald-400" />
                    </div>
                  </div>
                </div>
              </GlassCard>
            </div>
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
            <GlassCard className="border border-white/10 bg-slate-950/40 p-0">
              <div className="border-b border-white/10 px-5 py-4 sm:px-6">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Upcoming Activity</p>
                    <h3 className="mt-2 text-xl font-semibold text-white">Chronological agenda</h3>
                  </div>
                  <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-200">
                    <Sparkles size={14} /> IST formatted
                  </span>
                </div>
              </div>

              <div className="space-y-5 px-5 py-5 sm:px-6">
                {[
                  ["Today", groupedEvents.Today],
                  ["Tomorrow", groupedEvents.Tomorrow],
                  ["This Week", groupedEvents["This Week"]],
                  ["Completed", groupedEvents.Completed],
                ].map(([groupLabel, groupEvents]) => (
                  <div key={groupLabel} className="space-y-3">
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-2">
                        <div className="h-2.5 w-2.5 rounded-full bg-cyan-300 shadow-[0_0_20px_rgba(34,211,238,0.7)]" />
                        <h4 className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-300">{groupLabel}</h4>
                      </div>
                      <span className="text-xs text-slate-500">{groupEvents.length} item{groupEvents.length === 1 ? "" : "s"}</span>
                    </div>
                    <div className="space-y-3">
                      {groupEvents.length === 0 ? <p className="text-sm text-slate-400">No events in this group.</p> : null}
                      {groupEvents.map((event, idx) => (
                        <ActivityCard key={event.id || `${event.title}-${idx}`} event={event} idx={idx} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>

            <div className="space-y-6">
              <GlassCard className="border border-white/10 bg-slate-950/40">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Alerts</p>
                    <h3 className="mt-2 text-lg font-semibold text-white">Operational status</h3>
                  </div>
                  <Activity size={18} className="text-cyan-200" />
                </div>
                <div className="mt-4 space-y-3">
                  <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                    <p className="text-sm text-slate-400">Google sync health</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{syncHealth.score || 0}%</p>
                    <p className="mt-1 text-sm text-slate-300">{googleConnected ? "Connected and syncing" : "Waiting for sync confirmation"}</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                    <p className="text-sm text-slate-400">Retry queue</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{retryStats.pending || 0}</p>
                    <p className="mt-1 text-sm text-slate-300">Automatic retry pipeline is active.</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                    <p className="text-sm text-slate-400">Free time</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{freeTime.estimated_free_minutes || 0} min</p>
                    <p className="mt-1 text-sm text-slate-300">Working hours capacity for the current window.</p>
                  </div>
                </div>
              </GlassCard>

              <GlassCard className="border border-white/10 bg-slate-950/40">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Latest Notes</p>
                    <h3 className="mt-2 text-lg font-semibold text-white">Recent executive notes</h3>
                  </div>
                  <NotebookPen size={18} className="text-fuchsia-200" />
                </div>
                <div className="mt-4 space-y-3">
                  {latestNotes.length === 0 && <p className="text-sm text-slate-400">No notes yet.</p>}
                  {latestNotes.map((note, idx) => (
                    <motion.div
                      key={note.id || idx}
                      initial={{ opacity: 0, x: 6 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.06 }}
                      className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 transition-all duration-200 hover:border-fuchsia-300/30 hover:bg-white/[0.07]"
                    >
                      <p className="line-clamp-4 text-sm leading-6 text-slate-200">{note.content}</p>
                    </motion.div>
                  ))}
                </div>
              </GlassCard>
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <StatCard title="AI Requests" value={aiUsageCount} icon={MessageSquareText} tone="bg-fuchsia-500/40" accent="from-fuchsia-400/20 via-fuchsia-400/10 to-transparent" />
            <StatCard title="Calendar Sync Health" value={`${syncHealth.score || 0}%`} icon={ShieldCheck} tone="bg-emerald-500/40" accent="from-emerald-400/20 via-emerald-400/10 to-transparent" />
            <StatCard title="Upcoming Meetings" value={upcomingCount} icon={ChevronRight} tone="bg-cyan-500/40" accent="from-cyan-400/20 via-cyan-400/10 to-transparent" />
          </section>
        </div>
      )}
    </div>
  );
};

export default Dashboard;