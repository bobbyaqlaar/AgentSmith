// POST / DELETE /api/admin/apps/:id/ingest-token — issue, rotate or revoke the
// token an app's CI sends its gate record with (lib/tokenRoutes.ts).

import { tokenRoutes } from "@/lib/tokenRoutes";

export const { POST, DELETE } = tokenRoutes("dev");
