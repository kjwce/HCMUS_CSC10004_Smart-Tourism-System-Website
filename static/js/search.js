// =================== DOM ELEMENTS ===================
const searchName = document.getElementById("searchName");
// const searchCategory = document.getElementById("searchCategory");
const searchType = document.getElementById("searchType");
const searchPrice = document.getElementById("searchPrice");
const filterBtn = document.getElementById("filterBtn");
const searchResults = document.getElementById("searchResults");
const loading = document.getElementById("loading");
const locationInput = document.getElementById("userLocation");
const detectBtn = document.getElementById("detectBtn");

// 🔥 AUTOCOMPLETE DOM
const suggestionsList = document.getElementById("suggestionsList");

// =================== AUTO-FILL FROM HISTORY ===================
document.addEventListener('DOMContentLoaded', () => {
  const prefillData = localStorage.getItem('searchPrefill');
  
  if (prefillData) {
    try {
      const data = JSON.parse(prefillData);
      console.log('📋 Prefill data loaded:', data);
      
      if (searchName && data.dishName) {
        searchName.value = data.dishName;
      }

      if (searchType && data.restaurantType) {
        searchType.value = data.restaurantType;
      }      
      
      if (searchPrice && data.priceMin !== undefined && data.priceMax !== undefined) {
        searchPrice.value = `${data.priceMin}-${data.priceMax}`;
      }
      
      const searchDistance = document.getElementById('searchDistance');
      if (searchDistance && data.maxRadius !== undefined) {
        searchDistance.value = data.maxRadius;
      }
      
      if (locationInput && data.location) {
        locationInput.value = data.location;
      }
      
      if (data.lat && data.lon) {
        window.prefillCoordinates = {
          lat: data.lat,
          lon: data.lon
        };
      }
      
      localStorage.removeItem('searchPrefill');
      
      if (searchName) {
        searchName.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        const form = searchName.closest('form') || searchName.closest('.search-form');
        if (form) {
          form.classList.add('prefilled');
          setTimeout(() => form.classList.remove('prefilled'), 1500);
        }
      }
      
      showNotification('✅ Filled from search history', 'success');
      
    } catch (error) {
      console.error('Error parsing prefill data:', error);
      localStorage.removeItem('searchPrefill');
    }
  }
});


// =================== FORMAT PRICE ===================
function formatPrice(item) {
  // Nếu có price_text (text gốc), ưu tiên hiển thị
  if (item.price_text) {
    return item.price_text;
  }
  
  // Nếu có price_min và price_max, hiển thị range
  if (item.price_min && item.price_max) {
    if (item.price_min === item.price_max) {
      // Nếu min = max, chỉ hiển thị 1 giá
      return `${item.price_min.toLocaleString('vi-VN')}₫`;
    } else {
      // Hiển thị range
      return `${item.price_min.toLocaleString('vi-VN')}₫ - ${item.price_max.toLocaleString('vi-VN')}₫`;
    }
  }
  
  // Nếu chỉ có price_min
  if (item.price_min) {
    return `From ${item.price_min.toLocaleString('vi-VN')}₫`;
  }
  
  return "No price info";
}

