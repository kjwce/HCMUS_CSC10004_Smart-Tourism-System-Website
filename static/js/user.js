// =================== CONFIGURATION ===================
const API_BASE = '/search_api';

// Lấy userId từ session
let userId = 'anonymous';

// =================== MAIN INITIALIZATION ===================
document.addEventListener("DOMContentLoaded", () => {
  // Lấy user info
  const userNameElement = document.getElementById('userName');
  if (userNameElement && userNameElement.textContent !== 'Guest') {
    userId = userNameElement.textContent;
  }

  // 🌿 Xử lý chuyển tab (menu trái)
  const menuButtons = document.querySelectorAll(".menu-item");
  const sections = document.querySelectorAll(".section");

  menuButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      // Bỏ active ở tất cả nút và section
      menuButtons.forEach((b) => b.classList.remove("active"));
      sections.forEach((s) => s.classList.remove("active"));

      // Thêm active cho nút và section được chọn
      btn.classList.add("active");
      const target = btn.dataset.section;
      document.getElementById(target).classList.add("active");

      // ⭐ Load Search History khi vào tab History
      if (target === 'history') {
        loadSearchHistory();
      }

      // Load Favourites khi vào tab Favourites
      if (target == "favorites"){
        loadFavorites();
      }
    });
  });

  const backHomeBtn = document.getElementById('backhome');
  if (backHomeBtn) {
      backHomeBtn.addEventListener('click', function(e) {
          e.preventDefault(); // Ngăn hành vi mặc định
          window.location.href = '/home';
      });
      console.log('✅ Back Home button initialized'); // Debug
    }
});
  
  // =================== LOAD FAVOURITES ===================
  async function loadFavorites() {
    const grid = document.getElementById('favoritesGrid');
    grid.innerHTML = '<p>Đang tải...</p>';

    try {
      const res = await fetch('/auth/get_favorites');
      if (!res.ok) throw new Error("Không thể tải danh sách");
      
      const data = await res.json();

      if (data.length === 0) {
        grid.innerHTML = '<p style="width:100%; text-align:center;" data-key="No favorite restaurants yet">You have no favorite restaurants yet.</p>';
        if (window.translatePage) {
          window.translatePage();
        }
        return;
      }


      grid.innerHTML = ''; // Xóa loading

      data.forEach(fav => {
        // Tạo thẻ card
        const card = document.createElement('div');
        card.className = 'fav-card';
        
        // Tạo URL để khi click sẽ quay lại trang map
        const detailUrl = `/restaurant?name=${encodeURIComponent(fav.name)}&addr=${encodeURIComponent(fav.address)}&img=${encodeURIComponent(fav.image)}&lat=${fav.lat}&lon=${fav.lon}`;

        card.innerHTML = `
          <div style="height: 120px; overflow: hidden; border-radius: 8px; margin-bottom: 10px;">
            <img src="${fav.image}" style="width: 100%; height: 100%; object-fit: cover;" onerror="this.src='https://via.placeholder.com/150'">
          </div>
          <h4 style="font-size: 1rem; margin-bottom: 5px; color: #333;">${fav.name}</h4>
          <p style="font-size: 0.8rem; color: #666; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${fav.address}</p>
          <a href="${detailUrl}" style="display: inline-block; margin-top: 10px; text-decoration: none; color: #ff9966; font-weight: bold; font-size: 0.9rem;"><span data-key="View map">Xem Bản Đồ</span> &rarr;</a>
        `;

        grid.appendChild(card);
      });

      if (window.translatePage) {
        window.translatePage();
      }

    } catch (err) {
      console.error(err);
      grid.innerHTML = '<p style="color:red;">Lỗi khi tải danh sách yêu thích.</p>';
    }
  }

  // =================== LOAD HISTORY ===================
let searchHistory = [];

