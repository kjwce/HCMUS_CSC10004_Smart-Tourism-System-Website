// static/js/signup.js
document.addEventListener("DOMContentLoaded", function () {
  const form = document.querySelector("form");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const name = form.querySelector('input[type="text"]').value;
    const email = form.querySelector('input[type="email"]').value;
    const pass1 = form.querySelectorAll('input[type="password"]')[0].value;
    const pass2 = form.querySelectorAll('input[type="password"]')[1].value;

    if (pass1 !== pass2) {
      alert("Mật khẩu nhập lại không khớp!");
      return;
    }

    const res = await fetch("http://127.0.0.1:5000/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: name,
        email: email,
        password: pass1,
      }),
    });

    const data = await res.json();

    if (res.ok) {
      alert("Mã OTP đã được gửi đến email. Vui lòng nhập mã xác thực!");
      window.location.href = "/auth/verify";
    } else {
      alert(data.error || "Đăng ký thất bại!");
    }

  });
});
