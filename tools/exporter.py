import os
import uuid

import boto3
import weasyprint
from jinja2 import Environment, FileSystemLoader


env = Environment(loader=FileSystemLoader("templates"))


def generate_report(client_id: str, snapshot: dict, actions: list) -> str:
    """Generate a PDF report, upload to S3, and return a pre-signed URL."""
    bucket = os.getenv("REPORT_BUCKET")
    if not bucket:
        raise ValueError("REPORT_BUCKET is not set")

    tmpl = env.get_template("report.html")
    html = tmpl.render(client_id=client_id, snapshot=snapshot, actions=actions)

    pdf_bytes = weasyprint.HTML(string=html).write_pdf()

    s3 = boto3.client("s3")
    key = f"reports/{client_id}/{uuid.uuid4()}.pdf"
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )

    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=3600,
    )
