import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Button from "../components/Button";
import GlassCard from "../components/GlassCard";
import Loader from "../components/Loader";
import { createNote, getNotes } from "../services/api";

export default function Notes() {
  const [draft, setDraft] = useState("");
  const queryClient = useQueryClient();
  const notesQuery = useQuery({ queryKey: ["notes"], queryFn: getNotes });
  const createNoteMutation = useMutation({
    mutationFn: createNote,
    onSuccess: (created) => {
      if (!created) return;
      queryClient.setQueryData(["notes"], (prev = []) => [created, ...prev]);
    },
  });

  const saving = createNoteMutation.isPending;

  const notes = notesQuery.data || [];

  async function handleAdd() {
    const content = draft.trim();
    if (!content || saving) return;
    await createNoteMutation.mutateAsync(content);
    setDraft("");
  }

  function handleLocalDelete(id) {
    queryClient.setQueryData(["notes"], (prev = []) => prev.filter((note) => note.id !== id));
  }

  function handleLocalEdit(id, content) {
    queryClient.setQueryData(["notes"], (prev = []) =>
      prev.map((note) => (note.id === id ? { ...note, content } : note)),
    );
  }

  return (
    <div className="space-y-4">
      <GlassCard>
        <div className="flex flex-col gap-3 md:flex-row">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
            placeholder="Write a note..."
            className="flex-1 rounded-2xl border border-white/15 bg-slate-900/70 px-4 py-3 text-sm text-white outline-none ring-cyan-300/40 focus:ring"
          />
          <div className="flex items-end">
            <Button onClick={handleAdd} disabled={saving || !draft.trim()}>
              {saving ? "Saving..." : "Add Note"}
            </Button>
          </div>
        </div>
      </GlassCard>

      {notesQuery.isLoading ? (
        <GlassCard>
          <Loader label="Loading notes" />
        </GlassCard>
      ) : notesQuery.isError ? (
        <GlassCard>
          <p className="text-sm text-rose-300">Failed to load notes.</p>
        </GlassCard>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <AnimatePresence>
            {notes.map((note) => (
              <motion.div
                key={note.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
              >
                <GlassCard className="h-full" hover={false}>
                  <textarea
                    defaultValue={note.content}
                    onBlur={(e) => handleLocalEdit(note.id, e.target.value)}
                    className="min-h-28 w-full resize-y rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-slate-100 outline-none"
                  />
                  <div className="mt-3 flex justify-end">
                    <button
                      onClick={() => handleLocalDelete(note.id)}
                      className="rounded-lg border border-rose-300/30 px-2 py-1 text-xs text-rose-200 hover:bg-rose-400/10"
                    >
                      Delete (Local)
                    </button>
                  </div>
                </GlassCard>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
