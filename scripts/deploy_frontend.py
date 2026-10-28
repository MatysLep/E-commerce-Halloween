"""Upload static assets and public configuration after an explicit Terraform apply."""

import json
import mimetypes
import subprocess
import time
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]


def main():
    result = subprocess.run(
        ["terraform", f"-chdir={ROOT / 'infrastructure'}", "output", "-json"],
        check=True,
        capture_output=True,
        text=True,
    )
    outputs = {key: item["value"] for key, item in json.loads(result.stdout).items()}
    configuration = {
        "mode": "aws",
        "apiBase": "",
        "cognitoDomain": outputs["cognito_domain"],
        "clientId": outputs["cognito_client_id"],
    }
    s3 = boto3.client("s3", region_name="eu-west-3")
    for path in sorted((ROOT / "frontend").iterdir()):
        if path.suffix not in {".html", ".css", ".js", ".mjs"} or path.name == "config.local.js":
            continue
        content = path.read_bytes()
        if path.name == "config.js":
            content = f"window.SHOP_CONFIG = {json.dumps(configuration)};\n".encode()
        mime_type = (
            "text/javascript" if path.suffix in {".js", ".mjs"} else mimetypes.guess_type(path)[0]
        )
        s3.put_object(
            Bucket=outputs["frontend_bucket"],
            Key=path.name,
            Body=content,
            ContentType=f"{mime_type}; charset=utf-8",
            CacheControl="public,max-age=60",
        )
    boto3.client("cloudfront").create_invalidation(
        DistributionId=outputs["distribution_id"],
        InvalidationBatch={
            "Paths": {"Quantity": 1, "Items": ["/*"]},
            "CallerReference": str(time.time_ns()),
        },
    )
    print(f"Frontend uploaded: {outputs['site_url']}")


if __name__ == "__main__":
    main()
