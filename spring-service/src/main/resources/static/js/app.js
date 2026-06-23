// Auto-dismiss alerts sau 5 giây
document.querySelectorAll('.alert').forEach(el => {
    setTimeout(() => bootstrap.Alert.getOrCreateInstance(el)?.close(), 5000);
});