async function loadSearchHistory() {
  const historyList = document.getElementById('historyList');
  if (!historyList) return;

  try {
    showLoading();
    
    console.log('🔍 Loading history for userId:', userId); // DEBUG
    
    const res = await fetch(`${API_BASE}/history?user_id=${userId}`);
    console.log('📡 Response status:', res.status); // DEBUG
    
    const data = await res.json();
    console.log('📦 Response data:', data); // DEBUG
    
    searchHistory = data.history || [];
    console.log('📊 History items:', searchHistory.length); // DEBUG
    
    renderSearchHistory();
    
  } catch (error) {
    console.error('❌ Error loading search history:', error);
    historyList.innerHTML = '<li class="error-message">Không thể tải lịch sử tìm kiếm</li>';
  }
}

function renderSearchHistory() {
  const historyList = document.getElementById('historyList');
  
  if (!historyList) return;
  
  if (searchHistory.length === 0) {
    historyList.innerHTML = '<li class="empty-message" data-key="No search history">Chưa có lịch sử tìm kiếm</li>';
    if (window.translatePage) window.translatePage();
    return;
  }

  const historyHTML = searchHistory.map(item => {
    // ⭐ XÁC ĐỊNH LOCATION DISPLAY
    let locationDisplay = 'N/A';
    if (!item.location_text && item.latitude && item.longitude) {
      locationDisplay = `📍 GPS: ${item.latitude.toFixed(4)}, ${item.longitude.toFixed(4)}`;
    } else if (item.location_text) {
      locationDisplay = `📍 ${escapeHtml(item.location_text)}`;
    }

    // ⭐ HIỂN THỊ GIÁ THEO price_min / price_max
    let priceLabelHtml = '<span data-key="All prices">All prices</span>';
    const pMin = item.price_min || 0;
    const pMax = item.price_max || 0;

    if (pMin === 0 && pMax > 0) {
      priceLabelHtml = `≤ ${pMax.toLocaleString('vi-VN')}₫`;
    } else if (pMin > 0 && pMax === 0) {
      priceLabelHtml = `≥ ${pMin.toLocaleString('vi-VN')}₫`;
    } else if (pMin > 0 && pMax > 0) {
      priceLabelHtml = `${pMin.toLocaleString('vi-VN')}₫ - ${pMax.toLocaleString('vi-VN')}₫`;
    }

    // ⭐ RESTAURANT TYPE
    const rawType = item.restaurant_type || 'All types';
    const safeType = escapeHtml(rawType);
    const typeLabelHtml = `<span data-key="${safeType}">${safeType}</span>`;

    // ⭐ MAX RADIUS
    const radiusHtml = (item.max_radius && item.max_radius > 0)
      ? `${item.max_radius}km`
      : '<span data-key="Any distance">Any distance</span>';

    // 🔥 FIX: HIỂN THỊ ĐÚNG SỐ LƯỢNG KẾT QUẢ
    const resultsCount = item.results_count || 0;
    const restaurantText = resultsCount === 1 ? 'restaurant' : 'restaurants';

    return `
      <li class="history-item">
        <div class="history-info">
          <h3>
            <span>🔍 </span>
            <span data-key="Dish name">Dish name</span>:
            ${escapeHtml(item.dish_name || 'N/A')}
          </h3>
          <div class="history-details">
            <span>${locationDisplay}</span>
            <span>
              🏪 
              <span data-key="Type of restaurant">Type of restaurant</span>:
              ${typeLabelHtml}
            </span>
            <span>
              💰 <span data-key="Price">Price</span>:
              ${priceLabelHtml}
            </span>
            <span>
              📏 <span data-key="Radius">Radius</span>:
              ${radiusHtml}
            </span>
          </div>
          <div class="history-meta">
            <span>
              📊 
              <span data-key="Found">Found</span>:
              ${resultsCount}
              <span data-key="${restaurantText}">${restaurantText}</span>
            </span>
            <span class="time">
              🕐 <span data-key="Searched at">Searched at</span>: ${formatDate(item.created_at)}
            </span>
          </div>
        </div>
        <div class="history-actions">
          <button class="btn-repeat" onclick="repeatSearch(${item.id})">
            <i class='bx bx-refresh'></i>
            <span data-key="Search again">Search again</span>
          </button>
          <button class="btn-delete" onclick="deleteHistoryItem(${item.id})">
            <i class='bx bx-trash'></i>
          </button>
        </div>
      </li>
    `;
  }).join('');

  historyList.innerHTML = historyHTML + `
    <li class="clear-all-container">
      <button class="btn-clear-all" onclick="clearAllHistory()">
        🗑️ <span data-key="Clear all history">Xóa toàn bộ lịch sử</span>
      </button>
    </li>
  `;

  if (window.translatePage) {
    window.translatePage();
  }
}

  // =================== CHANGE PASSWORD ===================
