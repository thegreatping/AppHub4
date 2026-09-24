from dotenv import load_dotenv
load_dotenv()
from app import create_app

app = create_app()
with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user'] = {'name': 'Craig Pell', 'email': 'cpell@peakmade.com', 'oid': 'dev-mode'}
        sess['is_developer'] = True
        sess['user_modules'] = [{'id': 10, 'name': 'Property Data Manager', 'access': 'developer'}]

    markets_resp = client.get('/pdm/api/markets')
    print('markets status', markets_resp.status_code)
    assert markets_resp.status_code == 200
    markets = markets_resp.get_json()['markets']
    print('markets', len(markets))
    assert markets and 'ACTIVE_PROPERTY_COUNT' in markets[0]
    target = next((m for m in markets if (m.get('ACTIVE_PROPERTY_COUNT') or 0) > 0), markets[0])
    print('target', target.get('MARKET_KEY'), target.get('MARKET_CITY_STATE'), target.get('MARKET_STATE'), target.get('ACTIVE_PROPERTY_COUNT'))

    detail_resp = client.get(f"/pdm/api/markets/{target['MARKET_KEY']}/properties")
    print('detail status', detail_resp.status_code)
    assert detail_resp.status_code == 200
    detail = detail_resp.get_json()
    props = detail['properties']
    print('properties', len(props))
    assert len(props) == (target.get('ACTIVE_PROPERTY_COUNT') or 0)
    if props:
        assert props[0]['MARKET_STATE'] == target['MARKET_STATE']

print('ALL OK')
