
// UPDATE detail.js - Lấy rating động từ comments
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
    return `<span data-key="From">From</span> ${item.price_min.toLocaleString('vi-VN')}₫`;
  }
  
  // Nếu có price (giá đơn)
  if (item.price) {
    return `${item.price.toLocaleString('vi-VN')}₫`;
  }
  
  return `<span data-key="No price info">No price info</span>`;
}

// =================== MAIN INIT ===================
document.addEventListener("DOMContentLoaded", async () => {
  const data = JSON.parse(localStorage.getItem("selectedRestaurant"));
  
  document.getElementById("viewMapBtn").addEventListener("click", () => {
    window.location.href = "/restaurant";
  });

  if (!data) {
    console.error("Không tìm thấy dữ liệu món ăn!");
    alert("No restaurant data found. Please go back and select a restaurant.");
    window.location.href = "/";
    return;
  }

  console.log("Restaurant data loaded:", data);

  const restaurantId = data.id || data.restaurant_id;

  if (!restaurantId) {
    console.error(" Không tìm thấy restaurant_id!");
    alert(" Invalid restaurant ID. Please try again.");
    window.location.href = "/";
    return;
  }

  // 🔥 LẤY RATING THỰC TẾ TỪ COMMENTS
  await loadRealRating(restaurantId);

  // =================== GÁN DỮ LIỆU VÀO UI ===================
  
  // Restaurant Name
  document.getElementById("restaurantName").textContent =
    data.name || data.restaurant || "Unknown Name";

  // Restaurant Image
  document.getElementById("restaurantImage").src =
    data.image || "/static/images/food1.png";
  
  document.getElementById("restaurantImage").onerror = function() {
    this.src = "/static/images/food1.png";
  };

  // =================== HIỂN THỊ THÔNG TIN CHI TIẾT ===================
  const desc = document.getElementById("restaurantDesc");
  let descHTML = '';
  
  // 1. Opening hours
  if (data.opening_hours && data.opening_hours.trim()) {
    descHTML += `<p> <b data-key="Opening hours:">Opening hours:</b> ${data.opening_hours}</p>`;
  }

  // 2. Address
  if (data.address && data.address.trim()) {
    descHTML += `<p> <b data-key="Address:">Address:</b> ${data.address}</p>`;
  }

  // 3. Price
  if (data.price_text || data.price_min || data.price_max || data.price) {
    descHTML += `<p><b data-key="Price:">Price:</b> ${formatPrice(data)}</p>`;
  }

  // 4. Distance
  if (data.distance !== undefined && data.distance !== null) {
    descHTML += `<p><b data-key="Distance:">Distance:</b> ${data.distance} <span data-key="km">km</span></p>`;
  }
  
  // // 5. Restaurant Type
  // if (data.restaurant_type && data.restaurant_type.trim()) {
  //   descHTML += `<p><b data-key="Type:">Type:</b> ${data.restaurant_type}</p>`;
  // }
  
  // Nếu không có thông tin gì cả
  if (!descHTML || descHTML.trim() === '') {
    descHTML = '<p style="color: #999; font-style: italic;">No additional information available.</p>';
  }
  
  // Gán HTML vào description box
  desc.innerHTML = descHTML;

  // Gọi translate nếu có
  if (window.translatePage) {
    window.translatePage();
  }


  // =============== Rating Stars ===============
  let selectedRating = 0;
  const stars = document.querySelectorAll('.star');
  
  if (stars.length > 0) {
    stars.forEach(star => {
      star.addEventListener('click', function() {
        selectedRating = parseInt(this.getAttribute('data-value'));
        updateStarsDisplay();
        document.getElementById('ratingValue').textContent = selectedRating + '/5';
      });

      star.addEventListener('mouseover', function() {
        const value = parseInt(this.getAttribute('data-value'));
        highlightStars(value);
      });

      star.addEventListener('mouseout', function() {
        updateStarsDisplay();
      });
    });

    function highlightStars(value) {
      stars.forEach(star => {
        const starValue = parseInt(star.getAttribute('data-value'));
        if (starValue <= value) {
          star.classList.remove('bx-star');
          star.classList.add('bxs-star');
          star.style.color = '#ffc107';
        } else {
          star.classList.remove('bxs-star');
          star.classList.add('bx-star');
          star.style.color = '#ddd';
        }
      });
    }

    function updateStarsDisplay() {
      stars.forEach(star => {
        const starValue = parseInt(star.getAttribute('data-value'));
        if (starValue <= selectedRating) {
          star.classList.remove('bx-star');
          star.classList.add('bxs-star');
          star.style.color = '#ffc107';
        } else {
          star.classList.remove('bxs-star');
          star.classList.add('bx-star');
          star.style.color = '#ddd';
        }
      });
    }
  }

  // =============== Character Counter ===============
  const commentText = document.getElementById('commentText');
  const charCount = document.getElementById('charCount');
  const charCounter = document.querySelector('.char-counter');

  if (commentText && charCount) {
    commentText.addEventListener('input', function() {
      const currentLength = this.value.length;
      const maxLength = 500;
      
      charCount.textContent = currentLength;

      if (currentLength > maxLength - 50) {
        charCounter.classList.add('warning');
        charCounter.classList.remove('error');
      } else if (currentLength >= maxLength) {
        charCounter.classList.add('error');
        charCounter.classList.remove('warning');
      } else {
        charCounter.classList.remove('warning', 'error');
      }
    });

    commentText.addEventListener('keydown', function(e) {
      if (this.value.length >= 500 && e.key !== 'Backspace' && e.key !== 'Delete') {
        e.preventDefault();
      }
    });
  }

  // =============== Image Upload for Comment ===============
  const imgBtn = document.getElementById("commentImageBtn");
  const imgInput = document.getElementById("commentImage");
  const previewBox = document.getElementById("previewImage");
  const previewImg = document.getElementById("previewImgTag");
  const removePreview = document.getElementById("removePreview");

  if (imgBtn) {
    imgBtn.addEventListener("click", () => imgInput.click());
  }

  if (imgInput) {
    imgInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;

      const url = URL.createObjectURL(file);
      previewImg.src = url;
      previewBox.style.display = "block";
    });
  }

  if (removePreview) {
    removePreview.addEventListener("click", () => {
      imgInput.value = "";
      previewBox.style.display = "none";
    });
  }

  // =============== COMMENT SYSTEM ===============
  loadComments(restaurantId);

  const submitBtn = document.getElementById("submitComment");
  if (submitBtn) {
    submitBtn.addEventListener("click", async () => {
      const text = commentText.value.trim();
      const rating = selectedRating;
      const file = imgInput.files[0];

      if (!rating) return alert("Vui lòng chọn số sao!");
      if (!text && !file) return alert("Bạn phải nhập nội dung hoặc chọn ảnh!");

      const formData = new FormData();
      formData.append("restaurant_id", restaurantId);
      formData.append("rating", rating);
      formData.append("comment", text);
      if (file) formData.append("image", file);

      const res = await fetch("/auth/add_comment", {
        method: "POST",
        body: formData
      });

      const result = await res.json();
      alert(result.message || result.error);

      if (res.ok) {
        commentText.value = "";
        selectedRating = 0;
        imgInput.value = "";
        previewBox.style.display = "none";
        updateStarsDisplay();
        
        //  CẬP NHẬT RATING SAU KHI COMMENT MỚI
        await loadRealRating(restaurantId);
        loadComments(restaurantId);
      }
    });
  }
});