// 🔒 Xử lý đổi mật khẩu
const passwordForm = document.getElementById("passwordForm");
if (passwordForm) {
  passwordForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const inputs = passwordForm.querySelectorAll("input");
    const current = inputs[0].value.trim();
    const newPass = inputs[1].value.trim();
    const confirm = inputs[2].value.trim();

    if (newPass !== confirm) {
      alert("❌ Mật khẩu nhập lại không khớp!\n❌ Passwords don't match!");
      return;
    }

    if (newPass.length < 6) {
      alert("⚠️ Mật khẩu mới phải có ít nhất 6 ký tự!\n⚠️ The new password must be at least 6 characters long!");
      return;
    }

    const res = await fetch("/auth/change_password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: current,
        new_password: newPass,
      }),
    });

    const data = await res.json();
    const status = document.getElementById("passwordStatus");

    status.textContent = data.message || data.error;
    status.style.color = res.ok ? "green" : "red";

    alert(`${data.message || data.error}`);

    // Reset form nếu đổi mật khẩu thành công
    if (res.ok) passwordForm.reset();
  });
}

// ============ Upload Avatar ============
if (selectFileBtn && avatarInput) {
  // Click vào button custom → trigger input file
  selectFileBtn.addEventListener("click", () => {
    avatarInput.click();
  });

  // Khi chọn file
  avatarInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    
    if (!file) {
      fileName.innerHTML = '<span data-key="No file chosen">No file chosen</span>';
      fileName.classList.remove('selected');
      uploadSubmitBtn.disabled = true;
      return;
    }

    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('❌ Vui lòng chọn file ảnh!\n❌ Please select an image file!');
      avatarInput.value = '';
      return;
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      alert('❌ Ảnh không được vượt quá 5MB!\n❌ Image size must not exceed 5MB!');
      avatarInput.value = '';
      return;
    }

    // Hiển thị tên file
    fileName.textContent = file.name;
    fileName.classList.add('selected');
    
    // Enable nút upload
    uploadSubmitBtn.disabled = false;

    // Preview ảnh
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImage.src = e.target.result;
    };
    reader.readAsDataURL(file);
    
    // Dịch lại nếu có
    if (window.translatePage) {
      window.translatePage();
    }
  });
}

// Submit form
if (avatarForm) {
  avatarForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    
    const file = avatarInput.files[0];
    if (!file) {
      alert('❌ Vui lòng chọn ảnh trước!\n❌ Please select an image first!');
      return;
    }

    // Hiển thị loading
    uploadSubmitBtn.disabled = true;
    uploadSubmitBtn.innerHTML = '<i class="bx bx-loader-alt bx-spin"></i> <span data-key="Uploading...">Uploading...</span>';

    const formData = new FormData();
    formData.append("avatar", file);

    try {
      const res = await fetch("/auth/upload_avatar", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (res.ok) {
        alert(data.message || '✅ Upload thành công!\n✅ Upload successful!');
        
        // Cập nhật avatar ở sidebar
        if (data.avatar_url) {
          const timestamp = new Date().getTime();  
          const newAvatarUrl = `${data.avatar_url}?t=${timestamp}`;  
          
          document.getElementById("userAvatar").src = newAvatarUrl; 
          previewImage.src = newAvatarUrl;  
        }
        
        // Reset form
        avatarInput.value = '';
        fileName.innerHTML = '<span data-key="No file chosen">No file chosen</span>';
        fileName.classList.remove('selected');
        
      } else {
        alert('❌ ' + (data.error || 'Upload thất bại!\nUpload failed!'));
      }
      
    } catch (error) {
      console.error('Upload error:', error);
      alert('❌ Lỗi kết nối server!\n❌ Server connection error!');
    } finally {
      // Reset nút
      uploadSubmitBtn.disabled = false;
      uploadSubmitBtn.innerHTML = '<i class="bx bx-upload"></i> <span data-key="Upload Avatar">Upload Avatar</span>';
      
      // Dịch lại
      if (window.translatePage) {
        window.translatePage();
      }
    }
  });
}

