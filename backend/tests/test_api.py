import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app



@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = test_sessions()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.test_engine = engine
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()
    del app.state.test_engine


def test_health_endpoint(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_project_creation_and_plan_generation(client):
    create = client.post('/api/projects', json={
        'name': 'Alpha Launch',
        'description': 'Launch customer portal',
        'project_type': 'Web Application',
        'start_date': '2026-11-02',
        'deadline': '2026-12-18',
        'priority': 'High',
        'complexity': 'Medium',
        'working_days': [1, 2, 3, 4, 5],
        'hours_per_day': 8,
        'holidays': ['2026-11-26'],
        'buffer_percent': 10,
        'members': [{
            'id': 'PM-1',
            'name': 'Asha Patel',
            'role': 'Project Manager',
            'skills': ['planning', 'risk'],
            'experience': 6,
            'hours_per_day': 8,
            'allocation': 100,
            'available_from': '2026-11-02',
            'available_until': '2026-12-18',
            'leave_dates': ['2026-11-20'],
        }],
    })
    assert create.status_code == 201, create.text
    project_id = create.json()['id']
    upload = client.post(f'/api/projects/{project_id}/documents', files={'file': ('story.txt', b'As a customer, I want to log in so that I can access the portal. As an admin, I want to view analytics so that I can monitor adoption.')})
    assert upload.status_code == 200, upload.text
    plan = client.post(f'/api/projects/{project_id}/generate-plan')
    assert plan.status_code == 200, plan.text
    body = plan.json()
    assert body['summary']['task_count'] > 0


def test_member_crud_is_persisted(client):
    created = client.post('/api/team-members', json={
        'name': 'Rin Park', 'role': 'QA Engineer', 'skills': ['testing'], 'experience': 4,
        'hours_per_day': 7, 'working_days': ['Monday', 'Wednesday'], 'allocation': 75,
        'available_from': '2026-10-27', 'available_until': '2026-12-01', 'leave_dates': ['2026-11-02'],
    })
    assert created.status_code == 201, created.text
    member = created.json()
    assert member['id']
    assert member['working_days'] == ['Monday', 'Wednesday']
    assert client.get(f"/api/team-members/{member['id']}").json()['name'] == 'Rin Park'

    update = client.patch(f"/api/team-members/{member['id']}", json={'name': 'Rin Park Updated', 'allocation': 60})
    assert update.status_code == 200
    assert update.json()['allocation'] == 60
    client.app.state.test_engine.dispose()
    assert client.get('/api/team-members').json()[0]['name'] == 'Rin Park Updated'
    assert client.delete(f"/api/team-members/{member['id']}").status_code == 204
    assert client.get('/api/team-members').json() == []


def test_saved_plan_task_dashboard_archive_and_restore(client):
    member = client.post('/api/team-members', json={
        'name': 'Asha Patel', 'role': 'Frontend Developer', 'skills': ['react', 'ui', 'ux'],
        'experience': 6, 'hours_per_day': 8, 'allocation': 80,
    }).json()
    project = client.post('/api/projects', json={
        'name': 'Persistent Portal', 'description': 'Portal project', 'project_type': 'Web Application',
        'start_date': '2026-11-02', 'deadline': '2026-12-18', 'member_ids': [member['id']],
    })
    assert project.status_code == 201, project.text
    project_id = project.json()['id']
    upload = client.post(
        f'/api/projects/{project_id}/documents',
        files={'file': ('story.txt', b'As a customer, I want to sign in so that I can access my account.')},
    )
    assert upload.status_code == 200, upload.text
    generated = client.post(f'/api/projects/{project_id}/generate-plan')
    assert generated.status_code == 200, generated.text
    plan = generated.json()
    assert plan['project_id'] == project_id
    assert plan['tasks']
    workload_days = [day for day in plan['daily_workload'] if day['tasks']]
    assert workload_days
    assert all(day['allocated_hours'] <= day['capacity_hours'] for day in workload_days)
    member_workflow = [day for day in workload_days if day['member_id'] == member['id']]
    assert sum(len(day['tasks']) for day in member_workflow) >= 2
    assert all(task['category'] in {'UI/Frontend', 'Backend', 'QA/Testing', 'Integration', 'DevOps/Deployment', 'Documentation', 'Planning & Analysis', 'Other'} for task in plan['tasks'])

    reopened = client.get(f'/api/projects/{project_id}/plan').json()
    assert reopened['tasks'][0]['id'] == plan['tasks'][0]['id']
    assert reopened['tasks'][0]['assignee_id'] == member['id']
    task = reopened['tasks'][0]
    update = client.patch(f"/api/tasks/{task['id']}", json={'status': 'Completed'})
    assert update.status_code == 200
    in_progress_task = reopened['tasks'][1]
    assert client.patch(f"/api/tasks/{in_progress_task['id']}", json={'status': 'In Progress'}).status_code == 200
    client.app.state.test_engine.dispose()
    assert client.get(f'/api/projects/{project_id}/plan').json()['tasks'][0]['status'] == 'Completed'

    dashboard = client.get('/api/dashboard').json()
    assert dashboard['metrics']['total_projects'] == 1
    assert dashboard['metrics']['team_members'] == 1
    assert dashboard['metrics']['completed_projects'] == 0
    assert dashboard['metrics']['tasks_in_progress'] == 1
    assert dashboard['task_progress'][2]['value'] == 1
    assert dashboard['recent_projects'][0]['id'] == project_id

    assert [item['id'] for item in client.get('/api/projects').json()] == [project_id]
    assert client.get('/api/projects?archived=true').json() == []
    assert client.post(f'/api/projects/{project_id}/archive').status_code == 200
    archived_dashboard = client.get('/api/dashboard').json()
    assert archived_dashboard['metrics']['active_projects'] == 0
    assert archived_dashboard['metrics']['tasks_in_progress'] == 0
    assert client.get('/api/projects').json() == []
    assert [item['id'] for item in client.get('/api/projects?archived=true').json()] == [project_id]
    assert client.get(f'/api/projects/{project_id}/plan').json()['tasks']
    assert client.post(f'/api/projects/{project_id}/restore').status_code == 200
    assert client.get('/api/dashboard').json()['metrics']['tasks_in_progress'] == 1
    assert [item['id'] for item in client.get('/api/projects').json()] == [project_id]
    assert client.get('/api/projects?archived=true').json() == []
    assert client.get(f'/api/projects/{project_id}/tasks').json()[0]['status'] == 'Completed'
    assert client.delete(f"/api/team-members/{member['id']}").status_code == 409


def test_document_preview_replacement_and_project_update(client):
    first = client.post(
        '/api/documents/preview',
        files={'file': ('first.txt', b'As a customer, I want to reset my password so that I can securely sign in.')},
    )
    second = client.post(
        '/api/documents/preview',
        files={'file': ('second.txt', b'As a buyer, I want to track my order so that I know when it will arrive.')},
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()['stories'][0]['title'] != second.json()['stories'][0]['title']
    assert client.get('/api/projects').json() == []

    created = client.post('/api/projects', json={'name': 'Document Update', 'start_date': '2026-10-27'})
    assert created.status_code == 201, created.text
    project_id = created.json()['id']
    first_update = client.post(
        f'/api/projects/{project_id}/documents',
        files={'file': ('first.txt', b'As a customer, I want to reset my password so that I can securely sign in.')},
    )
    second_update = client.post(
        f'/api/projects/{project_id}/documents',
        files={'file': ('second.txt', b'As a buyer, I want to track my order so that I know when it will arrive.')},
    )
    assert first_update.status_code == 200, first_update.text
    assert second_update.status_code == 200, second_update.text
    assert client.get(f'/api/projects/{project_id}/stories').json()[0]['title'] == second.json()['stories'][0]['title']

    updated = client.patch(f'/api/projects/{project_id}', json={'name': 'Updated Document Project'})
    assert updated.status_code == 200, updated.text
    assert updated.json()['name'] == 'Updated Document Project'


def test_dashboard_recent_projects_excludes_drafts_and_archived_projects(client):
    draft = client.post('/api/projects', json={'name': 'Draft Only', 'start_date': '2026-10-27'})
    generated = client.post('/api/projects', json={'name': 'Generated Project', 'start_date': '2026-10-27'})
    duplicate = client.post('/api/projects', json={'name': '  generated   project ', 'start_date': '2026-10-27'})
    assert draft.status_code == 201
    assert generated.status_code == 201
    assert duplicate.status_code == 201
    generated_id = generated.json()['id']
    duplicate_id = duplicate.json()['id']
    with client.app.state.test_engine.begin() as connection:
        connection.exec_driver_sql("UPDATE projects SET status='Active', plan=? WHERE id IN (?, ?)", ('{"tasks": []}', generated_id, duplicate_id))

    active_projects = client.get('/api/projects').json()
    assert len(active_projects) == 1
    assert active_projects[0]['id'] == duplicate_id

    dashboard = client.get('/api/dashboard').json()
    assert [item['name'] for item in dashboard['recent_projects']] == ['  generated   project ']
    assert dashboard['metrics']['total_projects'] == 3
    assert dashboard['metrics']['active_projects'] == 2

    assert client.post(f'/api/projects/{generated_id}/archive').status_code == 200
    assert client.post(f'/api/projects/{duplicate_id}/archive').status_code == 200
    archived_dashboard = client.get('/api/dashboard').json()
    assert archived_dashboard['recent_projects'] == []
    assert archived_dashboard['metrics']['active_projects'] == 0
    assert archived_dashboard['project_status'][-1] == {'name': 'Archived', 'value': 2}
