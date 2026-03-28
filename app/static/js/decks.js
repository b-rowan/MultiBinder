/**
 * Deck builder JavaScript for MultiBinder
 */

const deckId = window.location.pathname.split('/').pop();
let currentDeck = null;
let currentUser = null;
let isOwner = false;
let selectedBoard = 'main';
let deckSearchTimeout = null;
let availabilityData = null;

const FORMAT_COLORS = {
    commander: 'text-purple-300 bg-purple-900/40 border-purple-800',
    standard: 'text-green-300 bg-green-900/40 border-green-800',
    modern: 'text-blue-300 bg-blue-900/40 border-blue-800',
    legacy: 'text-yellow-300 bg-yellow-900/40 border-yellow-800',
    vintage: 'text-red-300 bg-red-900/40 border-red-800',
    pioneer: 'text-cyan-300 bg-cyan-900/40 border-cyan-800',
    pauper: 'text-gray-300 bg-gray-900/40 border-gray-700',
    casual: 'text-pink-300 bg-pink-900/40 border-pink-800',
};

// ─── Load Deck ────────────────────────────────────────────────────────────────

async function loadDeck() {
    const res = await API.get(`/api/decks/${deckId}`);
    if (!res || res.detail) {
        document.getElementById('deck-title').textContent = 'Deck not found';
        return;
    }

    currentDeck = res;
    currentUser = window.currentUser;
    isOwner = res.owner.id === currentUser?.id;

    // Update header
    document.getElementById('deck-title').textContent = res.name;
    document.getElementById('deck-description').textContent = res.description || '';
    document.getElementById('deck-meta').textContent =
        `Owner: ${res.owner.username} · Created ${new Date(res.created_at).toLocaleDateString()}`;

    const formatBadge = document.getElementById('deck-format-badge');
    const formatClass = FORMAT_COLORS[res.format] || FORMAT_COLORS.casual;
    formatBadge.textContent = res.format.charAt(0).toUpperCase() + res.format.slice(1);
    formatBadge.className = `text-xs px-2.5 py-1 rounded-full border ${formatClass}`;

    if (res.is_shared) {
        document.getElementById('deck-shared-badge').classList.remove('hidden');
    }

    // Show/hide owner actions
    if (!isOwner) {
        document.getElementById('edit-deck-btn').style.display = 'none';
        document.getElementById('delete-deck-btn').style.display = 'none';
        document.getElementById('add-collab-section').style.display = 'none';
    } else {
        document.getElementById('add-collab-section').classList.remove('hidden');
    }

    // Show availability panel
    document.getElementById('availability-panel').style.display = '';

    // Render cards
    renderDeckCards(res.cards);

    // Render collaborators
    renderCollaborators(res.collaborators, res.owner);

    // Load availability automatically
    loadAvailability(true);
}

// ─── Render Cards ─────────────────────────────────────────────────────────────

function getAvailabilityStatus(cardId) {
    if (!availabilityData) return null;
    return availabilityData.find(a => a.card_id === cardId);
}

function renderDeckCards(cards) {
    const mainCards = cards.filter(c => c.board === 'main');
    const sideCards = cards.filter(c => c.board === 'side');
    const cmdrCards = cards.filter(c => c.board === 'commander');

    const mainCount = mainCards.reduce((sum, c) => sum + c.quantity, 0);
    const sideCount = sideCards.reduce((sum, c) => sum + c.quantity, 0);
    const cmdrCount = cmdrCards.length;
    const totalCount = mainCount + sideCount + cmdrCount;

    document.getElementById('total-card-count').textContent = totalCount;
    document.getElementById('main-count').textContent = `Main: ${mainCount}`;
    document.getElementById('side-count').textContent = `Side: ${sideCount}`;

    if (cmdrCards.length > 0) {
        document.getElementById('commander-section').classList.remove('hidden');
        document.getElementById('cmdr-count').classList.remove('hidden');
        document.getElementById('cmdr-count').textContent = `Commander: ${cmdrCount}`;
    }

    renderCardGrid('commander-cards', cmdrCards);
    renderCardGrid('main-cards', mainCards);
    renderCardGrid('side-cards', sideCards);
}

