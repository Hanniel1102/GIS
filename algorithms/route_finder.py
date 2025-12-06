"""
Route Finder - Tìm đường đến trạm sạc gần nhất
"""

import numpy as np
from scipy.spatial import cKDTree
import requests


def find_nearest_station(user_lat, user_lon, stations_gdf):
    """
    Tìm trạm sạc có đường đi NGẮN NHẤT (theo OSRM routing)
    
    Algorithm:
    1. Tìm 5 trạm gần nhất theo đường chim bay (KD-Tree)
    2. Gọi OSRM routing cho từng trạm để tính đường thực tế
    3. Chọn trạm có khoảng cách đường bộ ngắn nhất
    
    Parameters:
    -----------
    user_lat : float - Vĩ độ người dùng
    user_lon : float - Kinh độ người dùng
    stations_gdf : GeoDataFrame - Dữ liệu các trạm sạc
    
    Returns:
    --------
    dict - Thông tin trạm tối ưu và tuyến đường
    """
    
    if stations_gdf is None or len(stations_gdf) == 0:
        raise ValueError("Không có dữ liệu trạm sạc")
    
    # BƯỚC 1: Tìm 5 trạm gần nhất theo đường chim bay
    coords = np.array([[geom.y, geom.x] for geom in stations_gdf.geometry])
    tree = cKDTree(coords)
    
    user_point = np.array([[user_lat, user_lon]])
    k = min(5, len(stations_gdf))  # Tìm tối đa 5 trạm
    distances_euclidean, indices = tree.query(user_point, k=k)
    
    print(f"\n🔍 Tìm đường tối ưu cho {k} trạm ứng viên...")
    
    # BƯỚC 2: Tính đường đi thực tế cho từng trạm
    candidates = []
    
    for i, idx in enumerate(indices[0]):
        station = stations_gdf.iloc[idx]
        station_lat = station.geometry.y
        station_lon = station.geometry.x
        
        # Tính đường đi bằng OSRM
        route_result = calculate_route_osrm(user_lat, user_lon, station_lat, station_lon)
        
        candidates.append({
            'index': idx,
            'station': station,
            'distance_road': route_result['distance_km'],
            'duration': route_result['duration_min'],
            'route_coords': route_result['route_coords'],
            'route_geometry': route_result.get('route_geometry')  # GeoJSON geometry
        })
        
        print(f"   Trạm #{idx+1}: {route_result['distance_km']:.2f}km, {route_result['duration_min']:.1f}min")
    
    # BƯỚC 3: Chọn trạm có đường đi ngắn nhất
    best = min(candidates, key=lambda x: x['distance_road'])
    
    print(f"✅ Chọn trạm #{best['index']+1}: {best['distance_road']:.2f}km (ngắn nhất)\n")
    
    result = {
        'station': {
            'id': int(best['index'] + 1),  # Convert numpy.int64 to Python int
            'lat': float(best['station'].geometry.y),
            'lon': float(best['station'].geometry.x),
            'score': float(best['station'].get('score', 0))
        },
        'distance': float(round(best['distance_road'], 2)),
        'duration': float(round(best['duration'], 1)),
        'route_coords': best['route_coords'],
        'route_geometry': best['route_geometry']  # Thêm geometry để frontend vẽ
    }
    
    return result


def calculate_route_osrm(from_lat, from_lon, to_lat, to_lon):
    """
    Tính đường đi bằng OSRM API
    
    Returns:
    --------
    dict với keys: distance_km, duration_min, route_coords, route_geometry
    """
    try:
        url = f"https://router.project-osrm.org/route/v1/driving/{from_lon},{from_lat};{to_lon},{to_lat}?overview=full&geometries=geojson"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if data.get('routes') and len(data['routes']) > 0:
            route = data['routes'][0]
            
            # Lấy tọa độ tuyến đường (convert [lon,lat] → [lat,lon])
            route_coords = [[coord[1], coord[0]] for coord in route['geometry']['coordinates']]
            
            return {
                'distance_km': route['distance'] / 1000,
                'duration_min': route['duration'] / 60,
                'route_coords': route_coords,
                'route_geometry': route['geometry']  # GeoJSON format
            }
    except Exception as e:
        print(f"⚠️ OSRM error: {e}")
    
    # Fallback: đường thẳng
    distance_km = haversine_distance(from_lat, from_lon, to_lat, to_lon)
    return {
        'distance_km': distance_km,
        'duration_min': distance_km / 30 * 60,  # Giả sử 30km/h
        'route_coords': [[from_lat, from_lon], [to_lat, to_lon]],
        'route_geometry': None
    }


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Tính khoảng cách Haversine giữa 2 điểm (km)
    """
    R = 6371  # Bán kính Trái Đất (km)
    
    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    
    a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    
    return R * c
