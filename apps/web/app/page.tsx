"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState, useTransition } from "react";
import { StatusPill } from "@/components/StatusPill";
import { api, IncidentSummary, Scenario } from "@/lib/api";

export default function HomePage() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  async function refresh() {
    const [s, i] = await Promise.all([api.scenarios(), api.incidents()]);
    setScenarios(s);
    setIncidents(i);
    if (!selected && s[0]) setSelected(s[0].id);
  }

  useEffect(() => {
    refresh().catch((e) => setError(String(e.message || e)));
  }, []);

  function onLaunch(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setError(null);
    startTransition(async () => {
      try {
        const incident = await api.createIncident({
          scenario_id: selected,
          auto_investigate: true,
        });
        window.location.href = `/incidents/${incident.id}`;
      } catch (err) {
        setError(String((err as Error).message || err));
      }
    });
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 pb-16 pt-10">
      <header className="animate-rise mb-14">
        <p className="font-mono text-xs uppercase tracking-[0.28em] text-copper">
          AI SRE · Human-in-the-loop
        </p>
        <h1 className="mt-4 max-w-3xl text-5xl font-semibold tracking-tight text-ink md:text-6xl">
          OpsPilot
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-relaxed text-moss/80">
          Turns noisy logs, metrics, and deploys into an evidence-backed incident
          narrative — then waits for your approval before any remediation.
        </p>
        <div className="mt-6 h-1 w-40 origin-left animate-pulsebar rounded-full bg-gradient-to-r from-signal via-copper to-transparent" />
      </header>

      <section className="animate-rise grid gap-8 md:grid-cols-[1.1fr_0.9fr]" style={{ animationDelay: "80ms" }}>
        <form
          onSubmit={onLaunch}
          className="rounded-2xl border border-ink/10 bg-white/70 p-6 shadow-panel backdrop-blur"
        >
          <h2 className="text-xl font-semibold">Launch investigation</h2>
          <p className="mt-2 text-sm text-moss/70">
            Pick a synthetic production scenario. The agent queries telemetry and
            runbooks, ranks root causes, and proposes gated actions.
          </p>

          <label className="mt-6 block font-mono text-[11px] uppercase tracking-wider text-moss/60">
            Scenario
          </label>
          <select
            className="mt-2 w-full rounded-xl border border-ink/15 bg-sand/40 px-3 py-3 text-sm outline-none ring-signal focus:ring-2"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title} · {s.service_name}
              </option>
            ))}
          </select>

          {selected ? (
            <p className="mt-3 text-sm text-moss/75">
              {scenarios.find((s) => s.id === selected)?.description}
            </p>
          ) : null}

          {error ? (
            <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 font-mono text-xs text-danger">
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={pending || !selected}
            className="mt-6 inline-flex items-center justify-center rounded-xl bg-ink px-5 py-3 text-sm font-medium text-sand transition hover:bg-moss disabled:opacity-50"
          >
            {pending ? "Investigating…" : "Run incident agent"}
          </button>
        </form>

        <div className="rounded-2xl border border-ink/10 bg-ink p-6 text-sand shadow-panel">
          <h2 className="text-lg font-semibold text-white">Safety contract</h2>
          <ul className="mt-4 space-y-3 text-sm leading-relaxed text-sand/80">
            <li>Diagnosis tools run autonomously (logs, metrics, deploys, runbooks).</li>
            <li>Root causes require evidence scores above threshold after critic review.</li>
            <li>Restart / rollback / scale / config writes never execute without approval.</li>
            <li>Every decision is written to an immutable audit trail.</li>
          </ul>
          <div className="mt-8 rounded-xl border border-white/10 bg-white/5 p-4 font-mono text-[11px] text-mist/90">
            proof: diagnose with telemetry · remediate only with approval
          </div>
        </div>
      </section>

      <section className="animate-rise mt-14" style={{ animationDelay: "140ms" }}>
        <div className="mb-4 flex items-end justify-between">
          <h2 className="text-2xl font-semibold">Recent incidents</h2>
          <button
            onClick={() => refresh().catch((e) => setError(String(e.message || e)))}
            className="font-mono text-xs uppercase tracking-wider text-copper hover:underline"
          >
            Refresh
          </button>
        </div>

        <div className="overflow-hidden rounded-2xl border border-ink/10 bg-white/65 shadow-panel backdrop-blur">
          {incidents.length === 0 ? (
            <p className="px-5 py-10 text-sm text-moss/60">
              No incidents yet. Launch a scenario to generate the first workspace.
            </p>
          ) : (
            <ul className="divide-y divide-ink/8">
              {incidents.map((inc) => (
                <li key={inc.id}>
                  <Link
                    href={`/incidents/${inc.id}`}
                    className="flex flex-col gap-2 px-5 py-4 transition hover:bg-mist/40 md:flex-row md:items-center md:justify-between"
                  >
                    <div>
                      <p className="font-medium">{inc.title}</p>
                      <p className="mt-1 font-mono text-xs text-moss/60">
                        {inc.service_name} · {new Date(inc.created_at).toLocaleString()}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <StatusPill value={inc.severity} />
                      <StatusPill value={inc.status} />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </main>
  );
}
