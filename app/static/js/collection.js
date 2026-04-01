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

// Edit modal state
let editingEntry = null;
let editingCard = null;
let editModalQty = 1;

// Version picker state
let versionPickerMode = null; // 'add' or 'change'

// Active collection state
let activeCollectionId = null;
let activeCollectionType = 'personal'; // 'personal' or 'external'
let collectionsCache = [];

// Display mode
let collDisplayMode = 'grid'; // 'grid' or 'list'

function setCollDisplayMode(mode) {
    collDisplayMode = mode;
    document.getElementById('view-grid-btn').className = mode === 'grid'
        ? 'p-1.5 rounded-md transition-colors text-white bg-gray-600'
        : 'p-1.5 rounded-md transition-colors text-gray-400';
    document.getElementById('view-list-btn').className = mode === 'list'
        ? 'p-1.5 rounded-md transition-colors text-white bg-gray-600'
        : 'p-1.5 rounded-md transition-colors text-gray-400';
    loadCollection(1);
}

const RARITY_COLORS = {
    common: 'text-gray-400',
    uncommon: 'text-blue-300',
    rare: 'text-yellow-300',
    mythic: 'text-orange-400',
};

const FINISH_LABELS = {
    nonfoil: 'Regular',
    foil: '✦ Foil',
    etched: '◈ Etched',
    glossy: '◉ Glossy',
};

const FINISH_COLORS = {
    nonfoil: 'bg-gray-600 text-gray-300',
    foil: 'bg-blue-700 text-blue-200',
    etched: 'bg-purple-700 text-purple-200',
    glossy: 'bg-yellow-700 text-yellow-200',
};

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
        unique: true,
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

// List mode state — all grouped entries loaded at once, paginated client-side
let listAllGroups = [];

function goToCollPage(n) {
    if (collDisplayMode === 'list') {
        renderCollectionListPage(n);
    } else {
        loadCollection(n);
    }
}

