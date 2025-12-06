"""
EV Charging Station Optimizer - Web Application
Ứng dụng web tối ưu hóa vị trí trạm sạc xe điện
"""

from flask import Flask, render_template, request, jsonify, send_file
import geopandas as gpd
import folium
import json
import os
from algorithms.genetic_optimizer import optimize_stations
from algorithms.route_finder import find_nearest_station

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'data/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

# Global variables
stations_data = None
boundary_data = None

@app.route('/')
def index():
    """Trang chủ"""
    return render_template('index.html')

@app.route('/map')
def map_view():
    """Hiển thị bản đồ tương tác với đầy đủ layers"""
    global stations_data
    
    if stations_data is None:
        return render_template('map_dynamic.html', has_data=False)
    
    # Tạo map trung tâm Hà Nội
    m = folium.Map(
        location=[21.0285, 105.8542],
        zoom_start=12,
        tiles='OpenStreetMap'
    )
    
    # ========== LOAD CÁC LAYER GIS ==========
    # 1. Layer giới hạn Hà Nội
    try:
        boundary = gpd.read_file('data/hanoi_boundary.shp')
        folium.GeoJson(
            boundary,
            name='🗺️ Giới hạn Hà Nội',
            style_function=lambda x: {
                'fillColor': 'transparent',
                'color': 'red',
                'weight': 3,
                'dashArray': '5, 5'
            }
        ).add_to(m)
    except:
        pass
    
    # 2. Layer POI (Points of Interest) - từ points_hanoi_full.shp
    try:
        poi_data = gpd.read_file('data/points_hanoi_full.shp')
        # Lọc các loại POI quan trọng
        important_types = ['bank', 'hospital', 'school', 'university', 'supermarket', 
                          'mall', 'market_place', 'restaurant', 'cafe', 'post_office']
        
        if 'fclass' in poi_data.columns:
            poi_filtered = poi_data[poi_data['fclass'].isin(important_types)]
            if len(poi_filtered) == 0:
                poi_filtered = poi_data.sample(min(100, len(poi_data)))
        else:
            poi_filtered = poi_data.sample(min(100, len(poi_data)))
        
        poi_layer = folium.FeatureGroup(name='🏢 POI (Bank, Shop, etc)', show=False)
        for idx, row in poi_filtered.iterrows():
            poi_name = row.get('name', 'POI') if 'name' in poi_filtered.columns else 'POI'
            poi_type = row.get('fclass', 'unknown') if 'fclass' in poi_filtered.columns else 'unknown'
            
            # Xử lý cả Point và Polygon
            geom = row.geometry
            if geom.geom_type == 'Point':
                lat, lon = geom.y, geom.x
            else:
                lat, lon = geom.centroid.y, geom.centroid.x
            
            folium.CircleMarker(
                location=[lat, lon],
                radius=5,
                color='purple',
                fill=True,
                fillColor='purple',
                fillOpacity=0.7,
                popup=f'🏢 {poi_type}: {poi_name}'
            ).add_to(poi_layer)
        poi_layer.add_to(m)
    except Exception as e:
        print(f"⚠️ Không load được POI: {e}")
        pass
    
    # 3. Layer khu dân cư (Residential only - extracted from landuse)
    try:
        # Đọc file residential_only.shp (đã trích xuất từ landuse)
        residential = gpd.read_file('data/residential_only.shp')
        
        print(f"✅ Loaded residential layer: {len(residential)} vùng dân cư")
        
        # Vẽ lớp dân cư như Polygon với màu phủ
        folium.GeoJson(
            residential,
            name='🏘️ Khu dân cư (Residential)',
            style_function=lambda x: {
                'fillColor': '#FFA500',  # Màu cam
                'color': '#FF8C00',      # Viền cam đậm
                'weight': 1,
                'fillOpacity': 0.4
            },
            popup=folium.GeoJsonPopup(fields=['fclass'], aliases=['Loại đất:'])
        ).add_to(m)
    except Exception as e:
        print(f"⚠️ Không load được residential: {e}")
        pass
    
    # 4. Layer trạm biến áp
    try:
        substations = gpd.read_file('data/substations_real.shp')
        substations_layer = folium.FeatureGroup(name='⚡ Trạm biến áp', show=False)
        
        for idx, row in substations.iterrows():
            # Xử lý cả Point và Polygon
            geom = row.geometry
            if geom.geom_type == 'Point':
                lat, lon = geom.y, geom.x
            else:
                lat, lon = geom.centroid.y, geom.centroid.x
            
            folium.Marker(
                location=[lat, lon],
                popup=f'⚡ Trạm biến áp #{idx+1}',
                icon=folium.Icon(color='orange', icon='bolt', prefix='fa')
            ).add_to(substations_layer)
        substations_layer.add_to(m)
    except:
        pass
    
    # 5. Layer vùng phủ sóng (Coverage area)
    try:
        # Tạo buffer xung quanh mỗi trạm sạc (bán kính phủ sóng)
        coverage_radius_km = 3  # 3km bán kính phủ sóng
        
        # Chuyển sang UTM để tính buffer chính xác
        stations_utm = stations_data.to_crs('EPSG:32648')
        stations_utm['buffer'] = stations_utm.geometry.buffer(coverage_radius_km * 1000)  # meters
        
        # Tạo GeoDataFrame với geometry là buffer
        coverage_gdf = gpd.GeoDataFrame(
            stations_utm[['score', 'dist_res', 'dist_sub']], 
            geometry=stations_utm['buffer'],
            crs='EPSG:32648'
        )
        
        # Chuyển về WGS84 để hiển thị
        coverage_gdf = coverage_gdf.to_crs('EPSG:4326')
        
        print(f"✅ Created coverage layer: {len(coverage_gdf)} zones, radius={coverage_radius_km}km")
        
        # Vẽ lớp vùng phủ sóng
        folium.GeoJson(
            coverage_gdf,
            name=f'📡 Vùng phủ sóng ({coverage_radius_km}km)',
            style_function=lambda x: {
                'fillColor': '#4CAF50',  # Màu xanh lá
                'color': '#2E7D32',      # Viền xanh đậm
                'weight': 2,
                'fillOpacity': 0.2,
                'dashArray': '5, 5'
            },
            popup=folium.GeoJsonPopup(
                fields=['score', 'dist_res', 'dist_sub'],
                aliases=['Điểm:', 'Gần dân cư (m):', 'Gần trạm (m):']
            )
        ).add_to(m)
    except Exception as e:
        print(f"⚠️ Không tạo được coverage layer: {e}")
    
    # 6. Layer trạm sạc tối ưu
    stations_layer = folium.FeatureGroup(name='🔌 Trạm sạc tối ưu', show=True)
    for idx, row in stations_data.iterrows():
        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            popup=f"""
                <b>🔌 Trạm sạc #{idx+1}</b><br>
                📊 Score: {row['score']:.1f}<br>
                📏 Gần dân cư: {row['dist_res']:.0f}m<br>
                ⚡ Gần trạm: {row['dist_sub']:.0f}m<br>
                📡 Bán kính phủ sóng: {coverage_radius_km}km<br>
                🌍 Lat: {row.geometry.y:.6f}<br>
                🌍 Lon: {row.geometry.x:.6f}
            """,
            icon=folium.Icon(color='green', icon='charging-station', prefix='fa')
        ).add_to(stations_layer)
    stations_layer.add_to(m)
    
    # Thêm Layer Control
    folium.LayerControl(position='topright', collapsed=False).add_to(m)
    
    # Thêm JavaScript để xử lý click trên bản đồ
    click_js = """
    <script>
    var clickModeActive = false;
    var clickMarker = null;
    var routePolyline = null;
    
    function toggleClickMode() {
        clickModeActive = !clickModeActive;
        var btn = parent.document.getElementById('click-mode-text');
        if (btn) {
            btn.textContent = clickModeActive ? '✅ Click mode ON' : '🖱️ Click trên bản đồ';
        }
        if (clickModeActive) {
            alert('✅ Click mode BẬT. Click vào bản đồ để chọn vị trí.');
        }
    }
    
    // Lắng nghe sự kiện click trên map
    map.on('click', function(e) {
        if (clickModeActive) {
            var lat = e.latlng.lat;
            var lon = e.latlng.lng;
            
            // Xóa marker cũ
            if (clickMarker) {
                map.removeLayer(clickMarker);
            }
            
            // Thêm marker mới
            clickMarker = L.marker([lat, lon], {
                icon: L.icon({
                    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
                    iconSize: [25, 41],
                    iconAnchor: [12, 41]
                })
            }).addTo(map);
            clickMarker.bindPopup('📍 Vị trí đã chọn').openPopup();
            
            // Gửi tọa độ ra ngoài iframe
            if (parent.window.handleMapClick) {
                parent.window.handleMapClick(lat, lon);
            }
        }
    });
    
    // Cho phép gọi từ bên ngoài
    window.toggleClickMode = toggleClickMode;
    </script>
    """
    
    # Lưu map thành file HTML riêng
    map_file = 'static/temp_map.html'
    m.save(map_file)
    
    # Thêm JavaScript để nhận message từ parent và vẽ route
    route_js = """
    <script>
    var userMarker = null;
    var routeLine = null;
    var nearestMarker = null;
    
    // Tìm map object
    function getMapObject() {
        // Tìm tất cả biến có tên bắt đầu bằng 'map_'
        var mapIds = Object.keys(window).filter(key => key.startsWith('map_'));
        if (mapIds.length > 0) {
            console.log('Found map:', mapIds[0]);
            return window[mapIds[0]];
        }
        
        // Fallback: tìm qua DOM
        var leafletContainers = document.querySelectorAll('.leaflet-container');
        for (var i = 0; i < leafletContainers.length; i++) {
            if (leafletContainers[i]._leaflet_map) {
                console.log('Found map via container');
                return leafletContainers[i]._leaflet_map;
            }
        }
        
        console.error('Map not found!');
        return null;
    }
    
    // Nhận message từ parent window
    window.addEventListener('message', function(event) {
        if (event.data && event.data.type === 'drawRoute') {
            var data = event.data;
            var map = getMapObject();
            
            if (!map) {
                console.error('Cannot find map object');
                return;
            }
            
            // Xóa markers/lines cũ
            if (userMarker) map.removeLayer(userMarker);
            if (routeLine) map.removeLayer(routeLine);
            if (nearestMarker) map.removeLayer(nearestMarker);
            
            // Thêm user marker
            userMarker = L.marker([data.userLat, data.userLon], {
                icon: L.icon({
                    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
                    iconSize: [25, 41],
                    iconAnchor: [12, 41]
                })
            }).addTo(map);
            userMarker.bindPopup('<b>📍 Vị trí của bạn</b>').openPopup();
            
            // Vẽ route
            if (data.routeData && data.routeData.geometry) {
                var coords = data.routeData.geometry.coordinates.map(c => [c[1], c[0]]);
                routeLine = L.polyline(coords, {
                    color: '#2196F3',
                    weight: 5,
                    opacity: 0.8
                }).addTo(map);
            } else {
                routeLine = L.polyline(
                    [[data.userLat, data.userLon], [data.stationLat, data.stationLon]],
                    {color: 'blue', weight: 4, opacity: 0.7, dashArray: '10, 10'}
                ).addTo(map);
            }
            
            // Thêm station marker
            nearestMarker = L.circleMarker([data.stationLat, data.stationLon], {
                radius: 15,
                color: 'red',
                fillColor: 'yellow',
                fillOpacity: 0.5,
                weight: 3
            }).addTo(map);
            
            var durationText = data.duration ? '<br>⏱️ Thời gian: <b>' + data.duration.toFixed(0) + ' phút</b>' : '';
            var popup = '<div style="width: 220px;">' +
                '<b>🎯 TRẠM GẦN NHẤT</b><br>' +
                '<hr style="margin: 5px 0;">' +
                '🔌 Trạm #' + data.stationId + '<br>' +
                '📏 Khoảng cách: <b>' + data.distance.toFixed(2) + ' km</b>' + durationText + '<br>' +
                '⭐ Điểm: ' + data.stationScore + '/100<br>' +
                '<hr style="margin: 5px 0;">' +
                '<small>🛣️ Tính theo mạng lưới đường</small>' +
                '</div>';
            nearestMarker.bindPopup(popup).openPopup();
            
            // Zoom to fit
            map.fitBounds([[data.userLat, data.userLon], [data.stationLat, data.stationLon]], {padding: [50, 50]});
            
            console.log('✅ Route drawn successfully!');
        }
    });
    
    console.log('✅ Map ready to receive route commands');
    </script>
    """
    
    # Đọc file HTML và thêm JavaScript
    with open(map_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    html_content = html_content.replace('</body>', route_js + '</body>')
    
    with open(map_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Chuyển đổi stations_data sang JSON cho JavaScript
    stations_json = []
    for idx, row in stations_data.iterrows():
        stations_json.append({
            'id': idx + 1,
            'lat': float(row.geometry.y),
            'lon': float(row.geometry.x),
            'score': float(row['score'])
        })
    
    return render_template('map_dynamic.html', 
                         has_data=True, 
                         map_file='temp_map.html',
                         num_stations=len(stations_data),
                         stations_json=stations_json)  # Không dùng json.dumps, để Jinja tự xử lý

@app.route('/api/optimize', methods=['POST'])
def optimize():
    """API tối ưu hóa vị trí trạm sạc"""
    try:
        data = request.get_json()
        num_stations = data.get('num_stations', 100)
        population_size = data.get('population', 50)
        generations = data.get('generations', 100)
        
        print(f"\n🚀 API /api/optimize called with:")
        print(f"   Stations: {num_stations}, Population: {population_size}, Generations: {generations}")
        
        # Kiểm tra dữ liệu GIS có tồn tại không
        if not os.path.exists('data/hanoi_boundary.shp'):
            return jsonify({
                'error': 'Chưa có dữ liệu GIS. Vui lòng copy file shapefile vào thư mục data/'
            }), 400
        
        # Load dữ liệu GIS
        boundary = gpd.read_file('data/hanoi_boundary.shp')
        
        # Dùng candidates.shp (grid 500m) làm dữ liệu dân cư
        # points_hanoi_full.shp là POI (bank, hospital, etc) không phải dân cư
        residential = gpd.read_file('data/landuse_hanoi_full.shp')
        
        substations = gpd.read_file('data/substations_real.shp')
        roads = gpd.read_file('data/roads_hanoi_full.shp')
        
        print(f"📊 Loaded GIS data:")
        print(f"   Boundary: {len(boundary)} polygons")
        print(f"   Residential (candidates grid): {len(residential)} points")
        print(f"   Substations: {len(substations)} stations")
        print(f"   Roads: {len(roads)} segments")
        
        # Chạy thuật toán tối ưu
        result = optimize_stations(
            boundary=boundary,
            residential=residential,
            substations=substations,
            roads=roads,
            num_stations=num_stations,
            population_size=population_size,
            generations=generations
        )
        
        global stations_data
        stations_data = result
        
        avg_score = float(result['score'].mean())
        print(f"\n✅ Optimization completed!")
        print(f"   Stations: {len(result)}, Avg Score: {avg_score:.2f}")
        
        return jsonify({
            'success': True,
            'num_stations': len(result),
            'avg_score': avg_score,
            'data': result.to_json()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/find_route', methods=['POST'])
def find_route():
    """API tìm đường đến trạm gần nhất"""
    try:
        data = request.get_json()
        user_lat = data.get('lat')
        user_lon = data.get('lon')
        
        if not user_lat or not user_lon:
            return jsonify({'success': False, 'error': 'Missing coordinates'}), 400
        
        # Tìm trạm gần nhất
        result = find_nearest_station(user_lat, user_lon, stations_data)
        
        return jsonify({
            'success': True,
            'station': result['station'],
            'distance': result['distance'],
            'duration': result['duration'],
            'route': result['route_coords']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/upload_data', methods=['POST'])
def upload_data():
    """API upload dữ liệu GIS"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        data_type = request.form.get('type')  # boundary, residential, etc.
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Empty filename'}), 400
        
        # Lưu file
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{data_type}.shp")
        file.save(filepath)
        
        return jsonify({'success': True, 'message': f'{data_type} uploaded successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/export_results', methods=['GET'])
def export_results():
    """API xuất kết quả"""
    try:
        format_type = request.args.get('format', 'geojson')
        
        if stations_data is None:
            return jsonify({'success': False, 'error': 'No data to export'}), 400
        
        if format_type == 'geojson':
            output = stations_data.to_json()
            return output, 200, {'Content-Type': 'application/json'}
        
        elif format_type == 'shapefile':
            output_path = 'data/exports/optimal_stations.shp'
            stations_data.to_file(output_path)
            return send_file(output_path, as_attachment=True)
        
        elif format_type == 'excel':
            output_path = 'data/exports/optimal_stations.xlsx'
            report = stations_data.copy()
            report['lon'] = report.geometry.x
            report['lat'] = report.geometry.y
            report.to_excel(output_path, index=False)
            return send_file(output_path, as_attachment=True)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'version': '1.0.0'})

@app.route('/favicon.ico')
def favicon():
    """Favicon endpoint - return 204 no content"""
    return '', 204

if __name__ == '__main__':
    # Tạo thư mục cần thiết
    os.makedirs('data/uploads', exist_ok=True)
    os.makedirs('data/exports', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    # Chạy server
    app.run(
        host='0.0.0.0',  # Cho phép truy cập từ mạng LAN
        port=5000,
        debug=True
    )
