"""
LUMA Script 1 — OCR Processor
Uploads PDFs to AWS S3, runs async Textract OCR, extracts raw text.

Run: python -m luma.pipeline.ocr_processor
"""

import boto3
import json
import time
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

S3_BUCKET = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

textract = boto3.client("textract", region_name=AWS_REGION)
s3 = boto3.client("s3")


def upload_to_s3(local_path: str, s3_key: str) -> str:
    """Upload a file to S3. Returns the S3 key."""
    # Skip if already exists
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=s3_key)
        print(f"  Already in S3, skipping upload: {s3_key}")
        return s3_key
    except Exception:
        pass
    s3.upload_file(local_path, S3_BUCKET, s3_key)
    return s3_key


def start_textract_job(s3_key: str) -> str:
    """Start async Textract job. Returns JobId."""
    response = textract.start_document_text_detection(
        DocumentLocation={"S3Object": {"Bucket": S3_BUCKET, "Name": s3_key}}
    )
    return response["JobId"]


def poll_textract_job(job_id: str, max_wait_seconds: int = 120) -> list:
    """Poll until job complete. Returns list of result blocks."""
    waited = 0
    while waited < max_wait_seconds:
        response = textract.get_document_text_detection(JobId=job_id)
        status = response["JobStatus"]
        if status == "SUCCEEDED":
            blocks = response["Blocks"]
            # Handle pagination for large documents
            while "NextToken" in response:
                response = textract.get_document_text_detection(
                    JobId=job_id, NextToken=response["NextToken"]
                )
                blocks.extend(response["Blocks"])
            return blocks
        elif status == "FAILED":
            raise RuntimeError(f"Textract job failed: {job_id}")
        print(f"  Waiting for Textract... ({waited}s)")
        time.sleep(5)
        waited += 5
    raise TimeoutError(f"Textract job timed out after {max_wait_seconds}s")


def extract_text_from_blocks(blocks: list) -> str:
    """Pull all LINE-type blocks and join into raw text."""
    lines = [b["Text"] for b in blocks if b["BlockType"] == "LINE"]
    return "\n".join(lines)


def start_textract_with_retry(s3_key: str, max_retries: int = 3) -> str:
    """Start Textract with exponential backoff on throttling."""
    from botocore.exceptions import ClientError
    for attempt in range(max_retries):
        try:
            return start_textract_job(s3_key)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "ThrottlingException":
                wait = 2 ** attempt
                print(f"  Throttled. Retrying in {wait}s...")
                time.sleep(wait)
            elif code == "UnsupportedDocumentException":
                raise RuntimeError(f"Unsupported document format: {s3_key}")
            else:
                raise
    raise RuntimeError(f"Textract failed after {max_retries} attempts: {s3_key}")


def process_pdf_folder(folder_path: str, customer_id: str) -> list:
    """
    Process all PDFs in a folder.
    Returns list of dicts: {case_id, s3_key, raw_text, page_count}
    """
    results = []
    pdfs = list(Path(folder_path).glob("*.pdf"))
    print(f"\nFound {len(pdfs)} PDFs to process for customer: {customer_id}")

    for i, pdf in enumerate(pdfs):
        case_id = pdf.stem
        print(f"\n[{i+1}/{len(pdfs)}] Processing: {case_id}")
        try:
            s3_key = f"customers/{customer_id}/raw_pdfs/{case_id}.pdf"
            upload_to_s3(str(pdf), s3_key)
            job_id = start_textract_with_retry(s3_key)
            blocks = poll_textract_job(job_id)
            raw_text = extract_text_from_blocks(blocks)
            page_count = max((b.get("Page", 1) for b in blocks), default=1)
            results.append({
                "case_id": case_id,
                "s3_key": s3_key,
                "raw_text": raw_text,
                "page_count": page_count,
            })
            print(f"  ✅ Done ({page_count} pages, {len(raw_text)} chars)")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append({"case_id": case_id, "error": str(e)})

    success = len([r for r in results if "error" not in r])
    print(f"\n✅ OCR complete: {success}/{len(pdfs)} successful")
    return results


if __name__ == "__main__":
    customer_id = "funeral_home_001"
    folder_path = "./luma/data/incoming_pdfs/"

    results = process_pdf_folder(folder_path, customer_id)

    output_path = "./luma/data/ocr_output.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved to: {output_path}")