function renderCardGrid(containerId, cards) {
    const container = document.getElementById(containerId);

    if (!cards || cards.length === 0) {
        if (containerId === 'side-cards') {
            container.innerHTML = '<p class="col-span-full text-sm text-gray-500 py-4 text-center">No sideboard cards</p>';
        } else if (containerId === 'commander-cards') {
            container.innerHTML = '';
        } else {
            container.innerHTML = '<p class="col-span-full text-sm text-gray-500 py-4 text-center">No cards yet. Search and add cards on the left.</p>';
        }
        return;
    }

    container.innerHTML = cards.map(dc => {
        const card = dc.card;
        const avail = getAvailabilityStatus(card.scryfall_id);
        const borderColor = avail
            ? (avail.status === 'owned' ? 'border-green-500'
                : avail.status === 'collab_owned' ? 'border-blue-500'
                : avail.status === 'in_use' ? 'border-purple-500'
                : avail.status === 'partial' ? 'border-yellow-400'
                : 'border-red-500')
            : 'border-gray-600';

        return `
            <div class="relative group card-hover">
                <div class="relative rounded-xl overflow-hidden border-2 ${borderColor} shadow-lg">
                    <img src="${card.image_uri_small || ''}"
                        alt="${card.name}"
                        class="w-full aspect-[63/88] object-cover"
                        loading="lazy"
                        onerror="this.src=''">

                    <div class="absolute top-1.5 right-1.5 bg-black/70 text-white text-xs font-bold px-1.5 py-0.5 rounded-md">
                        ×${dc.quantity}
                    </div>
                    <!-- Hover controls -->
                    <div class="absolute inset-0 bg-black/0 group-hover:bg-black/50 transition-colors flex items-end justify-center opacity-0 group-hover:opacity-100 pb-2">
                        <div class="flex gap-1">
                            <button onclick="adjustDeckCardQty(${dc.id}, ${dc.quantity}, -1)"
                                class="w-7 h-7 bg-gray-800/90 hover:bg-red-800 text-white rounded-lg text-sm font-bold transition-colors">−</button>
                            <button onclick="adjustDeckCardQty(${dc.id}, ${dc.quantity}, 1)"
                                class="w-7 h-7 bg-gray-800/90 hover:bg-green-800 text-white rounded-lg text-sm font-bold transition-colors">+</button>
                            <button onclick="removeDeckCard(${dc.id})"
                                class="w-7 h-7 bg-gray-800/90 hover:bg-red-900 text-red-400 rounded-lg flex items-center justify-center transition-colors">
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

// ─── Board Selector ───────────────────────────────────────────────────────────

function setBoard(board) {
    selectedBoard = board;
    ['main', 'side', 'commander'].forEach(b => {
        const btn = document.getElementById(`board-${b}`);
        if (b === board) {
            btn.className = 'flex-1 text-xs py-1.5 rounded-lg bg-purple-700 text-white border border-purple-600 transition-colors board-btn';
        } else {
            btn.className = 'flex-1 text-xs py-1.5 rounded-lg bg-gray-700 text-gray-300 border border-gray-600 transition-colors board-btn';
        }
    });
}

// ─── Card Search (for deck builder) ──────────────────────────────────────────

async function searchCardsForDeck(q) {
    if (!q || q.length < 2) {
        document.getElementById('deck-search-results').innerHTML =
            '<p class="text-xs text-gray-500 text-center py-3">Type to search cards</p>';
        return;
    }

    const container = document.getElementById('deck-search-results');
    container.innerHTML = '<div class="flex justify-center py-2"><div class="spinner w-5 h-5"></div></div>';

    const res = await API.get(`/api/cards/search?q=${encodeURIComponent(q)}&limit=15&unique=true`);
    if (!res) {
        container.innerHTML = '<p class="text-xs text-red-400 text-center py-2">Search failed</p>';
        return;
    }

    if (!res.cards?.length) {
        container.innerHTML = '<p class="text-xs text-gray-500 text-center py-3">No cards found</p>';
        return;
    }

    container.innerHTML = res.cards.map(card => `
        <div class="flex items-center gap-2 p-1.5 rounded-lg hover:bg-gray-700 cursor-pointer transition-colors group border border-transparent hover:border-gray-600"
            onclick="openVersionPicker(${JSON.stringify(card.name).replace(/"/g, '&quot;')})">
            <img src="${card.image_uri_small || ''}"
                alt="${card.name}"
                class="w-8 h-11 rounded object-cover flex-shrink-0"
                onerror="this.src=''">
            <div class="flex-1 min-w-0">
                <p class="text-xs font-medium text-white truncate group-hover:text-purple-300">${card.name}</p>
                <p class="text-xs text-gray-500 truncate">${card.type_line || ''}</p>
                ${card.mana_cost ? `<p class="text-xs text-gray-400">${card.mana_cost}</p>` : ''}
            </div>
            <button class="flex-shrink-0 w-6 h-6 bg-purple-700/50 hover:bg-purple-600 text-white rounded-md flex items-center justify-center transition-colors">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
                </svg>
            </button>
        </div>
    `).join('');
}

// ─── Deck Card Operations ─────────────────────────────────────────────────────

async function addCardToDeck(cardId, cardName) {
    const res = await API.post(`/api/decks/${deckId}/cards`, {
        card_id: cardId,
        quantity: 1,
        board: selectedBoard,
    });

    if (res && res.id) {
        showFlash(`Added ${cardName} to ${selectedBoard}board`, 'success');
        loadDeck();
    } else {
        showFlash(res?.detail || 'Failed to add card', 'error');
    }
}

async function adjustDeckCardQty(deckCardId, currentQty, delta) {
    const newQty = currentQty + delta;
    if (newQty <= 0) {
        await removeDeckCard(deckCardId);
        return;
    }

    const res = await API.put(`/api/decks/${deckId}/cards/${deckCardId}`, { quantity: newQty });
    if (res) loadDeck();
}

async function removeDeckCard(deckCardId) {
    const res = await API.delete(`/api/decks/${deckId}/cards/${deckCardId}`);
    if (res) {
        showFlash('Card removed', 'info');
        loadDeck();
    }
}

async function deleteDeck() {
    if (!confirm(`Delete "${currentDeck?.name}"? This cannot be undone.`)) return;

    const res = await API.delete(`/api/decks/${deckId}`);
    if (res) {
        showFlash('Deck deleted', 'info');
        window.location.href = '/decks';
    } else {
        showFlash('Failed to delete deck', 'error');
    }
}

// ─── Edit Deck ────────────────────────────────────────────────────────────────

function showEditModal() {
    if (!currentDeck) return;
    document.getElementById('edit-deck-name').value = currentDeck.name;
    document.getElementById('edit-deck-format').value = currentDeck.format;
    document.getElementById('edit-deck-desc').value = currentDeck.description || '';
    document.getElementById('edit-deck-modal').classList.remove('hidden');
}

function hideEditModal() {
    document.getElementById('edit-deck-modal').classList.add('hidden');
}

document.getElementById('edit-deck-modal')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) hideEditModal();
});

document.getElementById('edit-deck-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('edit-deck-name').value.trim();
    const format = document.getElementById('edit-deck-format').value;
    const description = document.getElementById('edit-deck-desc').value.trim();

    const res = await API.put(`/api/decks/${deckId}`, { name, format, description });
    if (res && res.id) {
        showFlash('Deck updated!', 'success');
        hideEditModal();
        loadDeck();
    } else {
        showFlash('Failed to update deck', 'error');
    }
});

// ─── Collaborators ────────────────────────────────────────────────────────────

function renderCollaborators(collaborators, owner) {
    const container = document.getElementById('collaborator-list');

    if (!collaborators.length) {
        container.innerHTML = `
            <div class="flex items-center gap-2 p-2 rounded-lg bg-gray-900/50">
                <div class="w-7 h-7 rounded-full bg-purple-800 flex items-center justify-center text-xs font-bold text-white">${owner.username[0].toUpperCase()}</div>
                <div class="flex-1 min-w-0">
                    <p class="text-xs font-medium text-white">${owner.username}</p>
                    <p class="text-xs text-gray-500">Owner</p>
                </div>
            </div>
            <p class="text-xs text-gray-500 text-center py-1">No collaborators</p>`;
        return;
    }

    const ownerHtml = `
        <div class="flex items-center gap-2 p-2 rounded-lg bg-gray-900/50">
            <div class="w-7 h-7 rounded-full bg-purple-800 flex items-center justify-center text-xs font-bold text-white">${owner.username[0].toUpperCase()}</div>
            <div class="flex-1 min-w-0">
                <p class="text-xs font-medium text-white">${owner.username}</p>
                <p class="text-xs text-gray-500">Owner</p>
            </div>
        </div>`;

    const collabsHtml = collaborators.map(c => `
        <div class="flex items-center gap-2 p-2 rounded-lg bg-gray-900/50 group">
            <div class="w-7 h-7 rounded-full bg-blue-800 flex items-center justify-center text-xs font-bold text-white">${c.username[0].toUpperCase()}</div>
            <div class="flex-1 min-w-0">
                <p class="text-xs font-medium text-white">${c.username}</p>
                <p class="text-xs text-gray-500">Collaborator</p>
            </div>
            ${isOwner ? `
            <button onclick="removeCollaborator(${c.id})"
                class="opacity-0 group-hover:opacity-100 w-5 h-5 text-red-400 hover:text-red-300 transition-all">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
            </button>` : ''}
        </div>`).join('');

    container.innerHTML = ownerHtml + collabsHtml;
}

async function addCollaborator() {
    const username = document.getElementById('collab-username').value.trim();
    if (!username) return;

    const res = await API.post(`/api/decks/${deckId}/collaborators`, { username });
    if (res && res.message) {
        showFlash(res.message, 'success');
        document.getElementById('collab-username').value = '';
        loadDeck();
    } else {
        showFlash(res?.detail || 'Failed to add collaborator', 'error');
    }
}

async function removeCollaborator(userId) {
    const res = await API.delete(`/api/decks/${deckId}/collaborators/${userId}`);
    if (res) {
        showFlash('Collaborator removed', 'info');
        loadDeck();
    }
}

// Enter key for collaborator input
document.getElementById('collab-username')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') addCollaborator();
});

// ─── Availability ─────────────────────────────────────────────────────────────

async function loadAvailability(silent = false) {
    const res = await API.get(`/api/decks/${deckId}/availability`);
    if (!res) return;

    availabilityData = res.availability;

    // Update summary
    const owned = availabilityData.filter(a => a.status === 'owned').length;
    const inUse = availabilityData.filter(a => a.status === 'in_use').length;
    const partial = availabilityData.filter(a => a.status === 'partial').length;
    const missing = availabilityData.filter(a => a.status === 'missing').length;

    const parts = [`${owned} owned`];
    if (inUse > 0) parts.push(`${inUse} in use`);
    parts.push(`${partial} partial`, `${missing} missing`);
    document.getElementById('availability-summary').textContent = parts.join(' · ');

    // Re-render cards with availability dots
    if (currentDeck) renderDeckCards(currentDeck.cards);

    if (!silent) showFlash('Availability updated', 'info');
}

// ─── Export ───────────────────────────────────────────────────────────────────

function showExportModal() {
    if (!currentDeck) return;

    const lines = [];

    const cmdrCards = currentDeck.cards.filter(c => c.board === 'commander');
    const mainCards = currentDeck.cards.filter(c => c.board === 'main');
    const sideCards = currentDeck.cards.filter(c => c.board === 'side');

    if (cmdrCards.length) {
        lines.push('// Commander');
        cmdrCards.forEach(dc => lines.push(`1 ${dc.card.name}`));
        lines.push('');
    }

    if (mainCards.length) {
        lines.push('// Mainboard');
        mainCards.forEach(dc => lines.push(`${dc.quantity} ${dc.card.name}`));
        lines.push('');
    }

    if (sideCards.length) {
        lines.push('// Sideboard');
        sideCards.forEach(dc => lines.push(`${dc.quantity} ${dc.card.name}`));
    }

    document.getElementById('export-text').value = lines.join('\n');
    document.getElementById('export-modal').classList.remove('hidden');
}

function copyExport() {
    const text = document.getElementById('export-text').value;
    navigator.clipboard.writeText(text).then(() => {
        showFlash('Deck list copied to clipboard!', 'success');
    }).catch(() => {
        // Fallback
        document.getElementById('export-text').select();
        document.execCommand('copy');
        showFlash('Deck list copied!', 'success');
    });
}

document.getElementById('export-modal')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) e.currentTarget.classList.add('hidden');
});

// ─── Import ───────────────────────────────────────────────────────────────────

function showImportModal() {
    document.getElementById('import-deck-text').value = '';
    document.getElementById('import-replace').checked = false;
    document.getElementById('import-deck-results').classList.add('hidden');
    document.getElementById('import-deck-notfound-box').classList.add('hidden');
    document.getElementById('import-deck-btn').disabled = false;
    document.getElementById('import-deck-btn').textContent = 'Import';
    document.getElementById('import-deck-modal').classList.remove('hidden');
}

function hideImportModal() {
    document.getElementById('import-deck-modal').classList.add('hidden');
}

async function submitDeckImport() {
    const text = document.getElementById('import-deck-text').value.trim();
    if (!text) return;

    const replace = document.getElementById('import-replace').checked;
    const btn = document.getElementById('import-deck-btn');
    btn.disabled = true;
    btn.textContent = 'Importing...';

    const res = await API.post(`/api/decks/${deckId}/import`, { list: text, replace });

    btn.disabled = false;
    btn.textContent = 'Import';

    if (!res || res.detail) {
        showFlash(res?.detail || 'Import failed', 'error');
        return;
    }

    document.getElementById('import-deck-added').textContent = res.added;
    document.getElementById('import-deck-updated').textContent = res.updated;
    document.getElementById('import-deck-results').classList.remove('hidden');

    if (res.not_found && res.not_found.length > 0) {
        const box = document.getElementById('import-deck-notfound-box');
        box.innerHTML = `<p class="font-medium text-red-400 mb-1">Not found (${res.not_found.length}):</p>` +
            res.not_found.map(l => `<p>${l}</p>`).join('');
        box.classList.remove('hidden');
    }

    if (res.added > 0 || res.updated > 0) {
        showFlash(`Import complete: ${res.added} added, ${res.updated} updated`, 'success');
        loadDeck();
    }
}

document.getElementById('import-deck-modal')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) hideImportModal();
});

// ─── Version Picker ───────────────────────────────────────────────────────────

const RARITY_COLORS = {
    common: 'text-gray-400',
    uncommon: 'text-blue-300',
    rare: 'text-yellow-300',
    mythic: 'text-orange-400',
};

async function openVersionPicker(cardName) {
    const modal = document.getElementById('version-picker-modal');
    document.getElementById('version-picker-title').textContent = cardName;
    document.getElementById('version-picker-grid').innerHTML =
        '<div class="col-span-full flex justify-center py-6"><div class="spinner w-6 h-6"></div></div>';
    modal.classList.remove('hidden');

    const printings = await API.get(`/api/cards/printings?name=${encodeURIComponent(cardName)}`);

    if (!printings || !printings.length) {
        document.getElementById('version-picker-grid').innerHTML =
            '<p class="col-span-full text-sm text-gray-400 text-center py-4">No printings found</p>';
        return;
    }

    document.getElementById('version-picker-grid').innerHTML = printings.map(card => `
        <div class="cursor-pointer group" onclick="selectPrinting('${card.scryfall_id}', ${JSON.stringify(card.name).replace(/"/g, '&quot;')})">
            <div class="rounded-lg overflow-hidden border-2 border-transparent group-hover:border-purple-500 transition-colors">
                <img src="${card.image_uri_small || ''}" alt="${card.name}"
                    class="w-full aspect-[63/88] object-cover"
                    onerror="this.src=''">
            </div>
            <p class="text-xs text-gray-300 truncate mt-1">${card.set_name || card.set_code || ''}</p>
            <p class="text-xs ${RARITY_COLORS[card.rarity] || 'text-gray-500'}">#${card.collector_number || '?'} · ${card.rarity || ''}</p>
        </div>
    `).join('');
}

function closeVersionPicker() {
    document.getElementById('version-picker-modal').classList.add('hidden');
}

function selectPrinting(scryfallId, cardName) {
    closeVersionPicker();
    addCardToDeck(scryfallId, cardName);
}

// ─── Search Input ─────────────────────────────────────────────────────────────

document.getElementById('deck-card-search')?.addEventListener('input', (e) => {
    clearTimeout(deckSearchTimeout);
    deckSearchTimeout = setTimeout(() => searchCardsForDeck(e.target.value.trim()), 400);
});

// ─── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    const check = setInterval(() => {
        if (window.currentUser !== undefined) {
            clearInterval(check);
            if (window.currentUser) {
                loadDeck();
            }
        }
    }, 100);
});