// =================== DISPLAY SEARCH RESULTS WITH TRANSLATION ===================
function displayResults(data, responseData = {}) {
  searchResults.innerHTML = "";
  
  if (!data || data.length === 0) {
    searchResults.innerHTML = `<p class="no-result" data-key="No matching dishes found">No matching dishes found 😢</p>`;
    return;
  }

  data.forEach((item, index) => {
    const card = document.createElement("div");
    card.classList.add("card");

    // Format thời gian cập nhật
    let updateTimeText = '';
    if (item.updated_at) {
      const updatedDate = new Date(item.updated_at);
      const now = new Date();
      const diffMs = now - updatedDate;
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      
      if (diffDays === 0) {
        updateTimeText = '<span data-key="Today">Today</span>';
      } else if (diffDays === 1) {
        updateTimeText = '<span data-key="Yesterday">Yesterday</span>';
      } else if (diffDays < 7) {
        updateTimeText = `${diffDays} <span data-key="days ago">days ago</span>`;
      } else if (diffDays < 30) {
        const weeks = Math.floor(diffDays / 7);
        updateTimeText = `${weeks} <span data-key="weeks ago">weeks ago</span>`;
      } else if (diffDays < 365) {
        const months = Math.floor(diffDays / 30);
        updateTimeText = `${months} <span data-key="months ago">months ago</span>`;
      } else {
        updateTimeText = updatedDate.toLocaleDateString('en-US');
      }
    }
    
    card.innerHTML = `
      <img src="${item.image || "/static/images/food1.png"}" 
           alt="${item.name}" 
           onerror="this.src='/static/images/food1.png'">
      <div class="card-info">
        <h3 style="margin: 0 0 8px 0;">${item.name || item.restaurant}</h3>
        
        ${
          item.avg_rating > 0
            ? `<p>
                <span class="rating-badge">⭐ 
                  <span data-key="Rating:">Rating:</span> ${item.avg_rating}/5
                </span>
                <span class="rating-text">
                  (${item.review_count} <span data-key="reviews">reviews</span>)
                </span>
              </p>`
            : `<p>
                <span class="rating-badge rating-empty">
                  ⭐ <span data-key="No reviews yet">No reviews yet</span>
                </span>
              </p>`
        }
        
        <p><b data-key="Address:">Address:</b> ${item.address || '<span data-key="No address information">No address information</span>'}</p>
        
        <p><b data-key="Price:">Price:</b> ${formatPrice(item)}</p>
        
        ${item.distance !== undefined && item.distance !== null ? 
          `<p><b data-key="Distance:">Distance:</b> ${item.distance} <span data-key="km">km</span></p>` : ''}
        
        ${item.opening_hours ? 
          `<p><b data-key="Hours:">Hours:</b> ${item.opening_hours}</p>` : ''}

        ${
          updateTimeText
            ? `<p>
                <span class="update-badge">
                  <b data-key="Last updated:">Last updated:</b> ${updateTimeText}
                </span>
              </p>`
            : ''
        }
      </div>
    `;
    
    card.addEventListener("click", async () => {
      // 1. Chuẩn hóa dữ liệu trước khi lưu
      const normalizedData = {
        id: item.id || item.restaurant_id,
        restaurant_id: item.id || item.restaurant_id,
        name: item.name || item.restaurant || "Unknown Restaurant",
        address: item.address || "No address information",
        image: item.image || "/static/images/food1.png",
        
        // Rating
        avg_rating: item.avg_rating || 0,
        rating: item.avg_rating || item.rating || 0,
        review_count: item.review_count || 0,
        
        // Price
        price_text: item.price_text || null,
        price_min: item.price_min || null,
        price_max: item.price_max || null,
        price: item.price || null,
        
        // Location
        lat: item.lat || null,
        lon: item.lon || null,
        distance: item.distance || null,
        
        // Additional info
        opening_hours: item.opening_hours || null,
        description: item.description || null,
        restaurant_type: item.restaurant_type || null,
        category: item.category || null,
        
        // Metadata
        created_at: item.created_at || null,
        updated_at: item.updated_at || null
      };
      
      console.log('💾 Saving restaurant data:', normalizedData);
      localStorage.setItem("selectedRestaurant", JSON.stringify(normalizedData));

      // 2. Lưu location để chỉ đường (nếu cần)
      const locationText = locationInput ? locationInput.value.trim() : "";
      let startLat = null;
      let startLon = null;

      if (locationText) {
        // Check if GPS coordinates
        const gpsMatch = locationText.match(/(-?\d+(\.\d+)?)\s*,\s*(-?\d+(\.\d+)?)/);
        if (gpsMatch) {
          startLat = parseFloat(gpsMatch[1]);
          startLon = parseFloat(gpsMatch[3]);
          console.log("📍 routeStart from GPS:", startLat, startLon);
        } else {
          // Geocode address to GPS
          try {
            const res = await fetch("http://127.0.0.1:5000/search_api/geocode", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ location_text: locationText })
            });
            const data = await res.json();

            if (data.success && data.lat && data.lon) {
              startLat = data.lat;
              startLon = data.lon;
              console.log("Geocoded routeStart:", locationText, "=>", startLat, startLon);
            } else {
              console.warn("Geocode failed, will use GPS fallback");
            }
          } catch (e) {
            console.error("Geocode error:", e);
          }
        }
      }

      const routeStart = {
        location_text: locationText || null,
        lat: startLat,
        lon: startLon
      };

      console.log("💾 Saving routeStart:", routeStart);
      localStorage.setItem("routeStart", JSON.stringify(routeStart));

      // 3. Navigate to detail page
      window.location.href = "/detail";
    });
    
    searchResults.appendChild(card);
  });
  
  // Trigger translation after rendering
  if (window.translatePage) {
    window.translatePage();
  }
}


// =================== AUTOCOMPLETE DISH NAME ===================
// Dùng input #searchName + <ul id="suggestionsList">
// Debounce - không gọi API quá nhanh

function debounce(func, delay) {
  let timeout;
  return function (...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), delay);
  };
}

// Gọi API autocomplete
async function fetchSuggestions(query) {
  if (!suggestionsList) return;

  if (!query || query.length < 1) {
    suggestionsList.classList.add("hidden");
    return;
  }

  try {
    const response = await fetch(`/search_api/autocomplete/dishes?q=${encodeURIComponent(query)}&limit=8`);
    const data = await response.json();

    if (data.suggestions && data.suggestions.length > 0) {
      suggestionsList.innerHTML = data.suggestions
        .map(suggestion => `<li class="suggestion-item">${suggestion}</li>`)
        .join("");
      suggestionsList.classList.remove("hidden");
    } else {
      suggestionsList.classList.add("hidden");
    }
  } catch (error) {
    console.error("Autocomplete error:", error);
  }
}

const debouncedFetchSuggestions = debounce(fetchSuggestions, 100);

// Lắng nghe khi user gõ vào ô searchName
if (searchName) {
  searchName.addEventListener("input", (e) => {
    debouncedFetchSuggestions(e.target.value);
  });
}

// 🔥 Click suggestion → CHỈ ĐIỀN VÀO INPUT, KHÔNG TỰ SEARCH
if (suggestionsList) {
  suggestionsList.addEventListener("click", (e) => {
    if (e.target.classList.contains("suggestion-item")) {
      const value = e.target.textContent;

      if (searchName) {
        searchName.value = value;

        // 🎯 Visual feedback: highlight input để user biết đã điền
        searchName.style.background = '#e7f3ff';
        searchName.style.transition = 'background 0.3s ease';

        setTimeout(() => {
          searchName.style.background = '';
        }, 1000);

        // Focus vào input để user có thể edit nếu cần
        searchName.focus();
      }

      // Ẩn dropdown
      suggestionsList.classList.add("hidden");

      console.log(`✅ Auto-filled dish name: "${value}"`);
    }
  });
}

// Ẩn dropdown khi click ra ngoài
document.addEventListener("click", (e) => {
  if (!e.target.closest(".search-container")) {
    if (suggestionsList) suggestionsList.classList.add("hidden");
  }
});

