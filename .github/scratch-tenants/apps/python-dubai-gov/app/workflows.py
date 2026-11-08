"""The high-impact action the agency manifest lists, behind a named human gate."""


async def run_permit(workflow, tenant_id: str, request: dict, requested_by: str):
    return await workflow.run_with_hitl_gate(
        None,
        request,
        "deploy_to_production",
        request,
        "dlq_enqueue_activity",
        gate_result={"needs_hitl": True, "requested_by": requested_by},
        tenant_id=tenant_id,
        compliance=True,
    )


async def summarise(gateway, text: str) -> str:
    result = await gateway.complete(text, data_class="confidential")
    return result.text
