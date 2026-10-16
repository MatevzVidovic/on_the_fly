"""Deploy this directory as src/packages/_gurs/compare_pripis_ev/."""
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from packages.common.workflow_decorators import notify_on_completion


@activity.defn
def compare_pripis_ev_activity(id_rel_vm_pd: str) -> dict:
    from sdk.db_loader import get_db_manager_for_caller
    from packages._gurs.compare_pripis_ev.pairing import pair_buildings

    # session commits once, or rolls everything back on failure.
    with get_db_manager_for_caller().session() as cur:
        cur.execute("SET LOCAL statement_timeout = '10min'")
        cur.execute("SET LOCAL lock_timeout = '3s'")
        cur.execute("SET LOCAL TIME ZONE 'Europe/Ljubljana'")
        return pair_buildings(cur, id_rel_vm_pd, write=True)


@workflow.defn
class ComparePripisEvWorkflow:
    @notify_on_completion(
        title='Primerjava pripisa z EV', source='compare_pripis_ev',
        start_msg='Primerjava delov stavb se je začela.',
        success_msg='Primerjava delov stavb je zaključena.',
        error_msg='Primerjava delov stavb ni uspela.',
    )
    @workflow.run
    async def run(self, id_rel_vm_pd: str) -> dict:
        return await workflow.execute_activity(
            compare_pripis_ev_activity, id_rel_vm_pd,
            start_to_close_timeout=timedelta(minutes=12),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
