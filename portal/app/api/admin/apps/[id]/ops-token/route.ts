// POST / DELETE /api/admin/apps/:id/ops-token — issue, rotate or revoke the
// token an app's workers report with by the Ops contract (contract/ops/v1,
// lib/tokenRoutes.ts).

import { tokenRoutes } from "@/lib/tokenRoutes";

export const { POST, DELETE } = tokenRoutes("ops");