async function loadCollection(page = 1) {
    currentCollPage = page;
    const q = document.getElementById('collection-search')?.value?.trim() || '';

    const container = document.getElementById('collection-grid');
    const isList = collDisplayMode === 'list';

    container.className = isList
        ? 'space-y-1 overflow-y-auto max-h-[calc(100vh-380px)] pr-1'
        : 'grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 gap-3 overflow-y-auto max-h-[calc(100vh-380px)] pr-1';

    container.innerHTML = isList
        ? '<div class="flex justify-center py-8"><div class="spinner w-8 h-8"></div></div>'
        : '<div class="col-span-full flex justify-center py-8"><div class="spinner w-8 h-8"></div></div>';

    if (isList) {
        // Fetch all entries at once so we can group and paginate by unique name client-side
        const params = new URLSearchParams({ page: 1, limit: 500, q });
        if (activeCollectionId !== null) params.set('collection_id', activeCollectionId);
        const res = await API.get(`/api/collection?${params}`);
        if (!res) {
            container.innerHTML = '<p class="text-center text-red-400 py-8">Failed to load collection</p>';
            return;
        }
        document.getElementById('collection-count').textContent = `${res.total_quantity} cards · ${res.unique_names} unique`;

        const groups = new Map();
        for (const entry of res.entries) {
            const name = entry.card.name;
            if (!groups.has(name)) groups.set(name, []);
            groups.get(name).push(entry);
        }
        listAllGroups = [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
        renderCollectionListPage(1);
    } else {
        const params = new URLSearchParams({ page, limit: 24, q });
        if (activeCollectionId !== null) params.set('collection_id', activeCollectionId);
        const res = await API.get(`/api/collection?${params}`);
        if (!res) {
            container.innerHTML = '<p class="col-span-full text-center text-red-400 py-8">Failed to load collection</p>';
            return;
        }
        document.getElementById('collection-count').textContent = `${res.total_quantity} cards · ${res.unique_names} unique`;
        renderCollection(res.entries);
        updateCollectionPagination(res);
    }
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
        const isFoilish = entry.finish && entry.finish !== 'nonfoil';
        const rarityBorder = {
            common: 'border-gray-600',
            uncommon: 'border-slate-400',
            rare: 'border-yellow-500',
            mythic: 'border-orange-500',
        }[card.rarity] || 'border-gray-600';
        const foilBadge = entry.finish === 'foil' ? '✦'
            : entry.finish === 'etched' ? '◈'
            : entry.finish === 'glossy' ? '◉'
            : null;

        return `
            <div class="relative group card-hover cursor-pointer" onclick="openCollectionCardModal(${JSON.stringify(entry).replace(/"/g, '&quot;')})">
                <div class="relative rounded-xl overflow-hidden border-2 ${isFoilish ? 'border-purple-400 shadow-purple-500/20' : rarityBorder} shadow-lg">
                    <img src="${card.image_uri_small || ''}"
                        alt="${card.name}"
                        class="w-full aspect-[63/88] object-cover"
                        loading="lazy"
                        onerror="this.src=''"
                    >
                    ${isFoilish ? '<div class="absolute inset-0 bg-gradient-to-br from-purple-500/20 to-transparent pointer-events-none"></div>' : ''}
                    <!-- Quantity badge -->
                    <div class="absolute top-1.5 right-1.5 bg-black/70 text-white text-xs font-bold px-1.5 py-0.5 rounded-md">
                        ×${entry.quantity}
                    </div>
                    ${foilBadge ? `<div class="absolute top-1.5 left-1.5 bg-purple-600/80 text-white text-xs px-1.5 py-0.5 rounded-md">${foilBadge}</div>` : ''}
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

function renderCollectionListPage(page) {
    currentCollPage = page;
    const container = document.getElementById('collection-grid');

    if (listAllGroups.length === 0) {
        container.innerHTML = `
            <div class="text-center py-12 text-gray-500">
                <svg class="w-16 h-16 mx-auto mb-3 opacity-20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 6h16M4 10h16M4 14h16M4 18h16"/>
                </svg>
                <p class="text-sm">Your collection is empty.</p>
                <p class="text-xs mt-1">Search for cards on the left to add them.</p>
            </div>`;
        document.getElementById('collection-pagination').classList.add('hidden');
        return;
    }

    const PAGE_SIZE = 12;
    const totalPages = Math.ceil(listAllGroups.length / PAGE_SIZE) || 1;
    const start = (page - 1) * PAGE_SIZE;
    const pageGroups = listAllGroups.slice(start, start + PAGE_SIZE);

    container.innerHTML = pageGroups.map(([name, groupEntries], i) => {
        const idx = start + i;
        const totalQty = groupEntries.reduce((sum, e) => sum + e.quantity, 0);
        const variantCount = groupEntries.length;

        return `
            <div class="flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-gray-700/50 border border-transparent hover:border-gray-600 transition-colors">
                <p class="text-sm font-medium text-white flex-1 min-w-0 truncate">${name}</p>
                <div class="flex items-center gap-2 flex-shrink-0 ml-4">
                    <span class="text-sm font-bold text-gray-300">×${totalQty}</span>
                    <button onclick="openVariantModal(${idx})"
                        class="flex items-center gap-1 text-xs text-gray-400 hover:text-white bg-gray-700 hover:bg-gray-600 border border-gray-600 hover:border-gray-500 px-2 py-1 rounded-lg transition-colors">
                        ${variantCount} variant${variantCount !== 1 ? 's' : ''}
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                        </svg>
                    </button>
                </div>
            </div>`;
    }).join('');

    // Update pagination
    const pagination = document.getElementById('collection-pagination');
    const pageInfo = document.getElementById('coll-page-info');
    const prevBtn = document.getElementById('coll-prev');
    const nextBtn = document.getElementById('coll-next');

    if (totalPages <= 1) {
        pagination.classList.add('hidden');
    } else {
        pagination.classList.remove('hidden');
        pageInfo.textContent = `Page ${page} of ${totalPages}`;
        prevBtn.disabled = page <= 1;
        nextBtn.disabled = page >= totalPages;
    }
}

function openVariantModal(idx) {
    const [name, groupEntries] = listAllGroups[idx];
    document.getElementById('variant-modal-title').textContent = name;

    document.getElementById('variant-modal-list').innerHTML = groupEntries.map(entry => {
        const finishLabel = FINISH_LABELS[entry.finish] || entry.finish;
        const finishColor = FINISH_COLORS[entry.finish] || 'bg-gray-700 text-gray-300';
        const setLabel = entry.card.set_name
            ? `${entry.card.set_name} · #${entry.card.collector_number || ''}`
            : (entry.card.set_code || '');
        const entryJson = JSON.stringify(entry).replace(/"/g, '&quot;');
        return `
            <button onclick="closeVariantModal(); openCollectionCardModal(${entryJson})"
                class="w-full text-left flex items-center gap-3 px-4 py-3 hover:bg-gray-700 rounded-lg transition-colors">
                <span class="text-xs px-2 py-0.5 rounded font-medium ${finishColor} flex-shrink-0">${finishLabel}</span>
                <div class="flex-1 min-w-0">
                    ${setLabel ? `<p class="text-sm text-gray-300 truncate">${setLabel}</p>` : ''}
                </div>
                <span class="text-sm font-bold text-white flex-shrink-0">×${entry.quantity}</span>
            </button>`;
    }).join('');

    document.getElementById('variant-modal').classList.remove('hidden');
}

