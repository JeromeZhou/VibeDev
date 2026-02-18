/* GPU-Insight 主题切换 */
(function() {
    var STORAGE_KEY = 'gpu-insight-theme';

    function getPreferred() {
        var saved = localStorage.getItem(STORAGE_KEY);
        if (saved) return saved;
        return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }

    function apply(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(STORAGE_KEY, theme);
        // 更新按钮图标
        var icons = document.querySelectorAll('.theme-icon');
        icons.forEach(function(el) {
            el.textContent = theme === 'dark' ? 'light_mode' : 'dark_mode';
        });
    }

    // 页面加载时立即应用（防闪烁）
    apply(getPreferred());

    // 暴露切换函数
    window.toggleTheme = function() {
        var current = document.documentElement.getAttribute('data-theme') || 'dark';
        apply(current === 'dark' ? 'light' : 'dark');
    };
})();
