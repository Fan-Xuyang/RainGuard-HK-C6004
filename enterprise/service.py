import time
from sqlalchemy import select, update
from fastapi import HTTPException
from .db import Run, Job, User, Event, Notice, Artifact, event, uid
from .auth import require

REGIONS = [
    "中西區",
    "東區",
    "南區",
    "灣仔",
    "九龍城",
    "觀塘",
    "深水埗",
    "黃大仙",
    "油尖旺",
    "離島區",
    "葵青",
    "北區",
    "西貢",
    "沙田",
    "大埔",
    "荃灣",
    "屯門",
    "元朗",
]


def new_run(
    s, *, title, region, facility, question, mode, engine, creator, trigger_key=None
):
    r = Run(
        id=uid(),
        title=title,
        region=region,
        facility=facility,
        question=question,
        mode=mode,
        engine=engine,
        creator=creator,
        trigger_key=trigger_key,
        due_at=time.time() + 3600,
    )
    s.add(r)
    s.flush()
    s.add(Job(run_id=r.id, kind="start", payload={}))
    event(
        s,
        r.id,
        "workflow.created",
        creator,
        {"mode": mode, "engine": engine, "trigger": trigger_key},
    )
    return r


def transition(
    s,
    r,
    user,
    revision,
    action,
    note,
    assignee=None,
    facts="",
    checks=None,
    artifacts=None,
):
    if r.revision != revision:
        raise HTTPException(409, "记录已更新，请刷新后重试")
    phase = r.status
    payload = {"action": action, "note": note, "actor": user.id, "time": time.time()}
    if action == "retry":
        require(user, "admin", "supervisor")
        if phase != "failed":
            raise HTTPException(409, "只有失败流程可以重试")
        dead = s.scalar(
            select(Job)
            .where(Job.run_id == r.id, Job.status == "dead")
            .order_by(Job.available_at.desc())
        )
        if not dead:
            raise HTTPException(409, "没有待重试任务")
        if not s.execute(
            update(Run)
            .where(Run.id == r.id, Run.revision == revision, Run.status == phase)
            .values(status="queued", revision=revision + 1, updated_at=time.time())
        ).rowcount:
            raise HTTPException(409, "版本冲突")
        dead.status = "pending"
        dead.attempts = 0
        dead.available_at = time.time()
        event(s, r.id, "workflow.retry", user.id, {"note": note})
        return
    if phase == "waiting_approval":
        require(user, "admin", "supervisor")
        if r.creator == user.id:
            raise HTTPException(403, "创建者不能审批自己的流程，请另一位主管审批")
        if action not in ("approve", "rework"):
            raise HTTPException(400, "操作与当前阶段不匹配")
        if action == "approve":
            operator = s.get(User, assignee or "")
            if not operator or not operator.active or operator.role != "operator":
                raise HTTPException(400, "请选择有效现场执行人")
            payload["assignee"] = operator.id
    elif phase == "waiting_field":
        if action == "reassign":
            require(user, "admin", "supervisor")
            operator = s.get(User, assignee or "")
            if not operator or not operator.active or operator.role != "operator":
                raise HTTPException(400, "请选择有效现场执行人")
            payload["assignee"] = operator.id
        else:
            require(user, "operator")
            if r.assignee != user.id:
                raise HTTPException(403, "只有被指派的执行人可以提交现场核验")
            if action != "submit" or not facts.strip() or checks != [True, True, True]:
                raise HTTPException(400, "请填写现场事实并完成全部核验")
            for aid in artifacts or []:
                a = s.get(Artifact, aid)
                if not a or a.run_id != r.id:
                    raise HTTPException(400, "照片附件不属于当前流程")
            payload.update(facts=facts, checks=checks, artifacts=artifacts or [])
    elif phase == "waiting_review":
        require(user, "admin", "supervisor")
        if user.id in (r.creator, r.assignee):
            raise HTTPException(403, "复审必须由独立主管完成")
        if action not in ("accept", "return_field"):
            raise HTTPException(400, "操作与当前阶段不匹配")
    else:
        raise HTTPException(409, "当前阶段不接受业务操作")
    if not s.execute(
        update(Run)
        .where(Run.id == r.id, Run.revision == revision, Run.status == phase)
        .values(status="queued", revision=revision + 1, updated_at=time.time())
    ).rowcount:
        raise HTTPException(409, "另一位成员已操作，请刷新")
    s.add(
        Job(
            run_id=r.id,
            kind="reassign" if action == "reassign" else "resume",
            payload=payload,
        )
    )
    event(
        s,
        r.id,
        "decision." + action,
        user.id,
        {"note": note, "phase": phase, "assignee": assignee},
    )


def serialize(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