// =======================
// 🆕 HÀM LẤY RATING THỰC TỪ COMMENTS
// =======================
async function loadRealRating(restaurantId) {
  try {
    const res = await fetch(`/auth/get_restaurant_rating?restaurant_id=${restaurantId}`);
    const ratingData = await res.json();

    console.log("Real rating data:", ratingData);

    const ratingElement = document.getElementById("restaurantRating");
    
    if (ratingData.review_count === 0) {
      ratingElement.innerHTML = '⭐ <span data-key="No ratings yet">No ratings yet</span>';
      ratingElement.title = "Be the first to review!";
    } else {
      ratingElement.textContent = `⭐ ${ratingData.avg_rating}/5`;
      ratingElement.title = `${ratingData.review_count} reviews`;
      
      // Optional: Hiển thị rating breakdown
      const breakdown = ratingData.rating_breakdown;
      console.log("Rating breakdown:", breakdown);
    }

  } catch (error) {
    console.error(" Error loading rating:", error);
    document.getElementById("restaurantRating").textContent = "⭐ No rating";
  }
}

// =======================
// HÀM LOAD COMMENT
// =======================
async function loadComments(restaurantId) {
  const res = await fetch(`/auth/get_comments?restaurant_id=${restaurantId}`);
  const comments = await res.json();

  const list = document.getElementById("commentList");
  list.innerHTML = "";

  if (comments.length === 0) {
    list.innerHTML = `<p style="color:#777;">Chưa có bình luận nào.</p>`;
    return;
  }

  comments.forEach(c => {
      const div = document.createElement("div");
      div.className = "comment-item";

      const currentUser = document.body.getAttribute("data-user") || null;

      const avatarSrc = c.avatar 
        ? `/static/uploads/${c.avatar}`
        : `/static/images/default-avatar.png`;

      div.innerHTML = `
        <div class="comment-avatar">
          <img src="${avatarSrc}" alt="avatar">
        </div>

        <div class="comment-body">
          <div class="comment-header">
            <span class="comment-username">${c.username}</span>
            <span class="comment-rating">${c.rating} ⭐</span>
            <span class="comment-time">${formatDate(c.created_at)}</span>
            ${
              currentUser === c.username
              ? `
                  <button class="edit-btn" data-id="${c.id}" data-text="${c.comment}" data-key="Edit">Edit</button>
                  <button class="delete-btn" data-id="${c.id}" data-key="Delete">Delete</button>
                `
              : ""
            }
          </div>

          <div class="comment-text">${c.comment}</div>

          ${c.image ? `<img class="comment-photo" src="/static/comment_images/${c.image}">` : ""}
        </div>
      `;
      if (window.translatePage) {
        window.translatePage();
      }
      list.appendChild(div);
  });

  function formatDate(dateString) {
      const d = new Date(dateString);
      const day = String(d.getDate()).padStart(2, "0");
      const month = String(d.getMonth() + 1).padStart(2, "0");
      const year = d.getFullYear();
      return `${day}-${month}-${year}`;
  }

  // Delete
  document.querySelectorAll(".delete-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-id");

      if (!confirm("Bạn chắc muốn xoá bình luận này?")) return;

      const res = await fetch("/auth/delete_comment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment_id: id })
      });

      const result = await res.json();
      alert(result.message || result.error);

      if (res.ok) {
        // CẬP NHẬT RATING SAU KHI XÓA COMMENT
        await loadRealRating(restaurantId);
        loadComments(restaurantId);
      }
    });
  });

  // Edit
  let editingId = null;

  document.querySelectorAll(".edit-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      editingId = btn.dataset.id;
      const oldText = btn.dataset.text;

      document.getElementById("editCommentInput").value = oldText;
      document.getElementById("editModal").style.display = "flex";
    });
  });

  document.getElementById("cancelEditBtn").addEventListener("click", () => {
    document.getElementById("editModal").style.display = "none";
    editingId = null;
  });

  document.getElementById("saveEditBtn").addEventListener("click", async () => {
    const newText = document.getElementById("editCommentInput").value.trim();

    if (!newText) {
      alert("Nội dung không được trống!");
      return;
    }

    const res = await fetch("/auth/edit_comment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: editingId,
        comment: newText
      })
    });

    const result = await res.json();
    alert(result.message || result.error);

    if (res.ok) {
      document.getElementById("editModal").style.display = "none";
      loadComments(restaurantId);
    }
  });
}