// 🔥 HÀM HIỂN THỊ CẢNH BÁO LOCATION (ĐẸP HƠN ALERT)
function showLocationWarning() {
  if (!locationInput) return;
  
  // Highlight location input
  locationInput.style.borderColor = '#f44336';
  locationInput.style.borderWidth = '2px';
  locationInput.style.boxShadow = '0 0 8px rgba(244, 67, 54, 0.3)';
  
  // Scroll to location input
  locationInput.scrollIntoView({ 
    behavior: 'smooth', 
    block: 'center' 
  });
  
  // Focus vào input
  locationInput.focus();
  
  // Hiển thị thông báo inline
  const existingWarning = document.getElementById('location-warning-inline');
  if (existingWarning) {
    existingWarning.remove();
  }
  
  const warningDiv = document.createElement('div');
  warningDiv.id = 'location-warning-inline';
  warningDiv.style.cssText = `
    background: #fff3cd;
    border: 2px solid #ffc107;
    border-radius: 8px;
    padding: 12px 16px;
    margin-top: 8px;
    display: flex;
    align-items: center;
    gap: 10px;
    animation: slideDown 0.3s ease;
  `;
  
  warningDiv.innerHTML = `
    <i class="bx bx-error" style="font-size: 24px; color: #f57c00;"></i>
    <div style="flex: 1;">
      <div style="font-weight: 600; color: #e65100; margin-bottom: 4px;">
        ⚠️ <span data-key="Location Required">Location Required</span>
      </div>
      <div style="font-size: 14px; color: #555;">
        <span data-key="Location help text">
          Please click <b>"Detect Location"</b> or enter your address to search.
        </span>
      </div>
    </div>
  `;
  
  // Insert warning sau location input
  if (detectBtn && detectBtn.parentElement) {
    detectBtn.parentElement.insertAdjacentElement('afterend', warningDiv);
  }
  
  // Animate detect button
  if (detectBtn) {
    detectBtn.style.animation = 'pulse 0.5s ease 3';
  }
  
  // Auto remove warning sau 5s
  setTimeout(() => {
    locationInput.style.borderColor = '';
    locationInput.style.borderWidth = '';
    locationInput.style.boxShadow = '';
    
    if (warningDiv.parentNode) {
      warningDiv.style.animation = 'slideUp 0.3s ease';
      setTimeout(() => warningDiv.remove(), 300);
    }
    
    if (detectBtn) {
      detectBtn.style.animation = '';
    }
  }, 5000);
}

// Thêm CSS animations
const styleSheet = document.createElement('style');
styleSheet.textContent = `
  @keyframes slideDown {
    from {
      opacity: 0;
      transform: translateY(-10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  @keyframes slideUp {
    from {
      opacity: 1;
      transform: translateY(0);
    }
    to {
      opacity: 0;
      transform: translateY(-10px);
    }
  }
  
  @keyframes pulse {
    0%, 100% {
      transform: scale(1);
    }
    50% {
      transform: scale(1.05);
    }
  }
`;
document.head.appendChild(styleSheet);

console.log('✅ Autocomplete Module Loaded (Fixed - No Auto Search)');

