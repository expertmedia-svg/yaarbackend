from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pathlib import Path
import uuid
import aiofiles
import os

from app.core.config import settings
from app.core.security import get_current_user

router = APIRouter()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Type de fichier non supporté. JPG/PNG/WEBP uniquement")

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Fichier trop grand (max 5MB)")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4()}.{ext}"

    # If S3 configured, upload to S3
    if settings.AWS_S3_BUCKET and settings.AWS_ACCESS_KEY_ID:
        import boto3
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION,
        )
        s3.put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=f"uploads/{filename}",
            Body=content,
            ContentType=file.content_type,
            ACL="public-read",
        )
        url = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_S3_REGION}.amazonaws.com/uploads/{filename}"
    else:
        # Local storage
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True)
        file_path = upload_dir / filename
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        url = f"/uploads/{filename}"

    return {"url": url, "filename": filename}
