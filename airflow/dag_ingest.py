from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    "owner": "data-eng",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


with DAG(
    "client_profile_ingest",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    default_args=default_args,
    catchup=False,
) as dag:
    extract = BashOperator(
        task_id="extract",
        bash_command="python ingest/run_all.py",
    )
    materialise = BashOperator(
        task_id="feast_mat",
        bash_command=(
            "feast -c feature_repo materialize-incremental "
            '$(python -c "from datetime import UTC, datetime, timedelta; '
            'print((datetime.now(UTC) - timedelta(days=1)).strftime(\"%Y-%m-%dT00:00:00Z\"))")'
        ),
    )

    extract >> materialise