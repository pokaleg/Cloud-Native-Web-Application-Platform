import uuid
import time
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone

from app.core.database import get_db
from app.api.user import get_verified_user  # ← changed from get_current_user
from app.models.user import User
from app.models.course import Course
from app.models.syllabus import Syllabus
from app.schemas.course import (
    CourseCreateRequest, CourseUpdateRequest,
    CourseResponse, SyllabusResponse
)
from app.core.s3 import upload_file_to_s3, delete_file_from_s3
from app.core.config import settings
from app.core.logger import setup_logger
from app.core.metrics import record_api_call, record_api_time, record_db_query_time, record_s3_time

router = APIRouter(prefix="/v1/courses", tags=["courses"])
logger = setup_logger(__name__)


# ── Courses ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_course(
    body: CourseCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_verified_user),  # ← changed
):
    start = time.time()
    record_api_call("create_course")
    logger.info(f"create_course: {body.department_code}/{body.number} by {current_user.username}")

    course = Course(**body.model_dump())
    db.add(course)
    try:
        db_start = time.time()
        db.commit()
        db.refresh(course)
        record_db_query_time("course_create", (time.time() - db_start) * 1000)
    except IntegrityError:
        db.rollback()
        logger.warning(f"create_course: duplicate {body.department_code}/{body.number}")
        record_api_time("create_course", (time.time() - start) * 1000)
        raise HTTPException(
            status_code=409,
            detail=f"Course with department_code '{body.department_code}' and number '{body.number}' already exists"
        )

    logger.info(f"create_course: success — id={course.id}")
    record_api_time("create_course", (time.time() - start) * 1000)
    return JSONResponse(
        status_code=201,
        content=CourseResponse.model_validate(course).model_dump(mode="json"),
        headers={"Location": f"/v1/courses/{course.id}"},
    )


@router.get("", status_code=200)
def list_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_verified_user),  # ← changed
):
    start = time.time()
    record_api_call("list_courses")

    db_start = time.time()
    courses = db.query(Course).order_by(Course.department_code, Course.number).all()
    record_db_query_time("course_list", (time.time() - db_start) * 1000)

    logger.info(f"list_courses: returned {len(courses)} courses")
    record_api_time("list_courses", (time.time() - start) * 1000)
    return [CourseResponse.model_validate(c).model_dump(mode="json") for c in courses]


@router.get("/{course_id}", status_code=200)
def get_course(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_verified_user),  # ← changed
):
    start = time.time()
    record_api_call("get_course")

    db_start = time.time()
    course = db.query(Course).filter(Course.id == course_id).first()
    record_db_query_time("course_get", (time.time() - db_start) * 1000)

    if not course:
        logger.warning(f"get_course: not found — {course_id}")
        record_api_time("get_course", (time.time() - start) * 1000)
        raise HTTPException(status_code=404, detail="Course not found")

    logger.info(f"get_course: {course_id}")
    record_api_time("get_course", (time.time() - start) * 1000)
    return CourseResponse.model_validate(course).model_dump(mode="json")


@router.put("/{course_id}", status_code=200)
def update_course(
    course_id: uuid.UUID,
    body: CourseUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_verified_user),  # ← changed
):
    start = time.time()
    record_api_call("update_course")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        logger.warning(f"update_course: empty body for {course_id}")
        record_api_time("update_course", (time.time() - start) * 1000)
        raise HTTPException(
            status_code=400,
            detail="Request body must contain at least one updatable field"
        )

    db_start = time.time()
    course = db.query(Course).filter(Course.id == course_id).first()
    record_db_query_time("course_get", (time.time() - db_start) * 1000)

    if not course:
        logger.warning(f"update_course: not found — {course_id}")
        record_api_time("update_course", (time.time() - start) * 1000)
        raise HTTPException(status_code=404, detail="Course not found")

    for key, value in updates.items():
        setattr(course, key, value)
    course.date_updated = datetime.now(timezone.utc)

    db_start = time.time()
    db.commit()
    db.refresh(course)
    record_db_query_time("course_update", (time.time() - db_start) * 1000)

    logger.info(f"update_course: success — {course_id}")
    record_api_time("update_course", (time.time() - start) * 1000)
    return CourseResponse.model_validate(course).model_dump(mode="json")


@router.delete("/{course_id}", status_code=204)
def delete_course(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_verified_user),  # ← changed
):
    start = time.time()
    record_api_call("delete_course")

    db_start = time.time()
    course = db.query(Course).filter(Course.id == course_id).first()
    record_db_query_time("course_get", (time.time() - db_start) * 1000)

    if not course:
        logger.warning(f"delete_course: not found — {course_id}")
        record_api_time("delete_course", (time.time() - start) * 1000)
        raise HTTPException(status_code=404, detail="Course not found")

    if course.has_syllabus:
        logger.warning(f"delete_course: blocked — has syllabus {course_id}")
        record_api_time("delete_course", (time.time() - start) * 1000)
        raise HTTPException(
            status_code=409,
            detail="Cannot delete course with an attached syllabus. Delete the syllabus first."
        )

    db_start = time.time()
    db.delete(course)
    db.commit()
    record_db_query_time("course_delete", (time.time() - db_start) * 1000)

    logger.info(f"delete_course: success — {course_id}")
    record_api_time("delete_course", (time.time() - start) * 1000)
    return JSONResponse(status_code=204, content=None)


