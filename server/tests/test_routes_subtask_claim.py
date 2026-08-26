from eyened_orm import Creator, SubTask, Task, TaskDefinition
from eyened_orm.task import SubTaskState, TaskState


def test_patch_subtask_claim_already_assigned_returns_409(client, session):
    """PATCH /subtasks/{id} with claim=true on an owned subtask returns 409.

    The TestClient CurrentUser is creator_id=1 (username tester). Seed that
    creator first so it gets id 1 on empty sqlite, matching the client fixture
    and admin_scope actor_id. A second owner already holds the subtask.
    """
    tester = Creator(CreatorName="tester", IsHuman=True)
    session.add(tester)
    session.flush()
    owner = Creator(CreatorName="owner", IsHuman=True)
    session.add(owner)
    session.flush()

    td = TaskDefinition(TaskDefinitionName="td-claim")
    session.add(td)
    session.flush()
    task = Task(
        TaskName="T",
        TaskDefinitionID=td.TaskDefinitionID,
        CreatorID=owner.CreatorID,
        TaskState=TaskState.NotStarted,
    )
    session.add(task)
    session.flush()
    subtask = SubTask(
        TaskID=task.TaskID,
        TaskState=SubTaskState.NotStarted,
        CreatorID=owner.CreatorID,
    )
    session.add(subtask)
    session.commit()
    subtask_id = subtask.SubTaskID
    owner_id = owner.CreatorID
    session.expunge_all()

    response = client.patch(f"/subtasks/{subtask_id}", json={"claim": True})

    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "subtask_already_claimed"
    assert detail["creator_id"] == owner_id
