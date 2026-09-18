// portal/lib/workspaces.ts — the portal's areas, as the header shows them
// (portal phase 1, S4). Which areas a user MAY enter is lib/authz.areas(); this
// adds where each one lives and whether it has been built yet, so the switcher
// never links to an area with no pages in it.

import { areas, type Access, type Area } from "./authz";

export const WORKSPACES: Readonly<Record<Area, { label: string; home: string; built: boolean }>> = {
  dev: { label: "Dev", home: "/dev", built: true },
  ops: { label: "Ops", home: "/ops", built: true },
  admin: { label: "Administration", home: "/admin", built: true },
};

/** The areas this user may enter that exist, in switcher order. */
export function workspacesFor(access: Access, registry: typeof WORKSPACES = WORKSPACES): Area[] {
  return areas(access).filter((area) => registry[area].built);
}
