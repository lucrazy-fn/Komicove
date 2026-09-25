from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from komicove_backend.accounts.models import Report, User
from komicove_backend.api.deps import get_current_user, get_db
from komicove_backend.api.schemas import ReportCreate

router=APIRouter(prefix="/reports",tags=["reports"])

@router.post("",status_code=201)
def create(body:ReportCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    duplicate=db.scalar(select(Report).where(Report.reporter_user_id==user.id,
        Report.target_type==body.target_type,Report.target_id==body.target_id,Report.status=="open"))
    if duplicate: raise HTTPException(409,"Você já possui uma denúncia aberta para este item.")
    item=Report(reporter_user_id=user.id,target_type=body.target_type,target_id=body.target_id,
        reason=body.reason,description=body.description.strip())
    db.add(item); db.flush(); return {"id":item.id,"status":item.status}

@router.get("/admin")
def queue(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in {"moderator","admin","owner"}: raise HTTPException(403,"Acesso negado.")
    return [{"id":x.id,"target_type":x.target_type,"target_id":x.target_id,"reason":x.reason,
        "description":x.description,"status":x.status,"created_at":x.created_at}
        for x in db.scalars(select(Report).order_by(Report.created_at.desc())).all()]
