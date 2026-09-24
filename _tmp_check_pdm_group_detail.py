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
    assert groups and 'ACTIVE_PROPERTY_COUNT' in groups[0]
    target = next((g for g in groups if (g.get('ACTIVE_PROPERTY_COUNT') or 0) > 0), groups[0])
    print('target', target.get('PROPERTY_GROUP_KEY'), target.get('PROPERTY_GROUP_NAME'), target.get('ACTIVE_PROPERTY_COUNT'))

    detail_resp = client.get(f"/pdm/api/property-groups/{target['PROPERTY_GROUP_KEY']}/properties")
    print('detail status', detail_resp.status_code)
    assert detail_resp.status_code == 200
    detail = detail_resp.get_json()
    props = detail['properties']
    print('properties', len(props))
    assert len(props) == (target.get('ACTIVE_PROPERTY_COUNT') or 0)
    if props:
        assert props[0]['PROPERTY_GROUP'] == target['PROPERTY_GROUP_NAME']

print('ALL OK')