async function performSearch() {
  console.log("========== performSearch CALLED ==========");
  
  // 🔥 ẨN AUTOCOMPLETE NGAY KHI BẮT ĐẦU SEARCH
  if (suggestionsList) {
    suggestionsList.classList.add("hidden");
  }
  
  const dishName = searchName ? searchName.value.trim() : "";
  console.log("  dishName:", dishName);
  
  const restaurantType = searchType ? searchType.value : "";
  console.log("  restaurantType:", restaurantType);  
  
  let priceMin = 0;
  let priceMax = 0;

  if (searchPrice && searchPrice.value) {
    // value dạng "0-0", "0-50000", "50000-100000"...
    const [minStr, maxStr] = searchPrice.value.split("-");
    priceMin = parseInt(minStr) || 0;
    priceMax = parseInt(maxStr) || 0;
    console.log("priceMin", priceMin, "priceMax", priceMax);
  }
  
  const searchDistance = document.getElementById('searchDistance');
  let maxDistance = 0;
  if (searchDistance && searchDistance.value) {
    const distanceValue = parseFloat(searchDistance.value);
    maxDistance = (distanceValue >= 0) ? distanceValue : 0;
  }
  console.log("  maxDistance:", maxDistance, "km");
  
  const locationText = locationInput ? locationInput.value.trim() : "";
  console.log("  locationText:", locationText);

  // ⭐ VALIDATION
  if (!locationText) {
    console.warn(" No location entered");
    showLocationWarning();  // 🔥 dùng UI đẹp thay cho alert
    return;
  }

  console.log(" Validation passed, starting search...");

  searchResults.innerHTML = "";
  if (loading) {
    loading.style.display = "flex";
    console.log("  Loading indicator shown");
  }

  const payload = {
    dish_name: dishName,
    restaurant_type: restaurantType,
    price_min: priceMin,
    price_max: priceMax,
    max_radius: maxDistance,
    location_text: null,
    lat: null,
    lon: null,
    user_id: window.USER_ID || "anonymous",
  };

  // Parse location
  if (locationText) {
    const gpsMatch = locationText.match(/^([-\d.]+),\s*([-\d.]+)$/);
    if (gpsMatch) {
      payload.lat = parseFloat(gpsMatch[1]);
      payload.lon = parseFloat(gpsMatch[2]);
      console.log(`📍 Using GPS: ${payload.lat}, ${payload.lon}`);
    } else {
      payload.location_text = locationText;
      console.log(`📍 Using location text: ${locationText}`);
    }
  }

  try {
    console.log("Sending API request...");
    console.log("  Payload:", JSON.stringify(payload, null, 2));
    
    // 🔥 FIX: Thêm timeout và retry logic
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout
    
    const res = await fetch("http://127.0.0.1:5000/search_api/search_restaurants", {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify(payload),
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);

    console.log(" Response status:", res.status);

    // 🔥 KIỂM TRA CONTENT-TYPE
    const contentType = res.headers.get("content-type");
    console.log(" Content-Type:", contentType);
    
    if (!contentType || !contentType.includes("application/json")) {
      const textResponse = await res.text();
      console.error(" Server returned non-JSON response:");
      console.error("First 1000 chars:", textResponse.substring(0, 1000));
      throw new Error("Server returned invalid response format. Check Flask server logs.");
    }

    // 🔥 PARSE JSON AN TOÀN
    let data;
    try {
      const responseText = await res.text();
      console.log(" Response length:", responseText.length, "chars");
      
      // Kiểm tra nếu response rỗng
      if (!responseText || responseText.trim().length === 0) {
        throw new Error("Empty response from server");
      }
      
      data = JSON.parse(responseText);
      console.log("JSON parsed OK");
      console.log("Keys:", Object.keys(data));
    } catch (parseError) {
      console.error("JSON Parse Error:", parseError);
      console.error("Raw response:", responseText?.substring(0, 500));
      throw new Error(`Failed to parse server response: ${parseError.message}`);
    }
    
    if (loading) {
      loading.style.display = "none";
    }

    // 🔥 XỬ LÝ KẾT QUẢ
    if (res.ok && data.matches && data.matches.length > 0) {
      console.log(`Found ${data.matches.length} restaurants`);
      
      const f = data.filters || {};
      const fPriceMin = typeof f.price_min === "number" ? f.price_min : priceMin;
      const fPriceMax = typeof f.price_max === "number" ? f.price_max : priceMax;

      let priceLabel = "All prices";
      if (fPriceMin === 0 && fPriceMax > 0) {
        priceLabel = `≤ ${fPriceMax.toLocaleString("vi-VN")}₫`;
      } else if (fPriceMin > 0 && fPriceMax === 0) {
        priceLabel = `≥ ${fPriceMin.toLocaleString("vi-VN")}₫`;
      } else if (fPriceMin > 0 && fPriceMax > 0) {
        priceLabel = `${fPriceMin.toLocaleString("vi-VN")}₫ - ${fPriceMax.toLocaleString("vi-VN")}₫`;
      }

      const filterInfo = `
        <div style="background: #e7f3ff; padding: 12px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #2196F3;">
          <p style="margin: 5px 0;"><b>Search Results</b> – ${data.total_results} restaurants found</p>
          <p style="margin: 5px 0; font-size: 14px; color: #555;">
            Filters:
            dishName: ${dishName || "Any dish"},
            restaurantType: ${restaurantType || "All types"},
            price: ${priceLabel},
            maxDistance: ${maxDistance > 0 ? maxDistance + "km" : "Any distance"}
          </p>
          ${f.original_dish_input && f.original_dish_input !== dishName
            ? `<p style="margin: 5px 0; font-size: 13px; color: #1976D2;">
                AI corrected: "${f.original_dish_input}" → "${dishName}"
              </p>`
            : ""
          }
        </div>
      `;
      
      searchResults.innerHTML = filterInfo;
      displayResults(data.matches, data);
      
    } else if (res.status === 404) {
        // Không tìm thấy kết quả
        searchResults.innerHTML = `
          <div class="no-results-box">
            <div class="no-results-header">
              <span style="font-size:20px;">🔍</span>
              <div>
                <div class="no-results-title" data-key="No suitable restaurants">
                  Không tìm thấy quán phù hợp
                </div>
                <div class="no-results-subtitle" data-key="Try widening your filters">
                  Thử nới rộng điều kiện tìm kiếm một chút nhé.
                </div>
              </div>
            </div>

            <div><b data-key="Current filters:">Bộ lọc hiện tại:</b></div>
            <div class="no-results-filters">
              <div>• <span data-key="Dish name">Tên món ăn</span>: <b>${dishName || '<span data-key="Any dish">Bất kỳ</span>'}</b></div>
              <div>• <span data-key="Type of restaurant">Loại quán</span>: <b>${restaurantType ? `<span data-key="${restaurantType}">${restaurantType}</span>` : `<span data-key="All">Tất cả</span>`}</b></div>
              <div>• <span data-key="Price">Giá</span>: <b>${
                (priceMin === 0 && priceMax === 0)
                  ? `<span data-key="All">Tất cả</span>`
                  : (priceMin === 0)
                    ? `≤ ${priceMax.toLocaleString('vi-VN')}₫`
                    : (priceMax === 0)
                      ? `≥ ${priceMin.toLocaleString('vi-VN')}₫`
                      : `${priceMin.toLocaleString('vi-VN')}₫ - ${priceMax.toLocaleString('vi-VN')}₫`
              }</b></div>
              <div>• <span data-key="Distance">Bán kính</span>: <b>${maxDistance > 0 ? `≤ ${maxDistance}km` : '<span data-key="Unlimited distance">Không giới hạn</span>'}</b></div>
            </div>

            <div><b data-key="Suggestions:">Gợi ý:</b></div>
            <ul class="no-results-tips">
              <li data-key="Tip dish name">Thử bỏ bớt tên món hoặc gõ chung chung hơn.</li>
              <li data-key="Tip price">Chọn khoảng giá rộng hơn (ít nhất vài chục nghìn).</li>
              <li data-key="Tip distance">Tăng bán kính tìm kiếm hoặc bật GPS.</li>
            </ul>
          </div>
        `;
      } else {
      throw new Error(data.error || `Server error: ${res.status}`);
    }
    
  } catch (err) {
    if (loading) {
      loading.style.display = "none";
    }
    
    console.error("❌ SEARCH ERROR:", err);
    
    let errorMessage = err.message;
    let troubleshooting = [];
    
    if (err.name === 'AbortError') {
      errorMessage = "Request timeout (15s). Server might be slow or unresponsive.";
      troubleshooting = [
        "Check if Flask server is running",
        "Check server logs for errors",
        "Try with simpler search (no dish name)"
      ];
    } else if (err.message.includes("Failed to fetch")) {
      errorMessage = "Cannot connect to server. Is Flask running?";
      troubleshooting = [
        "Start Flask: <code>python app.py</code>",
        "Check Flask is on port 5000",
        "Test: <a href='http://127.0.0.1:5000/search_api/health' target='_blank'>Health Check</a>"
      ];
    } else {
      troubleshooting = [
        "Refresh page (Ctrl+F5)",
        "Check Flask terminal for errors",
        "Verify database file exists"
      ];
    }
    
    searchResults.innerHTML = `
      <div style="background: #f8d7da; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
        <p><b> Search Error</b></p>
        <p>${errorMessage}</p>
        ${troubleshooting.length > 0 ? `
          <hr style="margin: 15px 0;">
          <p><b>Troubleshooting:</b></p>
          <ul style="text-align: left;">
            ${troubleshooting.map(t => `<li>${t}</li>`).join('')}
          </ul>
        ` : ''}
      </div>
    `;
  }

  if (window.translatePage) {
    window.translatePage();
  }
  
  console.log("========== performSearch COMPLETED ==========");
}

// =================== EVENT LISTENERS ===================
filterBtn.addEventListener("click", performSearch);

searchName.addEventListener("keypress", (e) => {
  if (e.key === "Enter") performSearch();
});

// =================== LOCATION DETECTION ===================
function detectGPS() {
  if (!locationInput) return;
  
  if (!navigator.geolocation) {
    alert("Your browser does not support location detection.");
    return;
  }

  locationInput.value = "Detecting location...";

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const lat = pos.coords.latitude.toFixed(6);
      const lon = pos.coords.longitude.toFixed(6);
      locationInput.value = `${lat},${lon}`;
      console.log(` GPS detected: ${lat}, ${lon}`);
    },
    (err) => {
      console.error("Geolocation error:", err);
      let errorMsg = "Unable to detect location.";
      switch(err.code) {
        case err.PERMISSION_DENIED:
          errorMsg = "Permission denied. Please allow location access.";
          break;
        case err.POSITION_UNAVAILABLE:
          errorMsg = "Position unavailable. Try moving to an open area.";
          break;
        case err.TIMEOUT:
          errorMsg = "Location request timed out. Try again.";
          break;
      }
      alert(` ${errorMsg}`);
      locationInput.value = "";
    },
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0
    }
  );
}

