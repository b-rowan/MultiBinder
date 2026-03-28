/**
 * Collection page JavaScript for MultiBinder
 */

let currentSearchPage = 1;
let currentSearchTotal = 0;
let currentSearchPages = 0;
let currentCollPage = 1;
let collectionSearchTimeout = null;
let selectedCard = null;
let modalQty = 1;
let collectionSearchDebounce = null;

// ─── Search Cards ─────────────────────────────────────────────────────────────

async function searchCards(page = 1) {
    currentSearchPage = page;
    const q = document.getElementById('card-search-input').value.trim();
    const color = document.getElementById('filter-color').value;
    const rarity = document.getElementById('filter-rarity').value;
    const cardType = document.getElementById('filter-type').value;

    const container = document.getElementById('search-results-container');
    container.innerHTML = '<div class="flex justify-center py-4"><div class="spinner w-6 h-6"></div></div>';

    const params = new URLSearchParams({
        page,
        limit: 20,
        q,
        color,
        rarity,
        card_type: cardType,
    });

    const res = await API.get(`/api/cards/search?${params}`);
    if (!res) {
        container.innerHTML = '<p class="text-center text-red-400 text-sm py-4">Failed to load cards</p>';
        return;
    }

    currentSearchTotal = res.total;
    currentSearchPages = res.pages;

    renderSearchResults(res.cards);
    updateSearchPagination(res);
}

function renderSearchResults(cards) {
    const container = document.getElementById('search-results-container');

    if (!cards || cards.length === 0) {
        container.innerHTML = '<p class="text-center text-gray-500 text-sm py-4">No cards found</p>';
        return;
    }

    container.innerHTML = cards.map(card => {
        const rarityColor = {
            common: 'text-gray-400',
            uncommon: 'text-slate-300',
            rare: 'text-yellow-400',
            mythic: 'text-orange-400',
        }[card.rarity] || 'text-gray-400';

        return `
            <div class="flex items-center gap-2.5 p-2 rounded-lg hover:bg-gray-700 cursor-pointer transition-colors group border border-transparent hover:border-gray-600"
                onclick="openCardModal(${JSON.stringify(card).replace(/"/g, '&quot;')})">
                <img src="${card.image_uri_small || '/static/img/card-back.jpg'}"
                    alt="${card.name}"
                    class="w-9 h-12 rounded object-cover flex-shrink-0 shadow"
                    onerror="this.src='/static/img/card-back.jpg'">
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-white truncate group-hover:text-purple-300">${card.name}</p>
                    <p class="text-xs text-gray-400 truncate">${card.type_line || ''}</p>
                    <div class="flex items-center gap-2 mt-0.5">
                        <span class="text-xs ${rarityColor}">${card.rarity || ''}</span>
                        ${card.mana_cost ? `<span class="text-xs text-gray-500">${card.mana_cost}</span>` : ''}
                    </div>
                </div>
                <button class="flex-shrink-0 w-7 h-7 bg-purple-700/50 hover:bg-purple-600 text-white rounded-lg flex items-center justify-center transition-colors opacity-0 group-hover:opacity-100"
                    onclick="event.stopPropagation(); quickAddToCollection('${card.scryfall_id}')">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
                    </svg>
                </button>
            </div>
        `;
    }).join('');
}

function updateSearchPagination(data) {
    const pagination = document.getElementById('search-pagination');
    const pageInfo = document.getElementById('search-page-info');
    const prevBtn = document.getElementById('search-prev');
    const nextBtn = document.getElementById('search-next');

    if (data.pages <= 1) {
        pagination.classList.add('hidden');
        return;
    }

    pagination.classList.remove('hidden');
    pageInfo.textContent = `Page ${data.page} of ${data.pages} (${data.total} cards)`;
    prevBtn.disabled = data.page <= 1;
    nextBtn.disabled = data.page >= data.pages;
}

// ─── Collection ───────────────────────────────────────────────────────────────

async function loadCollection(page = 1) {
    currentCollPage = page;
    const q = document.getElementById('collection-search')?.value?.trim() || '';

    const container = document.getElementById('collection-grid');
    if (page === 1) {
        container.innerHTML = '<div class="col-span-full flex justify-center py-8"><div class="spinner w-8 h-8"></div></div>';
    }

    const params = new URLSearchParams({ page, limit: 40, q });
    const res = await API.get(`/api/collection?${params}`);

    if (!res) {
        container.innerHTML = '<p class="col-span-full text-center text-red-400 py-8">Failed to load collection</p>';
        return;
    }

    document.getElementById('collection-count').textContent = `${res.total} cards`;
    renderCollection(res.entries);
    updateCollectionPagination(res);
}

