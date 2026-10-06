"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { ScoreBar } from "@/components/ScoreBar";
import { StatusPill } from "@/components/StatusPill";
import { api, IncidentDetail } from "@/lib/api";

export default function IncidentPage() {
  const params = useParams<{ id: string }>();
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState("Approved after reviewing evidence bundle");
  const [pending, startTransition] = useTransition();

  async function load() {
    const data = await api.incident(params.id);
    setIncident(data);
  }

  useEffect(() => {
    load().catch((e) => setError(String(e.message || e)));
  }, [params.id]);

  function decide(actionId: string, approved: boolean) {
    startTransition(async () => {
      try {
        await api.decide(params.id, actionId, {
          approved,
          decided_by: "oncall-engineer",
          notes,
        });
        await load();
      } catch (err) {
        setError(String((err as Error).message || err));
      }
    });
  }

  if (error) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <p className="rounded-xl bg-red-50 p-4 font-mono text-sm text-danger">{error}</p>
        <Link href="/" className="mt-6 inline-block text-sm text-copper underline">
          Back to console
        </Link>
      </main>
    );
  }

  if (!incident) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <div className="h-2 w-48 animate-pulsebar rounded-full bg-signal/50" />
        <p className="mt-4 font-mono text-sm text-moss/60">Loading incident workspace…</p>
      </main>
    );
  }

  const primary = incident.hypotheses.find((h) => h.is_primary) || incident.hypotheses[0];

  return (
    <main className="mx-auto max-w-6xl px-6 pb-20 pt-8">
      <Link href="/" className="font-mono text-xs uppercase tracking-[0.2em] text-copper">
        ← OpsPilot console
      </Link>

      <header className="animate-rise mt-6 flex flex-col gap-4 border-b border-ink/10 pb-8 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill value={incident.severity} />
            <StatusPill value={incident.status} />
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight md:text-4xl">
            {incident.title}
          </h1>
          <p className="mt-2 font-mono text-sm text-moss/65">
            {incident.service_name}
            {incident.root_cause ? ` · root cause: ${incident.root_cause}` : ""}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            startTransition(async () => {
              try {
                const report = await api.report(incident.id);
                const blob = new Blob([report.markdown], { type: "text/markdown" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `opspilot-${incident.id}.md`;
                a.click();
                URL.revokeObjectURL(url);
              } catch (err) {
                setError(String((err as Error).message || err));
              }
            });
          }}
          className="rounded-xl border border-ink/15 bg-white/70 px-4 py-2 text-sm hover:bg-mist/50"
        >
          Export report
        </button>
      </header>

      <section className="animate-rise mt-8 grid gap-6 lg:grid-cols-3" style={{ animationDelay: "60ms" }}>
        <div className="rounded-2xl border border-ink/10 bg-white/70 p-5 shadow-panel lg:col-span-2">
          <h2 className="text-lg font-semibold">Investigation summary</h2>
          <p className="mt-3 text-sm leading-relaxed text-moss/80">
            {incident.summary || "Investigation in progress."}
          </p>
          {primary ? (
            <div className="mt-5 rounded-xl bg-mist/50 p-4">
              <p className="font-mono text-[11px] uppercase tracking-wider text-moss/60">
                Primary hypothesis
              </p>
              <p className="mt-1 font-medium">{primary.title}</p>
              <p className="mt-2 text-sm text-moss/75">{primary.description}</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <ScoreBar score={primary.evidence_score} label="Evidence" />
                <ScoreBar score={primary.confidence} label="Confidence" />
              </div>
              {primary.critic_notes ? (
                <p className="mt-3 font-mono text-xs text-copper">{primary.critic_notes}</p>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="rounded-2xl border border-ink/10 bg-ink p-5 text-sand shadow-panel">
          <h2 className="text-lg font-semibold text-white">Agent trace</h2>
          <ol className="mt-4 space-y-3">
            {(incident.agent_trace?.steps || []).map((step, idx) => (
              <li key={idx} className="border-l border-signal/40 pl-3">
                <p className="font-mono text-[11px] uppercase tracking-wider text-mist/70">
                  {String(step.node)}
                </p>
                <p className="mt-1 text-xs text-sand/70">
                  {JSON.stringify(step.detail).slice(0, 140)}
                  {JSON.stringify(step.detail).length > 140 ? "…" : ""}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-2">
        <div className="animate-rise rounded-2xl border border-ink/10 bg-white/70 p-5 shadow-panel" style={{ animationDelay: "100ms" }}>
          <h2 className="text-lg font-semibold">Timeline</h2>
          <ul className="mt-4 max-h-[420px] space-y-3 overflow-auto pr-2">
            {incident.timeline.map((ev) => (
              <li key={ev.id} className="rounded-xl bg-sand/40 px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[11px] text-moss/55">
                    {new Date(ev.event_time).toLocaleString()}
                  </span>
                  <span className="font-mono text-[10px] uppercase text-copper">
                    {ev.source}/{ev.kind}
                  </span>
                </div>
                <p className="mt-1 text-sm">{ev.message}</p>
              </li>
            ))}
          </ul>
        </div>

        <div className="animate-rise rounded-2xl border border-ink/10 bg-white/70 p-5 shadow-panel" style={{ animationDelay: "140ms" }}>
          <h2 className="text-lg font-semibold">Ranked hypotheses</h2>
          <ul className="mt-4 space-y-4">
            {incident.hypotheses.map((h) => (
              <li key={h.id} className="rounded-xl border border-ink/8 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">
                      #{h.rank} {h.title}
                      {h.is_primary ? " · primary" : ""}
                    </p>
                    <p className="mt-1 text-sm text-moss/70">{h.description}</p>
                  </div>
                  <span className="font-mono text-xs text-signal">
                    {Math.round(h.evidence_score * 100)}%
                  </span>
                </div>
                <div className="mt-3">
                  <ScoreBar score={h.evidence_score} />
                </div>
                {h.supporting_evidence?.length ? (
                  <ul className="mt-3 space-y-1">
                    {h.supporting_evidence.slice(0, 3).map((e, i) => (
                      <li key={i} className="font-mono text-[11px] text-moss/60">
                        • {e.message || JSON.stringify(e)}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="animate-rise mt-8 rounded-2xl border border-ink/10 bg-white/75 p-5 shadow-panel" style={{ animationDelay: "180ms" }}>
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Remediation approval gate</h2>
            <p className="mt-1 text-sm text-moss/70">
              Write actions stay proposed until an on-call engineer explicitly approves.
            </p>
          </div>
          <label className="block w-full md:max-w-sm">
            <span className="font-mono text-[11px] uppercase tracking-wider text-moss/55">
              Decision notes
            </span>
            <input
              className="mt-1 w-full rounded-xl border border-ink/15 bg-sand/30 px-3 py-2 text-sm outline-none ring-signal focus:ring-2"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </label>
        </div>

        <ul className="mt-6 space-y-4">
          {incident.actions.map((action) => (
            <li
              key={action.id}
              className="rounded-xl border border-ink/10 bg-sand/20 p-4 md:flex md:items-start md:justify-between md:gap-6"
            >
              <div className="max-w-2xl">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusPill value={action.status} />
                  <StatusPill value={action.risk_level} />
                  <span className="font-mono text-[11px] uppercase text-moss/50">
                    {action.action_type}
                  </span>
                </div>
                <p className="mt-2 font-medium">{action.title}</p>
                <p className="mt-1 text-sm text-moss/75">{action.description}</p>
                <p className="mt-2 font-mono text-xs text-moss/55">
                  target: {action.target_service}
                </p>
                <p className="mt-1 text-sm text-moss/70">
                  <span className="font-medium">Rollback:</span> {action.rollback_plan}
                </p>
                {action.execution_result?.message ? (
                  <p className="mt-2 rounded-lg bg-mist/60 px-3 py-2 font-mono text-xs">
                    {String(action.execution_result.message)}
                  </p>
                ) : null}
              </div>

              {action.status === "proposed" ? (
                <div className="mt-4 flex shrink-0 gap-2 md:mt-0 md:flex-col">
                  <button
                    disabled={pending}
                    onClick={() => decide(action.id, true)}
                    className="rounded-xl bg-signal px-4 py-2 text-sm font-medium text-white hover:brightness-110 disabled:opacity-50"
                  >
                    Approve & execute
                  </button>
                  <button
                    disabled={pending}
                    onClick={() => decide(action.id, false)}
                    className="rounded-xl border border-ink/20 bg-white px-4 py-2 text-sm hover:bg-stone-50 disabled:opacity-50"
                  >
                    Reject
                  </button>
                </div>
              ) : (
                <p className="mt-4 font-mono text-xs text-moss/55 md:mt-0">
                  decided by {action.decided_by || "—"}
                </p>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-ink/10 bg-white/70 p-5">
          <h2 className="text-lg font-semibold">Audit trail</h2>
          <ul className="mt-4 space-y-2">
            {incident.audit_logs.map((log) => (
              <li key={log.id} className="rounded-lg bg-sand/30 px-3 py-2 font-mono text-[11px]">
                <span className="text-copper">{new Date(log.created_at).toLocaleString()}</span>
                {" · "}
                <span>{log.actor}</span>
                {" · "}
                <span>{log.action}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-2xl border border-ink/10 bg-white/70 p-5">
          <h2 className="text-lg font-semibold">Incident report</h2>
          <pre className="mt-4 max-h-[360px] overflow-auto whitespace-pre-wrap rounded-xl bg-ink p-4 font-mono text-[11px] leading-relaxed text-sand">
            {incident.report_markdown || "Report not generated."}
          </pre>
        </div>
      </section>
    </main>
  );
}
