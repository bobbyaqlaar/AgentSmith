import { AreaDenied, AreaNav } from "@/components/AreaNav";
import { areas } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export default function DevLayout({ children }: { children: React.ReactNode }) {
  if (!areas(currentAccess()).includes("dev")) return <AreaDenied area="Dev" />;
  return (
    <>
      <AreaNav
        label="Dev"
        links={[
          { href: "/dev", text: "Apps", exact: true, covers: ["/dev/apps"] },
          { href: "/dev/approvals", text: "Awaiting approval" },
        ]}
      />
      {children}
    </>
  );
}