function closeVariantModal() {
    document.getElementById('variant-modal').classList.add('hidden');
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
    if (activeCollectionType === 'external') {
        showFlash('External collections are read-only', 'error');
        return;
    }
    const res = await API.post('/api/collection', {
        card_id: cardId,
        quantity: 1,
        finish: 'nonfoil',
        collection_id: activeCollectionId,
    });
    if (res && res.id) {
        showFlash('Added to collection!', 'success');
        loadCollection(currentCollPage);
    } else {
        showFlash(res?.detail || 'Failed to add card', 'error');
    }
}

async function addToCollectionFromModal() {
    if (!selectedCard) return;
    if (activeCollectionType === 'external') {
        showFlash('External collections are read-only', 'error');
        return;
    }

    const finish = document.getElementById('modal-finish').value;
    const btn = document.getElementById('modal-add-btn');
    btn.disabled = true;
    btn.textContent = 'Adding...';

    const res = await API.post('/api/collection', {
        card_id: selectedCard.scryfall_id,
        quantity: modalQty,
        finish,
        collection_id: activeCollectionId,
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

// ─── Add Card Modal (from version picker) ────────────────────────────────────

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
    document.getElementById('modal-finish').value = 'nonfoil';
    updateModalFinishOptions(card.finishes || []);
    document.getElementById('card-modal').classList.remove('hidden');
}

function closeCardModal() {
    document.getElementById('card-modal').classList.add('hidden');
    selectedCard = null;
}

function adjustModalQty(delta) {
    modalQty = Math.max(1, Math.min(99, modalQty + delta));
    document.getElementById('modal-qty').textContent = modalQty;
}

document.getElementById('card-modal')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeCardModal();
});

// ─── Collection Edit Modal ────────────────────────────────────────────────────

function openCollectionCardModal(entry) {
    editingEntry = entry;
    editingCard = { ...entry.card };
    editModalQty = entry.quantity;

    document.getElementById('edit-modal-card-name').textContent = editingCard.name;
    document.getElementById('edit-modal-card-image').src = editingCard.image_uri_normal || editingCard.image_uri_small || '';
    document.getElementById('edit-modal-mana-cost').textContent = editingCard.mana_cost || '';
    document.getElementById('edit-modal-type').textContent = editingCard.type_line || '';
    document.getElementById('edit-modal-qty').textContent = editModalQty;
    document.getElementById('edit-modal-finish').value = entry.finish || 'nonfoil';
    updateEditModalFinishOptions(editingCard.finishes || []);
    updateEditModalVersionBtn();

    document.getElementById('collection-edit-modal').classList.remove('hidden');
}

function updateEditModalVersionBtn() {
    const label = editingCard.set_name
        ? `${editingCard.set_name} · #${editingCard.collector_number}`
        : (editingCard.set_code || 'Unknown printing');
    document.getElementById('edit-version-btn').textContent = label;
}

function _populateFinishSelect(selectId, finishes, currentValue) {
    const sel = document.getElementById(selectId);
    if (!sel) return;
    const all = ['nonfoil', 'foil', 'etched', 'glossy'];
    const available = finishes && finishes.length ? finishes : all;
    sel.innerHTML = available.map(f =>
        `<option value="${f}">${FINISH_LABELS[f] || f}</option>`
    ).join('');
    // Keep current value if still available, else reset to first option
    sel.value = available.includes(currentValue) ? currentValue : available[0];
}

