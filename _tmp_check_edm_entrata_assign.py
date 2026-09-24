from dotenv import load_dotenv
load_dotenv()
from jinja2 import Environment, FileSystemLoader
from app import create_app

print('Parsing edm.html...')
Environment(loader=FileSystemLoader('templates')).parse(open('templates/edm.html', encoding='utf-8').read())
print('edm.html OK')

app = create_app()
with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user'] = {'name': 'Craig Pell', 'email': 'cpell@peakmade.com', 'oid': 'dev-mode'}
        sess['is_developer'] = True
        sess['user_modules'] = [{'id': 9, 'name': 'Employee Data Manager', 'access': 'developer'}]

    page = client.get('/edm/')
    print('/edm/', page.status_code)
    assert page.status_code == 200
    assert b'Entrata Users' in page.data

    rows = client.get('/edm/api/entrata-group-assignments')
    print('/edm/api/entrata-group-assignments', rows.status_code)
    assert rows.status_code == 200
    data = rows.get_json()
    print('assignment rows', len(data))
    assert len(data) >= 1
    assert {'id', 'employee_code', 'entrata_permission_group', 'entrata_department', 'entrata_property_group'} <= set(data[0])

    opts = client.get('/edm/api/entrata-assignment-options')
    print('/edm/api/entrata-assignment-options', opts.status_code)
    assert opts.status_code == 200
    options = opts.get_json()
    print('options', {k: len(v) for k, v in options.items()})
    assert options['permission_groups'] and options['departments'] and options['property_groups']
    assert 'types' in options

    employees = client.get('/edm/api/entrata-assignment-employees?q=craig')
    print('/edm/api/entrata-assignment-employees?q=craig', employees.status_code)
    assert employees.status_code == 200
    print('employee matches', len(employees.get_json()))

print('ALL OK')
