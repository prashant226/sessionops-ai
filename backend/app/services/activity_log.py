from sqlalchemy.orm import Session as DbSession

from .. import models


def log(db: DbSession, assignment_id: str, actor: str, message: str) -> None:
    db.add(models.AssignmentActivity(assignment_id=assignment_id, actor=actor, message=message))
