import json
import os
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from datetime import datetime, timedelta

class AnalyticsEngine:
    def __init__(self, credentials_file, property_id):
        self.property_id = property_id
        with open(credentials_file) as f:
            creds_dict = json.load(f)
        self.credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/analytics.readonly'])
        self.credentials.refresh(Request())
        self.access_token = self.credentials.token
    
    def _make_request(self, body):
        import urllib.request
        url = f'https://analyticsdata.googleapis.com/v1beta/properties/{self.property_id}:runReport'
        headers = {'Authorization': f'Bearer {self.access_token}', 'Content-Type': 'application/json'}
        data = json.dumps(body).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    
    def get_traffic_summary(self, days=7):
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        body = {'dateRanges': [{'startDate': start_date, 'endDate': end_date}], 'dimensions': [{'name': 'date'}], 'metrics': [{'name': 'activeUsers'}, {'name': 'screenPageViews'}, {'name': 'bounceRate'}, {'name': 'averageSessionDuration'}]}
        response = self._make_request(body)
        data = {'total_users': 0, 'total_pageviews': 0, 'avg_bounce_rate': 0, 'avg_session_duration': 0, 'daily': []}
        for row in response.get('rows', []):
            date, users, pageviews, bounce_rate, session_duration = row['dimensionValues'][0]['value'], int(row['metricValues'][0]['value']), int(row['metricValues'][1]['value']), float(row['metricValues'][2]['value']), float(row['metricValues'][3]['value'])
            data['total_users'] += users
            data['total_pageviews'] += pageviews
            data['daily'].append({'date': date, 'users': users, 'pageviews': pageviews, 'bounce_rate': bounce_rate, 'session_duration': session_duration})
        if data['daily']:
            data['avg_bounce_rate'] = round(sum(d['bounce_rate'] for d in data['daily']) / len(data['daily']), 2)
            data['avg_session_duration'] = round(sum(d['session_duration'] for d in data['daily']) / len(data['daily']), 2)
        return data
    
    def get_top_pages(self, days=7):
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        body = {'dateRanges': [{'startDate': start_date, 'endDate': end_date}], 'dimensions': [{'name': 'pagePath'}], 'metrics': [{'name': 'screenPageViews'}, {'name': 'activeUsers'}, {'name': 'averageSessionDuration'}], 'limit': 10}
        response = self._make_request(body)
        pages = [{'page': row['dimensionValues'][0]['value'], 'pageviews': int(row['metricValues'][0]['value']), 'users': int(row['metricValues'][1]['value']), 'avg_duration': round(float(row['metricValues'][2]['value']), 2)} for row in response.get('rows', [])]
        return sorted(pages, key=lambda x: x['pageviews'], reverse=True)
    
    def get_traffic_sources(self, days=7):
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        body = {'dateRanges': [{'startDate': start_date, 'endDate': end_date}], 'dimensions': [{'name': 'sessionDefaultChannelGroup'}], 'metrics': [{'name': 'activeUsers'}, {'name': 'screenPageViews'}]}
        response = self._make_request(body)
        return [{'channel': row['dimensionValues'][0]['value'], 'users': int(row['metricValues'][0]['value']), 'pageviews': int(row['metricValues'][1]['value'])} for row in response.get('rows', [])]