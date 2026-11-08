import { AreaDenied, AreaNav } from "@/components/AreaNav";
import { areas, can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const access = await currentAccess();
  if (!areas(access).includes("admin")) return <AreaDenied area="Administration" />;
  const links = [
    { href: "/admin/apps", text: "Apps" },
    ...(can(access, "admin.org") ? [{ href: "/api/admin/access-export", text: "Access review export" }] : []),
  ];
  return (
    <>
      <AreaNav label="Administration" links={links} />
      {children}
    </>
  );
}
