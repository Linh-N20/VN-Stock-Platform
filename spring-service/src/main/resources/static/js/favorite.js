// Load trạng thái yêu thích
(function () {
    fetch('/api/favorites', { credentials: 'same-origin' })
        .then(r => r.json())
        .then(data => {
            const favSet = new Set(data.favorites || []);
            document.querySelectorAll(".fav-btn").forEach(btn => {
                const sym = btn.dataset.symbol;
                setFavBtn(btn, favSet.has(sym));
            });
        })
        .catch(() => {});
})();

function setFavBtn(btn, isFav) {
    const icon = btn.querySelector(".fav-icon");
    if (!icon) return;
    if (isFav) {
        icon.className  = "bi bi-heart-fill fav-icon";
        btn.style.color = "#dc3545";
        btn.title       = "Bỏ yêu thích";
    } else {
        icon.className  = "bi bi-heart fav-icon";
        btn.style.color = "#d1d5db";
        btn.title       = "Yêu thích";
    }
}

function toggleFavorite(btn) {
    const symbol = btn.dataset.symbol;
    const csrf   = document.querySelector('meta[name="_csrf"]')?.content || "";

    fetch(`/api/favorites/toggle/${symbol}`, {
        method: "POST", credentials: "same-origin",
        headers: { "X-CSRF-TOKEN": csrf }
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) return;
        setFavBtn(btn, data.favorited);
        showFavoriteToast(data.favorited
            ? `❤️ Đã thêm ${symbol} vào yêu thích`
            : `🤍 Đã xóa ${symbol} khỏi yêu thích`);
    });
}

// Alias dùng cho dashboard — cùng logic, khác tên hàm
function toggleFavDashboard(btn) {
    toggleFavorite(btn);
}

function showFavoriteToast(msg) {
    let toast = document.getElementById("favorite-toast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "favorite-toast";
        toast.style.cssText =
            "position:fixed;bottom:24px;right:24px;z-index:9999;" +
            "background:#1e293b;color:white;padding:10px 18px;" +
            "border-radius:10px;opacity:0;transition:opacity .3s;";
        document.body.appendChild(toast);
    }
    toast.textContent    = msg;
    toast.style.opacity  = 1;
    setTimeout(() => toast.style.opacity = 0, 2500);
}