function updateModalFinishOptions(finishes) {
    const current = document.getElementById('modal-finish')?.value || 'nonfoil';
    _populateFinishSelect('modal-finish', finishes, current);
}

function updateEditModalFinishOptions(finishes) {
    const current = document.getElementById('edit-modal-finish')?.value || 'nonfoil';
    _populateFinishSelect('edit-modal-finish', finishes, current);
}

function closeEditModal() {
    document.getElementById('collection-edit-modal').classList.add('hidden');
    editingEntry = null;
    editingCard = null;
}

function adjustEditModalQty(delta) {
    editModalQty = Math.max(1, Math.min(99, editModalQty + delta));
    document.getElementById('edit-modal-qty').textContent = editModalQty;
}

async function saveCollectionEdit() {
    if (!editingEntry) return;

    const finish = document.getElementById('edit-modal-finish').value;
    const body = { quantity: editModalQty, finish };
    if (editingCard.scryfall_id !== editingEntry.card.scryfall_id) {
        body.card_id = editingCard.scryfall_id;
    }

    const res = await API.put(`/api/collection/${editingEntry.id}`, body);
    if (res && res.id) {
        showFlash('Collection updated!', 'success');
        closeEditModal();
        loadCollection(currentCollPage);
    } else {
        showFlash(res?.detail || 'Failed to update', 'error');
    }
}

async function removeFromCollectionModal() {
    if (!editingEntry) return;
    const res = await API.delete(`/api/collection/${editingEntry.id}`);
    if (res) {
        showFlash('Removed from collection', 'info');
        closeEditModal();
        loadCollection(currentCollPage);
    }
}

// ─── Version Picker ───────────────────────────────────────────────────────────

function openVersionPickerFromAddModal() {
    versionPickerMode = 'add';
    openVersionPicker(selectedCard.name);
}

function openVersionPickerForChange() {
    versionPickerMode = 'change';
    openVersionPicker(editingCard.name);
}

