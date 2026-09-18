// The links within one area, under the header. Server-rendered: the list is
// decided by the area's layout from the user's permissions.

import { NavLinks, type NavLink } from "./NavLinks";

export function AreaNav({ label, links }: { label: string; links: NavLink[] }) {
  return <NavLinks label={label} links={links} variant="area" />;
}

/** "You may not enter this area" — a different screen from "this does not exist". */
export function AreaDenied({ area }: { area: string }) {
  return (
    <div className="space-y-2">
      <h2 className="text-xl font-medium">You do not have access to the {area} workspace</h2>
      <p className="text-black/60 dark:text-white/60">
        Your account holds no role that opens it. An Administrator can grant one.
      </p>
    </div>
  );
}
