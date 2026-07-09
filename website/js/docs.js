// 文档页面交互功能

// 侧边栏导航高亮
const sections = document.querySelectorAll('.doc-section');
const navLinks = document.querySelectorAll('.docs-sidebar a');

function updateActiveLink() {
    let currentSection = '';
    
    sections.forEach(section => {
        const sectionTop = section.offsetTop;
        const sectionHeight = section.clientHeight;
        
        if (window.pageYOffset >= sectionTop - 150) {
            currentSection = section.getAttribute('id');
        }
    });
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === `#${currentSection}`) {
            link.classList.add('active');
        }
    });
}

window.addEventListener('scroll', updateActiveLink);
updateActiveLink();

// 代码块复制功能
document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
        const codeBlock = btn.closest('.code-block');
        const code = codeBlock.querySelector('pre').textContent;
        
        try {
            await navigator.clipboard.writeText(code);
            
            const originalHTML = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-check"></i> 已复制';
            btn.style.background = 'rgba(16, 185, 129, 0.2)';
            btn.style.borderColor = 'var(--success-color)';
            btn.style.color = 'var(--success-color)';
            
            setTimeout(() => {
                btn.innerHTML = originalHTML;
                btn.style.background = '';
                btn.style.borderColor = '';
                btn.style.color = '';
            }, 2000);
        } catch (err) {
            console.error('复制失败:', err);
            btn.innerHTML = '<i class="fas fa-times"></i> 失败';
            btn.style.background = 'rgba(239, 68, 68, 0.2)';
            btn.style.borderColor = 'var(--danger-color)';
            btn.style.color = 'var(--danger-color)';
            
            setTimeout(() => {
                btn.innerHTML = '<i class="fas fa-copy"></i>';
                btn.style.background = '';
                btn.style.borderColor = '';
                btn.style.color = '';
            }, 2000);
        }
    });
});

// 平滑滚动到锚点
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            const offsetTop = target.offsetTop - 100;
            window.scrollTo({
                top: offsetTop,
                behavior: 'smooth'
            });
        }
    });
});

// 搜索功能（如果有搜索框）
const searchInput = document.querySelector('.docs-search input');
if (searchInput) {
    searchInput.addEventListener('input', function() {
        const query = this.value.toLowerCase();
        
        sections.forEach(section => {
            const text = section.textContent.toLowerCase();
            if (text.includes(query) || query === '') {
                section.style.display = 'block';
            } else {
                section.style.display = 'none';
            }
        });
    });
}

// 表格响应式处理
const tables = document.querySelectorAll('table');
tables.forEach(table => {
    const wrapper = document.createElement('div');
    wrapper.className = 'table-wrapper';
    wrapper.style.overflowX = 'auto';
    wrapper.style.margin = '1.5rem 0';
    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(table);
});

// 代码块语法高亮（简单实现）
document.querySelectorAll('.code-block pre code').forEach(block => {
    let html = block.textContent;
    
    // 简单的语法高亮
    html = html
        .replace(/(import|from|def|class|return|if|else|elif|for|while|try|except|with|as|in|not|and|or|True|False|None)/g, '<span class="keyword">$1</span>')
        .replace(/('.*?'|".*?")/g, '<span class="string">$1</span>')
        .replace(/(#.*$)/gm, '<span class="comment">$1</span>')
        .replace(/\b(\d+)\b/g, '<span class="number">$1</span>');
    
    block.innerHTML = html;
});

// 添加语法高亮样式
const style = document.createElement('style');
style.textContent = `
    .keyword { color: #c792ea; }
    .string { color: #c3e88d; }
    .comment { color: #546e7a; font-style: italic; }
    .number { color: #f78c6c; }
`;
document.head.appendChild(style);

// 阅读进度条
const progressBar = document.createElement('div');
progressBar.className = 'reading-progress';
progressBar.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    height: 3px;
    background: var(--gradient-1);
    z-index: 1001;
    transition: width 0.1s;
`;
document.body.appendChild(progressBar);

window.addEventListener('scroll', () => {
    const windowHeight = window.innerHeight;
    const documentHeight = document.documentElement.scrollHeight - windowHeight;
    const scrolled = (window.pageYOffset / documentHeight) * 100;
    progressBar.style.width = scrolled + '%';
});

// 打印功能
const printBtn = document.querySelector('.print-btn');
if (printBtn) {
    printBtn.addEventListener('click', () => {
        window.print();
    });
}

// 键盘快捷键
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K 打开搜索
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.querySelector('.docs-search input');
        if (searchInput) {
            searchInput.focus();
        }
    }
    
    // Ctrl/Cmd + P 打印
    if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
        e.preventDefault();
        window.print();
    }
});

// 移动端侧边栏切换
const sidebarToggle = document.querySelector('.sidebar-toggle');
const sidebar = document.querySelector('.docs-sidebar');

if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('mobile-open');
    });
}

console.log('OpenCode Docs Loaded Successfully! 📚');