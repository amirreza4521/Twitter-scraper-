/**
 * متغیرهای سراسری مدیریت وضعیت کلاینت
 */
let requestQueue = []; // صف درخواست‌ها برای ذخیره کارهای در انتظار
let isBusy = false;    // وضعیت سیستم
let logInterval = null; // وضعیت برای دریافت لاگ ها

const $ = (id) => document.getElementById(id);

// تنظیمات مربوط به هر ماژول برای تغییر رابط کاربری
const MODULE_CONFIG = {
    'search': {
        hint: 'جستجو بر اساس هشتگ یا کلمه کلیدی در کل توییتر.',
        placeholder: '#ArtificialIntelligence',
        label: 'عبارت جستجو'
    },
    'comments': {
        hint: 'استخراج thread کامل و نظرات یک توییت خاص.',
        placeholder: 'https://x.com/user/status/123...',
        label: 'لینک پست'
    },
    'profile': {
        hint: 'خزش در تایم‌لاین کاربر و دریافت توییت‌ها.',
        placeholder: 'username',
        label: 'نام کاربری'
    }
};

//  بارگذاری صفحه: اتصال Event Listener ها به دکمه‌ها و ورودی‌ها
document.addEventListener('DOMContentLoaded', () => {
    updateUI(); // تنظیم اولیه UI
    $('mode').addEventListener('change', updateUI); // تغییر ورودی‌ها با تغییر ماژول
    $('btn-add').addEventListener('click', handleAddQueue); // دکمه افزودن به صف
    $('btn-clear').addEventListener('click', clearAll); // دکمه پاکسازی
    $('btn-start').addEventListener('click', startBatchProcess); // دکمه شروع اصلی
});

// رابط کاربری را بر اساس ماژول انتخاب شده (Search/Comments/Profile) به‌روزرسانی می‌کند.
function updateUI() {
    const mode = $('mode').value;
    const config = MODULE_CONFIG[mode];

    $('hint-text').textContent = config.hint;
    $('target_url').placeholder = config.placeholder;
    $('input-label').textContent = config.label;
}

// پردازش فرم ورودی و افزودن درخواست جدید به صف (requestQueue).
// این تابع خالی نبودن ورودی را هم انجام می‌دهد.
function handleAddQueue() {
    const inputVal = $('target_url').value.trim();

    // اگر ورودی خالی بود، کادر قرمز شود
    if (!inputVal) {
        $('target_url').classList.add('ring-2', 'ring-red-500');
        setTimeout(() => $('target_url').classList.remove('ring-2', 'ring-red-500'), 500);
        return;
    }

    // ایجاد آبجکت درخواست جدید
    const newItem = {
        id: Date.now().toString().slice(-6),
        mode: $('mode').value,
        target: inputVal,
        limit: parseInt($('limit_count').value) || 50,
        media: $('media_check').checked,
        status: 'pending', //  در انتظار
        extras: {}
    };

    requestQueue.push(newItem);
    renderTable(); // به‌روزرسانی جدول 
    $('target_url').value = ''; // پاک کردن فیلد ورودی
    $('target_url').focus();
}


// جدول HTML مدیریت صف را بر اساس requestQueue بازنویسی می‌کند.
function renderTable() {
    const tbody = $('queue-body');
    const emptyState = $('empty-state');

    tbody.innerHTML = '';

    if (requestQueue.length === 0) {
        emptyState.style.display = 'flex';
        return;
    }

    emptyState.style.display = 'none';

    requestQueue.forEach((item, idx) => {
        const statusMeta = getStatusBadge(item.status);

        // ساخت دکمه دانلود یا دکمه حذف
        let actionCellContent = '';

        if (item.status === 'completed' && item.resultFile) {
            // اگر تمام شده و فایل دارد، دکمه دانلود بساز
            // در فایل script.js
            actionCellContent = `<a href="/download/${item.resultFile}" target="_blank" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[10px] font-bold transition">دانلود (ZIP)</a>`;

        } else if (item.status === 'pending') {
            // اگر در صف است، دکمه حذف بساز
            actionCellContent = `<button onclick="removeItem('${item.id}')" class="text-slate-600 hover:text-rose-500 transition">✕</button>`;
        } else {
            // در غیر این صورت قفل
            actionCellContent = '<span class="text-slate-700 text-xs">🔒</span>';
        }

        const row = `
            <tr class="table-row-hover border-b border-slate-800 last:border-0 transition group">
                <td class="px-4 py-3 text-center text-slate-500 font-mono text-xs">${idx + 1}</td>
                <td class="px-4 py-3 text-blue-400 font-medium">${item.mode}</td>
                <td class="px-4 py-3 font-mono text-xs text-slate-300 truncate max-w-[150px]" title="${item.target}">${item.target}</td>
                <td class="px-4 py-3 text-center font-mono">${item.limit}</td>
                <td class="px-4 py-3 text-center text-xs">${item.media ? '✅' : '-'}</td>
                <td class="px-4 py-3 text-center">
                    <span class="px-2 py-1 rounded text-[10px] font-bold block w-full ${statusMeta.class}">
                        ${statusMeta.text}
                    </span>
                </td>
                <td class="px-4 py-3 text-center">
                    ${actionCellContent}
                </td>
            </tr>
        `;
        tbody.innerHTML += row;
    });
}