async function openVersionPicker(cardName) {
    const modal = document.getElementById('version-picker-modal');
    const grid = document.getElementById('version-picker-grid');
    const title = document.getElementById('version-picker-title');

    title.textContent = cardName;
    grid.innerHTML = '<div class="col-span-full flex justify-center py-4"><div class="spinner w-8 h-8"></div></div>';
    modal.classList.remove('hidden');

    const cards = await API.get(`/api/cards/printings?name=${encodeURIComponent(cardName)}`);
    if (!cards || cards.length === 0) {
        grid.innerHTML = '<p class="col-span-full text-center text-gray-500 py-4">No printings found</p>';
        return;
    }

    grid.innerHTML = cards.map(card => {
        const rarityColor = RARITY_COLORS[card.rarity] || 'text-gray-400';
        const finishes = card.finishes && card.finishes.length ? card.finishes : ['nonfoil'];
        const cardJson = JSON.stringify(card).replace(/"/g, '&quot;');
        const finishBadges = finishes.map(f => `
            <button onclick="event.stopPropagation(); selectPrinting(${cardJson}, '${f}')"
                class="text-xs px-1.5 py-0.5 rounded ${FINISH_COLORS[f] || 'bg-gray-600 text-gray-300'} hover:opacity-80 transition-opacity"
                title="${FINISH_LABELS[f] || f}">
                ${FINISH_LABELS[f] || f}
            </button>
        `).join('');
        return `
            <div class="${finishes.length === 1 ? 'cursor-pointer' : ''} group" ${finishes.length === 1 ? `onclick="selectPrinting(${cardJson}, '${finishes[0]}')"` : ''}>
                <div class="relative rounded-lg overflow-hidden border-2 border-gray-600 group-hover:border-purple-400 transition-colors">
                    <img src="${card.image_uri_small || ''}" alt="${card.name}"
                        class="w-full aspect-[63/88] object-cover"
                        onerror="this.src=''">
                </div>
                <p class="text-xs text-gray-400 mt-1 truncate">${card.set_name || card.set_code || ''}</p>
                <p class="text-xs ${rarityColor} mb-1">#${card.collector_number || ''}</p>
                <div class="flex flex-wrap gap-1">${finishBadges}</div>
            </div>
        `;
    }).join('');
}

function closeVersionPicker() {
    document.getElementById('version-picker-modal').classList.add('hidden');
}

function selectPrinting(card, finish) {
    closeVersionPicker();
    if (versionPickerMode === 'add') {
        selectedCard = card;
        document.getElementById('modal-card-name').textContent = card.name;
        document.getElementById('modal-card-image').src = card.image_uri_normal || card.image_uri_small || '';
        document.getElementById('modal-mana-cost').textContent = card.mana_cost || '';
        document.getElementById('modal-type').textContent = card.type_line || '';
        document.getElementById('modal-oracle').textContent = card.oracle_text || '';
        document.getElementById('modal-set').textContent = card.set_name ? `${card.set_name} · ${card.collector_number || ''}` : '';
        document.getElementById('modal-rarity').textContent = card.rarity ? card.rarity.charAt(0).toUpperCase() + card.rarity.slice(1) : '';
        updateModalFinishOptions(card.finishes || []);
        if (finish) document.getElementById('modal-finish').value = finish;
    } else if (versionPickerMode === 'change') {
        editingCard = card;
        updateEditModalVersionBtn();
        updateEditModalFinishOptions(card.finishes || []);
        if (finish) document.getElementById('edit-modal-finish').value = finish;
        document.getElementById('edit-modal-card-image').src = card.image_uri_normal || card.image_uri_small || '';
    }
}

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
    const importUrl = activeCollectionId
        ? `/api/collection/import?collection_id=${activeCollectionId}`
        : '/api/collection/import';
    let res;
    try {
        const response = await fetch(importUrl, {
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

// ─── Collection Management ────────────────────────────────────────────────────

async function loadCollections() {
    const collections = await API.get('/api/collections');
    if (!collections) return;

    collectionsCache = collections;
    const select = document.getElementById('collection-select');
    const totalCards = collections.reduce((sum, c) => sum + (c.entry_count || 0), 0);
    const totalUnique = collections.reduce((sum, c) => sum + (c.unique_card_count || 0), 0);
    const allOption = `<option value="0">All Collections (${totalCards} cards, ${totalUnique} unique)</option>`;
    select.innerHTML = allOption + collections.map(c => {
        const label = c.type === 'external'
            ? `${c.name} (${c.entry_count} cards, ${c.unique_card_count} unique) [${c.external_source || 'external'}]`
            : `${c.name} (${c.entry_count} cards, ${c.unique_card_count} unique)`;
        return `<option value="${c.id}">${label}</option>`;
    }).join('');

    // Default to All Collections view
    if (!activeCollectionId) {
        activeCollectionId = 0;
        activeCollectionType = 'aggregate';
    }

    select.value = activeCollectionId ?? 0;

    updateCollectionUI();
    loadCollection(1);
}

function updateCollectionUI() {
    const isAggregate = activeCollectionId === 0;
    const coll = isAggregate ? null : collectionsCache.find(c => c.id === activeCollectionId);

    if (!isAggregate && !coll) return;

    activeCollectionType = isAggregate ? 'aggregate' : coll.type;

    const isExternal = !isAggregate && coll.type === 'external';
    const syncBtn = document.getElementById('sync-btn');
    const lastSyncedLabel = document.getElementById('last-synced-label');
    const externalBadge = document.getElementById('external-badge');
    const importBtn = document.getElementById('import-btn');
    const deleteBtn = document.getElementById('delete-collection-btn');
    const myCardsTitle = document.getElementById('my-cards-title');

    syncBtn?.classList.toggle('hidden', !isExternal);
    externalBadge?.classList.toggle('hidden', !isExternal);
    importBtn?.classList.toggle('hidden', isExternal || isAggregate);
    deleteBtn?.classList.toggle('hidden', isAggregate);

    if (myCardsTitle) myCardsTitle.textContent = isAggregate ? 'All Collections' : coll.name;

    if (isExternal && coll.last_synced) {
        const d = new Date(coll.last_synced);
        lastSyncedLabel.textContent = `Synced ${d.toLocaleDateString()} ${d.toLocaleTimeString()}`;
        lastSyncedLabel.classList.remove('hidden');
    } else {
        lastSyncedLabel?.classList.add('hidden');
    }
}

function onCollectionChange() {
    const select = document.getElementById('collection-select');
    activeCollectionId = parseInt(select.value, 10);
    updateCollectionUI();
    loadCollection(1);
}

async function syncActiveCollection() {
    const btn = document.getElementById('sync-btn');
    if (!activeCollectionId) return;
    btn.disabled = true;
    btn.textContent = 'Syncing...';

    const res = await API.post(`/api/collections/${activeCollectionId}/sync`, {});
    btn.disabled = false;
    btn.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg> Sync`;

    if (res && res.message) {
        const skipped = res.not_found?.length || 0;
        await loadCollections();
        const updatedColl = collectionsCache.find(c => c.id === activeCollectionId);
        const totalCards = updatedColl ? updatedColl.entry_count : res.added;
        showFlash(`Synced "${res.source_name}": ${totalCards} cards${skipped ? `, ${skipped} not found` : ''}`, 'success');
    } else {
        showFlash(res?.detail || 'Sync failed', 'error');
    }
}

async function deleteActiveCollection() {
    if (!activeCollectionId) return;
    const coll = collectionsCache.find(c => c.id === activeCollectionId);
    if (!coll) return;
    if (!confirm(`Delete collection "${coll.name}"? This will remove all ${coll.entry_count} cards in it.`)) return;

    const res = await API.delete(`/api/collections/${activeCollectionId}`);
    if (res && res.message) {
        showFlash('Collection deleted', 'info');
        activeCollectionId = null;
        await loadCollections();
    } else {
        showFlash(res?.detail || 'Failed to delete collection', 'error');
    }
}

// ─── New Collection Modal ─────────────────────────────────────────────────────

function openNewCollectionModal() {
    document.getElementById('new-coll-name').value = '';
    document.getElementById('new-coll-description').value = '';
    document.querySelector('input[name="new-coll-type"][value="personal"]').checked = true;
    document.getElementById('new-coll-url').value = '';
    document.getElementById('external-fields').classList.add('hidden');
    document.getElementById('new-collection-modal').classList.remove('hidden');
    document.getElementById('new-coll-name').focus();
}

function closeNewCollectionModal() {
    document.getElementById('new-collection-modal').classList.add('hidden');
}

function toggleExternalFields() {
    const type = document.querySelector('input[name="new-coll-type"]:checked')?.value;
    document.getElementById('external-fields').classList.toggle('hidden', type !== 'external');
}

const _SOURCE_HINTS = {
    moxfield: {
        placeholder: 'https://www.moxfield.com/binders/...',
        hint: 'Paste a public Moxfield binder URL.',
    },
    manabox: {
        placeholder: 'https://manabox.app/decks/...',
        hint: 'Paste a public ManaBox deck URL.',
    },
};

function updateUrlPlaceholder() {
    const source = document.getElementById('new-coll-source').value;
    const cfg = _SOURCE_HINTS[source] || _SOURCE_HINTS.moxfield;
    document.getElementById('new-coll-url').placeholder = cfg.placeholder;
    document.getElementById('new-coll-url-hint').textContent = cfg.hint;
}

async function submitNewCollection() {
    const name = document.getElementById('new-coll-name').value.trim();
    if (!name) {
        showFlash('Please enter a collection name', 'error');
        return;
    }

    const type = document.querySelector('input[name="new-coll-type"]:checked')?.value || 'personal';
    const description = document.getElementById('new-coll-description').value.trim();
    const externalSource = type === 'external' ? document.getElementById('new-coll-source').value : null;
    const externalUrl = type === 'external' ? document.getElementById('new-coll-url').value.trim() : null;

    if (type === 'external' && !externalUrl) {
        showFlash('Please enter the external deck URL', 'error');
        return;
    }

    const res = await API.post('/api/collections', {
        name,
        description: description || null,
        type,
        external_source: externalSource,
        external_url: externalUrl,
    });

    if (res && res.id) {
        closeNewCollectionModal();
        activeCollectionId = res.id;
        await loadCollections();
        if (type === 'external') {
            showFlash(`Collection created. Click Sync to load cards from ${externalSource}.`, 'success');
        } else {
            showFlash('Collection created!', 'success');
        }
    } else {
        showFlash(res?.detail || 'Failed to create collection', 'error');
    }
}

// ─── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    const check = setInterval(() => {
        if (window.currentUser !== undefined) {
            clearInterval(check);
            if (window.currentUser) {
                loadCollections();
            }
        }
    }, 100);
});
