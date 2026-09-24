from dotenv import load_dotenv
load_dotenv()
from app import create_app

app = create_app()
with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user'] = {'name': 'Craig Pell', 'email': 'cpell@peakmade.com', 'oid': 'dev-mode'}
        sess['is_developer'] = True
        sess['user_modules'] = [{'id': 9, 'name': 'Employee Data Manager', 'access': 'developer'}]

    rows_resp = client.get('/edm/api/soft-terminations')
    print('soft rows status', rows_resp.status_code)
    assert rows_resp.status_code == 200
    rows = rows_resp.get_json()
    print('soft rows', len(rows))
    if rows:
        print('first keys', sorted(rows[0].keys()))
        assert 'expires_on' in rows[0]
        assert 'added_by' in rows[0]

    search_resp = client.get('/edm/api/soft-terminations/employees?q=samantha')
    print('employee search status', search_resp.status_code)
    assert search_resp.status_code == 200
    matches = search_resp.get_json()
    print('matches', len(matches))
    assert isinstance(matches, list)

print('ALL OK')
