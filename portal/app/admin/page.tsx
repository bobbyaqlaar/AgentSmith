import { redirect } from "next/navigation";

// Administration has one page so far; its area home is that page.
export default function AdminHome() {
  redirect("/admin/apps");
}
