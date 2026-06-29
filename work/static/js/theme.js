const themeSelect = document.getElementById("themeSelect");
if (themeSelect) {
  const savedTheme = localStorage.getItem("nba-theme") || "arena";
  document.documentElement.dataset.theme = savedTheme;
  themeSelect.value = savedTheme;
  themeSelect.addEventListener("change", () => {
    document.documentElement.dataset.theme = themeSelect.value;
    localStorage.setItem("nba-theme", themeSelect.value);
  });
}