# ── Syllabus ───────────────────────────────────────────────────────────────────

@router.post("/{course_id}/syllabus", status_code=201)
async def upload_syllabus(
    course_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_verified_user),  # ← changed
):
    start = time.time()
    record_api_call("upload_syllabus")
    logger.info(f"upload_syllabus: course={course_id} file={file.filename}")

    db_start = time.time()
    course = db.query(Course).filter(Course.id == course_id).first()
    record_db_query_time("course_get", (time.time() - db_start) * 1000)

    if not course:
        logger.warning(f"upload_syllabus: course not found — {course_id}")
        record_api_time("upload_syllabus", (time.time() - start) * 1000)
        raise HTTPException(status_code=404, detail="Course not found")

    if course.has_syllabus:
        logger.warning(f"upload_syllabus: already has syllabus — {course_id}")
        record_api_time("upload_syllabus", (time.time() - start) * 1000)
        raise HTTPException(status_code=409, detail="Course already has a syllabus")

    if not file or not file.filename:
        record_api_time("upload_syllabus", (time.time() - start) * 1000)
        raise HTTPException(status_code=400, detail="No file provided")

    contents = await file.read()
    if not contents:
        record_api_time("upload_syllabus", (time.time() - start) * 1000)
        raise HTTPException(status_code=400, detail="File is empty")

    s3_key = f"{course_id}/{uuid.uuid4()}/{file.filename}"
    content_type = file.content_type or "application/octet-stream"

    s3_start = time.time()
    url = upload_file_to_s3(contents, s3_key, content_type)
    record_s3_time("put_object", (time.time() - s3_start) * 1000)

    syllabus = Syllabus(
        course_id=course_id,
        file_name=file.filename,
        s3_bucket_name=settings.S3_BUCKET_NAME,
        s3_object_key=s3_key,
        content_type=content_type,
        file_size=len(contents),
        url=url,
    )
    db.add(syllabus)
    course.has_syllabus = True
    course.date_updated = datetime.now(timezone.utc)

    db_start = time.time()
    db.commit()
    db.refresh(syllabus)
    record_db_query_time("syllabus_create", (time.time() - db_start) * 1000)

    logger.info(f"upload_syllabus: success — course={course_id} s3_key={s3_key}")
    record_api_time("upload_syllabus", (time.time() - start) * 1000)
    return JSONResponse(
        status_code=201,
        content=SyllabusResponse.model_validate(syllabus).model_dump(mode="json"),
        headers={"Location": f"/v1/courses/{course_id}/syllabus"},
    )


@router.get("/{course_id}/syllabus", status_code=200)
def get_syllabus(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_verified_user),  # ← changed
):
    start = time.time()
    record_api_call("get_syllabus")

    db_start = time.time()
    course = db.query(Course).filter(Course.id == course_id).first()
    record_db_query_time("course_get", (time.time() - db_start) * 1000)

    if not course:
        logger.warning(f"get_syllabus: course not found — {course_id}")
        record_api_time("get_syllabus", (time.time() - start) * 1000)
        raise HTTPException(status_code=404, detail="Course not found")

    db_start = time.time()
    syllabus = db.query(Syllabus).filter(Syllabus.course_id == course_id).first()
    record_db_query_time("syllabus_get", (time.time() - db_start) * 1000)

    if not syllabus:
        logger.warning(f"get_syllabus: no syllabus for course {course_id}")
        record_api_time("get_syllabus", (time.time() - start) * 1000)
        raise HTTPException(status_code=404, detail="No syllabus found for this course")

    logger.info(f"get_syllabus: success — course={course_id}")
    record_api_time("get_syllabus", (time.time() - start) * 1000)
    return SyllabusResponse.model_validate(syllabus).model_dump(mode="json")


@router.delete("/{course_id}/syllabus", status_code=204)
def delete_syllabus(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_verified_user),  # ← changed
):
    start = time.time()
    record_api_call("delete_syllabus")

    db_start = time.time()
    course = db.query(Course).filter(Course.id == course_id).first()
    record_db_query_time("course_get", (time.time() - db_start) * 1000)

    if not course:
        logger.warning(f"delete_syllabus: course not found — {course_id}")
        record_api_time("delete_syllabus", (time.time() - start) * 1000)
        raise HTTPException(status_code=404, detail="Course not found")

    db_start = time.time()
    syllabus = db.query(Syllabus).filter(Syllabus.course_id == course_id).first()
    record_db_query_time("syllabus_get", (time.time() - db_start) * 1000)

    if not syllabus:
        logger.warning(f"delete_syllabus: no syllabus for course {course_id}")
        record_api_time("delete_syllabus", (time.time() - start) * 1000)
        raise HTTPException(status_code=404, detail="No syllabus found for this course")

    s3_start = time.time()
    delete_file_from_s3(syllabus.s3_object_key)
    record_s3_time("delete_object", (time.time() - s3_start) * 1000)

    db.delete(syllabus)
    course.has_syllabus = False
    course.date_updated = datetime.now(timezone.utc)

    db_start = time.time()
    db.commit()
    record_db_query_time("syllabus_delete", (time.time() - db_start) * 1000)

    logger.info(f"delete_syllabus: success — course={course_id}")
    record_api_time("delete_syllabus", (time.time() - start) * 1000)
    return JSONResponse(status_code=204, content=None)
