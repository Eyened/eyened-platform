Version 0.3 - 6-8-2026  
Modified to support tasks and subtasks that span multiple projects  
Supersedes v0.2 (21-7-2026, clarifications 22-7-2026)  
[DRAFT]

## Goal

Provide role-based access control (rbac) to ensure users can add restricted data to the platform. To achieve this, we want to define system administrators that can provide and revoke access on request of the users. For users, we want to be able to assign different roles within a project with different permissions (project admin, grader, read-only). Users may only modify their own annotations.

Tasks are how graders are given work, and some grading work is inherently cross-cohort — comparing projects, benchmarking graders across datasets, reviewing a data-quality problem that spans studies. A task must therefore be able to hold images from more than one project, without that becoming a way to widen anyone's access.

## What changed from v0.2

v0.2 listed *"Creating tasks that span multiple projects"* as out of scope and required that *"a task is linked to one project explicitly"*. That does not match the data: of 46 tasks measured on a production copy (3-8-2026), **19 already span more than one project and hold 88% of all subtask-to-image links**, and **315 subtasks** span projects by themselves (314 of them on a single task). Forcing them into one project would mean either splitting them or making them unreachable.

| # | v0.2 | v0.3 |
| - | ---- | ---- |
| 1 | Tasks spanning projects: out of scope | **Supported.** A task's subtasks may reference images from any project |
| 2 | A task is linked to one project explicitly | **A task has no project of its own.** Its projects are derived from the images it holds |
| 3 | Visibility implicitly per-project | **A user has access to a task only if they have access to every project the task touches** |
| 4 | *(absent)* | Spanning grants **no** access: project membership remains the only way to see project data |

Everything else in v0.2 — roles, the permission matrix, the enforcement tiers, and the application-wide data namespace — is carried over unchanged.

## Design considerations

These requirements are designed to be simple while meeting the basic requirements for security and privacy. We do not expect a large amount of users, so it is acceptable to have all platform-level administrative tasks (creating users, granting project access) handled by system administrators rather than providing those permissions to project admins.

For system administrators, even though we could already perform any task through direct database access, we want to define these roles explicitly so that we can relate the interactions to a specific user. This will be relevant for legal compliance. The implementation of system admin interactions could be through a separate dashboard.

This is an MVP and the requirements are expected to change. Where a choice is available, prefer the rule that is simplest to state, and the one that can be tightened later without withdrawing something users already have.

**The governing principle for spanning tasks:** a task is a *view over* project data, never a *grant of* project data. Putting an image into a task changes who can find the task; it never changes who can see the image.

**Out of scope for now:**

- Making additional data project-dependent, like features, form schemas, tags, and models. Currently the downsides of that granularity would outweigh the benefits.

- Providing access to only a part of a project.

- **Partial access to a task.** A user either has access to every project a task touches, and sees all of it, or has no access to the task at all. There is no partial view, and no indication to a user that a task they cannot see exists.

- **Task-level access grants.** Access is granted per project, never per task. A grader who must work on a task spanning three projects needs membership in all three.

- Defining organizations that span multiple projects or form groups of users.

- Trusted non-API paths (CLI, eorm, RQ workers, notebooks) remain outside RBAC enforcement; only the HTTP API and client are in scope.

**Deferred to a later delivery:** the system-administration HTTP API (creating users, granting and revoking access, the user overview) and the deployment-configurable registration modes. Until they exist, system administrators perform these actions through the CLI, which is already a trusted path. Enforcement of the permissions below does not depend on them.

## Roles

### Platform roles

| Role                 | Description                                                     |
| -------------------- | --------------------------------------------------------------- |
| System administrator | Manages users and assigns users to projects with a project role |
| User                 | Has access only to projects they are explicitly granted         |

### Project roles

A user is assigned exactly one role per project they have access to.

| Role          | Description                                  |
| ------------- | -------------------------------------------- |
| Project admin | Administers the project                      |
| Grader        | Creates and edits annotations                |
| Read-only     | Observes project data without making changes |

