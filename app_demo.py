"""
EV Charging Station Viewer - Demo với 100 trạm có sẵn
Ứng dụng xem bản đồ trạm sạc đã tối ưu sẵn (không cần chạy thuật toán)
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
import geopandas as gpd
import os

app = Flask(__name__)

# Load dữ liệu GIS
DATA_FOLDER = 'data'
stations_data = None
boundary_data = None
residential_data = None
substations_data = None
poi_data = None
roads_data = None

try:
    # 1. Trạm sạc tối ưu (100 trạm)
    stations_file = os.path.join(DATA_FOLDER, 'optimal_ev_stations_GA.shp')
    if os.path.exists(stations_file):
        stations_data = gpd.read_file(stations_file)
        print(f"✅ Loaded {len(stations_data)} stations")
    
    # 2. Ranh giới Hà Nội
    boundary_file = os.path.join(DATA_FOLDER, 'hanoi_boundary.shp')
    if os.path.exists(boundary_file):
        boundary_data = gpd.read_file(boundary_file)
        print(f"✅ Loaded boundary")
    
    # 3. Khu dân cư
    residential_file = os.path.join(DATA_FOLDER, 'residential_only.shp')
    if os.path.exists(residential_file):
        residential_data = gpd.read_file(residential_file)
        print(f"✅ Loaded {len(residential_data)} residential areas")
    
    # 4. Trạm biến áp
    substations_file = os.path.join(DATA_FOLDER, 'substations_real.shp')
    if os.path.exists(substations_file):
        substations_data = gpd.read_file(substations_file)
        print(f"✅ Loaded {len(substations_data)} substations")
    
    # 5. POI
    poi_file = os.path.join(DATA_FOLDER, 'points_hanoi_full.shp')
    if os.path.exists(poi_file):
        poi_data = gpd.read_file(poi_file)
        # Lấy mẫu để giảm dung lượng
        if len(poi_data) > 500:
            poi_data = poi_data.sample(500)
        print(f"✅ Loaded {len(poi_data)} POI")
    
    # 6. Roads (Đường giao thông) - sample để tránh quá nặng
    roads_file = os.path.join(DATA_FOLDER, 'roads_hanoi_full.shp')
    if os.path.exists(roads_file):
        roads_data = gpd.read_file(roads_file)
        # Lấy mẫu để giảm dung lượng
        if len(roads_data) > 1000:
            roads_data = roads_data.sample(1000)
        print(f"✅ Loaded {len(roads_data)} roads")
        
except Exception as e:
    print(f"❌ Error loading data: {e}")


@app.route('/')
def index():
    """Trang chủ - Hiển thị bản đồ có sẵn"""
    
    if stations_data is None:
        return """
        <html>
        <head>
            <title>Lỗi - Không có dữ liệu</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }
                .error-box {
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    text-align: center;
                }
                h1 { color: #e74c3c; }
                p { color: #555; margin: 20px 0; }
                code {
                    background: #f4f4f4;
                    padding: 5px 10px;
                    border-radius: 5px;
                    display: block;
                    margin: 10px 0;
                }
            </style>
        </head>
        <body>
            <div class="error-box">
                <h1>❌ Không tìm thấy dữ liệu trạm sạc</h1>
                <p>File shapefile không tồn tại:</p>
                <code>layer_gis_1/optimal_ev_stations_GA.shp</code>
                <p>Vui lòng chạy notebook <code>PJ_GIS.ipynb</code> để tạo dữ liệu trước.</p>
            </div>
        </body>
        </html>
        """
    
    # Thống kê
    num_stations = len(stations_data)
    avg_score = stations_data['score'].mean() if 'score' in stations_data.columns else 0
    
    # Chuyển đổi sang JSON cho JavaScript
    stations_json = []
    for idx, row in stations_data.iterrows():
        stations_json.append({
            'id': int(idx + 1),
            'lat': float(row.geometry.y),
            'lon': float(row.geometry.x),
            'score': float(row.get('score', 0)) if 'score' in stations_data.columns else 0
        })
    
    # Boundary JSON
    boundary_json = None
    if boundary_data is not None:
        boundary_json = boundary_data.to_json()
    
    # Residential JSON
    residential_json = None
    if residential_data is not None:
        residential_json = residential_data.to_json()
    
    # Substations JSON
    substations_json = []
    if substations_data is not None:
        for idx, row in substations_data.iterrows():
            substations_json.append({
                'lat': float(row.geometry.y),
                'lon': float(row.geometry.x),
                'name': row.get('name', f'Trạm {idx+1}')
            })
    
    # POI JSON
    poi_json = []
    if poi_data is not None:
        for idx, row in poi_data.iterrows():
            poi_json.append({
                'lat': float(row.geometry.y),
                'lon': float(row.geometry.x),
                'type': row.get('fclass', 'unknown'),
                'name': row.get('name', '')
            })
    
    # Roads JSON
    roads_json = None
    if roads_data is not None:
        roads_json = roads_data.to_json()
    
    return render_template('demo_viewer.html',
                         num_stations=num_stations,
                         avg_score=round(avg_score, 2),
                         stations_json=stations_json,
                         boundary_json=boundary_json,
                         residential_json=residential_json,
                         substations_json=substations_json,
                         poi_json=poi_json,
                         roads_json=roads_json)


@app.route('/api/stations')
def get_stations():
    """API lấy danh sách trạm sạc"""
    if stations_data is None:
        return jsonify({'success': False, 'error': 'No data'}), 404
    
    stations_list = []
    for idx, row in stations_data.iterrows():
        stations_list.append({
            'id': int(idx + 1),
            'lat': float(row.geometry.y),
            'lon': float(row.geometry.x),
            'score': float(row.get('score', 0)) if 'score' in stations_data.columns else 0,
            'dist_res': float(row.get('dist_res', 0)) if 'dist_res' in stations_data.columns else 0,
            'dist_sub': float(row.get('dist_sub', 0)) if 'dist_sub' in stations_data.columns else 0
        })
    
    return jsonify({
        'success': True,
        'stations': stations_list,
        'total': len(stations_list)
    })


@app.route('/api/find_route', methods=['POST'])
def find_route():
    """API tìm trạm gần nhất"""
    try:
        from algorithms.route_finder import find_nearest_station
        
        if stations_data is None:
            print("⚠️ No stations data loaded")
            return jsonify({'success': False, 'error': 'No station data available'}), 404
        
        data = request.get_json()
        if not data:
            print("⚠️ No JSON data received")
            return jsonify({'success': False, 'error': 'No data received'}), 400
            
        user_lat = data.get('lat')
        user_lon = data.get('lon')
        
        if user_lat is None or user_lon is None:
            print(f"⚠️ Missing coordinates: lat={user_lat}, lon={user_lon}")
            return jsonify({'success': False, 'error': 'Missing coordinates (lat, lon required)'}), 400
        
        # Validate coordinates
        try:
            user_lat = float(user_lat)
            user_lon = float(user_lon)
        except (ValueError, TypeError):
            print(f"⚠️ Invalid coordinates: lat={user_lat}, lon={user_lon}")
            return jsonify({'success': False, 'error': 'Invalid coordinate format'}), 400
        
        # Check if coordinates are in reasonable range for Hanoi
        if not (20.5 <= user_lat <= 21.5 and 105.0 <= user_lon <= 106.5):
            print(f"⚠️ Coordinates out of range: lat={user_lat}, lon={user_lon}")
            return jsonify({'success': False, 'error': 'Coordinates outside Hanoi area'}), 400
        
        # Tìm trạm có đường đi ngắn nhất
        result = find_nearest_station(user_lat, user_lon, stations_data)
        
        if not result or 'station' not in result:
            print("⚠️ No station found")
            return jsonify({'success': False, 'error': 'Could not find nearest station'}), 500
        
        return jsonify({
            'success': True,
            'station': result['station'],
            'distance': result['distance'],
            'duration': result['duration'],
            'route': result['route_coords'],
            'route_geometry': result.get('route_geometry')
        })
        
    except Exception as e:
        print(f"❌ Error in find_route: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500


@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'version': 'demo-1.0',
        'stations_loaded': stations_data is not None,
        'num_stations': len(stations_data) if stations_data is not None else 0
    })


@app.route('/favicon.ico')
def favicon():
    """Serve favicon to avoid 404 error"""
    return '', 204


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🗺️  EV CHARGING STATION VIEWER - DEMO MODE")
    print("="*60)
    if stations_data is not None:
        print(f"✅ Loaded: {len(stations_data)} stations (pre-optimized)")
        print(f"📊 Avg Score: {stations_data['score'].mean():.1f}/100" if 'score' in stations_data.columns else "")
    else:
        print("⚠️  No station data loaded")
    print("="*60)
    print("🌐 Open: http://localhost:5001")
    print("="*60 + "\n")
    
    app.run(
        host='0.0.0.0',
        port=5001,  # Port khác để không conflict với app chính
        debug=True
    )
