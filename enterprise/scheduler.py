import time
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from .db import connect, Run, Rule, Notice, event
from .graph import Bridge
from .service import new_run


def tick(factory, bridge=None, now=None):
    bridge = bridge or Bridge()
    now = now or time.time()
    with factory.begin() as s:
        for r in s.scalars(
            select(Run).where(
                Run.status.in_(["waiting_approval", "waiting_field", "waiting_review"]),
                Run.due_at < now,
            )
        ):
            key = f"{r.id}:{r.revision}:sla"
            if not s.get(Notice, key):
                s.add(
                    Notice(
                        id=key,
                        run_id=r.id,
                        text="阶段已超时，需要主管跟进；系统不会自动批准或完成",
                    )
                )
                event(s, r.id, "sla.overdue", "scheduler", {"phase": r.status})
        ids = list(
            s.scalars(
                select(Rule.id).where(Rule.enabled == True, Rule.next_check <= now)
            )
        )
    for rid in ids:
        with factory.begin() as s:
            r = s.get(Rule, rid)
            if not s.execute(
                update(Rule)
                .where(Rule.id == rid, Rule.next_check == r.next_check)
                .values(next_check=now + 300)
            ).rowcount:
                continue
            region, threshold, facility = r.region, r.threshold, r.facility
        try:
            result = bridge.call("compare_regions", {"regions": [region]}, "live")
            if (
                result.get("stale")
                or result.get("origin") != "online"
                or not result.get("observedAt")
            ):
                raise RuntimeError("unavailable")
            value = result["rows"][0].get("mm")
            if value is None:
                raise RuntimeError("missing")
            with factory.begin() as s:
                rule = s.get(Rule, rid)
                if not rule.enabled:
                    continue
                rule.last_error = None
                if value >= threshold:
                    key = f"{rid}:{result['observedAt']}"
                    if not s.scalar(select(Run.id).where(Run.trigger_key == key)):
                        new_run(
                            s,
                            title="雨量关注值触发的人工复核",
                            region=region,
                            facility=facility,
                            question=f"核对{region}的官方雨量来源及{facility}需要人工检查的事项。触发时区域过去一小时雨量上限为{value}mm，非设施现场积水。",
                            mode="live",
                            engine="evidence",
                            creator="system",
                            trigger_key=key,
                        )
        except IntegrityError:
            pass  # Unique trigger key provides cross-scheduler deduplication.
        except Exception:
            with factory.begin() as s:
                s.get(Rule, rid).last_error = "实时官方来源缺失或过期，未触发业务流程"


if __name__ == "__main__":
    _, factory = connect()
    while True:
        try:
            tick(factory)
        except Exception:
            pass
        time.sleep(30)