A user working in a task that spans projects holds one role per project, and those roles may differ. Every rule below resolves against the roles the user holds in the projects of the data being acted on, never against a single "role in the task".

## User stories

As a **system administrator**  
I want to **create new user accounts**  
So that I can **onboard users**

As a **system administrator**  
I want to **give and revoke user access to projects, with a specific project role**  
So that **access to restricted data can be provided and restricted at the right permission level**

As a **system administrator**  
I want to **see an overview of users, their project access, and their project roles**  
So that **I can effectively provide support**

As a **system administrator**  
I want to **see which projects a task spans**  
So that **I can grant exactly the memberships a grader needs, and no more**

As a **system administrator**  
I want to **grant a user everything they need for a given set of tasks in one action**  
So that **I can put a grader onto cross-cohort work without working out the project list by hand**

As a **user**  
I want to **see only the projects I have access to**  
So that **I cannot view restricted data**

As a **project admin**  
I want to **build a task whose subtasks contain images from more than one project**  
So that **I can run cross-cohort grading, benchmarks and data-quality reviews**

As a **project admin**  
I want to **be told which projects a task will span before I add images to it**  
So that **I do not build work that the intended graders turn out to have no access to**

As a **grader**  
I want to **create and edit my own annotations**  
So that **I can contribute annotations without changing others' work**

As a **read-only user**  
I want to **view project data without being able to change it**  
So that **I can review data safely**

## Visibility

**A task's projects are the projects of the images in its subtasks.** They are derived from the data, not declared. A task may touch zero projects (it holds no images), one, or many. Nothing is stored on the task that names a project, and no task belongs to a project.

**A user has access to an object only if they have access to every project that object touches.**

| Object | Projects it touches | Visible to a user when |
| ------ | ------------------- | ---------------------- |
| Patient, study, series, image | The project of the patient | The user is a member of that project |
| Annotation (segmentation, form annotation, applied tag) | The project of the data it annotates | The user is a member of that project. Never affected by which task it was made in |
| Subtask | The projects of its images | The user is a member of all of them |
| Task | The projects of all images in all its subtasks | The user is a member of all of them |

System administrators are members of every project for the purpose of these rules, and can therefore see all project data. Every administrative action is attributable and audit-logged.

An object a user has no access to is **not reported to exist**. Requests for it are answered as though it were absent, and lists return only the objects the user has access to.

**Consequences, stated so they are decided rather than discovered:**

1. **A task is all-or-nothing.** A user who has access to every project a task touches sees the whole task, including every subtask, every image, and every subtask's comments and grading state. A user missing any one of those projects does not see the task at all. There are no partial tasks and no placeholders for withheld data.

2. **Adding an image can remove other people's access.** Adding an image from a new project to a task narrows the set of users who can see that task: anyone without access to the new project loses the whole task. Nothing is deleted and no data leaks, but grading work in progress can become unreachable to the people doing it. This is why a project admin must be able to see which projects a task will span before adding to it.

3. **Removing an image can widen access.** When the last image of a project leaves a task, the task stops touching that project and becomes visible to users who could not see it before, including the subtask comments and grading state recorded while it spanned more.

4. **An object that touches no project is unrestricted.** A task with no images, or a subtask with no images, touches no projects, so the rule above is satisfied for everyone: any authenticated user can see and modify it. Tasks are empty when first created, so this is the normal state of a task under construction. **Accepted for now**; it applies today to 3 tasks and 230 subtasks that hold no images.

5. **Spanning never widens access.** Being able to see a task grants no access to any project data in it that the user would not otherwise have. Project membership remains the only access mechanism.

## Permission matrix

### Enforcement policy

| Tier | Meaning |
| ---- | ------- |
| **API-required** | Must return 403 when violated; client checks are not sufficient |
| **Client-only** | UI hides or disables actions; API allows if role otherwise permits |

