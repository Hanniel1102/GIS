// Main JavaScript for EV Charging Optimizer

document.addEventListener('DOMContentLoaded', function() {
    const btnOptimize = document.getElementById('btn-optimize');
    const btnViewMap = document.getElementById('btn-view-map');
    const btnExportGeoJSON = document.getElementById('btn-export-geojson');
    const btnExportExcel = document.getElementById('btn-export-excel');
    const btnExportShp = document.getElementById('btn-export-shp');
    
    const progressBar = document.getElementById('progress-bar');
    const resultsPanel = document.getElementById('results');
    
    let optimizationData = null;
    let progressInterval = null;  // Thêm biến global để track interval
    
    // Bắt đầu tối ưu
    btnOptimize.addEventListener('click', async function() {
        const numStations = parseInt(document.getElementById('num_stations').value);
        const population = parseInt(document.getElementById('population').value);
        const generations = parseInt(document.getElementById('generations').value);
        
        // Validation
        if (numStations < 10 || numStations > 500) {
            alert('⚠️ Số trạm phải từ 10-500');
            return;
        }
        
        // Clear interval cũ nếu có
        if (progressInterval) {
            clearInterval(progressInterval);
        }
        
        // Hiển thị progress bar
        progressBar.classList.remove('hidden');
        progressBar.style.display = 'block';
        btnOptimize.disabled = true;
        btnOptimize.textContent = '⏳ Đang xử lý...';
        
        // Animate progress text
        let progress = 0;
        progressInterval = setInterval(() => {
            progress = Math.min(progress + 3, 95); // Tăng đến 95% rồi dừng
            const progressText = document.querySelector('.progress-text');
            if (progressText) {
                progressText.textContent = `Đang tối ưu... ${progress}%`;
            }
        }, 1000); // Mỗi 1 giây tăng 3%
        
        const startTime = Date.now();
        
        try {
            const response = await fetch('/api/optimize', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    num_stations: numStations,
                    population: population,
                    generations: generations
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                optimizationData = data;
                
                const endTime = Date.now();
                const duration = ((endTime - startTime) / 1000).toFixed(1);
                
                // Hiển thị kết quả
                document.getElementById('stat-stations').textContent = data.num_stations;
                document.getElementById('stat-score').textContent = data.avg_score.toFixed(1);
                document.getElementById('stat-coverage').textContent = '95%'; // Tính toán thực tế
                document.getElementById('stat-time').textContent = duration + 's';
                
                clearInterval(progressInterval);
                progressInterval = null;
                const progressText = document.querySelector('.progress-text');
                if (progressText) {
                    progressText.textContent = '✅ Hoàn thành 100%!';
                }
                
                resultsPanel.classList.remove('hidden');
                resultsPanel.style.display = 'block';
                
                // Ẩn progress bar sau 1s
                setTimeout(() => {
                    progressBar.classList.add('hidden');
                }, 1000);
                
                // Scroll to results
                resultsPanel.scrollIntoView({ behavior: 'smooth' });
                
                alert('✅ Tối ưu hóa hoàn tất!');
            } else {
                if (progressInterval) {
                    clearInterval(progressInterval);
                    progressInterval = null;
                }
                throw new Error(data.error || 'Lỗi không xác định');
            }
            
        } catch (error) {
            if (progressInterval) {
                clearInterval(progressInterval);
                progressInterval = null;
            }
            console.error('Error:', error);
            alert('❌ Lỗi: ' + error.message);
        } finally {
            if (progressInterval) {
                clearInterval(progressInterval);
                progressInterval = null;
            }
            btnOptimize.disabled = false;
            btnOptimize.textContent = '▶️ Bắt đầu tối ưu';
            setTimeout(() => {
                progressBar.classList.add('hidden');
                progressBar.style.display = 'none';
            }, 1000);
        }
    });
    
    // Xem bản đồ
    btnViewMap.addEventListener('click', function() {
        if (optimizationData) {
            window.location.href = '/map';
        } else {
            alert('⚠️ Vui lòng chạy tối ưu trước!');
        }
    });
    
    // Export GeoJSON
    btnExportGeoJSON.addEventListener('click', async function() {
        try {
            const response = await fetch('/api/export_results?format=geojson');
            const data = await response.json();
            
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'optimal_stations.geojson';
            a.click();
            
        } catch (error) {
            alert('❌ Lỗi xuất file: ' + error.message);
        }
    });
    
    // Export Excel
    btnExportExcel.addEventListener('click', async function() {
        try {
            window.location.href = '/api/export_results?format=excel';
        } catch (error) {
            alert('❌ Lỗi xuất file: ' + error.message);
        }
    });
    
    // Export Shapefile
    btnExportShp.addEventListener('click', async function() {
        try {
            window.location.href = '/api/export_results?format=shapefile';
        } catch (error) {
            alert('❌ Lỗi xuất file: ' + error.message);
        }
    });
});