function renderCollection(entries) {
    const container = document.getElementById('collection-grid');

    if (!entries || entries.length === 0) {
        container.innerHTML = `
            <div class="col-span-full text-center py-12 text-gray-500">
                <svg class="w-16 h-16 mx-auto mb-3 opacity-20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 6h16M4 10h16M4 14h16M4 18h16"/>
                </svg>
                <p class="text-sm">Your collection is empty.</p>
                <p class="text-xs mt-1">Search for cards on the left to add them.</p>
            </div>`;
        return;
    }

    container.innerHTML = entries.map(entry => {
        const card = entry.card;
        const rarityBorder = {
            common: 'border-gray-600',
            uncommon: 'border-slate-400',
            rare: 'border-yellow-500',
            mythic: 'border-orange-500',
        }[card.rarity] || 'border-gray-600';

        return `
            <div class="relative group card-hover cursor-pointer" onclick="openCollectionCardModal(${JSON.stringify(entry).replace(/"/g, '&quot;')})">
                <div class="relative rounded-xl overflow-hidden border-2 ${entry.foil ? 'border-purple-400 shadow-purple-500/20' : rarityBorder} shadow-lg">
                    <img src="${card.image_uri_small || ''}"
                        alt="${card.name}"
                        class="w-full aspect-[63/88] object-cover"
                        loading="lazy"
                        onerror="this.src=''"
                    >
                    ${entry.foil ? '<div class="absolute inset-0 bg-gradient-to-br from-purple-500/20 to-transparent pointer-events-none"></div>' : ''}
                    <!-- Quantity badge -->
                    <div class="absolute top-1.5 right-1.5 bg-black/70 text-white text-xs font-bold px-1.5 py-0.5 rounded-md">
                        ×${entry.quantity}
                    </div>
                    ${entry.foil ? '<div class="absolute top-1.5 left-1.5 bg-purple-600/80 text-white text-xs px-1.5 py-0.5 rounded-md">✨</div>' : ''}
                    <!-- Hover overlay -->
                    <div class="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-end justify-center opacity-0 group-hover:opacity-100">
                        <div class="pb-2 flex gap-1">
                            <button onclick="event.stopPropagation(); adjustCollectionQty(${entry.id}, ${entry.quantity}, -1)"
                                class="w-7 h-7 bg-gray-800/90 hover:bg-red-800 text-white rounded-lg text-sm font-bold transition-colors">−</button>
                            <button onclick="event.stopPropagation(); adjustCollectionQty(${entry.id}, ${entry.quantity}, 1)"
                                class="w-7 h-7 bg-gray-800/90 hover:bg-green-800 text-white rounded-lg text-sm font-bold transition-colors">+</button>
                            <button onclick="event.stopPropagation(); removeFromCollection(${entry.id})"
                                class="w-7 h-7 bg-gray-800/90 hover:bg-red-900 text-red-400 rounded-lg text-sm transition-colors flex items-center justify-center">
                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
                <p class="text-xs text-gray-400 truncate mt-1 px-0.5">${card.name}</p>
            </div>
        `;
    }).join('');
}

function updateCollectionPagination(data) {
    const pagination = document.getElementById('collection-pagination');
    const pageInfo = document.getElementById('coll-page-info');
    const prevBtn = document.getElementById('coll-prev');
    const nextBtn = document.getElementById('coll-next');

    if (data.pages <= 1) {
        pagination.classList.add('hidden');
        return;
    }

    pagination.classList.remove('hidden');
    pageInfo.textContent = `Page ${data.page} of ${data.pages}`;
    prevBtn.disabled = data.page <= 1;
    nextBtn.disabled = data.page >= data.pages;
}

// ─── Add / Remove / Update ────────────────────────────────────────────────────

async function quickAddToCollection(cardId) {
    const res = await API.post('/api/collection', { card_id: cardId, quantity: 1, foil: false });
    if (res && res.id) {
        showFlash('Added to collection!', 'success');
        loadCollection(currentCollPage);
    } else {
        showFlash(res?.detail || 'Failed to add card', 'error');
    }
}

async function addToCollectionFromModal() {
    if (!selectedCard) return;

    const foil = document.getElementById('modal-foil').checked;
    const btn = document.getElementById('modal-add-btn');
    btn.disabled = true;
    btn.textContent = 'Adding...';

    const res = await API.post('/api/collection', {
        card_id: selectedCard.scryfall_id,
        quantity: modalQty,
        foil,
    });

    btn.disabled = false;
    btn.textContent = 'Add to Collection';

    if (res && res.id) {
        showFlash(`Added ${modalQty}× ${selectedCard.name} to collection!`, 'success');
        closeCardModal();
        loadCollection(currentCollPage);
    } else {
        showFlash(res?.detail || 'Failed to add card', 'error');
    }
}

async function adjustCollectionQty(entryId, currentQty, delta) {
    const newQty = currentQty + delta;
    if (newQty <= 0) {
        await removeFromCollection(entryId);
        return;
    }

    const res = await API.put(`/api/collection/${entryId}`, { quantity: newQty });
    if (res && res.id) {
        loadCollection(currentCollPage);
    }
}

async function removeFromCollection(entryId) {
    const res = await API.delete(`/api/collection/${entryId}`);
    if (res) {
        showFlash('Removed from collection', 'info');
        loadCollection(currentCollPage);
    }
}

