export function ScoreBar({ score, label }: { score: number; label?: string }) {
  const pct = Math.max(0, Math.min(100, Math.round(score * 100)));
  return (
    <div className="space-y-1">
      {label ? (
        <div className="flex justify-between font-mono text-[11px] text-moss/70">
          <span>{label}</span>
          <span>{pct}%</span>
        </div>
      ) : null}
      <div className="h-1.5 overflow-hidden rounded-full bg-ink/10">
        <div
          className="score-bar h-full rounded-full bg-gradient-to-r from-signal to-copper transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