// =================== SEARCH HISTORY FUNCTIONS ===================
async function deleteHistoryItem(id) {
  if (!confirm('Bạn có chắc muốn xóa mục này?\nAre you sure you want to delete this item?')) return;
  
  try {
    const res = await fetch(`${API_BASE}/history/${id}?user_id=${userId}`, {
      method: 'DELETE'
    });
    
    if (res.ok) {
      alert('✅ Đã xóa thành công\n✅ Successfully deleted');
      loadSearchHistory();
    } else {
      alert('❌ Không thể xóa mục này\n❌ Cannot delete this item');
    }
  } catch (error) {
    console.error('Error deleting item:', error);
    alert('❌ Lỗi khi xóa\n❌ Error while deleting');
  }
}

async function clearAllHistory() {
  if (!confirm('Xóa toàn bộ lịch sử tìm kiếm?\nClear all search history?')) return;
  
  try {
    const res = await fetch(`${API_BASE}/history/clear?user_id=${userId}`, {
      method: 'DELETE'
    });
    
    if (res.ok) {
      const data = await res.json();
      alert(`✅ Đã xóa ${data.deleted_count} mục\n✅ Deleted ${data.deleted_count} items`);
      loadSearchHistory();
    } else {
      alert('❌ Không thể xóa lịch sử\n❌ Cannot clear history');
    }
  } catch (error) {
    console.error('Error clearing history:', error);
    alert('❌ Lỗi khi xóa lịch sử\n❌ Error while clearing history');
  }
}

async function repeatSearch(id) {
  try {
    showLoading();
    
    const res = await fetch(`${API_BASE}/history/${id}?user_id=${userId}`);
    
    if (!res.ok) {
      alert('❌ Không thể tải thông tin tìm kiếm\n❌ Cannot load search info');
      loadSearchHistory();
      return;
    }
    
    const data = await res.json();
    
    // ⭐ XÁC ĐỊNH LOCATION VALUE
    let locationValue = '';
    
    if (!data.location_text && data.latitude && data.longitude) {
      locationValue = `${data.latitude},${data.longitude}`;
    } else if (data.location_text) {
      locationValue = data.location_text;
    }
    
    localStorage.setItem('searchPrefill', JSON.stringify({
      dishName: data.dish_name,
      restaurantType: data.restaurant_type,
      priceMin: data.price_min || 0,
      priceMax: data.price_max || 0,
      maxRadius: data.max_radius,
      location: locationValue,
      lat: data.latitude,
      lon: data.longitude
    }));
    
    window.location.href = '/search';
    
  } catch (error) {
    console.error('Error loading search detail:', error);
    alert('❌ Lỗi khi tải thông tin tìm kiếm\n❌ Error while loading search info');
    loadSearchHistory();
  }
}

// =================== HELPER FUNCTIONS ===================
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatDate(dateString) {
  if (!dateString) return 'N/A';
  
  try {
    // ⭐ QUAN TRỌNG: Không thêm 'Z' vì backend đã lưu giờ VN (không phải UTC)
    // Parse trực tiếp như local time
    const date = new Date(dateString.replace(' ', 'T'));
    
    return date.toLocaleString('vi-VN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
      // ⭐ BỎ timeZone vì đã là giờ VN rồi
    });
  } catch (e) {
    return dateString;
  }
}

function formatPrice(price) {
  return price.toLocaleString('vi-VN') + '₫';
}

function showLoading() {
  const historyList = document.getElementById('historyList');
  if (historyList) {
    historyList.innerHTML = '<li class="loading">⏳ Đang tải...</li>';
  }
}


