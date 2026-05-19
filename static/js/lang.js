let currentLang = localStorage.getItem("selectedLang") || "vi";
let translations = {};

document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("langToggle2");
  const track = document.getElementById("langTrack");
  const labelLeft = document.querySelector(".label.left");
  const labelRight = document.querySelector(".label.right");

  // Khởi tạo trạng thái nút dựa trên ngôn ngữ đã lưu
  updateToggleState();

  // Hàm load JSON
  async function loadTranslations(lang) {
    try {
      const res = await fetch(`/static/lang/${lang}.json`);
      translations = await res.json();
      translatePage();
      
      // Lưu ngôn ngữ đã chọn
      localStorage.setItem("selectedLang", lang);
    } catch (error) {
      console.error("Error loading translations:", error);
    }
  }

  function translatePage() {
    document.querySelectorAll("[data-key]").forEach(el => {
      const key = el.getAttribute("data-key");
      const translatedValue = translations[key]; // Lấy giá trị dịch

      if (translatedValue) {
        const tagName = el.tagName;

        // KIỂM TRA PHẦN TỬ LÀ INPUT, TEXTAREA, HAY BUTTON
        if (tagName === 'INPUT' || tagName === 'TEXTAREA') {
          // Nếu là input/textarea, thay đổi placeholder
          el.placeholder = translatedValue; 
        } else if (tagName === 'BUTTON') {
          // Nếu là button, thay đổi innerText (nội dung hiển thị)
          el.innerText = translatedValue;
        } else {
          // Các thẻ khác (h1, a, p, span), thay đổi innerText
          el.innerText = translatedValue; 
        }
      }
    });
  }
  window.translatePage = translatePage;


  // Cập nhật giao diện nút chuyển đổi
  function updateToggleState() {
    if (currentLang === "en") {
      track.classList.add("active");
      labelLeft.classList.remove("active");
      labelRight.classList.add("active");
    } else {
      track.classList.remove("active");
      labelRight.classList.remove("active");
      labelLeft.classList.add("active");
    }
  }

  // Load ngôn ngữ đã lưu
  loadTranslations(currentLang);

  // Sự kiện click
  toggle.addEventListener("click", () => {
    if (currentLang === "vi") {
      currentLang = "en";
    } else {
      currentLang = "vi";
    }
    
    updateToggleState();
    loadTranslations(currentLang);
  });
});