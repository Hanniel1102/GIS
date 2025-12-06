"""
Genetic Algorithm cho tối ưu hóa vị trí trạm sạc EV
Author: GitHub Copilot
Date: 2025-12-01
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Callable
import random


class GeneticAlgorithmOptimizer:
    """
    Genetic Algorithm để tối ưu vị trí trạm sạc.
    
    Encoding: Mỗi cá thể (individual) là một list các index vào candidate pool
    Fitness: Tổng suitability score - penalty cho khoảng cách
    """
    
    def __init__(
        self,
        candidates_df: pd.DataFrame,
        scoring_function: Callable,
        n_stations: int = 20,
        min_distance_km: float = 2.5,
        population_size: int = 100,
        n_generations: int = 200,
        mutation_rate: float = 0.2,
        crossover_rate: float = 0.8,
        elite_size: int = 10,
        verbose: bool = True
    ):
        """
        Parameters:
        -----------
        candidates_df : DataFrame với columns ['lat', 'lon', 'suitability_score']
        scoring_function : Function(lat, lon) -> score
        n_stations : Số lượng trạm cần chọn
        min_distance_km : Khoảng cách tối thiểu giữa các trạm
        population_size : Kích thước quần thể
        n_generations : Số thế hệ chạy
        mutation_rate : Tỷ lệ đột biến
        crossover_rate : Tỷ lệ lai ghép
        elite_size : Số cá thể tốt nhất được giữ lại mỗi thế hệ
        verbose : In progress
        """
        self.candidates = candidates_df.reset_index(drop=True)
        self.scoring_function = scoring_function
        self.n_stations = n_stations
        self.min_distance_km = min_distance_km
        self.population_size = population_size
        self.n_generations = n_generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elite_size = elite_size
        self.verbose = verbose
        
        self.n_candidates = len(candidates_df)
        self.best_solution = None
        self.best_fitness = -float('inf')
        self.fitness_history = []
    
    def calculate_distance(self, idx1: int, idx2: int) -> float:
        """Tính khoảng cách giữa 2 candidate (km)"""
        lat1, lon1 = self.candidates.loc[idx1, ['lat', 'lon']]
        lat2, lon2 = self.candidates.loc[idx2, ['lat', 'lon']]
        
        # Haversine distance approximation
        dlat = (lat2 - lat1) * 111.0
        dlon = (lon2 - lon1) * 111.0 * np.cos(np.radians((lat1 + lat2) / 2))
        distance = np.sqrt(dlat**2 + dlon**2)
        
        return distance
    
    def fitness(self, individual: List[int]) -> float:
        """
        Tính fitness của một cá thể.
        
        Fitness = Tổng suitability scores - Penalty cho vi phạm khoảng cách
        """
        # Tổng điểm phù hợp
        total_score = sum(self.candidates.loc[idx, 'suitability_score'] 
                         for idx in individual)
        
        # Penalty cho vi phạm khoảng cách
        penalty = 0
        for i in range(len(individual)):
            for j in range(i + 1, len(individual)):
                distance = self.calculate_distance(individual[i], individual[j])
                if distance < self.min_distance_km:
                    # Penalty tăng khi khoảng cách càng nhỏ
                    violation = self.min_distance_km - distance
                    penalty += violation * 50  # Hệ số penalty
        
        fitness_value = total_score - penalty
        return fitness_value
    
    def create_individual(self) -> List[int]:
        """Tạo một cá thể ngẫu nhiên (valid)"""
        individual = []
        available = list(range(self.n_candidates))
        
        while len(individual) < self.n_stations and available:
            # Chọn ngẫu nhiên với bias về candidates có score cao
            weights = [self.candidates.loc[idx, 'suitability_score'] for idx in available]
            weights = np.array(weights)
            weights = weights / weights.sum()
            
            chosen_idx = np.random.choice(available, p=weights)
            
            # Kiểm tra khoảng cách
            valid = True
            for existing_idx in individual:
                if self.calculate_distance(chosen_idx, existing_idx) < self.min_distance_km:
                    valid = False
                    break
            
            if valid:
                individual.append(chosen_idx)
            
            available.remove(chosen_idx)
        
        return individual
    
    def create_population(self) -> List[List[int]]:
        """Tạo quần thể ban đầu"""
        population = []
        for _ in range(self.population_size):
            individual = self.create_individual()
            if len(individual) == self.n_stations:
                population.append(individual)
        
        # Nếu không đủ valid individuals, tạo thêm
        while len(population) < self.population_size:
            individual = self.create_individual()
            if len(individual) == self.n_stations:
                population.append(individual)
        
        return population
    
    def selection(self, population: List[List[int]], fitnesses: List[float]) -> List[int]:
        """Tournament selection"""
        tournament_size = 5
        tournament_indices = random.sample(range(len(population)), tournament_size)
        tournament_fitnesses = [fitnesses[i] for i in tournament_indices]
        winner_idx = tournament_indices[np.argmax(tournament_fitnesses)]
        return population[winner_idx].copy()
    
    def crossover(self, parent1: List[int], parent2: List[int]) -> Tuple[List[int], List[int]]:
        """
        Order crossover (OX) - giữ thứ tự và tránh duplicate
        """
        if random.random() > self.crossover_rate:
            return parent1.copy(), parent2.copy()
        
        size = len(parent1)
        # Chọn 2 điểm cắt
        cx_point1, cx_point2 = sorted(random.sample(range(size), 2))
        
        # Tạo offspring 1
        child1 = [-1] * size
        child1[cx_point1:cx_point2] = parent1[cx_point1:cx_point2]
        
        # Fill remaining từ parent2
        remaining = [gene for gene in parent2 if gene not in child1]
        idx = 0
        for i in range(size):
            if child1[i] == -1:
                child1[i] = remaining[idx]
                idx += 1
        
        # Tương tự cho offspring 2
        child2 = [-1] * size
        child2[cx_point1:cx_point2] = parent2[cx_point1:cx_point2]
        remaining = [gene for gene in parent1 if gene not in child2]
        idx = 0
        for i in range(size):
            if child2[i] == -1:
                child2[i] = remaining[idx]
                idx += 1
        
        return child1, child2
    
    def mutation(self, individual: List[int]) -> List[int]:
        """
        Mutation: swap hoặc replace một gene
        """
        if random.random() > self.mutation_rate:
            return individual
        
        mutated = individual.copy()
        
        mutation_type = random.choice(['swap', 'replace'])
        
        if mutation_type == 'swap' and len(mutated) > 1:
            # Swap 2 positions
            idx1, idx2 = random.sample(range(len(mutated)), 2)
            mutated[idx1], mutated[idx2] = mutated[idx2], mutated[idx1]
        
        elif mutation_type == 'replace':
            # Replace một gene với candidate mới
            replace_idx = random.randint(0, len(mutated) - 1)
            available = [i for i in range(self.n_candidates) if i not in mutated]
            
            if available:
                # Chọn candidate mới, ưu tiên score cao
                weights = [self.candidates.loc[idx, 'suitability_score'] for idx in available]
                weights = np.array(weights)
                if weights.sum() > 0:
                    weights = weights / weights.sum()
                    new_gene = np.random.choice(available, p=weights)
                    mutated[replace_idx] = new_gene
        
        return mutated
    
    def evolve(self) -> pd.DataFrame:
        """
        Chạy Genetic Algorithm
        
        Returns:
        --------
        DataFrame với các trạm được chọn
        """
        if self.verbose:
            print(f"🧬 Starting Genetic Algorithm Optimization")
            print(f"   Population: {self.population_size}, Generations: {self.n_generations}")
            print(f"   Stations: {self.n_stations}, Min Distance: {self.min_distance_km} km")
        
        # Tạo quần thể ban đầu
        population = self.create_population()
        
        for generation in range(self.n_generations):
            # Tính fitness cho tất cả cá thể
            fitnesses = [self.fitness(ind) for ind in population]
            
            # Lưu best solution
            max_fitness_idx = np.argmax(fitnesses)
            if fitnesses[max_fitness_idx] > self.best_fitness:
                self.best_fitness = fitnesses[max_fitness_idx]
                self.best_solution = population[max_fitness_idx].copy()
            
            self.fitness_history.append(self.best_fitness)
            
            # Print progress
            if self.verbose and (generation % 20 == 0 or generation == self.n_generations - 1):
                avg_fitness = np.mean(fitnesses)
                print(f"   Gen {generation:3d}: Best={self.best_fitness:.2f}, "
                      f"Avg={avg_fitness:.2f}, "
                      f"Std={np.std(fitnesses):.2f}")
            
            # Elitism: giữ lại các cá thể tốt nhất
            elite_indices = np.argsort(fitnesses)[-self.elite_size:]
            new_population = [population[i].copy() for i in elite_indices]
            
            # Tạo thế hệ mới
            while len(new_population) < self.population_size:
                # Selection
                parent1 = self.selection(population, fitnesses)
                parent2 = self.selection(population, fitnesses)
                
                # Crossover
                child1, child2 = self.crossover(parent1, parent2)
                
                # Mutation
                child1 = self.mutation(child1)
                child2 = self.mutation(child2)
                
                new_population.extend([child1, child2])
            
            # Trim nếu vượt quá population size
            population = new_population[:self.population_size]
        
        # Tạo DataFrame kết quả
        if self.verbose:
            print(f"\n✅ Optimization complete!")
            print(f"   Best fitness: {self.best_fitness:.2f}")
        
        return self._create_result_dataframe()
    
    def _create_result_dataframe(self) -> pd.DataFrame:
        """Tạo DataFrame từ best solution"""
        selected_stations = []
        
        for idx in self.best_solution:
            station_info = self.candidates.loc[idx].to_dict()
            station_info['id'] = idx
            selected_stations.append(station_info)
        
        result_df = pd.DataFrame(selected_stations)
        
        # Sắp xếp theo suitability score
        result_df = result_df.sort_values('suitability_score', ascending=False)
        result_df = result_df.reset_index(drop=True)
        
        return result_df
    
    def plot_fitness_history(self):
        """Vẽ biểu đồ fitness qua các thế hệ"""
        import matplotlib.pyplot as plt
        
        plt.figure(figsize=(10, 6))
        plt.plot(self.fitness_history, linewidth=2)
        plt.xlabel('Generation', fontsize=12)
        plt.ylabel('Best Fitness', fontsize=12)
        plt.title('Genetic Algorithm - Fitness Evolution', fontsize=14, fontweight='bold')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        return plt.gcf()


def compare_greedy_vs_ga(
    candidates_df: pd.DataFrame,
    scoring_function: Callable,
    n_stations: int = 20,
    min_distance_km: float = 2.5
) -> dict:
    """
    So sánh Greedy vs Genetic Algorithm
    
    Returns:
    --------
    dict với keys: 'greedy_result', 'ga_result', 'improvement'
    """
    print("=" * 70)
    print("COMPARING GREEDY vs GENETIC ALGORITHM")
    print("=" * 70)
    
    # 1. Greedy Algorithm (baseline)
    print("\n1️⃣ Running Greedy Algorithm...")
    greedy_stations = []
    remaining = candidates_df.copy().reset_index(drop=True)
    
    for i in range(n_stations):
        if len(remaining) == 0:
            break
        
        best_candidate = remaining.iloc[0]
        greedy_stations.append(best_candidate.to_dict())
        
        # Remove candidates too close
        if i < n_stations - 1:
            distances = []
            for idx, candidate in remaining.iterrows():
                dlat = (candidate.lat - best_candidate.lat) * 111.0
                dlon = (candidate.lon - best_candidate.lon) * 111.0 * np.cos(
                    np.radians((candidate.lat + best_candidate.lat) / 2))
                dist = np.sqrt(dlat**2 + dlon**2)
                distances.append(dist)
            
            remaining = remaining[np.array(distances) >= min_distance_km]
            remaining = remaining.sort_values('suitability_score', ascending=False)
    
    greedy_df = pd.DataFrame(greedy_stations)
    greedy_score = greedy_df['suitability_score'].sum()
    greedy_avg = greedy_df['suitability_score'].mean()
    
    print(f"   Greedy Score: {greedy_score:.2f} (avg: {greedy_avg:.2f})")
    
    # 2. Genetic Algorithm
    print("\n2️⃣ Running Genetic Algorithm...")
    ga_optimizer = GeneticAlgorithmOptimizer(
        candidates_df=candidates_df,
        scoring_function=scoring_function,
        n_stations=n_stations,
        min_distance_km=min_distance_km,
        population_size=100,
        n_generations=200,
        mutation_rate=0.2,
        crossover_rate=0.8,
        elite_size=10,
        verbose=True
    )
    
    ga_df = ga_optimizer.evolve()
    ga_score = ga_df['suitability_score'].sum()
    ga_avg = ga_df['suitability_score'].mean()
    
    print(f"   GA Score: {ga_score:.2f} (avg: {ga_avg:.2f})")
    
    # 3. Comparison
    improvement = ((ga_score - greedy_score) / greedy_score) * 100
    
    print("\n" + "=" * 70)
    print("📊 RESULTS:")
    print(f"   Greedy Total Score: {greedy_score:.2f}")
    print(f"   GA Total Score:     {ga_score:.2f}")
    print(f"   Improvement:        {improvement:+.2f}%")
    print("=" * 70)
    
    return {
        'greedy_result': greedy_df,
        'ga_result': ga_df,
        'greedy_score': greedy_score,
        'ga_score': ga_score,
        'improvement_pct': improvement,
        'ga_optimizer': ga_optimizer
    }


# Wrapper function để tương thích với web app
def optimize_stations(boundary, residential, substations, roads, num_stations=100, 
                     population_size=50, generations=100):
    """
    Wrapper function để tối ưu trạm sạc từ GeoDataFrame
    
    Parameters:
    -----------
    boundary : GeoDataFrame - Ranh giới khu vực
    residential : GeoDataFrame - Khu dân cư  
    substations : GeoDataFrame - Trạm điện
    roads : GeoDataFrame - Mạng lưới đường
    num_stations : int - Số trạm cần tối ưu
    population_size : int - Kích thước quần thể
    generations : int - Số thế hệ
    
    Returns:
    --------
    GeoDataFrame - Kết quả tối ưu với điểm số
    """
    import geopandas as gpd
    from shapely.geometry import Point
    from scipy.spatial import cKDTree
    
    print(f"🚀 Bắt đầu tối ưu {num_stations} trạm sạc...")
    
    # Chuyển sang UTM
    utm_crs = 'EPSG:32648'
    boundary_utm = boundary.to_crs(utm_crs)
    residential_utm = residential.to_crs(utm_crs)
    substations_utm = substations.to_crs(utm_crs)
    
    # Tạo lưới candidates
    bounds = boundary_utm.total_bounds
    minx, miny, maxx, maxy = bounds
    
    grid_spacing = 500
    x_coords = np.arange(minx, maxx, grid_spacing)
    y_coords = np.arange(miny, maxy, grid_spacing)
    
    candidates = []
    for x in x_coords:
        for y in y_coords:
            point = Point(x, y)
            if boundary_utm.contains(point).any():
                candidates.append({'lon': x, 'lat': y})
    
    candidates_df = pd.DataFrame(candidates)
    print(f"✓ Tạo {len(candidates_df)} điểm ứng viên")
    
    # Tạo KD-Trees (xử lý cả Point và Polygon)
    res_coords = np.array([[geom.centroid.x if geom.geom_type != 'Point' else geom.x, 
                            geom.centroid.y if geom.geom_type != 'Point' else geom.y] 
                           for geom in residential_utm.geometry])
    sub_coords = np.array([[geom.centroid.x if geom.geom_type != 'Point' else geom.x,
                            geom.centroid.y if geom.geom_type != 'Point' else geom.y] 
                           for geom in substations_utm.geometry])
    
    res_tree = cKDTree(res_coords)
    sub_tree = cKDTree(sub_coords)
    
    # Hàm tính điểm
    def scoring_function(lat, lon):
        point = np.array([[lon, lat]])
        dist_res, _ = res_tree.query(point)
        dist_sub, _ = sub_tree.query(point)
        
        score_res = 100 / (1 + dist_res[0] / 1000)
        score_sub = 100 / (1 + dist_sub[0] / 1000)
        
        return 0.6 * score_res + 0.4 * score_sub
    
    # Tính điểm cho tất cả candidates
    candidates_df['suitability_score'] = candidates_df.apply(
        lambda row: scoring_function(row['lat'], row['lon']), axis=1
    )
    
    print("✓ Tính điểm suitability")
    
    # Chạy GA
    ga_optimizer = GeneticAlgorithmOptimizer(
        candidates_df=candidates_df,
        scoring_function=scoring_function,
        n_stations=num_stations,
        min_distance_km=2.0,
        population_size=population_size,
        n_generations=generations,
        mutation_rate=0.2,
        crossover_rate=0.8,
        elite_size=max(5, population_size // 10),
        verbose=True
    )
    
    result_df = ga_optimizer.evolve()
    
    # Chuyển về GeoDataFrame
    geometries = [Point(row['lon'], row['lat']) for _, row in result_df.iterrows()]
    result_utm = gpd.GeoDataFrame(result_df, geometry=geometries, crs=utm_crs)
    
    # Tính metrics
    coords = np.array([[geom.x, geom.y] for geom in result_utm.geometry])
    dist_res, _ = res_tree.query(coords)
    dist_sub, _ = sub_tree.query(coords)
    
    result_utm['dist_res'] = dist_res
    result_utm['dist_sub'] = dist_sub
    result_utm['dist_poi'] = 0
    result_utm['score'] = result_utm['suitability_score']
    
    # Chuyển về WGS84
    result = result_utm.to_crs('EPSG:4326')
    
    print(f"✅ Hoàn tất! Điểm trung bình: {result['score'].mean():.2f}")
    
    return result
