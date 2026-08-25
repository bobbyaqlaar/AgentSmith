// portal/components/ui/Timestamp.tsx — one way to print a time.
//
// The formatting rule and the reasoning behind it live in lib/formatTime.ts,
// which is a .ts so `npm test` can load it; this file is the markup around it.

import { formatUtc, isoOrUndefined } from "@/lib/formatTime";

export function Timestamp({ value, className = "" }: { value: string | Date; className?: string }) {
  const iso = isoOrUndefined(value);
  return (
    <time dateTime={iso} title={iso} className={className}>
      {formatUtc(value)}
    </time>
  );
}