Security-sensitive rules (data visibility, write restrictions, user management) are **API-required**. Other layout and display preferences are **client-only** (e.g. visibility of other graders' annotations within a Task).

Everything in the Visibility section above is API-required.

### Platform permissions

| Action                                                     | System administrator | User |
| ---------------------------------------------------------- | -------------------- | ---- |
| View list of users, project access, and project roles      | ✓                    | ✗    |
| View all user's information                                | ✓                    | ✗    |
| Create users                                               | ✓                    | ✗    |
| Delete users                                               | ✓                    | ✗    |
| Create and delete projects                                 | ✓                    | ✗    |
| Upload and delete images                                   | ✓                    | ✗    |
| Update image metadata (including series, study, patient)   | ✓                    | ✗    |
| Grant or revoke project access (with a project role)       | ✓                    | ✗    |
| Access and create application-wide data (e.g. features, models, devices) | ✓      | ✓    |
| Delete application-wide data                               | ✓                    | ✓    |
| View project-specific data for all projects                | ✓                    | ✗    |
| View the list of projects a task spans                     | ✓                    | ✓    |
| Self: view own profile and change own password             | ✓                    | ✓    |
| Run model inference on accessible project images           | ✓                    | ✓ (grader role in project) |

Platform permission notes:

- In the current design Users may delete application-wide data they can create; However, on database level this is restricted when other entities reference the record (referential integrity).
- **Create users** is deployment-configurable (open register, admin-only, OIDC auto-provision, or combinations); the configured mode must be enforced at API level. Deferred with the rest of the administration API.
- **Delete users** means **deactivate**. A user's annotations, tasks and subtasks carry their identity, and that attribution is the compliance control; erasing the account would destroy it. A deactivated user cannot authenticate and holds no access, while their existing work keeps its author.
- **View the list of projects a task spans:** a user can only see a task at all if they are a member of every project it spans, so naming those projects discloses nothing new. System administrators see the same list for every task, which is what they need in order to grant the right memberships.
- **Granting access for a task** is a convenience over granting projects, not a new kind of grant. A system administrator names one or more tasks and a role; the projects those tasks touch are resolved, and the user is granted membership in each. The result is ordinary project memberships — indistinguishable from having granted each project by hand, revoked the same way, and carrying the same access to that project's data outside the task. It must therefore be reviewed before it is applied: the administrator is shown which projects will be granted and which the user already holds. An existing role is never silently lowered, and a task touching no projects grants nothing and says so.

### Project permissions

Applies only to projects the user has been granted access to.

Each row below is evaluated against **every project the acted-on object touches**: the user needs the stated role in all of them. For an object touching a single project this is v0.2's rule unchanged. System administrators satisfy it for every project.

| Action                          | Project admin | Grader | Read-only |
| ------------------------------- | ------------- | ------ | --------- |
| View project-specific data      | ✓             | ✓      | ✓         |
| Create annotations              | ✓             | ✓      | ✗         |
| Modify own annotations          | ✓             | ✓      | ✗         |
| Modify other users' annotations | ✗             | ✗      | ✗         |
| Delete own annotations          | ✓             | ✓      | ✗         |
| Delete other users' annotations | ✓             | ✗      | ✗         |
| Create/delete tasks             | ✓             | ✗      | ✗         |
| Update tasks status             | ✓             | ✓      | ✗         |
| Add/remove subtasks in task     | ✓             | ✓      | ✗         |
| Add/remove images in subtasks   | ✓             | ✓      | ✗         |
| Update subtask grading status   | ✓             | ✓      | ✗         |
| View user information related to the project | ✓             | ✓      | ✓         |

For now, many of the actions we would want to specify are not yet implemented especially for project administration. The permission matrix will be expanded as we provide more features for data management.

'Annotations' includes image segmentations, forms and tags. These are each backed by respectively a feature, formschema or tag (definition), which are application-wide data; Applying tags to project entities is an annotation action.

Project permission notes:

- **Changing what a task holds is judged before and after the change.** Adding or removing an image, or adding or removing a subtask, requires the stated role in every project the task touches **before** the change and every project it touches **after** it. Without the "after" half, a grader could add an image from a project they have no role in; without the "before" half, they could alter a task they have no role in.
- **Creating a task is unrestricted**, because a new task holds no images and therefore touches no projects (Visibility, consequence 4). Authority over the task arrives with its first image and grows as it spans further.
- **Annotations are never gated by the task.** A grader annotating an image in project P needs the grader role in P, whether they reached that image through a task, a search, or the viewer. This is what makes spanning tasks safe: no annotation permission flows through a task.
- **Deleting a task does not delete annotations.** It removes the task, its subtasks and its image links; annotations made in it survive and lose only their link to the grading context.
- **View user information related to the project:** this refers to annotation author identity (username on annotations). Usernames for collaborators may be available at the API level; TaskConfig could control whether the client actually displays them.

## Data scope

**Application-wide data:** features, formschemas, models, devices, tags

**Project-specific data:** patients, images, annotations, formannotations, tasks, subtasks, metadata related to tasks

- Users may create and delete application-wide entities; deletion may fail when referenced by other records (e.g. you cannot delete a feature that is referenced by any segmentation).
- A task holds no project of its own. It is project-specific data by virtue of what it contains, and the projects governing it change as its contents change.

## Acceptance criteria

- [ ] Project-specific data is only accessible to users that are explicitly granted access
- [ ] When granting project access, a project role (project admin, grader, or read-only) must be assigned
- [ ] Project permissions match the permission matrix for each project role
- [ ] Users can create and modify only their own annotations
- [ ] Users cannot modify or delete other users' annotations
- [ ] Read-only users cannot create, modify, or delete annotations
- [ ] A list of users, project access, and project roles is available to system administrators
- [ ] Users do not have access to other users' information
- [ ] Users can see other users as annotation authors only (username only, and only within shared projects)
- [ ] System administrators can create new users
- [ ] System administrators can deactivate users, and a deactivated user's existing work keeps its author
- [ ] System administrators can provide and revoke user access to projects with a project role
- [ ] System administrators can grant a user the memberships a given set of tasks requires, in one action, after being shown what will change
- [ ] A grant or a revocation takes effect on the user's next request, without them signing in again
- [ ] Security-sensitive permissions are API-required per enforcement policy
- [ ] New user registration mode is deployment-configurable and documented

Replacing v0.2's *"A task is linked to one project explicitly"*:

- [ ] A task's subtasks may reference images from any project
- [ ] No project is recorded on a task; the projects governing a task are derived from the images it holds
- [ ] A user has access to a task only if they are a member of every project the task touches, and then sees all of it
- [ ] A user who is not a member of every project a task touches is not told that the task exists
- [ ] A subtask's comments, grading state and grader identity are visible on the same condition as the subtask itself
- [ ] Adding or removing an image or subtask requires grader or above in every project the task touches before and after the change
- [ ] Being able to see a task grants no access to any project data it contains; project membership remains the only access mechanism
- [ ] Deleting a task does not delete annotations made in it
- [ ] A user sees the names of the projects a task spans, for any task they can see

## Open questions

1. **Should a task record who created it?** Consequence 4 leaves an empty task open to any authenticated user, including deletion. Recording a creator and reserving empty tasks to them would close it, at the cost of introducing an ownership rule alongside the role rules. Deliberately not done for now.

2. **Should the existing spanning tasks be split into per-project tasks?** Not required by these requirements, and no data change is needed to satisfy them. It remains available later as a way to make cross-cohort work reachable by more people, and would be a data decision rather than a change to these rules.

## Decided

**Reaching the existing spanning tasks is an administrative problem, not a data one (6-8-2026).** 19 of 46 tasks touch more than one project, and under these rules each is reachable only by users granted membership in all of them. No task is split, re-parented or migrated to make it reachable; the memberships are granted instead, which is what the task-based grant above exists to make practical. The consequence to accept is that until those grants are made, work that was previously reachable by anyone is reachable by no one.
