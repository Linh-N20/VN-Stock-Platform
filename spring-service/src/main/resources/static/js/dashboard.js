// Load trạng thái yêu thích cho tất cả cổ phiếu trong watchlist
(function () {
    fetch('/api/favorites', { credentials: 'same-origin' })
        .then(r => r.json())
        .then(data => {
            const favSet = new Set(data.favorites || []);
            document.querySelectorAll('.fav-btn').forEach(btn => {
                const sym = btn.getAttribute('data-symbol');
                if (favSet.has(sym)) setFavBtn(btn, true);
            });
        })
        .catch(() => {});
})();
 
function setFavBtn(btn, isFav) {
    const icon = btn.querySelector('.fav-icon');
    if (isFav) {
        icon.className  = 'bi bi-heart-fill fav-icon';
        btn.style.color = '#dc3545';
        btn.title       = 'Bỏ yêu thích';
    } else {
        icon.className  = 'bi bi-heart fav-icon';
        btn.style.color = '#d1d5db';
        btn.title       = 'Yêu thích';
    }
}
 
function toggleFavDashboard(btn) {
    const sym       = btn.getAttribute('data-symbol');
    const csrfToken = document.querySelector('meta[name="_csrf"]')?.getAttribute('content') || '';
    fetch(`/api/favorites/toggle/${sym}`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'X-CSRF-TOKEN': csrfToken }
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) return;
        setFavBtn(btn, data.favorited);
        showDashToast(data.favorited
            ? `❤️ Đã thêm ${sym} vào yêu thích`
            : `🤍 Đã xóa ${sym} khỏi yêu thích`);
    })
    .catch(() => {});
}
 
function showDashToast(msg) {
    let t = document.getElementById('dash-toast');
    if (!t) {
        t = document.createElement('div');
        t.id = 'dash-toast';
        t.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9999;' +
            'background:#1e293b;color:#f1f5f9;padding:10px 18px;border-radius:10px;' +
            'font-size:.875rem;box-shadow:0 4px 16px rgba(0,0,0,.3);transition:opacity .3s;opacity:0';
        document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.opacity = '1';
    setTimeout(() => t.style.opacity = '0', 2500);
}