export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`bg-white dark:bg-white/[0.03] border border-black/10 dark:border-white/10
                  rounded-lg ${className}`}
    >
      {children}
    </div>
  );
}

export function MetricCard({ label, value, tone = "default" }: {
  label: string;
  value: React.ReactNode;
  tone?: "default" | "danger" | "warning" | "success";
}) {
  const toneClass = {
    default: "text-black dark:text-white",
    danger: "text-red-700 dark:text-red-400",
    warning: "text-amber-700 dark:text-amber-400",
    success: "text-green-700 dark:text-green-400",
  }[tone];

  return (
    <div className="bg-black/[0.03] dark:bg-white/[0.05] rounded-lg p-4">
      <p className="text-[13px] text-black/60 dark:text-white/60 mb-1.5">{label}</p>
      <p className={`text-2xl font-medium ${toneClass}`}>{value}</p>
    </div>
  );
}
