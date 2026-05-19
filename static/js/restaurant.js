document.addEventListener('DOMContentLoaded', async () => {

  // ============================================================
  // 1. LẤY DỮ LIỆU (Ưu tiên LocalStorage từ Detail Page, sau đó mới đến URL)
  // ============================================================
  
    let restaurant = {
        name: "Tên quán đang cập nhật",
        address: "Địa chỉ đang cập nhật",
        desc: "",
        rating: "N/A",
        price_text: "",
        image: "https://via.placeholder.com/600x400.png?text=No+Image",
        lat: null,
        lon: null,
        id: null
    };

    // Bước 1: Thử lấy từ LocalStorage (do detail.js lưu vào đây)
    const storedData = JSON.parse(localStorage.getItem("selectedRestaurant"));
        const storedRouteStart = JSON.parse(localStorage.getItem("routeStart") || "null");
        console.log("🚀 storedRouteStart in restaurant.js:", storedRouteStart);

    if (storedData) {
        console.log("📍 Dữ liệu Map lấy từ LocalStorage:", storedData);
        restaurant = {
            name: storedData.name || storedData.restaurant || "Tên quán đang cập nhật",
            address: storedData.address || "Địa chỉ đang cập nhật",
            desc: storedData.opening_hours 
                ? `<b data-key="Opening hours:">Opening hours:</b> ${storedData.opening_hours}` 
                : (storedData.description || ""),
            rating: storedData.rating || "N/A",
            price_text: storedData.price_text ? `<b data-key="Price:">Price:</b> ${storedData.price_text}` : "",
            image: storedData.image || "https://via.placeholder.com/600x400.png?text=No+Image",
            lat: parseFloat(storedData.latitude || storedData.lat),
            lon: parseFloat(storedData.longitude || storedData.lon),
            id: storedData.id || storedData.restaurant_id
        };
    } else {
        // Bước 2: Nếu không có LocalStorage, thử lấy từ URL (Fallback)
        console.log("Không tìm thấy LocalStorage, thử lấy từ URL...");
        const urlParams = new URLSearchParams(window.location.search);
        
        const parseCoord = (val) => {
            const num = parseFloat(val);
            return isNaN(num) ? null : num;
        };

        if (urlParams.has('lat')) {
            restaurant = {
                name: urlParams.get('name') || "Tên quán đang cập nhật",
                address: urlParams.get('addr') || "Địa chỉ đang cập nhật",
                desc: urlParams.get('desc') || "", 
                rating: urlParams.get('rate') || "N/A",
                image: urlParams.get('img') || "https://via.placeholder.com/600x400.png?text=No+Image",
                lat: parseCoord(urlParams.get('lat')),
                lon: parseCoord(urlParams.get('lon')),
                id: urlParams.get('id') || null
            };
        }
    }

    // 🔥 LẤY RATING THỰC TẾ TỪ API NẾU CÓ restaurant_id
    if (restaurant.id) {
        await loadRealRating(restaurant.id);
    }

    console.log("📍 Dữ liệu Map cuối cùng:", restaurant);
    console.log("📍 Route start từ search.js:", storedRouteStart);

// ============================================================
// 2. TẠO MAP
// ============================================================

    let center = [10.762622, 106.660172];
    let zoom = 13;

    const hasValidCoords = !isNaN(restaurant.lat) && !isNaN(restaurant.lon) && 
                            restaurant.lat !== null && restaurant.lon !== null;

    if (hasValidCoords) {
        center = [restaurant.lat, restaurant.lon];
        zoom = 16;
    } else {
        console.warn("Quán này chưa có dữ liệu tọa độ GPS hợp lệ.");
        alert("Không tìm thấy tọa độ của quán. Đang hiển thị trung tâm TP.HCM.");
    }

    const map = L.map('restaurant-map').setView(center, zoom);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap'
    }).addTo(map);

    const restaurantIcon = L.divIcon({
        className: 'restaurant-marker-pin', 
        html: `<img src="${restaurant.image}" onerror="this.src='https://via.placeholder.com/600x400?text=No+Image'" alt="Restaurant">`,
        iconSize: [50, 50],
        iconAnchor: [25, 55],
        popupAnchor: [0, -55]
    });

    const userIcon = L.divIcon({
        className: 'user-marker-pin',
        html: '',
        iconSize: [16, 16],
        iconAnchor: [8, 8],
        popupAnchor: [0, -10]
    });

    let marker;
    if (hasValidCoords) {
        marker = L.marker([restaurant.lat, restaurant.lon], { icon: restaurantIcon }).addTo(map);
    }

