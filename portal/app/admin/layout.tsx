import { AreaDenied, AreaNav } from "@/components/AreaNav";
import { areas } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  if (!areas(currentAccess()).includes("admin")) return <AreaDenied area="Administration" />;
  return (
    <>
      <AreaNav label="Administration" links={[{ href: "/admin/apps", text: "Apps" }]} />
      {children}
    </>
  );
}
