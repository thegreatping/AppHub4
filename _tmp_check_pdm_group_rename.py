from dotenv import load_dotenv
load_dotenv()
from app import create_app

app = create_app()
with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user'] = {'name': 'Craig Pell', 'email': 'cpell@peakmade.com', 'oid': 'dev-mode'}
        sess['is_developer'] = True
        sess['user_modules'] = [{'id': 10, 'name': 'Property Data Manager', 'access': 'developer'}]

    groups_resp = client.get('/pdm/api/property-groups')
    print('groups status', groups_resp.status_code)
    assert groups_resp.status_code == 200
    groups = groups_resp.get_json()['groups']
    print('groups', len(groups))
    assert groups
    row = next(g for g in groups if g.get('PROPERTY_GROUP_NAME'))
    print('test key/name/count', row['PROPERTY_GROUP_KEY'], row['PROPERTY_GROUP_NAME'], row.get('PROPERTY_COUNT'))

    patch_resp = client.patch(
        f"/pdm/api/property-groups/{row['PROPERTY_GROUP_KEY']}",
        json={'PROPERTY_GROUP_NAME': row['PROPERTY_GROUP_NAME']}
    )
    print('patch status', patch_resp.status_code, patch_resp.get_json())
    assert patch_resp.status_code == 200
    assert patch_resp.get_json().get('property_rows_updated') == 0

print('ALL OK')
