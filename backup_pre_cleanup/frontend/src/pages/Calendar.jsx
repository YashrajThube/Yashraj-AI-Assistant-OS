import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus2, CircleCheckBig, Clock3 } from "lucide-react";
import Button from "../components/Button";
import GlassCard from "../components/GlassCard";
import Loader from "../components/Loader";
import { createEvent, getEvents } from "../services/api";

const TIMEZONE = "Asia/Kolkata";

function formatEventDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: TIMEZONE,
  }).format(date);
}

function formatTimeRange(event) {
  const start = event.start_time || event.start;
  const end = event.end_time || event.end;
  if (!start || !end) return "";
  const startDate = new Date(start);
  const endDate = new Date(end);
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return `${start} to ${end}`;

  const formatter = new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: TIMEZONE,
  });
  return `${formatter.format(startDate)} • ${formatter.format(endDate)}`;
}

function getStatusLabel(status) {
  if (status === "synced") return { label: "Synced", tone: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200" };
  if (status === "retry_pending") return { label: "Sync Pending", tone: "border-amber-400/30 bg-amber-400/10 text-amber-200" };
  return { label: "Pending", tone: "border-slate-400/20 bg-slate-400/10 text-slate-200" };
}

function getPriorityBadge(priority) {
  if (priority === "high") return { label: "High Priority", tone: "border-rose-400/30 bg-rose-400/10 text-rose-200" };
  return { label: "Normal", tone: "border-slate-400/20 bg-slate-400/10 text-slate-200" };
}

function getEventTypeBadge(eventType, eventTypeLabel) {
  const label = eventTypeLabel || eventType || "General";
  const tones = {
    interview: "border-blue-400/30 bg-blue-400/10 text-blue-200",
    client: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
    personal: "border-amber-400/30 bg-amber-400/10 text-amber-200",
    academic: "border-violet-400/30 bg-violet-400/10 text-violet-200",
    standup: "border-slate-400/30 bg-slate-400/10 text-slate-200",
    team_sync: "border-cyan-400/30 bg-cyan-400/10 text-cyan-200",
    project: "border-indigo-400/30 bg-indigo-400/10 text-indigo-200",
    urgent: "border-rose-400/30 bg-rose-400/10 text-rose-200",
    ai_tech: "border-fuchsia-400/30 bg-fuchsia-400/10 text-fuchsia-200",
    meeting: "border-sky-400/30 bg-sky-400/10 text-sky-200",
  };
  return { label, tone: tones[eventType] || "border-slate-400/20 bg-slate-400/10 text-slate-200" };
}

function EventModal({ open, onClose, onSubmit, submitting }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    await onSubmit({ title, description, start_time: startTime, end_time: endTime });
    setTitle("");
    setDescription("");
    setStartTime("");
    setEndTime("");
    onClose();
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4"
        >
          <motion.form
            initial={{ y: 20, opacity: 0, scale: 0.98 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: 20, opacity: 0, scale: 0.98 }}
            onSubmit={handleSubmit}
            className="w-full max-w-lg rounded-2xl border border-white/20 bg-slate-900/95 p-6"
          >
            <h3 className="mb-4 text-lg font-semibold text-white">Create Event</h3>
            <div className="space-y-3">
              <input
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Title"
                className="w-full rounded-xl border border-white/15 bg-slate-900/80 px-3 py-2 text-white"
              />
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Description"
                className="w-full rounded-xl border border-white/15 bg-slate-900/80 px-3 py-2 text-white"
              />
              <input
                required
                type="datetime-local"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                className="w-full rounded-xl border border-white/15 bg-slate-900/80 px-3 py-2 text-white"
              />
              <input
                required
                type="datetime-local"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                className="w-full rounded-xl border border-white/15 bg-slate-900/80 px-3 py-2 text-white"
              />
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={onClose} className="rounded-xl border border-white/20 px-3 py-2 text-slate-200">
                Cancel
              </button>
              <Button type="submit" disabled={submitting}>
                {submitting ? "Saving..." : "Save"}
              </Button>
            </div>
          </motion.form>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default function Calendar() {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const eventsQuery = useQuery({ queryKey: ["events"], queryFn: getEvents });

  const createEventMutation = useMutation({
    mutationFn: createEvent,
    onSuccess: (created) => {
      if (created) {
        queryClient.setQueryData(["events"], (prev = []) => [created, ...prev]);
      } else {
        queryClient.invalidateQueries({ queryKey: ["events"] });
      }
    },
  });

  const submitting = createEventMutation.isPending;

  const events = useMemo(() => {
    const source = eventsQuery.data || [];
    return [...source].sort((a, b) => new Date(a.start_time || a.start).getTime() - new Date(b.start_time || b.start).getTime());
  }, [eventsQuery.data]);

  async function handleCreate(payload) {
    await createEventMutation.mutateAsync(payload);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-300">Manage your timeline in one place.</p>
        <Button onClick={() => setOpen(true)} className="inline-flex items-center gap-2">
          <CalendarPlus2 size={16} /> New Event
        </Button>
      </div>

      <GlassCard>
        {eventsQuery.isLoading ? (
          <Loader label="Loading events" />
        ) : eventsQuery.isError ? (
          <p className="text-sm text-rose-300">Failed to load events.</p>
        ) : events.length === 0 ? (
          <p className="text-sm text-slate-400">No events found.</p>
        ) : (
          <div className="space-y-3">
            <AnimatePresence>
              {events.map((event, idx) => (
                <motion.div
                  key={event.id || `${event.title}-${idx}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  className="group rounded-2xl border border-white/10 bg-gradient-to-br from-slate-950/85 to-slate-900/75 p-4 shadow-[0_12px_40px_rgba(15,23,42,0.25)] transition duration-300 hover:-translate-y-0.5 hover:border-cyan-300/30 hover:shadow-[0_18px_48px_rgba(34,211,238,0.12)]"
                >
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0 flex-1">
                      <p className="text-base font-semibold tracking-wide text-white transition group-hover:text-cyan-100">{event.title}</p>
                      <p className="mt-1 flex items-center gap-2 text-sm text-slate-300">
                        <Clock3 size={14} className="shrink-0 text-cyan-300" />
                        <span>{formatTimeRange(event)}</span>
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${getStatusLabel(event.sync_status).tone}`}>
                          <CircleCheckBig size={12} />
                          {getStatusLabel(event.sync_status).label}
                        </span>
                        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${getPriorityBadge(event.priority).tone}`}>
                          {getPriorityBadge(event.priority).label}
                        </span>
                        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${getEventTypeBadge(event.event_type, event.event_type_label).tone}`}>
                          {getEventTypeBadge(event.event_type, event.event_type_label).label}
                        </span>
                      </div>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-right text-xs uppercase tracking-[0.18em] text-slate-400">
                      {formatEventDateTime(event.created_at || event.start_time || event.start)}
                    </div>
                  </div>
                  <div className="mt-4 rounded-xl border border-white/8 bg-white/5 p-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Structured Description</p>
                    <div className="mt-2 grid gap-2 text-sm text-slate-300 md:grid-cols-2">
                      <div>
                        <span className="text-slate-500">Priority:</span> {event.priority_label || getPriorityBadge(event.priority).label}
                      </div>
                      <div>
                        <span className="text-slate-500">Event Type:</span> {event.event_type_label || getEventTypeBadge(event.event_type, event.event_type_label).label}
                      </div>
                      <div className="md:col-span-2">
                        <span className="text-slate-500">Timezone:</span> {event.timezone || TIMEZONE}
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </GlassCard>

      <EventModal open={open} onClose={() => setOpen(false)} onSubmit={handleCreate} submitting={submitting} />
    </div>
  );
}
