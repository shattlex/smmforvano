const form = document.getElementById("loginForm");
const error = document.getElementById("error");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.textContent = "";

  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;

  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email, password }),
    });

    const data = await res.json();
    if (!res.ok) {
      error.textContent = data.error || "Ошибка входа";
      return;
    }

    window.location.href = "/";
  } catch (e) {
    error.textContent = "Сетевая ошибка";
  }
});