if (detectBtn) {
  detectBtn.addEventListener("click", detectGPS);
}

if (locationInput) {
  locationInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") performSearch();
  });
}

// =================== CHATBOT STORAGE MANAGER ===================
window.ChatStorage = {
  STORAGE_KEY: 'foodie_chat_history',
  
  saveMessage(role, content) {
    const history = this.getHistory();
    history.push({
      role: role,
      content: content,
      timestamp: new Date().toISOString()
    });
    
    if (history.length > 50) {
      history.splice(0, history.length - 50);
    }
    
    sessionStorage.setItem(this.STORAGE_KEY, JSON.stringify(history));
    console.log(`Saved ${role} message (${history.length} total)`);
  },
  
  getHistory() {
    const stored = sessionStorage.getItem(this.STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  },
  
  clearHistory() {
    sessionStorage.removeItem(this.STORAGE_KEY);
    console.log('🗑️ Chat history cleared');
  }
};

// =================== DOM ELEMENTS ===================
let chatbotIcon, chatbox, closeChat, sendChat, chatInput, chatBody;
let uploadBtn, imageInput, langToggle, langVi, langEn;
let targetLanguage = 'vi'; // Ngôn ngữ đích cho dịch menu
let responseLanguage = 'vi'; // Ngôn ngữ chatbot trả lời
let initialized = false;

// =================== INIT FUNCTION ===================
function initChatbot() {
  if (initialized) {
    console.warn('⚠️ Chatbot already initialized');
    return;
  }
  
  chatbotIcon = document.getElementById("chatbotIcon");
  chatbox = document.getElementById("chatbox");
  closeChat = document.getElementById("closeChat");
  sendChat = document.getElementById("sendChat");
  chatInput = document.getElementById("chatInput");
  chatBody = document.getElementById("chatBody");
  uploadBtn = document.getElementById("uploadBtn");
  imageInput = document.getElementById("imageInput");
  langToggle = document.getElementById("langToggle");
  langVi = document.getElementById("langVi");
  langEn = document.getElementById("langEn");
  
  if (!chatBody) {
    console.warn('⚠️ chatBody not found, chatbot disabled');
    return;
  }
  
  console.log('✅ Chatbot elements found:', {
    icon: !!chatbotIcon,
    box: !!chatbox,
    body: !!chatBody,
    input: !!chatInput,
    upload: !!uploadBtn
  });

   // Hiển thị thanh ngôn ngữ ngay từ đầu
  if (langToggle) {
    langToggle.style.display = 'flex';
  }

  loadChatHistory();
  setupEventListeners();
  
  initialized = true;
  console.log(`✅ Chatbot initialized with ${window.ChatStorage.getHistory().length} messages`);
}

// =================== LOAD HISTORY ===================
function loadChatHistory() {
  const history = window.ChatStorage.getHistory();
  
  if (history.length === 0) {
    console.log('📭 No chat history');
    return;
  }
  
  console.log(`📚 Loading ${history.length} messages...`);
  chatBody.innerHTML = '';
  
  history.forEach((msg, index) => {
    try {
      if (msg.role === 'user') {
        addUserMessage(msg.content, false);
      } else if (msg.role === 'bot') {
        addBotMessage(msg.content, false);
      } else if (msg.role === 'image') {
        const imageDiv = document.createElement('div');
        imageDiv.className = 'image-message user';
        imageDiv.innerHTML = `<img src="${msg.content}" alt="Uploaded menu" style="max-width: 100%; border-radius: 8px;">`;
        chatBody.appendChild(imageDiv);
      }
    } catch (err) {
      console.error(`❌ Error loading message ${index}:`, err);
    }
  });
  
  chatBody.scrollTop = chatBody.scrollHeight;
}

// =================== EVENT LISTENERS ===================
function setupEventListeners() {
  if (chatbotIcon && chatbox) {
    chatbotIcon.addEventListener("click", () => {
      chatbox.classList.add("open");
      if (chatBody) chatBody.scrollTop = chatBody.scrollHeight;
    });
  }
  
  if (closeChat && chatbox) {
    closeChat.addEventListener("click", () => {
      chatbox.classList.remove("open");
    });
  }
  
  if (sendChat) {
    sendChat.addEventListener("click", sendMessage);
  }
  
  if (chatInput) {
    chatInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }
  
  // Xử lý chuyển đổi ngôn ngữ trả lời
  if (langVi && langEn) {
    langVi.addEventListener('click', () => {
      // EN→VI: OCR tiếng Anh, dịch ra tiếng Việt, chatbot trả lời tiếng Anh
      targetLanguage = 'vi';
      responseLanguage = 'vi'; // Chatbot trả lời bằng tiếng Anh
      langVi.classList.add('active');
      langEn.classList.remove('active');
      console.log('🌍 Mode: VI (Chatbot responds in Vietnamese)');
    });

    langEn.addEventListener('click', () => {
      // VI→EN: OCR tiếng Việt, dịch ra tiếng Anh, chatbot trả lời tiếng Việt
      targetLanguage = 'en';
      responseLanguage = 'en'; // Chatbot trả lời bằng tiếng Việt
      langEn.classList.add('active');
      langVi.classList.remove('active');
      console.log('🌍 Mode: EN (Chatbot responds in English)');
    });
  }
  
  if (uploadBtn && imageInput) {
    uploadBtn.addEventListener('click', () => {
      imageInput.click();
    });
    
    imageInput.addEventListener('change', handleImageUpload);
  }
}

// =================== TEXT MESSAGE ===================
async function sendMessage() {
  if (!chatInput || !chatBody) return;
  
  const msg = chatInput.value.trim();
  if (!msg) return;

  if (langToggle) langToggle.style.display = 'flex';

  console.log('📤 Sending request with responseLanguage:', responseLanguage); // ← THÊM DÒNG NÀY
  addUserMessage(msg);
  chatInput.value = "";

  showTypingIndicator();

  try {
    const res = await fetch("http://127.0.0.1:5000/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        question: msg,
        response_language: responseLanguage // Gửi ngôn ngữ trả lời
      })
    });

    const data = await res.json();
    removeTypingIndicator();

    if (data.answer) {
      addBotMessage(data.answer);
    } else {
      const errorMsg = responseLanguage === 'en' 
        ? '❌ Sorry, I could not understand your question.'
        : '❌ Xin lỗi, mình không hiểu câu hỏi của bạn.';
      addBotMessage(errorMsg);
    }
  } catch (err) {
    removeTypingIndicator();
    const errorMsg = responseLanguage === 'en'
      ? '❌ Connection error. Please try again.'
      : '❌ Lỗi kết nối. Vui lòng thử lại.';
    addBotMessage(errorMsg);
    console.error('Error:', err);
  }
}

