"""One user action, one atomic database activity."""
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activity import copy_pev_for_fo
    from packages.common.workflow_decorators import notify_on_completion


@workflow.defn
class CopyPevForFoWorkflow:
    @workflow.run
    @notify_on_completion(
        title="Kopija za FO",
        source="pev_copy_for_fo",
        success_msg="Kopija za FO je pripravljena. Osvežite tabelo in karto.",
        error_msg="Kopiranje za FO ni uspelo. Preverite podrobnosti poteka.",
    )
    async def run(self, request: dict) -> dict:
        return await workflow.execute_activity(
            copy_pev_for_fo,
            request,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
