import { AreaDenied, AreaNav } from "@/components/AreaNav";
import { areas, can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export default async function OpsLayout({ children }: { children: React.ReactNode }) {
  const access = await currentAccess();
  if (!areas(access).includes("ops")) return <AreaDenied area="Ops" />;
  const links = [
    { href: "/ops", text: "Apps", exact: true, covers: ["/ops/apps"] },
    { href: "/ops/dlq", text: "Dead-letter queue" },
    { href: "/ops/hitl", text: "Human decisions" },
    { href: "/ops/incidents", text: "Incidents" },
    { href: "/ops/compliance", text: "Compliance" },
    ...(can(access, "admin.audit") ? [{ href: "/ops/audit", text: "Audit log" }] : []),
  ];
  return (
    <>
      <AreaNav label="Ops" links={links} />
      {children}
    </>
  );
}