// ============================================================
// 🆕 HÀM LẤY RATING THỰC TỪ API
// ============================================================

    async function loadRealRating(restaurantId) {
        try {
            const res = await fetch(`/auth/get_restaurant_rating?restaurant_id=${restaurantId}`);
            const ratingData = await res.json();

            console.log("📊 Real rating data:", ratingData);

            if (ratingData.review_count === 0) {
                restaurant.rating = "No ratings yet";
            } else {
                restaurant.rating = `${ratingData.avg_rating}/5 (${ratingData.review_count} reviews)`;
            }

        } catch (error) {
            console.error("Error loading rating:", error);
            restaurant.rating = "N/A";
        }
    }

// ============================================================
// 3. XỬ LÝ GIAO DIỆN (PANEL) & 4. CHỨC NĂNG CHỈ ĐƯỜNG
// ============================================================

    const infoPanel = document.getElementById('infoPanel');
    const closePanelBtn = document.getElementById('closePanelBtn');
    const panelContent = document.getElementById('panelContent');
    const favBtn = document.getElementById('favoriteBtn'); // Có thể null nếu chưa login

    let currentRouteControl = null;

    const handleDirectionClick = async () => {
        if (!hasValidCoords) {
            alert("Không thể chỉ đường vì dữ liệu thiếu tọa độ GPS của quán.");
            return;
        }

        let startLat = null;
        let startLon = null;

        // 1. Nếu search.js đã lưu sẵn toạ độ (user nhập GPS hoặc backend đã xử lý)
        if (storedRouteStart && storedRouteStart.lat && storedRouteStart.lon) {
            startLat = storedRouteStart.lat;
            startLon = storedRouteStart.lon;
            console.log("✅ Dùng toạ độ từ routeStart (search.js):", startLat, startLon);
        } else {
            // 2. Không có lat/lon trong routeStart -> fallback dùng GPS thật
            console.log("📡 Không có lat/lon trong routeStart, dùng GPS thiết bị...");

            if (!navigator.geolocation) {
                alert("Trình duyệt của bạn không hỗ trợ lấy vị trí.");
                return;
            }

            if (infoPanel) infoPanel.classList.remove('open');

            const tempPopup = L.popup()
                .setLatLng([restaurant.lat, restaurant.lon])
                .setContent('<span data-key="Finding your location">⏳ Finding your location...</span>')
                .openOn(map);

            if (window.translatePage) {
                setTimeout(() => window.translatePage(), 50);
            }

            try {
                const position = await new Promise((resolve, reject) => {
                    navigator.geolocation.getCurrentPosition(resolve, reject);
                });

                map.closePopup(tempPopup);

                startLat = position.coords.latitude;
                startLon = position.coords.longitude;
                console.log("✅ GPS position:", startLat, startLon);
            } catch (error) {
                map.closePopup(tempPopup);
                console.error("❌ Geolocation error:", error);
                alert("❌ Không thể lấy vị trí. Vui lòng bật GPS.");
                return;
            }
        }

        // Có startLat / startLon rồi -> vẽ route
        if (currentRouteControl) {
            map.removeControl(currentRouteControl);
            currentRouteControl = null;
        }

        L.marker([startLat, startLon], { icon: userIcon })
            .addTo(map)
            .bindPopup('<span data-key="Your starting location">Your starting location</span>')
            .openPopup(); 

        currentRouteControl = L.Routing.control({
            waypoints: [
                L.latLng(startLat, startLon),
                L.latLng(restaurant.lat, restaurant.lon)
            ],
            createMarker: () => null,
            show: true,
            fitSelectedRoutes: true,
            routeWhileDragging: false,
            addWaypoints: false,
            lineOptions: { styles: [{ color: '#0033ff', opacity: 0.8, weight: 6 }] }
        }).addTo(map);

        if (infoPanel) infoPanel.classList.remove('open');

        // Nếu muốn, có thể clear routeStart sau khi dùng:
        // localStorage.removeItem("routeStart");

        if (window.translatePage) {
            window.translatePage();
        }
    };