// =================== IMAGE UPLOAD ===================
async function handleImageUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  if (langToggle) langToggle.style.display = 'flex';

  const reader = new FileReader();
  reader.onload = (event) => {
    const base64Image = event.target.result;
    
    const imageDiv = document.createElement('div');
    imageDiv.className = 'image-message user';
    imageDiv.innerHTML = `<img src="${base64Image}" alt="Uploaded menu" style="max-width: 100%; border-radius: 8px;">`;
    chatBody.appendChild(imageDiv);
    chatBody.scrollTop = chatBody.scrollHeight;

    window.ChatStorage.saveMessage('image', base64Image);
  };
  reader.readAsDataURL(file);

  showTypingIndicator();

  const formData = new FormData();
  formData.append('image', file);
  formData.append('targetLanguage', targetLanguage);

  try {
    const response = await fetch('http://127.0.0.1:5000/translate-menu', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    removeTypingIndicator();

    if (data.success) {
      addBotMessage(data.answer);
    } else {
      addBotMessage(data.answer || '❌ Sorry, I could not process the image.');
    }
  } catch (error) {
    removeTypingIndicator();
    addBotMessage('❌ Connection error. Please try again.');
    console.error('Error:', error);
  }

  imageInput.value = '';
}

// =================== UI HELPERS ===================
function addUserMessage(text, saveToStorage = true) {
  if (!chatBody) return;
  
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message user';
  messageDiv.innerHTML = `<p class="user-message">${text}</p>`;
  chatBody.appendChild(messageDiv);
  chatBody.scrollTop = chatBody.scrollHeight;
  
  if (saveToStorage) {
    window.ChatStorage.saveMessage('user', text);
  }
}

function addBotMessage(text, saveToStorage = true) {
  if (!chatBody) return;
  
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message';
  messageDiv.innerHTML = `<p class="bot-message">${text.replace(/\n/g, '<br>')}</p>`;
  chatBody.appendChild(messageDiv);
  chatBody.scrollTop = chatBody.scrollHeight;
  
  if (saveToStorage) {
    window.ChatStorage.saveMessage('bot', text);
  }
}

function showTypingIndicator() {
  if (!chatBody) return;
  
  const indicator = document.createElement('div');
  indicator.className = 'message typing';
  indicator.id = 'typingIndicator';
  indicator.innerHTML = `
    <div class="typing-indicator">
      <span></span>
      <span></span>
      <span></span>
    </div>
  `;
  chatBody.appendChild(indicator);
  chatBody.scrollTop = chatBody.scrollHeight;
}

function removeTypingIndicator() {
  const indicator = document.getElementById('typingIndicator');
  if (indicator) {
    indicator.remove();
  }
}

// =================== AUTO INIT ===================
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initChatbot);
} else {
  initChatbot();
}

// =================== EXPOSE API ===================
window.FoodieChatbot = {
  init: initChatbot,
  clearHistory: () => window.ChatStorage.clearHistory(),
  getHistory: () => window.ChatStorage.getHistory()
};

console.log('✅ Chatbot Module Loaded');


