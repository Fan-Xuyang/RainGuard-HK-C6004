import os, time, threading, contextlib, hashlib, argparse
from sqlalchemy import select, update, or_, and_, text
from langgraph.types import Command
from .db import connect, Run, Job, Notice, event, uid
from .graph import graph_context


@contextlib.contextmanager
def run_lock(engine, run_id):
    if engine.dialect.name != "postgresql":
        yield True
        return
    key = int.from_bytes(
        hashlib.sha256(run_id.encode()).digest()[:8], "big", signed=True
    )
    with engine.connect() as conn:
        locked = conn.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
        ).scalar()
        try:
            yield locked
        finally:
            if locked:
                conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})


def work_one(factory, graph, engine):
    worker = uid()
    now = time.time()
    with factory.begin() as s:
        job = s.scalar(
            select(Job)
            .where(
                or_(
                    and_(Job.status == "pending", Job.available_at <= now),
                    and_(Job.status == "running", Job.lease_until < now),
                )
            )
            .order_by(Job.available_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return False
        claimed = s.execute(
            update(Job)
            .where(Job.id == job.id, Job.status == job.status, Job.worker == job.worker)
            .values(
                status="running",
                worker=worker,
                lease_until=now + 180,
                attempts=job.attempts + 1,
            )
        )
        if not claimed.rowcount:
            return False
        job_id, run_id = job.id, job.run_id
        r = s.get(Run, run_id)
        r.status = "running"
        event(
            s, run_id, "job.claimed", "worker", {"job": job_id, "attempt": job.attempts}
        )
    with run_lock(engine, run_id) as locked:
        if not locked:
            with factory.begin() as s:
                s.execute(
                    update(Job)
                    .where(Job.id == job_id, Job.worker == worker)
                    .values(
                        status="pending",
                        worker=None,
                        available_at=time.time() + 5,
                        attempts=Job.attempts - 1,
                    )
                )
            return True
        stop = threading.Event()

        def heartbeat():
            while not stop.wait(10):
                try:
                    with factory.begin() as s:
                        s.execute(
                            update(Job)
                            .where(
                                Job.id == job_id,
                                Job.worker == worker,
                                Job.status == "running",
                            )
                            .values(lease_until=time.time() + 180)
                        )
                except Exception:
                    pass  # Lease fencing is checked before publishing any business transition.

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            with factory() as s:
                j = s.get(Job, job_id)
                r = s.get(Run, run_id)
                payload = dict(j.payload)
                kind = j.kind
                attempts = j.attempts
            if attempts > 3:
                raise RuntimeError("retries exhausted")
            config = {"configurable": {"thread_id": run_id}, "recursion_limit": 40}
            checkpoint = graph.get_state(config)
            if kind == "reassign":
                if checkpoint.values.get("last_command_id") != job_id:
                    graph.update_state(
                        config,
                        {
                            "decision": {
                                **checkpoint.values["decision"],
                                "assignee": payload["assignee"],
                            },
                            "last_command_id": job_id,
                        },
                        as_node="approval",
                    )
                arg = None
            elif kind == "start":
                arg = (
                    None
                    if checkpoint.values
                    else {
                        "run_id": run_id,
                        "question": r.question,
                        "region": r.region,
                        "facility": r.facility,
                        "mode": r.mode,
                        "engine": r.engine,
                    }
                )
            else:
                arg = (
                    None
                    if checkpoint.values.get("last_command_id") == job_id
                    else Command(resume={**payload, "command_id": job_id})
                )
            graph.invoke(arg, config)
            snapshot = graph.get_state(config)
            state = dict(snapshot.values)
            pending = [i for task in snapshot.tasks for i in task.interrupts]
            status = (
                pending[0].value["phase"]
                if pending
                else "archived"
                if state.get("archive")
                else "failed"
            )
            with factory.begin() as s:
                j = s.scalar(select(Job).where(Job.id == job_id).with_for_update())
                r = s.scalar(select(Run).where(Run.id == run_id).with_for_update())
                if (
                    j.worker != worker
                    or j.status != "running"
                    or j.lease_until < time.time()
                ):
                    return True
                j.status = "done"
                j.worker = None
                j.error = None
                r.status = status
                r.state = state
                r.revision += 1
                r.updated_at = time.time()
                r.due_at = time.time() + 3600
                if state.get("decision", {}).get("assignee"):
                    r.assignee = state["decision"]["assignee"]
                event(
                    s,
                    run_id,
                    "workflow." + status,
                    "worker",
                    {"revision": r.revision, "job": job_id},
                )
                s.add(
                    Notice(
                        id=f"{run_id}:{r.revision}:transition",
                        run_id=run_id,
                        text="流程已进入 " + status,
                    )
                )
        except Exception as exc:
            try:
                partial = graph.get_state({"configurable": {"thread_id": run_id}})
                diagnostics = {
                    **dict(partial.values),
                    "_execution": {
                        "next": list(partial.next),
                        "error_type": type(exc).__name__,
                    },
                }
            except Exception:
                diagnostics = {"_execution": {"error_type": type(exc).__name__}}
            with factory.begin() as s:
                j = s.scalar(select(Job).where(Job.id == job_id).with_for_update())
                r = s.get(Run, run_id)
                if j.worker == worker:
                    failed = j.attempts >= 3
                    j.status = "dead" if failed else "pending"
                    j.worker = None
                    j.available_at = time.time() + min(60, 2**j.attempts)
                    j.error = (
                        "节点执行失败；查看证据/模型配置后重试。未自动完成业务审批。"
                    )
                    r.status = "failed" if failed else "retrying"
                    r.state = diagnostics
                    r.updated_at = time.time()
                    if failed:
                        s.add(
                            Notice(
                                id=f"{run_id}:{r.revision}:{job_id}:dead",
                                run_id=run_id,
                                text="流程执行已失败；请主管检查来源或模型配置后手动重试。",
                            )
                        )
                    event(
                        s,
                        run_id,
                        "job.dead" if failed else "job.retry",
                        "worker",
                        {
                            "job": job_id,
                            "attempt": j.attempts,
                            "error_type": type(exc).__name__,
                        },
                    )
        finally:
            stop.set()
            thread.join(timeout=1)
    return True


@contextlib.contextmanager
def local_worker_lock():
    os.makedirs("runtime", exist_ok=True)
    with open("runtime/enterprise-worker.lock", "a+b") as f:
        f.write(b"0")
        f.flush()
        f.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                yield
            finally:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def main():
    engine, factory = connect()
    lock = (
        local_worker_lock()
        if engine.dialect.name == "sqlite"
        else contextlib.nullcontext()
    )
    with lock, graph_context() as graph:
        while True:
            try:
                if not work_one(factory, graph, engine):
                    time.sleep(1)
            except KeyboardInterrupt:
                return
            except Exception:
                time.sleep(3)


if __name__ == "__main__":
    main()
