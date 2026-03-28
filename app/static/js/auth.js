/**
 * Auth helpers for MultiBinder
 */

async function login(username, password) {
    const res = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });

    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.detail || 'Login failed');
    }

    localStorage.setItem('token', data.access_token);
    return data;
}

async function register(username, email, password) {
    const res = await fetch('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password }),
    });

    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.detail || 'Registration failed');
    }

    localStorage.setItem('token', data.access_token);
    return data;
}

function logout() {
    localStorage.removeItem('token');
    window.currentUser = null;
    window.location.href = '/login';
}

async function getCurrentUser() {
    const token = localStorage.getItem('token');
    if (!token) return null;

    const res = await fetch('/auth/me', {
        headers: { 'Authorization': `Bearer ${token}` },
    });

    if (!res.ok) {
        if (res.status === 401) {
            localStorage.removeItem('token');
        }
        return null;
    }

    return await res.json();
}

function checkAuth() {
    const token = localStorage.getItem('token');
    if (!token) {
        const publicPages = ['/login', '/register'];
        if (!publicPages.includes(window.location.pathname)) {
            window.location.href = '/login';
        }
        return false;
    }
    return true;
}

function isLoggedIn() {
    return !!localStorage.getItem('token');
}