// =================== IMAGE SEARCH FUNCTIONALITY ===================
const imageSearchBtn = document.getElementById("imageSearchBtn");
const imageUploadModal = document.getElementById("imageUploadModal");
const closeImageModal = document.getElementById("closeImageModal");
const cancelUpload = document.getElementById("cancelUpload");
const uploadArea = document.getElementById("uploadArea");
const imageInputSearch = document.getElementById("imageInputSearch");
const browseBtn = document.querySelector(".browse-btn");
const imagePreview = document.getElementById("imagePreview");
const previewImg = document.getElementById("previewImg");
const removeImage = document.getElementById("removeImage");
const searchWithImage = document.getElementById("searchWithImage");

// Mở modal khi click nút Search by Image
if (imageSearchBtn) {
  imageSearchBtn.addEventListener("click", () => {
    imageUploadModal.classList.add("active");
  });
}

// Đóng modal
function closeModal() {
  imageUploadModal.classList.remove("active");
  resetUploadArea();
}

if (closeImageModal) {
  closeImageModal.addEventListener("click", closeModal);
}

if (cancelUpload) {
  cancelUpload.addEventListener("click", closeModal);
}

// Click vào nút Browse
if (browseBtn) {
  browseBtn.addEventListener("click", () => {
    imageInputSearch.click(); // ĐỔI Ở ĐÂY
  });
}

// Xử lý chọn file
if (imageInputSearch) {
  imageInputSearch.addEventListener("change", function(e) {
    if (this.files && this.files[0]) {
      handleImageUploadSearch(this.files[0]); 
    }
  });
}
// Drag & drop functionality
if (uploadArea) {
  // Ngăn chặn hành vi mặc định
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    uploadArea.addEventListener(eventName, preventDefaults, false);
    document.body.addEventListener(eventName, preventDefaults, false);
  });

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  // Highlight drop area
  ['dragenter', 'dragover'].forEach(eventName => {
    uploadArea.addEventListener(eventName, highlight, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    uploadArea.addEventListener(eventName, unhighlight, false);
  });

  function highlight(e) {
    uploadArea.classList.add('drag-over');
  }

  function unhighlight(e) {
    uploadArea.classList.remove('drag-over');
  }
}

  // Handle drop
  uploadArea.addEventListener('drop', handleDrop, false);
  function handleDrop(e) {
  const dt = e.dataTransfer;
  const files = dt.files;

  if (files.length > 0) {
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(files[0]);
    imageInputSearch.files = dataTransfer.files; // SỬA Ở ĐÂY
    handleImageUploadSearch(files[0]);
  }
  }

// Xử lý upload ảnh
function handleImageUploadSearch(file) {
  if (!file.type.match('image.*')) {
    alert('Please upload an image file!');
    return;
  }

  if (file.size > 5 * 1024 * 1024) {
    alert('Image size should be less than 5MB!');
    return;
  }

  const reader = new FileReader();
  
  reader.onload = function(e) {
    previewImg.src = e.target.result;
    uploadArea.style.display = 'none';
    imagePreview.style.display = 'block';
    searchWithImage.disabled = false;
  }
  
  reader.readAsDataURL(file);
}

// Xóa ảnh đã chọn
if (removeImage) {
  removeImage.addEventListener("click", resetUploadArea);
}

// Trong hàm resetUploadArea
function resetUploadArea() {
  previewImg.src = "";
  uploadArea.style.display = 'block';
  imagePreview.style.display = 'none';
  searchWithImage.disabled = true;
  imageInputSearch.value = ""; // SỬA Ở ĐÂY
}
// Xử lý nút Search This Food
async function performImageSearch(file) {
  if (!file) return;

  try {
    const formData = new FormData();
    formData.append('image', file);

    // Hiển thị loading
    loading.style.display = 'flex';
    searchResults.innerHTML = '';

    const response = await fetch('/predict_food', {
      method: 'POST',
      body: formData
    });
    
    const data = await response.json();

    if (response.ok) {
      const foodName = data.prediction;
      searchName.value = foodName;
      
      // Đóng modal
      closeModal();
      
      // Tự động tìm kiếm với tên món ăn đã detect
      setTimeout(() => {
        performSearch();
      }, 500);
      
      showNotification(`🍽️ AI detected: "${foodName}". Searching now...`, 'success');
    } else {
      throw new Error(data.error || 'Prediction failed');
    }
  } catch (error) {
    console.error('Error predicting food:', error);
    showNotification(`❌ Error: ${error.message}`, 'error');
    
    // Vẫn đóng modal nhưng không tìm kiếm
    closeModal();
  } finally {
    loading.style.display = 'none';
  }
}

// Xử lý nút Search This Food
if (searchWithImage) {
  searchWithImage.addEventListener("click", async function() {
    const file = imageInputSearch.files[0];
    if (!file) {
      alert('Please select an image first!');
      return;
    }

    searchWithImage.innerHTML = '<i class="bx bx-loader-alt bx-spin"></i> Processing...';
    searchWithImage.disabled = true;

    await performImageSearch(file);

    searchWithImage.innerHTML = '<i class="bx bx-search"></i> Search This Food';
    searchWithImage.disabled = false;
  });
}

// Hàm hiển thị thông báo
function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  notification.style.cssText = `
    position: fixed;
    top: 100px;
    right: 20px;
    background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3'};
    color: white;
    padding: 12px 20px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    z-index: 1000;
    animation: slideInRight 0.3s ease;
  `;
  notification.textContent = message;
  
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.style.animation = 'slideOutRight 0.3s ease';
    setTimeout(() => {
      if (notification.parentNode) {
        document.body.removeChild(notification);
      }
    }, 300);
  }, 3000);
}

// Thêm animation cho thông báo
const style = document.createElement('style');
style.textContent = `
  @keyframes slideInRight {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }
  @keyframes slideOutRight {
    from { transform: translateX(0); opacity: 1; }
    to { transform: translateX(100%); opacity: 0; }
  }
`;
document.head.appendChild(style);

// =================== CONSOLE INFO ===================
console.log("🚀 Smart Food Search initialized");
console.log("🐍 Flask Backend: http://127.0.0.1:5000");
console.log("   📡 Search API: /search_api/search_restaurants (POST)");
console.log("   🤖 Chatbot API: /ask (POST)");
console.log("   ✅ Health Check: /search_api/health (GET)");