// ─── Modal ────────────────────────────────────────────────────────────────────

function openCardModal(card) {
    selectedCard = card;
    modalQty = 1;

    document.getElementById('modal-card-name').textContent = card.name;
    document.getElementById('modal-card-image').src = card.image_uri_normal || card.image_uri_small || '';
    document.getElementById('modal-mana-cost').textContent = card.mana_cost || '';
    document.getElementById('modal-type').textContent = card.type_line || '';
    document.getElementById('modal-oracle').textContent = card.oracle_text || '';
    document.getElementById('modal-set').textContent = card.set_name ? `${card.set_name} · ${card.collector_number || ''}` : '';
    document.getElementById('modal-rarity').textContent = card.rarity ? card.rarity.charAt(0).toUpperCase() + card.rarity.slice(1) : '';
    document.getElementById('modal-qty').textContent = '1';
    document.getElementById('modal-foil').checked = false;
    document.getElementById('card-modal').classList.remove('hidden');
}

function openCollectionCardModal(entry) {
    // Just show card details for collection entries
    openCardModal(entry.card);
}

function closeCardModal() {
    document.getElementById('card-modal').classList.add('hidden');
    selectedCard = null;
}

function adjustModalQty(delta) {
    modalQty = Math.max(1, Math.min(99, modalQty + delta));
    document.getElementById('modal-qty').textContent = modalQty;
}

// Close modal on backdrop click
document.getElementById('card-modal')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeCardModal();
});

// ─── Event Listeners ──────────────────────────────────────────────────────────

document.getElementById('card-search-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') searchCards(1);
});

document.getElementById('card-search-input')?.addEventListener('input', () => {
    clearTimeout(collectionSearchTimeout);
    collectionSearchTimeout = setTimeout(() => searchCards(1), 500);
});

document.getElementById('collection-search')?.addEventListener('input', () => {
    clearTimeout(collectionSearchDebounce);
    collectionSearchDebounce = setTimeout(() => loadCollection(1), 400);
});

document.getElementById('filter-color')?.addEventListener('change', () => searchCards(1));
document.getElementById('filter-rarity')?.addEventListener('change', () => searchCards(1));
document.getElementById('filter-type')?.addEventListener('change', () => searchCards(1));

// ─── CSV Import ───────────────────────────────────────────────────────────────

let importFile = null;

function openImportModal() {
    importFile = null;
    document.getElementById('import-file-input').value = '';
    document.getElementById('import-file-label').textContent = 'Click or drag a CSV file here';
    document.getElementById('import-results').classList.add('hidden');
    document.getElementById('import-errors-box').classList.add('hidden');
    document.getElementById('import-submit-btn').disabled = true;
    document.getElementById('import-modal').classList.remove('hidden');
}

function closeImportModal() {
    document.getElementById('import-modal').classList.add('hidden');
}

function handleImportFileSelect(event) {
    const file = event.target.files[0];
    if (file) setImportFile(file);
}

function handleImportDrop(event) {
    event.preventDefault();
    document.getElementById('import-drop-area').classList.remove('border-purple-500');
    const file = event.dataTransfer.files[0];
    if (file) setImportFile(file);
}

function setImportFile(file) {
    importFile = file;
    document.getElementById('import-file-label').textContent = file.name;
    document.getElementById('import-submit-btn').disabled = false;
    document.getElementById('import-results').classList.add('hidden');
}

async function submitImport() {
    if (!importFile) return;

    const btn = document.getElementById('import-submit-btn');
    btn.disabled = true;
    btn.textContent = 'Importing...';

    const formData = new FormData();
    formData.append('file', importFile);

    const token = localStorage.getItem('token');
    let res;
    try {
        const response = await fetch('/api/collection/import', {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
            body: formData,
        });
        res = await response.json();
    } catch (e) {
        showFlash('Import failed: network error', 'error');
        btn.disabled = false;
        btn.textContent = 'Import';
        return;
    }

    btn.disabled = false;
    btn.textContent = 'Import';

    if (res.detail) {
        showFlash(res.detail, 'error');
        return;
    }

    document.getElementById('import-added').textContent = res.added;
    document.getElementById('import-updated').textContent = res.updated;
    document.getElementById('import-skipped').textContent = res.skipped;
    document.getElementById('import-results').classList.remove('hidden');

    if (res.errors && res.errors.length > 0) {
        const box = document.getElementById('import-errors-box');
        box.innerHTML = res.errors.map(e => `<p>${e}</p>`).join('');
        box.classList.remove('hidden');
    }

    if (res.added > 0 || res.updated > 0) {
        showFlash(`Import complete: ${res.added} added, ${res.updated} updated`, 'success');
        loadCollection(1);
    }
}

document.getElementById('import-modal')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeImportModal();
});

// ─── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    const check = setInterval(() => {
        if (window.currentUser !== undefined) {
            clearInterval(check);
            if (window.currentUser) {
                loadCollection(1);
            }
        }
    }, 100);
});
