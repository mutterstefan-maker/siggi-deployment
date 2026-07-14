# ADD THESE IMPORTS TO app.py:
from analytics_engine import AnalyticsEngine
import os

# INITIALIZE AFTER LOADING DATABASE:
credentials_file = os.path.join(BASE_DIR, 'siggi-dashboard-ac0baeaaaef6.json')
property_id = '534389721'  # chefblick.de

if os.path.exists(credentials_file):
    analytics = AnalyticsEngine(credentials_file, property_id)
else:
    analytics = None

# ADD THESE ROUTES AT THE END BEFORE if __name__ == '__main__':

@app.route('/api/analytics/summary', methods=['GET'])
def get_analytics_summary():
    """Get Analytics summary for last 7 days"""
    if not analytics:
        return jsonify({'error': 'Analytics not configured'}), 500
    
    try:
        days = request.args.get('days', 7, type=int)
        summary = analytics.get_traffic_summary(days)
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/top-pages', methods=['GET'])
def get_top_pages():
    """Get top pages by pageviews"""
    if not analytics:
        return jsonify({'error': 'Analytics not configured'}), 500
    
    try:
        days = request.args.get('days', 7, type=int)
        pages = analytics.get_top_pages(days)
        return jsonify({'pages': pages})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/sources', methods=['GET'])
def get_traffic_sources():
    """Get traffic by source"""
    if not analytics:
        return jsonify({'error': 'Analytics not configured'}), 500
    
    try:
        days = request.args.get('days', 7, type=int)
        sources = analytics.get_traffic_sources(days)
        return jsonify({'sources': sources})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