// --- HÀM HIỂN THỊ PANEL ---
const showPanel = () => {
    if (!infoPanel || !panelContent) return;
    
    panelContent.innerHTML = `
        <div style="max-height: 60vh; overflow-y: auto; padding-right: 5px;">
            
            <div style="width:100%; height: 200px; overflow:hidden; border-radius: 8px; margin-bottom:15px;">
                <img src="${restaurant.image}" style="width:100%; height:100%; object-fit:cover;" 
                    onerror="this.src='https://via.placeholder.com/600x400?text=No+Image'">
            </div>

            <h1 style="font-size: 1.5rem; margin-bottom: 10px; line-height: 1.2;">${restaurant.name}</h1>
            
            <div class="rating" style="color: #ffb700; font-weight: bold; margin-bottom: 10px;">
                <i class='bx bxs-star'></i> ${restaurant.rating}
            </div>
            
            <div style="font-size: 1rem; color: #555; margin-bottom: 5px; line-height: 1.4;">
                ${restaurant.price_text}
            </div>
            <div style="font-size: 1rem; color: #555; margin-bottom: 10px; line-height: 1.4;">
                ${restaurant.desc}
            </div>            

            <hr style="border: 0; border-top: 1px solid #eee; margin: 10px 0;">
            
            <p style="margin-bottom: 20px; line-height: 1.5;"><b>📍</b> <b data-key="Address:">Address:</b> ${restaurant.address}</p>

            <button id="dynamicDirectionBtn" style="
                width: 100%; 
                padding: 12px; 
                background-color: #ff6600; 
                color: white; 
                border: none; 
                border-radius: 8px; 
                font-weight: bold; 
                cursor: pointer;
                margin-bottom: 10px;
                display: flex; align-items: center; justify-content: center; gap: 8px;">
                <i class='bx bxs-direction-right'></i> 
                <span data-key="Get Directions">Get Directions to Here</span>
            </button>
        </div>
    `;

    // NẾU CÓ NÚT TIM (tức là đã login), thì kiểm tra trạng thái favorite
    if (favBtn) {
        // Reset trạng thái tim
        favBtn.classList.remove('active', 'bxs-heart');
        favBtn.classList.add('bx-heart');

        // Gọi API kiểm tra xem quán này đã được like chưa
        fetch('/auth/check_favorite', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ restaurant_name: restaurant.name })
        })
        .then(res => res.json())
        .then(data => {
            if (data.is_favorite) {
                favBtn.classList.add('active');
                favBtn.classList.replace('bx-heart', 'bxs-heart');
            }
        })
        .catch(err => console.error("Lỗi check favorite:", err));
    }

    const btn = document.getElementById('dynamicDirectionBtn');
    if(btn) btn.addEventListener('click', handleDirectionClick);

    if (window.translatePage) {
        window.translatePage();
    }

    infoPanel.classList.add('open');
};

if (marker) {
    marker.on('click', showPanel);
    setTimeout(showPanel, 500); 
}

if (closePanelBtn) {
    closePanelBtn.addEventListener('click', () => { 
        infoPanel.classList.remove('open'); 
    });
}

map.on('click', () => { 
    if(infoPanel) infoPanel.classList.remove('open'); 
});

if(infoPanel) {
    L.DomEvent.disableClickPropagation(infoPanel);
    L.DomEvent.disableScrollPropagation(infoPanel);
}

// ============================================================
// XỬ LÝ CLICK NÚT TIM (CHỈ KHI CÓ favBtn - tức đã login)
// ============================================================

if (favBtn) {
    favBtn.addEventListener('click', () => {
        const payload = {
            name: restaurant.name,
            address: restaurant.address,
            image: restaurant.image,
            lat: restaurant.lat,
            lon: restaurant.lon
        };

        fetch('/auth/toggle_favorite', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(res => {
            if (res.status === 401) {
                alert("Vui lòng đăng nhập lại!");
                window.location.href = '/login';
                return null;
            }
            return res.json();
        })
        .then(data => {
            if (!data) return;

            if (data.action === 'added') {
                favBtn.classList.add('active');
                favBtn.classList.replace('bx-heart', 'bxs-heart');
            } else if (data.action === 'removed') {
                favBtn.classList.remove('active');
                favBtn.classList.replace('bxs-heart', 'bx-heart');
            }
        })
        .catch(err => console.error("Lỗi toggle favorite:", err));
    });
}

});