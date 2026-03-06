import os
import json
import uuid
import asyncio
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..models.job import ResumeEntry
from ..schemas.resume import TailorResponse
from ..services import resume_service, claude_service, excel_service
from .auth import get_current_user

router = APIRouter(prefix="/api/resume", tags=["resume"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}

# ── In-memory batch task store ────────────────────────────────────────────────
# Structure: { task_id: { status, total, done, jobs: [...] } }
_batch_tasks: Dict[str, dict] = {}


# ── Single resume tailor (original endpoint) ──────────────────────────────────

@router.post("/tailor", response_model=TailorResponse)
async def tailor_resume(
    resume_file:   UploadFile = File(...),
    output_folder: str        = Form(...),
    job_title:     str        = Form(""),
    company:       str        = Form(""),
    location:      str        = Form(""),
    job_url:       str        = Form(""),
    description:   str        = Form(...),
    extra_skills:  str        = Form(""),
    db:            AsyncSession = Depends(get_db),
    current_user   = Depends(get_current_user),
):
    ext = os.path.splitext(resume_file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file: {ext}")

    file_bytes  = await resume_file.read()
    resume_text = resume_service.extract_resume_text(file_bytes, resume_file.filename)
    if not resume_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from resume.")

    tailored_text       = await claude_service.tailor_resume(resume_text, job_title, company, location, description, extra_skills)
    company_description = await claude_service.research_company(company, job_title)
    docx_path, pdf_path = resume_service.save_tailored_resume(tailored_text, output_folder, job_title, location, company)
    filename            = resume_service.build_filename(job_title, location, company)

    db.add(ResumeEntry(
        user_id=current_user.id, filename=filename, job_title=job_title,
        company=company, location=location, job_url=job_url,
        company_description=company_description, pdf_path=pdf_path, docx_path=docx_path,
    ))
    await db.commit()

    return TailorResponse(filename=filename, job_url=job_url or None,
                          company_description=company_description,
                          pdf_path=pdf_path, docx_path=docx_path,
                          tailored_text=tailored_text)


# ── Batch generation ──────────────────────────────────────────────────────────

@router.post("/batch-start")
async def batch_start(
    background:    BackgroundTasks,
    resume_file:   UploadFile = File(...),
    output_folder: str        = Form(...),
    extra_skills:  str        = Form(""),
    jobs_json:     str        = Form(...),   # JSON array of job objects
    db:            AsyncSession = Depends(get_db),
    current_user   = Depends(get_current_user),
):
    """
    Start an async batch job to tailor resumes + generate cover letters
    for a list of selected job postings.
    """
    ext = os.path.splitext(resume_file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file: {ext}")

    file_bytes  = await resume_file.read()
    resume_text = resume_service.extract_resume_text(file_bytes, resume_file.filename)
    if not resume_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from resume.")

    try:
        jobs = json.loads(jobs_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid jobs JSON")

    if not jobs:
        raise HTTPException(status_code=400, detail="No jobs provided")

    task_id = str(uuid.uuid4())
    _batch_tasks[task_id] = {
        "status":  "running",
        "total":   len(jobs),
        "done":    0,
        "jobs":    [
            {
                "title":          j.get("title",       ""),
                "company":        j.get("company",     ""),
                "location":       j.get("location",    ""),
                "job_url":        j.get("job_url",     ""),
                "description":    j.get("description", ""),
                "status":         "pending",   # pending | processing | done | error
                "resume_filename":         "",
                "cover_letter_filename":   "",
                "company_description":     "",
                "resume_pdf_path":         "",
                "resume_docx_path":        "",
                "cover_letter_pdf_path":   "",
                "cover_letter_docx_path":  "",
                "error":          "",
            }
            for j in jobs
        ],
    }

    background.add_task(
        _run_batch,
        task_id=task_id,
        resume_text=resume_text,
        output_folder=output_folder,
        extra_skills=extra_skills,
        user_id=current_user.id,
    )

    return {"task_id": task_id, "total": len(jobs)}


@router.get("/batch-status/{task_id}")
async def batch_status(task_id: str, current_user=Depends(get_current_user)):
    task = _batch_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Batch task not found")
    return task


@router.get("/batch-export/{task_id}")
async def batch_export_excel(task_id: str, current_user=Depends(get_current_user)):
    """Download an Excel tracker for a completed batch task."""
    task = _batch_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    data = [
        {
            "filename":                   j.get("resume_filename", ""),
            "cover_letter_filename":      j.get("cover_letter_filename", ""),
            "job_title":                  j.get("title",   ""),
            "company":                    j.get("company", ""),
            "location":                   j.get("location",""),
            "job_url":                    j.get("job_url", ""),
            "company_description":        j.get("company_description", ""),
            "status":                     j.get("status",  ""),
        }
        for j in task.get("jobs", [])
    ]

    xlsx_bytes = excel_service.batch_tracker_to_excel(data)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=resume_batch_{task_id[:8]}.xlsx"},
    )


# ── Background worker ─────────────────────────────────────────────────────────

async def _run_batch(
    task_id: str,
    resume_text: str,
    output_folder: str,
    extra_skills: str,
    user_id: int,
):
    """Process each job sequentially: tailor resume + cover letter + save files."""
    task = _batch_tasks[task_id]
    for i, job in enumerate(task["jobs"]):
        job["status"] = "processing"
        try:
            title       = job["title"]
            company     = job["company"]
            location    = job["location"]
            description = job["description"]
            job_url     = job["job_url"]

            # Run research + tailoring concurrently for speed
            company_desc, tailored, cover = await asyncio.gather(
                claude_service.research_company(company, title),
                claude_service.tailor_resume(resume_text, title, company, location, description, extra_skills),
                asyncio.coroutine(lambda: "")() if not description else
                    _cover_letter_after_research(resume_text, title, company, location, description, extra_skills),
            )

            # Save resume (DOCX + PDF)
            resume_docx, resume_pdf = resume_service.save_tailored_resume(
                tailored, output_folder, title, location, company
            )
            # Save cover letter (DOCX + PDF)
            cl_docx, cl_pdf = resume_service.save_cover_letter(
                cover, output_folder, title, location, company
            )

            base = resume_service.build_filename(title, location, company)

            job.update({
                "status":                  "done",
                "company_description":     company_desc,
                "resume_filename":         base,
                "cover_letter_filename":   f"CoverLetter_{base}",
                "resume_pdf_path":         resume_pdf,
                "resume_docx_path":        resume_docx,
                "cover_letter_pdf_path":   cl_pdf,
                "cover_letter_docx_path":  cl_docx,
            })
        except Exception as exc:
            job["status"] = "error"
            job["error"]  = str(exc)

        task["done"] = i + 1
        await asyncio.sleep(0.1)   # yield to event loop

    task["status"] = "completed"


async def _cover_letter_after_research(
    resume_text, job_title, company, location, description, extra_skills
):
    """Helper that calls cover-letter generation (used inside gather)."""
    return await claude_service.generate_cover_letter(
        resume_text, job_title, company, location, description,
        company_description="", extra_skills=extra_skills,
    )


# ── Existing endpoints ────────────────────────────────────────────────────────

@router.get("/download")
async def download_resume(path: str, current_user=Depends(get_current_user)):
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=os.path.basename(path))


@router.post("/save-preview")
async def save_preview(
    text:          str = Form(...),
    output_folder: str = Form(...),
    filename:      str = Form("tailored_resume"),
    current_user   = Depends(get_current_user),
):
    """Save edited preview text as well-formatted DOCX + PDF to the given folder."""
    if not output_folder.strip():
        raise HTTPException(status_code=400, detail="output_folder is required")
    try:
        docx_path, pdf_path = resume_service.save_from_preview(
            text, output_folder.strip(), filename.strip() or "tailored_resume"
        )
        return {"docx_path": docx_path, "pdf_path": pdf_path}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tracker")
async def download_tracker(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result  = await db.execute(select(ResumeEntry).where(ResumeEntry.user_id == current_user.id))
    entries = result.scalars().all()
    data = [
        {
            "filename": e.filename, "job_title": e.job_title,
            "company": e.company,   "location": e.location,
            "job_url": e.job_url,   "company_description": e.company_description,
            "created_at": e.created_at,
        }
        for e in entries
    ]
    xlsx_bytes = excel_service.resume_tracker_to_excel(data)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=resume_tracker.xlsx"},
    )