// استایل و متن وضعیت را بر اساس وضعیت آیتم برمی‌گرداند.
function getStatusBadge(status) {
    switch (status) {
        case 'processing': return { class: 'bg-blue-900/50 text-blue-200 border border-blue-700/50 animate-pulse', text: 'در حال انجام' };
        case 'completed': return { class: 'bg-emerald-900/50 text-emerald-200 border border-emerald-700/50', text: 'تکمیل شده' };
        case 'failed': return { class: 'bg-rose-900/50 text-rose-200 border border-rose-700/50', text: 'خطا' };
        default: return { class: 'bg-slate-700/50 text-slate-400', text: 'در صف' };
    }
}

// حذف آیتم از صف
window.removeItem = (id) => {
    requestQueue = requestQueue.filter(i => i.id !== id);
    renderTable();
};

window.clearAll = () => {
    if (isBusy) return;
    requestQueue = [];
    renderTable();
};

// تابع اصلی پردازش صف
// به صورت ترتیبی (Batch) درخواست‌ها را به سرور ارسال می‌کند 
async function startBatchProcess() {
    if (requestQueue.length === 0 || isBusy) return;

    setSystemBusy(true);
    sysLog("Initiating batch process...");

    // شرپع polling
    if (!logInterval) logInterval = setInterval(pullLogs, 1500);

    for (let i = 0; i < requestQueue.length; i++) {
        if (requestQueue[i].status === 'pending') {
            const currentItem = requestQueue[i];

            // تغییر وضعیت در UI
            currentItem.status = 'processing';
            renderTable();

            try {
                // ارسال درخواست async به سرور و انتظار برای تمام شدن
                // نام فایل را از تابع بالا می‌گیریم
                const generatedFile = await sendRequestToAPI(currentItem);

                // حتماً آن را در آیتم ذخیره می‌کنیم
                if (generatedFile) {
                    currentItem.resultFile = generatedFile;
                }

                currentItem.status = 'completed';
    sysLog(`Job #${currentItem.id} finished successfully.`);
            } catch (e) {
                console.error(e);
                currentItem.status = 'failed';
                sysLog(`Job #${currentItem.id} failed: ${e}`);
            }

            renderTable();
        }
    }

    // پایان عملیات
    setSystemBusy(false);
    clearInterval(logInterval);
    logInterval = null;
    sysLog("All jobs processed.");
    alert("عملیات پایان یافت.");
}

// ارسال یک درخواست تکی به API سرور (/start-scrape)
// و انتظار تا زمانی که کار سرور تمام شود.
function sendRequestToAPI(payload) {
    return new Promise((resolve, reject) => {
        fetch('/start-scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: payload.mode,
                url: payload.target,
                count: payload.limit,
                download_img: payload.media,
                extras: payload.extras
            })
        })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'success') {
                    // منتظر می‌مانیم تا سرور کارش تمام شود
                    const poll = setInterval(async () => {
                        try {
                            const res = await fetch('/get-logs');
                            const logData = await res.json();

                            // اگر is_running فالس شد، یعنی کار تمام شده است
                            if (!logData.is_running) {
                                clearInterval(poll);
                                // تغییر مهم: نام فایل نهایی را هم برمی‌گردانیم
                                resolve(logData.last_file);
                            }
                        } catch (e) {
                            console.error("Polling error", e);
                        }
                    }, 2000);
                } else {
                    reject(data.message);
                }
            })
            .catch(err => reject(err));
    });
}
// دریافت لاگ‌های جدید از سرور و نمایش در کنسول پنل
async function pullLogs() {
    try {
        const res = await fetch('/get-logs');
        const data = await res.json();

        if (data.logs?.length) {
            data.logs.forEach(l => sysLog(l));
        }

        // اگر سرور نام فایلی را فرستاد، آن را به آیتم در حال پردازش نسبت بده
        if (data.last_file) {
            // پیدا کردن آیتمی که الان در حال پردازش است (یا تازه تمام شده)
            const processingItem = requestQueue.find(q => q.status === 'processing');
            if (processingItem) {
                processingItem.resultFile = data.last_file;
            }
        }

    } catch (e) { /* Silent fail if server is off */ }
}


// تابع کمکی برای افزودن خط جدید به کنسول لاگ در UI
function sysLog(msg) {
    const box = $('console-logs');
    const line = document.createElement('div');
    line.textContent = `> ${msg}`;
    line.className = "hover:bg-white/5 px-1 rounded transition";
    box.appendChild(line);
    box.scrollTop = box.scrollHeight;
}

// مدیریت وضعیت دکمه‌ها در هنگام مشغول بودن سیستم
function setSystemBusy(state) {
    isBusy = state;
    const btn = $('btn-start');
    const statusBadge = $('engine-status');

    if (state) {
        btn.disabled = true;
        btn.innerHTML = `<span class="animate-spin">⏳</span> پردازش...`;
        statusBadge.textContent = "BUSY";
        statusBadge.className = "text-blue-400 animate-pulse font-mono";
    } else {
        btn.disabled = false;
        btn.innerHTML = `شروع عملیات`;
        statusBadge.textContent = "READY";
        statusBadge.className = "text-emerald-400 font-mono";
    }
}