// =======================
// 🍽️ POPULAR RESTAURANTS CAROUSEL
// =======================

let currentSlide = 0;
let slidesToShow = 4;
let slideWidth = 0;
let popularRestaurants = [];

// Load popular restaurants
async function loadPopularRestaurants() {
    try {
        console.log('Loading popular restaurants...');
        const response = await fetch('/auth/popular_restaurants');
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Popular restaurants data:', data);
        
        popularRestaurants = data;
        
        if (popularRestaurants.length > 0) {
            initCarousel();
            renderCarousel();
            updateCarousel();
        } else {
            // Hiển thị thông báo nếu không có restaurants nào có review
            document.getElementById('carouselTrack').innerHTML = 
                '<p class="no-data">No restaurants with reviews yet. Be the first to review!</p>';
        }
    } catch (error) {
        console.error('Error loading popular restaurants:', error);
        document.getElementById('carouselTrack').innerHTML = 
            `<p class="no-data">Error loading popular restaurants: ${error.message}</p>`;
    }
}

// Khởi tạo carousel
function initCarousel() {
    const carouselTrack = document.getElementById('carouselTrack');
    
    // Tính toán dựa trên số lượng restaurants thực tế
    const containerWidth = carouselTrack.parentElement.offsetWidth;
    const cardWidth = 230; // Chiều rộng cố định của card
    const gap = 25;
    
    slideWidth = cardWidth + gap;
    slidesToShow = Math.min(Math.floor(containerWidth / slideWidth), popularRestaurants.length);
    currentSlide = 0; // Reset về slide đầu tiên
    
    console.log(`Carousel: ${slidesToShow} visible, ${popularRestaurants.length} total`);
}


function renderCarousel() {
    const carouselTrack = document.getElementById('carouselTrack');
    carouselTrack.innerHTML = '';

    popularRestaurants.forEach((restaurant, index) => {
        const card = document.createElement('div');
        card.className = 'restaurant-card';
        
        const rank = index + 1;
        const rankClass = rank <= 3 ? `top-rank-${rank}` : 'normal-rank';

        
        card.innerHTML = `
            <div class="rank-badge ${rankClass}">#${rank}</div>
            <img src="${restaurant.image}" 
                 alt="${restaurant.name}" 
                 onerror="this.src='/static/images/food1.png'">
            <h3>${restaurant.name}</h3>
            <div class="restaurant-stats">
                <span class="rating">⭐ ${restaurant.avg_rating}</span>
                <span class="reviews"> ${restaurant.review_count} reviews</span>
            </div>
            <div class="score-badge">
                <span data-key="Score:">Score:</span> ${restaurant.score}
            </div>
            <p class="address">${restaurant.address}</p>
            <p class="price"> ${restaurant.price_text}</p>
            ${restaurant.category ? `<p class="category"> <span data-key="${restaurant.category}">${restaurant.category}</span></p>` : ''}
        `;

        card.addEventListener('click', () => {

            // 🔥 FIX: Chuẩn hóa dữ liệu trước khi lưu
            const normalizedData = {
                id: restaurant.id,                    
                restaurant_id: restaurant.id,
                name: restaurant.name,
                address: restaurant.address,
                image: restaurant.image,
                rating: restaurant.avg_rating || restaurant.rating,
                // price: restaurant.price,
                price_text: restaurant.price_text,
                price_min: restaurant.price_min,
                price_max: restaurant.price_max,

                // Category
                category: restaurant.category,
                
                // ✅ Backend đã trả về lat/lon, dùng thẳng!
                lat: restaurant.lat,
                lon: restaurant.lon,
                        
                // Thêm metadata
                opening_hours: restaurant.opening_hours,
                reviews_count: restaurant.review_count
            };
            
            console.log('📍 Normalized restaurant data:', normalizedData);
            
            localStorage.setItem('selectedRestaurant', JSON.stringify(normalizedData));
            window.location.href = '/detail';
        });

        carouselTrack.appendChild(card);
    });

  if (window.translatePage) {
    window.translatePage();
  }
}

// Update carousel position
function updateCarousel() {
    const carouselTrack = document.getElementById('carouselTrack');
    const maxSlide = Math.max(0, popularRestaurants.length - slidesToShow);
    
    currentSlide = Math.max(0, Math.min(currentSlide, maxSlide));
    
    const translateX = -currentSlide * slideWidth;
    carouselTrack.style.transform = `translateX(${translateX}px)`;
    
    updateNavigationButtons();
}

// Cập nhật trạng thái nút navigation
function updateNavigationButtons() {
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const maxSlide = Math.max(0, popularRestaurants.length - slidesToShow);
    
    if (prevBtn) {
        prevBtn.style.opacity = currentSlide === 0 ? '0.5' : '1';
        prevBtn.style.cursor = currentSlide === 0 ? 'not-allowed' : 'pointer';
    }
    
    if (nextBtn) {
        nextBtn.style.opacity = currentSlide >= maxSlide ? '0.5' : '1';
        nextBtn.style.cursor = currentSlide >= maxSlide ? 'not-allowed' : 'pointer';
    }
}

// Navigation events
document.getElementById('prevBtn')?.addEventListener('click', () => {
    if (currentSlide > 0) {
        currentSlide--;
        updateCarousel();
    }
});

document.getElementById('nextBtn')?.addEventListener('click', () => {
    const maxSlide = Math.max(0, popularRestaurants.length - slidesToShow);
    if (currentSlide < maxSlide) {
        currentSlide++;
        updateCarousel();
    }
});

// Xử lý responsive
window.addEventListener('resize', () => {
    if (popularRestaurants.length > 0) {
        initCarousel();
        updateCarousel();
    }
});

// Initialize on load
document.addEventListener('DOMContentLoaded', function() {
    loadPopularRestaurants();
});
