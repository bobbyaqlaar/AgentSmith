import { AreaDenied, AreaNav } from "@/components/AreaNav";
import { areas, can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export default function OpsLayout({ children }: { children: React.ReactNode }) {
  const access = currentAccess();
  if (!areas(access).includes("ops")) return <AreaDenied area="Ops" />;
  const links = [
    { href: "/ops", text: "Apps", exact: true, covers: ["/ops/apps"] },
    { href: "/ops/dlq", text: "Dead-letter queue" },
    ...(can(access, "admin.audit") ? [{ href: "/ops/audit", text: "Audit log" }] : []),
  ];
  return (
    <>
      <AreaNav label="Ops" links={links} />
      {children}
    </>
  );
}
