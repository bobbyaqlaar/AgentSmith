import { AreaDenied, AreaNav } from "@/components/AreaNav";
import { areas, can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export default function DevLayout({ children }: { children: React.ReactNode }) {
  const access = currentAccess();
  if (!areas(access).includes("dev")) return <AreaDenied area="Dev" />;
  return (
    <>
      <AreaNav
        label="Dev"
        links={[
          { href: "/dev", text: "Apps", exact: true, covers: ["/dev/apps"] },
          { href: "/dev/approvals", text: "Awaiting approval" },
          // Only for someone who can — a link to a screen that would refuse them is
          // not part of their journey (.agent-rfc/designs/intake-form.md).
          ...(can(access, "dev.create") ? [{ href: "/dev/intakes/new", text: "Start a tenant", covers: ["/dev/intakes"] }] : []),
        ]}
      />
      {children}
    </>
  );
}
