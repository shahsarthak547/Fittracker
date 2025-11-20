document.addEventListener("DOMContentLoaded", function(){
  const btn = document.getElementById("darkToggle");
  const html = document.documentElement;
  if(btn){
    btn.addEventListener("click", () => {
      const cur = html.getAttribute("data-bs-theme") || "light";
      const next = cur === "light" ? "dark" : "light";
      html.setAttribute("data-bs-theme", next);
      btn.textContent = next === "dark" ? "Light" : "Dark";
    });
  }

  const chartCanvas = document.getElementById("multiChart");
  if (chartCanvas) {
    const params = new URLSearchParams({ start: window.startParam || "", end: window.endParam || "" });
    fetch("/api/chart-data?" + params.toString())
      .then(r => r.json())
      .then(data => {
        const ctx = chartCanvas.getContext('2d');
        new Chart(ctx, {
          type: 'line',
          data: {
            labels: data.dates,
            datasets: [
              {
                label: 'Steps',
                data: data.steps,
                tension: 0.3,
                yAxisID: 'y'
              },
              {
                label: 'Calories',
                data: data.calories,
                tension: 0.3,
                yAxisID: 'y1'
              },
              {
                label: 'Sleep',
                data: data.sleep,
                tension: 0.3,
                yAxisID: 'y2'
              }
            ]
          },
          options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            scales: {
              y: { type: 'linear', display: true, position: 'left' },
              y1: { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false } },
              y2: { type: 'linear', display: false }
            }
          }
        });
      }).catch(err => {
        console.error("Chart data error:", err);
      });
  }
});
