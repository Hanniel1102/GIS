"""
Route Finder - Tìm đường đến trạm sạc gần nhất
"""

import numpy as np
from scipy.spatial import cKDTree
import requests


def find_nearest_station(user_lat, user_lon, stations_gdf):
    """
    Tìm trạm sạc gần nhất và tính đường đi
    
    Parameters:
    -----------
    user_lat : float - Vĩ độ người dùng
    user_lon : float - Kinh độ người dùng
    stations_gdf : GeoDataFrame - Dữ liệu các trạm sạc
    
    Returns:
    --------
    dict - Thông tin trạm và tuyến đường
    """
    
    if stations_gdf is None or len(stations_gdf) == 0:
        raise ValueError("Không có dữ liệu trạm sạc")
    
    # Tạo KD-Tree
    coords = np.array([[geom.y, geom.x] for geom in stations_gdf.geometry])
    tree = cKDTree(coords)
    
    # Tìm trạm gần nhất
    user_point = np.array([[user_lat, user_lon]])
    distance, index = tree.query(user_point)
    
    nearest_station = stations_gdf.iloc[index[0]]
    station_lat = nearest_station.geometry.y
    station_lon = nearest_station.geometry.x
    
    # Tính đường đi bằng OSRM
    route_coords = []
    distance_km = 0
    duration_min = 0
    
    try:
        url = f"https://router.project-osrm.org/route/v1/driving/{user_lon},{user_lat};{station_lon},{station_lat}?overview=full&geometries=geojson"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('routes') and len(data['routes']) > 0:
            route = data['routes'][0]
            
            # Lấy tọa độ tuyến đường
            route_coords = [[coord[1], coord[0]] for coord in route['geometry']['coordinates']]
            
            # Khoảng cách và thời gian
            distance_km = route['distance'] / 1000
            duration_min = route['duration'] / 60
        else:
            # Fallback: đường thẳng
            route_coords = [[user_lat, user_lon], [station_lat, station_lon]]
            distance_km = haversine_distance(user_lat, user_lon, station_lat, station_lon)
            duration_min = distance_km / 30 * 60  # Giả sử 30km/h
            
    except Exception as e:
        print(f"⚠️ OSRM error: {e}, using straight line")
        route_coords = [[user_lat, user_lon], [station_lat, station_lon]]
        distance_km = haversine_distance(user_lat, user_lon, station_lat, station_lon)
        duration_min = distance_km / 30 * 60
    
    result = {
        'station': {
            'id': index[0] + 1,
            'lat': station_lat,
            'lon': station_lon,
            'score': float(nearest_station.get('score', 0))
        },
        'distance': round(distance_km, 2),
        'duration': round(duration_min, 1),
        'route_coords': route_coords
    }
    
    return result


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
